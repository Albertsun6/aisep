"""Shared fixtures (docs/mcp-interface.md §11): every test works in a fresh `git init` under tmp_path holding copies of
models/procurement, modules/, vendor/ (and tools/ + aisep/ so the CLI can run there); the real checkout is never touched."""
import os, shutil, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PY = sys.executable


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
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("modules", "vendor", "tools", "aisep"):
        shutil.copytree(os.path.join(ROOT, d), t / d, ignore=ign)
    shutil.copytree(os.path.join(ROOT, "models", "procurement"), t / "models" / "procurement", ignore=ign)
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
