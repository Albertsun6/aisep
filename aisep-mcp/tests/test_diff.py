"""S3: model_diff (docs/mcp-interface.md §5.8). Acceptance: T14, T15, T16, T19, T20 (diff part), T35, T36."""
import builtins, os, re, shutil

import pytest

from conftest import commit_all, git, init_repo
from aisep import diff, gitio
from aisep.errors import AisepError
from aisep.tools import Config

CFG = Config()
M = "https://aisep.example/model/procurement/"
SKOS_PREF = "http://www.w3.org/2004/02/skos/core#prefLabel"
HDR = """@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix arch:  <https://meta.linked.archi/core#> .
@prefix am4:   <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix :      <https://aisep.example/model/procurement/> .
"""
CODE_SUBJECTS = {M + s for s in ("quotationCode", "rel-quotationCode-implements-quotationBC", "quotationPackage",
                                 "rel-quotationPackage-realizes-quotationBC")}


def el(local, label="新元素", typ="am4:BusinessObject"):
    return f'\n:{local} a {typ} ;\n    arch:inModel <{M}> ;\n    skos:prefLabel "{label}"@zh .\n'


def add(root, text, f="am4.ttl"):
    with open(os.path.join(str(root), "models/procurement", f), "a") as fh:
        fh.write(text)


def edit(root, f, old, new):
    p = os.path.join(str(root), "models/procurement", f)
    s = open(p).read()
    assert s.count(old) == 1, old
    open(p, "w").write(s.replace(old, new))


def raises(code, fn, *a, **kw):
    with pytest.raises(AisepError) as e:
        fn(*a, **kw)
    assert e.value.code == code, (e.value.code, e.value.message)
    return e.value


def d(repo, head, **kw):
    return diff.model_diff(CFG, head, repo=str(repo), **kw)


def changes(r):
    return {(i["iri"].replace(M, ""), i["change"]) for i in r["items"]}


def status(root):
    return git(root, "status", "--porcelain", "--untracked-files=all")


# ---------------------------------------------------------------- T14: merge-base start

def test_T14_merge_base_not_main_tip(repo):
    git(repo, "branch", "feat")
    add(repo, el("mainX"))
    commit_all(repo, "main adds X")
    git(repo, "checkout", "-q", "feat")
    add(repo, el("featY"))
    commit_all(repo, "feat adds Y")
    r = d(repo, "feat", detail="items")
    assert changes(r) == {("featY", "added")} and r["base"]["viaMergeBase"] is True
    assert r["counts"]["element"] == {"added": 1, "modified": 0, "removed": 0} and r["changedElementCount"] == 1


def test_T14_stale_local_main_uses_remote_tracking(repo, tmp_path):
    b = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(repo), str(b))
    git(b, "config", "user.name", "t")
    git(b, "config", "user.email", "t@example.invalid")
    add(repo, el("teammateZ"))  # a teammate's work lands on origin/main
    commit_all(repo, "Z")
    git(b, "fetch", "-q")
    git(b, "checkout", "-q", "-b", "feat", "origin/main")
    add(b, el("featY"))
    commit_all(b, "Y")
    r = d(b, "feat", detail="items")
    assert changes(r) == {("featY", "added")} and r["base"]["mainRef"] == "refs/remotes/origin/main"
    stale = d(b, "feat", detail="items", mainRef="refs/heads/main")  # what a stale local main would have said
    assert ("teammateZ", "added") in changes(stale)


# ---------------------------------------------------------------- T15: semantics (Git ref mode, base = c0)

def _commit_case(repo, fn):
    c0 = git(repo, "rev-parse", "HEAD")
    fn(repo)
    return c0, commit_all(repo, "case")


def test_T15_added_and_label_only(repo):
    c0, c1 = _commit_case(repo, lambda r: (add(r, el("newBO")), edit(r, "am4.ttl", '"供应商"@zh', '"供货商"@zh')))
    r = d(repo, c1, base=c0, detail="triples")
    assert changes(r) == {("newBO", "added"), ("supplier", "modified")}
    sup = next(i for i in r["items"] if i["iri"] == M + "supplier")
    assert sup["changedPredicates"] == [SKOS_PREF] and "typeChanged" not in sup
    assert sup["triples"] == {"added": [[SKOS_PREF, '"供货商"@zh']], "removed": [[SKOS_PREF, '"供应商"@zh']]}


def test_T15_relationship_type_change_per_8_2_and_type_only(repo):
    c0, c1 = _commit_case(repo, lambda r: (
        edit(r, "am4.ttl", ":rel-supplier-assigned-submitQuotation a am4:Assignment",
             ":rel-supplier-serves-submitQuotation a am4:Serving"),
        edit(r, "am4.ttl", ":supplier a am4:Role", ":supplier a am4:BusinessActor")))
    r = d(repo, c1, base=c0, detail="items")
    assert r["counts"]["relationship"] == {"added": 1, "modified": 0, "removed": 1}
    rel = next(i for i in r["items"] if i["change"] == "added")
    assert rel["source"] == {"iri": M + "supplier", "label": "供应商"} and rel["target"]["iri"] == M + "submitQuotation"
    sup = next(i for i in r["items"] if i["iri"] == M + "supplier")
    assert sup["change"] == "modified" and sup["typeChanged"] is True
    assert r["touchedElementCount"] == 2  # supplier (modified) + submitQuotation (endpoint)


def test_T15_move_and_comment_prefix_only(repo):
    def move(r):
        p = os.path.join(str(r), "models/procurement/am4.ttl")
        s = open(p).read()
        block = re.search(r":supplier a am4:Role ;.*?\"Supplier\"@en \.\n", s, re.S).group(0)
        open(p, "w").write(s.replace(block, "").replace("@prefix :", "# a comment\n@prefix unused: <urn:unused#> .\n@prefix :"))
        open(os.path.join(str(r), "models/procurement/moved.ttl"), "w").write(HDR + block)
    c0, c1 = _commit_case(repo, move)
    r = d(repo, c1, base=c0, detail="items")
    assert r["items"] == [] and all(v == {"added": 0, "modified": 0, "removed": 0} for v in r["counts"].values())
    assert r["moves"] == [{"iri": M + "supplier", "files": {"base": ["models/procurement/am4.ttl"],
                                                            "head": ["models/procurement/moved.ttl"]}}]


def test_T15_view_membership_and_custom_view_subclass(repo):
    add(repo, "\n:v1 a arch:Diagram ;\n    arch:inModel <" + M + "> ;\n    skos:prefLabel \"视图\"@zh .\n")
    c0 = commit_all(repo, "view")
    add(repo, "\n:supplier arch:inView :v1 .\n:MyView rdfs:subClassOf arch:Diagram .\n"
              ":v2 a :MyView ;\n    arch:inModel <" + M + "> ;\n    skos:prefLabel \"自定义视图\"@zh .\n")
    edit(repo, "am4.ttl", "@prefix :", "@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix :")
    c1 = commit_all(repo, "membership")
    r = d(repo, c1, base=c0, detail="items")
    kinds = {i["iri"].replace(M, ""): (i["kind"], i["change"]) for i in r["items"]}
    assert kinds == {"v1": ("view", "modified"), "v2": ("view", "added"), "MyView": ("schema", "added")}
    assert r["counts"]["element"]["modified"] == 0 and r["changedElementCount"] == 0
    assert next(i for i in r["items"] if i["iri"] == M + "v1")["changedPredicates"] == ["https://meta.linked.archi/core#inView"]


@pytest.mark.parametrize("ttl,reason", [
    ("_:a skos:related _:b .\n_:b skos:related _:a .\n", "cycle"),
    (":supplier skos:related _:s .\n:procurementManager skos:related _:s .\n_:s skos:note \"x\" .\n", "shared"),
    ("_:u skos:related :supplier .\n", "unreferenced")])
def test_T15_bnode_unsupported(repo, ttl, reason):
    c0, c1 = _commit_case(repo, lambda r: add(r, "\n" + ttl))
    e = raises("DIFF_BNODE_UNSUPPORTED", d, repo, c1, base=c0)
    assert e.details["reason"] == reason and e.details["file"] == "models/procurement/am4.ttl"


def test_T15_tree_bnode_value_change(repo):
    add(repo, "\n:supplier skos:related [ skos:note \"a\" ; skos:related [ skos:note \"deep\" ] ] .\n")
    c0 = commit_all(repo, "tree bnode")
    edit(repo, "am4.ttl", 'skos:note "deep"', 'skos:note "deeper"')
    c1 = commit_all(repo, "change inside")
    r = d(repo, c1, base=c0, detail="items")
    assert changes(r) == {("supplier", "modified")}
    assert r["items"][0]["changedPredicates"] == ["http://www.w3.org/2004/02/skos/core#related"]
    assert d(repo, c0, base=c0)["changedElementCount"] == 0


# ---------------------------------------------------------------- T16: Git ref mode only sees commits

def test_T16_ref_mode_ignores_worktree_and_is_location_independent(repo, tmp_path):
    git(repo, "checkout", "-q", "-b", "feat")
    add(repo, el("committedY"))
    commit_all(repo, "Y")
    add(repo, el("uncommittedZ"))                 # uncommitted: must not show
    before = status(repo)
    r1 = d(repo, "feat", detail="items")
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "--detach", str(other), "main")
    r2 = diff.model_diff(CFG, "feat", repo=str(other), detail="items")
    assert changes(r1) == changes(r2) == {("committedY", "added")}
    assert status(repo) == before


# ---------------------------------------------------------------- T19: fast paths

def test_T19_code_only_branch_parses_nothing(repo):
    git(repo, "checkout", "-q", "-b", "feat")
    open(repo / "README.md", "w").write("code change\n")
    commit_all(repo, "code")
    n = diff.PARSE_CALLS
    r = d(repo, "feat")
    assert diff.PARSE_CALLS == n and r["changedElementCount"] == 0 and r["baseHasModels"] and r["headHasModels"]


def test_T19_no_models_either_side(tmp_path):
    r = init_repo(tmp_path / "plain")
    open(r / "README.md", "w").write("x")
    commit_all(r)
    git(r, "checkout", "-q", "-b", "feat")
    open(r / "x.py", "w").write("x")
    commit_all(r)
    res = diff.model_diff(CFG, "feat", repo=str(r))
    assert (res["baseHasModels"], res["headHasModels"]) == (False, False) and res["changedElementCount"] == 0


def test_T19_head_deletes_models(repo):
    c0 = git(repo, "rev-parse", "HEAD")
    git(repo, "rm", "-r", "-q", "models")
    c1 = commit_all(repo, "rm models")
    r = d(repo, c1, base=c0, detail="items")
    assert (r["baseHasModels"], r["headHasModels"]) == (True, False)
    assert r["items"] and all(i["change"] == "removed" for i in r["items"])
    assert r["counts"]["element"]["removed"] > 0 and r["counts"]["relationship"]["removed"] > 0


# ---------------------------------------------------------------- T20 (diff part): errors

def test_T20_diff_errors(repo, tmp_path):
    raises("REF_NOT_FOUND", d, repo, "no-such-branch")
    target = tmp_path / "x"
    raises("INVALID_ARGUMENT", d, repo, f"--output={target}")
    assert not target.exists()
    raises("INVALID_ARGUMENT", d, repo, "main", base={"worktree": "main"})
    raises("INVALID_ARGUMENT", d, repo, "main", detail="all")
    git(repo, "checkout", "-q", "--orphan", "lonely")
    commit_all(repo, "orphan")
    raises("NO_MERGE_BASE", d, repo, "lonely")


def test_T20_ambiguous_merge_base(repo):
    git(repo, "branch", "a")
    git(repo, "branch", "b")
    for br, f in (("a", "a.txt"), ("b", "b.txt")):
        git(repo, "checkout", "-q", br)
        open(repo / f, "w").write(br)
        commit_all(repo, br)
    a1, b1 = git(repo, "rev-parse", "a"), git(repo, "rev-parse", "b")
    git(repo, "checkout", "-q", "a")
    git(repo, "merge", "-q", "--no-ff", "-m", "a<-b", b1)
    git(repo, "checkout", "-q", "b")
    git(repo, "merge", "-q", "--no-ff", "-m", "b<-a", a1)
    e = raises("AMBIGUOUS_MERGE_BASE", d, repo, "a", mainRef="b")
    assert sorted(e.details["candidates"]) == sorted([a1, b1])


# ---------------------------------------------------------------- T35: worktree mode content

@pytest.fixture
def wt(repo, tmp_path):
    """feat-x checked out in its own worktree, one committed element on it; main moved on afterwards."""
    w = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feat-x", str(w))
    add(w, el("branchY"))
    commit_all(w, "Y on branch")
    add(repo, el("mainX"))
    commit_all(repo, "X on main later")
    return w


def W(repo, **kw):
    return d(repo, {"worktree": "feat-x"}, detail="items", **kw)


def test_T35_content_rules(repo, wt):
    edit(wt, "am4.ttl", '"供应商"@zh', '"供货商"@zh')                          # (a) tracked, modified
    open(wt / "models/procurement/extra.ttl", "w").write(HDR + el("extraE"))   # (b) untracked new file
    os.remove(wt / "models/procurement/uml.ttl")                               # (c) tracked, deleted, unstaged
    open(wt / ".gitignore", "w").write("models/procurement/ignored.ttl\n")
    open(wt / "models/procurement/ignored.ttl", "w").write(HDR + el("ignoredI"))
    open(wt / "models/procurement/staged.ttl", "w").write(HDR + el("stagedS"))
    git(wt, "add", "models/procurement/staged.ttl")                            # staged, not committed
    nested = init_repo(wt / "models/nested")
    open(nested / "n.ttl", "w").write(HDR + el("nestedN"))
    commit_all(nested)
    index = git(wt, "rev-parse", "--path-format=absolute", "--git-path", "index")
    before, index_before = status(wt), open(index, "rb").read()
    r = W(repo)
    got = changes(r)
    assert ("supplier", "modified") in got and ("extraE", "added") in got and ("stagedS", "added") in got
    assert {("QuotationEntity", "removed"), ("rel-QuotationEntity-refines-quotationAggregate", "removed")} <= got
    assert ("branchY", "added") in got                                          # committed on the branch
    assert not any(n in ("mainX", "ignoredI", "nestedN") for n, _ in got)        # merge-base; ignored; nested repo
    sup = next(i for i in r["items"] if i["iri"] == M + "supplier")
    assert sup["changedPredicates"] == [SKOS_PREF]
    assert r["head"] == {"kind": "worktree", "branch": "feat-x", "headCommit": git(wt, "rev-parse", "HEAD"), "dirty": True}
    assert r["incomplete"] is False
    assert status(wt) == before                                                 # read-only, index untouched
    assert open(index, "rb").read() == index_before
    ref = d(repo, "feat-x", detail="items")                                     # Git ref mode: committed only
    assert changes(ref) == {("branchY", "added")}


def test_T35_broken_file_makes_removals_indeterminate(repo, wt):
    edit(wt, "am4.ttl", '"供应商"@zh', '"供货商"@zh')
    os.remove(wt / "models/procurement/uml.ttl")
    open(wt / "models/procurement/broken.ttl", "w").write(HDR + ":half a am4:BusinessObject ;\n")
    r = W(repo)
    assert r["incomplete"] is True and [f["file"] for f in r["failedFiles"]] == ["models/procurement/broken.ttl"]
    assert ("supplier", "modified") in changes(r)
    # R2-14: with a failed file, nothing committed-but-unseen is reported removed (the deletion becomes undecidable)
    assert not [i for i in r["items"] if i["change"] == "removed"]
    assert {M + "QuotationEntity", M + "rel-QuotationEntity-refines-quotationAggregate"} <= set(r["indeterminate"])


def test_T35_truncated_tracked_file(repo, wt):
    p = wt / "models/procurement/code.ttl"
    s = open(p).read()
    open(p, "w").write(s[: len(s) // 2])
    r = W(repo)
    assert r["incomplete"] is True and CODE_SUBJECTS <= set(r["indeterminate"])
    assert changes(r) == {("branchY", "added")}  # nothing of code.ttl is reported, least of all as removed


def test_T35_renamed_then_truncated(repo, wt):
    git(wt, "mv", "models/procurement/code.ttl", "models/procurement/code2.ttl")
    p = wt / "models/procurement/code2.ttl"
    s = open(p).read()
    open(p, "w").write(s[: len(s) // 2])
    r = W(repo)
    assert CODE_SUBJECTS <= set(r["indeterminate"]) and not [i for i in r["items"] if i["change"] == "removed"]


def test_T35_symlinks_and_fifo(repo, wt, tmp_path):
    os.symlink("/etc/hosts", wt / "models/procurement/hosts.ttl")
    p = wt / "models/procurement/pipe.ttl"
    open(p, "w").write("")
    commit_all(wt, "pipe")
    os.remove(p)
    os.mkfifo(p)
    r = W(repo)
    errs = {f["file"]: f["error"] for f in r["failedFiles"]}
    assert errs == {"models/procurement/hosts.ttl": "symlink", "models/procurement/pipe.ttl": "not-regular"}


def test_T35_parent_dir_symlink_outside(repo, wt, tmp_path):
    outside = tmp_path / "outside"
    shutil.copytree(wt / "models/procurement", outside)
    with open(outside / "am4.ttl", "a") as f:
        f.write(":SECRET_FROM_OUTSIDE a am4:BusinessObject .\n")
    shutil.rmtree(wt / "models/procurement")
    os.symlink(outside, wt / "models/procurement")
    r = W(repo)
    assert r["incomplete"] is True and {f["error"] for f in r["failedFiles"]} == {"symlink"}
    assert "SECRET_FROM_OUTSIDE" not in repr(r)


def test_T35_assume_unchanged_and_skip_worktree(repo, wt):
    edit(wt, "am4.ttl", '"供应商"@zh', '"供货商"@zh')
    git(wt, "update-index", "--assume-unchanged", "models/procurement/am4.ttl")
    assert status(wt) == ""                       # git status is silent about it ...
    assert ("supplier", "modified") in changes(W(repo))   # ... the diff is not
    git(wt, "update-index", "--no-assume-unchanged", "models/procurement/am4.ttl")
    git(wt, "checkout", "-q", "--", "models/procurement/am4.ttl")
    git(wt, "update-index", "--skip-worktree", "models/procurement/uml.ttl")
    os.remove(wt / "models/procurement/uml.ttl")
    r = W(repo)
    assert not [i for i in r["items"] if i["change"] == "removed"] and r["incomplete"] is False


def test_T35_clean_worktree_equals_ref_and_fast_path(repo, wt, tmp_path):
    r = W(repo)
    ref = d(repo, git(wt, "rev-parse", "HEAD"), detail="items")
    assert r["head"]["dirty"] is False and r["items"] == ref["items"] and r["counts"] == ref["counts"]
    w2 = tmp_path / "wt2"
    git(repo, "worktree", "add", "-q", "-b", "feat-clean", str(w2))
    n = diff.PARSE_CALLS
    r = d(repo, {"worktree": "feat-clean"})
    assert diff.PARSE_CALLS == n and r["changedElementCount"] == 0 and r["head"]["dirty"] is False


def test_T35_reread_until_stable(repo, wt, monkeypatch):
    edit(wt, "am4.ttl", '"供应商"@zh', '"供货商"@zh')  # dirty, so the files are really read (no fast path)
    p = os.path.join(str(wt), "models/procurement/am4.ttl")
    real, calls = gitio.read_file, []

    def flaky(root, rel):  # the first read of am4.ttl races with one save; later reads are stable
        data = real(root, rel)
        if rel.endswith("am4.ttl") and not calls:
            calls.append(1)
            with open(p, "a") as f:
                f.write(el("savedDuringRead"))
        return data
    monkeypatch.setattr(gitio, "read_file", flaky)
    assert ("savedDuringRead", "added") in changes(W(repo))

    def always(root, rel):
        data = real(root, rel)
        if rel.endswith("am4.ttl"):
            with open(p, "a") as f:
                f.write("\n# keeps changing\n")
        return data
    monkeypatch.setattr(gitio, "read_file", always)
    e = raises("WORKTREE_CHANGED", W, repo)
    assert e.retryable is True


# ---------------------------------------------------------------- T36: worktree location and refusal

def test_T36_refusals_open_nothing(repo, wt, tmp_path, monkeypatch):
    opened = []
    real_open, real_os_open = builtins.open, os.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: opened.append(str(f)) or real_open(f, *a, **k))
    monkeypatch.setattr(os, "open", lambda f, *a, **k: opened.append(str(f)) or real_os_open(f, *a, **k))
    for bad in ("/etc", str(wt), "../x", f"--output={tmp_path / 'x'}", "refs/heads/feat-x", "@{-1}", "a\\b", ""):
        raises("INVALID_ARGUMENT", d, repo, {"worktree": bad})
    e = raises("INVALID_ARGUMENT", d, repo, {"worktree": "feat-x", "path": "/etc"})
    assert e.details["rejectedFields"] == ["path"]
    assert raises("WORKTREE_NOT_FOUND", d, repo, {"worktree": "nope"}).details["branchExists"] is False
    git(repo, "branch", "parked")
    assert raises("WORKTREE_NOT_FOUND", d, repo, {"worktree": "parked"}).details["branchExists"] is True
    assert opened == [] and not (tmp_path / "x").exists()


def test_T36_pruned_outside_root_and_foreign_gitdir(repo, tmp_path):
    w = tmp_path / "gone"
    git(repo, "worktree", "add", "-q", "-b", "gone", str(w))
    shutil.rmtree(w)
    raises("WORKTREE_NOT_FOUND", d, repo, {"worktree": "gone"})
    out = tmp_path / "elsewhere" / "wt"
    git(repo, "worktree", "add", "-q", "-b", "far", str(out))
    cfg = Config(allow_roots=(str(repo),))
    raises("PATH_OUTSIDE_ROOT", diff.model_diff, cfg, {"worktree": "far"}, repo=str(repo))
    foreign = init_repo(tmp_path / "foreign")
    open(foreign / "f", "w").write("x")
    commit_all(foreign)
    w2 = tmp_path / "w2"
    git(repo, "worktree", "add", "-q", "-b", "hijack", str(w2))
    gd = os.path.join(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"), "worktrees", "w2", "gitdir")
    open(gd, "w").write(str(foreign / ".git") + "\n")
    raises("WORKTREE_NOT_FOUND", d, repo, {"worktree": "hijack"})


def test_T35_status_does_not_rewrite_index(repo, wt):
    """A touched (mtime only) tracked file makes a plain `git status` refresh and rewrite .git/index; the diff must not."""
    index = git(wt, "rev-parse", "--path-format=absolute", "--git-path", "index")
    git(wt, "status")  # settle the index first
    before = open(index, "rb").read()
    p = wt / "models/procurement/am4.ttl"
    os.utime(p, (os.stat(p).st_atime + 100, os.stat(p).st_mtime + 100))
    r = W(repo)
    assert r["head"]["dirty"] is False and open(index, "rb").read() == before
