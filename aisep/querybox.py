"""Run one caller-supplied SPARQL query in a child process that cannot use the network (issue #60, mcp-interface §5.6).

pyoxigraph 0.5.13 really sends HTTP for SERVICE and has no switch to turn that off; recognising SERVICE in the query
text never converged (PR #56). So the guarantee does not look at the text: the query runs in a fresh interpreter that
confines itself before it reads the query, and any network attempt ends that process.

- Linux: a seccomp filter (no privileges needed, inherited by every thread and exec) kills the process with SIGSYS on
  socket / socketpair / io_uring_setup; a syscall from any other ABI is killed too. The child holds no socket: its
  stdin, stdout and stderr are pipes and nothing else is inherited (close_fds).
- macOS: sandbox_init with `(deny network* (with send-signal SIGKILL))`: connect / send / bind on any socket family
  (DNS through mDNSResponder included) is denied and the process is killed.
- Anything else, or a confinement that fails or cannot be confirmed: the child exits before reading the query, and
  the caller gets an error. Never falls back to running the query unconfined.

This file runs as a script in the child (`python -I querybox.py`): stdlib and pyoxigraph only, no aisep imports.
"""
import json
import os
import signal
import subprocess
import sys

CONFINE_FAILED = 3  # child exit status: confinement could not be established or confirmed; the query was not read
_KILLED_BY = {"linux": signal.SIGSYS, "darwin": signal.SIGKILL}


class NetworkAttempt(Exception):
    """The query tried to open a network connection; the confinement killed it before anything was sent."""


class Timeout(Exception):
    pass


class Unavailable(Exception):
    """No network-less child could be started on this platform; the query was not run."""


# ---------------------------------------------------------------- child

def _confine_linux():
    import ctypes
    import platform
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))  # SIGSYS would otherwise dump core
    audit, nrs = {"x86_64": (0xC000003E, (41, 53, 425)),  # socket, socketpair, io_uring_setup
                  "aarch64": (0xC00000B7, (198, 199, 425))}[platform.machine()]
    ld_abs, jeq, jge, ret = 0x20, 0x15, 0x35, 0x06
    kill, allow = 0x80000000, 0x7FFF0000  # SECCOMP_RET_KILL_PROCESS, SECCOMP_RET_ALLOW
    prog = [(ld_abs, 0, 0, 4), (jeq, 1, 0, audit), (ret, 0, 0, kill), (ld_abs, 0, 0, 0)]
    if audit == 0xC000003E:
        prog += [(jge, 0, 1, 0x40000000), (ret, 0, 0, kill)]  # x32 ABI numbers
    for nr in nrs:
        prog += [(jeq, 0, 1, nr), (ret, 0, 0, kill)]
    prog.append((ret, 0, 0, allow))

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]

    class Prog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    insns = (Filter * len(prog))(*(Filter(*i) for i in prog))
    fprog = Prog(len(prog), insns)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(38, 1, None, 0, 0):  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
    if libc.prctl(22, 2, ctypes.addressof(fprog), 0, 0):  # PR_SET_SECCOMP, SECCOMP_MODE_FILTER
        raise OSError(ctypes.get_errno(), "PR_SET_SECCOMP")
    if libc.prctl(21, 0, None, 0, 0) != 2:  # PR_GET_SECCOMP
        raise OSError("seccomp filter not in effect")


def _confine_darwin():
    import ctypes
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    lib.sandbox_init.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_char_p)]
    lib.sandbox_check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    err = ctypes.c_char_p()
    if lib.sandbox_init(b"(version 1)(allow default)(deny network* (with send-signal SIGKILL))", 0, ctypes.byref(err)):
        raise OSError(f"sandbox_init: {err.value!r}")
    if lib.sandbox_check(os.getpid(), b"network-outbound", 0) != 1:
        raise OSError("sandbox not in effect")


def _term(v):
    import pyoxigraph as ox
    if isinstance(v, ox.NamedNode):
        return {"type": "iri", "value": v.value}
    if isinstance(v, ox.BlankNode):
        return {"type": "bnode", "value": v.value}
    t = {"type": "literal", "value": v.value}
    if v.language:
        t["lang"] = v.language
    else:
        t["datatype"] = v.datatype.value
    return t


def run_query(store, sparql, prefixes, limit):
    """The §5.6 result dict of one query on `store`."""
    import pyoxigraph as ox
    res = store.query(sparql, prefixes=prefixes, use_default_graph_as_union=True)
    if isinstance(res, (ox.QueryBoolean, bool)):
        return {"kind": "ask", "value": bool(res)}
    rows = []
    if isinstance(res, ox.QueryTriples):
        for tr in res:
            if len(rows) == limit:
                return {"kind": "triples", "triples": rows, "truncated": True}
            rows.append([_term(tr.subject), _term(tr.predicate), _term(tr.object)])
        return {"kind": "triples", "triples": rows, "truncated": False}
    names = [v.value for v in res.variables]
    for sol in res:
        if len(rows) == limit:
            return {"kind": "select", "variables": names, "rows": rows, "truncated": True}
        rows.append({n: _term(sol[n]) for n in names if sol[n] is not None})
    return {"kind": "select", "variables": names, "rows": rows, "truncated": False}


def _child():
    try:
        {"linux": _confine_linux, "darwin": _confine_darwin}[sys.platform]()
    except Exception as e:  # noqa: BLE001 — any failure, including an unknown platform or CPU: do not run the query
        sys.stderr.write(f"confinement failed: {e!r}\n")
        sys.exit(CONFINE_FAILED)
    import pyoxigraph as ox
    head = json.loads(sys.stdin.buffer.readline())
    store = ox.Store()
    store.load(sys.stdin.buffer.read(), format=ox.RdfFormat.N_QUADS)
    try:
        out = {"result": run_query(store, head["sparql"], head["prefixes"], head["limit"])}
    except Exception as e:  # noqa: BLE001 — handed to the parent, which maps it as before
        kind = next((c.__name__ for c in _ERRORS.values() if isinstance(e, c)), "Exception")
        out = {"error": {"type": kind, "message": str(e)}}
    sys.stdout.write(json.dumps(out))


# ---------------------------------------------------------------- parent

_ERRORS = {c.__name__: c for c in (SyntaxError, OSError, ValueError, RuntimeError)}


def run(store, sparql, prefixes, limit, timeout_s):
    """run_query(store, ...) in a network-less child. Raises NetworkAttempt, Timeout, Unavailable, or the query's own
    SyntaxError / OSError / ValueError / RuntimeError (anything else as Exception)."""
    if sys.platform not in _KILLED_BY:
        raise Unavailable(f"平台 {sys.platform} 上没有无网络的查询进程")
    head = json.dumps({"sparql": sparql, "prefixes": prefixes, "limit": limit}).encode() + b"\n"
    data = head + store.dump(format=__import__("pyoxigraph").RdfFormat.N_QUADS)
    try:
        p = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)], input=data, capture_output=True,
                           timeout=timeout_s, close_fds=True, env={"PATH": os.environ.get("PATH", "")})
    except subprocess.TimeoutExpired:
        raise Timeout() from None
    if p.returncode == -_KILLED_BY[sys.platform]:
        raise NetworkAttempt()
    if p.returncode == CONFINE_FAILED:
        raise Unavailable(p.stderr.decode(errors="replace").strip())
    if p.returncode:
        raise RuntimeError(f"查询进程异常退出（{p.returncode}）：{p.stderr.decode(errors='replace').strip()[-500:]}")
    out = json.loads(p.stdout)
    if "error" in out:
        raise _ERRORS.get(out["error"]["type"], Exception)(out["error"]["message"])
    return out["result"]


if __name__ == "__main__":
    _child()
