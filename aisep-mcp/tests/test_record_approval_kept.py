"""S5 governance_record_approval — CONFLICT after a rollback that kept the record file (_unstage_and_maybe_delete ->
"kept"), written by a session that does not implement aisep/approval.py. docs/mcp-interface.md §5.9 steps 7-8, §7.1
rule 4, §7.2. Decided rule: a CONFLICT whose rollback kept the record file is never retryable — an unchanged retry
first meets DIRTY_WORKTREE (orphanApproval) for the kept file, so retrying is pointless. Such a CONFLICT also says
details.fileKept = True.

Paths covered:
  1. _misplaced: W is switched to feat/y before the write, the stray commit A on feat/y is taken back with update-ref,
     and then the record file turns out to have been changed by someone else -> kept.
  2. Step 7's sha256 check right before `git commit --only` differs (the file changed between `git add` and the
     commit) -> unstaged, kept.

Injection (same style as test_record_approval_review.py): the record file is really rewritten at the right moment, the
rollback itself is never mocked.
  - path 1: approval._our_commit is called inside _misplaced before the take-back and the rollback; a wrapper appends to
    the record file there (after `git commit`, so step 7's sha check has already passed).
  - path 2: approval._sha_file is first called right after `git add --intent-to-add` and before `git commit --only`; a
    wrapper appends to the record file on that first call only."""
import os

import pytest

from aisep import approval
from aisep.errors import AisepError
from fixtures.topology import GOV
from test_record_approval_review import _switch_before_write, call, err, new_records, staged, t  # noqa: F401

EDIT = b"# edited by someone else\n"


def _rel(t):
    return f"{GOV}/approval-20261120110000-architecture-{t.head[:7]}.ttl"


def _read(t, rel):
    with open(t.path(rel), "rb") as f:
        return f.read()


def _append(w, rel, out):
    with open(os.path.join(w, rel), "rb") as f:
        out["written"] = f.read()
    with open(os.path.join(w, rel), "ab") as f:
        f.write(EDIT)
    out["edited"] = out["written"] + EDIT


# ================================================================== path 1: _misplaced, take-back done, file kept

def _edit_before_take_back(monkeypatch, out):
    real = approval._our_commit

    def our(w, root, msg, blob, branch, tip2):
        out["a"] = real(w, root, msg, blob, branch, tip2)
        _append(w, f"{GOV}/{approval._name(msg)}", out)
        return out["a"]
    monkeypatch.setattr(approval, "_our_commit", our)


def test_misplaced_kept_file_conflict_not_retryable(t, monkeypatch):
    """W switched to feat/y before the write; our commit A lands on feat/y and _misplaced takes it back (feat/y -> A^);
    the record file had been changed by someone else, so the rollback keeps it and only unstages it.
    Expected: CONFLICT, retryable False, details.fileKept True, details.reason "worktree-switched", details.landedOn
    still ["refs/heads/feat/y"]; the edited file stays on disk, out of the index; feat/x untouched.
    Red on the current implementation: _misplaced ignores undone == "kept" and falls through to its last
    `CONFLICT ... retryable=True` without fileKept."""
    _switch_before_write(monkeypatch)
    seen = {}
    _edit_before_take_back(monkeypatch, seen)
    e = err(t)
    rel = _rel(t)
    # fixture: the injection ran, A really landed on feat/y and was taken back, the file on disk is the edited one
    assert seen.get("a") and "edited" in seen, f"fixture: injection did not run: {seen}"
    assert t.rev(f"{seen['a']}^") == t.head, "fixture: A should sit right on headCommit"
    assert t.rev("refs/heads/feat/y") == t.head, "fixture: A was not taken back from feat/y"
    assert t.rev("refs/heads/feat/x") == t.head, "feat/x moved"
    assert new_records(t) == [os.path.basename(rel)] and _read(t, rel) == seen["edited"], "edited file not kept"
    assert staged(t) == [], f"record still in the index: {staged(t)}"
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.details.get("reason") == "worktree-switched", e.details
    assert e.details.get("landedOn") == ["refs/heads/feat/y"], e.details
    assert e.retryable is False, (e.retryable, e.message)
    assert e.details.get("fileKept") is True, e.details


# ================================================================== path 2: sha256 differs before `git commit`

def _edit_after_add(monkeypatch, out):
    real = approval._sha_file

    def sha(w, rel):
        if "edited" not in out:
            _append(w, rel, out)
        return real(w, rel)
    monkeypatch.setattr(approval, "_sha_file", sha)


def _changed_before_commit(t, monkeypatch):
    seen = {}
    _edit_after_add(monkeypatch, seen)
    e = err(t)
    rel = _rel(t)
    # fixture: the edit happened, no commit was made, the edited file is on disk and out of the index
    assert "edited" in seen, "fixture: _sha_file was never called"
    assert t.rev("refs/heads/feat/x") == t.head, "feat/x moved"
    assert t.git("symbolic-ref", "HEAD") == "refs/heads/feat/x"
    assert new_records(t) == [os.path.basename(rel)] and _read(t, rel) == seen["edited"], "edited file not kept"
    assert staged(t) == [], f"record still in the index: {staged(t)}"
    return e


def test_changed_before_commit_kept_file_conflict_not_retryable(t, monkeypatch):
    """The record file changes between `git add --intent-to-add` and `git commit --only`: step 7's sha256 check fails,
    the rollback unstages the record and keeps the changed file.
    Expected: CONFLICT, retryable False, details.fileKept True; file keeps the changed content, not in the index,
    feat/x untouched.
    Red on the current implementation: that branch raises `CONFLICT ... retryable=True` with no details at all."""
    e = _changed_before_commit(t, monkeypatch)
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.retryable is False, (e.retryable, e.message)
    assert e.details.get("fileKept") is True, e.details


def test_changed_before_commit_unchanged_retry_is_dirty_worktree(t, monkeypatch):
    """Basis of retryable False: after path 2, leave the kept file in place and retry with the same arguments (injection
    removed). Step 7 meets the kept file first: DIRTY_WORKTREE with details.orphanApproval, files == [the record].
    Pins observed behaviour; expected to pass on the current implementation too."""
    first = _changed_before_commit(t, monkeypatch)
    assert first.code == "CONFLICT", (first.code, first.message)
    monkeypatch.undo()
    try:
        r = call(t)
    except AisepError as e:
        assert e.code == "DIRTY_WORKTREE", (e.code, e.message, e.details)
        assert e.details.get("orphanApproval") is True, e.details
        assert e.details.get("files") == [_rel(t)], e.details
    else:
        pytest.fail(f"unchanged retry succeeded: duplicate={r['duplicate']} commit={r['commit']}")
    assert t.rev("refs/heads/feat/x") == t.head
