"""Release gate steps that are not the MCP's (docs/mcp-interface.md §5.9 "发布关口" steps 1, 3, 5; ADR
workbench:adrReleaseStepsBySessionScript): the session prepares the release approval branch, the human approves or
rejects it on the gate page (record_approval, step 2), then the session tags, pushes and opens the approval-only PR.

    prepare(repo, *, now, worktree=None, remote="origin", main="main") -> {branch, evidence, worktree}
    publish(repo, branch, *, remote="origin", main="main", gh="gh") -> {branch, evidence, record, decision, tag,
                                                                      tagCreated, pr}

publish tags only when the branch is R plus exactly one approval commit whose single new record is a GateRelease
record with evidence R, no activity and decision Approved, and only after mergecheck.merge_check on that very tip
against the remote main finds nothing but the missing release tag (the same checks as at merge time: approver, one
decision, generation time, gate on R, approval-only shape). Nothing is tagged or pushed otherwise. A same-named tag already peeled to R is reused; one
peeled to another commit stops everything (nothing pushed). A Rejected record gets no tag; the branch is still pushed
and the PR opened so the record reaches main.
Usage (exit 0 = done, 1 = stopped; JSON on stdout):
    python -P tools/pyrun.py aisep.release prepare [--worktree DIR]
    python -P tools/pyrun.py aisep.release publish --branch approval/release-…
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime, timezone

from aisep import core, gitio, mergecheck as mc

RELEASE_BRANCH = re.compile(r"^approval/release-([0-9a-f]{7})-[0-9]{14}\Z")
DECISIONS = {mc.APPROVED: "批准", core.AISEP + "DecisionRejected": "驳回"}


class ReleaseError(Exception):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason, self.message = reason, message


def _git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if p.returncode:
        raise ReleaseError("git-error", f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def _peeled(repo, ref):
    p = subprocess.run(["git", "-C", repo, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}"],
                       capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def _remote_tag(repo, remote, name):
    """The remote's value of refs/tags/<name> peeled to a commit, or None."""
    refs = {}
    for line in _git(repo, "ls-remote", "--tags", remote, f"refs/tags/{name}", f"refs/tags/{name}^{{}}").splitlines():
        sha, ref = line.split("\t")
        refs[ref] = sha
    return refs.get(f"refs/tags/{name}^{{}}") or refs.get(f"refs/tags/{name}")


def _fetch_main(repo, remote, main):
    _git(repo, "fetch", "-q", "--no-tags", remote, f"+refs/heads/{main}:refs/remotes/{remote}/{main}")
    return _git(repo, "rev-parse", f"refs/remotes/{remote}/{main}")


def prepare(repo, *, now, worktree=None, remote="origin", main="main"):
    """Step 1: branch approval/release-{R7}-{UTC yyyymmddHHMMSS} from R = the remote main just fetched, checked out
    in its own worktree (record_approval commits in the branch's worktree)."""
    repo = gitio.locate_repo(repo)
    r = _fetch_main(repo, remote, main)
    branch = f"approval/release-{r[:7]}-{now.astimezone(timezone.utc):%Y%m%d%H%M%S}"
    worktree = os.path.abspath(worktree or os.path.join(repo, ".claude", "worktrees", branch.replace("/", "-")))
    _git(repo, "worktree", "add", "-q", "-b", branch, worktree, r)
    return {"branch": branch, "evidence": r, "worktree": worktree}


def _release_record(repo, branch):
    m = RELEASE_BRANCH.match(branch)
    if not m:
        raise ReleaseError("not-release-branch", f"{branch} 不是发布批准分支 approval/release-{{R 前 7 位}}-{{14 位时间}}")
    tip = _git(repo, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    parents = _git(repo, "rev-list", "--parents", "-n", "1", tip).split()[1:]
    if len(parents) != 1:
        raise ReleaseError("not-one-approval-commit", f"{branch} 的头 {tip[:7]} 不是只有一个父提交")
    r = parents[0]
    if r[:7] != m.group(1):
        raise ReleaseError("not-release-branch", f"{branch} 的名字指向 {m.group(1)}，但批准提交的父提交是 {r[:7]}")
    problems = mc.approval_commit_problems(repo, r, tip)
    if problems:
        raise ReleaseError("not-one-approval-commit", f"{branch} 的头不是一个批准提交：{problems[0]['message']}")
    side_h, side_r = mc._side(repo, tip), mc._side(repo, r)
    new = mc._new(side_h, side_r, mc.RECORD)
    if len(new) != 1:
        raise ReleaseError("not-one-record", f"批准提交新增了 {len(new)} 条批准记录，应恰好 1 条")
    rec = mc._record(side_h, new[0])
    if rec["gate"] != mc.GATE_RELEASE:
        raise ReleaseError("not-release-gate", f"记录 {rec['iri']} 的关口不是 GateRelease")
    if rec["evidence"] != r:
        raise ReleaseError("evidence-mismatch", f"记录的 evidence {rec['evidence']} 不等于被发布的提交 {r}")
    if rec["activities"]:
        raise ReleaseError("release-with-activity", "发布批准记录不应带 AI 活动")
    if len(mc._named(side_h, rec["iri"], mc.DECISION)) != 1 or rec["decision"] not in DECISIONS or rec["time"] is None:
        raise ReleaseError("bad-record", f"记录 {rec['iri']} 须恰好有一个结论，并有生成时间")
    return tip, r, rec


def publish(repo, branch, *, now, remote="origin", main="main", gh="gh"):
    """Steps 3 and 5: tag R only for an Approved record that passes the merge-time checks, push the checked tip (and
    the tag), open the approval-only PR."""
    repo = gitio.locate_repo(repo)
    main_head = _fetch_main(repo, remote, main)
    tip, r, rec = _release_record(repo, branch)
    if not mc._is_ancestor(repo, r, main_head):
        raise ReleaseError("release-head-not-on-main", f"被发布的提交 {r[:7]} 不在 {remote}/{main} 上")
    approved = rec["decision"] == mc.APPROVED
    tag = f"release/{rec['time'].astimezone(timezone.utc):%Y%m%d}-{r[:7]}" if approved else None
    local = _peeled(repo, f"refs/tags/{tag}") if tag else None
    far = _remote_tag(repo, remote, tag) if tag else None
    for where, sha in (("本地", local), ("远端", far)):
        if sha is not None and sha != r:
            raise ReleaseError("release-tag-conflict", f"{where}已有标签 {tag}，剥离后指向 {sha[:7]}，不是 {r[:7]}；由人处理")
    # The merge-time checks on exactly this tip (§5.9 合并时校验); before the tag exists the only expected problem
    # is the missing tag itself.
    problems = [p for p in mc.merge_check(repo, tip, main_head, head_ref=branch, now=now, remote=remote)
                if not (approved and far is None and p["reason"] == "release-tag-missing")]
    if problems:
        raise ReleaseError("merge-check-failed", "合并时校验不通过，不打标签、不推送：" +
                           "；".join(f"{p['reason']}：{p['message']}" for p in problems))
    created = False
    if tag and local is None and far is None:  # a remote tag already on R is reused as it is, not copied locally
        _git(repo, "tag", tag, r)
        created = True
    refspecs = [f"{tip}:refs/heads/{branch}"] + ([f"refs/tags/{tag}:refs/tags/{tag}"] if tag and far is None else [])
    _git(repo, "push", "--atomic", remote, *refspecs)
    verdict = DECISIONS[rec["decision"]]
    body = (f"发布关口{verdict}（批准专用 PR，ADR-021 第 1 款）。\n\n- 被发布的提交 R：`{r}`\n- 批准记录：`{rec['iri']}`\n"
            f"- 批准提交：`{tip}`\n- release 标签：{f'`{tag}`' if tag else '无（驳回不打标签）'}\n")
    try:
        p = subprocess.run([gh, "pr", "create", "--base", main, "--head", branch,
                            "--title", f"approval：发布关口{verdict} {r[:7]}", "--body", body],
                           cwd=repo, capture_output=True, text=True)
    except OSError as e:
        raise ReleaseError("pr-create-failed", f"已推送，开 PR 失败：{e}") from None
    if p.returncode:
        raise ReleaseError("pr-create-failed", f"已推送，开 PR 失败：{p.stderr.strip()}")
    return {"branch": branch, "evidence": r, "record": rec["iri"], "decision": verdict, "tag": tag,
            "tagCreated": created, "pr": p.stdout.strip().splitlines()[-1] if p.stdout.strip() else None}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -P tools/pyrun.py aisep.release", description="发布关口的会话步骤（§5.9）")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--main", default="main")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare", help="从远端 main 最新提交拉发布批准分支")
    pp.add_argument("--worktree")
    pp.add_argument("--now", help="xsd:dateTime，缺省为当前 UTC")
    pb = sub.add_parser("publish", help="核对记录，批准才打标签；推送并开批准专用 PR")
    pb.add_argument("--branch", required=True)
    pb.add_argument("--gh", default=os.environ.get("AISEP_GH", "gh"))
    a = ap.parse_args(argv)
    try:
        if a.cmd == "prepare":
            now = core.parse_xsd_datetime(a.now) if a.now else datetime.now(timezone.utc)
            out = prepare(a.repo, now=now, worktree=a.worktree, remote=a.remote, main=a.main)
        else:
            out = publish(a.repo, a.branch, now=datetime.now(timezone.utc), remote=a.remote, main=a.main, gh=a.gh)
    except ReleaseError as e:
        print(json.dumps({"problems": [{"reason": e.reason, "message": e.message}]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
