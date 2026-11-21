"""writer.write_files in-process rollback over three existing files, all renamed, then a failure; some renamed files
were changed from outside in the meantime.

Contract (independent test author):
  - AisepError CONFLICT, retryable False, details.kept True;
  - details.file is the first file found in conflict (compatible with today's single-file details);
  - details.keptFiles lists every file left unrolled-back because of a conflict (repo-relative paths);
  - every other renamed file — rolled back before or after the conflicting one — is restored to its pre-write bytes.

Trigger: all renames succeed; the first directory fsync after the renames (writer.write_files fsyncs one temp file per
edit, then the directories) runs the external edits and then raises OSError. Nothing in the rollback is mocked."""
import os

import pytest

from aisep import writer
from aisep.errors import AisepError

P = "models/procurement/"
FILES = [P + "am4.ttl", P + "bpmn.ttl", P + "code.ttl"]  # sorted: the rename order; rollback walks it in reverse
EXTERNAL = b"# rewritten from outside during the write\n"


def _read(repo, rel):
    with open(os.path.join(str(repo), rel), "rb") as f:
        return f.read()


def _run(repo, monkeypatch, changed):
    before = {f: _read(repo, f) for f in FILES}
    edits = {f: before[f].decode("utf-8") + "\n# appended by this write\n" for f in FILES}
    real, calls = os.fsync, []

    def fsync(fd):
        calls.append(fd)
        if len(calls) == len(FILES) + 1:  # first directory fsync: every rename has completed
            for f in FILES:
                assert _read(repo, f) == edits[f].encode("utf-8"), f"fixture: {f} not renamed yet"
            for f in changed:
                with open(os.path.join(str(repo), f), "wb") as fh:
                    fh.write(EXTERNAL)
            raise OSError("injected failure after all renames")
        return real(fd)
    monkeypatch.setattr(writer.os, "fsync", fsync)
    with pytest.raises(AisepError) as ei:
        writer.write_files(str(repo), edits, before)
    monkeypatch.undo()
    assert len(calls) > len(FILES), "fixture: failure was not injected"
    return ei.value, before


def _assert_conflict(e, first, kept):
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.retryable is False, e.retryable
    assert e.details.get("kept") is True, e.details
    assert e.details.get("file") == first, e.details
    k = e.details.get("keptFiles")
    assert isinstance(k, list), e.details
    assert sorted(k) == sorted(kept), e.details


def test_middle_file_conflict_others_restored(repo, monkeypatch):
    mid = FILES[1]
    e, before = _run(repo, monkeypatch, [mid])
    assert _read(repo, mid) == EXTERNAL  # kept as the outside editor left it
    assert _read(repo, FILES[2]) == before[FILES[2]], "file rolled back before the conflict not restored"
    assert _read(repo, FILES[0]) == before[FILES[0]], "file rolled back after the conflict not restored"
    _assert_conflict(e, mid, [mid])


def test_two_conflicting_files_both_listed(repo, monkeypatch):
    a, c = FILES[0], FILES[2]
    e, before = _run(repo, monkeypatch, [a, c])
    assert _read(repo, a) == EXTERNAL and _read(repo, c) == EXTERNAL
    assert _read(repo, FILES[1]) == before[FILES[1]], "non-conflicting file not restored"
    _assert_conflict(e, c, [a, c])  # rollback walks in reverse: code.ttl is met first
