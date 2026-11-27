"""Shared fixtures (docs/mcp-interface.md §11): every test works in a fresh `git init` under tmp_path holding copies of
models/procurement, modules/, vendor/ (and tools/ + aisep/ so the CLI can run there); the real checkout is never touched."""
import heapq, json, os, shutil, subprocess, sys

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


DURATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".test_durations")


def assign_shards(tests, durations, n):
    """tests: [(nodeid, group or None)] -> {nodeid: shard in range(n)}. Longest-processing-time-first greedy bin packing
    (pytest-split's least_duration): tests sharing a group form one unit (one session-fixture setup, one shard), units go
    heaviest first, each onto the shard with the least load so far; ties break on the unit key and the shard index, so the
    same input gives the same split in every job and xdist worker. A test with no recorded duration counts as the mean of
    the recorded ones among the tests given (1.0 when none is recorded)."""
    known = [durations[t] for t, _ in tests if t in durations]
    mean = sum(known) / len(known) if known else 1.0
    units = {}
    for t, g in sorted(tests):
        units.setdefault(("g", g) if g else ("t", t), []).append(t)
    order = sorted(((sum(durations.get(t, mean) for t in ts), k) for k, ts in units.items()), key=lambda u: (-u[0], u[1]))
    loads, out = [(0.0, i) for i in range(n)], {}
    for w, k in order:
        load, i = heapq.heappop(loads)
        out.update((t, i) for t in units[k])
        heapq.heappush(loads, (load + w, i))
    return out


def pytest_collection_modifyitems(config, items):
    """CI sharding: AISEP_SHARD="i/n" keeps shard i of the n that assign_shards makes from the recorded per-test durations
    (.test_durations, refreshed with tools/update_test_durations.py); tests marked xdist_group (by name)
    stay in one shard, so a session fixture they share is built in one shard only. Unset,
    every test runs. Under xdist each worker collects the same items and computes the same split."""
    spec = os.environ.get("AISEP_SHARD")
    if not spec:
        return
    try:
        i, n = (int(x) for x in spec.split("/"))
        assert 0 <= i < n
    except (ValueError, AssertionError):
        raise pytest.UsageError(f"AISEP_SHARD must be 'i/n' with 0 <= i < n, got {spec!r}")
    try:
        with open(DURATIONS, encoding="utf-8") as f:
            durations = json.load(f)
    except FileNotFoundError:
        durations = {}
    groups = {t: "_".join(sorted({str(m.args[0] if m.args else m.kwargs.get("name", "default"))
                                  for m in t.iter_markers("xdist_group")})) or None for t in items}
    shard = assign_shards([(t.nodeid, groups[t]) for t in items], durations, n)
    keep, drop = [], []
    for t in items:
        (keep if shard[t.nodeid] == i else drop).append(t)
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


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    t = tmp_path_factory.mktemp("template")
    ign = shutil.ignore_patterns("__pycache__", "node_modules")  # tools/elk/node_modules (elkjs, CI installs it) stays out
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
