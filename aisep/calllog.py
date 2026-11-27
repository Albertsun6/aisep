"""Server-side call log (ADR-031 layer A; docs/mcp-interface.md §3.6 调用日志).

One JSON line per audited call (the write tools, model_apply_action, governance_record_approval; success and refusal
alike) appended to <git-common-dir>/aisep/calls.jsonl. The location comes from the start-up parameters only: the first
--allow-root when it lies in a Git repository, else --repo; neither -> no log, a warning on stderr. Appends take a
repository-wide flock (<git-common-dir>/aisep/calls.lock) and write one whole line with O_APPEND. Fields are split by
source: `measured` (seen by the server) and `declared` (what the caller says; never used for any decision). A failure
to log only warns on stderr (fail-open). No hash chain, not pushed anywhere, no rotation: this log is a record of what
an honestly running server saw, not tamper-evident."""
import fcntl, hashlib, json, os, sys, threading, time
from datetime import datetime, timezone

from aisep import gitio

AUDITED = frozenset({"model_add_element", "model_add_relationship", "model_set_labels", "model_set_attributes",
                     "model_remove", "model_apply_action", "governance_record_approval"})
UNKNOWN_TOOL = "UNKNOWN_TOOL"  # a log-only outcome (an audited name the profile does not list), not an error code
LOG, LOCK = "calls.jsonl", "calls.lock"

_local = threading.local()  # the notes of the call running on this thread (tools run one per worker thread)


def note(**kw):
    """What a tool measured while running (worktree, files written, action version): kept for the current call."""
    notes = getattr(_local, "notes", None)
    if notes is not None:
        notes.update(kw)


def begin():
    _local.notes = {}
    return time.monotonic()


def log_dir(cfg):
    """<git-common-dir>/aisep of the first --allow-root, else of --repo, else None (ADR-031 decision 4)."""
    for path in (cfg.allow_roots[:1] or ()) + ((cfg.repo,) if cfg.repo else ()):
        common = gitio._common_dir(path) if os.path.isdir(path) else None
        if common:
            return os.path.join(common, "aisep")
    return None


def warn(msg):
    print(f"[aisep-mcp] 调用日志：{msg}", file=sys.stderr, flush=True)


def _sha_json(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _worktree(path):
    rc, branch, _ = gitio.git(path, "symbolic-ref", "-q", "--short", "HEAD")
    rc2, head, _ = gitio.git(path, "rev-parse", "--verify", "-q", "HEAD")
    return {"path": path, "branch": branch.strip() if rc == 0 else None, "head": head.strip() if rc2 == 0 else None}


def record(run, name, args, t0, outcome, result=None, client_info=None):
    """The log line of one call. `run` holds the start-up parameters (pid, profile, transport, allowRoots)."""
    notes = getattr(_local, "notes", None) or {}
    _local.notes = None
    ok = outcome == "ok" and isinstance(result, dict)
    target = args.get("iri") if isinstance(args.get("iri"), str) else (result.get("iri") if ok else None)
    m = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
         "server": run, "tool": name, "outcome": outcome, "dryRun": args.get("dryRun") is True,
         "argsSha256": _sha_json(args), "targetIri": target,
         "actionId": args.get("action") if name == "model_apply_action" and isinstance(args.get("action"), str) else None,
         "action": notes.get("action"), "worktree": _worktree(notes["worktree"]) if notes.get("worktree") else None,
         "files": notes.get("files", []), "durationMs": round((time.monotonic() - t0) * 1000)}
    if ok and name == "governance_record_approval":
        m["commit"] = result.get("commit")
        m["activityIri"] = (result.get("activity") or {}).get("iri")
    act = args.get("activity") if name == "governance_record_approval" and isinstance(args.get("activity"), dict) else {}
    d = {"clientInfo": client_info, "agent": act.get("agent"), "sessionRef": act.get("sessionRef")}
    return {"measured": m, "declared": d}


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
