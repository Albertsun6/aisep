"""Shared fixtures (docs/mcp-interface.md §11): every test works in a fresh `git init` under tmp_path holding copies of
models/procurement, modules/, vendor/ (and tools/ + aisep/ so the CLI can run there); the real checkout is never touched."""
import os, shutil, subprocess, sys, zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PY = sys.executable

# Git >= 2.4x starts `git maintenance run --auto --detach` after commits; its background repack moves loose objects into
# packs while a test is cloning the same repo ("unable to read sha1 file", T14 flaky). Turn auto-maintenance off for every
# git this test process and its children run (env-level config also covers clones, topology.py and the server).
_n = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
for _k, _v in (("maintenance.auto", "false"), ("gc.auto", "0")):
    os.environ[f"GIT_CONFIG_KEY_{_n}"], os.environ[f"GIT_CONFIG_VALUE_{_n}"] = _k, _v
    _n += 1
os.environ["GIT_CONFIG_COUNT"] = str(_n)


def pytest_collection_modifyitems(config, items):
    """CI sharding: AISEP_SHARD="i/n" keeps the test cases whose nodeid hashes (crc32) to i mod n. A new test lands in a
    shard by itself, with no list to maintain; unset, every test runs. Under xdist each worker collects and filters alike."""
    spec = os.environ.get("AISEP_SHARD")
    if not spec:
        return
    try:
        i, n = (int(x) for x in spec.split("/"))
        assert 0 <= i < n
    except (ValueError, AssertionError):
        raise pytest.UsageError(f"AISEP_SHARD must be 'i/n' with 0 <= i < n, got {spec!r}")
    keep, drop = [], []
    for t in items:
        (keep if zlib.crc32(t.nodeid.encode()) % n == i else drop).append(t)
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


def git(cwd, *args, check=True):
    p = subprocess.run(["git", "-C", str(cwd), "-c", "commit.gpgsign=false", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {p.stderr}")
    return p.stdout.strip()


def init_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@example.invalid")
    return path


def commit_all(path, msg="c"):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", msg)
    return git(path, "rev-parse", "HEAD")


@pytest.fixture(scope="session", autouse=True)
def _pycache_outside_home(tmp_path_factory):
    """tools/aisep.py and tools/pyrun.py keep bytecode under $XDG_CACHE_HOME/aisep-pycache, mirrored by source path;
    every test repo is a new path, so point that cache at this run's temp root instead of ~/.cache."""
    old = os.environ.get("XDG_CACHE_HOME")
    os.environ["XDG_CACHE_HOME"] = str(tmp_path_factory.getbasetemp().parent / "xdg-cache")
    yield
    if old is None:
        os.environ.pop("XDG_CACHE_HOME", None)
    else:
        os.environ["XDG_CACHE_HOME"] = old


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    t = tmp_path_factory.mktemp("template")
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("modules", "vendor", "tools", "aisep"):
        shutil.copytree(os.path.join(ROOT, d), t / d, ignore=ign)
    shutil.copytree(os.path.join(ROOT, "models", "procurement"), t / "models" / "procurement", ignore=ign)
    # like a real model repo: the server runs from the repo, so its own __pycache__ must be ignored
    shutil.copy2(os.path.join(ROOT, ".gitignore"), t / ".gitignore")
    return t


@pytest.fixture
def repo(template, tmp_path):
    """A git repo whose single commit (on main) is the procurement example + modules + vendor + tools."""
    r = tmp_path / "repo"
    shutil.copytree(template, r)
    init_repo(r)
    commit_all(r, "procurement")
    return r


def run_cli(root, *args):
    p = subprocess.run([PY, os.path.join(str(root), "tools", "aisep.py"), *args], cwd=str(root), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr
