"""U2 (docs/mcp-interface.md §3.3, §5.1, §5.9 step 5, T43; appendix D row "记录文件放在 models/<slug>/governance/ 子目录"):
one approval record per file under models/<slug>/governance/. These tests pin the READ side outside slice S5: the unified
file set, model_gate (workspace, ref, model filter, and the CLI gate the pre-commit hook runs), model_diff (ref and
worktree mode) and the approvalState derivation all see the record files in the subdirectory; after two branches each
approve and both merge, both records derive and governance.ttl's own record is untouched. Writing the record file
(record_approval steps 5/7/8) is slice S5 and is not exercised here; approval commits are built by fixtures.topology
in the exact shape S5 produces."""
import os

import pytest

from conftest import run_cli
from fixtures.topology import GOV, M, Topo
from aisep import diff, gitio
from aisep import tools as T

CFG = T.Config()
ARCH = "https://meta.linked.archi/core#"
STATE_Q = "SELECT ?s ?st WHERE { ?s arch:approvalState ?st }"
# a hand-written approvalState is an L1 Violation (spec §6.6, D10) whatever file it is in: a probe for "is this file read"
PROBE = ("@prefix arch: <https://meta.linked.archi/core#> .\n@prefix : <https://aisep.example/model/procurement/> .\n"
         ":supplier arch:approvalState arch:Approved .\n")


@pytest.fixture
def t(template, tmp_path):
    return Topo(template, tmp_path)


def states(t, ref=None):
    rows = T.model_query(CFG, STATE_Q, repo=str(t.root), ref=ref)["rows"]
    return {r["s"]["value"][len(M):]: r["st"]["value"].rsplit("#", 1)[1] for r in rows}


def handwritten(res):
    return [f for f in res["findings"] if f["severity"] == "Violation" and "hand-written arch:approvalState" in f["message"]]


def test_U2_baseline_records_live_in_subdir_and_derive(t):
    """Topo's baseline puts its two records in governance/ (not governance.ttl): both sources derive from them."""
    assert {f for f in gitio.model_files(str(t.root)) if f.startswith(GOV + "/")} == {
        f"{GOV}/approval-20261119120000-architecture-audittrail.ttl", f"{GOV}/approval-20261119130000-requirements-rejected.ttl"}
    for ref in (None, "main"):
        s = states(t, ref)
        assert s["auditTrail"] == "Approved", ref       # record only in governance/<local>.ttl
        assert s["supplier"] == "Rejected", ref         # Rejected record only in governance/<local>.ttl
        assert s["quoteApproval"] == "Approved", ref    # the old record in governance.ttl still derives


@pytest.mark.parametrize("tracked", [False, True])
def test_U2_gate_reads_subdir_files(t, tracked):
    """model_gate on the workspace, with a model filter, on a ref, and the CLI gate (the pre-commit hook) all read a
    file under governance/; the clean twin passes."""
    for res in (T.model_gate(CFG, repo=str(t.root)), T.model_gate(CFG, repo=str(t.root), ref="main")):
        assert res["result"] == "PASS", res["findings"]
    t.checkout("main", new="feat/probe")
    t.write(f"{GOV}/probe.ttl", PROBE)
    if tracked:
        t.commit_all("probe")
        r = T.model_gate(CFG, repo=str(t.root), ref="feat/probe")
        assert r["result"] == "FAIL" and handwritten(r), r["findings"]
    for r in (T.model_gate(CFG, repo=str(t.root)), T.model_gate(CFG, repo=str(t.root), model="procurement")):
        assert r["result"] == "FAIL" and handwritten(r), r["findings"]
    rc, out, err = run_cli(t.root, "gate")
    assert rc != 0 and "hand-written arch:approvalState" in out, out + err


def test_U2_diff_lists_subdir_record(t):
    """model_diff sees a record file under governance/: committed (ref mode), and uncommitted (worktree mode)."""
    t.checkout("main", new="feat/a")
    h = t.add_element("thingA", "甲")
    _, _, rec = t.approve("GateArchitecture", ["thingA"], evidence=h)
    want = {(rec, "governance", "added"), (M + "thingA", "element", "added")}
    for head in ("feat/a", {"worktree": "feat/a"}):
        items = diff.model_diff(CFG, head, repo=str(t.root), detail="items")["items"]
        assert want <= {(i["iri"], i["kind"], i["change"]) for i in items}, head
    t.write(f"{GOV}/approval-20261120120000-architecture-uncommitted.ttl",
            t.read(f"{GOV}/{rec[len(M):]}.ttl").replace(rec[len(M):], "approval-20261120120000-architecture-uncommitted"))
    items = diff.model_diff(CFG, {"worktree": "feat/a"}, repo=str(t.root), detail="items")["items"]
    assert (M + "approval-20261120120000-architecture-uncommitted", "governance", "added") in {
        (i["iri"], i["kind"], i["change"]) for i in items}


def test_T43_both_records_derive_after_both_merges(t):
    """T43: two branches each approve a different element (one new governance/ file each); after both merge into main,
    both records derive on main (ref and workspace), governance.ttl is byte-identical and its record still derives."""
    gov_ttl = "models/procurement/governance.ttl"
    gov_before = t.read(gov_ttl)
    before = states(t, "main")
    t.checkout("main", new="feat/a")
    t.approve("GateArchitecture", ["thingA"], evidence=t.add_element("thingA", "甲"))
    t.checkout("main", new="feat/b")
    t.approve("GateArchitecture", ["thingB"], evidence=t.add_element("thingB", "乙", rel="models/procurement/b.ttl"),
              at="2026-11-20T11:05:00Z")
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/a", "feat/a")
    t.git("merge", "-q", "--no-ff", "-m", "Merge feat/b", "feat/b")
    assert t.read(gov_ttl) == gov_before
    assert len([f for f in os.listdir(t.path(GOV)) if f.endswith(".ttl")]) == 4
    for ref in (None, "main"):
        s = states(t, ref)
        assert s["thingA"] == s["thingB"] == "Approved", ref
        assert s["quoteApproval"] == before["quoteApproval"] == "Approved", ref
        assert {k: v for k, v in s.items() if k in before} == before, ref
        assert T.model_gate(CFG, repo=str(t.root), ref=ref)["result"] == "PASS"
