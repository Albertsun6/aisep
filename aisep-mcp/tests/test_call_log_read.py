"""model_call_log: the read-only reader of the call log (docs/mcp-interface.md §5.15; ADR-031 as amended by Albert's
decision 14 of 2026-11-27). Exits 1.5/1–8 of the workbench read-only contract: the profile split, page order and
fidelity to disk, cursors that survive appends and refuse a replaced or truncated file, bad lines counted not returned,
the sentinel label absent from log and output, every filter (one by one and combined), restart-stable results."""
import json, os

import anyio
from mcp import Client, StdioServerParameters

from conftest import ROOT, git
from aisep import calllog, server, tools
from test_call_log import P0, PY, REGISTER, WB, full, lines, log_path, wrepo  # noqa: F401 — fixtures

SENT = "哨兵-7f3a"
RUN = {"pid": 0, "profile": "all", "transport": "test", "allowRoots": [], "repo": None}


def read(cfg, **args):
    r = server.call(cfg, "model_call_log", args)
    return r


def ok(cfg, **args):
    r = read(cfg, **args)
    assert not r.is_error, r.content[0].text
    return r.structured_content


def refused(cfg, n):
    """n audited calls refused by the schema (fast); each logs one line whose `iris` names it."""
    for i in range(n):
        server.logged_call(cfg, RUN, "model_set_labels", {"iri": f"urn:x:{i}", "bogus": 1})


def raw_lines(repo):
    """(offset, parsed) of every line on disk, oldest first."""
    out, off = [], 0
    with open(log_path(repo), "rb") as f:
        for b in f.read().split(b"\n")[:-1]:
            out.append((off, json.loads(b)))
            off += len(b) + 1
    return out


def walk(cfg, **args):
    """Every page until nextCursor is null; returns the items in order."""
    got, cur = [], None
    while True:
        p = ok(cfg, **args, **({"cursor": cur} if cur else {}))
        got += p["items"]
        cur = p["nextCursor"]
        if cur is None:
            return got


def ids(items):
    return [i["measured"]["request"]["iris"][0] for i in items]


# ---------------------------------------------------------------- 1: profiles; the reader itself is not logged

def test_listed_for_workbench_only_and_agent_cannot_call_it(repo):
    assert "model_call_log" in server.listed("workbench") and "model_call_log" in server.listed("all")
    assert "model_call_log" not in server.listed("agent")

    async def go():
        p = StdioServerParameters(command=PY, args=["-m", "aisep.server", "--repo", str(repo), "--allow-root",
                                                    str(repo.parent), "--profile", "agent"],
                                  cwd=str(repo), env=dict(os.environ, PYTHONPATH=ROOT))
        async with Client(p) as c:
            assert "model_call_log" not in {t.name for t in (await c.list_tools()).tools}
            try:
                await c.call_tool("model_call_log", {})
            except Exception as e:  # noqa: BLE001 — an unlisted tool is a protocol error
                return str(e)
            raise AssertionError("agent 画像调用 model_call_log 没有被拒")
    assert "Unknown tool" in anyio.run(go)
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 1)
    server.logged_call(cfg, RUN, "model_call_log", {})
    assert len(lines(repo)) == 1  # a read-only tool: reading writes no line


# ---------------------------------------------------------------- 2: order, limit, fidelity to disk; absent log

def test_first_page_newest_first_and_equal_to_disk_lines(repo):
    cfg = tools.Config(repo=str(repo))
    p = ok(cfg)
    assert p["log"] == {"path": log_path(repo), "present": False, "sizeBytes": None, "resolvedFrom": "repo"}
    assert p["items"] == [] and p["nextCursor"] is None
    refused(cfg, 7)
    disk = raw_lines(repo)
    p = ok(cfg, limit=5)
    assert p["log"]["present"] and p["log"]["sizeBytes"] == os.path.getsize(log_path(repo))
    assert p["items"] == [{"offset": o, **x} for o, x in reversed(disk)][:5]
    assert ids(p["items"]) == [f"urn:x:{i}" for i in (6, 5, 4, 3, 2)] and p["nextCursor"]
    assert ok(cfg, limit=50)["nextCursor"] is None
    assert ok(cfg) == ok(tools.Config(repo=str(repo)))  # T4: nothing kept between calls; a fresh config reads the same


def test_no_location_and_allow_root_first(repo, tmp_path):
    p = ok(tools.Config(allow_roots=(str(tmp_path / "nowhere"),)))
    assert p["log"] == {"path": None, "present": False, "sizeBytes": None, "resolvedFrom": None}
    p = ok(tools.Config(allow_roots=(os.path.realpath(repo),), repo=str(tmp_path)))
    assert p["log"]["resolvedFrom"] == "allow-root" and p["log"]["path"] == log_path(repo)


# ---------------------------------------------------------------- 3, 4: cursors

def test_cursor_pages_do_not_shift_when_lines_are_appended(repo):
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 10)
    p1 = ok(cfg, limit=4)
    p2 = ok(cfg, limit=4, cursor=p1["nextCursor"])
    refused(cfg, 3)  # urn:x:0..2 again, appended after the cursor was issued
    assert ok(cfg, limit=4, cursor=p1["nextCursor"]) == dict(p2, log=ok(cfg, limit=1)["log"])
    assert ids(p1["items"]) + ids(p2["items"]) == [f"urn:x:{i}" for i in range(9, 1, -1)]
    tail = walk(cfg, limit=4)
    assert len(tail) == 13 and len({i["offset"] for i in tail}) == 13  # no line twice, none missing


def test_cursor_on_a_replaced_or_truncated_log_is_refused(repo):
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 6)
    cur = ok(cfg, limit=2)["nextCursor"]
    path = log_path(repo)
    with open(path, "rb") as f:
        data = f.read()
    with open(path, "r+b") as f:  # same inode, shorter than the cursor's offset
        f.truncate(len(data) // 4)
    e = read(cfg, cursor=cur).structured_content["error"]
    assert e["code"] == "INVALID_ARGUMENT" and e["details"] == {"rejectedFields": ["cursor"], "reason": "log-truncated"}
    os.replace(path, path + ".old")
    with open(path + ".new", "wb") as f:
        f.write(data)
    os.replace(path + ".new", path)  # same bytes, another inode
    e = read(cfg, cursor=cur).structured_content["error"]
    assert e["details"] == {"rejectedFields": ["cursor"], "reason": "log-replaced"}
    for bad in ("cl1.e30", "not-a-cursor", "cl1.!!"):
        e = read(cfg, cursor=bad).structured_content["error"]
        assert e["code"] == "INVALID_ARGUMENT" and e["details"]["rejectedFields"] == ["cursor"]


# ---------------------------------------------------------------- 5: bad lines are counted, never returned

def test_malformed_and_unknown_version_lines_are_counted(repo):
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 1)
    with open(log_path(repo), "ab") as f:
        f.write(b"not json at all\n")
        f.write(json.dumps({"v": 99, "measured": {"tool": "model_remove"}}).encode() + b"\n")
        f.write(json.dumps({"v": True, "measured": {}}).encode() + b"\n")   # true is not 1
        f.write(json.dumps({"v": 1, "measured": "x"}).encode() + b"\n")    # v1 without a measured object
        f.write(b'{"v": 1, "measured": {"durationMs": NaN}}\n')            # not JSON (NaN)
        f.write(b'{"v": 1, "measured": {"x": ' + b"[" * 100000 + b"]" * 100000 + b"}}\n")  # json.loads: RecursionError
        f.write(b'{"v": 1, "measured": {"tool": "\\ud800"}}\n')            # lone surrogate: not encodable as UTF-8
    refused(cfg, 1)
    with open(log_path(repo), "ab") as f:
        f.write(b'{"v": 1, "measured": {"tool"')  # a line still being written: no newline yet, not read
    r = read(cfg)
    assert not r.is_error, r.content[0].text
    r.model_dump_json()  # the whole page must still go out on the wire
    p = r.structured_content
    assert ids(p["items"]) == ["urn:x:0", "urn:x:0"]
    assert p["skipped"] == {"malformed": 5, "unknownVersion": 2}


def test_unhashable_tool_field_does_not_break_a_filtered_read(repo):
    """A v1 line whose measured.tool is not a string (a list: unhashable) is skipped by the tools filter, not an
    INTERNAL error for the whole page."""
    cfg = tools.Config(repo=str(repo))
    refused(cfg, 1)
    with open(log_path(repo), "ab") as f:
        f.write(json.dumps({"v": 1, "measured": {"tool": ["model_remove"]}}).encode() + b"\n")
        f.write(json.dumps({"v": 1, "measured": {"tool": {"x": 1}}}).encode() + b"\n")
    assert len(ok(cfg)["items"]) == 3
    assert ok(cfg, tools=["model_remove"])["items"] == []
    assert ids(ok(cfg, tools=["model_set_labels"])["items"]) == ["urn:x:0"]


# ---------------------------------------------------------------- 6: the sentinel label reaches neither log nor output

def test_sentinel_label_is_in_neither_the_log_nor_the_reader_output(wrepo):
    async def go():
        p = StdioServerParameters(command=PY, args=["-m", "aisep.server", "--repo", str(wrepo), "--allow-root",
                                                    str(wrepo.parent), "--profile", "all"],
                                  cwd=str(wrepo), env=dict(os.environ, PYTHONPATH=ROOT))
        async with Client(p) as c:
            a = await c.call_tool("model_add_element", {
                "model": WB, "type": "aisep:AcceptanceCriterion", "prefLabel": SENT, "altLabel": SENT + " en",
                "definition": SENT + "定义", "slug": "acSentinel",
                "attributes": [{"predicate": "aisep:gherkin", "value": {"value": f"Given {SENT}\nWhen b\nThen c"}}]})
            b = await c.call_tool("model_apply_action", {"action": REGISTER, "params": dict(P0, prefLabel=SENT), "dryRun": True})
            assert not a.is_error and not b.is_error, (a.content[0].text, b.content[0].text)
            return await c.call_tool("model_call_log", {})
    r = anyio.run(go)
    assert not r.is_error and len(r.structured_content["items"]) == 2
    assert {i["measured"]["outcome"] for i in r.structured_content["items"]} == {"ok"}
    with open(log_path(wrepo), "rb") as f:
        assert SENT.encode() not in f.read()
    out = r.model_dump_json() + json.dumps(r.structured_content, ensure_ascii=False)
    assert SENT not in out and SENT.encode("unicode_escape").decode() not in out


# ---------------------------------------------------------------- 7: every filter, alone and combined

T = "2026-11-27T08:0{}:00.000Z"
ROWS = [  # (tool, outcome, model, actionId, branch)
    ("model_add_element", "ok", "procurement", None, "main"),
    ("model_apply_action", "PRECONDITION_FAILED", None, "register-acceptance-criterion", "feat/a"),
    ("model_apply_action", "ok", None, "remove-element", "feat/a"),
    ("governance_record_approval", "UNKNOWN_TOOL", None, None, None),
    ("model_set_labels", "INVALID_ARGUMENT", "workbench", None, "main"),
    ("model_add_element", "ok", "workbench", None, "feat/b"),
]


def _seed(cfg):
    for n, (tool, outcome, model, aid, branch) in enumerate(ROWS):
        calllog.append(cfg, {"v": 1, "measured": {
            "time": T.format(n), "tool": tool, "outcome": outcome,
            "request": {"iris": [f"urn:row:{n}"], "model": model, "actionId": aid},
            "target": None if branch is None else {"worktree": "/w", "branch": branch, "head": "0" * 40}}, "declared": {}})


CASES = [
    ({"tools": ["model_apply_action"]}, [2, 1]),
    ({"tools": ["model_add_element", "model_set_labels"]}, [5, 4, 0]),
    ({"outcome": "ok"}, [5, 2, 0]),
    ({"outcome": "rejected"}, [4, 3, 1]),
    ({"outcome": "PRECONDITION_FAILED"}, [1]),
    ({"outcome": "UNKNOWN_TOOL"}, [3]),
    ({"model": "workbench"}, [5, 4]),
    ({"actionId": "remove-element"}, [2]),
    ({"branch": "feat/a"}, [2, 1]),
    ({"since": "2026-11-27T08:02:00Z"}, [5, 4, 3, 2]),
    ({"until": "2026-11-27T16:02:00+08:00"}, [1, 0]),                     # right-open; any offset
    ({"since": "2026-11-27T08:02:00Z", "until": "2026-11-27T08:04:00Z"}, [3, 2]),
    ({"tools": ["model_add_element"], "outcome": "ok", "model": "workbench"}, [5]),
    ({"branch": "main", "outcome": "rejected"}, [4]),
]


def test_each_filter_alone_and_combined(repo):
    cfg = tools.Config(repo=str(repo))
    _seed(cfg)
    assert ids(ok(cfg)["items"]) == [f"urn:row:{n}" for n in (5, 4, 3, 2, 1, 0)]
    for args, want in CASES:
        assert ids(ok(cfg, **args)["items"]) == [f"urn:row:{n}" for n in want], args
        assert ids(walk(cfg, limit=1, **args)) == [f"urn:row:{n}" for n in want], args  # filters hold across pages


def test_bad_arguments_are_refused(repo):
    cfg = tools.Config(repo=str(repo))
    for args, field in [({"limit": 0}, "limit"), ({"limit": 201}, "limit"), ({"outcome": "nope"}, "outcome"),
                        ({"tools": ["model_query"]}, "tools"), ({"since": "2026-11-27"}, "since"),
                        ({"until": "yesterday"}, "until"), ({"repo": str(repo)}, "repo")]:
        e = read(cfg, **args).structured_content["error"]
        assert e["code"] == "INVALID_ARGUMENT" and field in e["details"]["rejectedFields"], (args, e)
    assert not os.path.exists(os.path.dirname(log_path(repo)))  # refusing wrote nothing
    assert git(repo, "status", "--porcelain") == ""
