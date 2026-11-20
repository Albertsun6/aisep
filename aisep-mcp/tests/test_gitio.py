"""S1: Git access and workspace reading (docs/mcp-interface.md §3.3). Acceptance: T10, T14 (main-branch resolution),
T19 (MODULES_NOT_IN_REF), T20 (ref errors), and the §3.3 file-set / safe-open rules (R2-10, R2-12, R2-16)."""
import os, shutil, signal, time

import pyoxigraph as ox
import pytest

from conftest import ROOT, commit_all, git, init_repo, run_cli
from aisep import core, gitio
from aisep.errors import AisepError

VIOLATION = "\n:quoteApproval am4:accesses :quotation .\n"  # a direct triple: L1 Violation (as in test_review_g7_g10)


def gate_lines(root, files, read):
    """[sev] layer text lines of a gate run in-process — the same set the CLI prints."""
    ctx = core.Ctx(core.discover(str(root)), [os.path.join(str(root), f) for f in files], read=read)
    if not any(p[1] == "L0" for p in ctx.problems):
        core.run_check(ctx)
        core.l3(ctx)
        core.l4(ctx)
    return {f"[{s}] {l} {t}" for s, l, t in ctx.problems}


def cli_lines(out):
    return {line for line in out.splitlines() if line.startswith("[")}


def raises(code, fn, *a, **kw):
    with pytest.raises(AisepError) as e:
        fn(*a, **kw)
    assert e.value.code == code, (e.value.code, e.value.message)
    return e.value


# ---------------------------------------------------------------- T10: gate at a commit = gate on that commit's checkout

def test_T10_snapshot_gate_equals_checkout_gate(repo, tmp_path):
    c1 = git(repo, "rev-parse", "HEAD")
    with open(repo / "models/procurement/am4.ttl", "a") as f:  # uncommitted violation in the working tree
        f.write(VIOLATION)
    rc_wt, out_wt, _ = run_cli(repo, "gate")
    assert rc_wt == 1 and "direct triple written in source models/procurement/am4.ttl" in out_wt

    co = tmp_path / "checkout"
    git(repo, "worktree", "add", "-q", "--detach", str(co), c1)
    rc_co, out_co, _ = run_cli(co, "gate")

    t = time.time()
    with gitio.snapshot(str(repo), gitio.resolve_commit(str(repo), c1)) as (snap, files):
        snap_lines = gate_lines(snap, files, lambda f: gitio.read_file(snap, os.path.relpath(f, snap)))
    print(f"T10 snapshot+gate seconds={time.time() - t:.2f}")
    assert rc_co == 0 and "result=PASS" in out_co
    assert snap_lines == cli_lines(out_co)
    assert not any(line.startswith("[Violation]") for line in snap_lines)


def test_T10_snapshot_sees_committed_violation(repo):
    with open(repo / "models/procurement/am4.ttl", "a") as f:
        f.write(VIOLATION)
    c2 = commit_all(repo, "violation")
    rc, out, _ = run_cli(repo, "gate")
    with gitio.snapshot(str(repo), c2) as (snap, files):
        lines = gate_lines(snap, files, lambda f: gitio.read_file(snap, os.path.relpath(f, snap)))
    assert rc == 1 and lines == cli_lines(out)
    assert any("direct triple" in line for line in lines)


def test_snapshot_is_removed(repo):
    c = git(repo, "rev-parse", "HEAD")
    with gitio.snapshot(str(repo), c) as (snap, files):
        assert files == sorted(f"models/procurement/{n}" for n in os.listdir(repo / "models/procurement"))
    assert not os.path.exists(snap)
    with pytest.raises(RuntimeError):
        with gitio.snapshot(str(repo), c) as (snap2, _):
            raise RuntimeError
    assert not os.path.exists(snap2)


# ---------------------------------------------------------------- T19: MODULES_NOT_IN_REF, no models/

def test_T19_modules_not_in_ref(tmp_path):
    r = init_repo(tmp_path / "r")
    os.makedirs(r / "models/p")
    (r / "models/p/a.ttl").write_text("")
    c = commit_all(r)
    e = raises("MODULES_NOT_IN_REF", lambda: gitio.snapshot(str(r), c).__enter__())
    assert e.details["missing"] == ["modules", "vendor"]


def test_T19_commit_without_models(repo):
    git(repo, "rm", "-r", "-q", "models")
    c = commit_all(repo, "drop models")
    with gitio.snapshot(str(repo), c) as (snap, files):
        assert files == [] and os.path.isdir(os.path.join(snap, "modules"))


# ---------------------------------------------------------------- T20: ref errors

def test_T20_ref_errors(repo, tmp_path):
    target = tmp_path / "x"
    raises("INVALID_ARGUMENT", gitio.resolve_commit, str(repo), f"--output={target}")
    assert not target.exists()
    raises("REF_NOT_FOUND", gitio.resolve_commit, str(repo), "no-such-branch")
    raises("REF_NOT_FOUND", gitio.resolve_commit, str(repo), "HEAD:models")  # a tree, not a commit
    assert gitio.resolve_commit(str(repo), "main") == git(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------- T14 (second half): main branch resolution

def test_T14_main_prefers_remote_tracking(tmp_path):
    a = init_repo(tmp_path / "a")
    (a / "f").write_text("1")
    commit_all(a)
    b = tmp_path / "b"
    git(tmp_path, "clone", "-q", str(a), str(b))
    (a / "f").write_text("2")
    c2 = commit_all(a)
    git(b, "fetch", "-q")
    assert git(b, "rev-parse", "main") != c2  # local main is behind origin/main
    assert gitio.resolve_main(str(b), "main") == ("refs/remotes/origin/main", c2)


def test_T14_main_uses_tracking_remote(tmp_path):
    a = init_repo(tmp_path / "a")
    (a / "f").write_text("1")
    commit_all(a)
    b = tmp_path / "b"
    git(tmp_path, "clone", "-q", str(a), str(b))
    git(b, "remote", "add", "up", str(a))
    (a / "f").write_text("2")
    c2 = commit_all(a)
    git(b, "fetch", "-q", "up")
    git(b, "config", "branch.main.remote", "up")
    assert gitio.resolve_main(str(b), "main") == ("refs/remotes/up/main", c2)


def test_T14_main_local_and_errors(repo):
    assert gitio.resolve_main(str(repo), "main") == ("refs/heads/main", git(repo, "rev-parse", "HEAD"))
    raises("REF_NOT_FOUND", gitio.resolve_main, str(repo), "trunk")
    raises("INVALID_ARGUMENT", gitio.resolve_main, str(repo), "--output=x")


# ---------------------------------------------------------------- §3.3: repo location

def test_locate_repo(repo, tmp_path):
    sub = repo / "models" / "procurement"
    assert gitio.locate_repo(str(sub), allow_roots=[str(tmp_path)]) == os.path.realpath(repo)
    raises("PATH_OUTSIDE_ROOT", gitio.locate_repo, str(repo), allow_roots=[str(tmp_path / "elsewhere")])
    plain = tmp_path / "plain"
    plain.mkdir()
    raises("NOT_A_GIT_REPO", gitio.locate_repo, str(plain))


# ---------------------------------------------------------------- §3.3 (R2-16): the one workspace file set

def test_file_set(repo, tmp_path):
    p = repo / "models/procurement"
    os.makedirs(p / "governance")
    (p / "governance/approval-x.ttl").write_text("")        # untracked, in a subdirectory: in
    (repo / ".gitignore").write_text("models/procurement/ignored.ttl\n")
    (p / "ignored.ttl").write_text("")                        # ignored: out
    (p / "notes.md").write_text("")                           # not .ttl: out
    nested = init_repo(repo / "models/nested")                # nested repository: out
    (nested / "x.ttl").write_text("")
    commit_all(nested)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "z.ttl").write_text("")
    os.symlink(outside, repo / "models/link")                 # untracked directory symlink: out
    files = gitio.model_files(str(repo))
    assert "models/procurement/governance/approval-x.ttl" in files
    assert "models/procurement/am4.ttl" in files
    assert not [f for f in files if "ignored" in f or "nested" in f or "link" in f or not f.endswith(".ttl")]


def test_deleted_tracked_file_is_not_in_the_set(repo):
    os.remove(repo / "models/procurement/uml.ttl")
    assert "models/procurement/uml.ttl" not in gitio.model_files(str(repo))
    rc, out, _ = run_cli(repo, "check")
    assert "files=6 " in out and "cannot parse" not in out


def test_cli_default_uses_file_set(repo):
    (repo / ".gitignore").write_text("models/procurement/ignored.ttl\n")
    (repo / "models/procurement/ignored.ttl").write_text("this is not turtle")
    rc, out, _ = run_cli(repo, "check")
    assert rc == 0 and "files=7" in out, out
    rc, out, _ = run_cli(repo, "check", "models/procurement/ignored.ttl")  # an explicit argument is still read
    assert rc == 1 and "cannot parse models/procurement/ignored.ttl" in out


# ---------------------------------------------------------------- §3.3 (R2-10, R2-12): safe open

def test_parent_directory_symlink_is_not_followed(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "am4.ttl").write_text("@prefix x: <urn:outside#> .\nx:secret x:p x:o .\n")
    shutil.rmtree(repo / "models/procurement")
    os.symlink(outside, repo / "models/procurement")
    files = gitio.model_files(str(repo))
    assert "models/procurement/am4.ttl" in files  # still listed from the index
    with pytest.raises(gitio.UnsafeFile, match="symlink"):
        gitio.read_file(str(repo), "models/procurement/am4.ttl")
    rc, out, _ = run_cli(repo, "check")
    assert rc == 1 and "[Violation] L0 cannot parse models/procurement/am4.ttl: symlink" in out
    assert "urn:outside" not in out


def test_file_symlink_and_fifo(repo, tmp_path):
    secret = tmp_path / "secret.ttl"
    secret.write_text("")
    os.symlink(secret, repo / "models/procurement/link.ttl")
    (repo / "models/procurement/pipe.ttl").write_text("")  # tracked, then replaced by a FIFO (git lists the index path;
    commit_all(repo, "pipe")                                # an untracked FIFO is never listed)
    os.remove(repo / "models/procurement/pipe.ttl")
    os.mkfifo(repo / "models/procurement/pipe.ttl")
    files = gitio.model_files(str(repo))
    assert {"models/procurement/link.ttl", "models/procurement/pipe.ttl"} <= set(files)
    with pytest.raises(gitio.UnsafeFile, match="symlink"):
        gitio.read_file(str(repo), "models/procurement/link.ttl")
    signal.alarm(5)  # a blocking open on the FIFO would hang the test; fail instead
    try:
        with pytest.raises(gitio.UnsafeFile, match="not-regular"):
            gitio.read_file(str(repo), "models/procurement/pipe.ttl")
    finally:
        signal.alarm(0)


def test_safe_read_parses_like_path_read(tmp_path):
    files = sorted(os.path.join("models/procurement", f) for f in os.listdir(os.path.join(ROOT, "models/procurement")))
    for f in files:
        by_path = list(ox.parse(path=os.path.join(ROOT, f), format=ox.RdfFormat.TURTLE))
        by_fd = list(ox.parse(gitio.read_file(ROOT, f), format=ox.RdfFormat.TURTLE))
        assert by_path == by_fd, f
    bad = tmp_path / "bad.ttl"
    bad.write_text("@prefix x: <urn:x#> .\nx:a x:b \n")
    mods = core.discover()
    a = core.Ctx(mods, [str(bad)], root=str(tmp_path)).problems
    b = core.Ctx(mods, [str(bad)], root=str(tmp_path), read=lambda f: open(f, "rb").read()).problems
    assert a == b and "(bad.ttl, line 3)" in a[0][2]
