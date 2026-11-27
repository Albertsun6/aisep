"""Acceptance test for `aisep.py diagram --process` (bpmn:Process -> BPMN 2.0 XML with BPMNDI generated from the model).

Every expected set or number comes from an independent SPARQL query run through `aisep.py query`, never from
aisep/diagram_bpmn.py. The XML is also read by bpmn-moddle (tools/bpmn-check, the parser bpmn-js imports with), which
must report no warning. Each check is paired with a mutation control: a deliberately broken copy of a real output that
the check must catch. Each claim prints CONFIRMED / REFUTED with evidence; exit 0 only if every claim is CONFIRMED.

Run:  <venv python> tests/acceptance/test_diagram_bpmn.py      (also run by `aisep.py test`; needs
      `npm ci --prefix tools/elk --ignore-scripts` and `npm ci --prefix tools/bpmn-check --ignore-scripts`)
"""
import copy, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
CHECK = os.path.join(ROOT, "tools", "bpmn-check")
M = "https://aisep.example/model/"
X = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
     "dc": "http://www.omg.org/spec/DD/20100524/DC", "di": "http://www.omg.org/spec/DD/20100524/DI"}
LANE_FIXTURE = os.path.join(ROOT, "modules", "bpmn", "tests", "valid", "quote-approval-process.ttl")
results = []


def run(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def files(slug, d=None):
    return sorted(glob.glob(os.path.join(d or os.path.join(ROOT, "models", slug), "*.ttl")))


def rows(q, fs):
    rc, out = run("query", q, *fs)
    assert rc == 0, out
    return [tuple(l.split("\t")) for l in out.splitlines()[1:] if l and not l.startswith("--")]


def loc(s):
    """Local name of a full IRI or of the short slug:local form `aisep.py query` prints."""
    return s.rsplit("/", 1)[-1].rsplit(":", 1)[-1] if "://" in s else s.split(":", 1)[-1]


def claim(text, ok, evidence):
    results.append(ok)
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {text}\n      evidence: {evidence}")


def moddle(*paths):
    """bpmn-moddle fromXML over the files: {path: {"warnings": [...], "error": ...}}."""
    if not os.path.isdir(os.path.join(CHECK, "node_modules", "bpmn-moddle")):
        return {p: {"warnings": [], "error": "bpmn-moddle not installed: npm ci --prefix tools/bpmn-check "
                                            "--ignore-scripts"} for p in paths}
    p = subprocess.run(["node", os.path.join(CHECK, "check.cjs"), *paths], cwd=CHECK, capture_output=True, text=True,
                       timeout=120)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# ------------------------------------------------------------------ independent facts (SPARQL)

def facts(process, fs):
    """Expected semantic part of a process: {local id: (bpmn type local, label)}, flows {id: (src, tgt, label)}, defaults
    {id: default flow id}, attrs {"" (the process) or id: {XML attribute: value}}."""
    pre = f"PREFIX bpmn: <https://meta.linked.archi/bpmn/onto#> "
    els = rows(pre + f"""SELECT ?m ?t (SAMPLE(?l) AS ?lab) WHERE {{ <{process}> bpmn:flowElements ?m . ?m a ?t
                         FILTER(STRSTARTS(STR(?t), STR(bpmn:))) OPTIONAL {{ ?m skos:prefLabel ?l }} }} GROUP BY ?m ?t""", fs)
    nodes = {loc(m): (loc(t), l) for m, t, l in els if loc(t) != "SequenceFlow"}
    flows = {}
    for m, s, t, l in rows(pre + f"""SELECT ?m ?s ?t ?l WHERE {{ <{process}> bpmn:flowElements ?m . ?m a bpmn:SequenceFlow ;
                                    arch:source ?s ; arch:target ?t OPTIONAL {{ ?m skos:prefLabel ?l }} }}""", fs):
        flows[loc(m)] = (loc(s), loc(t), l)
    defaults = {loc(g): loc(d) for g, d in rows(pre + f"""SELECT ?g ?d WHERE {{ <{process}> bpmn:flowElements ?g .
                                                     ?g bpmn:default ?d }}""", fs)}
    attrs = {"": {loc(k): v for k, v in rows(pre + f"""SELECT ?k ?v WHERE {{ <{process}> ?k ?v
                                                      FILTER(?k IN (bpmn:processType, bpmn:isExecutable)) }}""", fs)}}
    for m, k, v in rows(pre + f"""SELECT ?m ?k ?v WHERE {{ <{process}> bpmn:flowElements ?m . ?m ?k ?v
                                  FILTER(?k IN (bpmn:gatewayDirection, bpmn:isInterrupting)) }}""", fs):
        attrs.setdefault(loc(m), {})[loc(k)] = v
    return nodes, flows, defaults, attrs


# ------------------------------------------------------------------ checks over the XML (each has a mutation control)

TAG = {"StartEvent": "startEvent", "EndEvent": "endEvent", "UserTask": "userTask", "ServiceTask": "serviceTask",
       "ExclusiveGateway": "exclusiveGateway", "Task": "task"}


def semantic_problems(root, process, nodes, flows, defaults, attrs):
    out = []
    procs = root.findall("bpmn:process", X)
    if len(procs) != 1 or procs[0].get("id") != loc(process):
        return [f"process element: {[p.get('id') for p in procs]}"]
    pa = {k: v for k, v in procs[0].attrib.items() if k not in ("id", "name")}
    if pa != attrs.get("", {}):
        out.append(f"process attributes {pa}, want {attrs.get('', {})}")
    got = {e.get("id"): e for e in procs[0]}
    want = set(nodes) | set(flows)
    if set(got) != want:
        out.append(f"ids: only_xml={sorted(set(got) - want)[:3]} only_model={sorted(want - set(got))[:3]}")
    for i, (t, label) in nodes.items():
        e = got.get(i)
        if e is None:
            continue
        if e.tag != f"{{{X['bpmn']}}}{TAG.get(t, t)}" or e.get("name") != label:
            out.append(f"{i}: tag={e.tag.split('}')[1]} name={e.get('name')!r}, want {TAG.get(t, t)} {label!r}")
        if e.get("default") != defaults.get(i):
            out.append(f"{i}: default={e.get('default')} want {defaults.get(i)}")
        na = {k: v for k, v in e.attrib.items() if k not in ("id", "name", "default")}
        if na != attrs.get(i, {}):
            out.append(f"{i}: attributes {na}, want {attrs.get(i, {})}")
    for i, (s, t, label) in flows.items():
        e = got.get(i)
        if e is not None and (e.get("sourceRef"), e.get("targetRef"), e.get("name") or "") != (s, t, label or ""):
            out.append(f"{i}: {e.get('sourceRef')}->{e.get('targetRef')} {e.get('name')!r}, want {s}->{t} {label!r}")
    return out


def di_problems(root, process, nodes, flows):
    out = []
    ids = [e.get("id") for e in root.iter() if e.get("id")]
    if len(ids) != len(set(ids)):
        out.append(f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})[:3]}")
    planes = root.findall("bpmndi:BPMNDiagram/bpmndi:BPMNPlane", X)
    if len(planes) != 1 or planes[0].get("bpmnElement") != loc(process):
        return out + ["BPMNPlane missing or not on the process"]
    shapes = [s.get("bpmnElement") for s in planes[0].findall("bpmndi:BPMNShape", X)]
    edges = [s.get("bpmnElement") for s in planes[0].findall("bpmndi:BPMNEdge", X)]
    if sorted(shapes) != sorted(nodes):
        out.append(f"shapes: {len(shapes)} for {len(nodes)} nodes, only_di={sorted(set(shapes) - set(nodes))[:3]} "
                   f"missing={sorted(set(nodes) - set(shapes))[:3]}")
    if sorted(edges) != sorted(flows):
        out.append(f"edges: {len(edges)} for {len(flows)} flows, missing={sorted(set(flows) - set(edges))[:3]}")
    dangling = [r for r in shapes + edges if r not in ids]
    if dangling:
        out.append(f"bpmnElement not in the document: {dangling[:3]}")
    return out


def geometry(root):
    sem = {e.get("id"): e for e in root.iter() if e.get("id")}
    boxes, paths = {}, {}
    for s in root.iter(f"{{{X['bpmndi']}}}BPMNShape"):
        b = s.find("dc:Bounds", X)
        boxes[s.get("bpmnElement")] = tuple(b.get(k) for k in ("x", "y", "width", "height"))
    for e in root.iter(f"{{{X['bpmndi']}}}BPMNEdge"):
        f = sem.get(e.get("bpmnElement"))
        paths[e.get("bpmnElement")] = ([(p.get("x"), p.get("y")) for p in e.findall("di:waypoint", X)],
                                       f.get("sourceRef") if f is not None else None,
                                       f.get("targetRef") if f is not None else None)
    return boxes, paths


def on_border(p, box, tol=1):
    x, y, w, h = box
    px, py = p
    return ((abs(px - x) <= tol or abs(px - x - w) <= tol) and y - tol <= py <= y + h + tol) or \
           ((abs(py - y) <= tol or abs(py - y - h) <= tol) and x - tol <= px <= x + w + tol)


def geometry_problems(root):
    boxes, paths = geometry(root)
    raw = [v for b in boxes.values() for v in b] + [v for pts, _, _ in paths.values() for p in pts for v in p]
    if not all(v is not None and v.lstrip("-").isdigit() for v in raw):
        return ["a coordinate is not an integer"]
    boxes = {k: tuple(int(v) for v in b) for k, b in boxes.items()}
    out = []
    ks = sorted(boxes)
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            (ax, ay, aw, ah), (bx, by, bw, bh) = boxes[a], boxes[b]
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                out.append(f"shapes overlap: {a} {b}")
    for lb in root.iter(f"{{{X['bpmndi']}}}BPMNLabel"):  # names never cover a shape
        lx, ly, lw, lh = (int(lb.find("dc:Bounds", X).get(k)) for k in ("x", "y", "width", "height"))
        for k, (bx, by, bw, bh) in sorted(boxes.items()):
            if lx < bx + bw and bx < lx + lw and ly < by + bh and by < ly + lh:
                out.append(f"a label covers shape {k}")
    for f, (pts, s, t) in sorted(paths.items()):
        pts = [(int(x), int(y)) for x, y in pts]
        if len(pts) < 2 or s not in boxes or t not in boxes:
            out.append(f"{f}: {len(pts)} waypoints, source/target shape {s in boxes}/{t in boxes}"); continue
        if not (on_border(pts[0], boxes[s]) and on_border(pts[-1], boxes[t])):
            out.append(f"{f}: does not start on {s} and end on {t}")
        if any(a[0] != b[0] and a[1] != b[1] for a, b in zip(pts, pts[1:])):
            out.append(f"{f}: not orthogonal")
    return out


def all_problems(root, process, nodes, flows, defaults, attrs):
    return (semantic_problems(root, process, nodes, flows, defaults, attrs) + di_problems(root, process, nodes, flows)
            + geometry_problems(root))


# ------------------------------------------------------------------ mutation controls

def mutants(root):
    """(name, broken copy) pairs; every one must be caught by the checks above."""
    out = []
    plane = root.find("bpmndi:BPMNDiagram/bpmndi:BPMNPlane", X)
    m = copy.deepcopy(root)  # one flow drawn backwards
    e = m.find("bpmndi:BPMNDiagram/bpmndi:BPMNPlane/bpmndi:BPMNEdge", X)
    wps = e.findall("di:waypoint", X)
    for w in wps:
        e.remove(w)
    for i, w in enumerate(reversed(wps)):
        e.insert(i, w)
    out.append(("an edge's waypoints reversed", m))
    m = copy.deepcopy(root)  # a shape dropped
    p = m.find("bpmndi:BPMNDiagram/bpmndi:BPMNPlane", X)
    p.remove(p.find("bpmndi:BPMNShape", X))
    out.append(("a BPMNShape deleted", m))
    m = copy.deepcopy(root)  # a sourceRef changed to another existing node
    sf = m.findall("bpmn:process/bpmn:sequenceFlow", X)
    sf[0].set("sourceRef", sf[0].get("targetRef"))
    out.append(("a sourceRef changed", m))
    m = copy.deepcopy(root)  # two shapes moved onto each other
    bs = m.findall("bpmndi:BPMNDiagram/bpmndi:BPMNPlane/bpmndi:BPMNShape/dc:Bounds", X)
    bs[1].set("x", bs[0].get("x")); bs[1].set("y", bs[0].get("y"))
    out.append(("two shapes overlapping", m))
    m = copy.deepcopy(root)  # an external label moved onto a shape
    lb = m.find(".//bpmndi:BPMNLabel/dc:Bounds", X)
    sb = m.find(".//bpmndi:BPMNShape/dc:Bounds", X)
    lb.set("x", sb.get("x")); lb.set("y", sb.get("y"))
    out.append(("a label moved onto a shape", m))
    m = copy.deepcopy(root)  # a name changed
    m.find("bpmn:process/bpmn:userTask", X).set("name", "改坏的名称")
    out.append(("a task name changed", m))
    for path, a in (("bpmn:process", "processType"), ("bpmn:process", "isExecutable"),
                    ("bpmn:process/bpmn:exclusiveGateway", "gatewayDirection")):
        m = copy.deepcopy(root)  # an attribute the model states left out
        e = m.find(path, X)
        if e is not None and e.get(a) is not None:
            del e.attrib[a]
            out.append((f"{a} left out", m))
    assert plane is not None
    return out


def case(process, fs, tmp, want_nodes, want_flows, want_named=None):
    name = loc(process)
    out = os.path.join(tmp, name + ".bpmn")
    rc, log = run("diagram", "--process", process, "-o", out, *fs)
    claim(f"{name}: exit 0, SUMMARY printed, no warning", rc == 0 and "SUMMARY diagram" in log and "[Warning]" not in log
          and os.path.exists(out), log.strip().splitlines()[-1][:160])
    if rc != 0:
        return None
    xml = open(out, "rb").read()
    root = ET.fromstring(xml)
    nodes, flows, defaults, attrs = facts(process, fs)
    claim(f"{name}: model has the expected size ({want_nodes} flow nodes, {want_flows} sequence flows)",
          (len(nodes), len(flows)) == (want_nodes, want_flows), f"sparql nodes={len(nodes)} flows={len(flows)}")
    if want_named is not None:
        named = sum(1 for e in root.findall("bpmn:process/bpmn:sequenceFlow", X) if e.get("name"))
        claim(f"{name}: {want_named} sequence flows carry a name", named == want_named == sum(1 for f in flows.values()
              if f[2]), f"xml={named}")
    claim(f"{name}: the model states processType, isExecutable and gatewayDirection (so the check below has teeth)",
          {"processType", "isExecutable"} <= set(attrs[""]) and any("gatewayDirection" in a for a in attrs.values()),
          f"attrs={attrs}")
    for label, probs in (("semantic part equals the model (ids, types, names, ends, default, attributes)",
                          semantic_problems(root, process, nodes, flows, defaults, attrs)),
                         ("DI complete (one shape per node, one edge per flow, refs resolve, ids unique)",
                          di_problems(root, process, nodes, flows)),
                         ("geometry (no shape or label overlap, flows start/end on their shapes, orthogonal, integers)",
                          geometry_problems(root))):
        claim(f"{name}: {label}", not probs, f"problems={probs[:3]}")
    caught = [(n, all_problems(m, process, nodes, flows, defaults, attrs)) for n, m in mutants(root)]
    claim(f"{name}: mutation control - every broken copy ({len(caught)}) is caught", all(p for _, p in caught),
          "; ".join(f"{n}: {p[0] if p else 'NOT CAUGHT'}" for n, p in caught)[:600])
    mo = moddle(out)[out]
    claim(f"{name}: bpmn-moddle reads it with no warning", mo["error"] is None and mo["warnings"] == [],
          f"error={mo['error']} warnings={mo['warnings'][:2]}")
    out2 = os.path.join(tmp, name + ".2.bpmn")
    run("diagram", "--process", process, "-o", out2, *fs)
    claim(f"{name}: generating twice gives identical bytes (sha256)",
          hashlib.sha256(xml).hexdigest() == hashlib.sha256(open(out2, "rb").read()).hexdigest(),
          hashlib.sha256(xml).hexdigest()[:16])
    return root, xml


LP = f"{M}bpmn-test/proc"


def fixture(tmp, name, edit):
    """Draw LP from a copy of the lane fixture changed by edit(text): (exit code, log, [Warning] lines, xml or "",
    root or None (strict parse: expat rejects anything not well-formed), moddle result or None)."""
    txt = open(LANE_FIXTURE, encoding="utf-8").read()
    new = edit(txt)
    assert new != txt, name
    src, o = os.path.join(tmp, name + ".ttl"), os.path.join(tmp, name + ".bpmn")
    open(src, "w", encoding="utf-8").write(new)
    rc, log = run("diagram", "--process", LP, "-o", o, src)
    warns = [l for l in log.splitlines() if l.startswith("[Warning]")]
    xml = open(o, "rb").read() if os.path.exists(o) else b""
    try:
        root = ET.fromstring(xml) if xml else None
    except ET.ParseError as e:
        root, log = None, log + f"\nnot well-formed: {e}"
    return rc, log, warns, xml.decode("utf-8", "replace"), root, (moddle(o)[o] if xml else None), src


def clean(mo):
    return mo is not None and mo["error"] is None and mo["warnings"] == []


def probes(tmp):
    """Characters, ids and statements the picture cannot carry: each is either written faithfully or reported."""
    lane = f"[Warning] diagram {M}bpmn-test/buyerLane"
    # tab, LF, CR in a name: written as character references (a literal one is normalised to a space by any parser)
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "ctl-ok", lambda t: t.replace('"审核报价"@zh', '"审核\\n报价\\t签字\\r"@zh'))
    got = root.find("bpmn:process/bpmn:userTask[@id='review']", X).get("name") if root is not None else None
    claim("a name with tab/LF/CR: well-formed (expat), the name round-trips exactly, moddle clean",
          rc == 0 and got == "审核\n报价\t签字\r" and "&#10;" in xml and "&#9;" in xml and "&#13;" in xml and clean(mo),
          f"rc={rc} name={got!r} moddle={mo}")
    for ch in ("\\u0001", "\\u001F", "\\u0000"):
        rc, log, warns, xml, root, mo, _ = fixture(tmp, "ctl-bad", lambda t: t.replace('"审核报价"@zh', f'"审核{ch}报价"@zh'))
        claim(f"a name with C0 control {ch[1:]}: exit 1, [Violation] naming the element and the character, nothing written",
              rc == 1 and f"[Violation] diagram: {M}bpmn-test/review: skos:prefLabel contains U+{ch[2:].upper()}" in log
              and not xml, log.strip()[-160:])
    # (2a) a sequence flow between two drawn nodes that the process does not list
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "orphan-flow", lambda t: t + (
        ":sf7 a bpmn:SequenceFlow ; arch:inModel :model ; arch:source :review ; arch:target :end .\n"))
    claim("a SequenceFlow between drawn nodes but not in flowElements: one more [Warning] naming it, not written",
          rc == 0 and len(warns) == 2 and lane in "\n".join(warns) and f"{M}bpmn-test/sf7: bpmn:SequenceFlow" in "\n".join(warns)
          and 'id="sf7' not in xml and clean(mo), f"warnings={warns}")
    # (2b) bpmn:artifacts on the process
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "artifact", lambda t: t + (
        ':proc bpmn:artifacts :note .\n:note a bpmn:TextAnnotation ; arch:inModel :model ; skos:prefLabel "备注"@zh .\n'))
    claim("bpmn:artifacts (a TextAnnotation): one more [Warning] naming the predicate and the artifact, not written",
          rc == 0 and len(warns) == 2 and f"{M}bpmn-test/proc: bpmn:artifacts {M}bpmn-test/note" in "\n".join(warns)
          and "note" not in xml and "备注" not in xml and clean(mo), f"warnings={warns}")
    # (2b) bpmn:conditionExpression on a drawn flow
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "condition", lambda t: t + (
        ':sf3 bpmn:conditionExpression [ a bpmn:FormalExpression ; bpmn:body "amount > 1000" ] .\n'))
    claim("bpmn:conditionExpression on a drawn flow: one more [Warning] naming the flow and the predicate, not written",
          rc == 0 and len(warns) == 2 and f"{M}bpmn-test/sf3: bpmn:conditionExpression" in "\n".join(warns)
          and "condition" not in xml and "amount" not in xml and clean(mo), f"warnings={warns}")
    # (4) ids: an XML NCName that bpmn-moddle also accepts. A non-ASCII NCName is valid XML, but moddle drops the
    # element (control below), so it is refused instead of producing a picture bpmn-js shows with holes
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "ascii-id", lambda t: re.sub(r"(?<![\w:]):review\b", ":review_2.b-c", t))
    claim("an ASCII NCName with _ . - and digits is a valid id: exit 0, written, moddle clean",
          rc == 0 and 'id="review_2.b-c"' in xml and clean(mo), f"rc={rc} moddle={mo}")
    base = fixture(tmp, "plain", lambda t: t + "\n")[3]
    m = os.path.join(tmp, "cjk-moddle.bpmn")
    open(m, "w", encoding="utf-8").write(base.replace('"review', '"审核'))
    mo = moddle(m)[m]
    claim("control - bpmn-moddle refuses a non-ASCII NCName id (审核) that XML allows",
          any("illegal ID <审核>" in w for w in mo["warnings"]), f"warnings={mo['warnings'][:1]}")
    for name, bad in (("cjk-first", ":审核"), ("cjk-inside", ":review审核"), ("digit-first", ":1review")):
        rc, log, warns, xml, root, mo, _ = fixture(tmp, name, lambda t: re.sub(r"(?<![\w:]):review\b", bad, t))
        claim(f"a local name {bad[1:]!r} bpmn-moddle cannot load: exit 1, [Violation] naming it, nothing written",
              rc == 1 and "[Violation]" in log and bad[1:] in log and not xml, log.strip()[-160:])
    # (4) a member outside the process namespace: its id cannot be turned back into its IRI
    other = "https://aisep.example/model/other/end"
    rc, log, warns, xml, root, mo, _ = fixture(tmp, "other-ns", lambda t: re.sub(r"(?<![\w:]):end\b", f"<{other}>", t))
    claim("a flow element outside the process namespace: drawn, plus a [Warning] that its id does not map back",
          rc == 0 and len(warns) == 2 and f"[Warning] diagram {other}: outside the namespace" in "\n".join(warns)
          and 'id="end"' in xml and clean(mo), f"warnings={warns}")


def main():
    tmp = tempfile.mkdtemp(prefix="aisep-bpmn-")
    try:
        allf = sorted(glob.glob(os.path.join(ROOT, "models", "*", "*.ttl")))
        want = sorted(p for (p,) in rows("PREFIX bpmn: <https://meta.linked.archi/bpmn/onto#> "
                                         "SELECT ?p WHERE { ?p a bpmn:Process ; arch:inModel ?m }", allf))
        rc, log = run("diagram", "--list-processes", *allf)
        listed = sorted(f"{l.split(chr(9))[0][len(M):].replace('/', ':', 1)}" for l in log.splitlines()
                        if l.startswith(M))
        claim("--list-processes lists exactly the model's bpmn:Process members (3)", rc == 0 and listed == want
              and len(want) == 3, f"listed={listed}")

        p1 = f"{M}procurement/bpmnQuoteApproval"
        r1 = case(p1, files("procurement"), tmp, 6, 6)
        case(f"{M}workbench/bpmnApproverSelection", files("workbench"), tmp, 8, 8, want_named=3)
        case(f"{M}workbench/bpmnReleaseApproval", files("workbench"), tmp, 12, 12, want_named=6)
        if r1:
            root = r1[0]
            gw = root.find("bpmn:process/bpmn:exclusiveGateway[@id='bpmnAmountGateway']", X)
            rv = root.find("bpmn:process/bpmn:userTask[@id='bpmnReview']", X)
            claim("P1: bpmnReview is <bpmn:userTask name=\"审核报价单\">, gateway default=\"sf3\"",
                  rv is not None and rv.get("name") == "审核报价单" and gw is not None and gw.get("default") == "sf3",
                  f"review={rv is not None and rv.get('name')} default={gw is not None and gw.get('default')}")
            claim("P1: targetNamespace is the model namespace (id + namespace = the element IRI)",
                  root.get("targetNamespace") == f"{M}procurement/", root.get("targetNamespace"))

        # a moddle negative control: an unresolved reference must be reported (the checker is not blind)
        if r1:
            bad = os.path.join(tmp, "unresolved.bpmn")
            open(bad, "wb").write(r1[1].replace(b'targetRef="bpmnReview"', b'targetRef="noSuchNode"'))
            mo = moddle(bad)[bad]
            claim("mutation control - bpmn-moddle reports an unresolved targetRef", bool(mo["warnings"]),
                  f"warnings={mo['warnings'][:1]} error={mo['error']}")

        # not a process: Violation, nothing written
        o = os.path.join(tmp, "np.bpmn")
        rc, log = run("diagram", "--process", "procurement:quoteApproval", "-o", o, *files("procurement"))
        claim("an IRI that is not a bpmn:Process exits 1 with a Violation, writes nothing",
              rc == 1 and "[Violation]" in log and not os.path.exists(o), log.strip()[-120:])
        rc, log = run("diagram", "--process", "http://not an iri/", "-o", o, *files("procurement"))
        claim("--process that is not a valid IRI exits 1 with a Violation", rc == 1 and "[Violation]" in log
              and not os.path.exists(o), log.strip()[-120:])

        # unsupported structure (a lane): exactly one Warning naming it, not written, output still clean
        o = os.path.join(tmp, "lane.bpmn")
        rc, log = run("diagram", "--process", LP, "-o", o, LANE_FIXTURE)
        warns = [l for l in log.splitlines() if l.startswith("[Warning]")]
        xml = open(o, encoding="utf-8").read() if os.path.exists(o) else ""
        mo = moddle(o)[o] if xml else {"warnings": ["missing"], "error": None}
        claim("lane fixture: exit 0, exactly 1 [Warning] naming the lane IRI, no laneSet written, moddle clean",
              rc == 0 and len(warns) == 1 and f"{M}bpmn-test/buyerLane" in warns[0] and "laneSet" not in xml
              and "buyerLane" not in xml and mo["warnings"] == [] and mo["error"] is None, f"warnings={warns}")
        if xml:
            nodes, flows, defaults, attrs = facts(LP, [LANE_FIXTURE])
            probs = semantic_problems(ET.fromstring(xml.encode("utf-8")), LP, nodes, flows, defaults, attrs)
            claim("lane fixture: semantic part equals the model, incl. processType, isExecutable, gatewayDirection, "
                  "isInterrupting", not probs and attrs.get("start") == {"isInterrupting": "true"}, f"problems={probs[:3]}")
        probes(tmp)

        # text escaping and renaming: labels with < & " ' > survive exactly; ids do not move
        d = os.path.join(tmp, "proc")
        shutil.copytree(os.path.join(ROOT, "models", "procurement"), d)
        f = os.path.join(d, "bpmn.ttl")
        txt = open(f, encoding="utf-8").read()
        nasty = {'"审核报价单"@zh': ('"审核 <报价单> & \\"确认\\" \'签字\'"@zh', '审核 <报价单> & "确认" \'签字\''),
                 '"二级审批"@zh': ('"二级审批]]></bpmn:process>"@zh', '二级审批]]></bpmn:process>')}
        for old, (new, _) in nasty.items():
            assert txt.count(old) == 1, old
            txt = txt.replace(old, new)
        open(f, "w", encoding="utf-8").write(txt)
        o = os.path.join(tmp, "nasty.bpmn")
        rc, log = run("diagram", "--process", p1, "-o", o, *files("procurement", d))
        try:
            root = ET.parse(o).getroot() if rc == 0 else None
        except ET.ParseError as e:  # unescaped text: not well-formed XML
            root, log = None, f"not well-formed: {e}"
        claim("labels with < & \" ' ]]>: the output is well-formed XML", root is not None, log.strip()[-120:])
        names = {e.get("id"): e.get("name") for e in root.iter() if e.get("id")} if root is not None else {}
        mo = moddle(o)[o] if root is not None else {"warnings": [], "error": "not written or not well-formed"}
        claim("labels with < & \" ' ]]> are escaped: well-formed, names round-trip exactly, moddle clean",
              names.get("bpmnReview") == nasty['"审核报价单"@zh'][1]
              and names.get("bpmnSecondLevel") == nasty['"二级审批"@zh'][1] and mo["warnings"] == []
              and mo["error"] is None, f"review={names.get('bpmnReview')!r} error={mo['error']}")
        if r1 and root is not None:
            before = sorted(e.get("id") for e in r1[0].iter() if e.get("id"))
            refs = lambda r: sorted(e.get("bpmnElement") for e in r.iter() if e.get("bpmnElement"))
            claim("rename: every id and bpmnElement unchanged, only names differ",
                  before == sorted(names) and refs(r1[0]) == refs(root), f"ids={len(before)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"SUMMARY diagram-bpmn-acceptance claims={len(results)} confirmed={sum(results)} "
          f"result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
