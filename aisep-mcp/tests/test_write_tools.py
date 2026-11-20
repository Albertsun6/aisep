"""S4 write tools — acceptance tests written BEFORE the implementation (docs/mcp-interface.md §5.1–§5.3, §5.5, §5.10;
§11 T6, T7, T8, T9, T11, T12, T13, T17, T18, T37 write part, T41, T42).

Every test builds its fixture in the conftest `repo` (a tmp `git init` of the procurement example) and asserts the fixture
itself; the tool calls go through fixtures.pending, so while `aisep.write_tools` is missing the test still builds
everything and ends as XFAIL ("实现未写"). A fixture bug fails the test.

Entry points (style of aisep/tools.py: first argument cfg, return the tool's structuredContent dict, errors raise
AisepError with .code/.details; extra keyword arguments → INVALID_ARGUMENT with details.rejectedFields):

    aisep.write_tools.model_add_element(cfg, model, type, prefLabel, *, altLabel=None, slug=None, definition=None,
                                        attributes=None, file=None, dryRun=False, repo=None)
        → {iri, file, changed, turtle, filesChanged: [{path, sha256Before, sha256After}], findings, preexistingViolations}
    aisep.write_tools.model_add_relationship(cfg, type, source, target, *, model=None, file=None, dryRun=False, repo=None)
        → same shape as model_add_element
    aisep.write_tools.model_set_labels(cfg, iri, *, prefLabel=<not given>, altLabel=<not given>,
                                       definition=<not given>, dryRun=False, repo=None)
        not given = keep; None = delete (altLabel, definition)
        → {iri, changed, before, after, filesChanged, findings, preexistingViolations}
    aisep.write_tools.model_remove(cfg, iri, *, cascade=False, dryRun=False, planDigest=None, repo=None)
        → {target, plan: {delete, detach, blockers}, planDigest, written, changed?, alreadyAbsent?, filesChanged, findings}

Findings of the write tools carry `preexisting` (§5.1 step 5). File paths in results are repo-relative.

Not covered here: the editor-tampering hook of T8 (needs an internal injection point), T13's mid-write external edit /
rename failure / SIGKILL / approval-vs-agent lock race (injection points), the T7 census of focus over all L0–L2
Violation call sites, the derived-shortcut Warning of T12 (no shortcut example in the procurement model).
"""
import fcntl, hashlib, os, shutil, subprocess

import pyoxigraph as ox
import pytest

from conftest import commit_all, git
from aisep import tools as T
from fixtures.pending import call, error, pending, wrap_module

W = "aisep.write_tools"
M = "https://aisep.example/model/procurement/"
AM4 = "models/procurement/am4.ttl"
GOVTTL = "models/procurement/governance.ttl"
DIRECT = "\n:quoteApproval am4:accesses :quotation .\n"  # one L1 Violation (direct triple)
UNDECLARED = "https://example.invalid/undeclared"


# ------------------------------------------------------------------ helpers

def cfg(repo):
    return T.Config(allow_roots=(str(repo.parent),))


def wt(name, repo, *a, **kw):
    return call(W, name, cfg(repo), *a, repo=str(repo), **kw)


def wt_err(code, name, repo, *a, **kw):
    return error(code, W, name, cfg(repo), *a, repo=str(repo), **kw)


def snap(repo):
    """{repo-relative path: sha256} of every file under models/ (the state a refused write must not change)."""
    out = {}
    for d, _, fs in os.walk(repo / "models"):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, repo)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def sha(repo, rel):
    return hashlib.sha256(open(repo / rel, "rb").read()).hexdigest()


def append(repo, rel, text):
    with open(repo / rel, "a", encoding="utf-8") as f:
        f.write(text)


def triples(repo, rel):
    with open(repo / rel, "rb") as f:
        return {(q.subject, q.predicate, q.object) for q in ox.parse(f, format=ox.RdfFormat.TURTLE)}


def check_violations(repo):
    """L0–L2 Violation count of the worktree (read tool, already implemented): verifies a planted fixture."""
    return T.model_check(cfg(repo), repo=str(repo))["summary"]["violations"]


def violations(findings):
    return [f for f in findings if f["severity"] == "Violation"]


def add_invoice(repo, **kw):
    return wt("model_add_element", repo, "procurement", "am4:BusinessObject", "发票", altLabel="Invoice", **kw)


# ================================================================== T6 a refused write writes nothing

REFUSALS = [
    ("add_element-model", "MODEL_NOT_FOUND", "model_add_element", ("nosuch", "am4:BusinessObject", "发票"), {"slug": "invoice"}),
    ("add_element-type", "UNKNOWN_TYPE", "model_add_element", ("procurement", "am4:NoSuchType", "发票"), {"slug": "invoice"}),
    ("add_element-abstract", "ABSTRACT_TYPE", "model_add_element", ("procurement", "arch:Element", "发票"), {"slug": "invoice"}),
    ("add_element-no-slug", "INVALID_ARGUMENT", "model_add_element", ("procurement", "am4:BusinessObject", "发票"), {}),
    ("add_element-iri-exists", "IRI_EXISTS", "model_add_element", ("procurement", "am4:BusinessObject", "别的名字"), {"slug": "supplier"}),
    ("add_element-rejected", "WRITE_REJECTED", "model_add_element", ("procurement", "am4:BusinessObject", "发票"),
     {"slug": "invoice", "attributes": [{"predicate": UNDECLARED, "value": {"value": "x"}}]}),
    ("add_element-ref", "INVALID_ARGUMENT", "model_add_element", ("procurement", "am4:BusinessObject", "发票"), {"slug": "invoice", "ref": "HEAD"}),
    ("add_relationship-endpoint", "ELEMENT_NOT_FOUND", "model_add_relationship", ("am4:Assignment", "procurement:supplier", "procurement:nosuch"), {}),
    ("add_relationship-mixing", "WRITE_REJECTED", "model_add_relationship", ("am4:Assignment", "procurement:bpmnReview", "procurement:quoteApproval"), {}),
    ("set_labels-protected", "PROTECTED_RESOURCE", "model_set_labels", (M + "approval-20261119-arch-baseline",), {"prefLabel": "改"}),
    ("set_labels-missing", "ELEMENT_NOT_FOUND", "model_set_labels", (M + "nosuch",), {"prefLabel": "改"}),
    ("set_labels-empty", "INVALID_ARGUMENT", "model_set_labels", (M + "supplier",), {"prefLabel": ""}),
    ("set_labels-nothing", "INVALID_ARGUMENT", "model_set_labels", (M + "supplier",), {}),
    ("set_labels-extra-type", "INVALID_ARGUMENT", "model_set_labels", (M + "supplier",), {"prefLabel": "改", "type": "am4:Role"}),
    ("remove-referenced", "REFERENCED", "model_remove", (M + "quoteApproval",), {}),
    ("remove-cascade", "CASCADE_REQUIRED", "model_remove", (M + "quotation",), {}),
    ("remove-protected-record", "PROTECTED_RESOURCE", "model_remove", (M + "approval-20261119-arch-baseline",), {}),
    ("remove-protected-model", "PROTECTED_RESOURCE", "model_remove", (M,), {}),
    ("remove-missing", "ELEMENT_NOT_FOUND", "model_remove", (M + "nosuch",), {}),
]


@pytest.mark.parametrize("case,code,tool,args,kw", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_T6_refusal_writes_nothing(repo, case, code, tool, args, kw):
    before = snap(repo)
    e = wt_err(code, tool, repo, *args, **kw)
    assert snap(repo) == before
    if case in ("set_labels-extra-type", "add_element-ref") and not pending(e):
        assert ("type" if case == "set_labels-extra-type" else "ref") in e.details.get("rejectedFields", [])


def test_T6_accepted_write_changes_only_the_target_file(repo):
    before = snap(repo)
    dry = add_invoice(repo, dryRun=True)
    assert snap(repo) == before  # dryRun writes nothing
    r = add_invoice(repo)
    after = snap(repo)
    if not pending(r):
        assert dry["iri"] == r["iri"] == M + "invoice" and r["changed"] is True and r["file"] == AM4
        assert {k for k in after if after[k] != before.get(k)} == {AM4}
        assert r["filesChanged"] == [{"path": AM4, "sha256Before": before[AM4], "sha256After": after[AM4]}]
        assert "\n:invoice a am4:BusinessObject" in open(repo / AM4, encoding="utf-8").read()
        assert git(repo, "status", "--porcelain") == f"M {AM4}"  # not staged, not committed (§5.1 step 9)


# ================================================================== T7 (+ T37 write part) only NEW violations refuse

@pytest.mark.parametrize("planted", ["worktree", "committed"])
def test_T7_preexisting_violation_does_not_block(repo, planted):
    append(repo, AM4, DIRECT)
    if planted == "committed":  # T37: as if committed with --no-verify (the tmp repo has no hook)
        commit_all(repo, "legacy violation")
    assert check_violations(repo) >= 1  # the plant is a real L1 Violation
    ok = add_invoice(repo)
    if not pending(ok):
        assert ok["preexistingViolations"] == 1
        v = violations(ok["findings"])
        assert len(v) == 1 and v[0]["preexisting"] is True and v[0]["focus"]
    before = snap(repo)
    e = wt_err("WRITE_REJECTED", "model_add_element", repo, "procurement", "am4:BusinessObject", "收据",
               slug="receipt", attributes=[{"predicate": UNDECLARED, "value": {"value": "x"}}])
    assert snap(repo) == before
    if not pending(e):
        fs = violations(e.details["findings"])
        assert [f["preexisting"] for f in fs].count(True) == 1
        assert [f for f in fs if f["preexisting"] is False]
        assert all(M + "receipt" in (f["focus"] or "") for f in fs if f["preexisting"] is False)


def test_T7_same_rule_on_another_object_is_new(repo):
    """Instance key (severity, layer, rule, focus, message), counted as a multiset: :supplier already carries an
    undeclared predicate; a write giving :receipt the same one is refused."""
    append(repo, AM4, f"\n:supplier <{UNDECLARED}> \"x\" .\n")
    assert check_violations(repo) >= 1
    before = snap(repo)
    wt_err("WRITE_REJECTED", "model_add_element", repo, "procurement", "am4:BusinessObject", "收据", slug="receipt",
           attributes=[{"predicate": UNDECLARED, "value": {"value": "x"}}])
    assert snap(repo) == before
    add_invoice(repo)  # positive twin: a clean write still passes beside the planted violation


# ================================================================== T8 text-edit fidelity

def test_T8_append_keeps_every_line_and_only_adds_the_new_subject(repo):
    old_lines = open(repo / AM4, encoding="utf-8").read().splitlines()
    old = triples(repo, AM4)
    r = add_invoice(repo)
    if pending(r):
        return
    new_lines = open(repo / AM4, encoding="utf-8").read().splitlines()
    it = iter(new_lines)
    assert all(any(l == n for n in it) for l in old_lines)  # old lines are an ordered subsequence
    new = triples(repo, AM4)
    assert old <= new and {s for s, _, _ in new - old} == {ox.NamedNode(M + "invoice")}


def test_T8_two_subjects_in_one_block_edit_unsafe(repo):
    """§5.1 step 6: two subjects written in one block (here: on one line); removing one of them → EDIT_UNSAFE,
    nothing written. Positive twin: the same subject written in its own block is removed cleanly."""
    m = f"<{M}>"
    append(repo, AM4, f"\n:twinA a am4:BusinessObject ; arch:inModel {m} ; skos:prefLabel \"甲\"@zh . "
                      f":twinB a am4:BusinessObject ; arch:inModel {m} ; skos:prefLabel \"乙\"@zh .\n"
                      f"\n:solo a am4:BusinessObject ; arch:inModel {m} ; skos:prefLabel \"单\"@zh .\n")
    commit_all(repo, "twins")
    assert check_violations(repo) == 0
    before = snap(repo)
    wt_err("EDIT_UNSAFE", "model_remove", repo, M + "twinB")
    assert snap(repo) == before
    r = wt("model_remove", repo, M + "solo")
    if not pending(r):
        assert r["written"] is True and ":solo a" not in open(repo / AM4, encoding="utf-8").read()


# ================================================================== T9 idempotence

def test_T9_add_element_twice(repo):
    r1 = add_invoice(repo)
    s1 = snap(repo)
    r2 = add_invoice(repo)
    assert snap(repo) == s1
    if not pending(r2):
        assert r1["changed"] is True and r2["changed"] is False and r2["iri"] == r1["iri"]


def test_T9_add_relationship_replay_returns_existing_iri(repo):
    before = snap(repo)
    r = wt("model_add_relationship", repo, "am4:Assignment", "procurement:supplier", "procurement:quoteApproval")
    assert snap(repo) == before
    if not pending(r):
        assert r["iri"] == M + "rel-supplier-assigned-quoteApproval" and r["changed"] is False
    n1 = wt("model_add_relationship", repo, "am4:Assignment", "procurement:procurementManager",
            "procurement:submitQuotation")
    n2 = wt("model_add_relationship", repo, "am4:Assignment", "procurement:procurementManager",
            "procurement:submitQuotation")
    if not pending(n2):
        assert n1["changed"] is True and n2["changed"] is False and n2["iri"] == n1["iri"]
        assert not n2["iri"].endswith("-2")


# ================================================================== T11 IRI rule

def test_T11_same_endpoints_two_classes_get_suffix(repo):
    """F12: ddd:SubdomainImplementation quotationBC→procurementSubdomain exists (…-implements-…); a new
    aisep:Implementation between the same ends gets …-implements-…-2. The existing one replays without -2."""
    same = wt("model_add_relationship", repo, "ddd:SubdomainImplementation", "procurement:quotationBC",
              "procurement:procurementSubdomain", dryRun=True)
    other = wt("model_add_relationship", repo, "aisep:Implementation", "procurement:quotationBC",
               "procurement:procurementSubdomain", dryRun=True)
    if not pending(other):
        assert same["iri"] == M + "rel-quotationBC-implements-procurementSubdomain" and same["changed"] is False
        assert other["iri"] == M + "rel-quotationBC-implements-procurementSubdomain-2"


# ================================================================== T12 add_relationship refusals

def test_T12_notation_mixing_refused_legal_written_qualified_only(repo):
    before = snap(repo)
    e = wt_err("WRITE_REJECTED", "model_add_relationship", repo, "am4:Assignment", "procurement:bpmnReview",
               "procurement:quoteApproval")
    assert snap(repo) == before
    if not pending(e):
        assert violations(e.details["findings"])
    r = wt("model_add_relationship", repo, "am4:Assignment", "procurement:procurementManager",
           "procurement:submitQuotation")
    if not pending(r):
        assert "arch:source" in r["turtle"] and "assignedTo" not in r["turtle"]  # never the direct triple (§8.1)


# ================================================================== T13 lock and root

def test_T13_lock_held_means_locked(repo):
    lock = os.path.join(git(repo, "rev-parse", "--absolute-git-dir"), "aisep-write.lock")
    before = snap(repo)
    with open(lock, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wt_err("LOCKED", "model_add_element", repo, "procurement", "am4:BusinessObject", "发票", slug="invoice")
        assert snap(repo) == before
        fcntl.flock(fh, fcntl.LOCK_UN)
    add_invoice(repo)  # positive twin: lock released


def test_T13_model_dir_symlinked_outside_root(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    shutil.move(str(repo / "models" / "procurement"), str(outside / "procurement"))
    os.symlink(str(outside / "procurement"), str(repo / "models" / "procurement"))
    listing = sorted(os.listdir(outside / "procurement"))
    shas = {f: hashlib.sha256(open(outside / "procurement" / f, "rb").read()).hexdigest() for f in listing
            if os.path.isfile(outside / "procurement" / f)}
    wt_err("PATH_OUTSIDE_ROOT", "model_add_element", repo, "procurement", "am4:BusinessObject", "发票", slug="invoice",
           file=AM4)
    assert sorted(os.listdir(outside / "procurement")) == listing
    assert {f: hashlib.sha256(open(outside / "procurement" / f, "rb").read()).hexdigest() for f in shas} == shas


# ================================================================== T17 cascade remove

def test_T17_quoteApproval_referenced_only_by_the_approval(repo):
    e = wt_err("REFERENCED", "model_remove", repo, M + "quoteApproval")
    if not pending(e):
        subjects = {b["subject"] for b in e.details["plan"]["blockers"]}
        assert subjects == {M + "approval-20261119-arch-baseline"}  # no derived direct triple from the build graph


def test_T17_quotation_needs_cascade_three_relationships(repo):
    e = wt_err("CASCADE_REQUIRED", "model_remove", repo, M + "quotation")
    if not pending(e):
        rels = [d for d in e.details["plan"]["delete"] if d["kind"] == "relationship"]
        assert len(rels) == 3


def test_T17_bpmnReview_cascade_then_gate_passes(repo):
    r = wt("model_remove", repo, M + "bpmnReview", cascade=True)
    if pending(r):
        return
    assert {d["iri"] for d in r["plan"]["delete"]} >= {M + "sf1", M + "sf2"}
    assert [(d["subject"], d["predicate"].rsplit("#", 1)[-1].rsplit(":", 1)[-1]) for d in r["plan"]["detach"]] == \
        [(M + "bpmnQuoteApproval", "flowElements")]
    assert T.model_gate(cfg(repo), repo=str(repo))["result"] == "PASS"


def test_T17_cross_model_relationship_blocks(repo):
    b = "https://aisep.example/model/other/"
    os.makedirs(repo / "models" / "other")
    with open(repo / "models/other/am4.ttl", "w", encoding="utf-8") as f:
        f.write(f"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix : <{b}> .
<{b}> a arch:Model ; skos:prefLabel "其他"@zh .
:auditor a am4:Role ; arch:inModel <{b}> ; skos:prefLabel "审计员"@zh .
:rel-auditor-assigned-submitQuotation a am4:Assignment ; arch:inModel <{b}> ;
    arch:source :auditor ; arch:target <{M}submitQuotation> .
""")
    commit_all(repo, "model B")
    b_sha = sha(repo, "models/other/am4.ttl")
    e = wt_err("REFERENCED", "model_remove", repo, M + "submitQuotation", cascade=True)
    assert sha(repo, "models/other/am4.ttl") == b_sha
    if not pending(e):
        bl = e.details["plan"]["blockers"]
        assert any(x.get("reason") == "cross-model-relationship" and x["subject"] == b + "rel-auditor-assigned-submitQuotation"
                   for x in bl), bl


def test_T17_relationship_to_relationship_both_deleted(repo):
    m = f"<{M}>"
    append(repo, AM4, f"\n:ledger a am4:BusinessObject ; arch:inModel {m} ; skos:prefLabel \"台账\"@zh .\n"
                      f"\n:rel-submitQuotation-accesses-ledger a am4:Access ; arch:inModel {m} ;\n"
                      f"    arch:source :submitQuotation ; arch:target :ledger .\n"
                      f"\n:rel-assoc-on-access a am4:Association ; arch:inModel {m} ;\n"
                      f"    arch:source :rel-submitQuotation-accesses-ledger ; arch:target :supplier .\n")
    commit_all(repo, "relationship to relationship")
    r = wt("model_remove", repo, M + "ledger", cascade=True, dryRun=True)
    if not pending(r):
        assert {d["iri"] for d in r["plan"]["delete"]} >= {M + "rel-submitQuotation-accesses-ledger",
                                                          M + "rel-assoc-on-access"}


# ================================================================== T18 determinism and planDigest

def test_T18_plan_is_deterministic_digest_guards_and_replays(repo):
    runs = [wt("model_remove", repo, M + "quotation", cascade=True, dryRun=True) for _ in range(10)]
    if not pending(runs[0]):
        assert all(r == runs[0] for r in runs)
    old = runs[0]["planDigest"]
    append(repo, AM4, "\n# a comment changes the file\n")
    before = snap(repo)
    wt_err("PLAN_STALE", "model_remove", repo, M + "quotation", cascade=True, planDigest=old)
    assert snap(repo) == before
    fresh = wt("model_remove", repo, M + "quotation", cascade=True, dryRun=True)
    done = wt("model_remove", repo, M + "quotation", cascade=True, planDigest=fresh["planDigest"])
    again = wt("model_remove", repo, M + "quotation", cascade=True, planDigest=fresh["planDigest"])
    if not pending(again):
        assert done["written"] is True
        assert again["changed"] is False and again["alreadyAbsent"] is True
    wt_err("ELEMENT_NOT_FOUND", "model_remove", repo, M + "neverThere")


# ================================================================== T41 set_labels

def test_T41_set_label_changes_one_block_iri_kept(repo):
    r = wt("model_set_labels", repo, M + "supplier", prefLabel="供货商")
    if pending(r):
        return
    assert r["iri"] == M + "supplier" and r["changed"] is True
    assert r["before"]["prefLabel"] == "供应商" and r["after"]["prefLabel"] == "供货商"
    txt = open(repo / AM4, encoding="utf-8").read()
    assert '"供货商"@zh' in txt and 'skos:altLabel "Supplier"@en' in txt  # other languages untouched
    changed = [l for l in git(repo, "diff", "-U0", "--", AM4).splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    assert changed == ['-    skos:prefLabel "供应商"@zh ; skos:altLabel "Supplier"@en .',
                       '+    skos:prefLabel "供货商"@zh ; skos:altLabel "Supplier"@en .'], changed
    s = snap(repo)
    again = wt("model_set_labels", repo, M + "supplier", prefLabel="供货商")
    assert snap(repo) == s and again["changed"] is False


def test_T41_definition_add_then_delete(repo):
    r = wt("model_set_labels", repo, M + "supplier", definition="提供报价的外部组织")
    if pending(r):
        return
    assert 'skos:definition "提供报价的外部组织"@zh' in open(repo / AM4, encoding="utf-8").read()
    d = wt("model_set_labels", repo, M + "supplier", definition=None)
    assert d["changed"] is True and "skos:definition" not in open(repo / AM4, encoding="utf-8").read()


# ================================================================== T42 default write file

@pytest.mark.parametrize("typ,attrs,expect", [
    ("am4:Role", None, "models/procurement/am4.ttl"),
    ("bpmn:UserTask", None, "models/procurement/bpmn.ttl"),
    ("aisep:CodeLocation", [{"predicate": "aisep:path", "value": {"value": "services/x/"}}], "models/procurement/code.ttl"),
    ("arch:Stakeholder", None, GOVTTL),
])
def test_T42_element_default_file(repo, typ, attrs, expect):
    r = wt("model_add_element", repo, "procurement", typ, "新元素", slug="newOne", attributes=attrs, dryRun=True)
    if not pending(r):
        assert r["file"] == expect


def _relationships(repo):
    """(iri, type, source, target, file) of every qualified relationship of the procurement model, from the sources."""
    out = []
    for f in sorted(os.listdir(repo / "models/procurement")):
        if not f.endswith(".ttl"):
            continue
        rel = f"models/procurement/{f}"
        ts = triples(repo, rel)
        src = {s: o for s, p, o in ts if p.value == "https://meta.linked.archi/core#source"}
        tgt = {s: o for s, p, o in ts if p.value == "https://meta.linked.archi/core#target"}
        for s in src:
            typ = next(o.value for x, p, o in ts if x == s and p.value.endswith("#type"))
            out.append((s.value, typ, src[s].value, tgt[s].value, rel))
    return sorted(out)


def _cut_block(repo, rel, iri):
    """Remove the subject block of iri (from ':local a' to its terminating ' .' + newline)."""
    txt = open(repo / rel, encoding="utf-8").read()
    i = txt.index(f":{iri[len(M):]} a ")
    j = txt.index(" .\n", i) + 3
    with open(repo / rel, "w", encoding="utf-8") as f:
        f.write(txt[:i] + txt[j:])


def test_T42_relationship_default_file_matches_all_27(repo):
    rels = _relationships(repo)
    assert len(rels) == 27, len(rels)
    got = []
    for iri, typ, s, t, rel in rels:
        saved = open(repo / rel, encoding="utf-8").read()
        _cut_block(repo, rel, iri)
        r = wt("model_add_relationship", repo, typ, s, t, dryRun=True)
        with open(repo / rel, "w", encoding="utf-8") as f:
            f.write(saved)
        if pending(r):
            return
        got.append((iri, r["file"], rel))
    assert [g for g in got if g[1] != g[2]] == []


wrap_module(globals())
