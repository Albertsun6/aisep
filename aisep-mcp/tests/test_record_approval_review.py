"""S5 governance_record_approval — gaps found by the independent review of PR #24 (docs/mcp-interface.md §5.9), written
by a session that does not implement aisep/approval.py.

Each test names the implementation line whose removal / weakening turns it red ("变红"; line numbers as of 685bc25).
Two tests failed on the implementation as reviewed (b858c19) and passed once 685bc25 fixed it:
  - test_branch_switched_in_worktree_before_lock: W was re-checked for detached HEAD only, not for still having
    `branch` checked out, so the approval landed on another branch while the result said `branch`.
  - test_rollback_when_index_locked_at_commit: step 8 ignored the exit status of `git rm --cached`; when it failed the
    file was deleted anyway and COMMIT_FAILED said "已回滚" while the index still staged the record.
One test fails on f9c2338 and is marked xfail(strict=True); drop the mark once fixed:
  - test_branch_switched_in_worktree_after_recheck_before_commit: W switched after the locked symbolic-ref check.

Injection points are module attributes of aisep.approval / aisep.gitio replaced with monkeypatch (same style as
test_approval_extra.py): gitio.locate_worktree returns before the lock is taken; approval._sha_file is first called
after `git add` and right before `git commit --only`; approval._write_new runs right before `git add`."""
import os
from datetime import datetime, timezone

import pytest

from aisep import approval, gitio, tools
from aisep.errors import AisepError
from fixtures.topology import GOV, M, Topo

NOW = datetime(2026, 11, 20, 11, 0, 0, tzinfo=timezone.utc)
BOSS = M + "chiefArchitect"
BOT = M + "codingBot"  # arch:Stakeholder, not an aisep:AIAgent (baseline): a valid second approver


@pytest.fixture
def t(template, tmp_path):
    topo = Topo(template, tmp_path)
    topo.checkout("main", new="feat/x")
    topo.head = topo.add_element("newThing", "新东西")
    return topo


def call(t, **kw):
    args = dict(model="procurement", gate="GateArchitecture", decision="Approved", approvedBy=BOSS,
                approves=[M + "newThing"], branch="feat/x", headCommit=t.head, repo=str(t.root), now=NOW)
    args.update(kw)
    return approval.governance_record_approval(tools.Config(allow_roots=(str(t.tmp),)), **args)


def err(t, **kw):
    with pytest.raises(AisepError) as e:
        call(t, **kw)
    return e.value


def refs(t):
    return t.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")


def new_records(t):
    d = t.path(GOV)
    return sorted(f for f in os.listdir(d) if f.startswith("approval-20261120")) if os.path.isdir(d) else []


def staged(t):
    return [f for f in t.git("ls-files", "--", GOV).splitlines() if os.path.basename(f).startswith("approval-20261120")]


def after_locate(monkeypatch, action):
    """Run `action(w)` after gitio.locate_worktree found W and before approval takes W's write lock."""
    real = gitio.locate_worktree

    def located(*a, **k):
        w = real(*a, **k)
        action(w)
        return w
    monkeypatch.setattr(gitio, "locate_worktree", located)


# ================================================================== 1. W switched to another branch before the lock

def test_branch_switched_in_worktree_before_lock(t, monkeypatch):
    """§5.9 step 7: W is where `branch` is checked out. If W switches to feat/y (also from headCommit) between
    locate_worktree and the lock, committing in W would write to feat/y. Expected: CONFLICT, retryable (§7.1 rule 4:
    CONFLICT is retryable except the failed take-back of step 7), neither branch moves. details.reason
    "worktree-switched" is the implementation's name; §5.9 does not name this case (待定, not pinned).
    变红: drop the comparison of `git symbolic-ref HEAD` with refs/heads/<branch> (approval.py:380)."""
    after_locate(monkeypatch, lambda w: gitio.git(w, "checkout", "-q", "-b", "feat/y"))
    before = refs(t)
    try:
        r = call(t)
    except AisepError as e:
        assert e.code == "CONFLICT" and e.retryable is True, (e.code, e.retryable)
    else:
        pytest.fail(f"no error; commit {r['commit'][:7]} reported on {r['branch']}")
    assert t.rev("refs/heads/feat/x") == t.head
    assert t.rev("refs/heads/feat/y") == t.head
    assert new_records(t) == [] and staged(t) == []


@pytest.mark.xfail(strict=True, reason="f9c2338: symbolic-ref 只在锁内复验时核对一次（approval.py:380），之后到 git commit "
                                       "之间 W 被切到 feat/y，提交落在 feat/y、A^ 仍等于 tip'，工具报告成功提交到 feat/x")
def test_branch_switched_in_worktree_after_recheck_before_commit(t, monkeypatch):
    """§5.9 step 7: the write lock only excludes model_* writers; an agent's own `git checkout` in W can still happen
    after the locked symbolic-ref check and before `git commit`. Here W switches to feat/y (from tip', so A^ == tip'
    and the parent check alone does not see it) right before the record file is written.
    Never a reported success. Two honest end states:
    - taken back: feat/x and feat/y both still at headCommit, the record neither staged nor on disk; the error is
      STALE_HEAD or CONFLICT (§5.9 does not name this case: 待定);
    - not taken back: CONFLICT, retryable false, details.commit = the stray commit A and a hint for the human — same as
      step 7's failed compare-and-swap take-back ("不再动分支，报 CONFLICT（不可重试），details 给出 A 和恢复提示").
    In both, refs/heads/feat/x never gets an approval commit.
    变红 (once fixed): drop the post-commit check that the commit landed on refs/heads/<branch>."""
    real = approval._write_new

    def switch_then_write(w, rel, data):
        gitio.git(w, "checkout", "-q", "-b", "feat/y")
        return real(w, rel, data)
    monkeypatch.setattr(approval, "_write_new", switch_then_write)
    try:
        r = call(t)
    except AisepError as e:
        err_ = e
    else:
        pytest.fail(f"reported success: commit {r['commit'][:7]} on {r['branch']}; "
                    f"feat/x={t.rev('refs/heads/feat/x')[:7]} feat/y={t.rev('refs/heads/feat/y')[:7]}")
    assert t.rev("refs/heads/feat/x") == t.head
    y = t.rev("refs/heads/feat/y")
    if y == t.head:
        assert err_.code in ("STALE_HEAD", "CONFLICT"), err_.code
        assert new_records(t) == [] and staged(t) == []
    else:
        assert t.rev(f"{y}^") == t.head  # the fixture: the stray approval commit sits on feat/y
        assert err_.code == "CONFLICT" and err_.retryable is False, (err_.code, err_.retryable)
        assert err_.details.get("commit") == y and err_.hint


# ================================================================== 2. rollback when index.lock is held

def _hold_index_lock(t):
    p = os.path.join(t.root, t.git("rev-parse", "--git-path", "index.lock"))
    open(p, "w").close()
    return p


def _rollback_is_honest(t, e, positive):
    """§5.9 step 8 + step 9. Only two honest end states (checked after the lock is released):
    - rolled back: the record is neither staged nor on disk, code COMMIT_FAILED (the file was not modified);
    - not rolled back (git rm --cached failed): the file stays on disk next to its staged entry — never a staged
      entry whose file was deleted — the error does not say "已回滚", and the next call reports the leftover as
      DIRTY_WORKTREE + orphanApproval (step 7's recovery path). The error code for this case is not fixed by §5.9
      (待定: COMMIT_FAILED or CONFLICT accepted here)."""
    assert t.rev("refs/heads/feat/x") == t.head
    on_disk, in_index = new_records(t), staged(t)
    if not in_index:
        assert on_disk == [] and e.code == "COMMIT_FAILED", (e.code, on_disk)
        assert positive()["duplicate"] is False  # positive twin: the worktree is clean again
        return
    assert [os.path.basename(f) for f in in_index] == on_disk, "staged record whose file was deleted"
    assert e.code in ("COMMIT_FAILED", "CONFLICT") and "已回滚" not in e.message, (e.code, e.message)
    nxt = err(t)
    assert nxt.code == "DIRTY_WORKTREE" and nxt.details.get("orphanApproval") is True


def test_rollback_when_index_locked_at_commit(t, monkeypatch):
    """index.lock taken after `git add`, before `git commit --only`: commit fails, and so does `git rm --cached`.
    The rollback cannot finish: the file stays staged and on disk, COMMIT_FAILED with details.orphanApproval and
    details.recover. retryable False: §5.9 step 8 only covers a successful `git rm --cached`; §7.1 rule 4 makes
    COMMIT_FAILED retryable "锁占用时", but retrying unchanged here meets DIRTY_WORKTREE (the orphan), so per the rule's
    own principle ("原样重试没有意义") it is not retryable (待定: the spec should say so for this case).
    变红: ignore the exit status of `git rm --cached` again (approval.py:262-263, `return "stuck"`)."""
    lock, real = [], approval._sha_file

    def sha(w, rel):
        if not lock:
            lock.append(_hold_index_lock(t))
        return real(w, rel)
    monkeypatch.setattr(approval, "_sha_file", sha)
    try:
        e = err(t)
    finally:
        if lock and os.path.exists(lock[0]):
            os.remove(lock[0])
    monkeypatch.undo()
    assert staged(t), "fixture: the record was staged before the commit failed"
    assert e.code == "COMMIT_FAILED" and e.retryable is False, (e.code, e.retryable)
    assert e.details.get("orphanApproval") is True and staged(t)[0] in e.details.get("recover", "")
    _rollback_is_honest(t, e, lambda: call(t))


def test_rollback_when_index_locked_at_add(t, monkeypatch):
    """index.lock taken right after the file is created, before `git add`: add, commit and rm --cached all fail; the
    record never reached the index, so the honest end state is "rolled back" (file deleted, COMMIT_FAILED), retryable
    because index.lock was held (§7.1 rule 4: COMMIT_FAILED 锁占用时 retryable).
    变红: in _unstage_and_maybe_delete drop the os.remove (approval.py:265) → file left behind with COMMIT_FAILED."""
    lock, real = [], approval._write_new

    def write(w, rel, data):
        real(w, rel, data)
        lock.append(_hold_index_lock(t))
    monkeypatch.setattr(approval, "_write_new", write)
    try:
        e = err(t)
    finally:
        if lock and os.path.exists(lock[0]):
            os.remove(lock[0])
    monkeypatch.undo()
    assert staged(t) == []  # the fixture really kept the record out of the index
    assert e.code == "COMMIT_FAILED" and e.retryable is True, (e.code, e.retryable)
    _rollback_is_honest(t, e, lambda: call(t))


# ================================================================== 3. step 6: WRITE_REJECTED, branch unchanged

def test_write_rejected_approves_a_stakeholder(t):
    """R4-5: approves → chiefArchitect (an arch:Stakeholder, not an element) makes the new record invalid
    (Ctx.approval_problems), so step 6 refuses. 变红: drop `cand.approval_problems()` from `bad` (approval.py:424)."""
    before = refs(t)
    e = err(t, approves=[BOSS])
    assert e.code == "WRITE_REJECTED", e.code
    assert e.details["recordProblems"]
    assert refs(t) == before and new_records(t) == [] and t.git("status", "--porcelain") == ""


def test_write_rejected_candidate_adds_violation(t, monkeypatch):
    """The candidate graph (W + the new file) adds a Violation that is not a record problem: the record file is made
    to carry one extra triple (a second @zh prefLabel on :newThing). 变红: test only `bad`, not `new`
    (approval.py:426 `if new or bad`)."""
    real = approval._record_file
    monkeypatch.setattr(approval, "_record_file", lambda *a: real(*a) + EXTRA)
    before = refs(t)
    e = err(t)
    assert e.code == "WRITE_REJECTED", e.code
    assert e.details["findings"] and not e.details["recordProblems"]
    assert refs(t) == before and new_records(t) == [] and t.git("status", "--porcelain") == ""


EXTRA = '\n:newThing skos:prefLabel "第二个中文名"@zh .\n'


# ================================================================== 4. re-validation under the lock

def test_code_commit_after_locate_before_lock_stale(t, monkeypatch):
    """§5.9 step 7 锁内复验: an agent's ordinary commit lands after the unlocked step 1 and before the lock. The
    re-check on tip' sees a non-approval commit in headCommit..tip' → STALE_HEAD, no approval commit.
    变红: delete `_stale(root, head, tip2)` under the lock (approval.py:389)."""
    def agent_commit(w):
        t.write("src/agent.py", "print('agent')\n")
        agent_commit.c = t.commit_all("agent commit before the lock")
    after_locate(monkeypatch, agent_commit)
    e = err(t)
    assert e.code == "STALE_HEAD", e.code
    assert t.rev("refs/heads/feat/x") == agent_commit.c and t.rev(f"{agent_commit.c}^") == t.head
    assert new_records(t) == [] and t.git("status", "--porcelain") == ""


# ================================================================== 5. dedupe key: each component counts

@pytest.mark.parametrize("second", [
    pytest.param(dict(approvedBy=BOT), id="approvedBy"),
    pytest.param(dict(approves=[M + "newThing", M + "auditTrail"]), id="approves-set"),
    pytest.param(dict(decision="Rejected"), id="decision"),
])
def test_dedupe_key_components(t, second):
    """§5.9 step 4: duplicate only when (gate, decision, approvedBy, approves set, evidence) are all equal.
    变红: drop the corresponding element from the tuple compared in _find_duplicate (approval.py:115-116)."""
    r1 = call(t)
    assert r1["duplicate"] is False
    # one second later: an Approved and a Rejected record at the same instant are ambiguous (WRITE_REJECTED)
    second = dict(second, now=NOW.replace(second=1))
    r2 = call(t, **second)
    assert r2["duplicate"] is False and r2["approval"]["iri"] != r1["approval"]["iri"]
    assert t.rev("refs/heads/feat/x") == r2["commit"] and t.rev(f"{r2['commit']}^") == r1["commit"]
    assert len(new_records(t)) == 2
    assert call(t, **second)["duplicate"] is True  # positive twin: the same second call is a replay


# ================================================================== 6. APPROVER_NOT_ALLOWED: not a Stakeholder

@pytest.mark.parametrize("who", ["newThing", "auditTrail"])
def test_approver_not_a_stakeholder(t, who):
    """approvedBy exists but is a model element, not an arch:Stakeholder → APPROVER_NOT_ALLOWED (§5.9 input table).
    变红: drop `or not ctx.is_a(boss, ARCH + "Stakeholder")` (approval.py:338)."""
    before = refs(t)
    e = err(t, approvedBy=M + who)
    assert e.code == "APPROVER_NOT_ALLOWED", e.code
    assert e.details["rejectedFields"] == ["approvedBy"]
    assert refs(t) == before and new_records(t) == [] and t.git("status", "--porcelain") == ""
