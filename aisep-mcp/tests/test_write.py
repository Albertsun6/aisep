"""S4a: write layer and the add_element / add_relationship / set_labels tools (docs/mcp-interface.md §5.1-5.3, §5.10,
§3.4). Acceptance: T6, T7, T8, T9, T11, T12, T13 (lock / conflict / restore / kill / known-limitation / symlink parts),
T41, T42."""
import glob, hashlib, inspect, os, re, signal, subprocess, sys, textwrap

import pytest

from conftest import ROOT, commit_all, git
from aisep import core, diff, gitio, tools, write_tools as W, writer
from aisep.errors import AisepError

CFG = tools.Config()
M = "https://aisep.example/model/procurement/"
P = "models/procurement/"
DIRECT = "\n:quoteApproval am4:accesses :quotation .\n"  # an unrelated planted L1 Violation (direct triple)


def snap(repo):
    return {f: hashlib.sha256(open(f, "rb").read()).hexdigest()
            for f in sorted(glob.glob(os.path.join(str(repo), "models", "**", "*"), recursive=True)) if os.path.isfile(f)}


def raises(code, fn, *a, **kw):
    with pytest.raises(AisepError) as e:
        fn(*a, **kw)
    assert e.value.code == code, (e.value.code, e.value.message)
    return e.value


def unchanged(repo, code, fn, *a, **kw):
    """T6: a rejected write leaves every model file byte-identical."""
    before = snap(repo)
    e = raises(code, fn, *a, repo=str(repo), **kw)
    assert snap(repo) == before, code
    return e


def text(repo, f="am4.ttl"):
    return open(os.path.join(str(repo), P, f), encoding="utf-8").read()


def append(repo, s, f="am4.ttl"):
    with open(os.path.join(str(repo), P, f), "a", encoding="utf-8") as fh:
        fh.write(s)


# ---------------------------------------------------------------- T6: every rejection leaves the files untouched

def test_T6_add_element_rejections(repo):
    unchanged(repo, "MODEL_NOT_FOUND", W.model_add_element, CFG, "nope", "am4:BusinessObject", "x", slug="x")
    e = unchanged(repo, "UNKNOWN_TYPE", W.model_add_element, CFG, "procurement", "am4:BusinessObjekt", "x", slug="x")
    assert "am4:BusinessObject" in e.details["candidates"]
    unchanged(repo, "ABSTRACT_TYPE", W.model_add_element, CFG, "procurement", "arch:Element", "x", slug="x")
    unchanged(repo, "INVALID_ARGUMENT", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x")
    unchanged(repo, "INVALID_ARGUMENT", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x", slug="1bad")
    unchanged(repo, "INVALID_ARGUMENT", W.model_add_element, CFG, "procurement", "am4:Access", "x", slug="x")
    unchanged(repo, "INVALID_ARGUMENT", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "", slug="x")
    e = unchanged(repo, "IRI_EXISTS", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "供应商", slug="supplier")
    assert e.details["existing"]["types"] == ["am4:Role"]
    unchanged(repo, "WRITE_REJECTED", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x", slug="x",
              attributes=[{"predicate": "aisep:undeclaredThing", "value": {"value": "v"}}])


def test_T6_add_relationship_and_set_labels_rejections(repo):
    unchanged(repo, "ELEMENT_NOT_FOUND", W.model_add_relationship, CFG, "am4:Access", "procurement:nope", "procurement:quotation")
    unchanged(repo, "UNKNOWN_TYPE", W.model_add_relationship, CFG, "am4:Acess", "procurement:quoteApproval", "procurement:quotation")
    unchanged(repo, "INVALID_ARGUMENT", W.model_add_relationship, CFG, "am4:BusinessObject", "procurement:quoteApproval",
              "procurement:quotation")
    unchanged(repo, "ELEMENT_NOT_FOUND", W.model_set_labels, CFG, "procurement:nope", prefLabel="x")
    unchanged(repo, "PROTECTED_RESOURCE", W.model_set_labels, CFG, "procurement:approval-20261119-arch-baseline", prefLabel="x")
    unchanged(repo, "INVALID_ARGUMENT", W.model_set_labels, CFG, "procurement:supplier", prefLabel="")
    unchanged(repo, "INVALID_ARGUMENT", W.model_set_labels, CFG, "procurement:supplier")


def test_T6_parse_failed_locked_not_a_worktree(repo, tmp_path):
    append(repo, "\n:broken a ")
    unchanged(repo, "PARSE_FAILED", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x", slug="x")
    git(repo, "checkout", "-q", "--", "models")
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import fcntl, os, sys, time
        fd = os.open({os.path.join(git(repo, 'rev-parse', '--absolute-git-dir'), writer.LOCK_NAME)!r}, os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX); print("held", flush=True); time.sleep(30)""")], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        e = unchanged(repo, "LOCKED", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x", slug="x")
        assert e.retryable is True
    finally:
        holder.kill()
        holder.wait()
    assert W.model_add_element(CFG, "procurement", "am4:BusinessObject", "x", slug="x", repo=str(repo))["changed"]
    bare = tmp_path / "bare.git"
    git(tmp_path, "clone", "-q", "--bare", str(repo), str(bare))
    raises("NOT_A_WORKTREE", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "x", slug="y", repo=str(bare))


# ---------------------------------------------------------------- T7: only NEW violations are rejected

def test_T7_preexisting_does_not_block_and_is_marked(repo):
    append(repo, DIRECT)
    r = W.model_add_element(CFG, "procurement", "am4:BusinessObject", "报价行", altLabel="Quote Line", repo=str(repo))
    assert r["changed"] and r["preexistingViolations"] == 1
    v = [f for f in r["findings"] if f["severity"] == "Violation"]
    assert len(v) == 1 and v[0]["preexisting"] is True and v[0]["focus"] == M + "quoteApproval"
    e = unchanged(repo, "WRITE_REJECTED", W.model_add_relationship, CFG, "am4:Serving", "procurement:bpmnReview",
                  "procurement:quoteApproval")
    fs = e.details["findings"]
    assert [f["focus"] for f in fs if f["preexisting"]] == [M + "quoteApproval"]
    new = [f for f in fs if not f["preexisting"]]
    assert {f["focus"] for f in new} == {M + "rel-bpmnReview-serves-quoteApproval"}
    assert any("notation mixing" in f["message"] for f in new)


class _Stub:
    """Just enough of a Ctx for writer.judge: explicit focus on every instance, no fallback needed."""

    def __init__(self, *inst):
        self.instances, self.src_quads, self.prefixes = list(inst), {}, dict(core.NS)

    def rel(self, f):
        return f


def test_T7_instance_key_not_display_key():
    same = "AISEP: generic wording without the focus in it"
    a = ("Violation", "L1", same, M + "A", None, None)
    b = ("Violation", "L1", same, M + "B", None, None)
    _, new, pre = writer.judge(_Stub(a), _Stub(a, b))          # B gets A's wording: new, although the text is old
    assert [f["focus"] for f in new] == [M + "B"] and pre == 1
    _, new, pre = writer.judge(_Stub(a), _Stub(b))             # A fixed, B broken in one write: multiset count same
    assert [f["focus"] for f in new] == [M + "B"] and pre == 0
    _, new, _ = writer.judge(_Stub(a, a), _Stub(a, a, a))      # one more instance of the same key is new
    assert len(new) == 1
    nf_x = ("Violation", "L0", "cannot parse x", None, None, "models/p/x.ttl")
    nf_y = ("Violation", "L0", "cannot parse x", None, None, "models/p/y.ttl")
    _, new, _ = writer.judge(_Stub(nf_x), _Stub(nf_y))
    assert len(new) == 1  # focus null: the file is part of the key


def test_T7_census_every_L1_L2_violation_site_has_a_focus(tmp_path):
    """Write-tool gate (§5.1 step 5, R2-6): every L1/L2 Violation call site of the prototype, triggered on the module
    fixtures (+ one constructed case), yields findings whose focus is not null. L0 has no focus (file instead)."""
    src = open(os.path.join(ROOT, "aisep", "core.py"), encoding="utf-8").read().splitlines()
    sites = {i + 1 for i, l in enumerate(src) if re.search(r'\.add\((sev|"Violation"), "L[12]"', l)}
    hits, bad = set(), []
    real = core.Ctx.add

    def add(self, sev, layer, text, **kw):
        if layer in ("L1", "L2") and sev == "Violation":
            hits.add(inspect.currentframe().f_back.f_lineno)
        return real(self, sev, layer, text, **kw)
    cycle = tmp_path / "cycle.ttl"
    cycle.write_text("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix : <https://aisep.example/model/t/> .\n"
                     ":A rdfs:subClassOf :B .\n:B rdfs:subClassOf :A .\n")
    core.Ctx.add = add
    try:
        mods = core.discover()
        for fx in sorted(glob.glob(os.path.join(ROOT, "modules", "*", "tests", "invalid", "*.ttl"))) + [str(cycle)]:
            ctx = core.Ctx(mods, [fx])
            if any(p[1] == "L0" for p in ctx.problems):
                continue
            core.run_check(ctx)
            for f in tools._findings(ctx, ("L1", "L2")):
                if f["severity"] == "Violation" and not f["focus"]:
                    bad.append((os.path.basename(fx), f["message"][:100]))
    finally:
        core.Ctx.add = real
    assert sites - hits == set(), f"call sites never triggered: {sorted(sites - hits)}"
    assert bad == []


# ---------------------------------------------------------------- T8: text-edit fidelity

def _subsequence(old, new):
    it = iter(new)
    return all(line in it for line in old)


def test_T8_append_keeps_every_line_and_equivalence(repo):
    before = text(repo).splitlines()
    W.model_add_element(CFG, "procurement", "am4:BusinessObject", "报价行", altLabel="Quote Line", repo=str(repo))
    W.model_add_relationship(CFG, "am4:Access", "procurement:submitQuotation", "procurement:quoteLine", repo=str(repo))
    assert _subsequence(before, text(repo).splitlines())
    assert tools.model_gate(CFG, repo=str(repo))["result"] == "PASS"


def test_T8_tampered_editor_output_is_refused(repo, monkeypatch):
    real = writer.append_block
    monkeypatch.setattr(writer, "append_block", lambda t, b, p: real(t, b.replace('"报价行"@zh', '"篡改"@zh'), p))
    unchanged(repo, "EDIT_UNSAFE", W.model_add_element, CFG, "procurement", "am4:BusinessObject", "报价行", slug="quoteLine")
    monkeypatch.setattr(writer, "append_block", real)
    real_rw = writer.rewrite_blocks
    monkeypatch.setattr(writer, "rewrite_blocks", lambda *a: real_rw(*a).replace('"供货商"@zh', '"篡改"@zh'))
    unchanged(repo, "EDIT_UNSAFE", W.model_set_labels, CFG, "procurement:supplier", prefLabel="供货商")


def test_T8_block_with_blank_node_is_not_rewritten(repo):
    s = text(repo).replace('skos:prefLabel "供应商"@zh ;', 'skos:prefLabel "供应商"@zh ; skos:related [ skos:note "n" ] ;')
    open(os.path.join(str(repo), P, "am4.ttl"), "w", encoding="utf-8").write(s)
    unchanged(repo, "EDIT_UNSAFE", W.model_set_labels, CFG, "procurement:supplier", prefLabel="供货商")


# ---------------------------------------------------------------- T9 / T11 / T12

def test_T9_idempotent(repo):
    a = dict(model="procurement", type="am4:BusinessObject", prefLabel="报价行", altLabel="Quote Line")
    r1 = W.model_add_element(CFG, repo=str(repo), **a)
    s = snap(repo)
    r2 = W.model_add_element(CFG, repo=str(repo), **a)
    assert r1["changed"] and not r2["changed"] and r2["iri"] == r1["iri"] and snap(repo) == s
    rel = W.model_add_relationship(CFG, "am4:Assignment", "procurement:supplier", "procurement:quoteApproval", repo=str(repo))
    assert rel["changed"] is False and rel["iri"] == M + "rel-supplier-assigned-quoteApproval" and snap(repo) == s


def test_T11_iri_suffix_for_a_different_class(repo):
    r = W.model_add_relationship(CFG, "aisep:Implementation", "procurement:quotationBC", "procurement:procurementSubdomain",
                                 repo=str(repo))
    assert r["iri"] == M + "rel-quotationBC-implements-procurementSubdomain-2"  # ddd:SubdomainImplementation has -implements-
    assert r["file"] == P + "ddd.ttl"


def test_T12_mixing_rejected_shortcut_warned(repo):
    unchanged(repo, "WRITE_REJECTED", W.model_add_relationship, CFG, "am4:Serving", "procurement:bpmnReview",
              "procurement:quoteApproval")
    W.model_add_element(CFG, "procurement", "am4:Service", "报价查询", slug="quoteQuery", repo=str(repo))
    r = W.model_add_relationship(CFG, "am4:Realization", "procurement:procurementSystem", "procurement:quoteQuery",
                                 repo=str(repo))
    assert r["changed"] and [f for f in r["findings"] if not f["preexisting"] and f["severity"] == "Warning"
                              and "derived-only" in f["message"]]
    assert "am4:Realization" in text(repo) and "rel-procurementSystem-realizes-quoteQuery" in text(repo, "ddd.ttl") + text(repo)


# ---------------------------------------------------------------- T13 (S4a parts)

def _two_file_supplier(repo):
    append(repo, '\n:supplier skos:definition "旧定义"@zh .\n', "bpmn.ttl")
    commit_all(repo, "definition in another file")
    return {f: open(os.path.join(str(repo), P, f), "rb").read() for f in ("am4.ttl", "bpmn.ttl")}


def test_T13_conflict_keeps_external_content(repo, monkeypatch):
    real = writer.write_files

    def racing(root, edits, before):
        append(repo, "\n# saved by an editor meanwhile\n")
        return real(root, edits, before)
    monkeypatch.setattr(writer, "write_files", racing)
    e = raises("CONFLICT", W.model_set_labels, CFG, "procurement:supplier", prefLabel="供货商", repo=str(repo))
    assert e.retryable and text(repo).endswith("# saved by an editor meanwhile\n") and '"供应商"@zh' in text(repo)


def test_T13_second_rename_fails_both_restored(repo, monkeypatch):
    orig = _two_file_supplier(repo)
    n = []

    def fail_second(rel):
        n.append(rel)
        if len(n) == 2:
            raise OSError("injected rename failure")
    monkeypatch.setattr(writer, "_before_rename", fail_second)
    with pytest.raises(OSError, match="injected"):
        W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", definition="新定义", repo=str(repo))
    assert {f: open(os.path.join(str(repo), P, f), "rb").read() for f in orig} == orig
    assert not glob.glob(os.path.join(str(repo), P, ".*aisep-*"))


def test_T13_sigkill_between_renames_leaves_partial_write(repo):
    orig = _two_file_supplier(repo)
    script = textwrap.dedent(f"""
        import os, signal, sys
        sys.path.insert(0, {ROOT!r})
        from aisep import writer, write_tools as W, tools
        n = []
        def hook(rel):
            n.append(rel)
            if len(n) == 2:
                os.kill(os.getpid(), signal.SIGKILL)
        writer._before_rename = hook
        W.model_set_labels(tools.Config(), "procurement:supplier", prefLabel="供货商", definition="新定义", repo={str(repo)!r})
    """)
    p = subprocess.run([sys.executable, "-c", script], capture_output=True)
    assert p.returncode == -signal.SIGKILL
    now = {f: open(os.path.join(str(repo), P, f), "rb").read() for f in orig}
    assert now["am4.ttl"] != orig["am4.ttl"] and now["bpmn.ttl"] == orig["bpmn.ttl"]  # partial: not crash-atomic (§3.4)
    assert all(not f.startswith(P + ".") for f in gitio.model_files(str(repo)))   # leftover temp files are not model files


def test_T13_known_limitation_unlocked_write_after_hash_check_is_overwritten(repo, monkeypatch):
    def external(rel):
        append(repo, "\n# external write in the window\n")
    monkeypatch.setattr(writer, "_before_rename", external)
    W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", repo=str(repo))
    assert "# external write in the window" not in text(repo) and '"供货商"@zh' in text(repo)


def test_T13_symlinked_model_dir_is_outside_root(repo, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, repo / "models" / "other")
    ino, created, real = os.stat(outside).st_ino, [], os.open

    def spy(path, flags, *a, dir_fd=None, **k):  # any file created inside `outside`, even a temp removed later
        if flags & os.O_CREAT and dir_fd is not None and os.fstat(dir_fd).st_ino == ino:
            created.append(path)
        return real(path, flags, *a, dir_fd=dir_fd, **k)
    monkeypatch.setattr(os, "open", spy)
    unchanged(repo, "PATH_OUTSIDE_ROOT", W.model_add_element, CFG, "other", "am4:BusinessObject", "x", slug="x")
    assert os.listdir(outside) == [] and created == []


# ---------------------------------------------------------------- T41: set_labels

def test_T41_set_labels(repo):
    append(repo, '\n:supplier skos:altLabel "Lieferant"@de .\n')
    commit_all(repo, "de label")
    r = W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", repo=str(repo))
    assert r["changed"] and r["iri"] == M + "supplier"
    assert r["before"]["prefLabel"] == "供应商" and r["after"]["prefLabel"] == "供货商"
    hunks = re.findall(r"^@@ -(\d+)", git(repo, "diff", "-U0", "--", P + "am4.ttl"), re.M)
    assert len(hunks) == 1 and 14 <= int(hunks[0]) <= 16                    # only the supplier block changed
    assert '"Lieferant"@de' in text(repo)                                   # other languages untouched
    d = diff.model_diff(CFG, {"worktree": "main"}, detail="items", repo=str(repo))
    assert [(i["iri"], i["change"], i["changedPredicates"]) for i in d["items"]] == \
        [(M + "supplier", "modified", [W.PREF])]
    s = snap(repo)
    assert W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", repo=str(repo))["changed"] is False
    assert snap(repo) == s
    W.model_set_labels(CFG, "procurement:supplier", definition="提供报价的外部企业", repo=str(repo))
    assert '"提供报价的外部企业"@zh' in text(repo)
    r = W.model_set_labels(CFG, "procurement:supplier", definition=None, altLabel=None, repo=str(repo))
    assert r["after"]["definition"] is None and r["after"]["altLabel"] is None
    assert "skos:definition" not in text(repo).split(":procurementManager")[0] and '"Supplier"@en' not in text(repo)
    assert '"Lieferant"@de' in text(repo)                                   # only @en altLabel removed
    assert tools.model_gate(CFG, repo=str(repo))["result"] == "PASS"


# ---------------------------------------------------------------- T42: default target files

def test_T42_default_files(repo):
    ws = writer.Workspace(str(repo))
    ctx = ws.ctx()
    st = W._subject_triples(ctx)
    rels = [r for r, ts in st.items() if any(t.predicate.value == W.SOURCE for _, t in ts)]
    assert len(rels) == 27
    wrong = [(r, W._type_file(st, r), W.default_relationship_file(st, "procurement", *[
        next(t.object.value for _, t in st[r] if t.predicate.value == p) for p in (W.SOURCE, W.TARGET)]))
        for r in rels]
    assert [w for w in wrong if w[1] != w[2]] == []
    expect = {"aisep:CodeLocation": "code.ttl", "aisep:TestCase": "verification.ttl", "aisep:ApprovalRecord": "governance.ttl",
              "arch:Stakeholder": "governance.ttl", "am4:BusinessObject": "am4.ttl", "bpmn:Task": "bpmn.ttl",
              "uml:Class": "uml.ttl", "ddd:Aggregate": "ddd.ttl"}
    got = {k: W.default_element_file(ctx, "procurement", core.expand(ctx, k)).rsplit("/", 1)[1] for k in expect}
    assert got == expect
    r = W.model_add_element(CFG, "procurement", "aisep:CodeLocation", "行项目代码", slug="lineCode",
                            attributes=[{"predicate": "schema:codeRepository", "value": {"value": "https://example.org/r"}},
                                        {"predicate": "aisep:path", "value": {"value": "src/line"}}],
                            dryRun=True, repo=str(repo))
    assert r["file"] == P + "code.ttl" and r["dryRun"] is True
