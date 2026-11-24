"""aisep.release: the session's release gate steps (§5.9 steps 1, 3, 5; workbench:adrReleaseStepsBySessionScript).
Each test names the workbench acceptance criterion it verifies. Topo gives a tmp repo with a local bare `origin`;
`gh` is a stub that records its arguments, so nothing reaches GitHub."""
import json, os, stat
from datetime import datetime, timezone

import pytest

from aisep import approval, release
from aisep import tools as T
from fixtures.topology import M, Topo

NOW = datetime(2026, 11, 20, 11, 0, 0, tzinfo=timezone.utc)
PUB_NOW = datetime(2026, 11, 21, 9, 0, 0, tzinfo=timezone.utc)  # publish's merge-time check clock
BOSS = M + "chiefArchitect"


@pytest.fixture
def t(template, tmp_path):
    return Topo(template, tmp_path)


@pytest.fixture
def gh(tmp_path):
    log = tmp_path / "gh-args.json"
    p = tmp_path / "gh"
    p.write_text("#!/usr/bin/env python3\nimport json, sys\n"
                 f"json.dump(sys.argv[1:], open({str(log)!r}, 'w'))\nprint('https://example.invalid/pull/1')\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p), log


def remote_tag(t, name):
    out = t.git("ls-remote", "--tags", "origin", f"refs/tags/{name}", f"refs/tags/{name}^{{}}")
    refs = dict(reversed(line.split("\t")) for line in out.splitlines())
    return refs.get(f"refs/tags/{name}^{{}}") or refs.get(f"refs/tags/{name}")


def remote_branch(t, branch):
    return t.git("ls-remote", "origin", f"refs/heads/{branch}").split("\t")[0] or None


def release_branch(t, decision="Approved", gate="GateRelease", evidence=None, **approve):
    """A release approval branch from main with one hand-written record committed in the root checkout."""
    r = t.rev("refs/heads/main")
    name = f"approval/release-{r[:7]}-20261120110000"
    t.checkout("main", new=name)
    t.approve(gate, ["quoteApproval"], evidence or r, decision=decision, **approve)
    t.checkout("main")
    return name, r


def publish(t, name, gh):
    return release.publish(str(t.root), name, now=PUB_NOW, gh=gh[0])


def refused(t, name, gh, reason):
    with pytest.raises(release.ReleaseError) as e:
        publish(t, name, gh)
    assert e.value.reason == reason, e.value.message
    assert t.git("tag", "-l", "release/*") == "" and remote_branch(t, name) is None and not gh[1].exists()
    return e.value


def test_prepare_branches_from_remote_main(t, tmp_path):
    t.add_element("localOnly", "只在本地")  # local main ahead of origin/main: R must be the remote's
    r = t.rev("refs/remotes/origin/main")
    out = release.prepare(str(t.root), now=NOW, worktree=str(tmp_path / "w"))
    assert out["evidence"] == r != t.rev("refs/heads/main")
    assert out["branch"] == f"approval/release-{r[:7]}-20261120110000"
    assert t.rev(f"refs/heads/{out['branch']}") == r and os.path.isdir(out["worktree"])


def test_acTagOnApprovedRelease_and_acApprovedReleasePushed_with_record_approval(t, tmp_path, gh):
    """End to end with the real record_approval: prepare, approve GateRelease, publish."""
    prep = release.prepare(str(t.root), now=NOW, worktree=str(tmp_path / "w-release"))
    r = prep["evidence"]
    res = approval.governance_record_approval(
        T.Config(allow_roots=(str(tmp_path),)), model="procurement", gate="GateRelease", decision="Approved",
        approvedBy=BOSS, approves=[M + "quoteApproval"], branch=prep["branch"], headCommit=r, repo=str(t.root),
        now=NOW)
    assert res["evidence"] == r and res["activity"] is None
    out = publish(t, prep["branch"], gh)
    tag = f"release/20261120-{r[:7]}"
    assert out["decision"] == "批准" and out["tag"] == tag and out["tagCreated"] is True
    assert t.rev(f"refs/tags/{tag}^{{commit}}") == r and remote_tag(t, tag) == r
    assert remote_branch(t, prep["branch"]) == res["commit"]
    args = json.loads(gh[1].read_text())
    assert args[:2] == ["pr", "create"] and args[args.index("--head") + 1] == prep["branch"]
    assert args[args.index("--base") + 1] == "main" and out["pr"] == "https://example.invalid/pull/1"


def test_acNoTagOnRejectedRelease_and_acRejectedReleasePushed(t, gh):
    name, r = release_branch(t, decision="Rejected")
    out = publish(t, name, gh)
    assert out["decision"] == "驳回" and out["tag"] is None
    assert t.git("tag", "-l", "release/*") == "" and t.git("ls-remote", "--tags", "origin") == ""
    assert remote_branch(t, name) == t.rev(f"refs/heads/{name}")
    args = json.loads(gh[1].read_text())
    assert args[args.index("--head") + 1] == name


def test_acReleaseTagReused(t, gh):
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    t.tag(tag, r, annotated=True)  # already on origin, annotated: compared peeled
    out = publish(t, name, gh)
    assert out["tag"] == tag and out["tagCreated"] is False and remote_tag(t, tag) == r


def test_acReleaseTagReused_remote_only(t, gh):
    """Only the remote has the annotated tag on R: nothing new is tagged, and the tag is not pushed again."""
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    t.tag(tag, r, annotated=True)
    remote_obj = t.git("ls-remote", "--tags", "origin", f"refs/tags/{tag}").split("\t")[0]
    t.git("tag", "-d", tag)
    out = publish(t, name, gh)
    assert out["tag"] == tag and out["tagCreated"] is False and t.git("tag", "-l", tag) == ""
    assert t.git("ls-remote", "--tags", "origin", f"refs/tags/{tag}").split("\t")[0] == remote_obj
    assert remote_tag(t, tag) == r and remote_branch(t, name) == t.rev(f"refs/heads/{name}")


def test_acReleaseTagConflictStops(t, gh):
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    other = t.git("rev-parse", "refs/heads/main~1")
    t.tag(tag, other)
    with pytest.raises(release.ReleaseError) as e:
        publish(t, name, gh)
    assert e.value.reason == "release-tag-conflict"
    assert remote_tag(t, tag) == other and remote_branch(t, name) is None and not gh[1].exists()


def test_acReleaseTagConflictStops_remote_only(t, gh):
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    other = t.git("rev-parse", "refs/heads/main~1")
    t.tag(tag, other)
    t.git("tag", "-d", tag)  # only the remote has it
    with pytest.raises(release.ReleaseError) as e:
        publish(t, name, gh)
    assert e.value.reason == "release-tag-conflict" and remote_tag(t, tag) == other and remote_branch(t, name) is None


def test_acTagOnApprovedRelease_date_is_utc(t, gh):
    """23:30 at UTC-5 is the next day in UTC: the tag takes the UTC approval date."""
    name, r = release_branch(t, at="2026-11-20T23:30:00-05:00")
    out = publish(t, name, gh)
    assert out["tag"] == f"release/20261121-{r[:7]}" and remote_tag(t, out["tag"]) == r


@pytest.mark.parametrize("case", ["not-release-gate", "evidence-mismatch", "extra-commit", "merge-commit", "with-activity"])
def test_publish_refuses_anything_but_one_release_record(t, gh, case):
    if case == "not-release-gate":
        name, _ = release_branch(t, gate="GateArchitecture")
        want = "not-release-gate"
    elif case == "evidence-mismatch":
        name, _ = release_branch(t, evidence=t.git("rev-parse", "refs/heads/main~1"))
        want = "evidence-mismatch"
    elif case == "with-activity":
        r = t.rev("refs/heads/main")
        name, _ = release_branch(t, activity=dict(local=f"activity-20261120100000-{r[:7]}", head=r, base=r,
                                                  branch=f"approval/release-{r[:7]}-20261120110000"))
        want = "release-with-activity"
    elif case == "merge-commit":
        name, _ = release_branch(t)
        t.checkout("main", new="side")
        t.add_element("sideThing", "旁支")
        t.checkout(name)
        t.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        t.checkout("main")
        want = "not-one-approval-commit"
    else:  # the approval commit itself also changes a model element
        name, _ = release_branch(t)
        t.checkout(name)
        t.add_element("sneaky", "夹带")
        t.git("reset", "-q", "--soft", "HEAD~2")
        t.git("commit", "-q", "-C", name + "@{1}")
        t.checkout("main")
        want = "not-one-approval-commit"
    refused(t, name, gh, want)


@pytest.mark.parametrize("case", ["unknown-approver", "two-decisions", "future-time"])
def test_publish_runs_the_merge_time_checks_before_tagging(t, gh, case):
    """A record of the right shape that the merge-time check rejects gets no tag and nothing is pushed."""
    if case == "unknown-approver":
        name, _ = release_branch(t, approved_by=":nobodyHere")
        want = "merge-check-failed"
    elif case == "two-decisions":
        name, _ = release_branch(t, extra_ttl="")
        t.checkout(name)
        path = t.git("diff", "--name-only", "HEAD~1", "HEAD")
        t.write(path, t.read(path).replace("aisep:decision aisep:DecisionApproved ;",
                                           "aisep:decision aisep:DecisionApproved , aisep:DecisionRejected ;"))
        t.git("add", "-A")
        t.git("commit", "-q", "--amend", "--no-edit")
        t.checkout("main")
        want = "bad-record"
    else:
        name, _ = release_branch(t, at="2099-01-01T00:00:00Z")
        want = "merge-check-failed"
    refused(t, name, gh, want)


def test_publish_refuses_a_release_head_not_on_remote_main(t, gh):
    t.add_element("unpushed", "没推")  # local main ahead of origin/main
    name, _ = release_branch(t)
    refused(t, name, gh, "release-head-not-on-main")


def test_publish_refuses_a_branch_that_is_not_a_release_branch(t, gh):
    r = t.rev("refs/heads/main")
    t.checkout("main", new="approval/release-0000000-20261120110000")
    t.approve("GateRelease", ["quoteApproval"], r)
    t.checkout("main")
    refused(t, "approval/release-0000000-20261120110000", gh, "not-release-branch")
