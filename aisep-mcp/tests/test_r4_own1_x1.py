"""Two R4 re-review defects (spec §6.6 approvalState derivation, ADR-016; L0/L1 structural checks).

OWN-1: an otherwise well-formed aisep:ApprovalRecord whose aisep:approves names a METAMODEL term — typed in the
ontology (module / vendor) graphs but not a subject of any model source file, e.g. arch:Element — must be illegal
(approval_problems lists it) and must not derive an arch:approvalState for that term. Controls: the same record on a
real model element stays legal and derives a state; a record on an IRI that is neither a source subject nor typed in
the ontology ("target does not exist") keeps the current reading (not rejected by approval_problems; the merge-time
check judges it against the evidence snapshot).

X1: a blank node carrying arch:inModel in a model source must not crash the build (today: ValueError "No scheme found
in an absolute IRI"); model_gate returns FAIL with a structured Violation pointing at the blank node / inModel.
"""
import os, re, tempfile

import pytest

from aisep import core as T, tools
from aisep.mergecheck import CFG

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
"""
M = "https://aisep.example/model/t/"
META_TERM = "https://meta.linked.archi/core#Element"
GHOST = M + "ghostThing"


def record(local, target, at="2026-11-20T12:00:00Z"):
    return f""":{local} a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录 {local}"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :boss ;
    aisep:approves <{target}> ;
    aisep:evidence "89abcdef0123456789abcdef0123456789abcdef" ; prov:generatedAtTime "{at}"^^xsd:dateTime .
"""


def build(body):
    d = tempfile.mkdtemp(prefix="aisep-own1-")
    p = os.path.join(d, "t.ttl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(HDR + body)
    c = T.Ctx(T.discover(), [p])
    T.run_check(c)
    states = {s.value: o.value for s, p_, o, _ in c.built if p_.value == T.ARCH + "approvalState"}
    return c, states


# ------------------------------------------------------------------ OWN-1

def test_own1_metamodel_term_is_typed_in_ontology_not_in_sources():
    """Precondition guard: arch:Element really is an ontology-typed term and not a source subject, so the two tests
    below exercise the OWN-1 shape and not some other path."""
    c, _ = build(record("recMeta", META_TERM))
    onto_typed = c.rows(f"SELECT ?t WHERE {{ GRAPH ?g {{ <{META_TERM}> a ?t }} {c.onto_graph_filter()} }}")
    src_subject = c.rows(f"SELECT ?p WHERE {{ GRAPH ?g {{ <{META_TERM}> ?p ?o }} {c.src_graph_filter()} }}")
    assert onto_typed and not src_subject


def test_own1_record_approving_metamodel_term_is_illegal():
    """(a) approval_problems() must list the record that approves arch:Element."""
    c, _ = build(record("recMeta", META_TERM))
    assert M + "recMeta" in c.approval_problems(), c.approval_problems()


def test_own1_metamodel_term_gets_no_approval_state():
    """(b) the build must not derive any arch:approvalState for the metamodel term."""
    _, states = build(record("recMeta", META_TERM))
    assert META_TERM not in states, states


def test_own1_control_real_element_still_legal_and_approved():
    """Anti-false-green: the identical record on a real model element is legal and derives arch:Approved."""
    c, states = build(record("recReal", M + "x"))
    assert M + "recReal" not in c.approval_problems(), c.approval_problems()
    assert states.get(M + "x") == T.ARCH + "Approved", states


def test_own1_control_nonexistent_target_keeps_current_reading():
    """Anti-over-fix: a target that is neither a source subject nor ontology-typed is NOT rejected by
    approval_problems (current reading: the merge-time check judges it against the evidence snapshot)."""
    c, _ = build(record("recGhost", GHOST))
    assert M + "recGhost" not in c.approval_problems(), c.approval_problems()


# ------------------------------------------------------------------ X1

PM = "https://aisep.example/model/procurement/"
X1_PREFIXES = """@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix arch:  <https://meta.linked.archi/core#> .
@prefix am4:   <https://meta.linked.archi/archimate4/onto#> .
@prefix :      <https://aisep.example/model/procurement/> .
"""
BLANK_CASES = {
    # the simplest form: a blank node that claims model membership
    "bare_blank_element": f'[] a am4:BusinessObject ; arch:inModel <{PM}> ; skos:prefLabel "匿名对象"@zh .\n',
    # the re-review shape: a blank relationship nested under a named subject
    "nested_blank_relationship": (f':quotation skos:note [ a am4:Association ; arch:source :supplier ; '
                                  f'arch:target :quotation ; arch:inModel <{PM}> ] .\n'),
}


@pytest.mark.parametrize("case", sorted(BLANK_CASES))
def test_x1_blank_node_with_inmodel_is_a_violation_not_a_crash(repo, case):
    """Expected: model_gate does not raise; result is FAIL; at least one finding with severity "Violation" whose
    message mentions inModel or a blank node (case-insensitive: "inModel" / "blank" / "bnode" / "空白节点")."""
    rel = os.path.join(str(repo), "models", "procurement", "x1-blank.ttl")
    with open(rel, "w", encoding="utf-8") as f:
        f.write(X1_PREFIXES + BLANK_CASES[case])
    g = tools.model_gate(CFG, repo=str(repo))
    assert g["result"] == "FAIL", g["summary"]
    viol = [f["message"] for f in g["findings"] if f["severity"] == "Violation"]
    pat = re.compile(r"inmodel|blank|bnode|空白节点", re.I)
    assert any(pat.search(m) for m in viol), viol
