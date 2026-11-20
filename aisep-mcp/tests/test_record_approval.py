"""S5 governance_record_approval — acceptance tests written BEFORE the implementation (docs/mcp-interface.md §5.9 as
amended by the 第四轮 review / ADR-016; §11 T21, T22, T23, T24, T25, T26, T28, and the record_approval side of T39, T40,
T43).

Fixtures: fixtures.topology.Topo (tmp repo + local bare origin; nothing is pushed to GitHub). Calls go through
fixtures.pending: while `aisep.approval` is missing the test still builds every fixture and ends as XFAIL ("实现未写").

Entry point (style of aisep/tools.py):

    aisep.approval.governance_record_approval(cfg, model, gate, decision, approvedBy, approves, branch, headCommit, *,
        expectedBaseCommit=None, slug=None, prefLabel=None, activity=None, mainRef=None, repo=None, now=None)
        gate: "GateArchitecture" …; decision: "Approved" | "Rejected"; approvedBy / approves: full IRIs or slug:local;
        branch: short name only (refs/heads/… → INVALID_ARGUMENT, G4-5); activity: {agent, sessionRef, startedAt,
        endedAt?, branch?, label?}; now: injected clock (aware UTC datetime) for generatedAtTime, the seconds in the
        record / activity IRIs (R4-7) and the default endedAt. Extra keyword arguments (evidence, generatedAt,
        baseCommit …) → INVALID_ARGUMENT with details.rejectedFields.
        → {approval: {iri, file}, activity: {iri, reused} | None, evidence, baseCommit, commit, branch, duplicate,
           gate: {result, summary}, derivedApprovalState: [{iri, before, after}], findings}

The approval-commit criterion itself (aisep.mergecheck.approval_commit_problems) is tested directly in
test_merge_check_negatives.py; here it is exercised only through record_approval (T23).

Not covered here: the concurrent-commit window of step 7 (needs an injection point between re-validation and commit),
`.git/worktrees/<n>/gitdir` pointing into another repository, two models on one branch (R2-18: the fixture has one model),
the replay "after a lost response" beyond a plain second call (the server cannot tell them apart by design).
"""
import os, subprocess
from datetime import datetime, timezone

import pytest

from aisep import tools as T
from fixtures.pending import _missing, call, error, pending, wrap_module
from fixtures.topology import AM4, GOV, M, PREFIXES, Topo, git, record_ttl

A = "aisep.approval"
F = "governance_record_approval"
NOW = datetime(2026, 11, 20, 11, 0, 0, tzinfo=timezone.utc)
MAIN = "refs/heads/main"
BOSS = M + "chiefArchitect"
BOT = M + "codingBot"


@pytest.fixture
def t(template, tmp_path):
    return Topo(template, tmp_path)


def cfg(t):
    return T.Config(allow_roots=(str(t.tmp),))


def kw(t, gate="GateArchitecture", decision="Approved", approves=("newThing",), branch="feat/x", head=None, **extra):
    d = dict(model="procurement", gate=gate, decision=decision, approvedBy=BOSS,
             approves=[a if a.startswith("http") else M + a for a in approves], branch=branch,
             headCommit=head or t.rev(f"refs/heads/{branch}"),
             repo=str(t.root), now=NOW)
    d.update(extra)
    return d


def ra(t, **k):
    return call(A, F, cfg(t), **kw(t, **k))


def ra_err(code, t, **k):
    return error(code, A, F, cfg(t), **kw(t, **k))


def activity(session="s1", agent=BOT, **extra):
    return dict(agent=agent, sessionRef=session, startedAt="2026-11-20T09:00:00Z", **extra)


def commits(t):
    return t.git("rev-list", "--all", "--count")


def feature(t, branch="feat/x", element="newThing", label="新东西"):
    t.checkout("main", new=branch)
    return t.add_element(element, label)


def added_files(t, c):
    return t.git("show", "--format=", "--name-status", c).splitlines()


def gov_listing(t, ref):
    return sorted(t.git("ls-tree", "--name-only", f"{ref}:{GOV}").splitlines())


# ================================================================== T21 atomic commit, fields

def test_T21_one_commit_one_new_file_fields(t):
    h = feature(t)
    gov_ttl = t.git("rev-parse", f"{h}:models/procurement/governance.ttl")
    n = commits(t)
    r = ra(t, activity=activity())
    if pending(r):
        return
    local = f"approval-20261120110000-architecture-{h[:7]}"
    assert int(commits(t)) == int(n) + 1 and r["commit"] == t.rev("refs/heads/feat/x") and t.rev(f"{r['commit']}^") == h
    assert added_files(t, r["commit"]) == [f"A\t{GOV}/{local}.ttl"]
    assert r["approval"] == {"iri": M + local, "file": f"{GOV}/{local}.ttl"}
    assert t.git("rev-parse", f"{r['commit']}:models/procurement/governance.ttl") == gov_ttl
    body = t.git("show", f"{r['commit']}:{GOV}/{local}.ttl")
    act = M + f"activity-20261120110000-{h[:7]}"
    assert r["activity"] == {"iri": act, "reused": False}
    assert body.count(" a aisep:ApprovalRecord") == 1 and body.count(" a aisep:AgentActivity") == 1
    assert r["evidence"] == h and f'aisep:headCommit "{h}"' in body and f'aisep:evidence "{h}"' in body
    assert r["baseCommit"] == t.merge_base(h, MAIN) and f'aisep:baseCommit "{r["baseCommit"]}"' in body
    assert '"2026-11-20T11:00:00Z"^^xsd:dateTime' in body  # injected clock, UTC, Z
    assert t.git("log", "-1", "--format=%(trailers:key=AISEP-Evidence,valueonly)", r["commit"]).strip() == h
    assert {"iri": M + "newThing", "before": "Proposed", "after": "Approved"} in r["derivedApprovalState"]


def test_T21_record_iri_uses_seconds_and_differs_by_second(t):
    """R4-7: two branches approve the same object at the same gate a second apart → different local names."""
    h = feature(t)
    t.checkout(h, new="feat/y")
    w2 = t.tmp / "w-feat-y"
    t.checkout("feat/x")
    t.git("worktree", "add", "-q", str(w2), "feat/y")
    r1 = ra(t)
    r2 = call(A, F, cfg(t), **{**kw(t, branch="feat/y", head=h), "now": datetime(2026, 11, 20, 11, 0, 1, tzinfo=timezone.utc)})
    if not pending(r2):
        assert r1["approval"]["iri"].endswith(f"approval-20261120110000-architecture-{h[:7]}")
        assert r2["approval"]["iri"].endswith(f"approval-20261120110001-architecture-{h[:7]}")


# ================================================================== T22 approvals do not count as element changes

def test_T22_diff_element_count_unchanged_governance_plus_two(t):
    from aisep.diff import model_diff
    feature(t)
    before = model_diff(cfg(t), head="refs/heads/feat/x", base=MAIN, repo=str(t.root))
    r = ra(t, activity=activity())
    after = model_diff(cfg(t), head="refs/heads/feat/x", base=MAIN, repo=str(t.root))
    if not pending(r):
        assert after["changedElementCount"] == before["changedElementCount"]
        assert after["counts"]["governance"]["added"] == before["counts"]["governance"]["added"] + 2


# ================================================================== T23 branch-head check (via record_approval)

def _after_head(t, h, kind):
    """One commit after headCommit h on feat/x, of the given shape."""
    from fixtures.topology import activity_ttl
    if kind == "code":
        return t.relabel("newThing", "新东西改")
    if kind == "stakeholder-file":
        t.write(f"{GOV}/people.ttl", PREFIXES + "\n:fakeBoss a arch:Stakeholder ;\n    arch:inModel <" + M +
                "> ;\n    skos:prefLabel \"假人\"@zh .\n")
        return t.commit_all("add a person", trailers=[f"AISEP-Evidence: {h}"])
    if kind == "append-governance-ttl":
        t.write("models/procurement/governance.ttl", record_ttl("approval-20261120100000-x", "GateDesign",
                                                                ["newThing"], h), "a")
        return t.commit_all("append a record", trailers=[f"AISEP-Evidence: {h}"])
    if kind == "add-then-delete":
        t.write("src/tmp.py", "print(1)\n"); t.commit_all("add code")
        os.remove(t.path("src/tmp.py"))
        return t.commit_all("remove code")
    if kind == "merge":
        t.checkout("main"); t.relabel("supplier", "供应商V2")
        t.checkout("feat/x"); t.git("merge", "-q", "--no-ff", "-m", "merge main", "main")
        return t.rev()
    opts = {"forged-trailer": dict(trailer="0" * 40), "non-ttl": dict(path=f"{GOV}/a.txt"),
            "subdir": dict(path=f"{GOV}/sub/a.ttl"), "symlink": dict(symlink=True),
            "two-records": dict(extra_ttl=record_ttl("approval-extra", "GateDesign", ["newThing"], h)),
            "copied-record": dict(extra_ttl=t.record_block(f"{GOV}/approval-20261119120000-architecture-audittrail.ttl")),
            "filename-mismatch": dict(path=f"{GOV}/approval-renamed.ttl")}[kind]
    return t.approve("GateArchitecture", ["newThing"], evidence=h, **opts)[0]


STALE = ["code", "stakeholder-file", "append-governance-ttl", "forged-trailer", "non-ttl", "subdir", "symlink",
         "two-records", "add-then-delete", "merge", "copied-record", "filename-mismatch"]


@pytest.mark.parametrize("kind", STALE)
def test_T23_stale_head(t, kind):
    h = feature(t)
    tip = _after_head(t, h, kind)
    assert t.rev("refs/heads/feat/x") == tip != h
    n = commits(t)
    e = ra_err("STALE_HEAD", t, gate="GateDesign", head=h)
    assert commits(t) == n and t.rev("refs/heads/feat/x") == tip
    if not pending(e):
        assert e.details.get("tip") == tip


def test_T23_two_trailers_stale_head(t):
    h = feature(t)
    t.write(f"{GOV}/approval-20261120100000-x.ttl", PREFIXES + record_ttl("approval-20261120100000-x",
                                                                          "GateArchitecture", ["newThing"], h))
    c = t.commit_all("two trailers", trailers=[f"AISEP-Evidence: {h}", f"AISEP-Evidence: {h}"])
    assert t.trailer_count(c) == 2  # the fixture really carries two trailers
    n = commits(t)
    ra_err("STALE_HEAD", t, gate="GateDesign", head=h)
    assert commits(t) == n


def test_T23_second_gate_after_approval_commit_reuses_activity(t):
    """Positive twin: after headCommit only an approval commit → the next gate succeeds; same (sessionRef, headCommit,
    branch) → the activity is reused (1 activity, 2 records)."""
    h = feature(t)
    r1 = ra(t, activity=activity())
    r2 = ra(t, gate="GateDesign", head=h, activity=activity())
    if pending(r2):
        return
    assert r2["activity"] == {"iri": r1["activity"]["iri"], "reused": True}
    tree = "\n".join(t.git("show", f"{r2['commit']}:{GOV}/{f}") for f in gov_listing(t, r2["commit"]))
    assert tree.count(" a aisep:AgentActivity") == 2  # the baseline's + this session's
    assert tree.count(" a aisep:ApprovalRecord") == 4  # baseline 2 + 2


def test_T23_activity_reuse_key_includes_branch(t):
    """第四轮复查: same sessionRef and headCommit on another branch → a new activity whose aisep:branch is that branch."""
    h = feature(t)
    r1 = ra(t, activity=activity())
    t.git("branch", "feat/y", h)
    t.git("worktree", "add", "-q", str(t.tmp / "w-feat-y"), "feat/y")
    r2 = call(A, F, cfg(t), **{**kw(t, branch="feat/y", head=h), "activity": activity()})
    if pending(r2):
        return
    assert r2["activity"]["reused"] is False and r2["activity"]["iri"] != r1["activity"]["iri"]
    assert 'aisep:branch "feat/y"' in t.git("show", f"{r2['commit']}:{r2['approval']['file']}")


def test_T23_expected_base(t):
    h = feature(t)
    n = commits(t)
    ra_err("STALE_BASE", t, expectedBaseCommit=t.c0)
    assert commits(t) == n and t.merge_base(h, MAIN) != t.c0
    ra(t, expectedBaseCommit=t.merge_base(h, MAIN))  # positive twin


@pytest.mark.parametrize("branch,reason", [("main", "protected-branch"), ("refs/heads/feat/x", None),
                                           ("release/20261120-x", None), ("feat/x~1", None)])
def test_T23_branch_must_be_a_short_branch_name(t, branch, reason):
    h = feature(t)
    t.git("tag", "release/20261120-x", h)
    n = commits(t)
    e = error("INVALID_ARGUMENT", A, F, cfg(t), **kw(t, branch=branch, head=h))
    assert commits(t) == n
    if reason and not pending(e):
        assert e.details.get("reason") == reason
    ra(t, head=h)  # positive twin: the short name


def test_T23_branch_not_checked_out_or_outside_root(t, tmp_path_factory):
    h = feature(t)
    t.git("branch", "feat/z", h)
    n = commits(t)
    ra_err("BRANCH_NOT_CHECKED_OUT", t, branch="feat/z", head=h)
    outside = tmp_path_factory.mktemp("elsewhere") / "w"
    t.git("worktree", "add", "-q", str(outside), "feat/z")
    ra_err("PATH_OUTSIDE_ROOT", t, branch="feat/z", head=h)
    assert commits(t) == n and t.rev("refs/heads/feat/z") == h


# ================================================================== T24 gate threshold

@pytest.mark.parametrize("decision", ["Approved", "Rejected"])
def test_T24_gate_failed_only_for_approved(t, decision):
    feature(t)
    t.write("models/procurement/legacy.ttl", PREFIXES + "\n:quoteApproval am4:accesses :quotation .\n")
    h = t.commit_all("legacy direct triple (--no-verify)")
    assert T.model_gate(cfg(t), repo=str(t.root))["result"] == "FAIL"
    n = commits(t)
    if decision == "Approved":
        ra_err("GATE_FAILED", t, head=h)
        assert commits(t) == n
    else:
        r = ra(t, decision="Rejected", head=h)
        if not pending(r):
            assert int(commits(t)) == int(n) + 1


# ================================================================== T25 dedupe, refused fields

@pytest.mark.parametrize("with_activity", [False, True])
def test_T25_replay_is_duplicate(t, with_activity):
    h = feature(t)
    extra = {"activity": activity()} if with_activity else {}
    r1 = ra(t, **extra)
    n = commits(t)
    r2 = ra(t, head=h, **extra)
    assert commits(t) == n or pending(r2)
    if not pending(r2):
        assert r2["duplicate"] is True and r2["approval"] == r1["approval"]


@pytest.mark.parametrize("field,value", [("evidence", "0" * 40), ("baseCommit", "0" * 40),
                                         ("generatedAt", "2026-11-20T00:00:00Z")])
def test_T25_refused_fields(t, field, value):
    feature(t)
    n = commits(t)
    e = ra_err("INVALID_ARGUMENT", t, **{field: value})
    assert commits(t) == n
    if not pending(e):
        assert field in e.details["rejectedFields"]


# ================================================================== T26 rollback

def _hook(t, body):
    d = t.tmp / "hooks"
    d.mkdir(exist_ok=True)
    (d / "pre-commit").write_text("#!/bin/sh\n" + body + "\n")
    os.chmod(d / "pre-commit", 0o755)
    t.git("config", "core.hooksPath", str(d))


def test_T26_failing_hook_commit_failed_clean(t):
    h = feature(t)
    _hook(t, "echo refused by hook >&2; exit 1")
    ra_err("COMMIT_FAILED", t)
    assert t.git("status", "--porcelain") == "" and t.rev("refs/heads/feat/x") == h
    t.git("config", "--unset", "core.hooksPath")
    ra(t)  # positive twin


def test_T26_hook_rewrites_record_conflict_keeps_file(t):
    h = feature(t)
    _hook(t, f'for f in {GOV}/approval-20261120110000-*.ttl; do echo "# hook" >> "$f"; done; exit 1')
    ra_err("CONFLICT", t)
    files = [f for f in os.listdir(t.path(GOV)) if f.startswith("approval-20261120110000-")]
    assert t.rev("refs/heads/feat/x") == h
    if files:  # exists only once the implementation wrote it
        assert open(t.path(f"{GOV}/{files[0]}"), encoding="utf-8").read().endswith("# hook\n")
        assert t.git("ls-files", "--", f"{GOV}/{files[0]}") == ""


def test_T26_dirty_models(t):
    h = feature(t)
    t.write(AM4, "\n# uncommitted\n", "a")
    n = commits(t)
    ra_err("DIRTY_WORKTREE", t, head=h)
    assert commits(t) == n


@pytest.mark.parametrize("staged", [False, True])
def test_T26_orphan_record_file(t, staged):
    h = feature(t)
    rel = f"{GOV}/approval-20261120100000-architecture-{h[:7]}.ttl"
    t.write(rel, PREFIXES + record_ttl(f"approval-20261120100000-architecture-{h[:7]}", "GateArchitecture",
                                       ["newThing"], h))
    if staged:
        t.git("add", "--", rel)
    e = ra_err("DIRTY_WORKTREE", t, head=h)
    if not pending(e):
        assert e.details.get("orphanApproval") is True


# ================================================================== refusals of the input table (no commit, no file)

@pytest.mark.parametrize("over,code", [
    (dict(model="nosuch"), "MODEL_NOT_FOUND"),
    (dict(gate="GateFoo"), "GATE_UNKNOWN"),
    (dict(approves=("notThere",)), "ELEMENT_NOT_FOUND"),
    (dict(activity=dict(agent=BOT, sessionRef="s1", startedAt="yesterday")), "INVALID_DATETIME"),
    (dict(activity=dict(agent=BOT, sessionRef="s1", startedAt="2026-11-20T12:00:00Z", endedAt="2026-11-20T10:00:00Z")),
     "ACTIVITY_TIME_ORDER"),
    (dict(activity=dict(agent=BOT, sessionRef="s1", startedAt="2026-11-20T09:00:00Z", branch="feat/other")),
     "INVALID_ARGUMENT"),
])
def test_input_refusals_write_nothing(t, over, code):
    feature(t)
    n, st = commits(t), t.git("status", "--porcelain")
    ra_err(code, t, **over)
    assert commits(t) == n and t.git("status", "--porcelain") == st


# ================================================================== T28 PROV minimal stub (module side)

def test_T28_ai_agent_associated_ok_but_not_approver(t):
    """Q4-C: an activity may be associated with an aisep:AIAgent; an AIAgent may not approve (APPROVER_NOT_ALLOWED)."""
    declared = subprocess.run(["grep", "-rqE", r"^aisep:AIAgent\s+a\s", str(t.root / "modules")]).returncode == 0
    t.write("models/procurement/governance.ttl", "\n:claudeBot a aisep:AIAgent ;\n    arch:inModel <" + M +
            "> ;\n    skos:prefLabel \"Claude 代理\"@zh .\n", "a")
    t.commit_all("an AI agent")
    feature(t)
    if not declared:
        _missing.append("实现未写：PROV 最小桩（模块未声明 aisep:AIAgent，T28）")
        return
    assert T.model_gate(cfg(t), repo=str(t.root))["result"] == "PASS"
    ra(t, activity=activity(agent=M + "claudeBot"))
    error("APPROVER_NOT_ALLOWED", A, F, cfg(t), **{**kw(t, gate="GateDesign"), "approvedBy": M + "claudeBot"})


# ================================================================== T39 / T40 record_approval side (U4①)

def _release_branch(t, r):
    name = f"approval/release-{r[:7]}-20261120110000"
    t.git("worktree", "add", "-q", "-b", name, str(t.tmp / "w-release"), r)
    return name


def test_T40_release_success_evidence_r_no_activity(t):
    r = t.rev(MAIN)
    name = _release_branch(t, r)
    res = call(A, F, cfg(t), **kw(t, gate="GateRelease", approves=("quoteApproval",), branch=name, head=r))
    if pending(res):
        return
    assert res["evidence"] == r and res["activity"] is None
    assert "AgentActivity" not in t.git("show", f"{res['commit']}:{res['approval']['file']}")


@pytest.mark.parametrize("case", ["gate-architecture", "gate-architecture-with-activity", "release-with-activity"])
def test_T40_mainline_head_rules(t, case):
    r = t.rev(MAIN)
    name = _release_branch(t, r)
    gate = "GateRelease" if case == "release-with-activity" else "GateArchitecture"
    extra = {"activity": activity()} if "activity" in case else {}
    n = commits(t)
    e = error("INVALID_ARGUMENT", A, F, cfg(t), **kw(t, gate=gate, approves=("quoteApproval",), branch=name, head=r),
              **extra)
    assert commits(t) == n
    if not pending(e):
        if case == "release-with-activity":
            assert "activity" in e.details["rejectedFields"]
        else:
            assert e.details["reason"] == "mainline-head-gate-not-release"


def test_T40_release_head_only_on_feature(t):
    h = feature(t)
    n = commits(t)
    e = ra_err("INVALID_ARGUMENT", t, gate="GateRelease", head=h)
    assert commits(t) == n
    if not pending(e):
        assert e.details["reason"] == "release-head-not-on-main"


def test_T39_gate_architecture_on_release_approval_commit(t):
    """核对轮 4: headCommit = A (the release approval commit, effective content commit R) → still mainline."""
    r = t.rev(MAIN)
    name = _release_branch(t, r)
    w = t.tmp / "w-release"
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@example.invalid")
    from fixtures.topology import PREFIXES as P
    local = f"approval-20261120100000-release-{r[:7]}"
    (w / GOV / f"{local}.ttl").write_text(P + record_ttl(local, "GateRelease", ["quoteApproval"], r), encoding="utf-8")
    git(w, "add", "-A"); git(w, "commit", "-q", "-m", "release approval", "--trailer", f"AISEP-Evidence: {r}")
    a = git(w, "rev-parse", "HEAD")
    e = error("INVALID_ARGUMENT", A, F, cfg(t), **kw(t, approves=("quoteApproval",), branch=name, head=a))
    if not pending(e):
        assert e.details["reason"] == "mainline-head-gate-not-release"


def test_T39_branch_from_latest_main_with_old_r_stale(t):
    r = t.rev(MAIN)
    t.checkout("main"); m = t.add_element("later", "之后的提交")
    name = _release_branch(t, m)
    n = commits(t)
    ra_err("STALE_HEAD", t, gate="GateRelease", approves=("quoteApproval",), branch=name, head=r)
    assert commits(t) == n


# ================================================================== T43 one record per file (record_approval side)

def test_T43_two_branches_each_one_file_merge_clean(t):
    h = feature(t, "feat/a", "thingA", "甲")
    t.checkout("main", new="feat/b")
    hb = t.relabel("supplier", "供应商V2")
    t.checkout("feat/a")
    t.git("worktree", "add", "-q", str(t.tmp / "w-feat-b"), "feat/b")
    ra_ = call(A, F, cfg(t), **kw(t, approves=("thingA",), branch="feat/a", head=h))
    rb = call(A, F, cfg(t), **{**kw(t, approves=("supplier",), branch="feat/b", head=hb),
                               "now": datetime(2026, 11, 20, 11, 0, 5, tzinfo=timezone.utc)})
    if pending(rb):
        return
    for res in (ra_, rb):
        assert len(added_files(t, res["commit"])) == 1 and added_files(t, res["commit"])[0].startswith(f"A\t{GOV}/")
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/a", "feat/a")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/b", "feat/b")
    assert os.path.isfile(t.path(ra_["approval"]["file"])) and os.path.isfile(t.path(rb["approval"]["file"]))


wrap_module(globals())
