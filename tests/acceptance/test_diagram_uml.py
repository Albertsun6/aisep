"""Acceptance test for UML class diagrams of `aisep.py diagram --uml` (aisep/diagram_uml.py).

Inputs: models/procurement (P, the only real UML data: 1 class); modules/uml/tests/valid/order-class-diagram.ttl (C0: 3
classes, 1 interface, association, generalization, interface realization); and C1 = C0 plus, in a temp copy only, a package
holding Quotation and Supplier (arch:HasPart), two attributes and an abstract operation of Quotation, a data type, an
enumeration and a primitive type, one line of every remaining supported type (composition, aggregation, usage, dependency,
abstraction, realization), a reflexive association, a self-generalization, an unsupported uml:InformationFlow and an
association end property written on the association. Every expected set comes from an independent SPARQL query run
through `aisep.py query`, never from aisep/diagram_uml.py.
Acceptance list: docs/specs/uml-class-diagram.md「可证伪验收」. Each claim prints CONFIRMED / REFUTED with evidence;
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
:Money a uml:DataType ; arch:inModel :model ; skos:prefLabel "金额"@zh .
:Status a uml:Enumeration ; arch:inModel :model ; skos:prefLabel "状态"@zh .
:Decimal a uml:PrimitiveType ; arch:inModel :model ; skos:prefLabel "小数"@zh .
:agg-supplier-document a uml:Aggregation ; arch:inModel :model ; arch:source :Supplier ; arch:target :Document .
:dep-quotation-money a uml:Dependency ; arch:inModel :model ; arch:source :Quotation ; arch:target :Money .
:abs-money-decimal a uml:Abstraction ; arch:inModel :model ; arch:source :Money ; arch:target :Decimal .
:realz-status-document a uml:Realization ; arch:inModel :model ; arch:source :Status ; arch:target :Document .
:assoc-document-self a uml:Association ; arch:inModel :model ; skos:prefLabel "前序"@zh ;
    arch:source :Document ; arch:target :Document .
:gen-supplier-self a uml:Generalization ; arch:inModel :model ; arch:source :Supplier ; arch:target :Supplier .
"""
VIEW = """
:view-umlProbe a arch:Diagram ; arch:inModel :model ; skos:prefLabel "UML 声明式探针"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/uml/viewpoints#ClassDiagram> .
:Quotation arch:inView :view-umlProbe . :Document arch:inView :view-umlProbe . :Priceable arch:inView :view-umlProbe .
:assoc-quotation-supplier arch:inView :view-umlProbe .
"""
MULT = """
:p1 a uml:Property ; arch:inModel :model ; skos:prefLabel "联系人"@zh ; uml:lower 0 ; uml:upper "*" .
:p2 a uml:Property ; arch:inModel :model ; skos:prefLabel "电话"@zh ; uml:lower 1 ; uml:upper "many" .
:p3 a uml:Property ; arch:inModel :model ; skos:prefLabel "地址"@zh ; uml:lower -2 ; uml:upper 3 .
:rel-s-p1 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p1 .
:rel-s-p2 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p2 .
:rel-s-p3 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p3 .
:p4 a uml:Property ; arch:inModel :model ; skos:prefLabel "传真"@zh ; uml:lower 3 ; uml:upper 1 .
:p5 a uml:Property ; arch:inModel :model ; skos:prefLabel "邮箱"@zh ; uml:lower 5 .
:p6 a uml:Property ; arch:inModel :model ; skos:prefLabel "网址"@zh ; uml:lower 2 ; uml:upper 2 .
:rel-s-p4 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p4 .
:rel-s-p5 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p5 .
:rel-s-p6 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p6 .
:p7 a uml:Property ; arch:inModel :model ; skos:prefLabel "传呼"@zh ; uml:lower 0 ; uml:upper -3 .
:p8 a uml:Property ; arch:inModel :model ; skos:prefLabel "编号"@zh ; uml:lower 0 ; uml:upper -1 ; uml:isStatic true .
:rel-s-p7 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p7 .
:rel-s-p8 a arch:HasPart ; arch:inModel :model ; arch:source :Supplier ; arch:target :p8 .
"""
VIEW_UC = """
:view-uc a arch:Diagram ; arch:inModel :model ; skos:prefLabel "用例图探针"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/uml/viewpoints#UseCaseDiagram> .
:Quotation arch:inView :view-uc .
"""
OTHER = """
<https://other.example/models/x/> a arch:Model ; skos:prefLabel "外部模型"@zh .
<https://other.example/models/x/K> a uml:Class ; arch:inModel <https://other.example/models/x/> ; skos:prefLabel "K"@zh .
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
        rc1, log1 = run("diagram", "--uml", "ClassDiagram", "--model", "../x", "-o", out, c0)
        rc2, log2 = run("diagram", "--uml", "ClassDiagram", "--model", "nosuch", "-o", out, c0)
        claim("--model '../x' and an unknown --model each exit 1 with a Chinese Violation, write nothing",
              rc1 == 1 and "[Violation]" in log1 and "必须是简单名称" in log1
              and rc2 == 1 and "[Violation]" in log2 and "没有元素在这张图里" in log2 and not os.path.exists(out),
              f"{log1.strip()[-80:]} | {log2.strip()[-80:]}")

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

        ag = by.get("t:agg-supplier-document", {})
        claim("aggregation: solid, hollow diamond at the source (whole) end, nothing at the part end",
              ag.get("class") == "e" and ag.get("start") == "url(#u-dia-h)" and not ag.get("end")
              and on_border(ag["pts"][0], boxes["t:Supplier"]["box"]), f"class={ag.get('class')} start={ag.get('start')} "
              f"end={ag.get('end')}")
        dp = by.get("t:dep-quotation-money", {})
        claim("dependency: dashed with an open arrow at the Money (supplier) end, no keyword label",
              dp.get("class") == "e e-d" and dp.get("end") == "url(#u-open)" and not dp.get("start")
              and on_border(dp["pts"][-1], boxes["t:Money"]["box"]) and "«dependency»" not in svg,
              f"class={dp.get('class')} start={dp.get('start')} end={dp.get('end')}")
        ab = by.get("t:abs-money-decimal", {})
        claim("abstraction: dashed with an open arrow at the Decimal end and an «abstraction» label",
              ab.get("class") == "e e-d" and ab.get("end") == "url(#u-open)" and not ab.get("start")
              and on_border(ab["pts"][-1], boxes["t:Decimal"]["box"]) and ">«abstraction»<" in svg,
              f"class={ab.get('class')} end={ab.get('end')}")
        rz, st = by.get("t:realz-status-document", {}), boxes["t:Status"]["box"]
        claim("realization: dashed, hollow triangle at the Document (specification) end, Document above Status",
              rz.get("class") == "e e-d" and rz.get("end") == "url(#u-tri)" and not rz.get("start")
              and on_border(rz["pts"][-1], doc) and doc[1] + doc[3] <= st[1],
              f"class={rz.get('class')} end={rz.get('end')} Document.y={doc[1]} Status.y={st[1]}")
        kws = {i: [t for c, t in boxes[i]["texts"] if c == "kw"] for i in ("t:Money", "t:Status", "t:Decimal", "t:Supplier")}
        claim("DataType / Enumeration / PrimitiveType show «dataType» / «enumeration» / «primitive»; a plain class has no keyword",
              kws == {"t:Money": ["«dataType»"], "t:Status": ["«enumeration»"], "t:Decimal": ["«primitive»"], "t:Supplier": []}
              and {boxes[i]["type"] for i in ("t:Money", "t:Status", "t:Decimal")} ==
              {"uml:DataType", "uml:Enumeration", "uml:PrimitiveType"}, f"keywords={kws}")
        sl = by.get("t:assoc-document-self", {})
        claim("reflexive association: drawn as a self-loop from Document back to Document, with its name",
              sl.get("source") == sl.get("target") == "t:Document" and len(sl.get("pts", [])) >= 4
              and on_border(sl["pts"][0], doc) and on_border(sl["pts"][-1], doc) and ">前序<" in svg,
              f"points={sl.get('pts')}")

        # 6. geometry
        geometry_claims("C1", boxes, edges)

        # 7. warnings
        ws = [l for l in log.splitlines() if l.startswith("[Warning]")]
        claim("C1: exactly 3 warnings: the InformationFlow (out of scope), the association with uml:lower, and the "
              "self-generalization with its own reason (not 'out of scope'); SUMMARY warnings=3",
              len(ws) == 3 and any(T + "flow-document-supplier" in w and "不在类图范围" in w for w in ws)
              and any(T + "assoc-quotation-supplier" in w and "uml:lower" in w for w in ws)
              and any(T + "gen-supplier-self" in w and "不得成环" in w and "不在类图范围" not in w for w in ws)
              and "t:gen-supplier-self" not in by and "warnings=3" in log, f"warnings={ws}")
        claim("every warning text is Chinese (no English 'not drawn')", ws and all("未画" in w and "not drawn" not in w for w in ws),
              f"warnings={ws}")

        # multiplicity: "*" is unlimited; an illegal bound is a warning and the multiplicity is left out
        mf = os.path.join(tmp, "mult.ttl")
        open(mf, "w", encoding="utf-8").write(txt + MULT.replace(":model", f"<{T}>"))
        _, _, _, mfeats, mlog = diagram(os.path.join(tmp, "mult.svg"), "--uml", "ClassDiagram", "--model", "uml-test", mf)
        rowt = {i: t for i, _, t in mfeats.get("t:Supplier", [])}
        rowc = {i: (c or "").split() for i, c, _ in mfeats.get("t:Supplier", [])}
        mws = [l for l in mlog.splitlines() if l.startswith("[Warning]")]
        claim("uml:upper \"*\" and -1 show [0..*]; [2..2] shows [2]; upper \"many\", upper -3 (only -1 means unlimited), "
              "lower -2, lower 3 > upper 1 and lower 5 > the default upper 1 each give one warning and no multiplicity",
              rowt.get("t:p1") == "联系人 [0..*]" and rowt.get("t:p2") == "电话" and rowt.get("t:p3") == "地址"
              and rowt.get("t:p4") == "传真" and rowt.get("t:p5") == "邮箱" and rowt.get("t:p6") == "网址 [2]"
              and rowt.get("t:p7") == "传呼" and rowt.get("t:p8") == "编号 [0..*]"
              and len(mws) == 5 and any(T + "p2" in w and "uml:upper 'many'" in w for w in mws)
              and any(T + "p7" in w and "uml:upper '-3'" in w for w in mws)
              and any(T + "p3" in w and "uml:lower '-2'" in w for w in mws)
              and any(T + "p4" in w and "[3..1]" in w and "上界小于下界" in w for w in mws)
              and any(T + "p5" in w and "[5..1]" in w and "上界小于下界" in w for w in mws), f"rows={rowt} warnings={mws}")
        claim("a uml:isStatic true feature row is underlined (class st, .st{text-decoration:underline}); others are not",
              "st" in rowc.get("t:p8", []) and not any("st" in c for i, c in rowc.items() if i != "t:p8")
              and ".st{text-decoration:underline}" in open(os.path.join(tmp, "mult.svg"), encoding="utf-8").read(),
              f"classes={rowc}")

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
        ws = [l for l in log.splitlines() if l.startswith("[Warning]")]
        claim("declared view: exactly 1 warning, in Chinese, for the in-view association whose Supplier end is not in view",
              len(ws) == 1 and T + "assoc-quotation-supplier" in ws[0] and "有一端不在图中" in ws[0]
              and "not drawn" not in ws[0], f"warnings={ws}")

        # --view with an unsupported umlvp: viewpoint: Violation naming umlvp:<name>, nothing written
        uc = os.path.join(tmp, "uc.ttl")
        open(uc, "w", encoding="utf-8").write(txt + VIEW_UC.replace(":model", f"<{T}>"))
        out = os.path.join(tmp, "ucv.svg")
        rc, log = run("diagram", "--view", T + "view-uc", "-o", out, uc)
        claim("--view of a umlvp:UseCaseDiagram view exits 1 with a Violation naming umlvp:UseCaseDiagram, writes nothing",
              rc == 1 and "[Violation]" in log and "umlvp:UseCaseDiagram" in log and "图种 UseCaseDiagram" not in log
              and not os.path.exists(out), log.strip()[-160:])

        # --uml list: a model whose IRI is not https://aisep.example/model/<slug>/ is not offered as --model
        of = os.path.join(tmp, "other.ttl")
        open(of, "w", encoding="utf-8").write(txt + OTHER)
        rc, log = run("diagram", "--uml", "list", of)
        claim("`--uml list` prints --model only for model/<slug>/ IRIs; the other model gets a warning, not '--model x'",
              rc == 0 and "--uml ClassDiagram --model uml-test" in log and "--model x" not in log
              and any(l.startswith("[Warning]") and "https://other.example/models/x/" in l for l in log.splitlines()),
              log.strip())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"SUMMARY diagram-uml-acceptance claims={len(results)} confirmed={sum(results)} result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
