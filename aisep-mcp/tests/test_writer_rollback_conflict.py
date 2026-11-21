"""Rollback conflict contract of the model_* write path (aisep/writer.py write_files).

When a multi-file write fails part-way and the in-process rollback finds that a file it already renamed was changed
again from outside (content no longer equals the bytes this write put there, deletion included), the file is kept as
is and an AisepError is raised: code CONFLICT, retryable False, details {"file": <rel path>, "kept": True}.
The pre-rename hash-check CONFLICT ("changed during the write, not overwritten") stays retryable and has no `kept`."""
import os

import pytest

from conftest import commit_all
from aisep import tools, write_tools as W, writer
from aisep.errors import AisepError

CFG = tools.Config()
P = "models/procurement/"


def _path(repo, f):
    return os.path.join(str(repo), P, f)


def _read(repo, f):
    with open(_path(repo, f), "rb") as fh:
        return fh.read()


def _two_file_supplier(repo):
    """procurement:supplier gets a definition in bpmn.ttl, so set_labels(prefLabel, definition) writes am4.ttl then
    bpmn.ttl (write_files renames in sorted order)."""
    with open(_path(repo, "bpmn.ttl"), "a", encoding="utf-8") as fh:
        fh.write('\n:supplier skos:definition "旧定义"@zh .\n')
    commit_all(repo, "definition in another file")


def _fail_second_after(external):
    """_before_rename hook: on the second rename (bpmn.ttl), first run `external` on the already renamed am4.ttl, then
    fail the rename."""
    n = []

    def hook(rel):
        n.append(rel)
        if len(n) == 2:
            external()
            raise OSError("injected rename failure")
    return hook


def _assert_kept_conflict(e, rel):
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.details.get("file") == rel, e.details
    assert e.retryable is False, "rollback conflict must not be retryable"
    assert e.details.get("kept") is True, e.details
    d = e.to_dict()
    assert d["code"] == "CONFLICT" and d["retryable"] is False and d["details"].get("kept") is True


def _set_labels(repo):
    with pytest.raises(AisepError) as ei:
        W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", definition="新定义", repo=str(repo))
    return ei.value


# ---------------------------------------------------------------- rollback finds a renamed file changed again

def test_rollback_conflict_rewritten_file_is_kept_not_retryable(repo, monkeypatch):
    _two_file_supplier(repo)
    bpmn_before = _read(repo, "bpmn.ttl")
    external = "# rewritten by an editor during rollback\n"

    def rewrite():
        assert '"供货商"@zh' in _read(repo, "am4.ttl").decode("utf-8")  # precondition: am4.ttl was already renamed
        with open(_path(repo, "am4.ttl"), "w", encoding="utf-8") as fh:
            fh.write(external)
    monkeypatch.setattr(writer, "_before_rename", _fail_second_after(rewrite))
    e = _set_labels(repo)
    assert _read(repo, "am4.ttl").decode("utf-8") == external  # neither restored nor deleted
    assert _read(repo, "bpmn.ttl") == bpmn_before              # the second file was never renamed
    _assert_kept_conflict(e, P + "am4.ttl")


def test_rollback_conflict_deleted_file_stays_deleted_not_retryable(repo, monkeypatch):
    _two_file_supplier(repo)

    def delete():
        assert os.path.exists(_path(repo, "am4.ttl"))
        os.unlink(_path(repo, "am4.ttl"))
    monkeypatch.setattr(writer, "_before_rename", _fail_second_after(delete))
    e = _set_labels(repo)
    assert not os.path.exists(_path(repo, "am4.ttl"))  # not recreated from the original bytes
    _assert_kept_conflict(e, P + "am4.ttl")


def test_rollback_conflict_new_file_rewritten_is_kept_not_retryable(repo, monkeypatch):
    """A file created by the write (before is None): rollback would unlink it; changed from outside it is kept.
    The four tools do not easily create a new file alongside a second one, so this drives write_files directly with
    the same rel-path convention the tools use."""
    new, old = P + "aaa-new.ttl", P + "am4.ttl"  # sorted: the new file is renamed first
    am4_before = _read(repo, "am4.ttl")
    edits = {new: "# new file\n", old: am4_before.decode("utf-8") + "\n# appended\n"}
    external = "# new file, then edited from outside\n"

    def rewrite():
        assert _read(repo, "aaa-new.ttl") == b"# new file\n"
        with open(_path(repo, "aaa-new.ttl"), "w", encoding="utf-8") as fh:
            fh.write(external)
    monkeypatch.setattr(writer, "_before_rename", _fail_second_after(rewrite))
    with pytest.raises(AisepError) as ei:
        writer.write_files(str(repo), edits, {new: None, old: am4_before})
    assert _read(repo, "aaa-new.ttl").decode("utf-8") == external  # not unlinked
    assert _read(repo, "am4.ttl") == am4_before
    _assert_kept_conflict(ei.value, new)


# ---------------------------------------------------------------- control: pre-rename hash check stays retryable

def test_prerename_hash_conflict_stays_retryable_without_kept(repo, monkeypatch):
    real = writer.write_files
    marker = "\n# saved by an editor meanwhile\n"

    def racing(root, edits, before):
        with open(_path(repo, "am4.ttl"), "a", encoding="utf-8") as fh:
            fh.write(marker)
        return real(root, edits, before)
    monkeypatch.setattr(writer, "write_files", racing)
    with pytest.raises(AisepError) as ei:
        W.model_set_labels(CFG, "procurement:supplier", prefLabel="供货商", repo=str(repo))
    e = ei.value
    assert e.code == "CONFLICT", (e.code, e.message)
    assert e.retryable is True and e.to_dict()["retryable"] is True
    assert e.details.get("file") == P + "am4.ttl"
    assert "kept" not in e.details
    t = _read(repo, "am4.ttl").decode("utf-8")
    assert t.endswith(marker) and '"供货商"@zh' not in t
