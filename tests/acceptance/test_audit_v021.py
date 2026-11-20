"""Acceptance test for the v0.2.1 rules R1-R4 (closing audit probes a05 a06 a07 a11 a13 a14 a15 a16 a18 a19).

The fixtures under modules/*/tests prove each rule fires; this script asserts the *outcomes* a fixture cannot express:
derived arch:approvalState values, build Warnings, and that metamodel annotations written in a model file are not
honoured. It builds aisep.Ctx in-process, so build/graph.nq is never touched.

Run:  <venv python> tests/acceptance/test_audit_v021.py      (also run by `aisep.py test`)
"""
import contextlib, io, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)  # the aisep/ library package (tools/aisep.py is the CLI shell)
from aisep import core as T  # noqa: E402

HDR = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix bpmn: <https://meta.linked.archi/bpmn/onto#> .
@prefix ddd:  <https://aisep.example/ont/ddd#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/adv/> .
:t a arch:Model ; skos:prefLabel "对抗模型"@zh .
:ac a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .
:ac2 a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件二"@zh .
:boss a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "架构师"@zh .
"""
MODS = T.discover()
results = []


def rec(name, dec, x, ts, gate="aisep:GateArchitecture", ev=True):
    return (f':{name} a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录{name}"@zh ; aisep:gate {gate} ;\n'
            f'  aisep:decision aisep:{dec} ; aisep:approvedBy :boss ; aisep:approves :{x} ;'
            f'{" aisep:evidence \"3f2a9c1e7b4d5a6f8e9c0b1a2d3e4f5a6b7c8d9e\" ;" if ev else ""}\n  prov:generatedAtTime "{ts}"^^xsd:dateTime .\n')


def ctx_of(body, checks=True):
    d = tempfile.mkdtemp(prefix="aisep-v021-")
    path = os.path.join(d, "t.ttl")
    open(path, "w", encoding="utf-8").write(HDR + body)
    ctx = T.Ctx(MODS, [path])
    if checks:
        T.run_check(ctx)
        T.l4(ctx)
    return ctx


def states(ctx):
    return {T.short(s).split(":")[-1]: T.short(o) for s, p, o, _ in ctx.built if p.value == T.ARCH + "approvalState"}


def lines(ctx, sev, layer):
    return [t for s, l, t in ctx.problems if s == sev and l == layer]


def claim(probe, text, ok, evidence):
    results.append(bool(ok))
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {probe}: {text}\n      evidence: {evidence}")


# ---------------------------------------------------------------- R3 approval derivation
c = ctx_of(rec("rec", "DecisionApproved", "ac", "2026-11-19T10:00:00Z", gate="aisep:DecisionApproved"))
w = [x for x in lines(c, "Warning", "build") if "approval record ignored" in x]
claim("a13", "R3a: a record with an invalid gate is ignored (ac stays arch:Proposed) and build warns",
      states(c).get("ac") == "arch:Proposed" and w, f"ac={states(c).get('ac')}; {w[:1]}")

c = ctx_of(rec("rec", "DecisionApproved", "ac", "2026-11-19T10:00:00Z", ev=False))
v = [x for x in lines(c, "Violation", "L1") if "aisep:evidence" in x]
claim("a14", "R3a/b: a record without aisep:evidence is an L1 Violation and is ignored (ac stays arch:Proposed)",
      states(c).get("ac") == "arch:Proposed" and v, f"ac={states(c).get('ac')}; {v[:1]}")

for probe, tie_name in (("a15", "aTieApprove"), ("a15b", "zTieApprove")):
    body = (rec("zApprove", "DecisionApproved", "ac", "2026-11-19T10:00:00+08:00")
            + rec("aReject", "DecisionRejected", "ac", "2026-11-19T03:00:00Z")
            + rec(tie_name, "DecisionApproved", "ac2", "2026-11-19T05:00:00Z")
            + rec("bTieReject", "DecisionRejected", "ac2", "2026-11-19T13:00:00+08:00"))
    c = ctx_of(body)
    st = states(c)
    amb = [x for x in lines(c, "Violation", "L1") if "ambiguous approval" in x]
    claim(probe, "R3c: latest by timezone-normalised instant wins (ac: 03:00Z reject > 10:00+08:00 approve); a same-instant "
          "approve/reject is an 'ambiguous approval' Violation and leaves ac2 arch:Proposed, whatever the record IRIs",
          st.get("ac") == "aisep:Rejected" and st.get("ac2") == "arch:Proposed" and len(amb) == 1 and
          any("ambiguous approval" in x for x in lines(c, "Warning", "build")),
          f"ac={st.get('ac')} ac2={st.get('ac2')}; {amb[:1]}")

c = ctx_of(':old a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "旧组件"@zh ; dcterms:isReplacedBy :ac .\n'
           + rec("r", "DecisionApproved", "old", "2026-11-19T10:00:00Z"))
claim("R3d", "an element with dcterms:isReplacedBy is aisep:Superseded even after an approval",
      states(c).get("old") == "aisep:Superseded", f"old={states(c).get('old')}")

# ---------------------------------------------------------------- R1 model files must not change the metamodel
c = ctx_of(":MyServ rdfs:subClassOf am4:Serving ; aisep:assertedShortcut true .\n"
           ":r1 a :MyServ ; arch:inModel :t ; arch:source :ac ; arch:target :ac2 .\n")
v = [x for x in lines(c, "Violation", "L1") if "aisep:assertedShortcut" in x]
w = [x for x in lines(c, "Warning", "L2") if "adv:r1" in x and "derived-only" in x]
claim("a18", "R1: a model-declared aisep:assertedShortcut is a Violation and is not honoured (L2 still warns on r1)",
      v and w, f"{v[:1]} / {w[:1]}")

c = ctx_of("am4:Serving aisep:assertedShortcut true .\n:r2 a am4:Serving ; arch:inModel :t ; arch:source :ac2 ; arch:target :ac .\n")
v = [x for x in lines(c, "Violation", "L1") if "module/upstream term am4:Serving" in x]
w = [x for x in lines(c, "Warning", "L2") if "adv:r2" in x and "derived-only" in x]
claim("a19", "R1: a model file annotating am4:Serving is a Violation and does not exempt am4:Serving globally",
      v and w, f"{v[:1]} / {w[:1]}")

c = ctx_of(":MyServ rdfs:subClassOf am4:Serving ; aisep:dependency aisep:None .\n"
           ":r1 a :MyServ ; arch:inModel :t ; arch:source :ac ; arch:target :ac2 .\n")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    rows = T.impact(c, T.MODEL_BASE + "adv/ac", 3, "depends")
hop = [(d, T.short(x), note) for d, x, p, note in rows]
claim("R1", "a model-declared aisep:dependency is ignored: :MyServ inherits am4:Serving = Forward, so ac2 is traversed",
      (1, "adv:ac2", "") in hop and any("aisep:dependency" in x for x in lines(c, "Violation", "L1")), f"impact rows={hop}")

for probe, body, needle in (
        ("a05", ":Hybrid rdfs:subClassOf am4:BusinessObject , bpmn:Task .\n"
                ':h a :Hybrid ; arch:inModel :t ; skos:prefLabel "混合体"@zh .\n', "2 rdfs:subClassOf parents"),
        ("a06", ":BoNode rdfs:subClassOf am4:ApplicationComponent , am4:Node .\n"
                ':x a :BoNode ; arch:inModel :t ; skos:prefLabel "组件兼节点"@zh .\n', "2 rdfs:subClassOf parents"),
        ("a11", ":myState rdfs:subPropertyOf arch:approvalState .\n:ac :myState arch:Approved .\n", "rdfs:subPropertyOf")):
    c = ctx_of(body)
    v = [x for x in lines(c, "Violation", "L1") if "must not change the metamodel" in x and needle in x]
    claim(probe, f"R1: model file schema change rejected ({needle})", v, v[:1])

# ---------------------------------------------------------------- R2 one notation per element
c = ctx_of(':ag a ddd:Aggregate , am4:DataObject ; arch:inModel :t ; skos:prefLabel "聚合"@zh .\n'
           ':bdo a bpmn:DataObject , am4:BusinessObject ; arch:inModel :t ; skos:prefLabel "流程数据"@zh .\n')
v = [x for x in lines(c, "Violation", "L1") if "one notation per element" in x]
claim("a16", "R2: ddd:Aggregate+am4:DataObject and bpmn:DataObject+am4:BusinessObject are both rejected", len(v) == 2, v)

# ---------------------------------------------------------------- R4 refines to a replaced node
c = ctx_of(':old a am4:Process ; arch:inModel :t ; skos:prefLabel "旧过程"@zh ; owl:deprecated true ; dcterms:isReplacedBy :new .\n'
           ':new a am4:Process ; arch:inModel :t ; skos:prefLabel "新过程"@zh .\n'
           ':bp a bpmn:Process ; arch:inModel :t ; skos:prefLabel "流程"@zh .\n'
           ':r1 a arch:Refines ; arch:inModel :t ; arch:source :bp ; arch:target :old .\n')
w = [x for x in lines(c, "Warning", "L4") if "migrate the trace link to the replacing node" in x]
claim("a07", "R4: arch:Refines to a deprecated/replaced node gives an L4 Warning naming the replacement",
      w and "adv:new" in w[0], w[:1])

# ---------------------------------------------------------------- G1 one approval-validity definition (audit3 n12/n13/n13b)
# L1 (Ctx.approval_problems), L3 (ext-governance EG13/EG15) and the approval-state derivation must agree.
for probe, body, eg in (
        ("n12", ':robot a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "机器人"@zh .\n'
                + rec("rec", "DecisionApproved", "ac", "2026-11-19T10:00:00Z").replace("approvedBy :boss", "approvedBy :robot"), "EG13:"),
        ("n13", rec("rec", "DecisionApproved", "ac", "2026-02-30T10:00:00Z"), "EG15:"),
        ("n13b", rec("rec", "DecisionApproved", "ac", "2026-11-19T24:00:00Z"), "EG15:"),
        ("ok", rec("rec", "DecisionApproved", "ac", "2026-11-19T10:00:00.5+08:00"), None)):
    c = ctx_of(body)
    T.l3(c)
    l1 = [x for x in lines(c, "Violation", "L1") if x.startswith("adv:rec:")]
    l3 = [x for x in lines(c, "Violation", "L3") if eg and eg in x and "adv:rec" in x]
    st = states(c).get("ac")
    want = (bool(l1), bool(l3), st) == ((True, True, "arch:Proposed") if eg else (False, False, "arch:Approved"))
    claim(f"G1-{probe}", f"L1, L3 {eg or '(none)'} and the derivation agree the record is {'invalid' if eg else 'valid'}",
          want and (not eg or c.approval_problems().get(T.MODEL_BASE + "adv/rec")),
          f"L1={l1[:1]}; L3={l3[:1]}; ac={st}")

# v0.4 review finding 5: start <= end with one timezone-less value (read as UTC) — L1 (activity_problems) and L3 EG24
# must agree in both directions (before the fix, SPARQL found the mixed pair incomparable and EG24 stayed silent).
for probe, start, hit in (("eg24-mixed-bad", "2026-11-20T03:30:00", True), ("eg24-mixed-ok", "2026-11-19T18:30:00", False)):
    c = ctx_of(':act a aisep:AgentActivity ; arch:inModel :t ; skos:prefLabel "AI 活动"@zh ; prov:wasAssociatedWith :boss ;\n'
               f'  prov:startedAtTime "{start}"^^xsd:dateTime ; prov:endedAtTime "2026-11-20T03:00:00+08:00"^^xsd:dateTime ;\n'
               '  aisep:sessionRef "s" ; aisep:branch "b" ; aisep:baseCommit "0a1b2c3d4e5f60718293a4b5c6d7e8f901234567" ;\n'
               '  aisep:headCommit "3f2a9c1e7b4d5a6f8e9c0b1a2d3e4f5a6b7c8d9e" .\n')
    T.l3(c)
    l1 = [x for x in lines(c, "Violation", "L1") if "ends before it starts" in x]
    l3 = [x for x in lines(c, "Violation", "L3") if "EG24:" in x]
    claim(f"G1-{probe}", f"L1 and L3 EG24 agree a mixed-timezone activity is {'invalid' if hit else 'valid'}",
          (bool(l1), bool(l3)) == (hit, hit), f"L1={l1[:1]}; L3={l3[:1]}")

bad = results.count(False)
print(f"SUMMARY audit_v021 claims={len(results)} confirmed={len(results) - bad} refuted={bad}")
sys.exit(1 if bad else 0)
