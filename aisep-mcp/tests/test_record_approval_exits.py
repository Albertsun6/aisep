"""S5 governance_record_approval — uniform rollback exits (docs/mcp-interface.md §5.9 steps 7-8), written by a session
that does not implement aisep/approval.py.

Decided exits after _unstage_and_maybe_delete:
  - "taken" (W's HEAD already tracks the record, a commit C took it): CONFLICT, details.reason "taken-by-other-commit",
    retryable False, details.takenByCommit == C (40 chars), hint contains C[:7]; no details.commit when this call made
    no approval commit A of its own.
  - "kept" (the file was changed by someone else; out of the index, left on disk): retryable False,
    details.fileKept True, details.recover a non-empty manual cleanup command, a non-empty hint.

Call sites covered:
  1. `git add --intent-to-add` fails and the rollback (staged=False) answers "taken".
  2a. `git add --intent-to-add` fails and the rollback answers "kept".
  2b. `git commit --only` fails (pre-commit hook) and the rollback answers "kept".
  3. Post-commit parent check: A sits on an agent's commit C1, A is taken back with update-ref, then "kept".
  4. sha256 check right before `git commit --only` differs and the rollback answers "taken".

Injection is real (the rollback itself is never mocked): files are really rewritten / committed at the right moment.
  - gitio.git is wrapped and acts only on the `git add --intent-to-add` call (1);
  - approval._write_new is wrapped: it runs right before `git add` (2a);
  - a failing pre-commit hook rewrites the record (2b);
  - approval._sha_file is first called after `git add` and right before `git commit --only` (3, 4);
  - approval._landed is called right after `git commit --only` and before the parent check / take-back (3)."""
import os

from aisep import approval, gitio
from fixtures.topology import GOV
from test_record_approval_review import _hold_index_lock, err, new_records, staged, t  # noqa: F401  (t is a fixture)

EDIT = b"# edited by someone else\n"


def _rel(t):
    return f"{GOV}/approval-20261120110000-architecture-{t.head[:7]}.ttl"


def _read(t, rel):
    with open(t.path(rel), "rb") as f:
        return f.read()


def _append(path):
    with open(path, "ab") as f:
        f.write(EDIT)


def _assert_taken(e, c):
    assert e.code == "CONFLICT", (e.code, e.message, e.details)
    assert e.details.get("reason") == "taken-by-other-commit", e.details
    assert e.retryable is False, e.retryable
    assert len(c) == 40 and e.details.get("takenByCommit") == c, e.details
    assert c[:7] in (e.hint or ""), e.hint
    assert "commit" not in e.details, e.details  # this call made no approval commit A


def _assert_kept(e, rel):
    assert e.retryable is False, (e.retryable, e.message)
    assert e.details.get("fileKept") is True, e.details
    rec = e.details.get("recover")
    assert isinstance(rec, str) and rec.strip() and rel in rec, e.details
    assert (e.hint or "").strip(), e.hint


# ================================================================== 1. `git add --intent-to-add` failed -> "taken"

def test_add_failed_taken_by_other_commit(t, monkeypatch):
    """The record file is written; just before our `git add --intent-to-add`, an agent runs `git add -- rel` +
    `git commit` in W (commit C takes the record) and holds index.lock, so our add really fails. Rollback with
    staged=False finds HEAD:rel -> "taken". Expected: the taken exit (CONFLICT, taken-by-other-commit, retryable False,
    takenByCommit == C, hint names C[:7], no "commit" key) plus details.output (git's stderr).
    Red on the current implementation: the add-failed branch only checks `== "kept"`, so "taken" falls through to
    COMMIT_FAILED "git add 失败，已删除新建的记录文件" (retryable because the output mentions index.lock), although
    nothing was deleted."""
    real, done = gitio.git, []

    def git(cwd, *args, **kw):
        if not done and args[:2] == ("add", "--intent-to-add"):
            rel = args[-1]
            t.git("add", "--", rel)
            t.git("commit", "-q", "-m", "agent: commits the record")
            done.append(t.rev("HEAD"))
            lock = _hold_index_lock(t)
            try:
                return real(cwd, *args, **kw)
            finally:
                os.remove(lock)
        return real(cwd, *args, **kw)
    monkeypatch.setattr(gitio, "git", git)
    e = err(t)
    rel = _rel(t)
    # fixture: C really took the record, our add was really the call that failed, the file is still there
    assert done, "fixture: the git add --intent-to-add call was never intercepted"
    c = done[0]
    assert t.rev(f"{c}^") == t.head and t.rev("refs/heads/feat/x") == c, "fixture: C should sit right on headCommit"
    assert t.git("ls-tree", "--name-only", c, "--", rel) == rel, "fixture: C does not contain the record"
    assert os.path.exists(t.path(rel)), "committed record deleted from disk"
    _assert_taken(e, c)
    assert e.details.get("output"), e.details


# ================================================================== 2a. `git add --intent-to-add` failed -> "kept"

def test_add_failed_kept_file_details(t, monkeypatch):
    """The record file is written, then changed by someone else, and index.lock is held: `git add --intent-to-add`
    fails, the rollback (staged=False) sees a different sha256 -> "kept".
    Expected: CONFLICT, retryable False, details.fileKept True, details.recover a non-empty cleanup command naming
    rel, non-empty hint.
    Red on the current implementation: that CONFLICT carries details={"output": ...} only (no fileKept, no recover)
    and no hint."""
    real, lock, seen = approval._write_new, [], {}

    def write(w, rel, data):
        real(w, rel, data)
        _append(os.path.join(w, rel))
        seen["edited"] = data + EDIT
        lock.append(_hold_index_lock(t))
    monkeypatch.setattr(approval, "_write_new", write)
    try:
        e = err(t)
    finally:
        if lock and os.path.exists(lock[0]):
            os.remove(lock[0])
    rel = _rel(t)
    # fixture: file kept with the edited content, never staged, branch untouched
    assert "edited" in seen and lock, "fixture: injection did not run"
    assert new_records(t) == [os.path.basename(rel)] and _read(t, rel) == seen["edited"], "edited file not kept"
    assert staged(t) == [] and t.rev("refs/heads/feat/x") == t.head
    assert e.code == "CONFLICT", (e.code, e.message)
    _assert_kept(e, rel)


# ================================================================== 2b. `git commit --only` failed -> "kept"

def test_commit_failed_kept_file_details(t):
    """A pre-commit hook appends to the record file and exits 1: `git commit --only` fails, the rollback unstages the
    record and sees a different sha256 -> "kept".
    Expected: CONFLICT, retryable False, details.fileKept True, details.recover non-empty (names rel), non-empty hint.
    Red on the current implementation: that CONFLICT carries details={"output": ...} only and no hint."""
    d = t.tmp / "hooks"
    d.mkdir(exist_ok=True)
    (d / "pre-commit").write_text(
        f'#!/bin/sh\nfor f in {GOV}/approval-20261120110000-*.ttl; do echo "# hook" >> "$f"; done\nexit 1\n')
    os.chmod(d / "pre-commit", 0o755)
    t.git("config", "core.hooksPath", str(d))
    e = err(t)
    rel = _rel(t)
    # fixture: the hook ran (file ends with its line), file kept, not staged, branch untouched
    assert new_records(t) == [os.path.basename(rel)], "fixture: record file not kept"
    assert _read(t, rel).endswith(b"# hook\n"), "fixture: the hook did not rewrite the record"
    assert staged(t) == [] and t.rev("refs/heads/feat/x") == t.head
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.details.get("output") is not None, e.details
    _assert_kept(e, rel)


# ================================================================== 3. A on C1, taken back, then "kept"

def test_concurrent_commit_taken_back_then_kept(t, monkeypatch):
    """An agent's plain commit C1 (src/agent.py only) lands between `git add --intent-to-add` and `git commit --only`;
    our A sits on C1. Right after the commit (at _landed) someone appends to the record file. Step 7 takes A back
    (feat/x -> C1); the rollback unstages the record and sees a different sha256 -> "kept".
    Expected: STALE_HEAD, details.reason "concurrent-commit", details.fileKept True, details.recover non-empty, non-empty
    hint, and the message names rel (the file is still there).
    Red on the current implementation: "kept" falls through to the plain STALE_HEAD "已撤回本次批准" with
    details={"reason": "concurrent-commit"} only, no hint, no rel in the message."""
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

    def landed(w, root, branch, msg):
        seen["a"] = real_landed(w, root, branch, msg)
        p = os.path.join(w, GOV, approval._name(msg))
        with open(p, "rb") as f:
            seen["edited"] = f.read() + EDIT
        _append(p)
        return seen["a"]
    monkeypatch.setattr(approval, "_landed", landed)
    e = err(t)
    rel = _rel(t)
    # fixture: C1 injected, A landed on C1 and was taken back, the edited file is kept and out of the index
    assert injected and seen.get("a"), f"fixture: C1={injected} A={seen.get('a')}"
    c1, a = injected[0], seen["a"]
    assert t.rev(f"{c1}^") == t.head and t.rev(f"{a}^") == c1, "fixture: A should sit on C1"
    assert t.git("ls-tree", "--name-only", c1, "--", rel) == "", "fixture: C1 must not contain the record"
    assert t.rev("refs/heads/feat/x") == c1, "fixture: A was not taken back"
    assert new_records(t) == [os.path.basename(rel)] and _read(t, rel) == seen["edited"], "edited file not kept"
    assert staged(t) == [], f"record still in the index: {staged(t)}"
    assert e.code == "STALE_HEAD", (e.code, e.message)
    assert e.details.get("reason") == "concurrent-commit", e.details
    _assert_kept(e, rel)
    assert rel in e.message, e.message


# ================================================================== 4. sha256 differs before `git commit` -> "taken"

def test_changed_before_commit_taken_by_other_commit(t, monkeypatch):
    """After `git add --intent-to-add` and before `git commit --only`, an agent rewrites the record and commits it with a
    plain `git add -- rel` + `git commit` (C contains the rewritten record). Step 7's sha256 check differs, the rollback
    finds HEAD:rel -> "taken". Expected: the taken exit, no "commit" key.
    Probably already green on the current implementation: this call site already uses _taken(w, rel, ...) without
    commit=, and _taken sets retryable False, takenByCommit and a hint naming C[:7]; this test pins it."""
    real, done = approval._sha_file, []

    def agent_rewrites_and_commits(w, rel):
        if not done:
            _append(os.path.join(w, rel))
            t.git("add", "--", rel)
            t.git("commit", "-q", "-m", "agent: rewrites and commits the record")
            done.append(t.rev("HEAD"))
        return real(w, rel)
    monkeypatch.setattr(approval, "_sha_file", agent_rewrites_and_commits)
    e = err(t)
    rel = _rel(t)
    assert done, "fixture: _sha_file was never called"
    c = done[0]
    assert t.rev(f"{c}^") == t.head and t.rev("refs/heads/feat/x") == c, "fixture: C should sit right on headCommit"
    assert t.git("ls-tree", "--name-only", c, "--", rel) == rel, "fixture: C does not contain the record"
    assert t.git("show", f"{c}:{rel}").endswith(EDIT.decode().strip()), "fixture: C should hold the rewritten record"
    assert t.git("status", "--porcelain") == "", "committed record unstaged or deleted"
    _assert_taken(e, c)
