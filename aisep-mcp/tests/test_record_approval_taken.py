"""S5 governance_record_approval — CONFLICT "taken-by-other-commit" (approval._taken), written by a session that does not
implement aisep/approval.py. Expected behaviour (Albert 2026-11-21; docs/mcp-interface.md §5.9 steps 7-8, §7):
  1. retryable is False: the record now sits in a commit C that is not an approval commit, so an unchanged retry meets
     STALE_HEAD (_stale), never the record by the dedupe key;
  2. hint points the caller at C and says not to retry: it contains at least C's 7-char short SHA;
  3. details.takenByCommit == C (full 40 chars);
  4. details.commit names only this call's own approval commit A: absent when the call made no commit, == A (and
     != takenByCommit) when it did and then took A back.

Injection points (same style as test_record_approval_review.py): approval._sha_file is first called after
`git add --intent-to-add` and right before `git commit --only`; approval._unstage_and_maybe_delete is the rollback, so a
wrapper commits in W right after a take-back and before the real rollback looks at HEAD."""
import pytest

from aisep import approval, gitio
from aisep.errors import AisepError
from fixtures.topology import GOV
from test_record_approval_review import _switch_before_write, call, err, t  # noqa: F401  (t is a fixture)

REL = f"{GOV}/approval-20261120110000-architecture-{{}}.ttl"


def _commit_a_takes_record(t, monkeypatch):
    """An agent runs `git commit -a` in W between `git add --intent-to-add` and `git commit --only`: C takes the record.
    Our `git commit --only` then has nothing to commit and fails; step 8 finds HEAD tracking the record -> _taken
    (call site "git commit 失败"). Returns [C]."""
    real, done = approval._sha_file, []

    def agent_commits(w, rel):
        if not done:
            t.write("src/agent.py", "print('agent')\n")
            t.git("add", "--", "src/agent.py")
            t.git("commit", "-q", "-a", "-m", "agent: commit -a")
            done.append(t.rev("HEAD"))
        return real(w, rel)
    monkeypatch.setattr(approval, "_sha_file", agent_commits)
    return done


def _assert_taken(e, c):
    assert e.code == "CONFLICT" and e.details.get("reason") == "taken-by-other-commit", (e.code, e.details)
    assert e.retryable is False, e.retryable
    assert c[:7] in (e.hint or ""), e.hint
    assert e.details.get("takenByCommit") == c, e.details


# ================================================================== call site: `git commit --only` failed (no A)

def test_commit_a_taken_conflict_without_own_commit(t, monkeypatch):
    """Call site `_taken(w, rel, "git commit 失败", ...)`: this call made no commit, so details has no "commit" key.
    Red on the current implementation: _taken sets retryable=True, its hint ("重试会按去重键找到这条记录…") does not name
    C, and it reports C as details["commit"] instead of details["takenByCommit"]."""
    done = _commit_a_takes_record(t, monkeypatch)
    e = err(t)
    assert done, "fixture: the agent commit was not injected"
    c = done[0]
    assert t.git("ls-tree", "--name-only", c, "--", REL.format(t.head[:7])) == REL.format(t.head[:7]), \
        "fixture: git commit -a should take the intent-to-add record"
    _assert_taken(e, c)
    assert "commit" not in e.details, e.details


def test_commit_a_taken_unchanged_retry_is_stale_head(t, monkeypatch):
    """Basis of expectation 1: after C took the record, the same call again (injection removed) is STALE_HEAD — C is a
    non-approval commit after headCommit — not success and not duplicate. This pins the observed behaviour and passes
    on the current implementation; it is what makes retryable=True on the first CONFLICT wrong."""
    done = _commit_a_takes_record(t, monkeypatch)
    first = err(t)
    assert done and first.code == "CONFLICT", (first.code, first.details)
    monkeypatch.undo()
    try:
        r = call(t)
    except AisepError as e:
        assert e.code == "STALE_HEAD", (e.code, e.message, e.details)
    else:
        pytest.fail(f"unchanged retry succeeded: duplicate={r['duplicate']} commit={r['commit']}")


# ================================================================== call sites with an own commit A

def _commit_after_take_back(monkeypatch, out):
    """Right before the first rollback, the agent commits the still-staged record in W (plain `git commit`): its commit
    C is now W's HEAD and tracks the record, so the real rollback answers "taken"."""
    real = approval._unstage_and_maybe_delete

    def agent_then_rollback(w, rel, written_sha, staged=True):
        if "c" not in out:
            gitio.git(w, "commit", "-q", "-m", "agent: commits what is staged")
            out["c"] = gitio.git(w, "rev-parse", "HEAD")[1].strip()
        return real(w, rel, written_sha, staged)
    monkeypatch.setattr(approval, "_unstage_and_maybe_delete", agent_then_rollback)


def test_misplaced_taken_keeps_own_commit_and_taken_by(t, monkeypatch):
    """Call site in _misplaced (undone == "taken"): W is switched to feat/y before the write, our commit A lands on
    feat/y, _misplaced takes it back (feat/y -> A^), and the agent then commits the still-staged record as C on feat/y.
    Expected: details.commit == A (this call's commit), details.takenByCommit == C, A != C, retryable False, hint names C.
    Red on the current implementation: _taken overwrites _misplaced's details["commit"] (A) with C, sets no
    takenByCommit, retryable=True, and its hint does not name C."""
    _switch_before_write(monkeypatch)
    real_our, seen = approval._our_commit, {}

    def our(*a, **k):
        seen["a"] = real_our(*a, **k)
        return seen["a"]
    monkeypatch.setattr(approval, "_our_commit", our)
    _commit_after_take_back(monkeypatch, seen)
    e = err(t)
    a, c = seen.get("a"), seen.get("c")
    assert a and c and a != c, f"fixture: A={a} C={c}"
    assert t.rev("refs/heads/feat/x") == t.head, "feat/x moved"
    assert t.rev("refs/heads/feat/y") == c and t.rev(f"{c}^") == t.rev(f"{a}^"), "fixture: C should replace A on feat/y"
    _assert_taken(e, c)
    assert e.details.get("commit") == a, e.details


def test_concurrent_commit_taken_keeps_own_commit_and_taken_by(t, monkeypatch):
    """Call site "提交期间分支有新提交，已撤回提交 A" (undone == "taken"): an agent's plain commit C1 lands between
    `git add` and `git commit --only`, so our A sits on C1; step 7 takes A back (feat/x -> C1), then the agent commits
    the still-staged record as C on feat/x. A existed, so (expectation 4) details.commit == A and
    details.takenByCommit == C.
    Red on the current implementation: this call site passes no commit=A to _taken, which sets details["commit"] = C,
    no takenByCommit, retryable=True, and a hint without C."""
    real_sha, injected = approval._sha_file, []

    def agent_plain_commit(w, rel):
        if not injected:
            t.write("src/agent.py", "print('agent')\n")
            t.git("add", "--", "src/agent.py")
            t.git("commit", "-q", "-m", "agent: plain commit")
            injected.append(t.rev("HEAD"))
        return real_sha(w, rel)
    monkeypatch.setattr(approval, "_sha_file", agent_plain_commit)
    real_landed, seen = approval._landed, {}

    def landed(*a, **k):
        seen["a"] = real_landed(*a, **k)
        return seen["a"]
    monkeypatch.setattr(approval, "_landed", landed)
    _commit_after_take_back(monkeypatch, seen)
    e = err(t)
    a, c = seen.get("a"), seen.get("c")
    assert injected and a and c and a != c, f"fixture: C1={injected} A={a} C={c}"
    assert t.rev(f"{a}^") == injected[0] and t.rev(f"{c}^") == injected[0], "fixture: C should replace A on C1"
    assert t.rev("refs/heads/feat/x") == c
    _assert_taken(e, c)
    assert e.details.get("commit") == a, e.details
