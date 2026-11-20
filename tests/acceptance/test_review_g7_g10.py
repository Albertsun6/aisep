"""Acceptance probes for the cross-model (GPT) review holes G7–G10 — fixed case list C1–C4 plus n17/n19.
Each probe runs the real CLI (or the Ctx API for derived state) on a temp model and prints CONFIRMED/REFUTED; exit 1 if
any claim is refuted. Valid counterparts are probed too (impact/gate on the valid procurement example)."""
import glob, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
sys.path.insert(0, ROOT)  # the aisep/ library package (tools/aisep.py is the CLI shell)
from aisep import core as T  # noqa: E402

MODEL_FILES = sorted(glob.glob(os.path.join(ROOT, "models", "procurement", "*.ttl")))
HDR = """@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix bpmn: <https://meta.linked.archi/bpmn/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix aisepsh: <https://aisep.example/ont/aisep-shapes#> .
@prefix ex:   <https://example.com/> .
@prefix : <https://aisep.example/model/t/> .
:t a arch:Model ; skos:prefLabel "测试模型"@zh .
"""
results = []


def claim(case, text, ok, evidence):
    results.append(bool(ok))
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {case} {text}\n      evidence: {evidence}")


def model(body):
    d = tempfile.mkdtemp(prefix="aisep-g7-")
    p = os.path.join(d, "t.ttl")
    open(p, "w", encoding="utf-8").write(HDR + body)
    return [p]


def cli(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def l1(files):
    c = T.Ctx(T.discover(), files)
    T.run_check(c)
    return c, [t for s, layer, t in c.problems if s == "Violation"]


# ---- C1 (G7) undeclared predicate
c, v = l1(model(""":a a am4:Process ; arch:inModel :t ; skos:prefLabel "过程"@zh .
:b a bpmn:UserTask ; arch:inModel :t ; skos:prefLabel "任务"@zh .
:a ex:linksTo :b ."""))
claim("C1", "ex:linksTo between two model elements -> L1 Violation 'undeclared predicate ex:linksTo in model file'",
      any("undeclared predicate ex:linksTo in model file" in x for x in v), v[:2])

# ---- n17 / n19 (G7)
c, v = l1(model(':ac a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .\n'
                ':myShape sh:targetClass am4:ApplicationComponent .'))
claim("n17", "sh:targetClass triple in a model file -> L1 Violation (undeclared predicate)",
      any("undeclared predicate sh:targetClass" in x for x in v), v[:2])
c, v = l1(model(':ac a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .\n'
                'aisepsh:ApprovalRecordShape sh:deactivated true .'))
claim("n19", "sh:deactivated on a module shape IRI in a model file -> L1 Violation (undeclared predicate)",
      any("undeclared predicate sh:deactivated" in x for x in v), v[:2])

# ---- G7 valid: the procurement example has no G7 Violation
c, v = l1(MODEL_FILES)
claim("G7-valid", "procurement example: no undeclared-predicate / element-link Violation (L1+L2 clean)", not v, v[:2])

# ---- C2 (G8) isReplacedBy literal + valid Approved record
REC = """:boss a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "架构师"@zh .
:rec a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :boss ; aisep:approves :x ;
    aisep:evidence "0123456789abcdef0123456789abcdef01234567" ; prov:generatedAtTime "2026-11-19T10:00:00Z"^^xsd:dateTime .
"""
X = "https://aisep.example/model/t/x"
state = lambda c: {s.value: o.value for s, p, o, _ in c.built if p.value == T.ARCH + "approvalState"}.get(X)
c, v = l1(model(':x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh ; '
                'dcterms:isReplacedBy "not-a-node" .\n' + REC))
claim("C2", "isReplacedBy \"not-a-node\" -> L1 Violation and :x stays arch:Approved (not Superseded)",
      any("isReplacedBy target must be an IRI that is an element" in x for x in v) and state(c) == T.ARCH + "Approved",
      f"state={T.short(state(c) or '-')}; {v[:1]}")
c, v = l1(model(':x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh ; dcterms:isReplacedBy :y .\n'
                ':y a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "新组件"@zh .\n' + REC))
claim("G8-valid", "isReplacedBy an element of the model -> no Violation and :x is aisep:Superseded (wins over the record)",
      not v and state(c) == T.AISEP + "Superseded", f"state={T.short(state(c) or '-')}; {v[:1]}")

# ---- C3 (G9) impact refuses an invalid model
bad = model(""":first a bpmn:UserTask ; arch:inModel :t ; skos:prefLabel "首任务"@zh .
:req a am4:Requirement ; arch:inModel :t ; skos:prefLabel "需求"@zh .
:bad a am4:Triggering ; arch:inModel :t ; arch:source :first ; arch:target :req .""")
rc, out, err = cli("impact", "t:req", *bad)
claim("C3a", "impact t:req on an L1-invalid model exits non-zero and says to fix violations or pass --allow-invalid",
      rc != 0 and "--allow-invalid" in err and "fix the violations" in err and "element\tlabel" not in out,
      f"rc={rc}; {[l for l in err.splitlines() if 'refused' in l][:1]}")
rc, out, err = cli("impact", "t:req", "--allow-invalid", *bad)
claim("C3b", "impact --allow-invalid prints the result plus a warning banner (exit 0)",
      rc == 0 and "element\tlabel" in out and "IMPACT ON AN INVALID MODEL" in err,
      f"rc={rc}; stdout head={out.splitlines()[:1]}; banner={'IMPACT ON AN INVALID MODEL' in err}")
rc, out, err = cli("impact", "procurement:quotation", *MODEL_FILES)
claim("G9-valid", "impact on the valid procurement example runs without refusal or banner",
      rc == 0 and "element\tlabel" in out and "refused" not in err and "INVALID MODEL" not in err, f"rc={rc}")

# ---- C4 (G10) gate is atomic L0..L4
d = tempfile.mkdtemp(prefix="aisep-g10-")
for f in MODEL_FILES:
    src = open(f, encoding="utf-8").read()
    if os.path.basename(f) == "am4.ttl":
        src += "\n:quoteApproval am4:accesses :quotation .\n"
    open(os.path.join(d, os.path.basename(f)), "w", encoding="utf-8").write(src)
mut = sorted(glob.glob(os.path.join(d, "*.ttl")))
rc_g, out_g, _ = cli("gate", *mut)
rc_v, out_v, _ = cli("validate", *mut)
summ = [l for l in out_g.splitlines() if l.startswith("SUMMARY gate")]
claim("C4", "hand-written direct triple :quoteApproval am4:accesses :quotation -> gate exits 1 with ONE combined summary "
            "(validate alone may pass)",
      rc_g == 1 and len(summ) == 1 and "result=FAIL" in summ[0] and "direct triple written in source" in out_g,
      f"gate rc={rc_g} {summ}; validate rc={rc_v}")
rc, out, _ = cli("gate", *MODEL_FILES)
summ = [l for l in out.splitlines() if l.startswith("SUMMARY gate")]
claim("G10-valid", "gate on the valid procurement example: exit 0, one summary, result=PASS",
      rc == 0 and len(summ) == 1 and "result=PASS" in summ[0], summ)
doc = open(os.path.join(ROOT, "docs", "module-contract.md"), encoding="utf-8").read()
claim("G10-doc", "CONTRACT says CI and pre-commit use only `aisep.py gate`",
      "CI and pre-commit run **only** `aisep.py gate`" in doc, "CONTRACT.md CLI section")

print(f"SUMMARY review-g7-g10 confirmed={sum(results)}/{len(results)}")
sys.exit(0 if all(results) else 1)
