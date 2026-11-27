"""BPMN processes -> BPMN 2.0 XML with BPMNDI, generated from the model (no coordinates are stored anywhere).

One picture = one `bpmn:Process` and its `bpmn:flowElements` (docs/history design note 2026-11-27: BPMN's own boundary,
the unit bpmn.io and Camunda use; no arch:Diagram is declared). The XML is standard BPMN 2.0 (OMG namespaces), meant to
be shown by a stock BPMN viewer such as bpmn-js; `id` = the IRI's local name, `targetNamespace` = the process IRI's
namespace (spec §3: `{model}{local}`), so an id maps back to the model element.

Drawn: start/end/intermediate events, tasks (all task kinds and call activities), the five gateway kinds, sequence flows
(name from skos:prefLabel, a gateway's bpmn:default). Everything else a process refers to (lanes, sub-processes, data
objects, event definitions, ...) is reported as a warning and left out of both the semantic part and the DI, never
dropped silently.

Layout is ELK layered (elkjs, pinned in tools/elk/package-lock.json, same pipeline as aisep/diagram.py) with fixed
options and seed, left to right. Coordinates are rounded to integers. The output is a pure function of the model:
same model, same bytes.
"""
import re
from xml.sax.saxutils import escape as _esc

from aisep.core import NS
from aisep.diagram import elk_layout, local, tw, wrap

BPMN = NS["bpmn"]

# bpmn class local name -> (XML element, kind); kind decides the shape size and where its label goes
NODES = {
    "StartEvent": ("startEvent", "event"), "EndEvent": ("endEvent", "event"),
    "IntermediateCatchEvent": ("intermediateCatchEvent", "event"),
    "IntermediateThrowEvent": ("intermediateThrowEvent", "event"),
    "Task": ("task", "task"), "UserTask": ("userTask", "task"), "ServiceTask": ("serviceTask", "task"),
    "SendTask": ("sendTask", "task"), "ReceiveTask": ("receiveTask", "task"), "ManualTask": ("manualTask", "task"),
    "ScriptTask": ("scriptTask", "task"), "BusinessRuleTask": ("businessRuleTask", "task"),
    "CallActivity": ("callActivity", "task"),
    "ExclusiveGateway": ("exclusiveGateway", "gateway"), "ParallelGateway": ("parallelGateway", "gateway"),
    "InclusiveGateway": ("inclusiveGateway", "gateway"), "EventBasedGateway": ("eventBasedGateway", "gateway"),
    "ComplexGateway": ("complexGateway", "gateway"),
}
ORDER = list(NODES)  # semantic elements are written by kind in this order, then by id
SIZE = {"event": (36, 36), "gateway": (50, 50)}  # bpmn-js defaults; tasks are 100x80, widened for long names
TASK_W, TASK_H, TASK_W_MAX, LABEL_W = 100, 80, 200, 90
NCNAME = re.compile(r"[A-Za-z_][\w.-]*\Z")

ELK_OPTIONS = {
    "elk.algorithm": "layered", "elk.direction": "RIGHT", "elk.randomSeed": "1", "elk.edgeRouting": "ORTHOGONAL",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.spacing.nodeNode": "40", "elk.layered.spacing.nodeNodeBetweenLayers": "60",
    "elk.spacing.edgeNode": "20", "elk.spacing.edgeEdge": "12", "elk.spacing.edgeLabel": "4",
    "elk.edgeLabels.placement": "CENTER", "elk.padding": "[top=30,left=30,bottom=30,right=30]",
}


def _bpmn_type(ctx, x):
    """The most specific asserted bpmn: type local name of x, or None."""
    ts = sorted(local(t) for t in ctx.specific(x) if t.startswith(BPMN))
    return ts[0] if ts else None


def processes(ctx):
    """[(process IRI, label, model IRI)] for every bpmn:Process that is a model member, sorted by IRI."""
    out = []
    for x in sorted(ctx.asserted):
        if ctx.is_a(x, BPMN + "Process"):
            ms = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{x}> arch:inModel ?m }}"))
            out.append((x, ctx.label(x), ms[0] if ms else ""))
    return out


def select(ctx, process):
    """{"process", "label", "model", "attrs", "nodes", "flows"} and warnings. nodes: [{iri,id,type,label}];
    flows: [{iri,id,label,source,target}]. Raises ValueError when `process` is not a bpmn:Process of a model."""
    if process not in ctx.asserted or not ctx.is_a(process, BPMN + "Process"):
        raise ValueError(f"{process} is not a bpmn:Process member of any model")
    model = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{process}> arch:inModel ?m }}"))[0]
    warnings, nodes, pending = [], [], []
    members = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{process}> bpmn:flowElements ?m }}"))
    for x in members:
        t = _bpmn_type(ctx, x) if x in ctx.asserted else None
        if t in NODES:
            nodes.append({"iri": x, "id": local(x), "type": t, "label": ctx.label(x)})
            for (d,) in ctx.rows(f"SELECT ?d WHERE {{ <{x}> bpmn:eventDefinitions ?d }}"):
                warnings.append(f"{x}: bpmn:eventDefinitions {d} not drawn (event definitions unsupported)")
        elif t == "SequenceFlow":
            pending.append(x)
        else:
            warnings.append(f"{x}: {('bpmn:' + t) if t else 'untyped or not a model member'} not drawn (unsupported)")
    drawn = {n["iri"] for n in nodes}
    flows = []
    for x in pending:
        ends = sorted(ctx.rows(f"SELECT ?s ?t WHERE {{ <{x}> arch:source ?s ; arch:target ?t }}"))
        if len(ends) != 1 or ends[0][0] not in drawn or ends[0][1] not in drawn:
            warnings.append(f"{x}: bpmn:SequenceFlow not drawn (source or target is not a drawn flow node of {local(process)})")
            continue
        flows.append({"iri": x, "id": local(x), "label": ctx.label(x), "source": ends[0][0], "target": ends[0][1]})
    flow_iris = {f["iri"] for f in flows}
    for n in nodes:
        ds = sorted(d for (d,) in ctx.rows(f"SELECT ?d WHERE {{ <{n['iri']}> bpmn:default ?d }}"))
        n["default"] = local(ds[0]) if ds and ds[0] in flow_iris else None
        gd = sorted(v for (v,) in ctx.rows(f"SELECT ?v WHERE {{ <{n['iri']}> bpmn:gatewayDirection ?v }}"))
        n["direction"] = gd[0] if gd and NODES[n["type"]][1] == "gateway" else None
        if ds and ds[0] not in flow_iris:
            warnings.append(f"{n['iri']}: bpmn:default {ds[0]} is not a drawn sequence flow, not written")
    for (ls,) in sorted(ctx.rows(f"SELECT ?l WHERE {{ <{process}> bpmn:laneSets ?l }}")):
        lanes = sorted(l for (l,) in ctx.rows(f"SELECT ?l WHERE {{ <{ls}> bpmn:lanes ?l }}"))
        for lane in lanes or [ls]:
            warnings.append(f"{lane}: bpmn:{'Lane' if lanes else 'LaneSet'} not drawn (lanes unsupported)")
    attrs = {}
    for p in ("processType", "isExecutable"):
        vs = sorted(v for (v,) in ctx.rows(f"SELECT ?v WHERE {{ <{process}> bpmn:{p} ?v }}"))
        if vs:
            attrs[p] = vs[0]
    ids = [local(process)] + [n["id"] for n in nodes] + [f["id"] for f in flows]
    bad = [i for i in ids if not NCNAME.match(i)]
    if bad:
        raise ValueError(f"local names that are not XML ids (NCName): {bad[:3]}")
    di = [f"{i}_di" for i in ids] + [f"{local(process)}_diagram", f"{local(process)}_plane"]
    dup = sorted({i for i in ids + di if (ids + di).count(i) > 1})
    if dup:
        raise ValueError(f"local names collide as XML ids: {dup[:3]}")
    return {"process": process, "label": ctx.label(process), "model": model, "attrs": attrs,
            "nodes": nodes, "flows": flows}, warnings


# ------------------------------------------------------------------ layout (ELK, tools/elk)

def _text_box(label, px, max_w):
    lines = wrap(label, max_w, px) if label else []
    return (max((tw(l, px) for l in lines), default=0), len(lines) * (px + 3))


def _geometry(n):
    """(shape w, shape h, label w, label h) of a node; tasks carry their name inside the shape."""
    kind = NODES[n["type"]][1]
    if kind == "task":
        w = TASK_W
        while len(wrap(n["label"], w - 20, 12)) > 3 and w < TASK_W_MAX:  # bpmn-js draws 12px text; 3 lines leave padding in 80
            w += 20
        return w, TASK_H, 0, 0
    w, h = SIZE[kind]
    lw, lh = _text_box(n["label"], 11, LABEL_W)
    return w, h, (round(lw) + 4 if lw else 0), lh


def layout(sel):
    """{node iri: (shape x, y, w, h, label box or None)}, {flow iri: ([waypoints], label box or None)}, integers.
    Events and gateways carry their name as an ELK outside label below the shape (bpmn-js external label)."""
    geo, children = {}, []
    for i, n in enumerate(sorted(sel["nodes"], key=lambda n: n["iri"])):
        w, h, lw, lh = _geometry(n)
        geo[n["iri"]] = f"n{i}"
        node = {"id": f"n{i}", "width": w, "height": h}
        if lw:  # ELK reserves room for an outside label (node margins), so it overlaps neither nodes nor edges
            node["labels"] = [{"id": f"n{i}l", "text": n["label"], "width": lw, "height": lh, "layoutOptions":
                               {"elk.nodeLabels.placement": "OUTSIDE V_BOTTOM H_CENTER"}}]
        children.append(node)
    edges, flows = [], sorted(sel["flows"], key=lambda f: f["iri"])
    for i, f in enumerate(flows):
        e = {"id": f"e{i}", "sources": [geo[f["source"]]], "targets": [geo[f["target"]]]}
        if f["label"]:
            lw, lh = _text_box(f["label"], 11, LABEL_W)
            # ELK ignores a label with empty text
            e["labels"] = [{"id": f"e{i}l", "text": f["label"], "width": round(lw) + 4, "height": lh}]
        edges.append(e)
    out = elk_layout({"id": "root", "layoutOptions": ELK_OPTIONS, "children": children, "edges": edges})
    pos = {c["id"]: c for c in out.get("children", [])}
    shapes = {}
    for iri, nid in geo.items():
        c = pos[nid]
        label = None
        for l in c.get("labels", []):  # relative to the node
            label = (round(c["x"] + l["x"]), round(c["y"] + l["y"]), round(l["width"]), round(l["height"]))
        shapes[iri] = (round(c["x"]), round(c["y"]), c["width"], c["height"], label)
    routes = {}
    for f, e in zip(flows, sorted(out.get("edges", []), key=lambda e: int(e["id"][1:]))):
        s = e["sections"][0]
        pts = [s["startPoint"]] + s.get("bendPoints", []) + [s["endPoint"]]
        label = None
        for l in e.get("labels", []):
            label = (round(l["x"]), round(l["y"]), round(l["width"]), round(l["height"]))
        routes[f["iri"]] = ([(round(p["x"]), round(p["y"])) for p in pts], label)
    return shapes, routes


# ------------------------------------------------------------------ BPMN 2.0 XML

def _a(v):
    """An XML attribute value: escaped, quoted."""
    return '"' + _esc(str(v), {'"': "&quot;"}) + '"'


def render(sel):
    """BPMN 2.0 XML (semantic part + BPMNDI) for a selection from select()."""
    shapes, routes = layout(sel) if sel["nodes"] else ({}, {})
    pid = local(sel["process"])
    ns = sel["process"][: len(sel["process"]) - len(pid)]
    inc, outg = {}, {}
    for f in sel["flows"]:
        outg.setdefault(f["source"], []).append(f["id"])
        inc.setdefault(f["target"], []).append(f["id"])
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
           'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
           f'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id={_a(pid + "_definitions")} '
           f'targetNamespace={_a(ns)} exporter="AISEP tools/aisep.py diagram">']
    pattrs = "".join(f" {k}={_a(v)}" for k, v in sorted(sel["attrs"].items()))
    out.append(f'  <bpmn:process id={_a(pid)}' + (f' name={_a(sel["label"])}' if sel["label"] else "") + pattrs + ">")
    for n in sorted(sel["nodes"], key=lambda n: (ORDER.index(n["type"]), n["id"])):
        tag = NODES[n["type"]][0]
        attrs = (f' name={_a(n["label"])}' if n["label"] else "") + \
                (f' gatewayDirection={_a(n["direction"])}' if n.get("direction") else "") + (f' default={_a(n["default"])}' if n["default"] else "")
        kids = [f"      <bpmn:incoming>{_esc(i)}</bpmn:incoming>" for i in sorted(inc.get(n["iri"], []))] + \
               [f"      <bpmn:outgoing>{_esc(i)}</bpmn:outgoing>" for i in sorted(outg.get(n["iri"], []))]
        if kids:
            out += [f"    <bpmn:{tag} id={_a(n['id'])}{attrs}>"] + kids + [f"    </bpmn:{tag}>"]
        else:
            out.append(f"    <bpmn:{tag} id={_a(n['id'])}{attrs} />")
    by = {n["iri"]: n for n in sel["nodes"]}
    for f in sorted(sel["flows"], key=lambda f: f["id"]):
        out.append(f'    <bpmn:sequenceFlow id={_a(f["id"])}' + (f' name={_a(f["label"])}' if f["label"] else "") +
                   f' sourceRef={_a(by[f["source"]]["id"])} targetRef={_a(by[f["target"]]["id"])} />')
    out += ["  </bpmn:process>", f'  <bpmndi:BPMNDiagram id={_a(pid + "_diagram")}>',
            f'    <bpmndi:BPMNPlane id={_a(pid + "_plane")} bpmnElement={_a(pid)}>']
    def label(box):
        if not box:
            return []
        x, y, w, h = box
        return ["        <bpmndi:BPMNLabel>", f'          <dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" />',
                "        </bpmndi:BPMNLabel>"]
    for n in sorted(sel["nodes"], key=lambda n: (ORDER.index(n["type"]), n["id"])):
        x, y, w, h, lb = shapes[n["iri"]]
        marker = ' isMarkerVisible="true"' if n["type"] == "ExclusiveGateway" else ""
        out += [f'      <bpmndi:BPMNShape id={_a(n["id"] + "_di")} bpmnElement={_a(n["id"])}{marker}>',
                f'        <dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" />'] + label(lb) + \
               ["      </bpmndi:BPMNShape>"]
    for f in sorted(sel["flows"], key=lambda f: f["id"]):
        pts, lb = routes[f["iri"]]
        out += [f'      <bpmndi:BPMNEdge id={_a(f["id"] + "_di")} bpmnElement={_a(f["id"])}>'] + \
               [f'        <di:waypoint x="{x}" y="{y}" />' for x, y in pts] + label(lb) + ["      </bpmndi:BPMNEdge>"]
    out += ["    </bpmndi:BPMNPlane>", "  </bpmndi:BPMNDiagram>", "</bpmn:definitions>"]
    return "\n".join(out) + "\n"
