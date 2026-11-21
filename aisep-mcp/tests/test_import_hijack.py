"""The entry points (tools/pyrun.py, tools/aisep.py, tools/aisep-mcp) must run the checkout's reviewed .py source and
nothing else: no same-named module in the repo root or tools/ standing in for a standard-library or installed one, no
committed __pycache__/*.pyc, no extension module next to an aisep .py. And gate rejects tracked bytecode."""
import importlib.machinery, importlib.util, json, os, py_compile, subprocess, sys

from conftest import PY, commit_all, git, run_cli

# importlib / runpy: imported by pyrun itself; msvcrt: the stdlib's own `try: import msvcrt` on Linux and macOS;
# json, pyoxigraph, pyshacl: used by mergecheck and gate
SHADOWED = ("importlib", "runpy", "msvcrt", "json", "pyoxigraph", "pyshacl")


def shim(marker):
    """Source of a module that records it was loaded and ends the process with exit 0."""
    return f"import os\nopen({str(marker)!r}, 'w').close()\nprint('{{\"problems\": []}}', flush=True)\nos._exit(0)\n"


def mergecheck(repo):
    return subprocess.run([PY, "-P", os.path.join(str(repo), "tools", "pyrun.py"), "aisep.mergecheck", "--repo",
                           str(repo), "--github-event", str(repo / "no-such-event.json")],
                          cwd=str(repo), capture_output=True, text=True)


def test_same_named_modules_in_root_and_tools_are_not_loaded(repo, tmp_path):
    marker = tmp_path / "HIJACKED"
    for d in ("", "tools"):
        for name in SHADOWED:
            (repo / d / f"{name}.py").write_text(shim(marker))
    p = mergecheck(repo)
    assert not marker.exists() and p.returncode != 0 and "no-such-event.json" in p.stderr, p.stdout + p.stderr
    rc, out, err = run_cli(repo, "gate")
    assert not marker.exists() and rc == 0 and "result=PASS" in out, out + err


def test_bytecode_and_extension_modules_in_the_checkout_are_not_loaded(repo, tmp_path):
    marker = tmp_path / "HIJACKED"
    src = tmp_path / "shim.py"
    src.write_text(shim(marker))
    for target in ("aisep/mergecheck.py", "aisep/core.py", "tools/pyrun.py"):
        # unchecked-hash: Python would never compare it with the .py, so it runs whatever the .py says
        py_compile.compile(str(src), cfile=importlib.util.cache_from_source(str(repo / target)),
                           invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        # not a loadable library: importing it at all fails the run
        (repo / (target[:-3] + importlib.machinery.EXTENSION_SUFFIXES[0])).write_text("not an extension module")
    p = mergecheck(repo)
    assert not marker.exists() and p.returncode != 0 and "no-such-event.json" in p.stderr, p.stdout + p.stderr
    rc, out, err = run_cli(repo, "gate")
    assert not marker.exists() and rc == 0 and "result=PASS" in out, out + err


def test_gate_rejects_tracked_bytecode_and_extension_modules(repo):
    bad = ["tools/__pycache__/pyrun.cpython-312.pyc", "aisep/old.pyc", "aisep/core" + importlib.machinery.EXTENSION_SUFFIXES[0]]
    for f in bad:
        (repo / f).parent.mkdir(parents=True, exist_ok=True)
        (repo / f).write_bytes(b"x")
    git(repo, "add", "-f", "--", *bad)
    commit_all(repo, "bytecode")
    rc, out, err = run_cli(repo, "gate")
    assert rc == 1 and "result=FAIL" in out, out + err
    for f in bad:
        assert f"tracked bytecode / extension module {f}" in out, out


def test_aisep_mcp_entry_serves_and_ignores_shadowing_modules(repo, tmp_path):
    marker = tmp_path / "HIJACKED"
    for d in ("", "tools"):
        for name in SHADOWED:
            (repo / d / f"{name}.py").write_text(shim(marker))
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
    p = subprocess.run([os.path.join(str(repo), "tools", "aisep-mcp")], cwd=str(repo), input=json.dumps(init) + "\n",
                       capture_output=True, text=True, timeout=120, env={**os.environ, "AISEP_PY": sys.executable})
    assert not marker.exists(), p.stdout + p.stderr
    reply = json.loads(p.stdout.splitlines()[0])
    assert reply["id"] == 1 and reply["result"]["serverInfo"]["name"] == "aisep", p.stdout + p.stderr
