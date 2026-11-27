"""AISEP MCP server (docs/mcp-interface.md §3, §4, §7): one program, two transports.

    python -m aisep.server --transport stdio|http [--profile agent|workbench|all] [--allow-root DIR ...]
                           [--repo DIR] [--main-branch NAME] [--host 127.0.0.1] [--port 8765] [--allow-origin ORIGIN ...]

Every tool is a plain function of aisep.tools / aisep.diff / aisep.write_tools; this module only lists them, validates
the arguments against their inputSchema (additionalProperties: false), runs them and turns AisepError into a tool
execution error (isError + structuredContent.error, §7.1). The server keeps no state between calls (§3.5); the only
record outside the files is the call log of the audited tools (aisep.calllog, ADR-031), written from on_call_tool."""
import argparse, io, json, os, re, sys, traceback

import anyio
import jsonschema
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import CLIENT_INFO_META_KEY
from mcp_types.jsonrpc import INVALID_PARAMS

from aisep import actions, approval, branches, calllog, diff, tools, write_tools
from aisep.errors import ACTION_CODES, CODES, AisepError

MAX_TEXT_LINES = 200
QUERY_TIMEOUT_MAX = 60000  # ms; a query thread that times out is not killed, so the wait is bounded here
_LINE_BREAKING = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
LOOPBACK_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
CORS_HEADERS = "Content-Type, Accept, MCP-Protocol-Version, Mcp-Method, Mcp-Name"

# ---------------------------------------------------------------- schemas

S = lambda **kw: {"type": "string", **kw}
B = {"type": "boolean"}
REPO = S(description="仓库内任意路径（主 checkout 或 worktree）；缺省取服务器的 --repo")
REF = S(description="分支、标签或 commit；不传则读工作区（含未提交改动）")
MODEL = S(description="模型 IRI 或 slug，如 procurement")
# pattern stays ECMA-262 ($, not \Z); jsonschema runs it with Python re.search, where $ also matches before a
# trailing newline, so maxLength closes that (#77)
SHA40 = S(pattern="^[0-9a-f]{40}$", maxLength=40)


def obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


READ_IN = obj({"repo": REPO, "ref": REF, "model": MODEL})
def error_out(codes):
    return obj({"error": obj({"code": S(enum=sorted(codes)), "message": S(), "hint": S(), "retryable": B,
                              "details": {"type": "object"}}, ["code", "message", "retryable"])}, ["error"])


def out(*required, codes=CODES - ACTION_CODES):
    """outputSchema = success ∪ error (§5.0): a success result has these keys (an error result has only `error`).
    The codes only model_apply_action raises (errors.ACTION_CODES) are in its enum alone."""
    return {"type": "object", "oneOf": [{"type": "object", "required": list(required)}, error_out(codes)]}


ANN_READ = dict(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
ANN_ADD = dict(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
ANN_DESTRUCTIVE = dict(read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False)
# §4: it runs the repository's own pre-commit hook, which may reach outside
ANN_APPROVAL = dict(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True)

TOOLS = {  # name: (function, description, inputSchema, outputSchema, annotations, profiles)
    "model_check": (tools.model_check, "L0–L2 快速诊断（不是门禁结论）", READ_IN,
                    out("partial", "summary", "findings", "source"), ANN_READ, {"agent"}),
    "model_validate": (tools.model_validate, "L0 + L3（SHACL）诊断", READ_IN,
                       out("partial", "summary", "findings", "source"), ANN_READ, {"agent"}),
    "model_findings": (tools.model_findings, "L4 提示 + 当前全部 L0–L2 遗留违规（openViolations）", READ_IN,
                       out("partial", "summary", "findings", "source", "openViolations"), ANN_READ, {"agent", "workbench"}),
    "model_gate": (tools.model_gate, "L0–L4 门禁（提交与 CI 只认它）；FAIL 是正常结果", READ_IN,
                   out("result", "summary", "findings", "source"), ANN_READ, {"agent", "workbench"}),
    "model_query": (tools.model_query, "只读 SPARQL（SELECT/ASK/CONSTRUCT/DESCRIBE，拒绝 SERVICE）",
                    obj({"sparql": S(), "limit": {"type": "integer", "minimum": 1, "maximum": tools.QUERY_LIMIT_MAX},
                         "timeoutMs": {"type": "integer", "minimum": 1, "maximum": QUERY_TIMEOUT_MAX}, "allowPartial": B, "repo": REPO, "ref": REF},
                        ["sparql"]), out("kind", "source"), ANN_READ, {"agent", "workbench"}),
    "model_impact": (tools.model_impact, "影响面：沿依赖方向（depends）或双向（ripple）逐跳展开",
                     obj({"focus": S(), "mode": S(enum=["depends", "ripple"]),
                          "depth": {"type": "integer", "minimum": 1, "maximum": 10}, "allowInvalid": B,
                          "repo": REPO, "ref": REF}, ["focus"]),
                     out("focus", "items", "source"), ANN_READ, {"agent", "workbench"}),
    "model_diff": (diff.model_diff, "模型语义差异：head 为 Git 引用（只比已提交）或 {worktree: 分支名}（含未提交）",
                   obj({"head": {"oneOf": [S(), obj({"worktree": S()}, ["worktree"])]}, "base": S(), "mainRef": S(),
                        "detail": S(enum=["summary", "items", "triples"]), "model": MODEL, "repo": REPO}, ["head"]),
                   out("base", "head", "counts"), ANN_READ, {"agent", "workbench"}),
    "model_branches": (branches.model_branches, "本地分支及其 Git 事实（远端头、是否未推送、是否已合入主分支、是否改了模型）；不 fetch",
                       obj({"repo": REPO}), out("branches", "main"), ANN_READ, {"workbench"}),
    "model_add_element": (write_tools.model_add_element, "新增元素（写工作区，不提交；只拒绝新增违规）",
                          obj({"model": MODEL, "type": S(), "prefLabel": S(), "altLabel": S(), "slug": S(),
                               "definition": S(), "attributes": {"type": "array", "items": obj(
                                   {"predicate": S(), "value": {"type": "object"}}, ["predicate", "value"])},
                               "file": S(), "dryRun": B, "repo": REPO}, ["model", "type", "prefLabel"]),
                          out("iri", "changed"), ANN_ADD, {"agent"}),
    "model_add_relationship": (write_tools.model_add_relationship, "新增限定关系（不写直连三元组）",
                               obj({"type": S(), "source": S(), "target": S(), "model": MODEL, "file": S(),
                                    "dryRun": B, "repo": REPO}, ["type", "source", "target"]),
                               out("iri", "changed"), ANN_ADD, {"agent"}),
    "model_set_labels": (write_tools.model_set_labels, "改名称、英文名、定义（不动 IRI）；null 表示删除",
                         obj({"iri": S(), "prefLabel": S(), "altLabel": {"type": ["string", "null"]},
                              "definition": {"type": ["string", "null"]}, "dryRun": B, "repo": REPO}, ["iri"]),
                         out("iri", "changed"), ANN_DESTRUCTIVE, {"agent"}),
    "model_set_attributes": (write_tools.model_set_attributes,
                             "改已存在元素或关系的属性：set 按谓词整体替换该谓词的全部值，unset 删除该谓词的全部值"
                             "（类型、所属模型、关系端点不能改；名称、英文名、定义用 model_set_labels）",
                             obj({"iri": S(), "set": {"type": "array", "items": obj(
                                 {"predicate": S(), "value": {"type": "object"}}, ["predicate", "value"])},
                                  "unset": {"type": "array", "items": S()}, "dryRun": B, "repo": REPO}, ["iri"]),
                             out("iri", "changed"), ANN_DESTRUCTIVE, {"agent"}),
    "model_remove": (write_tools.model_remove, "删除元素/关系/视图；牵连时返回计划，需 cascade + planDigest",
                     obj({"iri": S(), "cascade": B, "dryRun": B, "planDigest": S(), "repo": REPO}, ["iri"]),
                     out("target", "planDigest"), ANN_DESTRUCTIVE, {"agent"}),
    # the two tools are fixed; what the catalogue (modules/ext-actions/catalog.ttl) holds never changes tools/list
    "model_list_actions": (actions.model_list_actions, "动作目录（只读）：每个动作的参数 schema、步骤、前置检查提示",
                           obj({}), out("actions"), ANN_READ, {"agent"}),
    "model_apply_action": (actions.model_apply_action,
                           "执行目录里的一个动作（一次写入，全有或全无，不提交）；含删除步骤的动作须先 dryRun 再带 planDigest",
                           obj({"action": S(), "params": {"type": "object"}, "dryRun": B, "planDigest": S(),
                                "repo": REPO}, ["action"]),
                           out("action", "changed", codes=CODES), ANN_DESTRUCTIVE, {"agent"}),
    # ADR-031 as amended: the call log, read-only, workbench only (the profile is no security boundary, §4)
    "model_call_log": (calllog.model_call_log,
                       "读本机服务端调用日志（只读，新的在前；只含哈希与标识符；诊断用、不防篡改）",
                       obj({"limit": {"type": "integer", "minimum": 1, "maximum": calllog.PAGE_MAX}, "cursor": S(),
                            "tools": {"type": "array", "items": S(enum=sorted(calllog.AUDITED))},
                            "outcome": S(enum=sorted({"ok", "rejected", calllog.UNKNOWN_TOOL} | CODES)),
                            "model": S(), "actionId": S(), "branch": S(),
                            "since": S(description="RFC 3339，含"), "until": S(description="RFC 3339，不含")}),
                       out("log", "items", "skipped", "nextCursor"), ANN_READ, {"workbench"}),
    "governance_record_approval": (
        approval.governance_record_approval,
        "记录一次关口批准：在 branch 检出的工作区新建一个记录文件并提交一次（evidence=headCommit，时间与 baseCommit 由服务器给）",
        obj({"model": MODEL, "gate": S(enum=["GateRequirements", "GateArchitecture", "GateDesign", "GateMerge", "GateRelease"]),
             "decision": S(enum=["Approved", "Rejected"]), "approvedBy": S(),
             "approves": {"type": "array", "items": S(), "minItems": 1}, "branch": S(),
             "headCommit": SHA40, "expectedBaseCommit": SHA40, "slug": S(),
             "prefLabel": S(), "activity": obj({"agent": S(), "sessionRef": S(), "startedAt": S(), "endedAt": S(),
                                                "branch": S(), "label": S()}, ["agent", "sessionRef", "startedAt"]),
             "mainRef": S(), "repo": REPO},
            ["model", "gate", "decision", "approvedBy", "approves", "branch", "headCommit"]),
        out("approval", "commit", "duplicate"), ANN_APPROVAL, {"workbench"}),
}
PROFILES = {"agent": "agent", "workbench": "workbench", "all": None}


def listed(profile):
    want = PROFILES[profile]
    return [n for n, t in TOOLS.items() if want is None or want in t[5]]


# ---------------------------------------------------------------- argument validation (§3.1: the SDK does not)

def _rejected(err, acc):
    if err.validator == "additionalProperties" and isinstance(err.instance, dict):
        acc.update(set(err.instance) - set(err.schema.get("properties", {})))
    elif err.validator == "required":
        acc.update(n for n in err.validator_value if n not in (err.instance or {}))
    elif err.context:
        for sub in err.context:
            _rejected(sub, acc)
    elif err.absolute_path:
        acc.add(str(err.absolute_path[0]))
    return acc


def validate_args(name, args):
    schema = TOOLS[name][2]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(args))
    if errors:
        fields = set()
        for e in errors:
            _rejected(e, fields)
        raise AisepError("INVALID_ARGUMENT", f"{name} 的参数不合规：{errors[0].message[:200]}",
                         hint="按 inputSchema 修改参数", details={"rejectedFields": sorted(fields)})


# ---------------------------------------------------------------- results (§5.0, §7.1)

def one_line(s):
    """Model text (labels, literals, IRIs) reaches the text content inside finding messages; escape every control and
    line-separator character so it can never start a line of its own (e.g. a forged "gate PASS", SEC-7). The structured
    content keeps the original text."""
    return _LINE_BREAKING.sub(lambda m: {"\n": "\\n", "\r": "\\r", "\t": "\\t"}.get(m.group(), f"\\u{ord(m.group()):04x}"),
                              str(s))


def _finding_lines(fs):
    return [one_line(f"[{f['severity']}] {f['layer']} {f['message']}") for f in fs]


def summary_text(name, res):
    head = {"model_gate": lambda r: f"gate {r['result']}：违规 {r['summary']['violations']}，警告 {r['summary']['warnings']}",
            "model_diff": lambda r: f"改动元素 {r['changedElementCount']}（触及 {r['touchedElementCount']}）"
                                    + ("，含未提交" if r["head"].get("dirty") else "")
                                    + ("，部分文件解析失败" if r.get("incomplete") else ""),
            "model_impact": lambda r: f"影响面 {len(r['items'])} 个元素" + ("（模型不合法）" if r.get("invalidModel") else ""),
            "model_query": lambda r: f"查询结果：{r['kind']}",
            "model_call_log": lambda r: f"调用日志 {len(r['items'])} 条" + ("，还有更早的" if r["nextCursor"] else "")
                                        + (f"，跳过坏行 {r['skipped']['malformed']}、未知版本 {r['skipped']['unknownVersion']}"
                                           if any(r["skipped"].values()) else ""),
            "model_branches": lambda r: f"分支 {len(r['branches'])} 个，改了模型且未合入 "
                                        f"{sum(b['hasModelChanges'] and not b['mergedIntoMain'] for b in r['branches'])} 个"}.get(name)
    if head is None:
        head = lambda r: f"{name} 完成" + (f"：{r['iri']}" if "iri" in r else "") + \
            ("（无变化）" if r.get("changed") is False else "")
    lines = [one_line(head(res))] + _finding_lines(res.get("findings", []))
    if len(lines) > MAX_TEXT_LINES:
        lines = lines[:MAX_TEXT_LINES] + [f"……其余 {len(lines) - MAX_TEXT_LINES} 行见 structuredContent"]
    return "\n".join(lines)


def error_result(e):
    text = one_line(e.message) + (f"\n提示：{one_line(e.hint)}" if e.hint else "")
    fs = e.details.get("findings") if isinstance(e.details, dict) else None
    if fs:
        text += "\n" + "\n".join(_finding_lines(fs)[:MAX_TEXT_LINES])
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                structured_content={"error": e.to_dict()}, is_error=True)


def call(cfg, name, args):
    """Run one tool call synchronously; never raises for anything but an unknown tool (a protocol error)."""
    try:
        validate_args(name, args)
        if os.environ.get("AISEP_MCP_FAULT") == name:  # test hook (T34): an uncaught exception inside a tool
            raise RuntimeError("injected fault")
        res = TOOLS[name][0](cfg, **args)
        res = json.loads(json.dumps(res, ensure_ascii=False))  # plain JSON (no tuples or other Python-only values)
        return types.CallToolResult(content=[types.TextContent(type="text", text=summary_text(name, res))],
                                    structured_content=res, is_error=False)
    except AisepError as e:
        return error_result(e)
    except Exception as e:  # noqa: BLE001 — §3.1: anything else is INTERNAL with a stderr summary, never a bare -32603
        print(f"[aisep-mcp] INTERNAL in {name}: {e!r}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return error_result(AisepError("INTERNAL", f"服务器内部错误：{type(e).__name__}: {str(e)[:300]}"))


def logged_call(cfg, run, name, args, client_info=None):
    """call() plus one call-log line for an audited tool (ADR-031); the log never changes the result."""
    if name not in calllog.AUDITED:
        return call(cfg, name, args)
    t0 = calllog.begin()
    res = call(cfg, name, args)
    _log(cfg, run, name, args, t0, res.structured_content["error"]["code"] if res.is_error else "ok",
         res.structured_content, client_info)
    return res


def _log(cfg, run, name, args, t0, outcome, result, client_info):
    try:
        rec = calllog.record(run, name, args, t0, outcome, result, client_info)
    except Exception as e:  # noqa: BLE001 — fail-open (ADR-031 decision 5)
        return calllog.warn(f"组装记录失败：{e!r}")
    calllog.append(cfg, rec)


def _unknown(cfg, run, name, args, client_info):
    _log(cfg, run, name, args, calllog.begin(), calllog.UNKNOWN_TOOL, None, client_info)


def _client_info(ctx, params):
    """Caller-declared clientInfo: from `initialize` (stdio), else from the request's params._meta (HTTP has no
    initialize; MCP SDK CLIENT_INFO_META_KEY). Best effort: a declared field never decides anything."""
    try:
        cp = ctx.session.client_params
        if cp is not None and cp.client_info is not None:
            return cp.client_info.model_dump(mode="json", by_alias=True, exclude_none=True)
        meta = params.meta
        return meta.get(CLIENT_INFO_META_KEY) if isinstance(meta, dict) else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- the MCP server

def build_server(cfg, profile="all", transport="stdio"):
    names = listed(profile)
    run = {"pid": os.getpid(), "profile": profile, "transport": transport, "allowRoots": list(cfg.allow_roots),
           "repo": cfg.repo}
    tool_list = [types.Tool(name=n, description=TOOLS[n][1], input_schema=TOOLS[n][2], output_schema=TOOLS[n][3],
                            annotations=types.ToolAnnotations(**TOOLS[n][4])) for n in names]

    async def on_list_tools(ctx, params):
        return types.ListToolsResult(tools=tool_list)

    async def on_call_tool(ctx, params):
        args, name = dict(params.arguments or {}), params.name
        if name not in names:
            if name in calllog.AUDITED:  # an audited name outside this profile: logged as UNKNOWN_TOOL
                await anyio.to_thread.run_sync(_unknown, cfg, run, name, args, _client_info(ctx, params))
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {name}")
        return await anyio.to_thread.run_sync(logged_call, cfg, run, name, args, _client_info(ctx, params))

    return Server("aisep", version="0.1.0", instructions="AISEP 架构模型仓库的 MCP 服务器（docs/mcp-interface.md）",
                  on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _started():  # test hook (T5): runs after the stdout diversion, before the SDK takes the streams
    pass


def run_stdio(server):
    """§3.1: keep the real fd 1 as the JSON-RPC wire and point fd 1 at stderr BEFORE the SDK starts, so a stray print
    or a C-level write anywhere (also outside a tool call) lands on stderr, never in the protocol stream."""
    wire_out, wire_in = os.dup(1), os.dup(0)
    os.dup2(2, 1)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    _started()

    async def main():
        stdin = anyio.wrap_file(io.TextIOWrapper(os.fdopen(wire_in, "rb"), encoding="utf-8", errors="replace"))
        stdout = anyio.wrap_file(io.TextIOWrapper(os.fdopen(wire_out, "wb"), encoding="utf-8", write_through=True))
        async with stdio_server(stdin, stdout) as (read, write):
            await server.run(read, write, server.create_initialization_options())
    anyio.run(main)


class OriginGate:
    """§3.2 security: a request with an Origin outside the allow-list -> 403 (preflight included; never `*` or `null`).
    Allowed origins get CORS headers and their OPTIONS preflight is answered here. No Origin (curl, local processes)
    passes; Host is checked by the SDK's DNS-rebinding protection (loopback only)."""

    def __init__(self, app, origins):
        self.app, self.origins = app, set(origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        origin = headers.get("origin")
        if origin is not None and origin not in self.origins:
            await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"text/plain")]})
            return await send({"type": "http.response.body", "body": b"Origin not allowed"})
        cors = [(b"access-control-allow-origin", origin.encode()), (b"vary", b"Origin")] if origin else []
        if scope["method"] == "OPTIONS" and origin:
            await send({"type": "http.response.start", "status": 204, "headers": cors + [
                (b"access-control-allow-methods", b"POST, GET, DELETE, OPTIONS"),
                (b"access-control-allow-headers", CORS_HEADERS.encode()), (b"access-control-max-age", b"600")]})
            return await send({"type": "http.response.body", "body": b""})

        async def send_cors(msg):
            if msg["type"] == "http.response.start" and cors:
                msg = dict(msg, headers=list(msg.get("headers", [])) + cors)
            await send(msg)
        return await self.app(scope, receive, send_cors)


def http_app(server, origins, host="127.0.0.1"):
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=LOOPBACK_HOSTS,
                                         allowed_origins=sorted(origins))
    return OriginGate(server.streamable_http_app(stateless_http=True, json_response=True,
                                                 transport_security=security, host=host), origins)


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="aisep-mcp")
    ap.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="agent")
    ap.add_argument("--allow-root", action="append", default=[])
    ap.add_argument("--repo")
    ap.add_argument("--main-branch", default="main")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--allow-origin", action="append", default=[])
    a = ap.parse_args(argv)
    if a.host not in ("127.0.0.1", "::1", "localhost"):
        ap.error("--host 只能是本机回环地址（§3.2）")
    bad = [o for o in a.allow_origin if o in ("*", "null")]
    if bad:
        ap.error(f"--allow-origin 不能是 {bad}（§3.2）")
    return a


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    cfg = tools.Config(allow_roots=tuple(os.path.realpath(r) for r in a.allow_root), repo=a.repo,
                       main_branch=a.main_branch)
    server = build_server(cfg, a.profile, a.transport)
    if calllog.log_dir(cfg) is None:
        calllog.warn("--allow-root 与 --repo 都不在 Git 仓库里，被审计的调用不会记录")
    if a.transport == "stdio":
        run_stdio(server)
    else:
        import uvicorn
        uvicorn.run(http_app(server, a.allow_origin, a.host), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
