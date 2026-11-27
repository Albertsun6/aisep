"""Server-side call log (ADR-031 layer A; docs/mcp-interface.md §3.6 调用日志) and its read-only reader
model_call_log (§5.15, workbench profile only).

One JSON line per audited call (the write tools, model_apply_action, governance_record_approval; success and refusal
alike) appended to <git-common-dir>/aisep/calls.jsonl. The location comes from the start-up parameters only: the first
--allow-root when it lies in a Git repository, else --repo; neither -> no log, a warning on stderr. Appends take a
repository-wide flock (<git-common-dir>/aisep/calls.lock) and write one whole line with O_APPEND. Fields are split by
source: `measured` (seen by the server; the structural arguments it received sit under measured.request) and
`declared` (what the caller says; never used for any decision). Every line carries `v` (the line format is a contract:
a format change bumps it). A failure to log only warns on stderr (fail-open). No hash chain, not pushed anywhere, no
rotation: this log is a record of what an honestly running server saw, not tamper-evident."""
import base64, binascii, fcntl, hashlib, json, os, sys, threading, time
from datetime import datetime, timezone

from aisep import gitio
from aisep.errors import AisepError

VERSION = 1
AUDITED = frozenset({"model_add_element", "model_add_relationship", "model_set_labels", "model_set_attributes",
                     "model_remove", "model_apply_action", "governance_record_approval"})
DRY_RUN_TOOLS = AUDITED - {"governance_record_approval"}        # the tools whose inputSchema has dryRun
PLAN_TOOLS = frozenset({"model_remove", "model_apply_action"})  # ... and planDigest
IRI_ARGS = ("iri", "source", "target", "approvedBy")             # string arguments that are IRIs (plus `approves`)
UNKNOWN_TOOL = "UNKNOWN_TOOL"  # a log-only outcome (an audited name the profile does not list), not an error code
LOG, LOCK = "calls.jsonl", "calls.lock"
PAGE_MAX, PAGE_DEFAULT = 200, 50
CURSOR_PREFIX = "cl1."

_local = threading.local()  # the notes of the call running on this thread (tools run one per worker thread)


def note(**kw):
    """What a tool measured while running (worktree, files written, action version, IRI parameters)."""
    notes = getattr(_local, "notes", None)
    if notes is not None:
        notes.update(kw)


def begin():
    _local.notes = {}
    return time.monotonic()


def locate(cfg):
    """(<git-common-dir>/aisep, "allow-root" | "repo") of the first --allow-root, else of --repo, else (None, None)
    (ADR-031 decision 4). Writer and reader use this one rule, so the reader reads what the writer wrote."""
    for src, path in [("allow-root", r) for r in cfg.allow_roots[:1]] + ([("repo", cfg.repo)] if cfg.repo else []):
        common = gitio._common_dir(path) if os.path.isdir(path) else None
        if common:
            return os.path.join(common, "aisep"), src
    return None, None


def log_dir(cfg):
    return locate(cfg)[0]


def warn(msg):
    print(f"[aisep-mcp] 调用日志：{msg}", file=sys.stderr, flush=True)


def _sha(h):
    return None if h is None else "sha256:" + h


def _sha_json(v):
    return _sha(hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest())


def _target(path):
    rc, branch, _ = gitio.git(path, "symbolic-ref", "-q", "--short", "HEAD")
    rc2, head, _ = gitio.git(path, "rev-parse", "--verify", "-q", "HEAD")
    return {"worktree": path, "branch": branch.strip() if rc == 0 else None, "head": head.strip() if rc2 == 0 else None}


def _str(v):
    return v if isinstance(v, str) else None


def _request(name, args, notes, result, known):
    """measured.request: the argument hash plus the structural values the server received (identifiers and booleans
    only; labels, definitions, gherkin and other free text are never copied). A name outside the profile is not
    interpreted: only its hash is kept."""
    if not known:
        return {"argsSha256": _sha_json(args), "model": None, "iris": [], "actionId": None, "actionVersion": None,
                "definitionDigest": None, "dryRun": None, "planDigestGiven": None, "repoArg": None}
    iris = [args[k] for k in IRI_ARGS if isinstance(args.get(k), str)]
    iris += [x for x in args.get("approves") or [] if isinstance(x, str)] if isinstance(args.get("approves"), list) else []
    iris += notes.get("iris", [])                                   # model_apply_action: values of its iriParams
    made = result.get("iri") if isinstance(result, dict) and isinstance(result.get("iri"), str) else None
    if made and made not in iris:                                   # the IRI an add tool minted
        iris.append(made)
    act = notes.get("action") or {}
    return {"argsSha256": _sha_json(args), "model": _str(args.get("model")), "iris": iris,
            "actionId": _str(args.get("action")) if name == "model_apply_action" else None,
            "actionVersion": act.get("version"), "definitionDigest": act.get("definitionDigest"),
            "dryRun": args.get("dryRun") is True if name in DRY_RUN_TOOLS else None,
            "planDigestGiven": "planDigest" in args if name in PLAN_TOOLS else None, "repoArg": _str(args.get("repo"))}


def record(run, name, args, t0, outcome, result=None, client_info=None):
    """The v1 log line of one call. `run` holds the start-up parameters (pid, profile, transport, allowRoots, repo)."""
    notes = getattr(_local, "notes", None) or {}
    _local.notes = None
    known = outcome != UNKNOWN_TOOL
    ok = outcome == "ok" and isinstance(result, dict)
    m = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
         "durationMs": round((time.monotonic() - t0) * 1000), "server": run, "tool": name,
         "request": _request(name, args, notes, result if ok else None, known), "outcome": outcome,
         "target": _target(notes["worktree"]) if notes.get("worktree") else None,
         "files": [{"path": f["path"], "before": _sha(f["sha256Before"]), "after": _sha(f["sha256After"])}
                   for f in notes.get("files", [])]}
    d = {"clientInfo": client_info}
    if name == "governance_record_approval":
        if ok:
            m["approval"] = {"commit": result.get("commit"), "activity": (result.get("activity") or {}).get("iri")}
        act = args.get("activity") if known and isinstance(args.get("activity"), dict) else None
        if act is not None:
            d["activity"] = {"agent": _str(act.get("agent")), "sessionRef": _str(act.get("sessionRef"))}
    return {"v": VERSION, "measured": m, "declared": d}


def append(cfg, rec):
    """One whole line under the repository-wide lock; any failure only warns (fail-open, ADR-031 decision 5)."""
    d = log_dir(cfg)
    if d is None:
        return warn("--allow-root 与 --repo 都不在 Git 仓库里，本次调用不记录")
    try:
        line = (json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        os.makedirs(d, exist_ok=True)
        lk = os.open(os.path.join(d, LOCK), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(lk, fcntl.LOCK_EX)
            fd = os.open(os.path.join(d, LOG), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                if os.write(fd, line) != len(line):
                    raise OSError("short write")
            finally:
                os.close(fd)
        finally:
            os.close(lk)
    except Exception as e:  # noqa: BLE001 — the log must never change a tool result
        warn(f"写入 {d} 失败：{e!r}")


# ---------------------------------------------------------------- reader: model_call_log (§5.15)

def _bad(field, message, **details):
    return AisepError("INVALID_ARGUMENT", message, hint="从第一页重新读（不带 cursor）" if field == "cursor" else None,
                      details={"rejectedFields": [field], **details})


def _cursor_encode(ino, end):
    raw = json.dumps({"ino": ino, "end": end}, separators=(",", ":")).encode()
    return CURSOR_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _cursor_decode(c):
    try:
        assert c.startswith(CURSOR_PREFIX)
        b = c[len(CURSOR_PREFIX):]
        d = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
        ino, end = d["ino"], d["end"]
        assert type(ino) is int and type(end) is int and end >= 0
        return ino, end
    except (AssertionError, ValueError, KeyError, TypeError, binascii.Error):
        raise _bad("cursor", "cursor 不是本工具给出的续页令牌") from None


def _time(s, field):
    try:
        t = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        t = None
    if t is None or t.tzinfo is None:
        if field is None:
            return None
        raise _bad(field, f"{field} 不是带时区的 RFC 3339 时间：{s!r}")
    return t


def _byte_at(f, i):
    f.seek(i)
    return f.read(1)


def _complete_end(f, size, chunk=1 << 16):
    """End of the last whole line (a trailing line without its newline may still be being written: not read)."""
    pos = size
    while pos > 0:
        n = min(chunk, pos)
        f.seek(pos - n)
        i = f.read(n).rfind(b"\n")
        if i >= 0:
            return pos - n + i + 1
        pos -= n
    return 0


def _newest_first(f, end, chunk=1 << 16):
    """(offset, line bytes without the newline) of every line in [0, end), newest first; data[end-1] is a newline."""
    buf, base = b"", end  # buf == data[base:stop], and it ends with a newline
    while buf or base > 0:
        i = buf.rfind(b"\n", 0, len(buf) - 1)
        while i < 0 and base > 0:
            n = min(chunk, base)
            base -= n
            f.seek(base)
            buf = f.read(n) + buf
            i = buf.rfind(b"\n", 0, len(buf) - 1)
        if not buf:
            return
        yield base + i + 1, buf[i + 1:-1]
        buf = buf[:i + 1]


def _reject_constant(c):
    raise ValueError(c)


def _get(o, *keys):
    for k in keys:
        o = o.get(k) if isinstance(o, dict) else None
    return o


def _matches(m, tools, outcome, model, actionId, branch, since, until):
    out = m.get("outcome")
    if tools is not None and m.get("tool") not in tools:
        return False
    if outcome is not None and not (out != "ok" if outcome == "rejected" else out == outcome):
        return False
    if model is not None and _get(m, "request", "model") != model:
        return False
    if actionId is not None and _get(m, "request", "actionId") != actionId:
        return False
    if branch is not None and _get(m, "target", "branch") != branch:
        return False
    if since is not None or until is not None:
        t = _time(m.get("time"), None)
        if t is None or (since is not None and t < since) or (until is not None and t >= until):
            return False
    return True


def model_call_log(cfg, limit=PAGE_DEFAULT, cursor=None, tools=None, outcome=None, model=None, actionId=None,
                   branch=None, since=None, until=None):
    """One page of the call log, newest first. Each item is the log line as written plus its byte `offset`. Lines
    that are not JSON objects (`malformed`) or carry another `v` (`unknownVersion`) are counted, never returned. The
    cursor encodes the file's inode and the offset of the oldest line returned: the log is append-only, so appends
    never shift a later page; a replaced or truncated file rejects the cursor. No state is kept between calls."""
    since_t, until_t = _time(since, "since") if since is not None else None, _time(until, "until") if until is not None else None
    want = None if cursor is None else _cursor_decode(cursor)
    d, src = locate(cfg)
    path = os.path.join(d, LOG) if d else None
    log = {"path": path, "present": False, "sizeBytes": None, "resolvedFrom": src}
    page = {"log": log, "items": [], "skipped": {"malformed": 0, "unknownVersion": 0}, "nextCursor": None}
    try:
        f = open(path, "rb") if path else None
    except FileNotFoundError:
        f = None
    if f is None:
        if want is not None:
            raise _bad("cursor", "调用日志已不存在，续页令牌失效", reason="log-replaced")
        return page
    with f:
        st = os.fstat(f.fileno())
        log.update(present=True, sizeBytes=st.st_size)
        end = _complete_end(f, st.st_size)
        if want is not None:
            if want[0] != st.st_ino:
                raise _bad("cursor", "调用日志文件已被替换，续页令牌失效", reason="log-replaced")
            if want[1] > end or (want[1] > 0 and _byte_at(f, want[1] - 1) != b"\n"):
                raise _bad("cursor", "调用日志文件已被截短，续页令牌失效", reason="log-truncated")
            end = want[1]
        tools_set = None if tools is None else set(tools)
        for off, raw in _newest_first(f, end):
            try:
                obj = json.loads(raw, parse_constant=_reject_constant)
            except ValueError:
                obj = None
            v = obj.get("v") if isinstance(obj, dict) else None
            if not isinstance(obj, dict) or (type(v) is int and v == VERSION and not isinstance(obj.get("measured"), dict)):
                page["skipped"]["malformed"] += 1
                continue
            if not (type(v) is int and v == VERSION):
                page["skipped"]["unknownVersion"] += 1
                continue
            if not _matches(obj["measured"], tools_set, outcome, model, actionId, branch, since_t, until_t):
                continue
            page["items"].append({"offset": off, **{k: x for k, x in obj.items() if k != "offset"}})
            if len(page["items"]) == limit:
                page["nextCursor"] = _cursor_encode(st.st_ino, off) if off > 0 else None
                break
    return page
