"""Merge-time check: negatives written BEFORE the implementation (docs/mcp-interface.md as amended by the 第四轮 review,
PR #11 / ADR-016; §5.9 "合并时校验" / "合并前重算" /
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
        unchanged. M is always merged locally on the given T, never refs/pull/N/merge (R4-10). [] = may merge.
    classify_pr(repo, pr_head, target_ref) -> "approval-only" | "normal"
    approval_commit_problems(repo, evidence, tip) -> list[problem]
        The step-1 criterion over evidence..tip (no merge commit; every commit satisfies (a)(b)(c)); the same function
        record_approval step 1/7 calls. merge_check must call it through the module attribute (the T38 stub test counts).
    target_unchanged(repo, branch, t_used, *, remote="origin") -> bool
        R4-11 ②: `git ls-remote` the target branch right before `gh pr merge`; False → recompute.
    post_merge_verify(repo, new_head, t_used, pr_head, *, head_ref, now) -> list[problem]
        R4-11 ③: new_head's first parent == t_used and second parent == pr_head → []; otherwise re-run the merge-result
        gate and checks 6, 7 on new_head (a failure means: open a revert PR and report).
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
    evidence-gate-failed            an Approved record's evidence snapshot fails model_gate; Rejected not checked (check 3, R4-4)
    merge-conflict                  T + `git merge --no-ff --no-commit H` conflicts (口径, R4-10)
    merge-result-gate-failed        model_gate on M fails (check 5, U3)
    unapproved-change-to-approved   element / model Approved on T modified (retirement included) or pre-approved IRI added, and
                                    no new Approved covering record that is also the effective record on M (check 6, U1,
                                    核对轮 2, R4-2, R4-3, R4-6, G4-2); an illegal record (approves a relationship, view,
                                    Stakeholder: R4-5) never covers
    approved-element-removed        element Approved on T removed, even with a covering record (check 6, Q6④, 核对轮 1, G4-2)
    approved-content-drifted        an approved object differs between the evidence snapshot and M (check 7, I, 核对轮 3/5)
    release-tag-missing             no compliantly named tag (release/{yyyymmdd}-{ev7} | release/v…) for an Approved GateRelease (tag check, K)
    release-tag-mismatch            such a tag exists but peels to another commit (tag check, K, L)
    git-error                       a git command failed / shallow clone (口径, G)
    governance-blank-node           a blank node in the model sources of H or M is typed as, or carries a predicate of, an
                                    ApprovalRecord / AgentActivity (2026-11-22 取证疑点一; independent of the L1 rule)
    governance-type-outside-models  a module or vendor file of M types a subject as an ApprovalRecord / AgentActivity (#105
                                    review; independent of the R1 rule)

Not covered here (other slices): record_approval's own errors (STALE_HEAD, INVALID_ARGUMENT …, slice S5), the workbench's
tag/branch creation (client.ts, S8), the record_approval half of the stub-count test, and the GitHub server-side merge
of T43 (only the local `git merge` is exercised), the revert PR itself after a failed post-merge verification, and
record_approval's own
side of G4-5 (`branch` = refs/heads/… → INVALID_ARGUMENT) and of R4-7 (seconds in the default IRI).
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
    return dict(local=local or f"activity-20261120110000-{head[:7]}", head=head,
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
        c = t.commit_all("aisep: two trailers", trailers=[f"AISEP-Evidence: {h}", f"AISEP-Evidence: {h}"])
        assert t.trailer_count(c) == 2  # the fixture really carries two trailers
        return h, c
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
    if kind == "r4-copies-existing-record":  # 第四轮 R4-8: the copy vanishes from the graph diff
        extra = t.record_block(f"{GOV}/approval-20261119120000-architecture-audittrail.ttl")
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, extra_ttl=extra)[0]
    if kind == "r4-filename-not-local-name":  # 第四轮 R4-8
        return h, t.approve("GateArchitecture", ["newThing"], evidence=h, path=f"{GOV}/approval-renamed.ttl")[0]
    raise AssertionError(kind)


DEVIATIONS = ["a-forged-trailer", "a-two-trailers", "b-modifies-governance-ttl", "b-non-ttl", "b-subdirectory",
              "b-symlink", "b-executable", "c-two-records", "c-record-plus-stakeholder", "c-activity-only",
              "r4-copies-existing-record", "r4-filename-not-local-name"]


@pytest.mark.parametrize("kind", ["valid", "valid-with-activity"])
def test_criterion_valid_shapes_pass(t, kind):
    h, a = _deviation(t, kind)
    assert t.git("show", "--format=", "--name-status", a).startswith("A\t")
    assert_clean(call("approval_commit_problems", str(t.root), h, a))


@pytest.mark.parametrize("kind", DEVIATIONS)
def test_criterion_deviation_is_not_an_approval_commit(t, kind):
    h, a = _deviation(t, kind)
    assert t.git("rev-list", "--count", f"{h}..{a}") == "1"
    added = [l.split() for l in t.git("diff-tree", "-r", "--no-commit-id", "--diff-filter=A", a).splitlines()]
    if kind == "b-symlink":
        assert len(added) == 1 and added[0][1] == "120000", added
    if kind == "b-executable":
        assert len(added) == 1 and added[0][1] == "100755", added
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
    rel = f"{GOV}/approval-20261119120000-architecture-audittrail.ttl"
    t.write(rel, t.read(rel).replace("aisep:approves :auditTrail", "aisep:approves :auditTrail, :supplier"))
    h = t.commit_all("widen an existing approval")
    assert cli_gate(t, h)
    assert_rejected(check(t, h, "feat/x"), "governance-record-modified", iri=t.base_record)


def test_T38_existing_activity_rewritten_rejected(t):
    t.checkout("main", new="feat/x")
    rel = f"{GOV}/approval-20261119120000-architecture-audittrail.ttl"
    t.write(rel, t.read(rel).replace('"ao-session-0"', '"ao-session-forged"'))
    h = t.commit_all("rewrite an existing activity")
    assert_rejected(check(t, h, "feat/x"), "governance-record-modified", iri=t.base_activity)


def test_T38_delete_rejected_record_rejected(t):
    t.checkout("main", new="feat/x")
    t.git("rm", "-q", f"{GOV}/approval-20261119130000-requirements-rejected.ttl")
    h = t.commit_all("drop the rejection")
    assert_rejected(check(t, h, "feat/x"), "governance-record-removed", iri=t.base_rejected)


def test_T38_unrelated_content_pr_is_clean(t):
    """ADR-016 (第四轮 R4-1): an ordinary PR adding a Proposed element with no approval record passes. Also the
    positive twin of the E cases and of U1."""
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


def test_T38_evidence_with_trailing_newline_rejected(t):
    """#77: "<40 hex>\\n" is not a commit id ($ would also match before the trailing newline), neither as a record's
    evidence (the merge-result gate's EG16 refuses it first) nor as the PR head."""
    h = feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h + "\\n", trailer=h)  # Turtle escape -> real "\n"
    p = check(t, a, "feat/x")
    assert_rejected(p, "merge-result-gate-failed")
    assert not isinstance(p, _Pending) and all("aisep:evidence" in _get(x, "message") for x in p), p
    assert_rejected(check(t, a + "\n", "feat/x"), "git-error")
    t.git("reset", "-q", "--hard", h)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h)
    assert_clean(check(t, a, "feat/x"))


def test_whole_string_patterns_reject_trailing_newline():
    """#77: the whole-string checks in mergecheck / release / writer end in \\Z, not $."""
    from aisep import mergecheck, release, writer
    for rx, ok in [(mergecheck.RECORD_FILE, "models/p/governance/a.ttl"), (mergecheck.TAG_DATED, "release/20261120-abcdef0"),
                   (release.RELEASE_BRANCH, "approval/release-abcdef0-20261120120000"), (writer._LOCAL, "quoteApproval")]:
        assert rx.match(ok) and not rx.match(ok + "\n"), rx.pattern


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
    t.approve("GateArchitecture", ["futureThing"], evidence=t.rev(MAIN), local="approval-20261120090000-pre-future")
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


@pytest.mark.parametrize("forge", ["none", "base", "branch", "branch-full-ref"])
def test_T38_activity_base_and_branch_recomputed(t, forge):
    h = feature(t)
    a_ = act(t, h, "feat/x")
    if forge == "base":
        a_["base"] = t.c0  # a real commit, but not merge-base(h, T)
        assert a_["base"] != t.merge_base(h, MAIN)
    if forge == "branch":
        a_["branch"] = "feat/other"
    if forge == "branch-full-ref":  # G4-5: aisep:branch is the short name; refs/heads/feat/x ≠ head_ref
        a_["branch"] = "refs/heads/feat/x"
    a, _, _ = t.approve("GateArchitecture", ["newThing"], activity=a_)
    p = check(t, a, "feat/x")
    if forge == "none":
        assert_clean(p)
    else:
        assert_rejected(p, {"base": "activity-base-mismatch", "branch": "activity-branch-mismatch",
                                  "branch-full-ref": "activity-branch-mismatch"}[forge])


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
    # R4-10: a platform merge ref built on the stale T1 (gate PASS there) must not be used; M is merged on T2
    t.git("checkout", "-q", "--detach", t1)
    t.git("merge", "-q", "--no-ff", "-m", "platform test merge", h)
    t.git("update-ref", "refs/pull/9/merge", t.rev())
    t.checkout("feat/x")
    event = {"pull_request": {"head": {"sha": h, "ref": "feat/x"}, "base": {"ref": "main"}, "number": 9}}
    inp = call("pr_inputs", event, {"GITHUB_SHA": t.rev("refs/pull/9/merge"), "GITHUB_REF": "refs/pull/9/merge"})
    assert inp["pr_head"] == h and inp["target_ref"] in (MAIN, "refs/remotes/origin/main")
    assert_rejected(check(t, h, "feat/x"), "merge-result-gate-failed")


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
    a, _, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, local="approval-20261120110000-release-handwritten")
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
        t.activity_only("activity-20261120110000-orphan", r, r, name)
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
        t.approve("GateArchitecture", ["supplier"], evidence=r, local="approval-20261120090000-main-other")
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
                record_ttl(f"approval-20261120110000-{el}", "GateArchitecture", [el], t.rev(MAIN)), "a")
        t.commit_all(f"append {el}")
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "a", "feat/a")
    p = subprocess.run(["git", "-C", str(t.root), "merge", "-q", "--no-ff", "-m", "b", "feat/b"],
                       capture_output=True, text=True)
    assert p.returncode != 0 and "governance.ttl" in t.git("diff", "--name-only", "--diff-filter=U")
    t.git("merge", "--abort")


# ================================================================== 第四轮 (PR #11, ADR-016): T38 / T43 additions

@pytest.mark.parametrize("cover", ["rejected", "other-gate-approved"])
def test_T38_R4_2_cover_must_be_approved_any_gate(t, cover):
    """R4-2: a Rejected record does not re-approve; an Approved record of another gate does."""
    t.checkout("main", new="feat/x")
    h = t.relabel("auditTrail", "审计轨迹V2")
    if cover == "rejected":
        a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h, decision="Rejected")
        assert_rejected(check(t, a, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")
    else:
        a, _, _ = t.approve("GateDesign", ["auditTrail"], evidence=h)
        assert_clean(check(t, a, "feat/x"))


def test_T38_R4_3_backdated_cover_rejected(t):
    """R4-3: the cover record is generated before T's own Approved record of the object (2026-11-19T12:00:00Z), so on
    M the old record stays effective."""
    t.checkout("main", new="feat/x")
    h = t.relabel("auditTrail", "审计轨迹V2")
    a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h, at="2026-11-19T11:00:00Z")
    assert_rejected(check(t, a, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")


def test_T38_R4_3_later_record_on_main_rejected_at_recompute(t):
    """R4-3: CI passes; main then takes a later record on the same object → the branch's cover is no longer effective
    on M; the pre-merge recompute refuses."""
    t.checkout("main", new="feat/x")
    h = t.relabel("auditTrail", "审计轨迹V2")
    a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h, at="2026-11-20T11:00:00Z")
    t1 = t.rev(MAIN)
    assert_clean(check(t, a, "feat/x", target=t1))
    t.checkout("main")
    t.approve("GateRequirements", ["auditTrail"], evidence=t1, at="2026-11-20T11:30:00Z",
              local="approval-20261120113000-requirements-main")
    t.checkout("feat/x")
    assert_rejected(check(t, a, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")


LEGACY = "models/procurement/legacy.ttl"


@pytest.mark.parametrize("decision", ["Approved", "Rejected"])
def test_T38_R4_4_approved_evidence_must_pass_gate(t, decision):
    """R4-4: main carries an L1 violation (a direct triple, as if committed with --no-verify) when the branch forks; the
    branch approves on top of it; main then fixes it so M passes. Approved → rejected; Rejected → not for this reason."""
    from fixtures.topology import PREFIXES
    t.checkout("main")
    t.write(LEGACY, PREFIXES + "\n:quoteApproval am4:accesses :quotation .\n")
    t0 = t.commit_all("legacy direct triple (--no-verify)")
    h = feature(t)
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h, decision=decision)
    t.checkout("main"); t.git("rm", "-q", LEGACY); t1 = t.commit_all("fix the legacy violation")
    t.checkout("feat/x")
    if decision == "Approved":  # the fixture is what it claims (gate runs once per decision would only repeat it)
        assert not cli_gate(t, h) and cli_gate(t, t1, merge=a) and t.merge_base(a, MAIN) == t0
    p = check(t, a, "feat/x")
    if decision == "Approved":
        assert_rejected(p, "evidence-gate-failed")
    elif not isinstance(p, _Pending):
        assert "evidence-gate-failed" not in reasons(p), p


@pytest.mark.parametrize("target", ["relationship", "view", "stakeholder"])
def test_T38_R4_5_record_approving_illegal_target_does_not_cover(t, target):
    """R4-5: approves may name elements (not records, activities, Stakeholders), models and ADRs only. A record that
    also names a relationship / view / Stakeholder is illegal (L1) and does not re-approve :auditTrail."""
    t.checkout("main", new="feat/x")
    if target == "view":
        t.write(AM4, "\n:overviewView a arch:View ;\n    arch:inModel <" + M + "> ;\n    skos:prefLabel \"总览视图\"@zh .\n", "a")
        t.commit_all("add a view")
    h = t.relabel("auditTrail", "审计轨迹V2")
    other = {"relationship": "rel-supplier-assigned-submitQuotation", "view": "overviewView",
             "stakeholder": "chiefArchitect"}[target]
    a, _, _ = t.approve("GateArchitecture", ["auditTrail", other], evidence=h)
    assert_rejected(check(t, a, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")


def _approve_model_on_main(t):
    t.checkout("main")
    t.approve("GateArchitecture", [f"<{M}>"], evidence=t.rev(MAIN), at="2026-11-20T09:00:00Z",
              local="approval-20261120090000-architecture-model")


@pytest.mark.parametrize("change,covered", [("prefLabel", False), ("conformsTo", False), ("prefLabel", True)])
def test_T38_R4_6_model_subject_triples_count_as_modification(t, change, covered):
    """R4-6: the model's own triples are in its comparison scope; relabelling an Approved model needs re-approval."""
    _approve_model_on_main(t)
    t.checkout("main", new="feat/x")
    if change == "prefLabel":
        h = t.set_model_label("采购V2")
    else:
        t.write(AM4, f"\n<{M}> arch:modelConformsToMetamodel <https://meta.linked.archi/archimate4/onto#> .\n", "a")
        h = t.commit_all("declare the metamodel")
    if covered:
        a, _, _ = t.approve("GateArchitecture", [f"<{M}>"], evidence=h)
        assert_clean(check(t, a, "feat/x"))
    else:
        assert_rejected(check(t, h, "feat/x"), "unapproved-change-to-approved", iri=M)


@pytest.mark.parametrize("model_approved", [False, True])
def test_T38_G4_4_relationship_change_does_not_touch_endpoint(t, model_approved):
    """G4-4: :quoteApproval is Approved on T. Retargeting a relationship that has it as an endpoint passes and leaves it
    Approved; when the whole model is Approved the same change needs re-approval of the model."""
    if model_approved:
        _approve_model_on_main(t)
    t.checkout("main", new="feat/x")
    h = t.retarget("rel-procurementManager-assigned-quoteApproval", "submitQuotation")
    assert "arch:target :submitQuotation" in t.git("show", f"{h}:{AM4}")
    p = check(t, h, "feat/x")
    if model_approved:
        assert_rejected(p, "unapproved-change-to-approved", iri=M)
    else:
        assert_clean(p)


@pytest.mark.parametrize("old_at,new_at,superseded", [
    ("2026-11-20T10:00:00Z", "2026-11-20T12:00:00+08:00", False),  # = 04:00Z, earlier: not a later superset
    ("2026-11-20T10:00:00Z", "2026-11-20T18:00:00+08:00", False),  # = 10:00Z, same instant: both checked
    ("2026-11-20T10:00:00Z", "2026-11-20T19:00:00+08:00", True),   # = 11:00Z, later: positive twin
])
def test_T38_G4_1_times_compared_as_utc_instants(t, old_at, new_at, superseded):
    h1 = feature(t)
    t.approve("GateArchitecture", ["newThing"], evidence=h1, at=old_at)
    h2 = t.relabel("newThing", "新东西改")
    a, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h2, at=new_at)
    p = check(t, a, "feat/x")
    if superseded:
        assert_clean(p)
    else:
        assert_rejected(p, "not-approval-commit", offending=h2)


@pytest.mark.parametrize("delete_first", [True, False])
def test_T38_G4_2_remove_approved_element_rejected_even_with_cover(t, delete_first):
    t.checkout("main", new="feat/x")
    if delete_first:
        h = t.remove_block("auditTrail")
        a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h)
    else:
        h = t.relabel("auditTrail", "审计轨迹V2")
        t.approve("GateArchitecture", ["auditTrail"], evidence=h)
        a = t.remove_block("auditTrail")
    assert ":auditTrail a " not in t.read(AM4)
    assert_rejected(check(t, a, "feat/x"), "approved-element-removed", iri=M + "auditTrail")


@pytest.mark.parametrize("retire_covered", [False, True])
def test_T38_G4_2_retirement_is_a_modification(t, retire_covered):
    """Retiring (owl:deprecated) an Approved element counts as modified: it needs an Approved cover in the same PR."""
    t.checkout("main", new="feat/x")
    t.write(AM4, "\n:auditTrail owl:deprecated true .\n", "a")
    if "@prefix owl:" not in t.read(AM4):
        t.write(AM4, "@prefix owl:   <http://www.w3.org/2002/07/owl#> .\n" + t.read(AM4))
    h = t.commit_all("retire auditTrail")
    if retire_covered:
        a, _, _ = t.approve("GateArchitecture", ["auditTrail"], evidence=h)
        assert_clean(check(t, a, "feat/x"))
    else:
        assert_rejected(check(t, h, "feat/x"), "unapproved-change-to-approved", iri=M + "auditTrail")


@pytest.mark.parametrize("full_superset", [True, False])
def test_T38_G4_3_reapprove_on_merge_commit(t, full_superset):
    """G4-3: approve, merge main into the branch, re-approve with the merge commit as evidence (same gate, later).
    A superset supersedes the old record (pass); a partial one leaves it checked (merge commit in its range)."""
    feature(t); t.add_element("otherThing", "另一个"); h1 = t.rev()
    t.approve("GateArchitecture", ["newThing", "otherThing"], evidence=h1)
    t.checkout("main"); t.relabel("supplier", "供应商V2")
    t.checkout("feat/x"); t.git("merge", "-q", "--no-ff", "-m", "Merge main", "main")
    mc = t.rev()
    assert len(t.git("rev-parse", f"{mc}^@").split()) == 2
    objs = ["newThing", "otherThing"] if full_superset else ["newThing"]
    a, _, _ = t.approve("GateArchitecture", objs, evidence=mc, at="2026-11-20T11:30:00Z")
    p = check(t, a, "feat/x")
    if full_superset:
        assert_clean(p)
    else:
        assert_rejected(p, "merge-commit-in-range")


def test_T38_G4_6_superseded_record_activity_not_recomputed(t):
    """G4-6: approve at C (activity base F); another PR merges the branch ancestor C1 into main → the activity's
    baseCommit no longer equals merge-base(C, T) → rejected; re-approving on a new commit supersedes the old record
    and its activity is not recomputed → pass."""
    f = t.rev(MAIN)
    t.checkout("main", new="feat/x")
    c1 = t.add_element("thingOne", "一")
    c = t.add_element("thingTwo", "二")
    a1, _, _ = t.approve("GateArchitecture", ["thingOne", "thingTwo"], activity=act(t, c, "feat/x"))
    assert t.merge_base(c, MAIN) == f
    t.checkout("main"); t.git("merge", "-q", "--no-ff", "-m", "other PR takes C1", c1)
    t.checkout("feat/x")
    assert t.merge_base(c, MAIN) == c1
    assert_rejected(check(t, a1, "feat/x"), "activity-base-mismatch")
    c2 = t.relabel("thingTwo", "二改")
    a2, _, _ = t.approve("GateArchitecture", ["thingOne", "thingTwo"], at="2026-11-20T11:30:00Z",
                         activity=act(t, c2, "feat/x", local=f"activity-20261120113000-{c2[:7]}"))
    assert_clean(check(t, a2, "feat/x"))


@pytest.mark.parametrize("same_second", [False, True])
def test_T43_R4_7_same_gate_same_r_two_branches(t, same_second):
    """R4-7: two approval branches from the same mainline commit R approve it at the same gate — in practice only the
    release gate (U4①: a mainline commit may only get GateRelease). Different seconds → different local names, both
    merge cleanly (checker: clean). Same second → same file name, different content → the second merge conflicts
    (the registered residual risk; checker: merge-conflict). The git half runs for real; tags only on the local origin."""
    r = t.rev(MAIN)
    na, nb = (f"approval/release-{r[:7]}-20261120110000", f"approval/release-{r[:7]}-20261120110001")
    t.checkout(r, new=na)
    aa, la, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, at="2026-11-20T11:00:00Z")
    t.checkout(r, new=nb)
    ab, lb, _ = t.approve("GateRelease", ["quoteApproval"], evidence=r, approved_by=":codingBot",
                          at="2026-11-20T11:00:00.500Z" if same_second else "2026-11-20T11:00:01Z")
    t.tag(f"release/20261120-{r[:7]}", r)
    assert (la == lb) is same_second and t.rev(f"{aa}^") == t.rev(f"{ab}^") == r
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", f"Merge {na}", na)
    p = subprocess.run(["git", "-C", str(t.root), "merge", "-q", "--no-ff", "-m", f"Merge {nb}", nb],
                       capture_output=True, text=True)
    assert (p.returncode != 0) is same_second, p.stdout + p.stderr
    if same_second:
        assert f"{GOV}/{la}.ttl" in t.git("diff", "--name-only", "--diff-filter=U")
        t.git("merge", "--abort")
    else:
        t.git("reset", "-q", "--hard", "HEAD~1")  # main = T after the first release PR; check the second against it
    res = check(t, ab, nb)
    if same_second:
        assert_rejected(res, "merge-conflict")
    else:
        assert call("classify_pr", str(t.root), ab, MAIN) == "approval-only"
        assert_clean(res)


def test_T43_non_release_gate_after_other_branch_merged(t):
    """The topology R4-7 was first written with (U4①, check 3): feat/a and feat/b share the content commit H and each
    approve it with GateArchitecture; once feat/a is merged, H is on main, so feat/b's record now approves a mainline
    commit at a non-release gate → mainline-head-gate-not-release. Positive twin: feat/b checked before feat/a merges."""
    t.checkout("main", new="feat/a")
    h = t.add_element("thingA", "甲")
    t.checkout("main", new="feat/b")
    t.git("reset", "-q", "--hard", h)
    t.checkout("feat/a")
    t.approve("GateArchitecture", ["thingA"], evidence=h, at="2026-11-20T11:00:00Z")
    t.checkout("feat/b")
    ab, _, _ = t.approve("GateArchitecture", ["thingA"], evidence=h, approved_by=":codingBot",
                         at="2026-11-20T11:00:01Z")
    t1 = t.rev(MAIN)
    assert_clean(check(t, ab, "feat/b", target=t1))
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/a", "feat/a")
    assert subprocess.run(["git", "-C", str(t.root), "merge-base", "--is-ancestor", h, MAIN]).returncode == 0
    assert_rejected(check(t, ab, "feat/b"), "mainline-head-gate-not-release")


def test_T38_R4_11_target_moved_before_merge_means_recompute(t):
    """R4-11 ②: the recompute used T1; the remote main then moves → ls-remote differs → do not merge, recompute."""
    t1 = t.rev(MAIN)
    assert call("target_unchanged", str(t.root), "main", t1) == True  # noqa: E712 (positive twin)
    t.checkout("main"); t.add_element("later", "之后的提交"); t.push("main")
    assert t.git("ls-remote", "origin", "refs/heads/main").split()[0] != t1
    assert call("target_unchanged", str(t.root), "main", t1) == False  # noqa: E712


@pytest.mark.parametrize("parents_match", [True, False])
def test_T38_R4_11_post_merge_verify(t, parents_match):
    """R4-11 ③: the PR passed against T1. If the platform merged onto T1, the new head's parents are (T1, H) → [].
    If main had moved to T2 (deleting the element the PR references), the parents differ and re-running the merge
    result gate on the new head fails."""
    t.checkout("main"); t1 = t.add_element("ledger", "台账", rel="models/procurement/ledger.ttl")
    t.checkout("main", new="feat/x")
    h = t.add_relationship("rel-quoteApproval-accesses-ledger", "am4:Access", "quoteApproval", "ledger")
    t.checkout("main")
    if not parents_match:
        t.remove_block("ledger", rel="models/procurement/ledger.ttl")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/x", h)
    m2 = t.rev()
    assert (t.git("rev-parse", f"{m2}^1") == t1) is parents_match and t.git("rev-parse", f"{m2}^2") == h
    p = call("post_merge_verify", str(t.root), m2, t1, h, head_ref="feat/x", now=NOW)
    if parents_match:
        assert_clean(p)
    else:
        assert_rejected(p, "merge-result-gate-failed")


# ================================================================== 空白节点形式的批准记录与活动（2026-11-22 取证，疑点一）
# A record written as a blank node referenced by a named subject (`<x> skos:note [ a aisep:ApprovalRecord ; … ]`) used
# to pass gate and merge_check while the derivation honoured it: diff.Side folds a referenced blank node into its
# referrer's signature, so no record IRI was "new" and check 3 never ran. Two independent guards now hold:
#   layer 1 — aisep-core ApprovalRecordShape / AgentActivityShape: a record or activity must be an IRI with
#             arch:inModel (L1 Violation → gate FAIL; Ctx.approval_problems → the derivation ignores the record);
#   layer 2 — merge_check scans the model sources of H and M and reports every blank node typed as, or carrying a
#             predicate of, a record or activity (reason governance-blank-node), whatever the gate says.

BNODE = "governance-blank-node"
SHA256 = "sha256:" + "ab" * 32
ARCH_NS = "https://meta.linked.archi/core#"
LAYER1_MARK = "must be a model element, an IRI with arch:inModel"


def bnode_record(approves, decision="Approved", gate="GateArchitecture", at="2026-11-20T11:30:00Z", activity=None):
    objs = ", ".join(a if a.startswith("<") else f":{a}" for a in approves)
    act = f" ; aisep:activity {activity}" if activity else ""
    return (f"[ a aisep:ApprovalRecord ; aisep:gate aisep:{gate} ; aisep:decision aisep:Decision{decision} ; "
            f"aisep:approvedBy :chiefArchitect ; aisep:approves {objs} ; aisep:evidence \"{SHA256}\" ; "
            f"prov:generatedAtTime \"{at}\"^^xsd:dateTime{act} ]")


def bnode_activity(head, base, branch):
    return (f"[ a aisep:AgentActivity ; prov:wasAssociatedWith :codingBot ; "
            f"prov:startedAtTime \"2026-11-20T09:00:00Z\"^^xsd:dateTime ; prov:endedAtTime \"2026-11-20T10:00:00Z\"^^xsd:dateTime ; "
            f"aisep:sessionRef \"s-bnode\" ; aisep:branch \"{branch}\" ; aisep:headCommit \"{head}\" ; aisep:baseCommit \"{base}\" ]")


def hang(t, holder, blob, rel=AM4, msg="note"):
    """Attach blob to a named subject with skos:note (the referenced-blank-node form) and commit."""
    from fixtures.topology import PREFIXES
    t.write(rel, "\n" + PREFIXES + f"\n{holder} skos:note {blob} .\n", "a")
    return t.commit_all(msg)


def state(t, commit, iri):
    """The derived arch:approvalState values of iri on commit (in-process, the code under test)."""
    from aisep import tools
    with tools.loaded(tools.Config(), str(t.root), ref=commit) as (ctx, _):
        return {o.value for s, p, o, _ in ctx.built if s.value == iri and p.value == ARCH_NS + "approvalState"}


OTHER = "https://aisep.example/model/other/"


def _bnode_case(t, case):
    """Build one bypass attempt on a branch. Returns (H, head_ref, the IRI whose state the attempt targets or None)."""
    if case == "new-element-approved":  # r1: a new element carries its own approval
        feature(t)
        return hang(t, ":newThing", bnode_record(["newThing"])), "feat/x", M + "newThing"
    if case == "proposed-element-no-new-iri":  # r2: no new IRI; :submitQuotation is Proposed on main
        t.checkout("main", new="feat/x")
        return hang(t, f"<{M}>", bnode_record(["submitQuotation"])), "feat/x", M + "submitQuotation"
    if case == "approved-element-rejected":  # r4 step 1: downgrade :auditTrail (Approved on main)
        t.checkout("main", new="feat/x")
        return hang(t, f"<{M}>", bnode_record(["auditTrail"], decision="Rejected")), "feat/x", M + "auditTrail"
    if case == "activity-blank":  # a complete blank-node activity, referenced by the model resource
        t.checkout("main", new="feat/x")
        base = t.rev(MAIN)
        return hang(t, f"<{M}>", bnode_activity(base, base, "feat/x")), "feat/x", None
    if case == "record-in-other-model-file":  # unverified direction 1: the record lives in another model's file
        t.checkout("main", new="feat/x")
        from fixtures.topology import PREFIXES
        t.write("models/other/other.ttl", PREFIXES + f"\n<{OTHER}> a arch:Model ;\n    skos:prefLabel \"其他\"@zh .\n")
        t.commit_all("add model other")
        return hang(t, f"<{OTHER}>", bnode_record(["submitQuotation"]), rel="models/other/other.ttl"), "feat/x", \
            M + "submitQuotation"
    if case == "approves-whole-model":  # unverified direction 2: the target is the arch:Model itself
        t.checkout("main", new="feat/x")
        return hang(t, f"<{M}>", bnode_record([f"<{M}>"])), "feat/x", M
    if case == "record-with-activity":  # unverified direction 3: a blank-node record that names an (IRI) activity
        h0 = feature(t)
        from fixtures.topology import activity_ttl
        a = act(t, h0, "feat/x")
        t.write(f"{GOV}/{a['local']}.ttl", PREFIXES_() + activity_ttl(**a))
        t.commit_all("add activity")
        return hang(t, ":newThing", bnode_record(["newThing"], activity=f":{a['local']}")), "feat/x", M + "newThing"
    if case == "record-with-blank-activity":  # an IRI record (approval-commit shape) whose activity is a blank node
        h0 = feature(t)
        from fixtures.topology import record_ttl
        local = f"approval-20261120110000-architecture-{h0[:7]}"
        body = record_ttl(local, "GateArchitecture", ["newThing"], h0)[:-3] + \
            f" ;\n    aisep:activity {bnode_activity(h0, t.merge_base(h0, MAIN), 'feat/x')} .\n"
        t.write(f"{GOV}/{local}.ttl", PREFIXES_() + body)
        return t.commit_all(f"aisep: GateArchitecture Approved {local}", trailers=[f"AISEP-Evidence: {h0}"]), "feat/x", \
            M + "newThing"
    raise AssertionError(case)


def PREFIXES_():
    from fixtures.topology import PREFIXES
    return PREFIXES


BNODE_CASES = ["new-element-approved", "proposed-element-no-new-iri", "approved-element-rejected", "activity-blank",
               "record-in-other-model-file", "approves-whole-model", "record-with-activity", "record-with-blank-activity"]


@pytest.mark.parametrize("case", BNODE_CASES)
def test_bnode_governance_rejected_by_gate_mergecheck_and_derivation(t, case):
    """Both layers on: the branch head and the merge result fail the real gate, merge_check reports
    governance-blank-node (and the failed merge-result gate), and the derived state of the target is the one on main."""
    t_main = t.rev(MAIN)
    h, ref, target = _bnode_case(t, case)
    assert "[" in t.git("show", h, "--", AM4, "models/other/other.ttl", GOV)  # the fixture really writes a blank node
    assert not cli_gate(t, h)
    assert not cli_gate(t, t_main, merge=h)
    p = check(t, h, ref)
    assert_rejected(p, BNODE)
    assert_rejected(p, "merge-result-gate-failed")
    if target:  # h^ is the same branch without the blank node
        assert state(t, h, target) == state(t, f"{h}^", target)


def test_bnode_rejected_record_two_step_downgrade(t):
    """r4: step 1 hangs a blank-node Rejected record on the Approved :auditTrail; step 2 (another PR) changes it.
    Step 1 is refused; even if it had been merged (as before this fix), :auditTrail stays Approved on main, main fails
    the gate, and step 2 is refused as an unapproved change to an Approved element."""
    audit = M + "auditTrail"
    assert state(t, t.rev(MAIN), audit) == {ARCH_NS + "Approved"}
    t.checkout("main", new="feat/y")  # step 2 branches off main before step 1 lands: H itself has no blank node
    h2 = t.relabel("auditTrail", "审计轨迹V2")
    t.checkout("main", new="feat/r")
    h1 = hang(t, f"<{M}>", bnode_record(["auditTrail"], decision="Rejected"), rel="models/procurement/notes.ttl")
    assert_rejected(check(t, h1, "feat/r"), BNODE)
    t.checkout("main"); t.git("merge", "-q", "--no-ff", "-m", "Merge feat/r (as if merged before the fix)", "feat/r")
    t1 = t.rev()
    assert state(t, t1, audit) == {ARCH_NS + "Approved"}
    assert not cli_gate(t, t1)
    assert "skos:note" not in t.git("show", f"{h2}:{AM4}") and "skos:note" in t.git("show", f"{t1}:models/procurement/notes.ttl")
    p2 = check(t, h2, "feat/y")
    assert_rejected(p2, "unapproved-change-to-approved", iri=audit)
    assert_rejected(p2, BNODE)  # only M carries the blank node (from main)


def _layer1_off(monkeypatch):
    """Stub layer 1: drop the two aisep-core constraints that require a record / activity to be an IRI with
    arch:inModel (everything else in the shapes stays)."""
    from aisep import core, mergecheck
    real = core.sparql_constraints
    monkeypatch.setattr(core, "sparql_constraints", lambda path: [c for c in real(path) if LAYER1_MARK not in c[2]])
    monkeypatch.setattr(mergecheck, "_GATES", {})


def _layer2_off(monkeypatch):
    from aisep import mergecheck
    monkeypatch.setattr(mergecheck, "_governance_bnodes", lambda *a, **kw: [])
    monkeypatch.setattr(mergecheck, "_GATES", {})


INDEPENDENCE_CASES = ["new-element-approved", "proposed-element-no-new-iri", "approved-element-rejected", "activity-blank"]


@pytest.mark.parametrize("case", INDEPENDENCE_CASES)
def test_bnode_layer2_holds_without_layer1(t, case, monkeypatch):
    """Layer 1 stubbed out: the derivation honours the blank-node record again (the stub is real), yet merge_check still
    refuses with governance-blank-node."""
    _layer1_off(monkeypatch)
    h, ref, target = _bnode_case(t, case)
    p = check(t, h, ref)
    assert_rejected(p, BNODE)
    if target:
        assert state(t, h, target) != state(t, f"{h}^", target)  # proves the stub really removed layer 1


@pytest.mark.parametrize("case", INDEPENDENCE_CASES)
def test_bnode_layer1_holds_without_layer2(t, case, monkeypatch):
    """Layer 2 stubbed out: merge_check no longer names the blank node, yet the merge-result gate fails (layer 1) and
    the derivation ignores the record."""
    _layer2_off(monkeypatch)
    h, ref, target = _bnode_case(t, case)
    p = check(t, h, ref)
    if not isinstance(p, _Pending):
        assert BNODE not in reasons(p), p  # proves the stub really removed layer 2
    assert_rejected(p, "merge-result-gate-failed")
    if target:
        assert state(t, h, target) == state(t, f"{h}^", target)


def test_bnode_post_merge_verify_scans_new_head(t):
    """Main moved after the recompute and the platform merged anyway: post_merge_verify re-checks the new head and
    names the blank-node record."""
    t.checkout("main", new="feat/x")
    h = hang(t, f"<{M}>", bnode_record(["submitQuotation"]))
    t1 = t.rev(MAIN)
    t.checkout("main"); t.add_element("later", "之后的提交", rel="models/procurement/later.ttl")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/x", h)
    assert t.git("rev-parse", "HEAD^1") != t1  # main moved: post_merge_verify re-checks
    p = call("post_merge_verify", str(t.root), t.rev(), t1, h, head_ref="feat/x", now=NOW)
    assert_rejected(p, BNODE)


def test_bnode_untyped_with_record_predicates_rejected_by_mergecheck(t):
    """An untyped blank node with aisep:approves / aisep:decision cannot be read by the derivation (it needs the type),
    but merge_check still refuses it (fail closed: a module-declared subclass would not be visible to diff.Side)."""
    t.checkout("main", new="feat/x")
    h = hang(t, f"<{M}>", "[ aisep:approves :submitQuotation ; aisep:decision aisep:DecisionApproved ]")
    assert_rejected(check(t, h, "feat/x"), BNODE)


@pytest.mark.parametrize("fixture", ["approval-record-blank-node", "approval-record-not-in-model"])
def test_layer1_derivation_ignores_record_that_is_not_a_model_element(fixture):
    """Layer 1 in core: the aisep-core invalid fixture's record is in Ctx.approval_problems, the derivation leaves the
    approved element arch:Proposed, and L1 reports the record (the run_fixture check covers only the L1 message)."""
    from aisep import core
    ctx = core.Ctx(core.discover(), [os.path.join(core.ROOT, "modules/aisep-core/tests/invalid", fixture + ".ttl")])
    assert any(LAYER1_MARK in m for ms in ctx.approval_problems().values() for m in ms)
    states = {o.value for s, p, o, _ in ctx.built if s.value == "https://aisep.example/model/t/ac"
              and p.value == ARCH_NS + "approvalState"}
    assert states == {ARCH_NS + "Proposed"}
    ctx.l1()
    assert any(LAYER1_MARK in text for sev, layer, text in ctx.problems if sev == "Violation" and layer == "L1")


@pytest.mark.parametrize("typed", ["aisep:AgentActivity", ":ProbeRecord"])
def test_bnode_typed_without_record_predicates_rejected_by_mergecheck(t, typed):
    """A blank node typed as a record / activity but with none of their predicates is reported too; a subclass declared
    in a model file (itself an L1 violation, R1) is followed through the merge result's subclass closure."""
    t.checkout("main", new="feat/x")
    if typed == ":ProbeRecord":
        t.write(AM4, "\n:ProbeRecord rdfs:subClassOf aisep:ApprovalRecord .\n", "a")
        t.write(AM4, "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" + t.read(AM4))
    h = hang(t, f"<{M}>", f"[ a {typed} ; skos:prefLabel \"无谓词\"@zh ]")
    assert_rejected(check(t, h, "feat/x"), BNODE)


@pytest.mark.parametrize("fixture", ["approval-record-blank-node", "activity-blank-node-standalone"])
def test_layer1_blank_node_finding_is_stable_across_parses(fixture):
    """The L1 finding of a blank-node record / activity names a stable focus (the named subject referring to it) and a
    stable message, so the write tools' instance keys (§5.1 step 5) do not change between two parses of the same file."""
    from aisep import core, writer
    path = os.path.join(core.ROOT, "modules/aisep-core/tests/invalid", fixture + ".ttl")
    keys = []
    for _ in range(2):
        ctx = core.Ctx(core.discover(), [path])
        core.run_check(ctx)
        ks = sorted(k for k, f in writer._instances(ctx) if LAYER1_MARK in f["message"] and f["severity"] == "Violation")
        assert ks and all(k[3] and k[3].startswith("https://aisep.example/model/t/") for k in ks), ks
        keys.append(ks)
    assert keys[0] == keys[1]


def test_bnode_plain_note_still_passes(t):
    """Positive twin: a blank node with no governance type or predicate (a structured note) is not reported."""
    t.checkout("main", new="feat/x")
    h = hang(t, f"<{M}>", "[ skos:prefLabel \"备注\"@zh ]")
    p = check(t, h, "feat/x")
    if not isinstance(p, _Pending):
        assert BNODE not in reasons(p), p


# ------------------------------------------------------------------ #78 评审遗留（minor 1–3）

_T_HEADER = """@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/t/> .
:t a arch:Model ; skos:prefLabel "测试模型"@zh .
:ac a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .
:boss a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "架构师"@zh .
:bot a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "编码代理"@zh .
"""
_T_REC = ("a aisep:ApprovalRecord ; aisep:gate aisep:GateMerge ; aisep:decision aisep:DecisionApproved ; "
          "aisep:approvedBy :boss ; aisep:approves :ac ; aisep:evidence \"" + SHA256 + "\" ; "
          "prov:generatedAtTime \"2026-11-20T11:00:00+08:00\"^^xsd:dateTime")
_T_ACT = ("a aisep:AgentActivity ; prov:wasAssociatedWith :bot ; prov:startedAtTime \"2026-11-20T01:00:00Z\"^^xsd:dateTime ; "
          "prov:endedAtTime \"2026-11-20T02:00:00Z\"^^xsd:dateTime ; aisep:sessionRef \"s\" ; aisep:branch \"b\" ; "
          "aisep:baseCommit \"0a1b2c3d4e5f60718293a4b5c6d7e8f901234567\" ; aisep:headCommit \"3f2a9c1e7b4d5a6f8e9c0b1a2d3e4f5a6b7c8d9e\"")


@pytest.mark.parametrize("body", [_T_REC, _T_ACT], ids=["record", "activity"])
def test_layer1_unreferenced_blank_node_finding_is_stable(tmp_path, body):
    """minor 1: an UNREFERENCED blank-node record / activity has no named subject to anchor on. Its L1 finding has
    focus null and names the file (§7.3: focus null → file joins the instance key), so the write tools' "new violation"
    comparison (§5.1 step 5) sees the same key on every parse instead of a fresh random blank node label."""
    from aisep import core, writer
    f = tmp_path / "loose.ttl"
    f.write_text(_T_HEADER + f"[ {body} ] .\n", encoding="utf-8")
    keys = []
    for _ in range(2):
        ctx = core.Ctx(core.discover(), [str(f)])
        core.run_check(ctx)
        fs = [f_ for _, f_ in writer._instances(ctx) if LAYER1_MARK in f_["message"] and f_["severity"] == "Violation"]
        assert fs and all(x["focus"] is None and x["file"] for x in fs), fs
        keys.append(sorted(k for k, f_ in writer._instances(ctx) if f_ in fs))
    assert keys[0] == keys[1]


@pytest.mark.parametrize("where", ["holder", "nested"])
def test_bnode_class_of_governance_rejected_by_mergecheck(t, where):
    """minor 2: a blank node used as a subclass of aisep:ApprovalRecord. holder: the blank class hangs on the model
    resource; nested: a blank-node instance typed with a blank class (the only tree-shaped way to use one)."""
    t.checkout("main", new="feat/x")
    cls = "[ rdfs:subClassOf aisep:ApprovalRecord ]"
    blob = cls if where == "holder" else f"[ a {cls} ; skos:prefLabel \"无谓词\"@zh ]"
    from fixtures.topology import PREFIXES
    t.write(AM4, "\n" + PREFIXES + "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            + f"\n<{M}> skos:note {blob} .\n", "a")
    h = t.commit_all("note")
    assert_rejected(check(t, h, "feat/x"), BNODE)


def test_bnode_with_ontology_declared_governance_predicate_rejected_by_mergecheck(t):
    """minor 2: the governance predicates are read from the merge result's rdfs:domain declarations (the built-in list
    stays as a floor), so a predicate declared later with domain aisep:ApprovalRecord is covered without a code change.
    Declared here in a model file (itself an R1 violation) to stand in for a module change."""
    t.checkout("main", new="feat/x")
    t.write(AM4, "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n" + t.read(AM4)
            + "\n:probeP rdfs:domain aisep:ApprovalRecord .\n")
    t.commit_all("declare a governance predicate")
    h = hang(t, f"<{M}>", "[ :probeP \"x\" ]")
    assert_rejected(check(t, h, "feat/x"), BNODE)


@pytest.mark.parametrize("fixture,target", [("approval-record-in-model-not-a-model", "https://aisep.example/model/t/ac")])
def test_layer1_derivation_ignores_record_whose_in_model_is_not_a_model(fixture, target):
    """minor 3: arch:inModel must name an arch:Model, not just be present; such a record is ignored by the derivation."""
    from aisep import core
    ctx = core.Ctx(core.discover(), [os.path.join(core.ROOT, "modules/aisep-core/tests/invalid", fixture + ".ttl")])
    assert any(LAYER1_MARK in m for ms in ctx.approval_problems().values() for m in ms)
    states = {o.value for s, p, o, _ in ctx.built if s.value == target and p.value == ARCH_NS + "approvalState"}
    assert states == {ARCH_NS + "Proposed"}


# ================================================================== #105：模块或 vendor 声明的批准记录 / 活动子类
# The derivation honours a record typed with any subclass of aisep:ApprovalRecord declared anywhere in the merge result
# (modules/ and vendor/ included); merge_check must recognise the same records and activities, or checks 1, 3 and 4 are
# skipped for them (PR #104 independent review, issue #105).

SUB_REC = "https://aisep.example/ont/ddd#Signoff"
SUB_ACT = "https://aisep.example/ont/ddd#AgentRun"
SUB_SITES = {"module": "modules/ddd/onto.ttl", "vendor": "vendor/meta.linked.archi/ttl/archimate4_onto.ttl"}
NO_COMMIT = "ab" * 20  # 40 hex, not a commit in the repository


def declare_sub(t, site, sub=SUB_REC, sup="https://aisep.example/ont/aisep#ApprovalRecord"):
    t.write(SUB_SITES[site], f"\n<{sub}> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{sup}> .\n", "a")
    return t.commit_all(f"declare {sub} in {site}")


def sub_record(t, local, approves, evidence, decision="Approved", activity=None, msg=None):
    from fixtures.topology import record_ttl
    body = record_ttl(local, "GateArchitecture", approves, evidence, decision=decision, activity=activity)
    assert " a aisep:ApprovalRecord ;" in body
    t.write(f"{GOV}/{local}.ttl", PREFIXES_() + body.replace(" a aisep:ApprovalRecord ;", f" a <{SUB_REC}> ;"))
    return t.commit_all(msg or f"aisep: GateArchitecture {decision} {local}", trailers=[f"AISEP-Evidence: {evidence}"])


@pytest.mark.parametrize("site", ["module", "vendor"])
def test_105_subclass_record_with_unchecked_evidence_rejected(t, site):
    """A record typed with a subclass declared in a module / vendor file, evidence not a commit: the derivation makes
    :newThing Approved, so merge_check must run check 3 on it. Positive twin: the declaration alone is clean."""
    feature(t)
    d = declare_sub(t, site)
    assert_clean(check(t, d, "feat/x"))
    a = sub_record(t, "approval-20261120110000-architecture-forged", ["newThing"], NO_COMMIT)
    assert state(t, a, M + "newThing") == {ARCH_NS + "Approved"}  # the fixture really reaches the derivation
    assert_rejected(check(t, a, "feat/x"), "evidence-not-ancestor", iri=M + "approval-20261120110000-architecture-forged")


@pytest.mark.parametrize("change", ["modified", "removed"])
def test_105_existing_subclass_record_rewritten_rejected(t, change):
    """Check 1 on a record already on T whose type is a module-declared subclass. Positive twin: an unrelated PR."""
    declare_sub(t, "module")
    local = "approval-20261120110000-architecture-onmain"
    sub_record(t, local, ["submitQuotation"], t.rev(MAIN), decision="Rejected")
    t.checkout("main", new="feat/x")
    rel = f"{GOV}/{local}.ttl"
    assert_clean(check(t, t.relabel("submitQuotation", "提交报价单V2"), "feat/x"))
    if change == "modified":
        t.write(rel, t.read(rel).replace("GateArchitectureRejected", "GateArchitectureRejected2"))
    else:
        os.remove(t.path(rel))
    h = t.commit_all(f"{change} the record")
    assert_rejected(check(t, h, "feat/x"), f"governance-record-{change}", iri=M + local)


def test_105_subclass_activity_branch_checked(t):
    """Check 4 on an activity typed with a module-declared subclass of aisep:AgentActivity. Positive twin: the same
    activity with the right branch."""
    from fixtures.topology import activity_ttl
    feature(t)
    h0 = declare_sub(t, "module", SUB_ACT, "https://aisep.example/ont/aisep#AgentActivity")
    for branch, bad in (("other/branch", True), ("feat/x", False)):
        t.git("reset", "-q", "--hard", h0)
        a = act(t, h0, branch)
        t.write(f"{GOV}/{a['local']}.ttl", PREFIXES_() + activity_ttl(**a).replace(
            " a aisep:AgentActivity ;", f" a <{SUB_ACT}> ;"))
        h = t.commit_all("add activity")
        p = check(t, h, "feat/x")
        if bad:
            assert_rejected(p, "activity-branch-mismatch", iri=M + a["local"])
        else:
            assert "activity-branch-mismatch" not in reasons(p), p


# A record / activity whose rdf:type triple sits in a module or vendor file (its other triples in a model file): the
# derivation honours it (the type may come from any graph), but merge_check reads only models/, so checks 1, 3 and 4
# cannot see it. Before this guard only the merge-result gate's R1 refused it; now merge_check itself fails closed
# (reason governance-type-outside-models), independent of the gate (#105 review, non-blocking 1).
OUTSIDE = "governance-type-outside-models"


@pytest.mark.parametrize("site,kind", [("module", "record"), ("vendor", "record"), ("module", "activity")])
def test_105_governance_type_outside_models_rejected(t, site, kind, monkeypatch):
    from fixtures.topology import activity_ttl, record_ttl
    h0 = feature(t)
    if kind == "record":
        local, cls = "approval-20261120110000-architecture-typeout", "ApprovalRecord"
        body = record_ttl(local, "GateArchitecture", ["newThing"], NO_COMMIT)
    else:
        a = act(t, h0, "other/branch")
        local, cls = a["local"], "AgentActivity"
        body = activity_ttl(**a)
    head = f" a aisep:{cls} ;\n    arch:inModel"
    assert head in body
    t.write(f"{GOV}/{local}.ttl", PREFIXES_() + body.replace(head, " arch:inModel"))
    t.write(SUB_SITES[site], f"\n<{M}{local}> a <https://aisep.example/ont/aisep#{cls}> .\n", "a")
    h = t.commit_all(f"aisep: {local}", trailers=[f"AISEP-Evidence: {NO_COMMIT}"])
    if kind == "record":
        assert state(t, h, M + "newThing") == {ARCH_NS + "Approved"}  # the derivation does honour it
    assert_rejected(check(t, h, "feat/x"), OUTSIDE, iri=M + local)
    # independent of the gate: with the merge-result gate stubbed to PASS the guard still holds
    from aisep import mergecheck
    monkeypatch.setattr(mergecheck._Analysis, "check5", lambda self: [])
    assert_rejected(check(t, h, "feat/x"), OUTSIDE, iri=M + local)
    assert OUTSIDE not in reasons(check(t, h0, "feat/x"))  # positive twin: the same branch before the record

# A record typed with a subclass of aisep:ApprovalRecord is honoured by the derivation, but the approval-commit criterion
# (§5.9 step 1 (c)) recognises only the class itself and subclasses declared in the same models/<slug>/ files, so a
# commit adding a record typed with a module-declared subclass is not an approval commit: merge_check rejects it and
# a PR made only of it is a normal PR (spec §6.6「类型」, Albert 2026-11-26 选 A; PR #110 review 2).
def _gate_record(t, local, gate, approves, evidence, sub):
    from fixtures.topology import record_ttl
    body = record_ttl(local, gate, approves, evidence)
    if sub:
        assert " a aisep:ApprovalRecord ;" in body
        body = body.replace(" a aisep:ApprovalRecord ;", f" a <{SUB_REC}> ;")
    t.write(f"{GOV}/{local}.ttl", PREFIXES_() + body)
    return t.commit_all(f"aisep: {gate} Approved {local}", trailers=[f"AISEP-Evidence: {evidence}"])


@pytest.mark.parametrize("sub", [True, False], ids=["subclass", "class-itself"])
def test_105_subclass_record_commit_is_not_an_approval_commit(t, sub):
    """A feature-branch approval whose record is typed with a module-declared subclass, evidence a real commit on the
    branch: rejected as not-approval-commit although the derivation approves :newThing. Positive twin: the same record
    typed aisep:ApprovalRecord is clean."""
    feature(t)
    d = declare_sub(t, "module")
    a = _gate_record(t, "approval-20261120110000-architecture-subcommit", "GateArchitecture", ["newThing"], d, sub)
    assert state(t, a, M + "newThing") == {ARCH_NS + "Approved"}  # the derivation honours both
    if sub:
        assert_rejected(check(t, a, "feat/x"), "not-approval-commit", offending=a)
    else:
        assert_clean(check(t, a, "feat/x"))


@pytest.mark.parametrize("sub", [True, False], ids=["subclass", "class-itself"])
def test_105_subclass_release_record_not_approval_only(t, sub):
    """A release branch whose one commit adds a GateRelease record typed with a module-declared subclass: classified
    normal, rejected by merge_check, refused by release publishing. Positive twin: the class itself."""
    from aisep import release
    declare_sub(t, "module")  # on main
    r = t.rev(MAIN)
    name = release_branch(t, r)
    a = _gate_record(t, "approval-20261120110000-release-subcommit", "GateRelease", ["quoteApproval"], r, sub)
    t.tag(f"release/20261120-{r[:7]}", r)
    if sub:
        assert call("classify_pr", str(t.root), a, MAIN) == "normal"
        assert_rejected(check(t, a, name), "not-approval-commit", offending=a)
        with pytest.raises(release.ReleaseError, match="不是一个批准提交"):
            release._release_record(str(t.root), name)
    else:
        assert call("classify_pr", str(t.root), a, MAIN) == "approval-only"
        assert_clean(check(t, a, name))
        assert release._release_record(str(t.root), name)[0] == a


def test_has_type_empty_class_set_matches_nothing(t):
    """_has_type with an explicit empty class set must not fall back to the model-file class chain (#110 review 3)."""
    from aisep import mergecheck
    side = mergecheck._side(str(t.root), t.rev(MAIN))
    assert mergecheck._has_type(side, t.base_record, mergecheck.RECORD)  # positive twin: no set given
    assert not mergecheck._has_type(side, t.base_record, mergecheck.RECORD, set())


# A plain record kept in the shared models/<slug>/governance.ttl: deleting or rewriting it adds no IRI (post-merge
# review under ADR-024 第 1 款) and the gate passes, so only check 1 stops it (ADR-024 后果补记; followups 第 4 项).
@pytest.mark.parametrize("change", ["removed", "modified"])
def test_T38_record_in_governance_ttl_removed_or_modified_rejected(t, change):
    from fixtures.topology import record_ttl
    local, rel = "approval-20261119140000-architecture-inttl", "models/procurement/governance.ttl"
    t.write(rel, record_ttl(local, "GateArchitecture", ["supplier"], t.c0, at="2026-11-19T14:00:00Z",
                            decision="Rejected"), "a")
    t.commit_all("main: a plain record inside governance.ttl")
    t.checkout("main", new="feat/x")
    # positive twin: rewriting a non-record subject in the same governance.ttl is not a governance-record change
    assert '"编码代理"@zh' in t.read(rel)
    t.write(rel, t.read(rel).replace('"编码代理"@zh', '"编码代理V2"@zh'))
    twin = check(t, t.commit_all("relabel :codingBot in governance.ttl"), "feat/x")
    assert not {"governance-record-removed", "governance-record-modified"} & reasons(twin), twin
    txt = t.read(rel)
    if change == "removed":
        t.write(rel, txt[:txt.index(f":{local}")])
    else:
        j = txt.rindex("aisep:DecisionRejected")
        t.write(rel, txt[:j] + "aisep:DecisionApproved" + txt[j + len("aisep:DecisionRejected"):])
    h = t.commit_all(f"{change} the record in governance.ttl")
    assert t.git("diff", "--name-only", f"{h}^", h) == rel
    assert cli_gate(t, h)  # the gate passes: only check 1 stops it
    assert_rejected(check(t, h, "feat/x"), f"governance-record-{change}", iri=M + local)


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
