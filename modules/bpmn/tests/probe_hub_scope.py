"""Probe for spec §10.2: alignment axioms and validation scope must be kept apart.

Runs the vendored ArchiMate 4.0 shapes (archimate4_shapes.ttl) over the VALID BPMN fixture twice:
  A) BPMN alignment (modules/bpmn/align.ttl) IN the data graph   -> expected: FAILS (false positive:
     bpmn:SequenceFlow becomes an am4:Triggering, and task -> gateway is not in the am4 matrix)
  B) BPMN alignment EXCLUDED (inheritsHubRules=false)            -> expected: PASSES
It also checks that the same alignment does make BPMN visible to hub queries (what §7.1 needs).
Exit 0 iff A fails, B passes and the query assertions hold.

Run: /Users/yongqian/Desktop/AISEP/spike-linked-archi/.venv/bin/python modules/bpmn/tests/probe_hub_scope.py
"""
import os
import sys

import pyshacl
import rdflib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TTL = os.path.join(ROOT, "vendor", "meta.linked.archi", "ttl")
FIXTURE = os.path.join(ROOT, "modules", "bpmn", "tests", "valid", "quote-approval-process.ttl")
ALIGN = os.path.join(ROOT, "modules", "bpmn", "align.ttl")
ONTOS = ["core.ttl", "archimate4_onto.ttl", "bpmn_infra.ttl", "bpmn_onto.ttl"]
SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")


def data_graph(with_alignment):
    g = rdflib.Graph().parse(FIXTURE)
    for f in ONTOS:  # ontologies in the data graph, as AISEP L3 does (sh:targetClass follows rdfs:subClassOf there)
        g.parse(os.path.join(TTL, f))
    if with_alignment:
        g.parse(ALIGN)
    return g


def run(shapes, with_alignment):
    ok, report, _ = pyshacl.validate(data_graph(with_alignment), shacl_graph=shapes,
                                     inference="none", allow_warnings=True)
    focus = sorted({str(f).rsplit("/", 1)[-1] for f in report.objects(None, SH.focusNode)})
    srcs = sorted({str(s).rsplit("#", 1)[-1] for s in report.objects(None, SH.sourceShape)
                   if isinstance(s, rdflib.URIRef)})
    return ok, focus, srcs


def main():
    shapes = rdflib.Graph().parse(os.path.join(TTL, "archimate4_shapes.ttl"))
    a_ok, a_focus, a_src = run(shapes, True)
    print(f"A) am4 shapes, BPMN alignment IN data graph : conforms={a_ok}  "
          f"(expected False) focus={a_focus} shapes={a_src}")
    b_ok, b_focus, b_src = run(shapes, False)
    print(f"B) am4 shapes, BPMN alignment EXCLUDED      : conforms={b_ok}  "
          f"(expected True) focus={b_focus} shapes={b_src}")

    # Query side (§7.1): with the alignment loaded, hub queries see BPMN; tasks are NOT promoted (D4).
    g = data_graph(True)
    pre = ("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
           "PREFIX am4: <https://meta.linked.archi/archimate4/onto#> ")
    procs = {str(r[0]).rsplit("/", 1)[-1] for r in g.query(pre + "SELECT ?x WHERE { ?x a/rdfs:subClassOf* am4:Process }")}
    trig = {str(r[0]).rsplit("/", 1)[-1] for r in g.query(pre + "SELECT ?x WHERE { ?x a/rdfs:subClassOf* am4:Triggering }")}
    evts = {str(r[0]).rsplit("/", 1)[-1] for r in g.query(pre + "SELECT ?x WHERE { ?x a/rdfs:subClassOf* am4:Event }")}
    print(f"Q) with alignment: am4:Process={sorted(procs)} am4:Triggering={len(trig)} am4:Event={sorted(evts)}")

    checks = {
        "A fails (false positive reproduced)": a_ok is False and "TriggeringShape" in a_src,
        "B passes (alignment excluded)": b_ok is True,
        "Q only the bpmn:Process is an am4:Process (tasks not promoted, D4)": procs == {"proc"},
        "Q all 6 sequence flows are am4:Triggering": len(trig) == 6,
        "Q start/end events are am4:Event": evts == {"start", "end"},
    }
    for k, v in checks.items():
        print(("CONFIRMED " if v else "REFUTED   ") + k)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
