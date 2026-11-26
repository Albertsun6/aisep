"""Acceptance test for C4 views of `aisep.py diagram` (aisep/diagram_c4.py).

Input: modules/c4/tests/valid/dual-model-ok.ttl plus a few extra C4 members appended in a temp copy (a web app, a
second external system, a component calling an external system, a second component, a database server and an
infrastructure node), so every view has inner and outer elements and at least one implied relationship.
Every expected set comes from an independent SPARQL query run through `aisep.py query` over the built direct triples
(c4:hasContainer, c4:hasComponent, c4:uses, structurizr:deployedOn, arch:hasPart), never from aisep/diagram_c4.py.
Each claim prints CONFIRMED / REFUTED with evidence; exit 0 only if every claim is CONFIRMED.

Run:  <venv python> tests/acceptance/test_diagram_c4.py      (also run by `aisep.py test`)
"""
import os, shutil, subprocess, sys, tempfile
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
T = "https://aisep.example/model/t/"
PFX = ("PREFIX c4: <https://meta.linked.archi/c4/onto#> PREFIX sz: <https://meta.linked.archi/c4/structurizr#> "
       f"PREFIX t: <{T}> ")
PEOPLE_SYSTEMS = "VALUES ?ty { c4:Person c4:ExternalPerson c4:SoftwareSystem c4:ExternalSoftwareSystem }"
DOWN = "(c4:hasContainer|c4:hasComponent)*"
results = []

EXTRA = """
:orderWeb a c4:ClientSideWebApp ; arch:inModel :t ; skos:prefLabel "订单前端"@zh ; c4:technology "React" .
:rel-orderSys-has-orderWeb a c4:ContainerContainment ; arch:inModel :t ; arch:source :orderSys ; arch:target :orderWeb .
:rel-buyer-uses-orderWeb a c4:Using ; arch:inModel :t ; arch:source :buyer ; arch:target :orderWeb ;
    skos:prefLabel "下单"@zh ; c4:technology "HTTPS" .
:rel-orderWeb-uses-orderApi a c4:Using ; arch:inModel :t ; arch:source :orderWeb ; arch:target :orderApi ;
    skos:prefLabel "调用 API"@zh ; c4:technology "JSON/HTTPS" .
:sms a c4:ExternalSoftwareSystem ; arch:inModel :t ; skos:prefLabel "短信网关"@zh .
:rel-orderApi-uses-sms a c4:Using ; arch:inModel :t ; arch:source :orderApi ; arch:target :sms ;
    skos:prefLabel "发送通知"@zh ; c4:technology "HTTPS" .
:rel-validator-uses-payment a c4:Using ; arch:inModel :t ; arch:source :validator ; arch:target :payment ;
    skos:prefLabel "预校验支付"@zh .
:audit a c4:Component ; arch:inModel :t ; skos:prefLabel "审计记录器"@zh .
:rel-orderApi-has-audit a c4:ComponentContainment ; arch:inModel :t ; arch:source :orderApi ; arch:target :audit .
:rel-validator-uses-audit a c4:Using ; arch:inModel :t ; arch:source :validator ; arch:target :audit ;
    skos:prefLabel "记录校验结果"@zh .
:dbNode a structurizr:DeploymentNode ; arch:inModel :t ; skos:prefLabel "数据库服务器"@zh ;
    structurizr:environment "Production" .
:rel-euWest-haspart-dbNode a arch:HasPart ; arch:inModel :t ; arch:source :euWest ; arch:target :dbNode .
:rel-orderDb-deployed-dbNode a structurizr:Deployment ; arch:inModel :t ; arch:source :orderDb ; arch:target :dbNode .
:lb a structurizr:InfrastructureNode ; arch:inModel :t ; skos:prefLabel "负载均衡"@zh ; structurizr:environment "Production" .
:rel-euWest-haspart-lb a arch:HasPart ; arch:inModel :t ; arch:source :euWest ; arch:target :lb .
"""
VIEW = """
:view-c4Probe a arch:Diagram ; arch:inModel :t ; skos:prefLabel "C4 声明式探针"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/c4/viewpoints#ContainerDiagram> .
:orderSys arch:inView :view-c4Probe . :orderApi arch:inView :view-c4Probe . :orderDb arch:inView :view-c4Probe .
:buyer arch:inView :view-c4Probe .
"""


def run(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def rows(q, fs):
    rc, out = run("query", PFX + q, *fs)
    assert rc == 0, out
    return [tuple(l.split("\t")) for l in out.splitlines()[1:] if l and not l.startswith("--")]


def ids(q, fs):
    return {r[0] for r in rows(q, fs)}


def short(iri):
    return "t:" + iri[len(T):] if iri and iri.startswith(T) else iri


def claim(text, ok, evidence):
    results.append(ok)
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {text}\n      evidence: {evidence}")


def diagram(out, *args):
    rc, log = run("diagram", *args, "-o", out)
    assert rc == 0, log
    svg = open(out, encoding="utf-8").read()
    root = ElementTree.fromstring(svg)  # well-formed XML (raises otherwise)
    boxes, edges = [], []
    for e in root.iter():
        k = e.get("data-kind")
        if k in ("element", "boundary", "deployment-node"):
            boxes.append({"kind": k, "iri": short(e.get("data-iri")), "parent": short(e.get("data-parent")) or None,
                          "box": tuple(float(v) for v in e.get("data-box").split())})
        elif k == "relationship":
            pts = [tuple(float(v) for v in p.split(",")) for p in e.get("d")[1:].split(" L")]
            edges.append({"iris": tuple(short(i) for i in e.get("data-iri").split()), "implied": e.get("data-implied") == "true",
                          "source": short(e.get("data-source")), "target": short(e.get("data-target")), "pts": pts})
    return svg, boxes, edges


def on_border(p, box, tol=1.5):
    x, y, w, h = box
    px, py = p
    vertical = (abs(px - x) <= tol or abs(px - x - w) <= tol) and y - tol <= py <= y + h + tol
    horizontal = (abs(py - y) <= tol or abs(py - y - h) <= tol) and x - tol <= px <= x + w + tol
    return vertical or horizontal


def common_claims(name, svg, boxes, edges, using):
    """Claims every C4 view must satisfy. using: {u: (s, o)} from SPARQL."""
    elements = [b for b in boxes if b["kind"] == "element"]
    drawn = {b["iri"] for b in elements}
    bad = [e["iris"] for e in edges if not e["implied"] and (len(e["iris"]) != 1 or using.get(e["iris"][0]) != (e["source"], e["target"]))]
    claim(f"{name}: every direct line is a c4:Using with the model's source and target", not bad and bool(edges),
          f"mismatched={bad[:3]} lines={len(edges)}")
    want = {u for u, (s, o) in using.items() if s in drawn and o in drawn and s != o}
    got = {e["iris"][0] for e in edges if not e["implied"]}
    claim(f"{name}: every c4:Using between two drawn elements is drawn as a direct line, and only those",
          want == got, f"missing={sorted(want - got)} extra={sorted(got - want)}")
    imp_bad = [e["iris"] for e in edges if e["implied"] and not all(u in using for u in e["iris"])]
    claim(f"{name}: every implied line stands for c4:Using resources of the model", not imp_bad, f"bad={imp_bad}")
    by = {b["iri"]: b["box"] for b in elements}
    geo = [e["iris"] for e in edges if not (on_border(e["pts"][0], by[e["source"]]) and on_border(e["pts"][-1], by[e["target"]]))]
    claim(f"{name}: every line starts on its source's box and ends on its target's box (geometry)", not geo,
          f"off-box={geo[:3]} checked={len(edges)}")
    claim(f"{name}: no arch:Refines line and no am4 element drawn", "refines" not in svg and "orderComp" not in svg
          and "am4:" not in svg, "checked data-iri/data-type text")


def main():
    tmp = tempfile.mkdtemp(prefix="aisep-diagram-c4-")
    try:
        src = os.path.join(tmp, "c4.ttl")
        shutil.copy(os.path.join(ROOT, "modules", "c4", "tests", "valid", "dual-model-ok.ttl"), src)
        with open(src, "a", encoding="utf-8") as fh:
            fh.write(EXTRA)
        fs = [src]
        rc, log = run("gate", *fs)
        claim("enriched C4 fixture passes gate", rc == 0, log.strip().splitlines()[-1])
        using = {u: (s, o) for u, s, o in rows("SELECT ?u ?s ?o WHERE { ?u a c4:Using ; arch:source ?s ; arch:target ?o }", fs)}

        # 1. system context of orderSys
        svg, boxes, edges = diagram(os.path.join(tmp, "ctx.svg"), "--viewpoint", "SystemContext", "--of", T + "orderSys", *fs)
        want = {"t:orderSys"} | ids(f"""SELECT DISTINCT ?x WHERE {{ t:orderSys {DOWN} ?a . {{ ?a c4:uses ?b }} UNION {{ ?b c4:uses ?a }}
                                       ?x {DOWN} ?b . ?x a ?ty {PEOPLE_SYSTEMS} FILTER(?x != t:orderSys) }}""", fs)
        got = {b["iri"] for b in boxes if b["kind"] == "element"}
        claim("context: elements = orderSys + people/systems connected to it or its descendants (SPARQL)", got == want,
              f"svg={sorted(got)} sparql={sorted(want)}")
        claim("context: no boundary and no container drawn", all(b["kind"] == "element" for b in boxes)
              and 'data-type="Container"' not in svg and 'data-type="Database"' not in svg, f"boxes={len(boxes)}")
        imp = {(e["source"], e["target"]): e["iris"] for e in edges if e["implied"]}
        claim("context: orderApi→sms is drawn as the implied line orderSys→sms",
              imp.get(("t:orderSys", "t:sms")) == ("t:rel-orderApi-uses-sms",), f"implied={imp}")
        claim("context: buyer→orderWeb is not lifted, buyer→orderSys already exists directly",
              ("t:buyer", "t:orderSys") not in imp and any(e["iris"] == ("t:rel-buyer-uses-orderSys",) for e in edges),
              f"implied={sorted(imp)}")
        common_claims("context", svg, boxes, edges, using)
        svg2, _, _ = diagram(os.path.join(tmp, "ctx2.svg"), "--viewpoint", "SystemContext", "--of", T + "orderSys", *fs)
        claim("context: generating twice gives identical bytes", svg == svg2, f"len={len(svg)}")

        # 2. containers of orderSys
        svg, boxes, edges = diagram(os.path.join(tmp, "cont.svg"), "--viewpoint", "ContainerDiagram", "--of", T + "orderSys", *fs)
        inner = ids("SELECT ?c WHERE { t:orderSys c4:hasContainer ?c }", fs)
        outer = ids(f"""SELECT DISTINCT ?x WHERE {{ t:orderSys c4:hasContainer ?c . ?c c4:hasComponent* ?a .
                         {{ ?a c4:uses ?b }} UNION {{ ?b c4:uses ?a }} ?x {DOWN} ?b . ?x a ?ty {PEOPLE_SYSTEMS}
                         FILTER(?x != t:orderSys) }}""", fs)
        got_in = {b["iri"] for b in boxes if b["kind"] == "element" and b["parent"] == "t:orderSys"}
        got_out = {b["iri"] for b in boxes if b["kind"] == "element" and b["parent"] is None}
        claim("container: inside the orderSys boundary = its c4:hasContainer targets (SPARQL)", got_in == inner,
              f"svg={sorted(got_in)} sparql={sorted(inner)}")
        claim("container: outside = people/systems connected to those containers or their components (SPARQL)",
              got_out == outer, f"svg={sorted(got_out)} sparql={sorted(outer)}")
        claim("container: the boundary is orderSys and it encloses every inner box",
              [b["iri"] for b in boxes if b["kind"] == "boundary"] == ["t:orderSys"] and all(
                  inside(b["box"], next(x["box"] for x in boxes if x["kind"] == "boundary")) for b in boxes
                  if b["parent"] == "t:orderSys"), "boundary geometry checked")
        imp = {(e["source"], e["target"]): e["iris"] for e in edges if e["implied"]}
        claim("container: validator→payment is drawn as the implied line orderApi→payment",
              imp.get(("t:orderApi", "t:payment")) == ("t:rel-validator-uses-payment",), f"implied={imp}")
        claim("container: validator→orderDb is not lifted, orderApi→orderDb already exists directly",
              ("t:orderApi", "t:orderDb") not in imp, f"implied={sorted(imp)}")
        claim("container: line text has the Using's prefLabel and [technology]", "读写订单" in svg and "[SQL]" in svg,
              "读写订单 / [SQL]")
        common_claims("container", svg, boxes, edges, using)

        # 3. components of orderApi
        svg, boxes, edges = diagram(os.path.join(tmp, "comp.svg"), "--viewpoint", "ComponentDiagram", "--of", T + "orderApi", *fs)
        inner = ids("SELECT ?c WHERE { t:orderApi c4:hasComponent ?c }", fs)
        outer = ids(f"""SELECT DISTINCT ?x WHERE {{ t:orderApi c4:hasComponent ?a . {{ ?a c4:uses ?b }} UNION {{ ?b c4:uses ?a }}
                         {{ t:orderSys c4:hasContainer ?x . ?x c4:hasComponent* ?b FILTER(?x != t:orderApi) }} UNION
                         {{ ?x {DOWN} ?b . ?x a ?ty {PEOPLE_SYSTEMS} FILTER(?x != t:orderSys) }} }}""", fs)
        got_in = {b["iri"] for b in boxes if b["kind"] == "element" and b["parent"] == "t:orderApi"}
        got_out = {b["iri"] for b in boxes if b["kind"] == "element" and b["parent"] is None}
        claim("component: inside the orderApi boundary = its c4:hasComponent targets (SPARQL)", got_in == inner,
              f"svg={sorted(got_in)} sparql={sorted(inner)}")
        claim("component: outside = same-system containers and people/systems the components use (SPARQL)",
              got_out == outer, f"svg={sorted(got_out)} sparql={sorted(outer)}")
        common_claims("component", svg, boxes, edges, using)

        # 4. deployment, environment Production
        svg, boxes, edges = diagram(os.path.join(tmp, "dep.svg"), "--viewpoint", "C4Deployment", "--of", "Production", *fs)
        nest = set(rows("SELECT ?p ?n WHERE { ?p arch:hasPart ?n }", fs))
        got_nodes = {(b["parent"], b["iri"]) for b in boxes if b["kind"] == "deployment-node" and b["parent"]}
        claim("deployment: deployment-node nesting = arch:hasPart between deployment nodes (SPARQL)",
              got_nodes == {(p, n) for p, n in nest if n != "t:lb"}, f"svg={sorted(got_nodes)} sparql={sorted(nest)}")
        placed = set(rows("SELECT ?n ?c WHERE { ?c sz:deployedOn ?n }", fs)) | {("t:euWest", "t:lb")}
        got = {(b["parent"], b["iri"]) for b in boxes if b["kind"] == "element"}
        claim("deployment: each container sits in the node structurizr:deployedOn names; infrastructure node in its parent",
              got == placed, f"svg={sorted(got)} sparql={sorted(placed)}")
        claim("deployment: every box lies inside its parent box", all(
            inside(b["box"], next(x["box"] for x in boxes if x["iri"] == b["parent"])) for b in boxes if b["parent"]),
              f"boxes={len(boxes)}")
        claim("deployment: the node title shows structurizr:instances", "×3" in svg, "×3")
        common_claims("deployment", svg, boxes, edges, using)

        # 5. renaming changes the picture, nothing else
        d = os.path.join(tmp, "renamed.ttl")
        txt = open(src, encoding="utf-8").read()
        assert txt.count('"订单 API"@zh') == 1
        open(d, "w", encoding="utf-8").write(txt.replace('"订单 API"@zh', '"订单 API（改名探针）"@zh'))
        _, boxes0, _ = diagram(os.path.join(tmp, "c0.svg"), "--viewpoint", "ContainerDiagram", "--of", T + "orderSys", *fs)
        svg3, boxes3, _ = diagram(os.path.join(tmp, "c3.svg"), "--viewpoint", "ContainerDiagram", "--of", T + "orderSys", d)
        claim("rename: new label drawn, old gone, same element set", "订单 API（改名探针）" in svg3 and ">订单 API<" not in svg3
              and sorted(b["iri"] for b in boxes3) == sorted(b["iri"] for b in boxes0), "checked")

        # 6. declared C4 view: an element containing another member becomes its boundary
        dv = os.path.join(tmp, "view.ttl")
        open(dv, "w", encoding="utf-8").write(txt + VIEW)
        rc, log = run("gate", dv)
        claim("declared C4 view fixture passes gate", rc == 0, log.strip().splitlines()[-1])
        svg, boxes, edges = diagram(os.path.join(tmp, "dv.svg"), "--view", T + "view-c4Probe", dv)
        got = {(b["kind"], b["iri"], b["parent"]) for b in boxes}
        claim("declared C4 view: orderSys is the boundary of orderApi and orderDb, buyer outside",
              got == {("boundary", "t:orderSys", None), ("element", "t:orderApi", "t:orderSys"),
                      ("element", "t:orderDb", "t:orderSys"), ("element", "t:buyer", None)}, f"drawn={sorted(got)}")
        claim("declared C4 view: title is the view's prefLabel", ">C4 声明式探针<" in svg, "title checked")
        common_claims("declared", svg, boxes, edges, using)

        # errors are reported, not drawn
        for args, text in [(("ContainerDiagram", T + "orderApi"), "ContainerDiagram --of a container"),
                           (("ComponentDiagram", T + "orderSys"), "ComponentDiagram --of a system"),
                           (("C4Deployment", "Staging"), "C4Deployment --of an environment with no node"),
                           (("C4Deployment", "../Production"), "C4Deployment --of a non-plain name")]:
            out = os.path.join(tmp, "err.svg")
            rc, log = run("diagram", "--viewpoint", args[0], "--of", args[1], "-o", out, *fs)
            claim(f"{text} exits 1 with a Violation and writes nothing", rc == 1 and "[Violation]" in log
                  and not os.path.exists(out), log.strip()[-120:])
        rc, log = run("diagram", "--viewpoint", "ContainerDiagram", "-o", os.path.join(tmp, "x.svg"), *fs)
        claim("a C4 viewpoint without --of prints usage (exit 2)", rc == 2, f"rc={rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"SUMMARY diagram-c4-acceptance claims={len(results)} confirmed={sum(results)} result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def inside(box, outer, tol=0.5):
    x, y, w, h = box
    X, Y, W, H = outer
    return x >= X - tol and y >= Y - tol and x + w <= X + W + tol and y + h <= Y + H + tol


if __name__ == "__main__":
    sys.exit(main())
