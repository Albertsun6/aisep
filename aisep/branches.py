"""`model_branches`: local branches and their Git facts, for the workbench's list of gate pages (docs/mcp-interface.md §5.11).

Read-only and offline: plumbing commands only (for-each-ref, rev-parse, merge-base, diff-tree), no fetch, no index
refresh. Remote-tracking refs are whatever the last fetch left; `remoteHead` is `refs/remotes/origin/<branch>`.
"""
from aisep import gitio
from aisep.errors import AisepError


def _git(root, *args):
    rc, out, err = gitio.git(root, *args)
    if rc not in (0, 1):
        raise AisepError("INTERNAL", f"git {args[0]} 失败：{err.strip()}")
    return rc, out


def _is_ancestor(root, a, b):
    return _git(root, "merge-base", "--is-ancestor", a, b)[0] == 0


def _has_model_changes(root, head, main):
    rc, mb = _git(root, "merge-base", head, main)
    if rc != 0:  # unrelated histories: every model file on the branch is its own
        rc, out = _git(root, "ls-tree", "-r", "-z", "--name-only", head, "--", "models/")
    else:
        rc, out = _git(root, "diff-tree", "-r", "-z", "--name-only", "--no-renames", mb.strip(), head, "--", "models/")
    return any(p.endswith(".ttl") for p in out.split("\0"))


def model_branches(cfg, repo=None):
    root = gitio.locate_repo(repo, cfg.allow_roots, cfg.repo)
    main_ref, main = gitio.resolve_main(root, cfg.main_branch)
    _, out = _git(root, "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads", "refs/remotes/origin")
    local, remote = {}, {}
    for line in out.splitlines():
        sha, ref = line.split(" ", 1)
        if ref.startswith("refs/heads/"):
            local[ref[len("refs/heads/"):]] = sha
        else:
            remote[ref[len("refs/remotes/origin/"):]] = sha
    branches = []
    for name in sorted(local):
        head, rhead = local[name], remote.get(name)
        branches.append({
            "branch": name, "head": head, "remoteHead": rhead,
            "unpushed": rhead is None or not _is_ancestor(root, head, rhead),
            "mergedIntoMain": _is_ancestor(root, head, main),
            "hasModelChanges": _has_model_changes(root, head, main)})
    return {"branches": branches, "main": {"ref": main_ref, "commit": main}}
