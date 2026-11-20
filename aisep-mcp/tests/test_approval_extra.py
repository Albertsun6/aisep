"""S5 cases test_record_approval.py leaves out (its docstring lists them): the concurrent-commit window of §5.9 step 7,
the lock shared with the write tools (T13: approval vs agent write on the same worktree), and one successful call
through the real MCP stdio server."""
import os, subprocess, sys, textwrap
from datetime import datetime, timezone

import anyio
import pytest
from mcp import Client, StdioServerParameters

from conftest import ROOT
from fixtures.topology import GOV, M, Topo
from aisep import approval, tools, writer
from aisep.errors import AisepError

NOW = datetime(2026, 11, 20, 11, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def t(template, tmp_path):
    topo = Topo(template, tmp_path)
    topo.checkout("main", new="feat/x")
    topo.head = topo.add_element("newThing", "新东西")
    return topo


def call(t, **kw):
    args = dict(model="procurement", gate="GateArchitecture", decision="Approved", approvedBy=M + "chiefArchitect",
                approves=[M + "newThing"], branch="feat/x", headCommit=t.head, repo=str(t.root), now=NOW)
    args.update(kw)
    return approval.governance_record_approval(tools.Config(allow_roots=(str(t.tmp),)), **args)


def test_concurrent_commit_between_recheck_and_commit_is_undone(t, monkeypatch):
    """Step 7: an agent's own `git commit` lands after the locked re-check, before ours. Our commit A then has the
    wrong parent: it is taken back with a compare-and-swap update-ref, the agent's commit C stays, STALE_HEAD."""
    real = approval._write_new

    def racing(w, rel, data):
        t.write("src/agent.py", "print('agent')\n")
        c = t.commit_all("agent commit in the window")
        racing.c = c
        return real(w, rel, data)
    monkeypatch.setattr(approval, "_write_new", racing)
    with pytest.raises(AisepError) as e:
        call(t)
    assert e.value.code == "STALE_HEAD" and e.value.details["reason"] == "concurrent-commit"
    assert t.rev("refs/heads/feat/x") == racing.c                        # C kept, our commit gone
    assert not [f for f in os.listdir(t.path(GOV)) if f.startswith("approval-20261120")]  # record file removed
    assert t.git("status", "--porcelain") == ""


def test_write_lock_is_shared_with_the_write_tools(t):
    """T13: while a write tool holds the worktree's lock, record_approval answers LOCKED and commits nothing."""
    lock = os.path.join(t.git("rev-parse", "--absolute-git-dir"), writer.LOCK_NAME)
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import fcntl, os, sys
        fd = os.open({lock!r}, os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX); print("held", flush=True); sys.stdin.read()""")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)  # holds until we close its stdin, not for a duration
    try:
        assert holder.stdout.readline().strip() == "held"
        n = t.git("rev-list", "--all", "--count")
        with pytest.raises(AisepError) as e:
            call(t)
        assert e.value.code == "LOCKED" and e.value.retryable
        assert t.git("rev-list", "--all", "--count") == n and t.git("status", "--porcelain") == ""
    finally:
        holder.stdin.close()
        holder.wait()
    assert call(t)["duplicate"] is False  # positive twin: lock released


def test_through_the_mcp_server(t):
    """Workbench profile over stdio: one approval, one commit with exactly one new governance file."""
    async def go():
        p = StdioServerParameters(command=sys.executable, args=[
            "-m", "aisep.server", "--profile", "workbench", "--repo", str(t.root), "--allow-root", str(t.tmp)],
            cwd=str(t.root), env=dict(os.environ, PYTHONPATH=ROOT))
        async with Client(p) as c:
            return await c.call_tool("governance_record_approval", {
                "model": "procurement", "gate": "GateArchitecture", "decision": "Approved",
                "approvedBy": "procurement:chiefArchitect", "approves": ["procurement:newThing"], "branch": "feat/x",
                "headCommit": t.head, "activity": {"agent": "procurement:codingBot", "sessionRef": "ao-1",
                                                   "startedAt": "2026-11-20T09:00:00Z"}})
    r = anyio.run(go)
    assert r.is_error is False, r.content[0].text
    sc = r.structured_content
    assert sc["commit"] == t.rev("refs/heads/feat/x") and t.rev(f"{sc['commit']}^") == t.head
    assert t.git("show", "--format=", "--name-status", sc["commit"]).splitlines() == [f"A\t{sc['approval']['file']}"]
    assert sc["activity"]["reused"] is False and {"iri": M + "newThing", "before": "Proposed", "after": "Approved"} \
        in sc["derivedApprovalState"]


def test_evidence_is_head_commit_not_branch_tip(t):
    """A second gate after an approval commit: the tip is that commit, evidence must still be headCommit."""
    call(t)
    tip = t.rev("refs/heads/feat/x")
    assert tip != t.head
    r = call(t, gate="GateDesign")
    assert r["evidence"] == t.head
    assert f'aisep:evidence "{t.head}"' in t.git("show", f"{r['commit']}:{r['approval']['file']}")
    assert t.git("log", "-1", "--format=%(trailers:key=AISEP-Evidence,valueonly)", r["commit"]).strip() == t.head


def test_activity_with_same_session_and_head_on_another_branch_is_not_reused(t):
    """第四轮复查 key (sessionRef, headCommit, branch): feat/y starts after feat/x's approval commit, so its tip already
    holds feat/x's activity (same session, same head) — it must get its own activity carrying branch feat/y."""
    act = {"agent": M + "codingBot", "sessionRef": "s1", "startedAt": "2026-11-20T09:00:00Z"}
    r1 = call(t, activity=act)
    t.git("branch", "feat/y", r1["commit"])
    t.git("worktree", "add", "-q", str(t.tmp / "w-y"), "feat/y")
    r2 = call(t, branch="feat/y", gate="GateDesign", activity=act)
    assert r2["activity"]["reused"] is False and r2["activity"]["iri"] != r1["activity"]["iri"]
    assert 'aisep:branch "feat/y"' in t.git("show", f"{r2['commit']}:{r2['approval']['file']}")


def test_main_ref_with_slash_is_protected(t):
    """Review minor: mainRef release/1.0 resolves to refs/remotes/origin/release/1.0; branch release/1.0 is that main
    branch and is refused, while a branch merely ending in its last segment (1.0) is not."""
    t.git("branch", "release/1.0", "main")
    t.git("update-ref", "refs/remotes/origin/release/1.0", "main")
    with pytest.raises(AisepError) as e:
        call(t, branch="release/1.0", mainRef="release/1.0")
    assert e.value.code == "INVALID_ARGUMENT" and e.value.details.get("reason") == "protected-branch"
    t.git("branch", "1.0", "main")
    with pytest.raises(AisepError) as e:
        call(t, branch="1.0", mainRef="release/1.0")
    assert e.value.details.get("reason") != "protected-branch"
