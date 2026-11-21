"""governance_record_approval: the record file is deleted after `git add --intent-to-add` and before `git commit`.

Contract (written by an independent test author, not the implementer of aisep/approval.py):
  - AisepError (not FileNotFoundError), code CONFLICT, retryable True, no details.fileKept,
    details.reason == "file-deleted-before-commit";
  - afterwards the record path is not in the index (`git ls-files` finds nothing), the worktree is clean, and the
    branch head has not moved.

Injection: aisep.gitio.git is wrapped; right after the real `git add --intent-to-add -- <rel>` returns, the record
file is removed from disk. Nothing in the rollback itself is mocked."""
import os

from aisep import gitio
from fixtures.topology import GOV
from test_record_approval_review import call, t  # noqa: F401  (t is a fixture)

import pytest

from aisep.errors import AisepError


def _delete_after_intent_to_add(monkeypatch, seen):
    real = gitio.git

    def git(cwd, *args, **kw):
        res = real(cwd, *args, **kw)
        if not seen and args[:2] == ("add", "--intent-to-add"):
            rel = args[-1]
            os.remove(os.path.join(cwd, rel))
            seen.append(rel)
        return res
    monkeypatch.setattr(gitio, "git", git)


def test_record_deleted_between_intent_to_add_and_commit(t, monkeypatch):
    seen = []
    _delete_after_intent_to_add(monkeypatch, seen)
    try:
        call(t)
    except AisepError as e:
        err = e
    except FileNotFoundError as e:  # the defect: the rollback's os.remove meets the missing file
        pytest.fail(f"FileNotFoundError leaked instead of AisepError: {e!r}")
    else:
        pytest.fail("record_approval succeeded although the record file was deleted before the commit")
    monkeypatch.undo()
    assert seen, "fixture: the intent-to-add call was never seen"
    rel = seen[0]
    assert rel.startswith(GOV + "/"), rel

    assert err.code == "CONFLICT", (err.code, err.message)
    assert err.retryable is True, (err.retryable, err.message)
    assert "fileKept" not in err.details, err.details
    assert err.details.get("reason") == "file-deleted-before-commit", err.details

    assert t.git("ls-files", "--", rel) == "", "record path still in the index"
    assert t.git("status", "--porcelain") == "", t.git("status", "--porcelain")
    assert t.rev("refs/heads/feat/x") == t.head, "feat/x moved"
    assert t.git("symbolic-ref", "HEAD") == "refs/heads/feat/x"
