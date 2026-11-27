"""Acceptance test for DDD views of `aisep.py diagram` (aisep/diagram_ddd.py): ContextMap and AggregateDiagram.

Input: the real models (models/procurement, models/workbench) and modules/ddd/tests/valid/context-map-legal.ttl in a
temp copy whose model IRI is rewritten to https://aisep.example/model/ddd-legal/ (so `--model ddd-legal` names it);
temp variants of that copy probe escaping and every warning. Every expected set and every end label comes from an
independent SPARQL query run through `aisep.py query`, never from aisep/diagram_ddd.py.
Each claim prints CONFIRMED / REFUTED with evidence; exit 0 only if every claim is CONFIRMED.

Run:  <venv python> tests/acceptance/test_diagram_ddd.py      (also run by `aisep.py test`)
"""
import os, re, shutil, subprocess, sys, tempfile
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
L = "https://aisep.example/model/ddd-legal/"
DDD = "https://aisep.example/ont/ddd#"
PFX = f"PREFIX ddd: <{DDD}> PREFIX l: <{L}> "
MAP_TYPES = "VALUES ?t { ddd:UpstreamDownstream ddd:CustomerSupplier ddd:Partnership ddd:SharedKernel ddd:SubdomainImplementation }"
results = []
# a role value that would close the IRI and comment out the rest if it were spliced into SPARQL text
INJECT = "https://aisep.example/ont/ddd#AntiCorruptionLayer> ?p ?v } #"


def run(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def rows(q, fs=()):
    rc, out = run("query", PFX + q, *fs)
    assert rc == 0, out
    return [tuple(l.split("\t")) for l in out.splitlines()[1:] if l and not l.startswith("--")]


def ids(q, fs=()):
    return {r[0] for r in rows(q, fs)}


def short(iri):
    """Model member IRIs as `aisep.py query` prints them: <slug>:<local>."""
    if iri and iri.startswith("https://aisep.example/model/") and iri.count("/") > 4:
        slug, local = iri[len("https://aisep.example/model/"):].split("/", 1)
        return f"{slug}:{local}"
    return iri


def claim(text, ok, evidence):
    results.append(ok)
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {text}\n      evidence: {evidence}")


def diagram(out, *args):
    rc, log = run("diagram", *args, "-o", out)
    assert rc == 0, log
    svg = open(out, encoding="utf-8").read()
    root = ElementTree.fromstring(svg)  # well-formed XML (raises otherwise)
    boxes, edges, labels = [], [], []
    for e in root.iter():
        k = e.get("data-kind")
        if k in ("element", "boundary", "aggregate"):
            r = next(c for c in e if c.tag.endswith("rect"))
            boxes.append({"kind": k, "iri": short(e.get("data-iri")), "type": e.get("data-type"),
                          "shape": (r.get("class"), r.get("rx")),
                          "parent": short(e.get("data-parent")) or None, "via": short(e.get("data-via")) or None,
                          "box": tuple(float(v) for v in e.get("data-box").split()),
                          "text": " ".join(t.text or "" for t in e.iter() if t.tag.endswith("text"))})
        elif k == "relationship":
            pts = [tuple(float(v) for v in p.split(",")) for p in e.get("d")[1:].split(" L")]
            edges.append({"iri": short(e.get("data-iri")), "type": e.get("data-type"), "source": short(e.get("data-source")),
                          "target": short(e.get("data-target")), "pts": pts})
        elif k == "edge-label":
            labels.append({"for": short(e.get("data-for")), "end": e.get("data-end"),
                           "box": tuple(float(v) for v in e.get("data-box").split()),
                           "text": " ".join(t.text or "" for t in e.iter() if t.tag.endswith("text"))})
    warnings = [l for l in log.splitlines() if l.startswith("[Warning]")]
    return svg, root, boxes, edges, labels, warnings


def legend(tree):
    """{data-legend key: {shape: (class, rx) of its swatch rect or None, text}} of the drawn legend."""
    out = {}
    for g in tree.iter():
        if g.get("data-kind") == "legend-item":
            r = next((c for c in g if c.tag.endswith("rect")), None)
            out[g.get("data-legend")] = {"shape": (r.get("class"), r.get("rx")) if r is not None else None,
                                         "text": " ".join(t.text or "" for t in g.iter() if t.tag.endswith("text"))}
    return out


def legend_key(b):
    """The legend entry that explains a drawn box (by its ddd: type; a root entity by its «聚合根» mark)."""
    return {"ddd:BoundedContext": "k:boundary" if b["kind"] == "boundary" else "k:bc",
            "ddd:Subdomain": "s:" + b["shape"][0].split()[-1], "ddd:Aggregate": "k:agg", "ddd:ValueObject": "k:vo",
            "ddd:Entity": "root:" if "«聚合根»" in b["text"] else "k:ent"}[b["type"]]


def legend_claims(name, tree, boxes):
    lg = legend(tree)
    bad = [(b["iri"], b["shape"], legend_key(b), (lg.get(legend_key(b)) or {}).get("shape")) for b in boxes
           if (lg.get(legend_key(b)) or {}).get("shape") != b["shape"]]
    want = {legend_key(b) for b in boxes if not legend_key(b).startswith("s:")}
    got = {k for k in lg if k.startswith(("k:", "root:"))}
    claim(f"{name}: every box looks like (css class, corner radius) its legend entry; legend lists exactly the box kinds drawn",
          not bad and got == want, f"mismatch={bad} legend={sorted(got)} drawn={sorted(want)}")
    return lg


def on_border(p, box, tol=1.5):
    x, y, w, h = box
    px, py = p
    vertical = (abs(px - x) <= tol or abs(px - x - w) <= tol) and y - tol <= py <= y + h + tol
    horizontal = (abs(py - y) <= tol or abs(py - y - h) <= tol) and x - tol <= px <= x + w + tol
    return vertical or horizontal


def dist(box, other):
    """Distance between the centre of box and the rectangle other."""
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    x, y, w, h = other
    return (max(x - cx, 0, cx - x - w) ** 2 + max(y - cy, 0, cy - y - h) ** 2) ** 0.5


def inside(box, outer, tol=0.5):
    x, y, w, h = box
    X, Y, W, H = outer
    return x >= X - tol and y >= Y - tol and x + w <= X + W + tol and y + h <= Y + H + tol


def expected_map(model, fs=()):
    """SPARQL: contexts, subdomains and {rel: (most specific type, source, target)} of the context map of model."""
    bcs = ids(f"SELECT ?x WHERE {{ ?x a ddd:BoundedContext ; arch:inModel <{model}> }}", fs)
    subs = ids(f"SELECT ?x WHERE {{ ?x a ddd:Subdomain ; arch:inModel <{model}> }}", fs)
    rels = {short(x): (t, short(s), short(o)) for x, t, s, o in rows(
        f"""SELECT ?x ?t ?s ?o WHERE {{ {MAP_TYPES} ?x a ?t ; arch:inModel <{model}> ; arch:source ?s ; arch:target ?o
            FILTER NOT EXISTS {{ ?x a ?t2 . ?t2 rdfs:subClassOf+ ?t }} }}""", fs)}
    return {short(x) for x in bcs}, {short(x) for x in subs}, rels


def orphans(fs=(), model=L):
    """SPARQL: aggregates no bounded context owns, and entities / value objects in no aggregate a context owns."""
    own = "?o a/rdfs:subClassOf* ddd:Ownership ; arch:source ?b ; arch:target ?a . ?b a/rdfs:subClassOf* ddd:BoundedContext ."
    aggs = ids(f"""SELECT ?x WHERE {{ ?x arch:inModel <{model}> ; a/rdfs:subClassOf* ddd:Aggregate
        FILTER NOT EXISTS {{ {own.replace('?a', '?x')} }} }}""", fs)
    leaves = ids(f"""SELECT ?x WHERE {{ ?x arch:inModel <{model}> ; a ?t . VALUES ?t {{ ddd:Entity ddd:ValueObject }}
        FILTER NOT EXISTS {{ ?c a/rdfs:subClassOf* ddd:Containment ; arch:source ?a ; arch:target ?x . {own} }} }}""", fs)
    return {short(x) for x in aggs | leaves}


def map_claims(name, boxes, edges, labels, want):
    bcs, subs, rels = want
    got_bc = {b["iri"] for b in boxes if b["type"] == "ddd:BoundedContext"}
    got_sub = {b["iri"] for b in boxes if b["type"] == "ddd:Subdomain"}
    claim(f"{name}: bounded contexts and subdomains drawn = SPARQL", got_bc == bcs and got_sub == subs,
          f"svg={sorted(got_bc)}/{sorted(got_sub)} sparql={sorted(bcs)}/{sorted(subs)}")
    got = {e["iri"]: (e["type"], e["source"], e["target"]) for e in edges}
    claim(f"{name}: every line is a context-map relationship with the model's most specific type, source and target",
          got == rels, f"svg={sorted(got.items())} sparql={sorted(rels.items())}")
    by = {b["iri"]: b["box"] for b in boxes}
    geo = [e["iri"] for e in edges if not (on_border(e["pts"][0], by[e["source"]]) and on_border(e["pts"][-1], by[e["target"]]))]
    claim(f"{name}: every line starts on its source's box and ends on its target's box (geometry)", not geo,
          f"off-box={geo} checked={len(edges)}")
    ends = {(l["for"], l["end"]): l["box"] for l in labels if l["end"] in ("tail", "head")}
    bad = [e["iri"] for e in edges if (e["iri"], "tail") in ends and not (
        dist(ends[(e["iri"], "tail")], by[e["source"]]) < dist(ends[(e["iri"], "tail")], by[e["target"]])
        and dist(ends[(e["iri"], "head")], by[e["target"]]) < dist(ends[(e["iri"], "head")], by[e["source"]]))]
    claim(f"{name}: each U label sits nearer the upstream (source) box, each D label nearer the downstream box",
          not bad, f"misplaced={bad} labelled={sum(1 for k in ends if k[1] == 'tail')}")
    bc_bottom = max(b["box"][1] + b["box"][3] for b in boxes if b["type"] == "ddd:BoundedContext")
    sub_top = min((b["box"][1] for b in boxes if b["type"] == "ddd:Subdomain"), default=None)
    claim(f"{name}: bounded contexts form the upper band, subdomains the lower (every context ends above every subdomain)",
          sub_top is not None and bc_bottom < sub_top, f"lowest context bottom={bc_bottom} highest subdomain top={sub_top}")


def main():
    tmp = tempfile.mkdtemp(prefix="aisep-diagram-ddd-")
    try:
        # ------------------------------------------------ real models
        for slug, n_bc, n_impl in (("workbench", 2, 2), ("procurement", 1, 1)):
            model = f"https://aisep.example/model/{slug}/"
            out = os.path.join(tmp, f"{slug}.svg")
            rc, log = run("diagram", "--viewpoint", "ContextMap", "--model", slug, "-o", out)
            claim(f"{slug} ContextMap: exit 0, warnings=0", rc == 0 and "warnings=0" in log
                  and "[Warning]" not in log, log.strip().splitlines()[-1][:160])
            svg, tree, boxes, edges, labels, _ = diagram(out, "--viewpoint", "ContextMap", "--model", slug)
            want = expected_map(model)
            map_claims(f"{slug} ContextMap", boxes, edges, labels, want)
            legend_claims(f"{slug} ContextMap", tree, boxes)
            claim(f"{slug} ContextMap: {n_bc} contexts, {n_impl} implementation lines, no context-context line (model facts)",
                  len(want[0]) == n_bc and sum(1 for e in edges if e["type"] == "ddd:SubdomainImplementation") == n_impl
                  and len(edges) == n_impl, f"contexts={len(want[0])} lines={len(edges)}")
            claim(f"{slug} ContextMap: subdomain shows its type (核心域)", "核心域" in svg, "核心域")
        svg, tree, boxes, edges, _, warnings = diagram(os.path.join(tmp, "q.svg"), "--viewpoint", "AggregateDiagram",
                                                       "--of", "https://aisep.example/model/procurement/quotationBC")
        lg = legend_claims("procurement AggregateDiagram", tree, boxes)
        claim("procurement AggregateDiagram: the context is drawn and explained as a dashed boundary, not a solid box",
              lg.get("k:boundary", {}).get("shape") == ("bnd", "10") and "k:bc" not in lg, f"legend={sorted(lg)}")
        aggs = [b for b in boxes if b["kind"] == "aggregate"]
        leaves = [b for b in boxes if b["kind"] == "element"]
        want_aggs = ids("SELECT ?a WHERE { ?r a ddd:Ownership ; arch:source <https://aisep.example/model/procurement/quotationBC> ; arch:target ?a }")
        claim("procurement AggregateDiagram: aggregates = SPARQL ddd:Ownership targets, each inside the context box",
              {b["iri"] for b in aggs} == want_aggs and all(inside(b["box"], boxes[0]["box"]) for b in aggs)
              and boxes[0]["kind"] == "boundary", f"svg={[b['iri'] for b in aggs]} sparql={sorted(want_aggs)}")
        claim("procurement AggregateDiagram: one leaf, the root entity, marked «聚合根», inside its aggregate, warnings=0",
              len(leaves) == 1 and "«聚合根»" in leaves[0]["text"] and inside(leaves[0]["box"], aggs[0]["box"])
              and not warnings, f"leaves={[(b['iri'], b['text']) for b in leaves]} warnings={warnings}")
        claim("procurement AggregateDiagram: containment is nesting, no line drawn", not edges, f"lines={len(edges)}")
        out = os.path.join(tmp, "none.svg")
        rc, log = run("diagram", "--viewpoint", "AggregateDiagram", "--of",
                      "https://aisep.example/model/workbench/workbenchGovernanceBC", "-o", out)
        claim("AggregateDiagram of a context owning no aggregate exits 1 with a Violation and writes nothing",
              rc == 1 and "[Violation]" in log and not os.path.exists(out), log.strip()[-140:])
        rc, log = run("diagram", "--viewpoint", "AggregateDiagram", "--of",
                      "https://aisep.example/model/procurement/procurementSubdomain", "-o", out)
        claim("AggregateDiagram --of a subdomain (not a bounded context) exits 1 with a Violation",
              rc == 1 and "[Violation]" in log and not os.path.exists(out), log.strip()[-140:])
        rc, log = run("diagram", "--ddd", "list", "--model", "procurement")
        claim("--ddd list names the renderable DDD views of procurement", rc == 0 and "VIEW --viewpoint ContextMap --model procurement" in log
              and "VIEW --viewpoint AggregateDiagram --of https://aisep.example/model/procurement/quotationBC" in log
              and "views=2" in log, log.strip()[-200:])
        for extra in (("--viewpoint", "ContextMap"), ("--of", "procurement:quotationBC"), ("--view", "x")):
            rc, log = run("diagram", "--ddd", "list", "--model", "procurement", *extra)
            claim(f"--ddd list with {extra[0]} is a usage error naming it (exit 2), nothing listed",
                  rc == 2 and f"[Violation] diagram: --ddd list" in log and extra[0] in log and "VIEW" not in log,
                  log.strip()[-160:])

        # ------------------------------------------------ legal sample: every context-map relationship
        src = os.path.join(tmp, "legal.ttl")
        txt = open(os.path.join(ROOT, "modules", "ddd", "tests", "valid", "context-map-legal.ttl"), encoding="utf-8").read()
        txt = txt.replace("@prefix :      <https://aisep.example/model/ddd-legal/> .",
                          "@prefix :      <https://aisep.example/model/ddd-legal/> .\n@prefix m: <https://aisep.example/model/> .")
        txt = txt.replace(":model a arch:Model", "m:ddd-legal\\/ a arch:Model").replace("arch:inModel :model", "arch:inModel m:ddd-legal\\/")
        assert "m:ddd-legal\\/ a arch:Model" in txt
        open(src, "w", encoding="utf-8").write(txt)
        fs = [src]
        rc, log = run("gate", *fs)
        claim("legal sample (model IRI rewritten) passes gate", rc == 0, log.strip().splitlines()[-1])
        svg, tree, boxes, edges, labels, warnings = diagram(os.path.join(tmp, "legal.svg"), "--viewpoint", "ContextMap",
                                                            "--model", "ddd-legal", *fs)
        want = expected_map(L, fs)
        map_claims("legal ContextMap", boxes, edges, labels, want)
        lg = legend_claims("legal ContextMap", tree, boxes)
        claim("legal ContextMap (has Customer-Supplier): the U/D legend entry explains S and C",
              "S 供应方" in lg.get("ud:", {}).get("text", "") and "C 客户" in lg["ud:"]["text"], lg.get("ud:"))
        claim("legal ContextMap: 3 contexts, 4 context-context lines, 1 implementation line (SPARQL)",
              len(want[0]) == 3 and sum(1 for t, _, _ in want[2].values() if t != "ddd:SubdomainImplementation") == 4
              and len(edges) == 5, f"rels={sorted(want[2])}")
        lab = {(l["for"], l["end"]): l["text"] for l in labels}
        up = ", ".join(sorted(v for (v,) in rows("SELECT ?n WHERE { l:rel-ud ddd:upstreamRole ?r . ?r skos:notation ?n }", fs)))
        down = ", ".join(sorted(v for (v,) in rows("SELECT ?n WHERE { l:rel-ud ddd:downstreamRole ?r . ?r skos:notation ?n }", fs)))
        claim("legal ContextMap: rel-ud ends are 'U | <upstream notations>' and 'D | <downstream notations>' (SPARQL)",
              lab.get(("ddd-legal:rel-ud", "tail")) == f"U | {up}" and lab.get(("ddd-legal:rel-ud", "head")) == f"D | {down}" and up == "OHS, PL",
              f"tail={lab.get(('ddd-legal:rel-ud', 'tail'))!r} head={lab.get(('ddd-legal:rel-ud', 'head'))!r} sparql={up!r}/{down!r}")
        exp = sorted(v for (v,) in rows("SELECT ?n WHERE { l:rel-cs ddd:exposedAggregate ?a . ?a skos:prefLabel ?n }", fs))
        claim("legal ContextMap: rel-cs ends are 'U,S' / 'D,C', middle names 客户-供应方 and the exposed aggregate",
              lab.get(("ddd-legal:rel-cs", "tail")) == "U,S" and lab.get(("ddd-legal:rel-cs", "head")) == "D,C"
              and lab.get(("ddd-legal:rel-cs", "center")) == "客户-供应方 暴露：" + "、".join(exp), f"labels={[(k, v) for k, v in lab.items() if k[0] == 'ddd-legal:rel-cs']}")
        claim("legal ContextMap: Partnership and Shared Kernel have no U/D labels, only their type in the middle",
              all((r, e) not in lab for r in ("ddd-legal:rel-partnership", "ddd-legal:rel-kernel") for e in ("tail", "head"))
              and lab.get(("ddd-legal:rel-partnership", "center")) == "合作关系" and lab.get(("ddd-legal:rel-kernel", "center")) == "共享内核",
              f"labels={[(k, v) for k, v in lab.items() if k[0] in ('ddd-legal:rel-partnership', 'ddd-legal:rel-kernel')]}")
        claim("legal ContextMap: lines carry no arrow (Context Mapper)", "marker-end" not in svg and "<marker" not in svg, "no marker")
        unsupported = ids(f"""SELECT ?x WHERE {{ ?x arch:inModel <{L}> ; a ?t FILTER(STRSTARTS(STR(?t), "{DDD}"))
            FILTER(?t NOT IN (ddd:BoundedContext, ddd:Subdomain, ddd:Aggregate, ddd:Entity, ddd:ValueObject, ddd:Ownership,
                   ddd:Containment, ddd:RootContainment, ddd:UpstreamDownstream, ddd:CustomerSupplier, ddd:Partnership,
                   ddd:SharedKernel, ddd:SubdomainImplementation)) }}""", fs)
        unsupported |= orphans(fs)
        warned = {re.match(r"\[Warning\] diagram (\S+):", w).group(1) for w in warnings}
        claim("legal ContextMap: every DDD member no DDD view draws (unsupported type, or an aggregate / entity / value "
              "object no owned aggregate reaches) is a warning naming it, nothing else warned",
              {short(w) for w in warned} == unsupported and len(warnings) == len(unsupported) and all("not drawn by any DDD view" in w for w in warnings),
              f"warned={sorted(map(short, warned))} sparql={sorted(map(short, unsupported))}")
        svg2, *_ = diagram(os.path.join(tmp, "legal2.svg"), "--viewpoint", "ContextMap", "--model", "ddd-legal", *fs)
        claim("legal ContextMap: generating twice gives identical bytes", svg == svg2, f"len={len(svg)}")

        svg, tree, boxes, edges, _, warnings = diagram(os.path.join(tmp, "o.svg"), "--viewpoint", "AggregateDiagram",
                                                       "--of", L + "orderingBC", *fs)
        legend_claims("legal AggregateDiagram orderingBC", tree, boxes)
        got = {(b["kind"], b["iri"], b["parent"]) for b in boxes}
        owned = ids("SELECT ?a WHERE { l:orderingBC ddd:owns ?a }", fs)
        members = set(rows("SELECT ?a ?x WHERE { l:orderingBC ddd:owns ?a . ?a ddd:contains|ddd:hasRoot ?x }", fs))
        want_got = {("boundary", "ddd-legal:orderingBC", None)} | {("aggregate", short(a), "ddd-legal:orderingBC") for a in owned} | \
                   {("element", short(x), short(a)) for a, x in members}
        claim("legal AggregateDiagram orderingBC: boxes = context ⊃ owned aggregates (ddd:owns) ⊃ contained members (ddd:contains)",
              got == want_got and "ddd-legal:stockAgg" not in {b["iri"] for b in boxes}, f"svg={sorted(got)} sparql={sorted(want_got)}")
        root = ids("SELECT ?x WHERE { ?a ddd:hasRoot ?x . l:orderingBC ddd:owns ?a }", fs)
        marks = {b["iri"]: ("«聚合根»" in b["text"], "«值对象»" in b["text"]) for b in boxes if b["kind"] == "element"}
        claim("legal AggregateDiagram orderingBC: the ddd:hasRoot member is marked «聚合根», the value object «值对象», others not root",
              {i for i, (r, _) in marks.items() if r} == {short(x) for x in root} and marks.get("ddd-legal:address") == (False, True),
              f"marks={marks} root={sorted(root)}")
        claim("legal AggregateDiagram: every box lies inside its parent box", all(
            inside(b["box"], next(x["box"] for x in boxes if x["iri"] == b["parent"])) for b in boxes if b["parent"]),
              f"boxes={len(boxes)}")
        _, _, boxes, *_ = diagram(os.path.join(tmp, "i.svg"), "--viewpoint", "AggregateDiagram", "--of", L + "inventoryBC", *fs)
        claim("legal AggregateDiagram inventoryBC: only stockAgg and its root", {b["iri"] for b in boxes} ==
              {"ddd-legal:inventoryBC", "ddd-legal:stockAgg", "ddd-legal:stockItem"}, f"svg={sorted(b['iri'] for b in boxes)}")

        # ------------------------------------------------ escaping
        # one hostile text per site the model's own words reach: context label, contextType label, role notation (end
        # label and legend abbreviation), exposed aggregate (middle label), aggregate label, entity label
        def evil(site):
            return f'<script>alert(1)</script> A<&"B {site}'

        def lit(site):
            return '"' + evil(site).replace('"', '\\"') + '"'
        etxt = txt
        for old, new in (('"订单上下文"@zh', lit("bc") + "@zh"), ('"订单聚合"@zh', lit("agg") + "@zh"),
                         ('"订单"@zh', lit("ent") + "@zh"), ('"库存聚合"@zh', lit("exp") + "@zh"),
                         ("ddd:contextType ddd:Application .",
                          f"ddd:contextType :evilType .\n:evilType skos:prefLabel {lit('ctype')}@zh ."),
                         ("ddd:upstreamRole ddd:OpenHost , ddd:PublishedLanguage ;",
                          f"ddd:upstreamRole ddd:OpenHost , ddd:PublishedLanguage , :evilRole ;\n    ")):
            assert etxt.count(old) == 1, old
            etxt = etxt.replace(old, new)
        etxt += f"\n:evilRole skos:inScheme ddd:UpstreamRoleScheme ; skos:notation {lit('role')} .\n"
        e_src = os.path.join(tmp, "evil.ttl")
        open(e_src, "w", encoding="utf-8").write(etxt)

        def has(text, site):
            return evil(site).replace(" ", "") in text.replace(" ", "")
        for vp, arg in (("ContextMap", ("--model", "ddd-legal")), ("AggregateDiagram", ("--of", L + "orderingBC"))):
            svg, tree, boxes, edges, labels, _ = diagram(os.path.join(tmp, f"evil-{vp}.svg"), "--viewpoint", vp, *arg, e_src)
            box = {b["iri"]: b["text"] for b in boxes}
            lab = {(l["for"], l["end"]): l["text"] for l in labels}
            lg = " ".join(v["text"] for v in legend(tree).values())
            if vp == "ContextMap":
                sites = {"bc": box.get("ddd-legal:orderingBC", ""), "ctype": box.get("ddd-legal:orderingBC", ""),
                         "role": lab.get(("ddd-legal:rel-ud", "tail"), ""), "exp": lab.get(("ddd-legal:rel-cs", "center"), "")}
                sites["role (legend)"] = lg
            else:
                sites = {"bc": box.get("ddd-legal:orderingBC", ""), "agg": box.get("ddd-legal:orderAgg", ""),
                         "ent": box.get("ddd-legal:order", "")}
            missing = [k for k, v in sites.items() if not has(v, k.split()[0])]
            claim(f"escaping {vp}: hostile text (<script>, &, \") at {sorted(sites)} stays text: XML parses, no script "
                  "element, each site shows its text intact",
                  not missing and not any(t.tag.endswith("script") for t in tree.iter()) and "<script" not in svg
                  and "&lt;script&gt;" in svg and "&amp;" in svg and "&quot;" in svg, f"missing={missing}")

        # ------------------------------------------------ warnings: drawn degraded or not drawn, named
        def variant(name, old, new):
            assert old is None or txt.count(old) == 1, old
            p = os.path.join(tmp, name + ".ttl")
            open(p, "w", encoding="utf-8").write((txt.replace(old, new) if old else txt + new))
            return [p]
        _, _, _, _, _, w0 = diagram(os.path.join(tmp, "w0.svg"), "--viewpoint", "ContextMap", "--model", "ddd-legal", *fs)
        w0 = set(w0)
        cases = [
            ("w2", ":rel-partnership a ddd:Partnership ;", ":rel-partnership a ddd:Partnership ; ddd:upstreamRole ddd:OpenHost ;",
             "ContextMap", "rel-partnership: symmetric relationship has roles, roles not drawn"),
            # OpenHost has a skos:notation (OHS) but is an upstream role: only the scheme check keeps it off the D end
            ("w3", "ddd:downstreamRole ddd:AntiCorruptionLayer .", "ddd:downstreamRole ddd:AntiCorruptionLayer , ddd:OpenHost .",
             "ContextMap", "rel-ud: role https://aisep.example/ont/ddd#OpenHost is not in ddd:DownstreamRoleScheme, not drawn"),
            # a literal role value shaped to break out of a SPARQL IRI: a literal, so warned and never queried
            ("w7", "ddd:downstreamRole ddd:AntiCorruptionLayer .",
             'ddd:downstreamRole ddd:AntiCorruptionLayer , "' + INJECT + '" .',
             "ContextMap", f'rel-ud: role "{INJECT}" is not in ddd:DownstreamRoleScheme, not drawn'),
            ("w1", None, "\n:rel-bad a ddd:UpstreamDownstream ; arch:inModel m:ddd-legal\\/ ; arch:source :pricingBC ; arch:target :orderingSub .\n",
             "ContextMap", "rel-bad: an end is not in this view, not drawn"),
            ("w6", "ddd:exposedAggregate :stockAgg .", "ddd:exposedAggregate :stockAgg , :stockItem .",
             "ContextMap", "rel-cs: exposed aggregate https://aisep.example/model/ddd-legal/stockItem is not an Aggregate, not drawn"),
            ("w4", ":rel-root-order a ddd:RootContainment ;", ":rel-root-order a ddd:Containment ;",
             "AggregateDiagram", "orderAgg: no root entity, drawn without root mark"),
            ("w5", None, "\n:rel-own-stock2 a ddd:Ownership ; arch:inModel m:ddd-legal\\/ ; arch:source :orderingBC ; arch:target :stockAgg .\n",
             "AggregateDiagram", "stockAgg: also owned by https://aisep.example/model/ddd-legal/inventoryBC"),
        ]
        for name, old, new, vp, text in cases:
            vf = variant(name, old, new)
            arg = ("--model", "ddd-legal") if vp == "ContextMap" else ("--of", L + "orderingBC")
            svg, _, boxes, edges, labels, ws = diagram(os.path.join(tmp, name + ".svg"), "--viewpoint", vp, *arg, *vf)
            new_ws = [w for w in ws if w not in w0] if vp == "ContextMap" else ws
            ok = len(new_ws) == 1 and new_ws[0] == f"[Warning] diagram {L}{text}"
            if name == "w2":
                ok = ok and not any(l["for"] == "ddd-legal:rel-partnership" and l["end"] != "center" for l in labels)
            if name in ("w3", "w7"):
                ok = ok and {(l["for"], l["end"]): l["text"] for l in labels}.get(("ddd-legal:rel-ud", "head")) == "D | ACL"
            if name == "w1":
                ok = ok and "ddd-legal:rel-bad" not in {e["iri"] for e in edges}
            if name == "w4":
                ok = ok and not any("«聚合根»" in b["text"] for b in boxes if b["iri"] == "ddd-legal:order")
                lg = legend_claims("w4 AggregateDiagram (non-root entity and value object)", ElementTree.fromstring(svg), boxes)
                claim("entity and value object have different notations, in the diagram and in the legend",
                      lg.get("k:ent", {}).get("shape") not in (None, lg.get("k:vo", {}).get("shape"))
                      and {b["shape"] for b in boxes if b["iri"] == "ddd-legal:order"} != {b["shape"] for b in boxes if b["iri"] == "ddd-legal:address"},
                      f"ent={lg.get('k:ent')} vo={lg.get('k:vo')}")
            if name == "w5":
                ok = ok and any(b["iri"] == "ddd-legal:stockAgg" and b["parent"] == "ddd-legal:orderingBC" for b in boxes)
            claim(f"warning {name}: exactly one new warning, naming the IRI; drawn as stated", ok, f"new={new_ws}")
        # orphans: an aggregate no context owns; an entity and a value object in no owned aggregate; each named once
        vf = variant("orphans", None, "\n:lonelyAgg a ddd:Aggregate ; arch:inModel m:ddd-legal\\/ ; skos:prefLabel \"孤儿聚合\"@zh .\n"
                     ":lonelyEnt a ddd:Entity ; arch:inModel m:ddd-legal\\/ ; skos:prefLabel \"孤儿实体\"@zh .\n"
                     ":lonelyVo a ddd:ValueObject ; arch:inModel m:ddd-legal\\/ ; skos:prefLabel \"孤儿值对象\"@zh .\n"
                     ":inLonely a ddd:Entity ; arch:inModel m:ddd-legal\\/ ; skos:prefLabel \"孤儿聚合的根\"@zh .\n"
                     ":rel-root-lonely a ddd:RootContainment ; arch:inModel m:ddd-legal\\/ ; arch:source :lonelyAgg ; arch:target :inLonely .\n")
        *_, ws = diagram(os.path.join(tmp, "orphans.svg"), "--viewpoint", "ContextMap", "--model", "ddd-legal", *vf)
        new_ws = sorted(w for w in ws if w not in w0)
        want_o = {"ddd-legal:" + n for n in ("lonelyAgg", "lonelyEnt", "lonelyVo", "inLonely")}
        claim("orphans: an unowned aggregate, and every entity / value object no owned aggregate reaches, is one "
              "warning each naming it (SPARQL agrees)",
              {short(re.match(r"\[Warning\] diagram (\S+):", w).group(1)) for w in new_ws} == want_o
              and len(new_ws) == 4 and want_o <= orphans(vf), f"new={new_ws}")
        # no Customer-Supplier: the U/D legend says nothing about S and C
        vf = variant("nocs", ":rel-cs a ddd:CustomerSupplier ;", ":rel-cs a ddd:UpstreamDownstream ;")
        _, tree, *_ = diagram(os.path.join(tmp, "nocs.svg"), "--viewpoint", "ContextMap", "--model", "ddd-legal", *vf)
        ud = legend(tree).get("ud:", {}).get("text", "")
        claim("without Customer-Supplier the U/D legend entry does not mention S / C", ud and "供应方" not in ud
              and "客户" not in ud and "S" not in ud.replace("U/D", ""), f"ud={ud!r}")
        # the same aggregate both contains (ddd:Containment, IRI sorting first) and has as root (ddd:RootContainment)
        # the same entity: not a conflict, root mark kept, no warning
        vf = variant("dup", None, "\n:rel-dup a ddd:Containment ; arch:inModel m:ddd-legal\\/ ; arch:source :orderAgg ; arch:target :order .\n")
        _, _, boxes, _, _, ws = diagram(os.path.join(tmp, "dup.svg"), "--viewpoint", "AggregateDiagram",
                                        "--of", L + "orderingBC", *vf)
        order = [b for b in boxes if b["iri"] == "ddd-legal:order"]
        claim("dup Containment + RootContainment of one member in one aggregate: drawn once, marked «聚合根», warnings=0",
              len(order) == 1 and "«聚合根»" in order[0]["text"] and order[0]["parent"] == "ddd-legal:orderAgg" and not ws,
              f"order={[(b['parent'], b['text']) for b in order]} warnings={ws}")
        vf = variant("nobc", None, "")
        open(vf[0], "w", encoding="utf-8").write("\n".join(l for l in txt.splitlines() if "a ddd:BoundedContext" not in l))
        out = os.path.join(tmp, "nobc.svg")
        rc, log = run("diagram", "--viewpoint", "ContextMap", "--model", "ddd-legal", "-o", out, *vf)
        claim("ContextMap of a model without bounded contexts exits 1 with a Violation and writes nothing",
              rc == 1 and "[Violation] diagram: no ddd:BoundedContext" in log and not os.path.exists(out), log.strip()[-140:])
        rc, log = run("diagram", "--viewpoint", "AggregateDiagram", "--model", "ddd-legal", "-o", out, *fs)
        claim("AggregateDiagram without --of prints usage (exit 2)", rc == 2, f"rc={rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    p = subprocess.run(["git", "status", "--porcelain", "--", "models", "modules", "vendor"], cwd=ROOT,
                       capture_output=True, text=True)
    claim("models/, modules/ and vendor/ are untouched by the run", p.returncode == 0 and not p.stdout.strip(),
          p.stdout.strip()[:200] or "clean")
    ok = all(results)
    print(f"SUMMARY diagram-ddd-acceptance claims={len(results)} confirmed={sum(results)} result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
