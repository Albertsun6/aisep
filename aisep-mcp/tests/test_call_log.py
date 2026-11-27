"""ADR-031 layer A: the server-side call log (docs/mcp-interface.md §3.6). Exits of issue #170: 1, 2 and 5 go through a
real stdio server (the hook sits in on_call_tool); 3 runs 8 processes over two worktrees; 3a, 3b, 6, 7 call
server.logged_call (what on_call_tool runs) in-process. Exit 8 (the hook removed -> 1 and 2 fail) was checked by hand
(PR description)."""
import hashlib, json, os, shutil, subprocess, sys, textwrap

import anyio
import pytest
from mcp import Client, StdioServerParameters

from conftest import ROOT, commit_all, git, init_repo
from fixtures.topology import M, Topo
from aisep import actions, calllog, server, tools
from test_server import http_url  # noqa: F401 — fixture

PY = sys.executable
WB = "https://aisep.example/model/workbench/"
REQ = WB + "reqApprovalProgress"
AC = WB + "acProgressFourStages"
REGISTER, REMOVE = "register-acceptance-criterion", "remove-element"
P0 = {"requirement": REQ, "prefLabel": "探针验收标准", "altLabel": "Probe criterion",
      "definition": "独立测试用的验收标准。", "gherkin": "Given a\nWhen b\nThen c"}
RUN = {"pid": 0, "profile": "all", "transport": "test", "allowRoots": [], "repo": None}
SENT = "SENTINEL-7f3a"  # a caller-supplied text that must never reach `measured`


@pytest.fixture(scope="session", autouse=True)
def _catalog_from_worktree():
    assert actions.CATALOG_PATH is None


@pytest.fixture(scope="session")
def full(tmp_path_factory):
    """models/ (all models), modules/, vendor/, tools/, aisep/ and .gitignore of the checkout under test."""
    t = tmp_path_factory.mktemp("calllog-template")
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("models", "modules", "vendor", "tools", "aisep"):
        shutil.copytree(os.path.join(ROOT, d), t / d, ignore=ign)
    shutil.copy2(os.path.join(ROOT, ".gitignore"), t / ".gitignore")
    return t


@pytest.fixture
def wrepo(full, tmp_path):
    r = tmp_path / "w"
    shutil.copytree(full, r)
    init_repo(r)
    commit_all(r, "start")
    return r


def log_path(repo):
    return os.path.join(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"), "aisep", calllog.LOG)


def lines(repo):
    p = log_path(repo)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f.read().splitlines()]


def sha_file(repo, rel):
    with open(os.path.join(repo, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def session(repo, profile, steps, allow_root=None):
    """One stdio server; steps: [(tool, args, check)], check(result_or_exception, new_log_lines) runs after each call."""
    async def go():
        p = StdioServerParameters(command=PY, args=["-m", "aisep.server", "--repo", str(repo), "--allow-root",
                                                    str(allow_root or repo.parent), "--profile", profile],
                                  cwd=str(repo), env=dict(os.environ, PYTHONPATH=ROOT))
        async with Client(p) as c:
            for tool, args, check in steps:
                n = len(lines(repo))
                try:
                    res = await c.call_tool(tool, args)
                except Exception as e:  # noqa: BLE001 — an unknown tool is a protocol error
                    res = e
                check(res, lines(repo)[n:])
    anyio.run(go)


def one(outcome, tool):
    def check(res, new):
        assert len(new) == 1, (tool, new)
        assert new[0]["v"] == 1 and new[0]["measured"]["tool"] == tool and new[0]["measured"]["outcome"] == outcome, new[0]
        if outcome != "ok" and outcome != calllog.UNKNOWN_TOOL:
            assert res.is_error and res.structured_content["error"]["code"] == outcome
    return check


def none(res, new):
    assert new == []


# ---------------------------------------------------------------- exit 1: every audited tool, success

def test_exit1_each_audited_write_tool_logs_one_ok_line_with_real_hashes(wrepo):
    state = {}
    snap = {}

    def ok_written(tool, dry=False):
        def check(res, new):
            assert not res.is_error, res.content[0].text
            one("ok", tool)(res, new)
            m = new[0]["measured"]
            assert m["target"] == {"worktree": os.path.realpath(wrepo), "branch": "main", "head": git(wrepo, "rev-parse", "HEAD")}
            assert m["request"]["dryRun"] is dry and m["server"]["profile"] == "all" and m["server"]["transport"] == "stdio"
            assert m["server"]["repo"] == str(wrepo)
            assert new[0]["declared"]["clientInfo"]["name"]  # stdio: from initialize
            if dry:
                assert m["files"] == []
            else:
                assert m["files"], m
                for f in m["files"]:
                    assert f["after"] == "sha256:" + sha_file(wrepo, f["path"])     # after == disk now
                    before = snap.get(f["path"])                                     # before == disk before the call
                    assert f["before"] == (None if before is None else "sha256:" + before)
            sc = res.structured_content
            state.setdefault("iris", []).append(sc.get("iri"))
            state["last"] = new[0]
        return check

    def take():
        for r, _, fs in os.walk(wrepo / "models"):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), wrepo)
                snap[rel] = sha_file(wrepo, rel)

    def step(tool, args, dry=False):
        def check(res, new):
            ok_written(tool, dry)(res, new)
            take()
        return (tool, args, check)

    take()
    X = WB + "acCallLog"
    session(wrepo, "all", [
        step("model_add_element", {"model": WB, "type": "aisep:AcceptanceCriterion", "prefLabel": "探针", "slug": "acCallLog",
                                   "attributes": [{"predicate": "aisep:gherkin", "value": {"value": "Given a\nWhen b\nThen c"}}]}),
        step("model_add_relationship", {"type": "am4:Aggregation", "source": REQ, "target": X}),
        step("model_set_labels", {"iri": X, "prefLabel": "探针二"}),
        step("model_set_attributes", {"iri": X, "set": [{"predicate": "aisep:gherkin",
                                                          "value": {"value": "Given x\nWhen y\nThen z"}}]}),
        step("model_apply_action", {"action": REGISTER, "params": P0, "dryRun": True}, dry=True),
        step("model_apply_action", {"action": REGISTER, "params": P0}),
    ])
    a = state["last"]["measured"]
    r = a["request"]
    assert r["actionId"] == REGISTER and r["actionVersion"] and r["definitionDigest"].startswith("sha256:")
    assert r["definitionDigest"] == next(x["definitionDigest"] for x in actions.model_list_actions(
        tools.Config(repo=str(wrepo)))["actions"] if x["id"] == REGISTER)     # the single action's digest
    assert r["iris"] == [REQ] and r["planDigestGiven"] is False and r["model"] is None
    rel_iri = state["iris"][1]
    session(wrepo, "all", [step("model_remove", {"iri": rel_iri})])
    assert state["last"]["measured"]["request"]["iris"] == [rel_iri]
    # exit 4: the log is in the common dir, outside every graph the model tools load
    sha = state["last"]["measured"]["request"]["argsSha256"].removeprefix("sha256:")
    q = server.call(tools.Config(repo=str(wrepo)), "model_query",
                    {"sparql": f'SELECT ?s WHERE {{ ?s ?p ?o FILTER(CONTAINS(STR(?o), "{sha}") || CONTAINS(STR(?o), "calls.jsonl")) }}'})
    assert not q.is_error and q.structured_content["rows"] == []
    assert "calls" not in git(wrepo, "status", "--porcelain", "--ignored")


def test_exit9_definition_digest_follows_an_edit_of_the_action_definition(wrepo):
    """ADR-031 exit 9, second half: after the action's definition changes, a new line carries the new digest (the one
    model_list_actions now gives), not the old one."""
    cfg = tools.Config(repo=str(wrepo))

    def apply_and_digests():
        r = server.logged_call(cfg, RUN, "model_apply_action", {"action": REGISTER, "params": P0, "dryRun": True})
        assert not r.is_error, r.content[0].text
        listed = next(x["definitionDigest"] for x in actions.model_list_actions(cfg)["actions"] if x["id"] == REGISTER)
        return lines(wrepo)[-1]["measured"]["request"]["definitionDigest"], listed

    before, listed_before = apply_and_digests()
    assert before == listed_before
    cat = wrepo / "modules" / "ext-actions" / "catalog.ttl"
    text = cat.read_text(encoding="utf-8")
    old = '"验收标准的中文名称"@zh'
    assert text.count(old) == 1
    cat.write_text(text.replace(old, '"验收标准的中文名称（改）"@zh'), encoding="utf-8")
    after, listed_after = apply_and_digests()
    assert after == listed_after and after != before


def test_exit1_record_approval_logs_commit_activity_and_file_hash(template, tmp_path):
    t = Topo(template, tmp_path)
    t.checkout("main", new="feat/x")
    h = t.add_element("newThing", "新东西")
    got = {}

    def check(res, new):
        assert not res.is_error, res.content[0].text
        one("ok", "governance_record_approval")(res, new)
        got["line"], got["res"] = new[0], res.structured_content

    args = {"model": "procurement", "gate": "GateArchitecture", "decision": "Approved", "approvedBy": M + "chiefArchitect",
            "approves": [M + "newThing"], "branch": "feat/x", "headCommit": h, "repo": str(t.root),
            "activity": {"agent": M + "codingBot", "sessionRef": "s-calllog", "startedAt": "2026-11-20T09:00:00Z"}}
    session(t.root, "workbench", [("governance_record_approval", args, check)], allow_root=t.tmp)
    m, r = got["line"]["measured"], got["res"]
    assert m["approval"] == {"commit": r["commit"], "activity": r["activity"]["iri"]} and r["commit"] == t.rev("refs/heads/feat/x")
    assert m["target"]["head"] == r["commit"] and m["target"]["branch"] == "feat/x"
    assert m["files"] == [{"path": r["approval"]["file"], "before": None,
                           "after": "sha256:" + sha_file(t.root, r["approval"]["file"])}]
    assert m["request"]["iris"] == [M + "chiefArchitect", M + "newThing"] and m["request"]["model"] == "procurement"
    assert got["line"]["declared"]["activity"] == {"agent": M + "codingBot", "sessionRef": "s-calllog"}


# ---------------------------------------------------------------- exits 2 and 5: refusals; what is not logged

def test_exit2_and_5_refusals_each_log_one_line_reads_and_unknown_names_none(wrepo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "z"
    init_repo(outside)
    (outside / "f").write_text("x")
    commit_all(outside)
    X = WB + "acDoomed"
    session(wrepo, "all", [
        ("model_add_element", {"model": WB, "type": "aisep:AcceptanceCriterion", "prefLabel": "待删", "slug": "acDoomed",
                               "attributes": [{"predicate": "aisep:gherkin", "value": {"value": "Given a\nWhen b\nThen c"}}]},
         one("ok", "model_add_element")),
        ("model_set_labels", {"iri": X, "prefLabel": "x", "bogus": 1}, one("INVALID_ARGUMENT", "model_set_labels")),
        ("model_apply_action", {"action": REGISTER, "params": dict(P0, requirement=AC)},
         one("PRECONDITION_FAILED", "model_apply_action")),
        ("model_apply_action", {"action": REMOVE, "params": {"iri": X}}, one("PLAN_REQUIRED", "model_apply_action")),
        ("model_apply_action", {"action": REMOVE, "params": {"iri": X}, "planDigest": "sha256:" + "0" * 64},
         one("PLAN_STALE", "model_apply_action")),
        ("model_set_labels", {"iri": X, "prefLabel": "x", "repo": str(outside)}, one("PATH_OUTSIDE_ROOT", "model_set_labels")),
        ("model_check", {}, none),                                   # exit 5: a read-only tool
        ("model_list_actions", {}, none),
        ("no_such_tool", {}, none),                                  # exit 5: an unknown name outside the audited set
    ])
    assert lines(wrepo)[-1]["measured"]["target"] is None  # refused before any worktree was located
    assert lines(wrepo)[-1]["measured"]["request"]["repoArg"] == str(outside)
    session(wrepo, "agent", [
        ("governance_record_approval", {"model": "procurement"}, one(calllog.UNKNOWN_TOOL, "governance_record_approval")),
        ("model_query", {"sparql": "ASK { ?s ?p ?o }"}, none),
    ])
    assert not os.path.exists(os.path.join(outside, ".git", "aisep"))


# ---------------------------------------------------------------- exit 3: concurrency over two worktrees

WORKER = textwrap.dedent("""
    import sys, threading
    sys.path.insert(0, sys.argv[2])
    from aisep import server, tools
    root = sys.argv[1]
    cfg = tools.Config(allow_roots=(root,), repo=root)
    run = {"pid": 0, "profile": "agent", "transport": "test", "allowRoots": [root]}
    bar = threading.Barrier(50)
    bad = []
    def go(i):
        bar.wait()
        r = server.logged_call(cfg, run, "model_set_labels", {"iri": "x%d" % i, "bogus": i})
        if not r.is_error:
            bad.append(i)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(50)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    sys.exit(1 if bad else 0)
""")


def test_exit3_eight_processes_two_worktrees_400_whole_lines(repo, tmp_path):
    wt2 = tmp_path / "wt2"
    git(repo, "worktree", "add", "-q", "-b", "side", str(wt2))
    procs = [subprocess.Popen([PY, "-c", WORKER, str(w), ROOT]) for w in (repo, wt2) for _ in range(4)]
    assert [p.wait(timeout=300) for p in procs] == [0] * 8
    got = lines(repo)  # json.loads of every line raises on a torn or interleaved line
    assert len(got) == 400 and lines(wt2) == got
    assert {g["measured"]["outcome"] for g in got} == {"INVALID_ARGUMENT"}
    assert git(repo, "status", "--porcelain") == "" and git(wt2, "status", "--porcelain") == ""  # exit 4


# ---------------------------------------------------------------- exits 3a, 3b: where the log goes

DRY = {"model": "procurement", "type": "am4:BusinessObject", "prefLabel": "探针", "slug": "probe", "dryRun": True}


def test_exit3a_repo_only_logs_there_and_neither_logs_nothing(repo, capfd):
    r = server.logged_call(tools.Config(repo=str(repo)), RUN, "model_add_element", dict(DRY))
    assert not r.is_error and len(lines(repo)) == 1
    os.remove(log_path(repo))
    plain = server.call(tools.Config(), "model_add_element", dict(DRY, repo=str(repo)))
    capfd.readouterr()
    logged = server.logged_call(tools.Config(), RUN, "model_add_element", dict(DRY, repo=str(repo)))
    assert logged.model_dump_json() == plain.model_dump_json()
    assert lines(repo) == [] and "调用日志" in capfd.readouterr().err


def test_exit3b_first_allow_root_wins_over_repo_and_caller_repo(repo, tmp_path_factory):
    y, z = (init_repo(tmp_path_factory.mktemp(n) / "r") for n in ("y", "z"))
    for d in (y, z):
        (d / "f").write_text("x")
        commit_all(d)
    cfg = tools.Config(allow_roots=(os.path.realpath(repo),), repo=str(y))
    r = server.logged_call(cfg, RUN, "model_set_labels", {"iri": "procurement:supplier", "prefLabel": "x", "repo": str(z)})
    assert r.structured_content["error"]["code"] == "PATH_OUTSIDE_ROOT"
    assert len(lines(repo)) == 1 and lines(y) == [] and lines(z) == []
    assert not os.path.exists(os.path.join(y, ".git", "aisep")) and not os.path.exists(os.path.join(z, ".git", "aisep"))


# ---------------------------------------------------------------- exit 6: fail-open

def test_exit6_unwritable_log_dir_keeps_the_result_byte_for_byte(repo, capfd):
    cfg = tools.Config(repo=str(repo))
    d = os.path.dirname(log_path(repo))
    os.makedirs(d)
    os.chmod(d, 0o555)
    try:
        plain = server.call(cfg, "model_add_element", dict(DRY))
        capfd.readouterr()
        logged = server.logged_call(cfg, RUN, "model_add_element", dict(DRY))
        assert logged.model_dump_json() == plain.model_dump_json()
        assert "调用日志" in capfd.readouterr().err and lines(repo) == []
    finally:
        os.chmod(d, 0o755)


# ---------------------------------------------------------------- exit 7: declared stays declared

def test_exit7_caller_values_only_under_declared(repo):
    cfg = tools.Config(repo=str(repo))
    server.logged_call(cfg, RUN, "governance_record_approval", {
        "model": "procurement", "gate": "GateArchitecture", "decision": "Approved", "approvedBy": M + "chiefArchitect",
        "approves": [M + "supplier"], "branch": "main", "headCommit": git(repo, "rev-parse", "HEAD"), "prefLabel": SENT + "-label",
        "activity": {"agent": SENT + "-agent", "sessionRef": SENT + "-session", "startedAt": "2026-11-20T09:00:00Z"}},
        client_info={"name": SENT + "-client", "version": "1"})
    server.logged_call(cfg, RUN, "model_add_element", dict(DRY, prefLabel=SENT + "-label", definition=SENT + "-def"))
    a, b = lines(repo)
    assert a["declared"] == {"clientInfo": {"name": SENT + "-client", "version": "1"},
                             "activity": {"agent": SENT + "-agent", "sessionRef": SENT + "-session"}}
    for x in (a, b):
        assert SENT not in json.dumps(x["measured"], ensure_ascii=False)


def test_http_client_info_comes_from_params_meta(repo, http_url):
    from test_server import META, _call, _post
    meta = dict(META, **{"io.modelcontextprotocol/clientInfo": {"name": SENT + "-http", "version": "2"}})
    r = _post(http_url, _call("model_set_labels", {"iri": "procurement:supplier", "bogus": 1}, meta))
    assert r.status_code == 200 and r.json()["result"]["isError"]
    (line,) = lines(repo)
    assert line["declared"]["clientInfo"]["name"] == SENT + "-http" and line["measured"]["server"]["transport"] == "http"
    assert line["measured"]["outcome"] == "INVALID_ARGUMENT"
