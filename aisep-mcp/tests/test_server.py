"""S7: the MCP shell (docs/mcp-interface.md §3.1, §3.2, §4, §5.0, §7). Acceptance: T1, T2, T4, T5, T30, T34.
Real transports: a stdio subprocess (raw JSON-RPC and the SDK Client), a real uvicorn HTTP server on a free port,
and the official TypeScript SDK v1 client (T34, aisep-mcp/tests/ts, `npm ci` on first use)."""
import glob, hashlib, json, os, re, socket, subprocess, sys, tempfile, textwrap, time

import http.client
from urllib.parse import urlsplit

import anyio
import pytest
from mcp import Client, StdioServerParameters

from conftest import ROOT, commit_all, git
from aisep import server as S

PY = sys.executable
M = "https://aisep.example/model/procurement/"
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}
TS_DIR = os.path.join(ROOT, "aisep-mcp", "tests", "ts")


def server_cmd(repo, *extra):
    return [PY, "-m", "aisep.server", "--repo", str(repo), "--allow-root", str(repo.parent), "--profile", "all", *extra]


def env():
    return dict(os.environ, PYTHONPATH=ROOT)


def stdio_calls(repo, calls, extra_env=None):
    """[(tool, args)] over a fresh stdio server with the SDK Client -> [CallToolResult]."""
    async def go():
        p = StdioServerParameters(command=PY, args=server_cmd(repo)[1:], cwd=str(repo), env=dict(env(), **(extra_env or {})))
        async with Client(p) as c:
            return [await c.call_tool(t, a) for t, a in calls]
    return anyio.run(go)


def tree_digest(repo):
    """sha256 of every file of the worktree and of .git/refs, .git/HEAD, .git/index (T2 read-only check)."""
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(str(repo), "**", "*"), recursive=True)):
        if os.path.isfile(f) and "__pycache__" not in f:
            h.update(f.encode() + open(f, "rb").read())
    gd = git(repo, "rev-parse", "--absolute-git-dir")
    for f in sorted(glob.glob(os.path.join(gd, "refs", "**", "*"), recursive=True)) + [os.path.join(gd, "HEAD"),
                                                                                        os.path.join(gd, "index")]:
        if os.path.isfile(f):
            h.update(f.encode() + open(f, "rb").read())
    return h.hexdigest()


READ_CALLS = [("model_check", {}), ("model_validate", {}), ("model_findings", {}), ("model_gate", {}),
              ("model_query", {"sparql": "SELECT ?x WHERE { ?x a am4:BusinessObject } ORDER BY ?x"}),
              ("model_impact", {"focus": "procurement:quotation"}), ("model_diff", {"head": "main", "detail": "items"}),
              ("model_gate", {"ref": "main"})]


# ---------------------------------------------------------------- T1 / T2

def test_T1_tool_names():
    for profile in S.PROFILES:
        for n in S.listed(profile):
            assert re.fullmatch(r"[a-z_]{1,64}", n) and "." not in n
            assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", "mcp__aisep__" + n)


EXPECTED_ANNOTATIONS = {  # §4 table: (readOnly, destructive, idempotent, openWorld)
    "model_query": (True, None, True, False), "model_check": (True, None, True, False),
    "model_validate": (True, None, True, False), "model_findings": (True, None, True, False),
    "model_gate": (True, None, True, False), "model_impact": (True, None, True, False),
    "model_diff": (True, None, True, False), "model_branches": (True, None, True, False), "model_add_element": (False, False, True, False),
    "model_add_relationship": (False, False, True, False), "model_remove": (False, True, True, False),
    "model_set_labels": (False, True, True, False), "model_set_attributes": (False, True, True, False),
    "governance_record_approval": (False, False, True, True),
    "model_list_actions": (True, None, True, False), "model_apply_action": (False, True, True, False),
    "model_list_views": (True, None, True, False), "model_render_view": (True, None, True, False),
    "model_call_log": (True, None, True, False)}
EXPECTED_PROFILES = {"agent": set(EXPECTED_ANNOTATIONS) - {"governance_record_approval", "model_branches", "model_call_log"},
                     "workbench": {"model_query", "model_findings", "model_gate", "model_impact", "model_diff",
                                   "model_branches", "model_call_log", "governance_record_approval", "model_list_views",
                                   "model_render_view"}}


def test_T2_annotations_profiles_and_readonly_really_reads_only(repo):
    async def listing(profile):
        p = StdioServerParameters(command=PY, args=server_cmd(repo)[1:-2] + ["--profile", profile], cwd=str(repo), env=env())
        async with Client(p) as c:
            return (await c.list_tools()).tools
    tools_all = anyio.run(listing, "all")
    got = {t.name: (t.annotations.read_only_hint, t.annotations.destructive_hint, t.annotations.idempotent_hint,
                    t.annotations.open_world_hint) for t in tools_all}
    assert got == EXPECTED_ANNOTATIONS
    for t in tools_all:
        assert t.input_schema["additionalProperties"] is False and t.output_schema["oneOf"]
    for profile, want in EXPECTED_PROFILES.items():
        assert {t.name for t in anyio.run(listing, profile)} == want
    before = tree_digest(repo)
    res = stdio_calls(repo, READ_CALLS)
    assert all(not r.is_error for r in res), [r.content[0].text for r in res if r.is_error]
    assert tree_digest(repo) == before


# ---------------------------------------------------------------- T4: stateless

def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in sorted(x.items()) if k != "seconds"}
    if isinstance(x, list):
        items = [_norm(v) for v in x]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return x


def test_T4_restart_gives_same_results_and_leaves_nothing(repo, tmp_path):
    private = tmp_path / "server-tmp"  # the server's own TMPDIR: other processes' temp files cannot interfere
    private.mkdir()
    first = [_norm(r.structured_content) for r in stdio_calls(repo, READ_CALLS, {"TMPDIR": str(private)})]   # process 1
    second = [_norm(r.structured_content) for r in stdio_calls(repo, READ_CALLS, {"TMPDIR": str(private)})]  # process 2
    assert first == second
    assert git(repo, "status", "--porcelain") == "" and os.listdir(private) == []


# ---------------------------------------------------------------- T5: stdout carries only JSON-RPC

def test_T5_stdout_is_only_jsonrpc_even_with_stray_prints(repo):
    wrapper = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {ROOT!r})
        from aisep import server, tools
        def started():
            print("LEGACY-PRINT-BEFORE-SDK", flush=True)
            os.write(1, b"C-LEVEL-WRITE-BEFORE-SDK\\n")
        server._started = started
        real = server.TOOLS["model_check"]
        def noisy(cfg, **kw):
            print("LEGACY-PRINT-IN-TOOL", flush=True)
            os.write(1, b"C-LEVEL-WRITE-IN-TOOL\\n")
            return real[0](cfg, **kw)
        server.TOOLS["model_check"] = (noisy,) + real[1:]
        server.main({json.dumps(server_cmd(repo)[3:])})
    """)
    calls = [("model_check", {})] + [(t, a) for t, a in READ_CALLS] + [
        ("model_add_element", {"model": "procurement", "type": "am4:BusinessObject", "prefLabel": "发票", "slug": "invoice",
                               "dryRun": True}),
        ("model_add_relationship", {"type": "am4:Access", "source": "procurement:submitQuotation",
                                    "target": "procurement:quotation"}),
        ("model_set_labels", {"iri": "procurement:supplier", "prefLabel": "供应商"}),
        ("model_remove", {"iri": "procurement:quotation"}), ("no_such_tool", {})]
    lines = "".join(json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                "params": {"name": t, "arguments": a, "_meta": META}}, ensure_ascii=False) + "\n"
                    for i, (t, a) in enumerate(calls, 1))
    p = subprocess.Popen([PY, "-c", wrapper], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, cwd=str(repo))
    p.stdin.write(lines)
    p.stdin.flush()
    msgs = []
    while len(msgs) < len(calls):  # keep stdin open until every response arrived (EOF ends the session)
        line = p.stdout.readline()
        assert line, "server closed stdout early"
        if line.strip():
            msgs.append(json.loads(line))                    # any non-JSON line fails here
    p.stdin.close()
    rest, err = p.stdout.read(), p.stderr.read()
    p.wait(timeout=120)
    assert not rest.strip(), rest                             # nothing else on stdout either
    assert sorted(m["id"] for m in msgs) == list(range(1, len(calls) + 1))
    by_id = {m["id"]: m for m in msgs}
    assert by_id[1]["result"]["isError"] is False             # the noisy call still got its full response
    assert by_id[len(calls)]["error"]["code"] == -32602        # unknown tool: protocol error
    for marker in ("LEGACY-PRINT-BEFORE-SDK", "C-LEVEL-WRITE-BEFORE-SDK", "LEGACY-PRINT-IN-TOOL", "C-LEVEL-WRITE-IN-TOOL"):
        assert marker in err and all(marker not in json.dumps(m) for m in msgs)


# ---------------------------------------------------------------- T30: HTTP

@pytest.fixture
def http_url(repo):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen(server_cmd(repo, "--transport", "http", "--port", str(port), "--allow-origin", "app://renderer",
                                       "--allow-origin", "http://localhost:5173"), cwd=str(repo), env=env(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(200):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    proc.kill()
    proc.wait()


class Resp:
    def __init__(self, status, headers, body):
        self.status_code, self.headers, self.body = status, {k.lower(): v for k, v in headers}, body

    def json(self):
        return json.loads(self.body)


def request(method, url, body=None, headers=None):
    u = urlsplit(url)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=300)
    h = dict(headers or {})
    c.putrequest(method, u.path, skip_host="Host" in h)
    for k, v in h.items():
        c.putheader(k, v)
    data = json.dumps(body).encode() if body is not None else b""
    c.putheader("Content-Length", str(len(data)))
    c.endheaders(data)
    r = c.getresponse()
    out = Resp(r.status, r.getheaders(), r.read().decode())
    c.close()
    return out


def _post(url, body, **headers):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
         "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": body["method"]}
    if body["method"] == "tools/call":
        h["Mcp-Name"] = body["params"]["name"]
    h.update({k.replace("_", "-"): v for k, v in headers.items() if v is not None})
    for k in [k for k, v in headers.items() if v is None]:
        h.pop(k.replace("_", "-"), None)
    return request("POST", url, body, h)


def _call(name, args, meta=META):
    return {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": args, "_meta": meta}}


def test_T30_http_security_and_protocol(http_url):
    http = http_url
    ok = _post(http, _call("model_gate", {}))                       # no initialize, 2026-07-28 envelope
    assert ok.status_code == 200 and ok.json()["result"]["structuredContent"]["result"] == "PASS"
    assert "mcp-session-id" not in {k.lower() for k in ok.headers}
    allowed = _post(http, _call("model_gate", {}), Origin="app://renderer")
    assert allowed.status_code == 200 and allowed.headers["access-control-allow-origin"] == "app://renderer"
    for bad in ("https://evil.example", "null", "file://"):
        assert _post(http, _call("model_gate", {}), Origin=bad).status_code == 403
    assert _post(http, _call("model_gate", {}), Host="evil.example:80").status_code in (400, 403, 421)
    pre = request("OPTIONS", http, headers={"Origin": "app://renderer", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "content-type, mcp-method, mcp-name"})
    assert pre.status_code in (200, 204)
    ah = pre.headers["access-control-allow-headers"]
    assert "Mcp-Method" in ah and "Mcp-Name" in ah and pre.headers["access-control-allow-origin"] == "app://renderer"
    for bad in ("https://evil.example", "null"):
        assert request("OPTIONS", http, headers={"Origin": bad, "Access-Control-Request-Method": "POST"}).status_code == 403
    missing = _post(http, _call("model_gate", {}), Mcp_Name=None)
    assert missing.status_code == 400 or missing.json().get("error", {}).get("code") == -32020
    wrong = _post(http, _call("model_gate", {}, dict(META, **{"io.modelcontextprotocol/protocolVersion": "2025-11-25"})))
    assert wrong.status_code == 400 or "error" in wrong.json()


def test_T30_cli_refuses_wildcards_and_public_hosts(repo):
    for extra in (["--allow-origin", "*"], ["--allow-origin", "null"], ["--host", "0.0.0.0"]):
        p = subprocess.run(server_cmd(repo, "--transport", "http", *extra), capture_output=True, text=True, env=env(), timeout=60)
        assert p.returncode == 2 and "§3.2" in p.stderr


# ---------------------------------------------------------------- T34: TS SDK v1 client and every error shape

def _ts_ready():
    if not os.path.isdir(os.path.join(TS_DIR, "node_modules", "@modelcontextprotocol")):
        p = subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=TS_DIR, capture_output=True, text=True, timeout=600)
        assert p.returncode == 0, "T34 needs the pinned TS SDK: `npm ci` in aisep-mcp/tests/ts failed:\n" + p.stderr[-2000:]


def test_T34_ts_client_receives_every_error_code(repo, tmp_path):
    _ts_ready()
    with open(os.path.join(str(repo), "models/procurement/am4.ttl"), "a", encoding="utf-8") as f:
        f.write('\n_:a skos:related _:b .\n_:b skos:related _:a .\n')  # a committed blank-node cycle for DIFF_BNODE_UNSUPPORTED
    bnode = commit_all(repo, "bnode cycle")
    git(repo, "revert", "--no-edit", "HEAD")
    git(repo, "branch", "parked")
    feat = git(repo, "rev-parse", "parked")
    plain = tmp_path / "plain"
    plain.mkdir()
    foreign = tempfile.mkdtemp(prefix="aisep-t34-outside-")  # a real repository outside --allow-root (= tmp_path)
    subprocess.run(["git", "init", "-q", foreign], check=True)
    cases = [
        ("model_check", {"bogus": 1}, "INVALID_ARGUMENT"),
        ("model_check", {"model": "nope"}, "MODEL_NOT_FOUND"),
        ("model_gate", {"ref": "no-such-ref"}, "REF_NOT_FOUND"),
        ("model_gate", {"repo": str(plain)}, "NOT_A_GIT_REPO"),
        ("model_gate", {"repo": foreign}, "PATH_OUTSIDE_ROOT"),
        ("model_impact", {"focus": "procurement:quotatoin"}, "ELEMENT_NOT_FOUND"),
        ("model_query", {"sparql": "INSERT DATA { <urn:a> <urn:b> <urn:c> }"}, "QUERY_NOT_READONLY"),
        ("model_query", {"sparql": "SELEC x"}, "QUERY_FAILED"),
        ("model_query", {"sparql": "SELECT (COUNT(*) AS ?n) WHERE { ?a ?b ?c . ?d ?e ?f . ?g ?h ?i }", "timeoutMs": 100},
         "QUERY_TIMEOUT"),
        ("model_diff", {"head": {"worktree": "parked"}}, "WORKTREE_NOT_FOUND"),
        ("model_diff", {"head": bnode, "base": "HEAD~2"}, "DIFF_BNODE_UNSUPPORTED"),
        ("model_add_element", {"model": "procurement", "type": "am4:BusinessObjekt", "prefLabel": "x", "slug": "x"}, "UNKNOWN_TYPE"),
        ("model_add_element", {"model": "procurement", "type": "arch:Element", "prefLabel": "x", "slug": "x"}, "ABSTRACT_TYPE"),
        ("model_add_element", {"model": "procurement", "type": "am4:BusinessObject", "prefLabel": "x", "slug": "supplier"}, "IRI_EXISTS"),
        ("model_add_relationship", {"type": "am4:Serving", "source": "procurement:bpmnReview",
                                    "target": "procurement:quoteApproval"}, "WRITE_REJECTED"),
        ("model_set_labels", {"iri": "procurement:approval-20261119-arch-baseline", "prefLabel": "x"}, "PROTECTED_RESOURCE"),
        ("model_remove", {"iri": "procurement:quoteApproval", "cascade": True}, "REFERENCED"),
        ("model_remove", {"iri": "procurement:quotation"}, "CASCADE_REQUIRED"),
        ("model_remove", {"iri": "procurement:quotation", "cascade": True, "planDigest": "sha256:0"}, "PLAN_STALE"),
        ("governance_record_approval", {"model": "procurement", "gate": "GateArchitecture", "decision": "Approved",
                                        "approvedBy": "procurement:chiefArchitect", "approves": ["procurement:supplier"],
                                        "branch": "main", "headCommit": feat}, "INVALID_ARGUMENT"),
        ("governance_record_approval", {"model": "procurement", "gate": "GateArchitecture", "decision": "Approved",
                                        "approvedBy": "procurement:chiefArchitect", "approves": ["procurement:supplier"],
                                        "branch": "parked", "headCommit": feat, "evidence": feat}, "INVALID_ARGUMENT"),
        ("model_findings", {}, "INTERNAL"),  # AISEP_MCP_FAULT below makes this tool raise
    ]
    spec = {"command": PY, "args": server_cmd(repo)[1:], "cwd": str(repo),
            "env": dict(env(), AISEP_MCP_FAULT="model_findings"), "calls": [[t, a] for t, a, _ in cases]}
    p = subprocess.run(["node", os.path.join(TS_DIR, "call_errors.mjs"), json.dumps(spec)], cwd=TS_DIR,
                       capture_output=True, text=True, timeout=900)
    assert p.returncode == 0, p.stderr[-2000:]
    got = [json.loads(l) for l in p.stdout.splitlines()]
    assert [g["threw"] for g in got] == [None] * len(cases), [g for g in got if g["threw"]]
    assert [(g["tool"], g["code"]) for g in got] == [(t, c) for t, _, c in cases]
    assert all(g["isError"] for g in got)


def test_mcp_json_launcher_starts_the_agent_profile(repo):
    """The repository's .mcp.json (what Claude Code starts, §3.2) launches the stdio server on the worktree, agent profile."""
    spec = json.load(open(os.path.join(ROOT, ".mcp.json"), encoding="utf-8"))["mcpServers"]["aisep"]

    async def go():
        p = StdioServerParameters(command=spec["command"], args=spec["args"], cwd=str(repo), env=dict(env(), AISEP_PY=PY))
        async with Client(p) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            gate = await c.call_tool("model_gate", {})
            return names, gate
    names, gate = anyio.run(go)
    assert names == EXPECTED_PROFILES["agent"] and gate.structured_content["result"] == "PASS"
    assert gate.structured_content["source"]["repo"] == os.path.realpath(repo)


@pytest.mark.parametrize("field", ["headCommit", "expectedBaseCommit"])
def test_sha_argument_with_trailing_newline_is_rejected_by_schema(field):
    """#77: jsonschema runs `pattern` with Python re.search, where $ also matches before a trailing newline; the
    inputSchema's maxLength refuses "<40 hex>\\n" before the tool runs."""
    args = {"model": "procurement", "gate": "GateArchitecture", "decision": "Approved", "approvedBy": "x",
            "approves": ["x"], "branch": "feat/x", "headCommit": "a" * 40}
    S.validate_args("governance_record_approval", args)
    with pytest.raises(S.AisepError) as e:
        S.validate_args("governance_record_approval", {**args, field: "a" * 40 + "\n"})
    assert e.value.code == "INVALID_ARGUMENT" and "too long" in e.value.message, e.value.message
