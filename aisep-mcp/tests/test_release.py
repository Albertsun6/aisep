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


def release_branch(t, decision="Approved", gate="GateRelease", evidence=None):
    """A release approval branch from main with one hand-written record committed in the root checkout."""
    r = t.rev("refs/heads/main")
    name = f"approval/release-{r[:7]}-20261120110000"
    t.checkout("main", new=name)
    t.approve(gate, ["quoteApproval"], evidence or r, decision=decision)
    t.checkout("main")
    return name, r


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
    out = release.publish(str(t.root), prep["branch"], gh=gh[0])
    tag = f"release/20261120-{r[:7]}"
    assert out["decision"] == "批准" and out["tag"] == tag and out["tagCreated"] is True
    assert t.rev(f"refs/tags/{tag}^{{commit}}") == r and remote_tag(t, tag) == r
    assert remote_branch(t, prep["branch"]) == res["commit"]
    args = json.loads(gh[1].read_text())
    assert args[:2] == ["pr", "create"] and args[args.index("--head") + 1] == prep["branch"]
    assert args[args.index("--base") + 1] == "main" and out["pr"] == "https://example.invalid/pull/1"


def test_acNoTagOnRejectedRelease_and_acRejectedReleasePushed(t, gh):
    name, r = release_branch(t, decision="Rejected")
    out = release.publish(str(t.root), name, gh=gh[0])
    assert out["decision"] == "驳回" and out["tag"] is None
    assert t.git("tag", "-l", "release/*") == "" and t.git("ls-remote", "--tags", "origin") == ""
    assert remote_branch(t, name) == t.rev(f"refs/heads/{name}")
    args = json.loads(gh[1].read_text())
    assert args[args.index("--head") + 1] == name


def test_acReleaseTagReused(t, gh):
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    t.tag(tag, r, annotated=True)  # already on origin, annotated: compared peeled
    out = release.publish(str(t.root), name, gh=gh[0])
    assert out["tag"] == tag and out["tagCreated"] is False and remote_tag(t, tag) == r


def test_acReleaseTagConflictStops(t, gh):
    name, r = release_branch(t)
    tag = f"release/20261120-{r[:7]}"
    other = t.git("rev-parse", "refs/heads/main~1")
    t.tag(tag, other)
    with pytest.raises(release.ReleaseError) as e:
        release.publish(str(t.root), name, gh=gh[0])
    assert e.value.reason == "release-tag-conflict"
    assert remote_tag(t, tag) == other and remote_branch(t, name) is None and not gh[1].exists()


@pytest.mark.parametrize("case", ["not-release-gate", "evidence-mismatch", "extra-commit"])
def test_publish_refuses_anything_but_one_release_record(t, gh, case):
    if case == "not-release-gate":
        name, _ = release_branch(t, gate="GateArchitecture")
        want = "not-release-gate"
    elif case == "evidence-mismatch":
        name, _ = release_branch(t, evidence=t.git("rev-parse", "refs/heads/main~1"))
        want = "evidence-mismatch"
    else:
        name, _ = release_branch(t)
        t.checkout(name)
        t.add_element("sneaky", "夹带")
        t.checkout("main")
        want = "not-one-approval-commit"
    with pytest.raises(release.ReleaseError) as e:
        release.publish(str(t.root), name, gh=gh[0])
    assert e.value.reason == want
    assert t.git("tag", "-l", "release/*") == "" and remote_branch(t, name) is None and not gh[1].exists()
