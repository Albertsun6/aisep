"""spec §6.6 / R4-5 (ADR-016): arch:approvalState is derived only for approvable elements. Approval records, agent
activities and arch:Stakeholders are arch:Elements but can never be approved, so they get no approvalState (the
workbench ELEMENTS_QUERY lists exactly the subjects that have one, docs/mcp-interface.md §8)."""
import os, tempfile

from aisep import core as T

HDR = """@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/t/> .
:t a arch:Model ; skos:prefLabel "测试模型"@zh .
:x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .
:boss a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "架构师"@zh .
:act a aisep:AgentActivity ; arch:inModel :t ; skos:prefLabel "AI 活动"@zh ;
    prov:wasAssociatedWith :boss ;
    prov:startedAtTime "2026-11-20T10:00:00Z"^^xsd:dateTime ; prov:endedAtTime "2026-11-20T11:00:00Z"^^xsd:dateTime ;
    aisep:sessionRef "s1" ; aisep:branch "claude/t" ;
    aisep:baseCommit "0123456789abcdef0123456789abcdef01234567" ;
    aisep:headCommit "89abcdef0123456789abcdef0123456789abcdef" .
:rec a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :boss ;
    aisep:approves :x ; aisep:activity :act ;
    aisep:evidence "89abcdef0123456789abcdef0123456789abcdef" ; prov:generatedAtTime "2026-11-20T12:00:00Z"^^xsd:dateTime .
"""
M = "https://aisep.example/model/t/"


def states(body=""):
    d = tempfile.mkdtemp(prefix="aisep-derive-scope-")
    p = os.path.join(d, "t.ttl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(HDR + body)
    c = T.Ctx(T.discover(), [p])
    T.run_check(c)
    violations = [t for s, _, t in c.problems if s == "Violation"]
    return {s.value[len(M):]: T.short(o.value) for s, p, o, _ in c.built if p.value == T.ARCH + "approvalState"}, violations


def test_only_approvable_elements_get_a_state():
    got, violations = states()
    assert violations == []  # a valid model: the record (with its activity) is legal
    assert got == {"x": "arch:Approved"}, got


def test_illegal_record_naming_an_activity_or_stakeholder_derives_nothing_for_it():
    # R4-5: such a record is illegal (L1) and ignored by the derivation, so its target stays without a state
    body = """:rec2 a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录二"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :boss ;
    aisep:approves :act , :boss ;
    aisep:evidence "89abcdef0123456789abcdef0123456789abcdef" ; prov:generatedAtTime "2026-11-20T13:00:00Z"^^xsd:dateTime .
"""
    got, violations = states(body)
    assert any("not an approvable target" in v for v in violations), violations
    assert "act" not in got and "boss" not in got and "rec2" not in got, got
