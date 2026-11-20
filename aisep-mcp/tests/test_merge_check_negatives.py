"""Merge-time check: negatives written BEFORE the implementation (docs/mcp-interface.md §5.9 "合并时校验" / "合并前重算" /
"批准专用 PR" / "发布关口", the approval-commit criterion of step 1, §11 T38 / T39 / T40 / T43, "第三轮" + "核对轮").

Each test first builds its Git topology in a tmp repo (+ a local bare `origin`; nothing is ever pushed to GitHub) and
asserts the topology itself; only then does it call the checker. While the checker module does not exist the call ends
the test as XFAIL ("检查脚本未实现"); a fixture bug fails the test before that point. Every negative has a positive twin
on the same builder, so a checker that rejects everything (or nothing) cannot pass.

Interface contract the implementation session (slice S6) is to provide — module `aisep.mergecheck` (CHECKER below):

    merge_check(repo, pr_head, target_ref, *, head_ref, now, remote="origin") -> list[problem]
        repo       path of a full clone; pr_head = pull_request.head.sha (40 hex); target_ref = the current main ref,
                   e.g. "refs/heads/main" (CI: refs/remotes/origin/main; tests also pass a commit id); head_ref = pull_request.head.ref (the PR
                   source branch name, compared with aisep:branch of new activities); now = aware UTC datetime (the
                   injected clock of check 3); remote = where release tags are read (git ls-remote).
        Runs checks 1–7, the approval-only-PR rules and the release-tag check. Builds M locally
        (T + `git merge --no-ff --no-commit H` in a scratch worktree) and leaves every ref and the caller's worktree
        unchanged. [] = may merge.
    classify_pr(repo, pr_head, target_ref) -> "approval-only" | "normal"
    approval_commit_problems(repo, evidence, tip) -> list[problem]
        The step-1 criterion over evidence..tip (no merge commit; every commit satisfies (a)(b)(c)); the same function
        record_approval step 1/7 calls. merge_check must call it through the module attribute (the T38 stub test counts).
    pr_inputs(event, env) -> {"pr_head", "head_ref", "target_ref"}
        From the GitHub event payload and environment: pr_head = event.pull_request.head.sha, never env GITHUB_SHA.

    problem: a mapping with key "reason" (values below); "offendingCommit" (40 hex) when a commit is to blame, "iri"
    when a record / element / activity is. Git command failure (non-zero exit, shallow clone) is a problem with reason
    "git-error" — fail closed, never skipped.

reason vocabulary (details.reason; the two marked * are the strings §5.9 step 1 already fixes):
    merge-commit-in-range           criterion: a merge commit in evidence..tip (step 1, R2-9)
    not-approval-commit             criterion: a commit failing (a) trailer, (b) one new 100644 governance/*.ttl, (c) one record
    evidence-not-ancestor           evidence is not an ancestor of the PR head / tip (check 3)
    governance-record-modified      an ApprovalRecord / AgentActivity already on T is modified (check 1, E)
    governance-record-removed       … or removed, Rejected records included (check 1, E)
    evidence-not-commit             evidence is sha256:… (check 3, C)
    generated-at-future             generatedAtTime > now + 5 min (check 3, C)
    approves-missing-at-evidence    an approves IRI absent from the evidence snapshot (check 3, 核对轮 2)
    mainline-head-gate-not-release* evidence's effective content commit is on T but gate ≠ GateRelease (check 3, U4①)
    release-head-not-on-main*       GateRelease evidence not an ancestor of T (check 3, O)
    release-in-normal-pr            a new GateRelease record outside an approval-only PR (check 3, O)
    activity-on-mainline-approval   a mainline-evidence record carries aisep:activity (check 3, U4①)
    activity-base-mismatch          new activity baseCommit ≠ merge-base(headCommit, T) (check 4, Q)
    activity-branch-mismatch        new activity aisep:branch ≠ head_ref (check 4, Q)
    ambiguous-merge-base            merge-base(headCommit, T) has several answers (check 4)
    merge-result-gate-failed        model_gate on M fails (check 5, U3)
    unapproved-change-to-approved   element Approved on T modified / pre-approved IRI added, no new covering record (check 6, U1, 核对轮 2)
    approved-element-removed        element Approved on T removed (check 6, Q6④, 核对轮 1)
    approved-content-drifted        an approved object differs between the evidence snapshot and M (check 7, I, 核对轮 3/5)
    release-tag-missing             no compliantly named tag (release/{yyyymmdd}-{ev7} | release/v…) for an Approved GateRelease (tag check, K)
    release-tag-mismatch            such a tag exists but peels to another commit (tag check, K, L)
    git-error                       a git command failed / shallow clone (口径, G)

Not covered here (other slices): record_approval's own errors (STALE_HEAD, INVALID_ARGUMENT …, slice S5), the workbench's
tag/branch creation (client.ts, S8), the record_approval half of the stub-count test, and the GitHub server-side merge
of T43 (only the local `git merge` is exercised).
"""
import functools, importlib, os, subprocess
from datetime import datetime, timezone

import pytest

from conftest import PY
from fixtures.topology import AM4, GOV, M, Topo, git

CHECKER = "aisep.mergecheck"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
MAIN = "refs/heads/main"


# ------------------------------------------------------------------ checker access (xfail until S6 exists)
# While the checker is missing, call() returns a _Pending placeholder instead of stopping the test, so every test still
# builds ALL its fixtures (the positive twins after the first check included); the wrapper at the bottom of this file
# then ends the test as XFAIL. A fixture assertion that fails anywhere in the test is a real failure.

class _Pending:
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = None

    def __getitem__(self, k):
        return self

    def __iter__(self):
        return iter(())


_missing = []


def _module():
    try:
        return importlib.import_module(CHECKER)
    except ModuleNotFoundError as e:
        if e.name == CHECKER:
            return None
        raise


def call(name, *a, **kw):
    mod = _module()
    fn = getattr(mod, name, None) if mod else None
    if fn is None:
        _missing.append(f"检查脚本未实现：{CHECKER}{'' if mod is None else '.' + name} 不存在（附录 D GAP，切片 S6）")
        return _Pending()
    try:
        return fn(*a, **kw)
    except NotImplementedError:
        _missing.append(f"检查脚本未实现：{CHECKER}.{name} 抛 NotImplementedError")
        return _Pending()


def check(t, head, head_ref, target=MAIN, now=NOW, repo=None):
    return call("merge_check", str(repo or t.root), head, target, head_ref=head_ref, now=now)


def _get(p, k):
    return p.get(k) if hasattr(p, "get") else getattr(p, k, None)


def reasons(problems):
    if isinstance(problems, _Pending):
        return problems
    return {_get(p, "reason") for p in problems}


def assert_clean(problems):
    if isinstance(problems, _Pending):
        return
    assert list(problems) == [], problems


def assert_rejected(problems, reason, offending=None, iri=None):
    if isinstance(problems, _Pending):
        return
    hits = [p for p in problems if _get(p, "reason") == reason]
    assert hits, f"expected reason {reason!r}, got {problems}"
    if offending:
        assert offending in {_get(p, "offendingCommit") for p in hits}, hits
    if iri:
        assert iri in {_get(p, "iri") for p in hits}, hits


# ------------------------------------------------------------------ topology helpers

@pytest.fixture
def t(template, tmp_path):
    return Topo(template, tmp_path)


def feature(t, branch="feat/x", element="newThing", label="新东西", start="main"):
    t.checkout(start, new=branch)
    return t.add_element(element, label)


def act(t, head, branch, base=None, local=None):
    return dict(local=local or f"activity-20261120-{head[:7]}", head=head,
                base=base or t.merge_base(head, MAIN), branch=branch)


def release_branch(t, r, ts="20261120120000"):
    name = f"approval/release-{r[:7]}-{ts}"
    t.checkout(r, new=name)
    return name


def refs_snapshot(t):
    return t.git("for-each-ref", "--format=%(refname) %(objectname)"), t.git("status", "--porcelain")


def cli_gate(t, commit, merge=None):
    """Fixture verification only: run the real `aisep.py gate` on a detached checkout of commit (optionally with
    `git merge --no-ff --no-commit merge` applied). Returns True on PASS."""
    d = t.tmp / f"gate-{len(os.listdir(t.tmp))}"
    t.git("worktree", "add", "-q", "--detach", str(d), commit)
    if merge:
        git(d, "merge", "-q", "--no-ff", "--no-commit", merge)
    p = subprocess.run([PY, "tools/aisep.py", "gate"], cwd=d, capture_output=True, text=True)
    t.git("worktree", "remove", "--force", str(d))
    return p.returncode == 0 and "result=PASS" in p.stdout


# ================================================================== fixture sanity (runs for real, must pass)

def test_fixture_baseline_and_approval_commit_pass_real_gate(t):
    """The builders write records the prototype accepts: baseline main and a branch with an activity-linked approval
    commit both gate PASS, and the approval commit has exactly the §5.9 shape (one A line, 100644, one trailer)."""
    assert cli_gate(t, t.rev(MAIN))
    h = feature(t)
    a, local, _ = t.approve("GateArchitecture", ["newThing"], activity=act(t, h, "feat/x"))
    assert t.git("show", "--format=", "--name-status", a) == f"A\t{GOV}/{local}.ttl"
    assert t.git("ls-tree", a, f"{GOV}/{local}.ttl").split()[0] == "100644"
    assert t.git("log", "-1", "--format=%(trailers:key=AISEP-Evidence,valueonly)", a).strip() == h
    assert cli_gate(t, a)


# ================================================================== step-1 criterion (approval_commit_problems)

def test_criterion_empty_range_and_two_gates_pass(t):
    h = feature(t)
    assert t.rev() == h
    a1, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h)
    a2, _, _ = t.approve("GateDesign", ["newThing"], evidence=h)
    assert t.git("rev-list", "--count", f"{h}..{a2}") == "2"
    assert_clean(call("approval_commit_problems", str(t.root), h, h))
    assert_clean(call("approval_commit_problems", str(t.root), h, a2))


def test_criterion_code_commit_after_approval_rejected(t):
    h = feature(t)
    t.approve("GateArchitecture", ["newThing"], evidence=h)
    c = t.relabel("newThing", "新东西改")
    assert_rejected(call("approval_commit_problems", str(t.root), h, c), "not-approval-commit", offending=c)


def test_criterion_merge_commit_rejected(t):
    h = feature(t)
    t.approve("GateArchitecture", ["newThing"], evidence=h)
    t.checkout("main"); t.relabel("supplier", "供应商V2")
    t.checkout("feat/x"); t.git("merge", "-q", "--no-ff", "-m", "merge main", "main")
    m = t.rev()
    assert len(t.git("rev-list", "--min-parents=2", f"{h}..{m}").split()) == 1
    assert_rejected(call("approval_commit_problems", str(t.root), h, m), "merge-commit-in-range")


def _deviation(t, kind):
    h = feature(t)
    act_ = act(t, h, "feat/x")
    if kind == "valid":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h)[0]
    if kind == "valid-with-activity":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, activity=act_)[0]
    if kind == "a-forged-trailer":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, trailer="0" * 40)[0]
    if kind == "a-two-trailers":
        from fixtures.topology import PREFIXES, record_ttl
        t.write(f"{GOV}/approval-x.ttl", PREFIXES + record_ttl("approval-x", "GateArchitecture", ["newThing"], h))
        return h, t.commit_all("aisep: two trailers", trailers=[f"AISEP-Evidence: {h}", f"AISEP-Evidence: {h}"])
    if kind == "b-modifies-governance-ttl":
        t.write("models/procurement/governance.ttl", "\n:intruder a arch:Stakeholder ;\n    arch:inModel <" + M +
                "> ;\n    skos:prefLabel \"闯入者\"@zh .\n", "a")
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h)[0]
    if kind == "b-non-ttl":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, path=f"{GOV}/approval-x.txt")[0]
    if kind == "b-subdirectory":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, path=f"{GOV}/sub/approval-x.ttl")[0]
    if kind == "b-symlink":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, symlink=True)[0]
    if kind == "b-executable":
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, executable=True)[0]
    if kind == "c-two-records":
        from fixtures.topology import record_ttl
        extra = record_ttl("approval-extra", "GateDesign", ["newThing"], h)
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, extra_ttl=extra)[0]
    if kind == "c-record-plus-stakeholder":
        extra = "\n:fakeApprover a arch:Stakeholder ;\n    arch:inModel <" + M + "> ;\n    skos:prefLabel \"假人\"@zh .\n"
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, extra_ttl=extra)[0]
    if kind == "c-activity-only":
        return h, t.activity_only(act_["local"], h, act_["base"], "feat/x")
    raise AssertionError(kind)


DEVIATIONS = ["a-forged-trailer", "a-two-trailers", "b-modifies-governance-ttl", "b-non-ttl", "b-subdirectory",
              "b-symlink", "b-executable", "c-two-records", "c-record-plus-stakeholder", "c-activity-only"]


@pytest.mark.parametrize("kind", ["valid", "valid-with-activity"])
def test_criterion_valid_shapes_pass(t, kind):
    h, a = _deviation(t, kind)
    assert t.git("show", "--format=", "--name-status", a).startswith("A\t")
    assert_clean(call("approval_commit_problems", str(t.root), h, a))


@pytest.mark.parametrize("kind", DEVIATIONS)
def test_criterion_deviation_is_not_an_approval_commit(t, kind):
    h, a = _deviation(t, kind)
    assert t.git("rev-list", "--count", f"{h}..{a}") == "1"
    if kind == "b-symlink":
        assert t.git("ls-tree", a, "--", f"{GOV}/").count("120000") == 1
    if kind == "b-executable":
        assert "100755" in t.git("ls-tree", "-r", a, "--", f"{GOV}/")
    assert_rejected(call("approval_commit_problems", str(t.root), h, a), "not-approval-commit", offending=a)


# ================================================================== T38 merge-time check

def test_T38_code_commit_after_approval_rejected_and_two_gates_pass(t):
    h = feature(t)
    t.approve("GateArchitecture", ["newThing"], activity=act(t, h, "feat/x"))
    a2, _, _ = t.approve("GateDesign", ["newThing"], evidence=h, at="2026-11-20T11:10:00Z")  # 连过两个关口
    before = refs_snapshot(t)
    assert_clean(check(t, a2, "feat/x"))
    assert refs_snapshot(t) == before  # 检查前后两条分支头不变
    c = t.relabel("newThing", "新东西改")
    assert_rejected(check(t, c, "feat/x"), "not-approval-commit", offending=c)


def test_T38_merge_main_into_branch_after_approval_rejected(t):
    h = feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"])
    t.checkout("main"); t.relabel("supplier", "供应商V2")
    t.checkout("feat/x"); t.git("merge", "-q", "--no-ff", "-m", "Merge main (Resolve conflicts)", "main")
    m = t.rev()
    assert_rejected(check(t, m, "feat/x"), "merge-commit-in-range")
    assert_clean(check(t, a, "feat/x"))  # positive: same approval without the merge


def test_T38_same_gate_superset_later_supersedes(t):
    h1 = feature(t)
    t.add_element("otherThing", "另一个")
    h1 = t.rev()
    t.approve("GateArchitecture", ["newThing", "otherThing"], evidence=h1)
    h2 = t.relabel("newThing", "新东西改")
    a, _, _ = t.approve("GateArchitecture", ["newThing", "otherThing"], evidence=h2, at="2026-11-20T11:30:00Z")
    assert_clean(check(t, a, "feat/x"))


def test_T38_partial_new_record_does_not_supersede(t):
    feature(t); t.add_element("otherThing", "另一个"); h1 = t.rev()
    t.approve("GateArchitecture", ["newThing", "otherThing"], evidence=h1)
    h2 = t.relabel("newThing", "新东西改")
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h2, at="2026-11-20T11:30:00Z")
    assert_rejected(check(t, a, "feat/x"), "not-approval-commit", offending=h2)


def test_T38_cross_gate_record_does_not_supersede(t):
    """D: an older GateMerge record is still checked when a later GateRequirements record covers the same object."""
    h1 = feature(t)
    t.approve("GateMerge", ["newThing"], evidence=h1)
    h2 = t.relabel("newThing", "新东西改")
    a, _, _ = t.approve("GateRequirements", ["newThing"], evidence=h2, at="2026-11-20T11:30:00Z")
    assert_rejected(check(t, a, "feat/x"), "not-approval-commit", offending=h2)


def test_T38_same_instant_records_both_checked(t):
    h1 = feature(t)
    t.approve("GateArchitecture", ["newThing"], evidence=h1, at="2026-11-20T11:00:00Z")
    h2 = t.relabel("newThing", "新东西改")
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h2, at="2026-11-20T11:00:00Z")
    assert_rejected(check(t, a, "feat/x"), "not-approval-commit", offending=h2)


def test_T38_existing_record_rewritten_rejected_although_gate_passes(t):
    """E: rewrite the approves of a record already on T. Gate PASS on the PR head (so only this check stops it)."""
    t.checkout("main", new="feat/x")
    rel = f"{GOV}/approval-20261119-architecture-audittrail.ttl"
    t.write(rel, t.read(rel).replace("aisep:approves :auditTrail", "aisep:approves :auditTrail, :supplier"))
    h = t.commit_all("widen an existing approval")
    assert cli_gate(t, h)
    assert_rejected(check(t, h, "feat/x"), "governance-record-modified", iri=t.base_record)


def test_T38_existing_activity_rewritten_rejected(t):
    t.checkout("main", new="feat/x")
    rel = f"{GOV}/approval-20261119-architecture-audittrail.ttl"
    t.write(rel, t.read(rel).replace('"ao-session-0"', '"ao-session-forged"'))
    h = t.commit_all("rewrite an existing activity")
    assert_rejected(check(t, h, "feat/x"), "governance-record-modified", iri=t.base_activity)


def test_T38_delete_rejected_record_rejected(t):
    t.checkout("main", new="feat/x")
    t.git("rm", "-q", f"{GOV}/approval-20261119-requirements-rejected.ttl")
    h = t.commit_all("drop the rejection")
    assert_rejected(check(t, h, "feat/x"), "governance-record-removed", iri=t.base_rejected)


def test_T38_unrelated_content_pr_is_clean(t):
    """Positive twin of the E cases and of U1: a PR touching nothing approved and no record."""
    h = feature(t)
    assert_clean(check(t, h, "feat/x"))


def test_T38_sha256_evidence_rejected(t):
    h = feature(t)
    ev = "sha256:" + "ab" * 32
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=ev)
    assert_rejected(check(t, a, "feat/x"), "evidence-not-commit")
    t.git("reset", "-q", "--hard", h)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h)
    assert_clean(check(t, a, "feat/x"))


@pytest.mark.parametrize("at,forge_committer,bad", [
    ("2026-11-20T12:06:00Z", False, True),
    ("2026-11-20T12:06:00Z", True, True),   # committer time forged to the same future instant: verdict unchanged
    ("2026-11-20T12:04:00Z", False, False),
])
def test_T38_future_generated_at(t, at, forge_committer, bad):
    feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], at=at, date=at if forge_committer else None)
    if forge_committer:
        assert t.git("log", "-1", "--format=%cI", a).startswith("2026-11-20T12:06:00")
    p = check(t, a, "feat/x")
    if bad:
        assert_rejected(p, "generated-at-future")
    else:
        assert_clean(p)


def test_T38_approves_iri_missing_at_evidence_rejected(t):
    h = feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing", "notYetThere"], evidence=h)
    assert "notYetThere" not in t.git("show", f"{h}:{AM4}")
    assert_rejected(check(t, a, "feat/x"), "approves-missing-at-evidence", iri=M + "notYetThere")


def test_T38_preapproved_iri_created_without_reapproval(t):
    """核对轮 2: T holds a record approving :futureThing before it exists; a PR creating it needs a new approval."""
    t.approve("GateArchitecture", ["futureThing"], evidence=t.rev(MAIN), local="approval-20261120-pre-future")
    t.push("main")
    h = feature(t, element="futureThing", label="未来之物")
    assert_rejected(check(t, h, "feat/x"), "unapproved-change-to-approved", iri=M + "futureThing")
    a, _, _ = t.approve("GateArchitecture", ["futureThing"], evidence=h, at="2026-11-20T11:30:00Z")
    assert_clean(check(t, a, "feat/x"))


def test_T38_U1_modify_approved_element_needs_new_approval(t):
    t.checkout("main", new="feat/x")
    h = t.relabel("auditTrail", "审计轨迹V2")
    assert_rejected(check(t, h, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")
    a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h)
    assert_clean(check(t, a, "feat/x"))


def test_T38_remove_approved_element_always_rejected(t):
    t.checkout("main"); t.add_element("scratchNote", "草稿")  # an unapproved element on T for the positive twin
    t.checkout("main", new="feat/x")
    h = t.remove_block("auditTrail")
    assert_rejected(check(t, h, "feat/x"), "approved-element-removed", iri=M + "auditTrail")
    t.checkout("main", new="feat/y")
    h2 = t.remove_block("scratchNote")
    assert_clean(check(t, h2, "feat/y"))


@pytest.mark.parametrize("forge", ["none", "base", "branch"])
def test_T38_activity_base_and_branch_recomputed(t, forge):
    h = feature(t)
    a_ = act(t, h, "feat/x")
    if forge == "base":
        a_["base"] = t.c0  # a real commit, but not merge-base(h, T)
        assert a_["base"] != t.merge_base(h, MAIN)
    if forge == "branch":
        a_["branch"] = "feat/other"
    a, _, _ = t.approve("GateArchitecture", ["newThing"], activity=a_)
    p = check(t, a, "feat/x")
    if forge == "none":
        assert_clean(p)
    else:
        assert_rejected(p, {"base": "activity-base-mismatch", "branch": "activity-branch-mismatch"}[forge])


def _criss_cross(t):
    """main and feat/x merge each other's tips P1/Q1 → merge-base(main, feat/x) = {P1, Q1} (F)."""
    t.checkout("main", new="feat/x")
    q1 = t.add_element("newThing", "新东西")
    t.checkout("main")
    p1 = t.relabel("supplier", "供应商V2")
    t.git("merge", "-q", "--no-ff", "-m", "main takes feat@Q1", q1)
    t.checkout("feat/x")
    t.git("merge", "-q", "--no-ff", "-m", "feat takes main@P1", p1)
    f1 = t.rev()
    assert sorted(t.git("merge-base", "--all", "main", "feat/x").split()) == sorted([p1, q1])
    return f1


def _linear_same_content(t):
    t.checkout("main"); t.relabel("supplier", "供应商V2")
    t.checkout("main", new="feat/x")
    return t.add_element("newThing", "新东西")


@pytest.mark.parametrize("topology", ["criss-cross", "linear"])
@pytest.mark.parametrize("code_after", [False, True])
def test_T38_criss_cross_verdict_independent_of_merge_base(t, topology, code_after):
    ev = (_criss_cross if topology == "criss-cross" else _linear_same_content)(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=ev)
    h = t.relabel("newThing", "新东西改") if code_after else a
    p = check(t, h, "feat/x")
    if code_after:
        assert reasons(p) == {"not-approval-commit"}, p
    else:
        assert_clean(p)


def test_T38_criss_cross_activity_ambiguous_merge_base_rejected(t):
    f1 = _criss_cross(t)
    assert len(t.git("merge-base", "--all", f1, MAIN).split()) == 2
    a, _, _ = t.approve("GateArchitecture", ["newThing"], activity=act(t, f1, "feat/x", base=f1))
    assert_rejected(check(t, a, "feat/x"), "ambiguous-merge-base")


def test_T38_shallow_clone_fails_closed(t, tmp_path):
    feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"])
    url = "file://" + str(t.root)
    shallow, full = tmp_path / "shallow", tmp_path / "full"
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--no-single-branch", url, str(shallow)], check=True)
    subprocess.run(["git", "clone", "-q", url, str(full)], check=True)
    assert git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    assert git(shallow, "rev-parse", "refs/remotes/origin/feat/x") == a
    p = call("merge_check", str(shallow), a, "refs/remotes/origin/main", head_ref="feat/x", now=NOW)
    assert_rejected(p, "git-error")
    assert_clean(call("merge_check", str(full), a, "refs/remotes/origin/main", head_ref="feat/x", now=NOW))


def test_T38_github_sha_is_not_the_pr_head(t):
    """G: GITHUB_SHA is the test merge commit; the script takes pull_request.head.sha."""
    feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"])
    t.git("checkout", "-q", "--detach", "main")
    t.git("merge", "-q", "--no-ff", "-m", "test merge", a)
    g = t.rev()
    t.checkout("main")
    assert g != a and t.git("rev-parse", f"{g}^2") == a
    event = {"pull_request": {"head": {"sha": a, "ref": "feat/x"}, "base": {"ref": "main"}, "number": 9}}
    inp = call("pr_inputs", event, {"GITHUB_SHA": g, "GITHUB_REF": "refs/pull/9/merge"})
    assert inp["pr_head"] == a and inp["head_ref"] == "feat/x" and inp["target_ref"] in (MAIN, "refs/remotes/origin/main")
    assert_clean(check(t, a, "feat/x"))
    assert_rejected(check(t, g, "feat/x"), "merge-commit-in-range")  # why GITHUB_SHA must not be used


def test_T38_merge_result_gate_and_pre_merge_recompute(t):
    """Check 5 + U3: CI passes on T1; main then deletes the element the PR's new relationship targets (T2). Both
    sides gate PASS, the merge result fails; recomputing against the current T2 refuses the merge."""
    t.checkout("main"); t1 = t.add_element("ledger", "台账", rel="models/procurement/ledger.ttl")
    t.checkout("main", new="feat/x")
    h = t.add_relationship("rel-quoteApproval-accesses-ledger", "am4:Access", "quoteApproval", "ledger")
    t.checkout("main"); t2 = t.remove_block("ledger", rel="models/procurement/ledger.ttl")
    t.checkout("feat/x")
    assert t1 != t2 and t.merge_base(h, MAIN) == t1
    assert cli_gate(t, t1, merge=h) and cli_gate(t, t2) and cli_gate(t, h) and not cli_gate(t, t2, merge=h)
    before = refs_snapshot(t)
    assert_clean(check(t, h, "feat/x", target=t1))  # CI ran when main was at T1
    assert refs_snapshot(t) == before  # 检查前后两条分支头不变、工作区不变
    assert_rejected(check(t, h, "feat/x"), "merge-result-gate-failed")  # 合并前重算 against the current T2


def test_T38_stub_count_criterion_called_by_merge_check(t, monkeypatch):
    """CI and record_approval step 1 call one criterion function (CI half; the record_approval half waits for S5)."""
    feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"])
    mod = _module()
    if mod is None or not hasattr(mod, "approval_commit_problems"):
        call("approval_commit_problems")  # records the missing piece → XFAIL
        return
    calls = []
    real = mod.approval_commit_problems
    monkeypatch.setattr(mod, "approval_commit_problems", lambda *a_, **k: calls.append(a_) or real(*a_, **k))
    assert_clean(check(t, a, "feat/x"))
    assert calls


@pytest.mark.parametrize("main_touches", ["quotation", "supplier"])
def test_T38_approved_content_drifted_on_main(t, main_touches):
    """核对轮 5: the PR approves :quotation (unchanged on the branch); main then relabels it → evidence ≠ M for it.
    Positive twin: main relabels :supplier instead."""
    h = feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing", "quotation"], evidence=h)
    t.checkout("main"); t.relabel(main_touches, "主线改名")
    t.checkout("feat/x")
    assert not t.git("rev-list", "--min-parents=2", f"{h}..{a}")
    p = check(t, a, "feat/x")
    if main_touches == "quotation":
        assert_rejected(p, "approved-content-drifted", iri=M + "quotation")
    else:
        assert_clean(p)


# ================================================================== T39 approval-only PR

def _release(t, r=None, *, tag=True, approves=("quoteApproval",), gate="GateRelease", **kw):
    r = r or t.rev(MAIN)
    name = release_branch(t, r)
    a, local, iri = t.approve(gate, list(approves), evidence=r, **kw)
    if tag:
        t.tag(f"release/20261120-{r[:7]}", r)
    return r, name, a


def test_T39_release_branch_is_approval_only_and_clean(t):
    r, name, a = _release(t)
    assert t.git("rev-list", f"{a}", f"^{MAIN}") == a
    assert call("classify_pr", str(t.root), a, MAIN) == "approval-only"
    assert_clean(check(t, a, name))


def test_T39_forged_release_commit_passes_ci_not_a_security_guarantee(t):
    """U4②: a hand-written, correctly shaped GateRelease commit (borrowing an existing Stakeholder) is classified
    approval-only and passes. The criterion checks shape, not provenance; the human PR approval is the guard."""
    r = t.rev(MAIN)
    name = release_branch(t, r)
    a, _, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, local="approval-20261120-release-handwritten")
    t.tag(f"release/20261120-{r[:7]}", r)
    assert call("classify_pr", str(t.root), a, MAIN) == "approval-only"
    assert_clean(check(t, a, name))


@pytest.mark.parametrize("extra", ["code-commit", "stakeholder-in-governance-ttl", "forged-trailer", "activity-only"])
def test_T39_extra_commit_makes_pr_normal(t, extra):
    r = t.rev(MAIN)
    name = release_branch(t, r)
    trailer = "0" * 40 if extra == "forged-trailer" else None
    a, _, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, trailer=trailer)
    t.tag(f"release/20261120-{r[:7]}", r)
    if extra == "code-commit":
        t.add_element("sneaky", "夹带")
    elif extra == "stakeholder-in-governance-ttl":
        t.write("models/procurement/governance.ttl", "\n:intruder a arch:Stakeholder ;\n    arch:inModel <" + M +
                "> ;\n    skos:prefLabel \"闯入者\"@zh .\n", "a")
        t.commit_all("add a person")
    elif extra == "activity-only":
        t.activity_only("activity-20261120-orphan", r, r, name)
    h = t.rev()
    assert call("classify_pr", str(t.root), h, MAIN) == "normal"
    assert_rejected(check(t, h, name), "release-in-normal-pr")


def test_T39_branch_from_latest_main_with_old_r_rejected(t):
    r = t.rev(MAIN)
    t.checkout("main"); m = t.add_element("later", "之后的提交")
    t.checkout(m, new="approval/release-x")
    a, _, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r)
    t.tag(f"release/20261120-{r[:7]}", r)
    assert t.git("rev-list", f"{r}..{a}").split()[1:] == [m]  # R..head contains the later mainline commit
    assert_rejected(check(t, a, "approval/release-x"), "not-approval-commit", offending=m)


def test_T39_non_release_gate_on_mainline_commit_rejected(t):
    r = t.rev(MAIN)
    release_branch(t, r)
    a, _, _ = t.approve("GateArchitecture", ["quoteApproval"], evidence=r)
    assert_rejected(check(t, a, f"approval/release-{r[:7]}-20261120120000"), "mainline-head-gate-not-release")


def test_T39_gate_architecture_on_release_approval_commit_rejected(t):
    """核对轮 4: headCommit = A (the release approval commit, not on main); its effective content commit is R."""
    r, name, a = _release(t)
    assert subprocess.run(["git", "-C", str(t.root), "merge-base", "--is-ancestor", a, MAIN]).returncode == 1
    a2, _, _ = t.approve("GateArchitecture", ["quoteApproval"], evidence=a, at="2026-11-20T11:30:00Z")
    assert_rejected(check(t, a2, name), "mainline-head-gate-not-release")


def test_T39_release_with_activity_rejected(t):
    r = t.rev(MAIN)
    name = release_branch(t, r)
    a, _, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, activity=act(t, r, "x", base=r))
    t.tag(f"release/20261120-{r[:7]}", r)
    assert_rejected(check(t, a, name), "activity-on-mainline-approval")


def test_T39_release_evidence_not_on_main_rejected(t):
    h = feature(t)
    a, _, _ = t.approve("GateRelease", ["newThing"], evidence=h)
    t.tag(f"release/20261120-{h[:7]}", h, push=True)
    assert_rejected(check(t, a, "feat/x"), "release-head-not-on-main")


@pytest.mark.parametrize("approves,main_touches,drift", [
    (("quoteApproval",), "quoteApproval", True),
    (("quoteApproval",), "supplier", False),
    ((f"<{M}>",), "supplier", True),       # 核对轮 3: model-as-object, a member changed
    ((f"<{M}>",), "new-record", False),    # … only another approval record was added: not a member change
])
def test_T39_release_of_old_r_with_drifted_object(t, approves, main_touches, drift):
    r = t.rev(MAIN)
    t.checkout("main")
    if main_touches == "new-record":
        t.approve("GateArchitecture", ["supplier"], evidence=r, local="approval-20261120-main-other")
    else:
        t.relabel(main_touches, "主线改名")
    _, name, a = _release(t, r, approves=approves)
    p = check(t, a, name)
    if drift:
        assert_rejected(p, "approved-content-drifted")
    else:
        assert call("classify_pr", str(t.root), a, MAIN) == "approval-only"
        assert_clean(p)


# ================================================================== T40 release tag check (CI side) + GC + names

@pytest.mark.parametrize("variant,ok", [
    ("dated", True), ("version", True), ("annotated", True), ("missing", False), ("bad-name", False),
    ("points-elsewhere", False),
])
def test_T40_release_tag(t, variant, ok):
    r = t.rev(MAIN)
    _, name, a = _release(t, r, tag=False)
    other = t.c0
    if variant == "dated":
        t.tag(f"release/20261120-{r[:7]}", r)
    elif variant == "version":
        t.tag("release/v1.2.0", r)
    elif variant == "annotated":
        t.tag(f"release/20261120-{r[:7]}", r, annotated=True)
        assert t.git("rev-parse", f"refs/tags/release/20261120-{r[:7]}") != r  # tag object ≠ R; peeled = R
        assert t.git("rev-parse", f"refs/tags/release/20261120-{r[:7]}^{{commit}}") == r
    elif variant == "bad-name":
        t.tag("release/foo", r)
    elif variant == "points-elsewhere":
        t.tag(f"release/20261120-{r[:7]}", other)
    remote_tags = t.git("ls-remote", "--tags", "origin")
    assert (variant == "missing") == ("release/" not in remote_tags)
    p = check(t, a, name)
    if ok:
        assert_clean(p)
    else:
        assert_rejected(p, "release-tag-mismatch" if variant == "points-elsewhere" else "release-tag-missing")


def test_T40_tag_moved_after_ci_fails(t):
    r, name, a = _release(t)
    assert_clean(check(t, a, name))
    t.tag(f"release/20261120-{r[:7]}", t.c0, force=True)  # local bare origin only
    assert t.git("ls-remote", "origin", f"refs/tags/release/20261120-{r[:7]}").split()[0] == t.c0
    assert_rejected(check(t, a, name), "release-tag-mismatch")


def test_T40_rejected_release_needs_no_tag(t):
    r, name, a = _release(t, tag=False, decision="Rejected")
    assert "release/" not in t.git("ls-remote", "--tags", "origin")
    assert_clean(check(t, a, name))


def test_T40_branch_name_with_seconds_does_not_collide(t, tmp_path):
    """L (git fact the workbench relies on; runs for real): a second approval of the same R with the same branch name
    fails `worktree add -b`; the seconds-stamped name does not."""
    r = t.rev(MAIN)
    n1 = f"approval/release-{r[:7]}-20261120120000"
    t.git("worktree", "add", "-q", "-b", n1, str(tmp_path / "w1"), r)
    assert t.git("worktree", "add", "-q", "-b", n1, str(tmp_path / "w2"), r, check=False) == ""
    assert not (tmp_path / "w2").exists()
    t.git("worktree", "add", "-q", "-b", f"approval/release-{r[:7]}-20261120120001", str(tmp_path / "w3"), r)


def _two_approvals_then_merge(t, squash):
    h1 = feature(t)
    t.approve("GateArchitecture", ["newThing"], evidence=h1)
    h2 = t.relabel("newThing", "新东西改")
    t.approve("GateArchitecture", ["newThing"], evidence=h2, at="2026-11-20T11:30:00Z")
    t.checkout("main")
    if squash:
        t.git("merge", "-q", "--squash", "feat/x")
        t.commit_all("squash feat/x")
    else:
        t.git("merge", "-q", "--no-ff", "-m", "Merge feat/x", "feat/x")
    t.git("branch", "-q", "-D", "feat/x")
    t.git("update-ref", "-d", "ORIG_HEAD", check=False)
    t.git("reflog", "expire", "--expire=now", "--all")
    t.git("gc", "-q", "--prune=now")
    return h1


@pytest.mark.parametrize("squash", [False, True])
def test_T40_gc_keeps_old_evidence_only_with_merge_commit(t, squash):
    """N (falsifiable form; runs for real): H1 lives only on the merged branch side. After merge + delete branch +
    gc --prune=now it stays reachable and its snapshot readable; the squash control loses it."""
    from aisep import gitio
    h1 = _two_approvals_then_merge(t, squash)
    alive = subprocess.run(["git", "-C", str(t.root), "cat-file", "-e", f"{h1}^{{commit}}"]).returncode == 0
    assert alive is (not squash)
    if not squash:
        with gitio.snapshot(str(t.root), h1) as (snap, files):
            assert any(f.endswith("am4.ttl") for f in files)
            assert "新东西" in open(os.path.join(snap, AM4), encoding="utf-8").read()


# ================================================================== T43 one record per file

def test_T43_two_branches_each_approve_then_both_merge_clean(t):
    t.checkout("main", new="feat/a")
    ha = t.add_element("thingA", "甲")
    aa, la, _ = t.approve("GateArchitecture", ["thingA"], evidence=ha)
    t.checkout("main", new="feat/b")
    hb = t.relabel("supplier", "供应商V2")  # mid-file, so the two am4.ttl edits do not touch
    ab, lb, _ = t.approve("GateArchitecture", ["supplier"], evidence=hb, at="2026-11-20T11:05:00Z")
    gov_before = t.git("rev-parse", f"{MAIN}:models/procurement/governance.ttl")
    for a, local in ((aa, la), (ab, lb)):
        assert t.git("show", "--format=", "--name-status", a) == f"A\t{GOV}/{local}.ttl"
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/a", "feat/a")
    t_after_a = t.rev()
    p = subprocess.run(["git", "-C", str(t.root), "merge", "-q", "--no-ff", "-m", "Merge feat/b", "feat/b"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        pytest.fail(f"fixture: second merge conflicted: {p.stdout}{p.stderr}")
    for local in (la, lb):
        assert os.path.isfile(t.path(f"{GOV}/{local}.ttl"))
    assert t.git("rev-parse", "HEAD:models/procurement/governance.ttl") == gov_before
    assert_clean(check(t, aa, "feat/a", target=t.merge_base(aa, t_after_a)))  # PR A against T before it merged
    assert_clean(check(t, ab, "feat/b", target=t_after_a))  # PR B against T after PR A merged


def test_T43_control_append_to_governance_ttl_conflicts(t):
    """Control (runs for real): both branches append a record to governance.ttl → the second merge conflicts."""
    from fixtures.topology import record_ttl
    for br, el in (("feat/a", "supplier"), ("feat/b", "quotation")):
        t.checkout("main", new=br)
        t.write("models/procurement/governance.ttl",
                record_ttl(f"approval-20261120-{el}", "GateArchitecture", [el], t.rev(MAIN)), "a")
        t.commit_all(f"append {el}")
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "a", "feat/a")
    p = subprocess.run(["git", "-C", str(t.root), "merge", "-q", "--no-ff", "-m", "b", "feat/b"],
                       capture_output=True, text=True)
    assert p.returncode != 0 and "governance.ttl" in t.git("diff", "--name-only", "--diff-filter=U")
    t.git("merge", "--abort")


# ------------------------------------------------------------------ every test: build all fixtures, then XFAIL if the
# checker was missing for any call (see "checker access" above)

def _xfail_if_pending(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        _missing.clear()
        fn(*a, **kw)
        if _missing:
            pytest.xfail(f"{_missing[0]}（本例 {len(_missing)} 次检查待实现；夹具已全部建成）")
    return wrapper


for _name, _f in list(globals().items()):
    if _name.startswith("test_") and callable(_f):
        globals()[_name] = _xfail_if_pending(_f)
