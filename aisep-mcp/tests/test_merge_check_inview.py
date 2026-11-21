"""Merge-time check, R3 口径 (第四轮复评 R3 选 A, Albert 2026-11-21, ADR-017; docs/metamodel-spec.md, docs/mcp-interface.md
§5.8 第 6 步): `arch:inView` 计入视图、不计入元素. A normal PR that only puts an element Approved on main into a new,
valid view (`:v1` + `:<element> arch:inView :v1`) does not modify that element, so merge_check returns [].

The control twin relabels the same approved element on the same baseline and must be rejected with
`unapproved-change-to-approved` — proof that the scenario does see element changes (no false green)."""
from datetime import datetime, timezone

from fixtures.topology import AM4, M, Topo

from aisep import mergecheck

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
MAIN = "refs/heads/main"
VP = "<https://meta.linked.archi/archimate4/viewpoints#ApplicationCooperationViewpoint>"


def _approved_on_main(t, local):
    """Baseline sanity: :local is Approved on main (Topo.baseline approves :auditTrail)."""
    assert f":{local} a " in t.read(AM4)
    assert "aisep:approves :" + local in t.read(
        "models/procurement/governance/approval-20261119120000-architecture-audittrail.ttl")


def test_r3_adr017_inview_into_new_view_is_not_change_to_approved_element(template, tmp_path):
    """R3 口径 (ADR-017): adding approved :auditTrail to a new view via arch:inView alone → merge_check == []."""
    t = Topo(template, tmp_path)
    _approved_on_main(t, "auditTrail")
    t.checkout("main", new="feat/view")
    t.write(AM4, f"\n:v1 a arch:Diagram ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"视图\"@zh ;\n"
                 f"    arch:viewConformsToViewpoint {VP} .\n:auditTrail arch:inView :v1 .\n", "a")
    head = t.commit_all("add view :v1 containing approved :auditTrail")
    problems = mergecheck.merge_check(str(t.root), head, MAIN, head_ref="feat/view", now=NOW)
    assert problems == [], problems


def test_r3_adr017_control_relabel_approved_element_is_rejected(template, tmp_path):
    """R3 口径 (ADR-017) 对照组: relabelling the same approved :auditTrail → unapproved-change-to-approved."""
    t = Topo(template, tmp_path)
    _approved_on_main(t, "auditTrail")
    t.checkout("main", new="feat/relabel")
    head = t.relabel("auditTrail", "审计轨迹V2")
    problems = mergecheck.merge_check(str(t.root), head, MAIN, head_ref="feat/relabel", now=NOW)
    hits = [p for p in problems if p["reason"] == "unapproved-change-to-approved"]
    assert hits, problems
    assert M + "auditTrail" in {p.get("iri") for p in hits}, hits
