"""Acceptance test for UML class diagrams of `aisep.py diagram --uml` (aisep/diagram_uml.py).

Inputs: models/procurement (P, the only real UML data: 1 class); modules/uml/tests/valid/order-class-diagram.ttl (C0: 3
classes, 1 interface, association, generalization, interface realization); and C1 = C0 plus, in a temp copy only, a package
holding Quotation and Supplier (arch:HasPart), two attributes and an abstract operation of Quotation, a composition, a
usage, an unsupported uml:InformationFlow and an association end property written on the association. Every expected set
comes from an independent SPARQL query run through `aisep.py query`, never from aisep/diagram_uml.py.
Acceptance list: coordination/design-uml-view-20261127.md §4. Each claim prints CONFIRMED / REFUTED with evidence;
exit 0 only if every claim is CONFIRMED.

Run:  <venv python> tests/acceptance/test_diagram_uml.py      (also run by `aisep.py test`)
"""
import glob, os, re, shutil, subprocess, sys, tempfile
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
T = "https://aisep.example/model/uml-test/"
PFX = f"PREFIX uml: <https://meta.linked.archi/uml/onto#> PREFIX t: <{T}> "
SVG = "{http://www.w3.org/2000/svg}"
results = []

C1_EXTRA = """
:pkgOrder a uml:Package ; arch:inModel :model ; skos:prefLabel "订单包"@zh .
:rel-pkg-has-quotation a arch:HasPart ; arch:inModel :model ; arch:source :pkgOrder ; arch:target :Quotation .
:rel-pkg-has-supplier a arch:HasPart ; arch:inModel :model ; arch:source :pkgOrder ; arch:target :Supplier .
:QuotationLine a uml:Class ; arch:inModel :model ; skos:prefLabel "报价行"@zh .
:quotationNo a uml:Property ; arch:inModel :model ; skos:prefLabel "编号"@zh ; uml:visibility uml:Public ;
    uml:lower 1 ; uml:upper 1 .
:quotationTags a uml:Property ; arch:inModel :model ; skos:prefLabel "标签"@zh ; uml:visibility uml:Private ;
    uml:lower 0 ; uml:upper -1 .
:priceOp a uml:Operation ; arch:inModel :model ; skos:prefLabel "计价"@zh ; uml:visibility uml:Public ; uml:isAbstract true .
:rel-q-has-no a arch:HasPart ; arch:inModel :model ; arch:source :Quotation ; arch:target :quotationNo .
:rel-q-has-tags a arch:HasPart ; arch:inModel :model ; arch:source :Quotation ; arch:target :quotationTags .
:rel-q-has-price a arch:HasPart ; arch:inModel :model ; arch:source :Quotation ; arch:target :priceOp .
:comp-quotation-line a uml:Composition ; arch:inModel :model ; arch:source :Quotation ; arch:target :QuotationLine .
:use-supplier-priceable a uml:Usage ; arch:inModel :model ; arch:source :Supplier ; arch:target :Priceable .
:flow-document-supplier a uml:InformationFlow ; arch:inModel :model ; arch:source :Document ; arch:target :Supplier .
:assoc-quotation-supplier uml:lower 0 .
"""
VIEW = """
:view-umlProbe a arch:Diagram ; arch:inModel :model ; skos:prefLabel "UML 声明式探针"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/uml/viewpoints#ClassDiagram> .
:Quotation arch:inView :view-umlProbe . :Document arch:inView :view-umlProbe . :Priceable arch:inView :view-umlProbe .
"""
EVIL = '<script>alert(1)</script> & "q" \'x\''


def run(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def rows(q, fs):
    rc, out = run("query", PFX + q, *fs)
    assert rc == 0, out
    return [tuple(l.split("\t")) for l in out.splitlines()[1:] if l and not l.startswith("--")]


def short(iri):
    """t:name for the test model, whether written as a full IRI (SVG) or as `aisep.py query` prints it (uml-test:name)."""
    for pre in (T, "uml-test:"):
        if iri and iri.startswith(pre):
            return "t:" + iri[len(pre):]
    return iri


def claim(text, ok, evidence):
    results.append(ok)
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {text}\n      evidence: {evidence}")


def diagram(out, *args):
    rc, log = run("diagram", *args, "-o", out)
    assert rc == 0, log
    svg = open(out, encoding="utf-8").read()
    root = ElementTree.fromstring(svg)  # well-formed XML (raises otherwise)
    boxes, edges, feats = {}, [], {}
    for g in root.iter():
        k = g.get("data-kind")
        if k in ("element", "package"):
            name = g.find(f"{SVG}text[@class]")
            boxes[short(g.get("data-iri"))] = {
                "kind": k, "type": g.get("data-type"), "parent": short(g.get("data-parent")) or None,
                "box": tuple(float(v) for v in g.get("data-box").split()),
                "texts": [(t.get("class"), t.text) for t in g.iter(f"{SVG}text")]}
            if k == "element":
                feats[short(g.get("data-iri"))] = [(short(t.get("data-iri")), t.get("class"), t.text)
                                                    for t in g.iter(f"{SVG}text") if t.get("data-kind") == "feature"]
        elif k == "relationship":
            pts = [tuple(float(v) for v in p.split(",")) for p in g.get("d")[1:].split(" L")]
            edges.append({"iri": short(g.get("data-iri")), "type": g.get("data-type"), "source": short(g.get("data-source")),
                          "target": short(g.get("data-target")), "pts": pts, "class": g.get("class"),
                          "start": g.get("marker-start"), "end": g.get("marker-end")})
    return svg, boxes, edges, feats, log


def on_border(p, box, tol=1.5):
    x, y, w, h = box
    px, py = p
    vertical = (abs(px - x) <= tol or abs(px - x - w) <= tol) and y - tol <= py <= y + h + tol
    horizontal = (abs(py - y) <= tol or abs(py - y - h) <= tol) and x - tol <= px <= x + w + tol
    return vertical or horizontal


def inside(box, outer, tol=0.5):
    x, y, w, h = box
    X, Y, W, H = outer
    return x >= X - tol and y >= Y - tol and x + w <= X + W + tol and y + h <= Y + H + tol


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def geometry_claims(name, boxes, edges):
    sib = {}
    for i, b in boxes.items():
        sib.setdefault(b["parent"], []).append(i)
    bad = [(a, c) for g in sib.values() for k, a in enumerate(g) for c in g[k + 1:] if overlap(boxes[a]["box"], boxes[c]["box"])]
    claim(f"{name}: no two sibling boxes overlap", not bad, f"overlapping={bad} boxes={len(boxes)}")
    out = [i for i, b in boxes.items() if b["parent"] and not inside(b["box"], boxes[b["parent"]]["box"])]
    claim(f"{name}: every box lies inside its package frame", not out, f"outside={out}")
    off = [e["iri"] for e in edges if not (on_border(e["pts"][0], boxes[e["source"]]["box"])
                                         and on_border(e["pts"][-1], boxes[e["target"]]["box"]))]
    claim(f"{name}: every line starts on its model source's box and ends on its model target's box", not off,
          f"off-box={off} checked={len(edges)}")
    diag = [e["iri"] for e in edges if any(a[0] != b[0] and a[1] != b[1] for a, b in zip(e["pts"], e["pts"][1:]))]
    claim(f"{name}: every line is orthogonal", not diag, f"diagonal={diag}")


def ends_claim(name, edges, fs):
    model = {(short(r), short(s), short(o)) for r, s, o in rows(
        f"SELECT ?r ?s ?o WHERE {{ ?r arch:source ?s ; arch:target ?o ; a ?ty FILTER(STRSTARTS(STR(?ty), STR(uml:))) }}", fs)}
    got = {(e["iri"], e["source"], e["target"]) for e in edges}
    claim(f"{name}: each line's data-source / data-target is the model's arch:source / arch:target (SPARQL)",
          got <= model and bool(got), f"not_in_model={sorted(got - model)}")


NODES_Q = ("SELECT ?x WHERE {{ ?x arch:inModel <{m}> ; a ?t VALUES ?t {{ uml:Class uml:Interface uml:DataType "
           "uml:Enumeration uml:PrimitiveType }} FILTER NOT EXISTS {{ ?x arch:source ?s }} }}")


def main():
    tmp = tempfile.mkdtemp(prefix="aisep-diagram-uml-")
    try:
        # 1. real model: procurement
        pfs = sorted(glob.glob(os.path.join(ROOT, "models", "procurement", "**", "*.ttl"), recursive=True))
        svg, boxes, edges, _, log = diagram(os.path.join(tmp, "p.svg"), "--uml", "ClassDiagram", "--model", "procurement", *pfs)
        want = {x.replace("procurement:", "https://aisep.example/model/procurement/")
                for (x,) in rows(NODES_Q.format(m="https://aisep.example/model/procurement/"), pfs)}
        claim("procurement: drawn classifiers = SPARQL classifiers of the model (exactly 1), no line, warnings=0",
              set(boxes) == want and len(want) == 1 and not edges and "warnings=0" in log,
              f"svg={sorted(boxes)} sparql={sorted(want)} lines={len(edges)}")
        rc, log = run("diagram", "--uml", "list", *pfs)
        claim("`--uml list` lists the procurement class diagram", rc == 0 and "--uml ClassDiagram --model procurement" in log,
              log.strip().splitlines()[0] if log.strip() else log)

        # C0: the module's valid fixture, model IRI written as a plain slug in a temp copy
        txt = open(os.path.join(ROOT, "modules", "uml", "tests", "valid", "order-class-diagram.ttl"), encoding="utf-8").read()
        txt = re.sub(r"^:model ", f"<{T}> ", txt, flags=re.M).replace("arch:inModel :model", f"arch:inModel <{T}>")
        c0 = os.path.join(tmp, "c0.ttl")
        open(c0, "w", encoding="utf-8").write(txt)
        svg, boxes, edges, _, log = diagram(os.path.join(tmp, "c0.svg"), "--uml", "ClassDiagram", "--model", "uml-test", c0)
        claim("C0: 4 classifiers, 3 lines, warnings=0", len(boxes) == 4 and len(edges) == 3 and "warnings=0" in log,
              f"boxes={len(boxes)} lines={len(edges)} {log.strip().splitlines()[-1][:80]}")
        out = os.path.join(tmp, "uc.svg")
        rc, log = run("diagram", "--uml", "UseCaseDiagram", "--model", "uml-test", "-o", out, c0)
        claim("--uml UseCaseDiagram exits 1 with a Violation and writes nothing", rc == 1 and "[Violation]" in log
              and not os.path.exists(out), log.strip()[-100:])

        # C1
        c1 = os.path.join(tmp, "c1.ttl")
        open(c1, "w", encoding="utf-8").write(txt + C1_EXTRA.replace(":model", f"<{T}>"))
        fs = [c1]
        rc, log = run("gate", *fs)
        claim("C1 passes gate", rc == 0, log.strip().splitlines()[-1])
        svg, boxes, edges, feats, log = diagram(os.path.join(tmp, "c1.svg"), "--uml", "ClassDiagram", "--model", "uml-test", *fs)
        svg2, *_ = diagram(os.path.join(tmp, "c1b.svg"), "--uml", "ClassDiagram", "--model", "uml-test", *fs)
        claim("C1: generating twice gives identical bytes", svg == svg2, f"len={len(svg)}")

        # 4. members
        want = {short(x) for (x,) in rows(NODES_Q.format(m=T), fs)}
        got = {i for i, b in boxes.items() if b["kind"] == "element"}
        claim("C1: drawn classifiers = SPARQL projection; the association resource is not a node",
              got == want and "t:assoc-quotation-supplier" not in boxes, f"svg={sorted(got)} sparql={sorted(want)}")
        ends_claim("C1", edges, fs)
        want_f = {short(f) for (f,) in rows("SELECT ?f WHERE { t:Quotation arch:hasPart ?f . "
                                            "{ ?f a uml:Property } UNION { ?f a uml:Operation } }", fs)}
        fq = feats.get("t:Quotation", [])
        claim("C1: Quotation's rows are exactly its arch:hasPart features (SPARQL), 3 rows",
              {i for i, _, _ in fq} == want_f and len(fq) == 3, f"rows={fq} sparql={sorted(want_f)}")
        tags = next((t for i, _, t in fq if i == "t:quotationTags"), "")
        op = next((c for i, c, _ in fq if i == "t:priceOp"), "")
        claim("C1: the private attribute row starts with '- ' and shows [0..*]; the abstract operation row is italic",
              tags.startswith("- ") and "[0..*]" in tags and "ab" in (op or "").split(), f"tags={tags!r} op class={op!r}")
        pk = {i: b["parent"] for i, b in boxes.items() if b["kind"] == "element"}
        want_p = {(short(p), short(c)) for p, c in rows("SELECT ?p ?c WHERE { ?p a uml:Package ; arch:hasPart ?c }", fs)}
        claim("C1: package frame = uml:Package arch:hasPart targets (SPARQL)",
              {(p, c) for c, p in pk.items() if p} == want_p and boxes.get("t:pkgOrder", {}).get("kind") == "package",
              f"svg={sorted((p, c) for c, p in pk.items() if p)} sparql={sorted(want_p)}")

        # 5. notation and direction
        by = {e["iri"]: e for e in edges}
        g, doc, q = by.get("t:gen-quotation-document", {}), boxes["t:Document"]["box"], boxes["t:Quotation"]["box"]
        claim("generalization: solid, hollow triangle at the end, on Document's border; Document above Quotation",
              g.get("class") == "e" and g.get("end") == "url(#u-tri)" and not g.get("start")
              and on_border(g["pts"][-1], doc) and doc[1] + doc[3] <= q[1], f"edge={ {k: g.get(k) for k in ('class', 'end')} } "
              f"Document.y={doc[1]} Quotation.y={q[1]}")
        r = by.get("t:real-quotation-priceable", {})
        claim("interface realization: dashed, hollow triangle at the Priceable end",
              r.get("class") == "e e-d" and r.get("end") == "url(#u-tri)" and on_border(r["pts"][-1], boxes["t:Priceable"]["box"]),
              f"class={r.get('class')} end={r.get('end')}")
        c = by.get("t:comp-quotation-line", {})
        claim("composition: filled diamond at the source (whole) end, nothing at the part end",
              c.get("start") == "url(#u-dia-f)" and not c.get("end") and on_border(c["pts"][0], q),
              f"start={c.get('start')} end={c.get('end')}")
        u = by.get("t:use-supplier-priceable", {})
        claim("usage: dashed with an open arrow and a «use» label", u.get("class") == "e e-d" and u.get("end") == "url(#u-open)"
              and ">«use»<" in svg, f"class={u.get('class')} end={u.get('end')}")
        a = by.get("t:assoc-quotation-supplier", {})
        claim("association: no marker", a and not a.get("start") and not a.get("end"), f"start={a.get('start')} end={a.get('end')}")
        claim("Priceable shows «interface»; Document's name is italic and tagged {abstract}",
              ("kw", "«interface»") in boxes["t:Priceable"]["texts"] and ("cn ab", "单据") in boxes["t:Document"]["texts"]
              and ("tag", "{abstract}") in boxes["t:Document"]["texts"], f"Document texts={boxes['t:Document']['texts']}")

        # 6. geometry
        geometry_claims("C1", boxes, edges)

        # 7. warnings
        ws = [l for l in log.splitlines() if l.startswith("[Warning]")]
        claim("C1: exactly 2 warnings, one naming the InformationFlow, one the association with uml:lower; SUMMARY warnings=2",
              len(ws) == 2 and any(T + "flow-document-supplier" in w for w in ws)
              and any(T + "assoc-quotation-supplier" in w and "uml:lower" in w for w in ws) and "warnings=2" in log,
              f"warnings={ws}")

        # escaping: hostile label text is drawn as text, never as markup
        evil = os.path.join(tmp, "evil.ttl")
        open(evil, "w", encoding="utf-8").write(txt.replace('"供应商"@zh', '"' + EVIL.replace('"', '\\"') + '"@zh'))
        svg, boxes, *_ = diagram(os.path.join(tmp, "evil.svg"), "--uml", "ClassDiagram", "--model", "uml-test", evil)
        names = [t for _, t in boxes["t:Supplier"]["texts"]]
        claim("a label with <script>, &, quotes is escaped: no <script element, the text round-trips through the XML parser",
              "<script" not in svg and "&lt;script&gt;" in svg and EVIL in names
              and not any(e.tag == f"{SVG}script" for e in ElementTree.fromstring(svg).iter()), f"name={names}")

        # 8. --view dispatch: a declared umlvp:ClassDiagram is drawn by the UML renderer
        dv = os.path.join(tmp, "view.ttl")
        open(dv, "w", encoding="utf-8").write(txt + VIEW.replace(":model", f"<{T}>"))
        svg, boxes, edges, _, log = diagram(os.path.join(tmp, "dv.svg"), "--view", T + "view-umlProbe", dv)
        types = {b["type"] for b in boxes.values()}
        claim("--view umlvp:ClassDiagram: UML renderer (data-type uml:*), exactly the 3 inView members, no ArchiMate band '其他'",
              all(t.startswith("uml:") for t in types) and set(boxes) == {"t:Quotation", "t:Document", "t:Priceable"}
              and ">其他<" not in svg and ">UML 声明式探针<" in svg, f"types={sorted(types)} boxes={sorted(boxes)}")
        ends_claim("declared view", edges, [dv])
        geometry_claims("declared view", boxes, edges)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"SUMMARY diagram-uml-acceptance claims={len(results)} confirmed={sum(results)} result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
