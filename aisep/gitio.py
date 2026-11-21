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


# SEC-3: a directory inside a checkout that looks like a git dir (HEAD, objects/, refs/, config) must never be picked
# up as a repository by implicit discovery: its config (core.fsmonitor, ...) would run. Only real worktrees (a .git
# directory or a .git file) are discovered. Every git call of the server goes through these options.
GIT = ("git", "-c", "safe.bareRepository=explicit")


def git(cwd, *args, binary=False):
    p = subprocess.run([*GIT, "-C", cwd, *args], capture_output=True, text=not binary)
    return p.returncode, p.stdout, p.stderr


def bare_refused(stderr):
    """git refused to discover a bare repository (safe.bareRepository=explicit): the path is a bare repo or a
    directory shaped like one. The key name is not translated, unlike the rest of the message."""
    return "safe.bareRepository" in (stderr or "")


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
    models/ (subdirectories included), minus tracked files deleted from disk. Ignored files and files of nested
    repositories are not part of the model."""
    seen = set()
    for extra in ((), ("--others", "--exclude-standard")):
        rc, out, err = git(root, "ls-files", "-z", *extra, "--", "models/")
        if rc != 0:
            raise AisepError("NOT_A_GIT_REPO", f"git ls-files 失败：{err.strip()}", details={"repo": root})
        seen.update(p for p in out.split("\0") if p.endswith(".ttl"))
    # a tracked file deleted from disk is not part of the workspace model (content always comes from disk, §3.3)
    return sorted(p for p in seen if os.path.lexists(os.path.join(root, p)))


def read_file(root, relpath):
    """Bytes of root/relpath, opened component by component from the realpath'd root with O_NOFOLLOW. Raises
    UnsafeFile('symlink' | 'not-regular') instead of following a link at any level or blocking on a FIFO."""
    parts = relpath.split("/")
    if any(p in ("", ".", "..") for p in parts):  # never step out of root or name a directory as the file
        raise UnsafeFile("not-normalised")
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
        p = subprocess.Popen([*GIT, "-C", repo, "archive", "--format=tar", commit, "--", *present], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
            tar.extractall(tmp, filter="data")
        if p.wait() != 0:
            raise AisepError("INTERNAL", f"git archive {commit[:7]} 失败")
        yield tmp, files
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- worktrees, merge-base, committed blobs (§3.3, §5.8)

def validate_branch_name(repo, name):
    """A branch short name only: no path, no refs/…, no @{-1} (check-ref-format --branch must return it unchanged)."""
    if not isinstance(name, str) or not name or name.startswith(("-", "/", "refs/")) or "\\" in name or "\0" in name:
        raise AisepError("INVALID_ARGUMENT", f"只接受分支短名，收到 {name!r}", details={"rejectedFields": ["worktree"]})
    rc, out, _ = git(repo, "check-ref-format", "--branch", name)
    if rc != 0 or out.strip() != name:
        raise AisepError("INVALID_ARGUMENT", f"{name!r} 不是合法的分支短名", details={"rejectedFields": ["worktree"]})


def worktree_entries(repo):
    rc, out, err = git(repo, "worktree", "list", "--porcelain", "-z")
    if rc != 0:
        raise AisepError("NOT_A_GIT_REPO", f"git worktree list 失败：{err.strip()}")
    entries, cur = [], {}
    for field in out.split("\0"):
        if not field:
            if cur:
                entries.append(cur)
            cur = {}
            continue
        k, _, v = field.partition(" ")
        cur[k] = v
    if cur:
        entries.append(cur)
    return entries


def _common_dir(path):
    rc, out, _ = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return _real(out.strip()) if rc == 0 else None


def locate_worktree(repo, branch, allow_roots=()):
    """The worktree W where refs/heads/<branch> is checked out, found only among Git's own registrations, then checked:
    realpath(W) under an allow-root (else PATH_OUTSIDE_ROOT) and W's common dir == repo's (else WORKTREE_NOT_FOUND)."""
    validate_branch_name(repo, branch)
    want = f"refs/heads/{branch}"
    hits = [e for e in worktree_entries(repo) if e.get("branch") == want]
    if not hits:
        raise AisepError("WORKTREE_NOT_FOUND", f"分支 {branch} 没有检出的工作区",
                         hint="改用 Git 引用模式：head 传分支名字符串", details={"branchExists": _ref_exists(repo, want)})
    w = hits[0]["worktree"]
    if "prunable" in hits[0] or not os.path.isdir(w):
        raise AisepError("WORKTREE_NOT_FOUND", f"分支 {branch} 的工作区目录已不存在",
                         details={"branchExists": True, "prunable": True})
    if allow_roots and not under(w, allow_roots):
        raise AisepError("PATH_OUTSIDE_ROOT", f"分支 {branch} 的工作区不在允许的根目录之下", details={"branch": branch})
    if _common_dir(w) != _common_dir(repo):
        raise AisepError("WORKTREE_NOT_FOUND", f"分支 {branch} 登记的工作区不属于本仓库", details={"branchExists": True})
    return _real(w)


def merge_base(repo, a, b):
    rc, out, _ = git(repo, "merge-base", "--all", a, b)
    found = out.split() if rc == 0 else []
    if not found:
        raise AisepError("NO_MERGE_BASE", f"{a[:7]} 与 {b[:7]} 没有共同祖先")
    if len(found) > 1:
        raise AisepError("AMBIGUOUS_MERGE_BASE", f"有 {len(found)} 个 merge-base（交叉合并），无法确定比较起点",
                         hint="显式传 base", details={"candidates": found})
    return found[0]


def tree_entries(repo, commit, path):
    """{path: (mode, type, sha)} of the entries directly under path in commit, keyed by full path ({} if absent)."""
    rc, out, _ = git(repo, "ls-tree", "-z", commit, "--", path.rstrip("/") + "/")
    res = {}
    for rec in out.split("\0") if rc == 0 else ():
        if rec:
            meta, name = rec.split("\t", 1)
            mode, typ, sha = meta.split()
            res[name] = (mode, typ, sha)
    return res


def commit_files(repo, commit, prefixes=("models/",)):
    """{path: bytes | "symlink" | "not-regular"} of the .ttl blobs under the prefixes in commit, read with one
    cat-file --batch. A link (mode 120000) or gitlink is never followed."""
    meta = {}
    for prefix in prefixes:
        rc, out, err = git(repo, "ls-tree", "-r", "-z", commit, "--", prefix)
        if rc != 0:
            raise AisepError("REF_NOT_FOUND", f"读不了提交 {commit} 的树：{err.strip()}", details={"ref": commit})
        for rec in out.split("\0"):
            if rec:
                m, path = rec.split("\t", 1)
                mode, typ, sha = m.split()
                if path.endswith(".ttl"):
                    meta[path] = (mode, typ, sha)
    files = {p: ("symlink" if mode == "120000" else "not-regular") for p, (mode, typ, _) in meta.items()
             if mode == "120000" or typ != "blob"}
    want = [(p, sha) for p, (mode, typ, sha) in sorted(meta.items()) if p not in files]
    if want:
        p = subprocess.run([*GIT, "-C", repo, "cat-file", "--batch"], input="".join(f"{sha}\n" for _, sha in want).encode(),
                           capture_output=True)
        buf, pos = p.stdout, 0
        for path, _ in want:
            nl = buf.index(b"\n", pos)
            size = int(buf[pos:nl].split()[2])
            files[path] = buf[nl + 1:nl + 1 + size]
            pos = nl + 1 + size + 1
    return files


def index_flags(w):
    """{path: tag} from `ls-files -v` under models/: 'S' = skip-worktree, lowercase = assume-unchanged."""
    rc, out, _ = git(w, "ls-files", "-v", "-z", "--", "models/")
    return {rec[2:]: rec[0] for rec in out.split("\0") if rec} if rc == 0 else {}


def sparse_checkout(w):
    rc, out, _ = git(w, "config", "--bool", "core.sparseCheckout")
    return rc == 0 and out.strip() == "true"


def open_dir(root, reldir):
    """fd of root/reldir opened component by component with O_NOFOLLOW (write side of §3.3's safe open): a symlink at
    any level raises UnsafeFile('symlink'); a missing directory raises FileNotFoundError."""
    names = [p for p in reldir.split("/") if p]
    if any(p in (".", "..") for p in names):  # never step out of root
        raise UnsafeFile("not-normalised")
    dfd = os.open(_real(root), os.O_RDONLY | os.O_DIRECTORY)
    for name in names:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
        except OSError as e:
            if e.errno in (errno.ELOOP, errno.ENOTDIR):
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                os.close(dfd)
                raise UnsafeFile("symlink" if stat.S_ISLNK(st.st_mode) else "not-regular") from None
            os.close(dfd)
            raise
        os.close(dfd)
        dfd = fd
    return dfd
