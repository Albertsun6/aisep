"""S5 governance_record_approval — gaps found by the independent review of PR #24 (docs/mcp-interface.md §5.9), written
by a session that does not implement aisep/approval.py.

Each test names the implementation line whose removal / weakening turns it red ("变红"; line numbers as of 685bc25).
Two tests failed on the implementation as reviewed (b858c19) and passed once 685bc25 fixed it:
  - test_branch_switched_in_worktree_before_lock: W was re-checked for detached HEAD only, not for still having
    `branch` checked out, so the approval landed on another branch while the result said `branch`.
  - test_rollback_when_index_locked_at_commit: step 8 ignored the exit status of `git rm --cached`; when it failed the
    file was deleted anyway and COMMIT_FAILED said "已回滚" while the index still staged the record.
  - test_branch_switched_in_worktree_after_recheck_before_commit (failed on f9c2338, passes on 78bb9a1): W switched
    after the locked symbolic-ref check; the commit landed on feat/y while success was reported on feat/x.
  - test_switched_take_back_spares_other_branch_with_same_subject, test_switched_branch_tip_with_same_subject_is_not_ours
    (failed on 78bb9a1, pass on 9dbae0b): the commit was recognised by its subject.
  - test_plain_success_does_not_depend_on_the_reflog[reflog-off / reflog-expired-after-commit] (failed on 9dbae0b,
    pass on f9515a3): the commit was found only through W's HEAD reflog.
  - test_hook_stacks_beyond_the_candidate_windows_still_names_a[off-21 / on-51] (failed on 1874d8f, pass on 79e202a):
    A was searched for only in fixed windows (last 20 commits of W, last 50 reflog entries).
Marked xfail(strict=True) on 26e7f7e: test_agent_plain_commit_takes_staged_record (major),
test_hook_on_top_reason_is_not_worktree_switched and test_rollback_kept_file_conflict_retryable_per_7_2 (minor).

Injection points are module attributes of aisep.approval / aisep.gitio replaced with monkeypatch (same style as
test_approval_extra.py): gitio.locate_worktree returns before the lock is taken; approval._sha_file is first called
after `git add` and right before `git commit --only`; approval._write_new runs right before `git add`."""
import os
from datetime import datetime, timezone

import pytest

from aisep import approval, gitio, tools
from aisep.errors import AisepError
from fixtures.topology import GOV, M, PREFIXES, Topo, record_ttl

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


def _switch_before_write(monkeypatch):
    """W switches to feat/y (from tip') after the locked symbolic-ref check, right before the record file is written."""
    real = approval._write_new

    def switch_then_write(w, rel, data):
        gitio.git(w, "checkout", "-q", "-b", "feat/y")
        return real(w, rel, data)
    monkeypatch.setattr(approval, "_write_new", switch_then_write)


def _no_success(t):
    try:
        r = call(t)
    except AisepError as e:
        return e
    pytest.fail(f"reported success: commit {r['commit'][:7]} on {r['branch']}; branches: {refs(t)}")


def _msg(t):
    """The subject record_approval gives its commit (the implementation recognises its own commit by it)."""
    return f"aisep: GateArchitecture Approved approval-20261120110000-architecture-{t.head[:7]}"


def _taken_back(t, e, tip):
    """The stray commit was taken back from feat/y only; feat/x (= tip) untouched; nothing staged or on disk."""
    assert e.code == "CONFLICT" and e.retryable is True, (e.code, e.retryable)
    assert e.details.get("reason") == "worktree-switched" and e.details.get("landedOn") == ["refs/heads/feat/y"]
    assert t.rev("refs/heads/feat/x") == tip and t.rev("refs/heads/feat/y") == tip
    assert new_records(t) == [] and staged(t) == []
    assert t.git("status", "--porcelain") == ""


def test_branch_switched_in_worktree_after_recheck_before_commit(t, monkeypatch):
    """§5.9 step 7: the write lock only excludes model_* writers; an agent's own `git checkout` in W can still happen
    after the locked symbolic-ref check and before `git commit`, which then moves feat/y (A^ == tip', so the parent
    check alone does not see it). Expected (78bb9a1): the stray commit is taken back from feat/y with a compare-and-swap
    update-ref, refs/heads/feat/x is never updated, the record file is unstaged and deleted (step 8, no `git restore`),
    CONFLICT retryable (§7.1 rule 4) with details.reason "worktree-switched" and details.landedOn (names not fixed by
    §5.9: 待定). Neither branch keeps an approval commit; nothing left in the index or on disk.
    Failed on f9c2338: reported success on feat/x while the commit sat on feat/y.
    变红: drop the post-commit check `_landed` (approval.py: `a = _landed(...)`, `if a is None: raise _misplaced(...)`)."""
    _switch_before_write(monkeypatch)
    _taken_back(t, _no_success(t), t.head)


def test_branch_switched_and_commit_stacked_cannot_take_back(t, monkeypatch):
    """Same window, and the agent also commits on feat/y right after our commit: ours is no longer a branch tip, so it
    cannot be taken back without dropping the agent's commit. §5.9 step 7 for a failed take-back: do not touch the
    branches, CONFLICT not retryable, a recovery hint for the human. refs/heads/feat/x untouched, the agent's commit
    kept, details.commit = our commit A (§5.9 step 7: "details 给出 A"; added in 9dbae0b).
    变红: let _misplaced update-ref whatever branch W is on even when ours is not its tip."""
    _switch_before_write(monkeypatch)
    real = approval._landed

    def agent_commits_first(w, root, branch, msg):
        t.write("src/agent.py", "print('agent')\n")
        agent_commits_first.c = t.commit_all("agent commit on top")
        return real(w, root, branch, msg)
    monkeypatch.setattr(approval, "_landed", agent_commits_first)
    e = _no_success(t)
    assert e.code == "CONFLICT" and e.retryable is False and e.hint, (e.code, e.retryable, e.hint)
    assert t.rev("refs/heads/feat/x") == t.head
    c = agent_commits_first.c
    assert t.rev("refs/heads/feat/y") == c and t.git("log", "-1", "--format=%s", f"{c}^") == _msg(t)
    assert t.rev(f"{c}^^") == t.head
    assert e.details.get("commit") == t.rev(f"{c}^")


def test_switched_take_back_spares_other_branch_with_same_subject(t, monkeypatch):
    """The commit is recognised by its subject. Another branch feat/z whose tip merely has the same subject (any
    commit can carry it) must not be rewound: the take-back may only touch the branch W actually moved.
    Failed on 78bb9a1 (feat/z rewound). 变红: identify the stray commit by subject alone again (_misplaced)."""
    z = t.git("commit-tree", "main^{tree}", "-p", "main", "-m", _msg(t))
    t.git("update-ref", "refs/heads/feat/z", z)
    _switch_before_write(monkeypatch)
    e = _no_success(t)
    assert t.rev("refs/heads/feat/z") == z, "feat/z was rewound"
    _taken_back(t, e, t.head)


def test_switched_branch_tip_with_same_subject_is_not_ours(t, monkeypatch):
    """refs/heads/feat/x's tip is a valid approval commit (another record file, GateDesign, evidence = headCommit) whose
    subject happens to equal the one record_approval will use. W then switches to feat/y before our commit. The
    implementation must not take feat/x's tip for its own commit: feat/x keeps that commit (no update-ref on
    `branch`), our stray commit is taken back from feat/y, CONFLICT.
    Failed on 78bb9a1 (feat/x rewound). 变红: recognise our commit by the subject of refs/heads/<branch>'s tip alone
    again (_landed)."""
    local = "approval-20261119230000-design-crafted"
    t.write(f"{GOV}/{local}.ttl", PREFIXES + record_ttl(local, "GateDesign", ["newThing"], t.head,
                                                        at="2026-11-19T23:00:00Z"))
    x = t.commit_all(_msg(t), trailers=[f"AISEP-Evidence: {t.head}"])
    _switch_before_write(monkeypatch)
    e = _no_success(t)
    assert t.rev("refs/heads/feat/x") == x, "feat/x was rewound"
    _taken_back(t, e, x)


def _drop_reflogs(t):
    """core.logAllRefUpdates=false and no reflog files: Git then writes no reflog at all for HEAD or the branches."""
    t.git("config", "core.logAllRefUpdates", "false")
    for ref in ("HEAD", "refs/heads/feat/x"):
        p = os.path.join(t.root, t.git("rev-parse", "--git-path", f"logs/{ref}"))
        if os.path.exists(p):
            os.remove(p)


@pytest.mark.parametrize("how", ["reflog-off", "reflog-expired-after-commit"])
def test_plain_success_does_not_depend_on_the_reflog(t, monkeypatch, how):
    """No branch switch at all. §5.9 step 7 decides success by the commit and its parent (A^ == tip'); nothing in
    §5.9 depends on a reflog, which may be disabled (core.logAllRefUpdates=false without log files) or emptied
    (`git reflog expire --expire=now --all`, e.g. a concurrent gc with aggressive settings) between `git commit` and
    the post-commit check. The plain call must still succeed with A on feat/x.
    Failed on 9dbae0b (reported CONFLICT). 变红: identify the commit only through the HEAD reflog again."""
    if how == "reflog-off":
        _drop_reflogs(t)
    else:
        real = approval._landed

        def expire_then_check(w, root, branch, msg):
            gitio.git(w, "reflog", "expire", "--expire=now", "--all")
            return real(w, root, branch, msg)
        monkeypatch.setattr(approval, "_landed", expire_then_check)
    try:
        r = call(t)
    except AisepError as e:
        pytest.fail(f"{e.code} (retryable={e.retryable}): {e.message}; feat/x={t.rev('refs/heads/feat/x')[:7]}")
    assert r["commit"] == t.rev("refs/heads/feat/x") and t.rev(f"{r['commit']}^") == t.head
    assert t.git("status", "--porcelain") == ""


def _hook_stacks(t, n):
    d = t.tmp / "hooks"
    d.mkdir(exist_ok=True)
    (d / "post-commit").write_text(
        '#!/bin/sh\n[ -n "$AISEP_TEST_IN_HOOK" ] && exit 0\nexport AISEP_TEST_IN_HOOK=1\nunset GIT_INDEX_FILE\n'
        f'i=0; while [ $i -lt {n} ]; do i=$((i+1)); git commit -q --allow-empty -m "hook-commit $i" || exit 1; done\n')
    os.chmod(d / "post-commit", 0o755)
    t.git("config", "core.hooksPath", str(d))


def test_post_commit_hook_commits_on_top(t):
    """A post-commit hook makes one more (empty) commit C on top of ours (A). A is no longer the branch tip: same as
    step 7's failed take-back ("A 之上又有新提交") — CONFLICT not retryable, details.commit = A, the branch is not
    rewound (C stays). Never a reported success.
    变红: report success whenever the reflog finds our commit, without checking it is the branch tip (_landed)."""
    d = t.tmp / "hooks"
    d.mkdir(exist_ok=True)
    (d / "post-commit").write_text('#!/bin/sh\n[ -n "$AISEP_TEST_IN_HOOK" ] && exit 0\n'
                                   'AISEP_TEST_IN_HOOK=1 exec env -u GIT_INDEX_FILE git commit -q --allow-empty -m hook-commit\n')
    os.chmod(d / "post-commit", 0o755)
    t.git("config", "core.hooksPath", str(d))
    e = _no_success(t)
    c = t.rev("refs/heads/feat/x")
    assert t.git("log", "-1", "--format=%s", c) == "hook-commit" and t.rev(f"{c}^^") == t.head
    a = t.rev(f"{c}^")
    assert e.code == "CONFLICT" and e.retryable is False, (e.code, e.retryable)
    assert e.details.get("commit") == a and e.hint


@pytest.mark.parametrize("reflog,n", [("off", 21), ("on", 51)])
def test_hook_stacks_beyond_the_candidate_windows_still_names_a(t, reflog, n):
    """Same as test_post_commit_hook_commits_on_top, but the hook stacks n commits on A: 21 with reflogs off (past the
    "last 20 commits of W" window), 51 with reflogs on (past the 50 reflog entries as well). A is not the tip, so
    nothing is taken back (CONFLICT, not retryable, branch kept) — and §5.9 step 7 still requires details to name A.
    A is reachable from refs/heads/<branch>: it is the first-parent ancestor of the tip whose parent is tip', so no
    fixed window is needed to find it.
    Failed on 1874d8f (details.commit None). 变红: bound the search for A to a fixed number of recent commits again."""
    if reflog == "off":
        _drop_reflogs(t)
    _hook_stacks(t, n)
    e = _no_success(t)
    c = t.rev("refs/heads/feat/x")
    a = t.rev(f"{c}~{n}")
    assert t.rev(f"{a}^") == t.head and t.git("log", "-1", "--format=%s", c) == f"hook-commit {n}"
    assert e.code == "CONFLICT" and e.retryable is False, (e.code, e.retryable)
    assert e.details.get("commit") == a, e.details.get("commit")


# ================================================================== 1b. an agent's plain `git commit` takes our staged record

def _in_head(t, rel):
    return t.git("ls-tree", "--name-only", "HEAD", "--", rel) == rel


@pytest.mark.xfail(strict=True, reason="26e7f7e: 记录先 git add 进 W 的共享 index，代理在 commit --only 之前的普通 git commit 把它带走；"
                                       "我们的 commit 失败后按「已回滚」处理：暂存删除已被 HEAD 跟踪的记录并删掉磁盘文件")
def test_agent_plain_commit_takes_staged_record(t, monkeypatch):
    """§5.9 step 7: after `git add -- <record>` and before `git commit --only`, the agent runs `git add src/agent.py`
    and a plain `git commit` (no -a) in W. Its commit C picks up everything staged, our record included.
    Two acceptable outcomes:
    - C does not contain the record (e.g. the record is staged in a private index, not W's): then step 7's parent
      check applies — A^ must be tip', so our call either succeeds with A^ == tip' or answers STALE_HEAD
      (concurrent-commit) after taking A back; nothing of ours left staged or on disk;
    - C contains the record: CONFLICT that names C (in details or the message); our record is then part of C.
    In no case "已回滚", and never undo what HEAD already tracks: a record file committed in C is not staged for
    deletion and not deleted from disk (step 8 rolls back only what this call staged).
    变红 (once fixed): stage the record in W's shared index again and roll back with `git rm --cached` + delete."""
    real, done = approval._sha_file, []

    def agent_commits(w, rel):
        if not done:
            done.append(1)
            t.write("src/agent.py", "print('agent')\n")
            t.git("add", "--", "src/agent.py")
            t.git("commit", "-q", "-m", "agent: plain commit")
            done.append(t.rev("HEAD"))
        return real(w, rel)
    monkeypatch.setattr(approval, "_sha_file", agent_commits)
    try:
        r, e = call(t), None
    except AisepError as x:
        r, e = None, x
    assert len(done) == 2, "fixture: the agent commit was not injected"
    c = done[1]
    assert t.rev(f"{c}^") == t.head
    rel = f"{GOV}/approval-20261120110000-architecture-{t.head[:7]}.ttl"
    c_has_record = t.git("ls-tree", "--name-only", c, "--", rel) == rel
    if e is not None:
        assert "已回滚" not in e.message, e.message
    if _in_head(t, rel):  # whatever happened, what HEAD tracks is not undone
        assert os.path.exists(t.path(rel)), "committed record deleted from disk"
        assert t.git("diff", "--cached", "--name-status", "--", rel) == "", "committed record staged for deletion"
    if c_has_record:
        assert e is not None and e.code == "CONFLICT", (e and e.code, r)
        assert c in repr(e.details) or c[:7] in e.message, (e.message, e.details)
    else:
        if e is None:
            assert t.rev(f"{r['commit']}^") == t.head, "approval commit stacked on the agent's commit"
        else:
            assert e.code == "STALE_HEAD" and e.details.get("reason") == "concurrent-commit", (e.code, e.details)
            assert t.rev("refs/heads/feat/x") == c
        assert staged(t) == [] or e is None
        assert new_records(t) == [] or e is None


# ================================================================== 1c. minor: reason and retryable of CONFLICT

@pytest.mark.xfail(strict=True, reason="26e7f7e: 钩子在 A 上叠提交（W 没被切换）也报 reason=worktree-switched")
def test_hook_on_top_reason_is_not_worktree_switched(t):
    """W is never switched; a post-commit hook stacks one commit on A. The CONFLICT must not claim the worktree was
    switched (details.reason). 变红 (once fixed): always use "worktree-switched" in _misplaced."""
    _hook_stacks(t, 1)
    e = _no_success(t)
    assert e.code == "CONFLICT" and e.details.get("reason") != "worktree-switched", (e.code, e.details.get("reason"))


@pytest.mark.xfail(strict=True, reason="26e7f7e: 回滚时记录文件被改动而保留的 CONFLICT 报 retryable=false；§7.2 只把"
                                       "「提交后撤回失败」的 CONFLICT 列为不可重试")
@pytest.mark.parametrize("where", ["commit-hook", "add-locked"])
def test_rollback_kept_file_conflict_retryable_per_7_2(t, monkeypatch, where):
    """§7.2: CONFLICT is retryable, except record_approval's failed take-back after a commit (§5.9 step 7). The
    step-8 CONFLICT "file changed by a hook or editor, kept" (commit failed) and its git-add twin are not take-backs.
    Note: retrying unchanged then meets DIRTY_WORKTREE + orphanApproval for the kept file, so §7.1 rule 4's principle
    would say not retryable — the spec's letter (§7.2) is asserted here as requested; the spec may want to list
    these CONFLICTs as exceptions instead.
    变红 (once fixed): retryable=False on those CONFLICTs again."""
    if where == "commit-hook":
        d = t.tmp / "hooks"
        d.mkdir(exist_ok=True)
        (d / "pre-commit").write_text(f'#!/bin/sh\nfor f in {GOV}/approval-20261120110000-*.ttl; do echo "# hook" >> "$f"; done\nexit 1\n')
        os.chmod(d / "pre-commit", 0o755)
        t.git("config", "core.hooksPath", str(d))
    else:
        real, lock = approval._write_new, []

        def write(w, rel, data):
            real(w, rel, data)
            with open(os.path.join(w, rel), "a", encoding="utf-8") as f:
                f.write("# editor\n")
            lock.append(_hold_index_lock(t))
        monkeypatch.setattr(approval, "_write_new", write)
    try:
        e = err(t)
    finally:
        if where == "add-locked" and lock and os.path.exists(lock[0]):
            os.remove(lock[0])
    assert e.code == "CONFLICT" and e.retryable is True, (e.code, e.retryable, e.message)
    assert t.rev("refs/heads/feat/x") == t.head and staged(t) == []


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
