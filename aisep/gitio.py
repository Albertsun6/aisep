"""Git access and workspace file reading for the MCP server and the CLI (docs/mcp-interface.md §3.3).

- repo location: `locate_repo` (toplevel, --allow-root check)
- refs: `resolve_commit` (safe rev-parse), `resolve_main` (remote-tracking branch first)
- committed content: `snapshot` materialises models/ modules/ vendor/ of one commit into a temp dir
- working tree: `model_files` (the ONE file-set rule: tracked + untracked-not-ignored .ttl under models/) and
  `read_file` (component-wise O_NOFOLLOW open from the worktree root; symlinks and non-regular files refused)
"""
import contextlib, errno, os, shutil, stat, subprocess, tarfile, tempfile

from aisep.errors import AisepError


class UnsafeFile(OSError):
    """A workspace file that must not be read: a symlink at any path level, or not a regular file."""


def git(cwd, *args, binary=False):
    p = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=not binary)
    return p.returncode, p.stdout, p.stderr


def _real(path):
    return os.path.realpath(path)


def under(path, roots):
    rp = _real(path)
    return any(rp == _real(r) or rp.startswith(_real(r).rstrip(os.sep) + os.sep) for r in roots)


def locate_repo(repo=None, allow_roots=(), default=None):
    """Toplevel (realpath) of the worktree containing `repo` (else `default`, else cwd); must lie under an allow-root."""
    path = repo or default or os.getcwd()
    if not os.path.isdir(path):
        raise AisepError("NOT_A_GIT_REPO", f"{path} 不是目录", details={"repo": path})
    rc, out, _ = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        raise AisepError("NOT_A_GIT_REPO", f"{path} 不在 Git 仓库里", details={"repo": path})
    top = _real(out.strip())
    if allow_roots and not under(top, allow_roots):
        raise AisepError("PATH_OUTSIDE_ROOT", f"{top} 不在服务器允许的根目录之下",
                         hint="用 --allow-root 启动服务器时把它加进去", details={"repo": top, "allowRoots": list(allow_roots)})
    return top


def resolve_commit(repo, ref):
    """40-hex commit for `ref`; never lets a ref be read as an option."""
    if not isinstance(ref, str) or not ref or ref.startswith("-"):
        raise AisepError("INVALID_ARGUMENT", f"ref {ref!r} 不合法", details={"rejectedFields": ["ref"]})
    rc, out, _ = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if rc != 0:
        raise AisepError("REF_NOT_FOUND", f"找不到提交 {ref}", details={"ref": ref})
    return out.strip()


def _ref_exists(repo, full):
    return git(repo, "show-ref", "--verify", "--quiet", full)[0] == 0


def resolve_main(repo, name="main"):
    """(full ref name, commit) of the main branch. A short name <b> resolves to refs/remotes/<upstream>/<b> when it
    exists (upstream = <b>'s tracking remote, else origin), else refs/heads/<b> (§3.3: a stale local main would move
    the merge-base back and count teammates' merged work as this branch's)."""
    if not isinstance(name, str) or not name or name.startswith("-"):
        raise AisepError("INVALID_ARGUMENT", f"mainRef {name!r} 不合法", details={"rejectedFields": ["mainRef"]})
    if name.startswith("refs/"):
        candidates = [name]
    else:
        rc, out, _ = git(repo, "config", "--get", f"branch.{name}.remote")
        remote = out.strip() if rc == 0 and out.strip() and out.strip() != "." else "origin"
        candidates = [f"refs/remotes/{remote}/{name}", f"refs/heads/{name}"]
    for full in candidates:
        if _ref_exists(repo, full):
            return full, resolve_commit(repo, full)
    raise AisepError("REF_NOT_FOUND", f"找不到主分支 {name}", details={"ref": name, "tried": candidates})


def model_files(root):
    """Workspace model files, relative to the worktree root, sorted: tracked ∪ untracked-and-not-ignored .ttl under
    models/ (subdirectories included). Ignored files and files of nested repositories are not part of the model."""
    seen = set()
    for extra in ((), ("--others", "--exclude-standard")):
        rc, out, err = git(root, "ls-files", "-z", *extra, "--", "models/")
        if rc != 0:
            raise AisepError("NOT_A_GIT_REPO", f"git ls-files 失败：{err.strip()}", details={"repo": root})
        seen.update(p for p in out.split("\0") if p.endswith(".ttl"))
    return sorted(seen)


def read_file(root, relpath):
    """Bytes of root/relpath, opened component by component from the realpath'd root with O_NOFOLLOW. Raises
    UnsafeFile('symlink' | 'not-regular') instead of following a link at any level or blocking on a FIFO."""
    parts = relpath.split("/")
    dfd = os.open(_real(root), os.O_RDONLY | os.O_DIRECTORY)
    try:
        for i, name in enumerate(parts):
            last = i == len(parts) - 1
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_NONBLOCK if last else os.O_DIRECTORY)
            try:
                fd = os.open(name, flags, dir_fd=dfd)
            except OSError as e:
                if e.errno in (errno.ELOOP, errno.ENOTDIR, errno.EMLINK):
                    st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                    raise UnsafeFile("symlink" if stat.S_ISLNK(st.st_mode) else "not-regular") from None
                raise
            os.close(dfd)
            dfd = fd
        if not stat.S_ISREG(os.fstat(dfd).st_mode):
            raise UnsafeFile("not-regular")
        with os.fdopen(dfd, "rb") as f:
            dfd = None
            return f.read()
    finally:
        if dfd is not None:
            os.close(dfd)


@contextlib.contextmanager
def snapshot(repo, commit):
    """Materialise models/ modules/ vendor/ of `commit` into a temp dir (deleted on exit). Yields (dir, model files
    relative to dir). A commit without modules/ or vendor/ cannot be checked with its own metamodel."""
    rc, out, err = git(repo, "ls-tree", "-z", "--name-only", commit, "--", "models", "modules", "vendor")
    if rc != 0:
        raise AisepError("REF_NOT_FOUND", f"读不了提交 {commit} 的树：{err.strip()}", details={"ref": commit})
    present = [p for p in out.split("\0") if p]
    missing = [p for p in ("modules", "vendor") if p not in present]
    if missing:
        raise AisepError("MODULES_NOT_IN_REF", f"提交 {commit[:7]} 里没有 {'、'.join(missing)}/，无法用它自己的元模型检查",
                         details={"commit": commit, "missing": missing})
    rc, out, _ = git(repo, "ls-tree", "-r", "-z", "--name-only", commit, "--", "models/")
    files = sorted(p for p in out.split("\0") if p.endswith(".ttl"))
    tmp = tempfile.mkdtemp(prefix="aisep-snap-")
    try:
        p = subprocess.Popen(["git", "-C", repo, "archive", "--format=tar", commit, "--", *present], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
            tar.extractall(tmp, filter="data")
        if p.wait() != 0:
            raise AisepError("INTERNAL", f"git archive {commit[:7]} 失败")
        yield tmp, files
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
