"""Acceptance test for spec §15 ("本规范的可执行验证（原型）") on the cross-notation example models/procurement.

Each claim is executed through tools/aisep.py (subprocess) and printed as CONFIRMED / REFUTED with evidence.
Exit 0 only if every claim is CONFIRMED. Known spec inconsistencies are printed as SPEC-DEVIATION lines: their
*evidence* is asserted (so a semantic change is noticed), but the spec sentence itself is not treated as a claim.

Run:  <venv python> tests/acceptance/test_spec15.py      (also run by `aisep.py test`)
"""
import glob, os, re, shutil, subprocess, sys, tempfile, time
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
MODEL_DIR = os.path.join(ROOT, "models", "procurement")
MODEL_FILES = sorted(glob.glob(os.path.join(MODEL_DIR, "*.ttl")))
P = "procurement:"  # how aisep.py prints https://aisep.example/model/procurement/<local>

results, timings, deviations = [], {}, []


def aisep(cmd, *args, files=None):
    t = time.time()
    p = subprocess.run([sys.executable, AISEP, cmd, *args, *(files if files is not None else MODEL_FILES)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr, time.time() - t


def claim(no, text, ok, evidence):
    results.append((no, text, bool(ok)))
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] §15.{no} {text}\n      evidence: {evidence}")


def mutated(file_name, old, new):
    """Temp copy of the whole example with exactly one textual change in one file; returns the file list."""
    d = tempfile.mkdtemp(prefix="aisep-acc-")
    for f in MODEL_FILES:
        shutil.copy(f, d)
    path = os.path.join(d, file_name)
    src = open(path, encoding="utf-8").read()
    assert src.count(old) == 1, f"mutation anchor not unique in {file_name}: {old!r}"
    open(path, "w", encoding="utf-8").write(src.replace(old, new))
    return sorted(glob.glob(os.path.join(d, "*.ttl")))


def appended(file_name, text):
    """Temp copy of the whole example with `text` appended to one file (the file's prefixes apply)."""
    d = tempfile.mkdtemp(prefix="aisep-acc-")
    for f in MODEL_FILES:
        shutil.copy(f, d)
    with open(os.path.join(d, file_name), "a", encoding="utf-8") as fh:
        fh.write("\n" + text + "\n")
    return sorted(glob.glob(os.path.join(d, "*.ttl")))


def standalone(text):
    """A one-file temp model (own prefixes) for rules that need no example content."""
    d = tempfile.mkdtemp(prefix="aisep-acc-")
    path = os.path.join(d, "t.ttl")
    open(path, "w", encoding="utf-8").write(text)
    return [path]


def query_rows(sparql, files=None):
    rc, out, _ = aisep("query", sparql, files=files)
    assert rc == 0, out
    lines = [l for l in out.splitlines() if l and not l.startswith("--")]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def notation(prefixed_type):
    return {"am4": "am4", "ddd": "DDD", "uml": "UML", "bpmn": "BPMN", "aisep": "ext", "arch": "core"}.get(
        prefixed_type.split(":")[0], prefixed_type)


# ---------------------------------------------------------------- baseline: the example itself is clean
rc_c, out_c, timings["check"] = aisep("check")
rc_v, out_v, timings["validate"] = aisep("validate")
claim(0, "baseline: the procurement example passes check (L0-L2) and validate (L3)", rc_c == 0 and rc_v == 0,
      f"check rc={rc_c} ({out_c.strip().splitlines()[-1]}); validate rc={rc_v} ({out_v.strip().splitlines()[-1]})")

# ---------------------------------------------------------------- §15.1 write layer
rc, out, timings["build"] = aisep("build")
m = re.search(r"direct_triples=(\d+)", out)
n_direct = int(m.group(1)) if m else -1
qr = query_rows("SELECT ?r ?s ?t ?u WHERE { GRAPH ?g { ?r arch:source ?s ; arch:target ?t } "
                "FILTER(STRSTARTS(STR(?g), 'urn:aisep:src:')) ?r a ?c . ?c rdfs:subClassOf* ?d . ?d arch:unqualifiedForm ?u }")
qr_resources = {r["r"] for r in qr}
nq = open(os.path.join(ROOT, "build", "graph.nq"), encoding="utf-8").read()
probe = ("<https://aisep.example/model/procurement/quoteApproval> <https://meta.linked.archi/archimate4/onto#accesses> "
         "<https://aisep.example/model/procurement/quotation> <https://aisep.example/model/procurement/>")
probe2 = ("<https://aisep.example/model/procurement/QuotationEntity> <https://meta.linked.archi/core#refines> "
          "<https://aisep.example/model/procurement/quotationAggregate> <https://aisep.example/model/procurement/>")
claim(1, "build emits one direct triple per qualified relationship, into the model graph",
      rc == 0 and n_direct == len(qr_resources) > 0 and probe in nq and probe2 in nq,
      f"direct_triples={n_direct}, qualified relationships in sources={len(qr_resources)}; graph.nq contains "
      f"'quoteApproval am4:accesses quotation' and 'QuotationEntity arch:refines quotationAggregate' in graph <…/procurement/>")

files = mutated("am4.ttl", ":quoteManagementService a am4:Service ;",
                ":quoteApproval am4:accesses :quotation .\n:quoteManagementService a am4:Service ;")
rc, out, _ = aisep("check", files=files)
hit = [l for l in out.splitlines() if "direct triple written in source" in l]
claim(1, "a hand-written direct triple in a source file makes check fail with a fix suggestion",
      rc == 1 and hit and "am4:Access" in hit[0] and "instead" in hit[0], hit[0] if hit else out[-300:])

# ---------------------------------------------------------------- §15.2 validation scope
sf_aligned = aisep("query", "ASK { bpmn:SequenceFlow rdfs:subClassOf* am4:Triggering }")[1].strip() == "True"
gw_flows = query_rows("SELECT ?f WHERE { ?f a bpmn:SequenceFlow ; arch:source|arch:target ?g . ?g a bpmn:ExclusiveGateway }")
claim(2, "a valid BPMN task->gateway->task flow passes validate although SequenceFlow ⊑ am4:Triggering",
      rc_v == 0 and rc_c == 0 and len(gw_flows) >= 3 and sf_aligned,
      f"{len(gw_flows)} sequence flows touch the gateway; alignment active in queries "
      f"(ASK SequenceFlow ⊑* am4:Triggering = {sf_aligned}); validate rc={rc_v}")

files = mutated("ddd.ttl", ":rel-quotationBC-owns-quotationAggregate a ddd:Ownership ;",
                ":rel-bad-composition a am4:Composition ;\n    arch:inModel <https://aisep.example/model/procurement/> ;\n"
                "    arch:source :quotationBC ; arch:target :quotationAggregate .\n"
                ":rel-quotationBC-owns-quotationAggregate a ddd:Ownership ;")
rc1, out1, _ = aisep("check", files=files)
rc2, out2, _ = aisep("validate", files=files)
l2 = [l for l in out1.splitlines() if "rel-bad-composition" in l and "illegal by ArchiMate 4.0 relationship table" in l]
l3 = [l for l in out2.splitlines() if "rel-bad-composition" in l and "invalid source/target combination" in l]
claim(2, "a DDD BoundedContext -Composition-> Aggregate is stopped by the am4 matrix (L2 table and L3 am4 shapes)",
      rc1 == 1 and rc2 == 1 and l2 and l3, f"L2: {l2[0] if l2 else out1[-200:]} | L3: {l3[0][:160] if l3 else out2[-200:]}")

# ---------------------------------------------------------------- §15.3 one generic query through all notations
TC, CODE = P + "tcSecondLevelApproval", P + "quotationCode"
GENERIC = """SELECT DISTINCT ?s ?st ?r ?c ?t ?tt WHERE {
  ?r a ?c . ?c rdfs:subClassOf* arch:QualifiedRelationship .
  ?r arch:source ?s ; arch:target ?t .
  ?s a ?st . ?st rdfs:subClassOf* arch:Element .
  ?t a ?tt . ?tt rdfs:subClassOf* arch:Element .
  <https://aisep.example/model/procurement/tcSecondLevelApproval> ((^arch:source/arch:target)|(^arch:target/arch:source))* ?s .
}"""
assert not re.search(r"\b(am4|bpmn|uml|ddd):", GENERIC), "generic query must not name notation-specific terms"
edges = query_rows(GENERIC)
typ, adj = {}, {}
for e in edges:
    typ[e["s"]], typ[e["t"]] = e["st"], e["tt"]
    adj.setdefault(e["s"], []).append((e["t"], e["c"], "->"))
    adj.setdefault(e["t"], []).append((e["s"], e["c"], "<-"))
prev, todo = {TC: None}, deque([TC])
while todo:
    x = todo.popleft()
    for y, c, d in adj.get(x, []):
        if y not in prev:
            prev[y] = (x, c, d); todo.append(y)


def path_to(n):
    steps = []
    while prev.get(n):
        x, c, d = prev[n]
        steps.append((x, c, d, n)); n = x
    return list(reversed(steps))


def show(steps):
    if not steps:
        return "(unreachable)"
    s = f"{steps[0][0]} [{notation(typ[steps[0][0]])}]"
    for x, c, d, y in steps:
        s += f" {'-' if d == '->' else '<-'}{c}{'->' if d == '->' else '-'} {y} [{notation(typ[y])}]"
    return s


reached = {notation(typ[n]) for n in prev}
main_path = path_to(CODE)
print("      path TC -> CodeLocation: " + show(main_path))
branch = {}
for want in ("BPMN", "UML"):
    node = next((n for n in sorted(prev) if notation(typ[n]) == want), None)
    branch[want] = node
    print(f"      branch to {want}: " + show(path_to(node) if node else []))
on_path = {notation(typ[n]) for st in main_path for n in (st[0], st[3])}
claim(3, "one generic SPARQL (QR source/target + subClassOf*, no notation predicates) reaches the CodeLocation from "
         "the TestCase, and the reached trace covers am4, DDD, UML and BPMN",
      CODE in prev and {"am4", "DDD", "UML", "BPMN"} <= reached and {"am4", "DDD"} <= on_path,
      f"{len(edges)} edges, {len(prev)} nodes reached; notations reached={sorted(reached)}; "
      f"notations on the TC->code path={sorted(on_path)}")
# (v0.1 deviation resolved in v0.2 §7.1: BPMN and UML nodes are refines leaves beside the main chain.)

# ---------------------------------------------------------------- §15.4 impact as data
# Expected set for "change 报价单 (am4 BusinessObject)" derived by hand from the §9 table, default depth 3.
# Rule reminder: X impacts Y when Y depends on X: Forward = target depends on source, Backward = source depends on
# target, Both = either way; Association/None = not traversed.
EXPECTED = {
    "quoteApproval":        (1, "Access backward: the approval process accesses 报价单, so it depends on it"),
    "submitQuotation":      (1, "Access backward: submit-quotation accesses 报价单"),
    "quotationAggregate":   (1, "Realization both: the DDD aggregate realizes 报价单 (cross-notation am4 -> DDD)"),
    "supplier":             (2, "Assignment both: supplier is assigned to the approval/submission process"),
    "procurementManager":   (2, "Assignment both: procurement manager is assigned to the approval process"),
    "reqTwoLevelApproval":  (2, "Realization both: approval process realizes the requirement (requirement depends on its realizer)"),
    "procurementSubdomain": (2, "Realization both: approval process realizes the Procurement subdomain (⊑ Capability)"),
    "bpmnQuoteApproval":    (2, "arch:Refines backward: the BPMN process refines the am4 approval process (am4 -> BPMN)"),
    "QuotationEntity":      (2, "arch:Refines backward: the UML class refines the aggregate (DDD -> UML)"),
    "quotationBC":          (2, "ddd:Ownership ⊑ Assignment both: the BC owns the aggregate"),
    "quotationRoot":        (2, "RootContainment ⊑ Composition both (v0.2 §9): the root entity's existence depends on its aggregate"),
    "procurementSystem":    (3, "Composition both: 采购系统 is composed of the BC (the whole's structure depends on the part)"),
    "quotationCode":        (3, "aisep:Implementation backward: the code location implements the BC (code depends on design)"),
    "quotationPackage":     (3, "Realization both: the deployable realizes the BC"),
}
NOT_EXPECTED = {
    "quoteManagementService": "Serving forward: the approval process depends on 报价管理, not the other way round",
    "acOver100kSecondLevel": "Aggregation backward: the requirement depends on its criterion, not vice versa",
    "tcSecondLevelApproval": "depends only on the acceptance criterion, which is not impacted",
}
rc, out, timings["impact"] = aisep("impact", P + "quotation")
got = {}
for l in out.splitlines():
    f = l.split("\t")
    if len(f) >= 5 and f[0].startswith(P):
        got[f[0][len(P):]] = (int(f[3].split()[0]), f[4])
cross = got.get("quotationCode", (0, ""))[1]
claim(4, "impact (depends) of 报价单 equals the §9-derived set (14 elements, depths as justified), incl. a cross-notation chain",
      rc == 0 and {k: v[0] for k, v in got.items()} == {k: v[0] for k, v in EXPECTED.items()}
      and not set(NOT_EXPECTED) & set(got) and "ddd:Ownership" in cross and "aisep:Implementation" in cross,
      f"got {len(got)}: {sorted(got)}; missing={sorted(set(EXPECTED) - set(got))}, extra={sorted(set(got) - set(EXPECTED))}; "
      f"cross-notation chain: {cross}")
for k, (d, why) in EXPECTED.items():
    print(f"      expected {k:<22} depth {d}: {why}")
for k, why in NOT_EXPECTED.items():
    print(f"      excluded {k:<22}: {why}")

# Spike regression (spec v0.2 §9 "两种模式"): the spike model is exactly am4.ttl. depends gives 5; the spike's 7-element
# answer is the ripple set (= the undirected 3-hop neighbourhood, there is no Association in am4.ttl).
SPIKE_DEPENDS = {"quoteApproval": 1, "submitQuotation": 1, "supplier": 2, "procurementManager": 2, "reqTwoLevelApproval": 2}
SPIKE_RIPPLE = dict(SPIKE_DEPENDS, quoteManagementService=2, procurementSystem=3)


def impact_set(mode, files=None):
    rc, out, _ = aisep("impact", P + "quotation", "--mode", mode, files=files)
    assert rc == 0, out
    return {f[0][len(P):]: int(f[3].split()[0]) for f in (l.split("\t") for l in out.splitlines())
            if len(f) >= 5 and f[0].startswith(P)}


am4_only = [os.path.join(MODEL_DIR, "am4.ttl")]
dep5, rip7 = impact_set("depends", am4_only), impact_set("ripple", am4_only)
und = query_rows("SELECT ?s ?t WHERE { ?r arch:source ?s ; arch:target ?t }", files=am4_only)
nbr = {}
for e in und:
    nbr.setdefault(e["s"], set()).add(e["t"]); nbr.setdefault(e["t"], set()).add(e["s"])
ring, frontier = {P + "quotation"}, {P + "quotation"}
for _ in range(3):
    frontier = {y for x in frontier for y in nbr.get(x, ())} - ring
    ring |= frontier
undirected3 = {x[len(P):] for x in ring} - {"quotation"}
claim(4, "spike regression: on the spike model (am4.ttl) depends gives exactly the 5 §9 dependents, ripple gives the "
         "spike's 7 (= undirected 3-hop neighbourhood)",
      dep5 == SPIKE_DEPENDS and rip7 == SPIKE_RIPPLE and set(rip7) == undirected3,
      f"depends={sorted(dep5.items())}; ripple={sorted(rip7.items())}; undirected 3-hop={sorted(undirected3)}")
# Full example, ripple: the depends set plus what depends would never reach (the Serving provider 报价管理, the
# aggregated acceptance criterion); Association/None would still only be listed as related.
RIPPLE_FULL = dict({k: v[0] for k, v in EXPECTED.items()}, quoteManagementService=2, acOver100kSecondLevel=3)
ripf = impact_set("ripple")
claim(4, "impact (ripple) of 报价单 on the full example = depends set + 报价管理 (depth 2) + the acceptance criterion (depth 3)",
      ripf == RIPPLE_FULL and set(got) < set(ripf),
      f"got {len(ripf)}: missing={sorted(set(RIPPLE_FULL) - set(ripf))}, extra={sorted(set(ripf) - set(RIPPLE_FULL))}, "
      f"depth mismatches={sorted(k for k in set(ripf) & set(RIPPLE_FULL) if ripf[k] != RIPPLE_FULL[k])}")

# ---------------------------------------------------------------- §15.5 closed world (one mutation per module file)
CASES = [
    ("misspelled type (am4)", "am4.ttl", ":quotation a am4:BusinessObject ;", ":quotation a am4:BusinesObject ;",
     "is not a class declared by a loaded ontology"),
    ("misspelled type (BPMN)", "bpmn.ttl", ":bpmnReview a bpmn:UserTask ;", ":bpmnReview a bpmn:UserTsk ;",
     "is not a class declared by a loaded ontology"),
    ("two most-specific types (DDD)", "ddd.ttl", ":quotationBC a ddd:BoundedContext ;", ":quotationBC a ddd:BoundedContext , am4:Node ;",
     "more than one most-specific rdf:type"),
    ("missing inModel (UML)", "uml.ttl", ":QuotationEntity a uml:Class ;\n    arch:inModel <https://aisep.example/model/procurement/> ;",
     ":QuotationEntity a uml:Class ;", "has no arch:inModel"),
    ("dangling endpoint (code)", "code.ttl", "arch:source :quotationCode ; arch:target :quotationBC .",
     "arch:source :quotationCode ; arch:target :quotationBc .", "relationship endpoint is not a member of any model"),
    ("deprecated arch:partOfModel (verification)", "verification.ttl",
     ":tcSecondLevelApproval a aisep:TestCase ;\n    arch:inModel", ":tcSecondLevelApproval a aisep:TestCase ;\n    arch:partOfModel",
     "forbidden term arch:partOfModel"),
]
for name, f, old, new, expect in CASES:
    rc, out, _ = aisep("check", files=mutated(f, old, new))
    hit = [l for l in out.splitlines() if l.startswith("[Violation]") and expect in l]
    claim(5, f"closed world stops: {name}", rc == 1 and hit, hit[0][:200] if hit else f"rc={rc}: {out[-250:]}")

# D6: a redundant asserted superclass (importer habit) of the SAME notation is accepted. v0.2.1 (R2 "one notation per
# element") changed this claim: it used ddd:BoundedContext + am4:ApplicationComponent (D1 alignment), which is now a
# cross-notation typing and rejected (asserted just below).
rc, out, _ = aisep("check", files=mutated("am4.ttl", ":procurementSystem a am4:ApplicationComponent ;",
                                          ":procurementSystem a am4:ApplicationComponent , am4:ApplicationDomainElement ;"))
claim(5, "D6: an additional asserted superclass (same notation) of the one most-specific type is accepted",
      rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
rc, out, _ = aisep("check", files=mutated("ddd.ttl", ":quotationBC a ddd:BoundedContext ;",
                                          ":quotationBC a ddd:BoundedContext , am4:ApplicationComponent ;"))
hit = [l for l in out.splitlines() if l.startswith("[Violation]") and "one notation per element" in l]
claim(5, "R2: a redundant superclass from another notation (ddd:BoundedContext + am4:ApplicationComponent) is rejected",
      rc == 1 and hit, hit[0][:200] if hit else f"rc={rc}: {out[-250:]}")

# ---------------------------------------------------------------- v0.2: audit cases H and J (spec §7.2, §7.3)
H = (":sfBad a bpmn:SequenceFlow ; arch:inModel <https://aisep.example/model/procurement/> ;\n"
     "    arch:source :quotation ; arch:target :reqTwoLevelApproval .")
rc, out, _ = aisep("check", files=appended("bpmn.ttl", H))
hit = [l for l in out.splitlines() if l.startswith("[Violation]") and "sfBad" in l and "notation mixing" in l]
claim(6, "audit case H: a bpmn:SequenceFlow between two am4 elements is rejected (notation mixing, §7.3)",
      rc == 1 and hit, hit[0][:220] if hit else f"rc={rc}: {out[-250:]}")
J = (":rel-quotation-refines-reqTwoLevelApproval a arch:Refines ; arch:inModel <https://aisep.example/model/procurement/> ;\n"
     "    arch:source :quotation ; arch:target :reqTwoLevelApproval .")
rc, out, _ = aisep("check", files=appended("am4.ttl", J))
hit = [l for l in out.splitlines() if l.startswith("[Violation]") and "rel-quotation-refines" in l and "within one notation" in l]
claim(6, "audit case J: arch:Refines between two am4 elements is rejected (same-notation refines, §7.2)",
      rc == 1 and hit, hit[0][:220] if hit else f"rc={rc}: {out[-250:]}")

# ---------------------------------------------------------------- v0.2: derived approvalState (spec §6.6, D10)
GOV = """@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/gov/> .
:gov a arch:Model ; skos:prefLabel "治理测试"@zh .
:alice a arch:Stakeholder ; arch:inModel :gov ; skos:prefLabel "张架构师"@zh .
:a a am4:ApplicationComponent ; arch:inModel :gov ; skos:prefLabel "甲系统"@zh .
:b a am4:ApplicationComponent ; arch:inModel :gov ; skos:prefLabel "乙系统"@zh .
:c a am4:ApplicationComponent ; arch:inModel :gov ; skos:prefLabel "丙系统"@zh ; dcterms:isReplacedBy :b .
:d a am4:ApplicationComponent ; arch:inModel :gov ; skos:prefLabel "丁系统"@zh .
:approval-20261101-ad a aisep:ApprovalRecord ; arch:inModel :gov ; skos:prefLabel "首次评审"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :alice ;
    aisep:approves :a , :d , :c ; prov:generatedAtTime "2026-11-01T09:00:00Z"^^xsd:dateTime ;
    aisep:evidence "5e2b8c1d4a7f0e3b6c9d2a5f8e1b4c7d0a3f6e9b" .
:approval-20261110-a a aisep:ApprovalRecord ; arch:inModel :gov ; skos:prefLabel "复审"@zh ;
    aisep:gate aisep:GateDesign ; aisep:decision aisep:DecisionRejected ; aisep:approvedBy :alice ;
    aisep:approves :a ; prov:generatedAtTime "2026-11-10T09:00:00Z"^^xsd:dateTime ;
    aisep:evidence "b7d0a3f6e9c2b5e8a1d4c7f0b3e6a9d2c5f8b1e4" .
"""
gov = standalone(GOV)
rc, out, _ = aisep("check", files=gov)
states = {r["x"].split(":")[-1]: r["s"] for r in query_rows("SELECT ?x ?s WHERE { ?x arch:approvalState ?s }", files=gov)}
want = {"a": "aisep:Rejected", "b": "arch:Proposed", "c": "aisep:Superseded", "d": "arch:Approved"}  # :alice (arch:Stakeholder) gets none (R4-5)
claim(7, "build derives arch:approvalState from approval records: latest decision wins, none -> Proposed, replaced -> Superseded; "
      "a Stakeholder has no approvalState",
      rc == 0 and states == want and "alice" not in states, f"check rc={rc}; derived={sorted(states.items())}")
rc, out, _ = aisep("check", files=appended("am4.ttl", ":quotation arch:approvalState arch:Approved ."))
hit = [l for l in out.splitlines() if l.startswith("[Violation]") and "hand-written arch:approvalState" in l]
claim(7, "a hand-written arch:approvalState in the example is rejected by check (L1)",
      rc == 1 and hit, hit[0][:200] if hit else f"rc={rc}: {out[-250:]}")

# ---------------------------------------------------------------- v0.2: L4 trace gaps (spec §6.2, §6.5)
L4 = """:reqMust a am4:Requirement ; arch:inModel <https://aisep.example/model/procurement/> ;
    skos:prefLabel "必须项需求"@zh ; aisep:priority aisep:Must .
:reqCould a am4:Requirement ; arch:inModel <https://aisep.example/model/procurement/> ;
    skos:prefLabel "可选项需求"@zh ; aisep:priority aisep:Could .
:tcReview a aisep:TestCase ; arch:inModel <https://aisep.example/model/procurement/> ; skos:prefLabel "审核任务测试"@zh .
:rel-tcReview-verifies-bpmnReview a aisep:Verification ; arch:inModel <https://aisep.example/model/procurement/> ;
    arch:source :tcReview ; arch:target :bpmnReview .
:tcProcess a aisep:TestCase ; arch:inModel <https://aisep.example/model/procurement/> ; skos:prefLabel "审批流程测试"@zh .
:rel-tcProcess-verifies-bpmnQuoteApproval a aisep:Verification ; arch:inModel <https://aisep.example/model/procurement/> ;
    arch:source :tcProcess ; arch:target :bpmnQuoteApproval ."""
rc, out, _ = aisep("findings", files=appended("verification.ttl", L4))
gaps = {l.split()[2][len(P):] for l in out.splitlines() if l.startswith("[Warning] L4") and "trace gap" in l}
claim(8, "L4 trace gaps: only the unverified Must requirement and the verified BPMN task without a refines to the hub",
      gaps == {"reqMust", "bpmnReview"}, f"gaps={sorted(gaps)} (not expected: reqCould, bpmnQuoteApproval, reqTwoLevelApproval)")

# ---------------------------------------------------------------- summary
print(f"      timings (s): " + ", ".join(f"{k}={v:.2f}" for k, v in timings.items()))
bad = [r for r in results if not r[2]]
print(f"SUMMARY spec15 claims={len(results)} confirmed={len(results) - len(bad)} refuted={len(bad)} "
      f"spec_deviations={len(deviations)}")
sys.exit(1 if bad else 0)
