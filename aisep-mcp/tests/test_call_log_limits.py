"""PR #175 minor items (Albert's decision 25 of 2026-11-27; docs/mcp-interface.md §3.6, §5.17): the iris cap with its
count and hash, the shape rule of files[].path and target.worktree, the unified `files` rule for the writer's
rollback (keptFiles), the record_approval "gone" exit, lone surrogates in argsSha256, RFC 3339 only for since/until,
and a replaced log holding only half a line."""
import hashlib, json, os, shutil, subprocess

import pytest

from conftest import commit_all, init_repo
from fixtures.topology import M
from aisep import calllog, server, tools, writer
from aisep.errors import AisepError
from test_call_log import DRY, RUN, _h, _raw, lines, log_path
from test_call_log_read import ok, read, refused
from test_minor_1_record_deleted_before_commit import _delete_after_intent_to_add
from test_record_approval_review import t  # noqa: F401 — fixture

APPROVAL = {"model": "procurement", "gate": "GateArchitecture", "decision": "Approved",
            "approvedBy": M + "chiefArchitect", "branch": "main", "headCommit": "0" * 40}


def _sha_list(v):
    return "sha256:" + hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                                      .encode("utf-8", "surrogatepass")).hexdigest()


def test_iris_keeps_the_first_50_plus_count_and_hash_of_the_whole_list(repo):
    cfg = tools.Config(repo=str(repo))
    approves = [M + f"farIri{i:03d}" for i in range(120)]
    r = server.logged_call(cfg, RUN, "governance_record_approval", dict(APPROVAL, approves=approves, repo=str(repo)))
    assert r.is_error
    req = lines(repo)[0]["measured"]["request"]
    full = [APPROVAL["approvedBy"]] + approves
    assert calllog.IRIS_MAX == 50 and req["iris"] == full[:50]
    assert req["irisCount"] == 121 and req["irisSha256"] == _sha_list(full)
    raw = _raw(repo)
    assert b"farIri048" in raw and b"farIri049" not in raw and b"farIri119" not in raw  # item 51 on: count + hash only
    server.logged_call(cfg, RUN, "model_add_element", dict(DRY, slug=None))  # nothing to list: same fields
    short = lines(repo)[1]["measured"]["request"]
    assert short["iris"] == [] and short["irisCount"] == 0 and short["irisSha256"] == _sha_list([])
    server.logged_call(cfg, RUN, "model_set_labels", {"iri": "procurement:supplier", "prefLabel": "x"})
    one = lines(repo)[2]["measured"]["request"]
    assert one["iris"][0] == "procurement:supplier" and one["irisCount"] == len(one["iris"]) <= 2


def test_file_path_and_worktree_outside_the_path_rule_are_hashed(template, tmp_path):
    """The caller's `file` reaches measured.files[].path and its served directory reaches target.worktree: a Chinese
    file name or directory name passes no path rule, so only its sha256 is logged; a plain path stays verbatim."""
    r = tmp_path / "工作区 哨兵"
    shutil.copytree(template, r)
    init_repo(r)
    commit_all(r, "start")
    cfg = tools.Config(repo=str(r))
    rel = "models/procurement/哨兵文件.ttl"
    res = server.logged_call(cfg, RUN, "model_add_element", dict(DRY, slug="newThing", file=rel, dryRun=False))
    assert not res.is_error, res.content[0].text
    plain = server.logged_call(cfg, RUN, "model_set_labels", {"iri": "procurement:supplier", "prefLabel": "供应商甲"})
    assert not plain.is_error, plain.content[0].text
    a, b = lines(r)
    root = os.path.realpath(r)
    assert a["measured"]["files"] == [{"path": _h(rel), "before": None,
                                       "after": "sha256:" + hashlib.sha256(open(os.path.join(r, rel), "rb").read()).hexdigest()}]
    assert a["measured"]["target"]["worktree"] in (_h(str(r)), _h(root)) and a["measured"]["target"]["branch"] == "main"
    assert [f["path"] for f in b["measured"]["files"]] == [f["path"] for f in plain.structured_content["filesChanged"]]
    assert all(isinstance(f["path"], str) for f in b["measured"]["files"])
    raw = _raw(r)
    assert "哨兵".encode() not in raw and "哨兵".encode("unicode_escape") not in raw
    out = json.dumps(calllog.model_call_log(cfg)["items"], ensure_ascii=False)  # log.path is a start-up value
    assert "哨兵" not in out


def test_writer_rollback_logs_the_kept_files_like_approval_kept(repo, monkeypatch):
    """write_files fails after the rename and someone has changed the written file meanwhile: it stays on disk
    (details.keptFiles), so `files` names it with `after` = the bytes this call wrote (§3.6 unified rule)."""
    cfg = tools.Config(repo=str(repo))
    real, calls, seen = os.fsync, [], {}

    def fsync(fd):
        calls.append(fd)
        if len(calls) == 2:  # one edit: its temp file, then the first directory fsync after the rename
            (rel,) = subprocess.run(["git", "-C", str(repo), "diff", "--name-only"], capture_output=True, text=True,
                                    check=True).stdout.split()
            p = os.path.join(repo, rel)
            with open(p, "rb") as f:
                seen.update(rel=rel, wrote=hashlib.sha256(f.read()).hexdigest())
            with open(p, "ab") as f:
                f.write(b"# changed from outside during the write\n")
            raise OSError("injected failure after the rename")
        return real(fd)
    before = {}
    for rel in ("models/procurement/am4.ttl",):
        with open(os.path.join(repo, rel), "rb") as f:
            before[rel] = hashlib.sha256(f.read()).hexdigest()
    monkeypatch.setattr(writer.os, "fsync", fsync)
    res = server.logged_call(cfg, RUN, "model_set_labels", {"iri": "procurement:supplier", "prefLabel": "供应商乙"})
    monkeypatch.undo()
    assert res.is_error and res.structured_content["error"]["code"] == "CONFLICT", res.content[0].text
    assert res.structured_content["error"]["details"]["keptFiles"] == [seen["rel"]]
    (line,) = lines(repo)
    assert line["measured"]["outcome"] == "CONFLICT"
    assert line["measured"]["files"] == [{"path": seen["rel"], "before": "sha256:" + before[seen["rel"]],
                                          "after": "sha256:" + seen["wrote"]}]


def test_record_approval_file_deleted_before_commit_logs_no_file(t, monkeypatch):
    """The "gone" exit (file-deleted-before-commit): the record this call wrote is no longer on disk -> files []."""
    seen = []
    _delete_after_intent_to_add(monkeypatch, seen)
    cfg = tools.Config(allow_roots=(str(t.root),))
    r = server.logged_call(cfg, RUN, "governance_record_approval", dict(
        APPROVAL, approves=[M + "newThing"], branch="feat/x", headCommit=t.head, repo=str(t.root)))
    monkeypatch.undo()
    assert seen and r.is_error, r.content[0].text
    assert r.structured_content["error"]["details"]["reason"] == "file-deleted-before-commit"
    (line,) = lines(t.root)
    assert line["measured"]["outcome"] == "CONFLICT" and line["measured"]["target"]["branch"] == "feat/x"
    assert line["measured"]["files"] == []


def test_args_with_a_lone_surrogate_are_hashed_with_surrogatepass(repo):
    cfg = tools.Config(repo=str(repo))
    args = dict(DRY, prefLabel="\ud800x")
    server.logged_call(cfg, RUN, "model_add_element", args)
    (line,) = lines(repo)
    assert line["measured"]["request"]["argsSha256"] == _sha_list(args)


def test_since_until_take_rfc3339_only(repo):
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 2)
    for bad in ("20261127T000000Z", "2026-11-27T00:00:00", "2026-11-27 00:00:00Z", "2026-W48-5T00:00:00Z"):
        for field in ("since", "until"):
            e = read(cfg, **{field: bad}).structured_content["error"]
            assert e["code"] == "INVALID_ARGUMENT" and e["details"]["rejectedFields"] == [field], (field, bad)
        with pytest.raises(AisepError):
            calllog._time(bad, "since")
    assert len(ok(cfg, since="2000-01-01t00:00:00z")["items"]) == 2
    assert len(ok(cfg, until="2000-01-01T08:00:00.5+08:00")["items"]) == 0


def test_cursor_on_a_log_replaced_by_half_a_line_is_log_replaced(repo):
    """Same inode, the new content only half a line (no complete line yet): the file was replaced, not truncated."""
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 4)
    cur = ok(cfg, limit=1)["nextCursor"]
    path = log_path(repo)
    ino = os.stat(path).st_ino
    with open(path, "r+b") as f:
        f.truncate(0)
        f.write(b'{"v":1,"measured":')
    assert os.stat(path).st_ino == ino
    e = read(cfg, cursor=cur).structured_content["error"]
    assert e["code"] == "INVALID_ARGUMENT" and e["details"] == {"rejectedFields": ["cursor"], "reason": "log-replaced"}
