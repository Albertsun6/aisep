"""Acceptance test for `aisep.py diagram` (ArchiMate 4 view -> SVG generated from the model).

Every expected number comes from an independent SPARQL query run through `aisep.py query`, never from aisep/diagram.py.
Each claim prints CONFIRMED / REFUTED with evidence; exit 0 only if every claim is CONFIRMED.

Run:  <venv python> tests/acceptance/test_diagram.py      (also run by `aisep.py test`)
"""
import glob, os, re, shutil, subprocess, sys, tempfile
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AISEP = os.path.join(ROOT, "tools", "aisep.py")
M = "https://aisep.example/model/"
VP = "https://meta.linked.archi/archimate4/viewpoints#"
results = []
LAST_ENDS = {}  # relationship IRI -> (source, target, data-type) of the last diagram() call
LAST_GEO = {}   # "boxes": element IRI -> (x, y, w, h); "paths": relationship IRI -> [(x, y), ...]


def run(*args):
    p = subprocess.run([sys.executable, AISEP, *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def files(slug, d=None):
    return sorted(glob.glob(os.path.join(d or os.path.join(ROOT, "models", slug), "*.ttl")))


def count(q, fs):
    rc, out = run("query", q, *fs)
    lines = [l for l in out.splitlines() if l and not l.startswith("--")]
    assert rc == 0 and lines[0] == "n", out
    return int(lines[1])


def iris_in_model(model, fs):
    rc, out = run("query", f"SELECT DISTINCT ?x WHERE {{ ?x arch:inModel <{model}> }}", *fs)
    assert rc == 0, out
    return {l for l in out.splitlines()[1:] if l and not l.startswith("--")}


def rows(q, fs):
    rc, out = run("query", q, *fs)
    assert rc == 0, out
    return [tuple(l.split("\t")) for l in out.splitlines()[1:] if l and not l.startswith("--")]


def short(iri):
    slug, loc = iri[len(M):].split("/", 1)
    return f"{slug}:{loc}"


def claim(text, ok, evidence):
    results.append(ok)
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] {text}\n      evidence: {evidence}")


def diagram(out, *args):
    rc, log = run("diagram", *args, "-o", out)
    assert rc == 0, log
    with open(out, encoding="utf-8") as fh:
        svg = fh.read()
    root = ElementTree.fromstring(svg)  # claim: well-formed XML (raises otherwise)
    kinds, ends, boxes, paths = {}, {}, {}, {}
    for e in root.iter():
        k = e.get("data-kind")
        if k:
            kinds.setdefault(k, []).append(e.get("data-iri"))
        if k == "relationship":
            ends[e.get("data-iri")] = (e.get("data-source"), e.get("data-target"), e.get("data-type"))
            paths[e.get("data-iri")] = [tuple(float(v) for v in p.split(",")) for p in e.get("d")[1:].split(" L")]
        if k == "element":
            boxes[e.get("data-iri")] = tuple(float(v) for v in e.get("data-box").split())
    LAST_ENDS.clear(); LAST_ENDS.update(ends)
    LAST_GEO.clear(); LAST_GEO.update(boxes=boxes, paths=paths)
    return svg, kinds.get("element", []), kinds.get("relationship", [])


ELEM = ("{{ ?x arch:inModel <{m}> . ?x a ?t . <{vp}> arch:includesConcept ?t "
        "FILTER NOT EXISTS {{ ?x arch:source ?s0 }} }}")


def viewpoint_case(slug, viewpoint, tmp):
    model, vp, fs = f"{M}{slug}/", VP + viewpoint, files(slug)
    want_e = count(f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {ELEM.format(m=model, vp=vp)}", fs)
    el_s = ELEM.format(m=model, vp=vp).replace("?x", "?s").replace("?t ", "?ts ").replace("?s0", "?s1")
    el_t = ELEM.format(m=model, vp=vp).replace("?x", "?o").replace("?t ", "?to ").replace("?s0", "?s2")
    want_r = count(f"""SELECT (COUNT(DISTINCT ?r) AS ?n) WHERE {{ ?r arch:inModel <{model}> ; arch:source ?s ;
                       arch:target ?o FILTER(?s != ?o) {el_s} {el_t} }}""", fs)
    out = os.path.join(tmp, f"{slug}-{viewpoint}.svg")
    svg, els, rels = diagram(out, "--viewpoint", viewpoint, "--model", slug, *fs)
    claim(f"{slug} {viewpoint}: element count equals SPARQL count (>0)", len(els) == want_e > 0,
          f"svg={len(els)} sparql={want_e}")
    want_set = {x for (x,) in rows(f"SELECT DISTINCT ?x WHERE {ELEM.format(m=model, vp=vp)}", fs)}
    claim(f"{slug} {viewpoint}: drawn element set equals the SPARQL element set",
          {short(i) for i in els} == want_set, f"only_svg={sorted({short(i) for i in els} - want_set)[:3]} "
          f"only_sparql={sorted(want_set - {short(i) for i in els})[:3]}")
    ends_claim(f"{slug} {viewpoint}", model, fs)
    geometry_claim(f"{slug} {viewpoint}")
    claim(f"{slug} {viewpoint}: relationship count equals SPARQL count (>0)", len(rels) == want_r > 0,
          f"svg={len(rels)} sparql={want_r}")
    members = iris_in_model(model, fs)
    ghosts = [i for i in els + rels if short(i) not in members]
    claim(f"{slug} {viewpoint}: every data-iri is a member of the model", not ghosts, f"not members: {ghosts[:3]}")
    claim(f"{slug} {viewpoint}: no element or relationship drawn twice", len(set(els)) == len(els)
          and len(set(rels)) == len(rels), f"elements={len(els)} distinct={len(set(els))}")
    svg2, _, _ = diagram(out + ".2.svg", "--viewpoint", viewpoint, "--model", slug, *fs)
    claim(f"{slug} {viewpoint}: generating twice gives identical bytes", svg == svg2, f"len={len(svg)}")
    return svg, els, rels


def on_border(p, box, tol=1.5):
    x, y, w, h = box
    px, py = p
    return ((abs(px - x) <= tol or abs(px - x - w) <= tol) and y - tol <= py <= y + h + tol) or \
           ((abs(py - y) <= tol or abs(py - y - h) <= tol) and x - tol <= px <= x + w + tol)


def off_box(paths):
    b, bad = LAST_GEO["boxes"], []
    for r, pts in paths.items():
        s, t, _ = LAST_ENDS[r]
        if not (on_border(pts[0], b[s]) and on_border(pts[-1], b[t])):
            bad.append(short(r))
    return bad


def geometry_claim(name):
    """Each drawn line starts on its data-source's box and ends on its data-target's box."""
    bad = off_box(LAST_GEO["paths"])
    claim(f"{name}: every line starts on its source's box and ends on its target's box (geometry)",
          not bad and bool(LAST_GEO["paths"]), f"off-box={bad[:3]} checked={len(LAST_GEO['paths'])}")
    # mutation control: the same lines drawn backwards (an edge reversed in the layout) must all be caught
    rev = off_box({r: pts[::-1] for r, pts in LAST_GEO["paths"].items()})
    claim(f"{name}: mutation control - every line reversed is caught by the geometry check",
          len(rev) == len(LAST_GEO["paths"]) > 0, f"caught={len(rev)} of {len(LAST_GEO['paths'])}")


def ends_claim(name, model, fs):
    """Every drawn relationship has the model's source, target and type (SPARQL)."""
    facts = rows(f"SELECT ?r ?s ?o ?t WHERE {{ ?r arch:inModel <{model}> ; arch:source ?s ; arch:target ?o ; a ?t }}", fs)
    st, types = {r: (s, o) for r, s, o, _ in facts}, {}
    for r, _, _, t in facts:
        types.setdefault(r, set()).add(t)
    def mismatched(ends):
        return [short(r) for r, (s, o, t) in ends.items()
                if (short(s), short(o)) != st.get(short(r)) or t not in types.get(short(r), set())]
    bad = mismatched(LAST_ENDS)
    claim(f"{name}: every drawn relationship has the model's source, target and type", not bad and bool(LAST_ENDS),
          f"mismatched={bad[:3]} checked={len(LAST_ENDS)}")
    # mutation control: every relationship with source and target swapped must be caught
    swapped = mismatched({r: (o, s, t) for r, (s, o, t) in LAST_ENDS.items()})
    claim(f"{name}: mutation control - every relationship with swapped ends is caught by the endpoint check",
          len(swapped) == len(LAST_ENDS) > 0, f"caught={len(swapped)} of {len(LAST_ENDS)}")


def main():
    tmp = tempfile.mkdtemp(prefix="aisep-diagram-")
    try:
        # 1-2: one view per sample model (workbench: requirements realization incl. business-common Process/Role;
        #      procurement: layered = business + application)
        svg, els, rels = viewpoint_case("workbench", "RequirementsRealizationViewpoint", tmp)
        claim("workbench view contains a business/common-domain element (am4:Process)",
              'data-type="am4:Process"' in svg, "am4:Process present" if 'am4:Process' in svg else "absent")
        viewpoint_case("procurement", "LayeredViewpoint", tmp)

        # 3: renaming an element changes the picture, nothing else
        d = os.path.join(tmp, "wb")
        shutil.copytree(os.path.join(ROOT, "models", "workbench"), d)
        am4 = os.path.join(d, "am4.ttl")
        txt = open(am4, encoding="utf-8").read()
        old, new = '"关口批准流转"@zh', '"关口批准流转（改名探针）"@zh'
        assert txt.count(old) == 1
        open(am4, "w", encoding="utf-8").write(txt.replace(old, new))
        svg3, els3, rels3 = diagram(os.path.join(tmp, "renamed.svg"), "--viewpoint", "RequirementsRealizationViewpoint",
                                    "--model", "workbench", *files("workbench", d))
        claim("rename: new label drawn, old label gone, same data-iri sets",
              "关口批准流转（改名探针）" in svg3 and ">关口批准流转<" in svg and ">关口批准流转<" not in svg3
              and sorted(els3) == sorted(els) and sorted(rels3) == sorted(rels),
              f"new_in={'关口批准流转（改名探针）' in svg3} old_before={'>关口批准流转<' in svg}")

        # 5: declared view (arch:Diagram + arch:inView): exactly its members, plus relationships between them
        d2 = os.path.join(tmp, "wb2")
        shutil.copytree(os.path.join(ROOT, "models", "workbench"), d2)
        view = f"{M}workbench/view-diagramProbe"
        members = ["gateApprovalFlow", "approverRole", "reqApprovalProgress"]
        with open(os.path.join(d2, "am4.ttl"), "a", encoding="utf-8") as fh:
            fh.write(f"\n<{view}> a arch:Diagram ;\n    arch:inModel <{M}workbench/> ;\n"
                     f'    skos:prefLabel "出图探针视图"@zh ;\n'
                     f"    arch:viewConformsToViewpoint <{VP}RequirementsRealizationViewpoint> .\n"
                     + "".join(f":{x} arch:inView <{view}> .\n" for x in members)
                     # a relationship asserted with an am4 type and its am4 subclass: the subclass must be drawn
                     + f":rel-diagramProbe-twoTypes a am4:Association, am4:DirectedAssociation ;\n"
                       f"    arch:inModel <{M}workbench/> ;\n"
                       f'    skos:prefLabel "出图探针：多类型关系"@zh ;\n'
                       f"    arch:source :approverRole ;\n    arch:target :reqApprovalProgress .\n")
        fs2 = files("workbench", d2)
        rc, log = run("gate", *fs2)
        claim("declared view fixture passes gate", rc == 0, log.strip().splitlines()[-1])
        vals = " ".join(f":{x}" for x in members)
        want_r = count(f"""PREFIX : <{M}workbench/> SELECT (COUNT(DISTINCT ?r) AS ?n) WHERE {{
                           VALUES ?s {{ {vals} }} VALUES ?o {{ {vals} }} ?r arch:source ?s ; arch:target ?o
                           FILTER(?s != ?o) }}""", fs2)
        svg5, els5, rels5 = diagram(os.path.join(tmp, "declared.svg"), "--view", view, *fs2)
        claim("declared view: exactly the 3 arch:inView members are drawn",
              sorted(els5) == sorted(f"{M}workbench/{x}" for x in members), f"drawn={[short(i) for i in els5]}")
        claim("declared view: relationship count equals SPARQL count (>0)", len(rels5) == want_r > 0,
              f"svg={len(rels5)} sparql={want_r}")
        ends_claim("declared view", f"{M}workbench/", fs2)
        geometry_claim("declared view")
        claim("declared view: title is the view's prefLabel", ">出图探针视图<" in svg5, "title checked")
        two = LAST_ENDS.get(f"{M}workbench/rel-diagramProbe-twoTypes", (None, None, None))[2]
        claim("a relationship typed am4:Association and am4:DirectedAssociation is drawn as the most specific type",
              two == "am4:DirectedAssociation", f"data-type={two}")

        # errors are reported, not drawn
        rc, log = run("diagram", "--viewpoint", "NoSuchViewpoint", "--model", "workbench", "-o",
                      os.path.join(tmp, "x.svg"), *files("workbench"))
        claim("unknown viewpoint exits 1 with a Violation", rc == 1 and "[Violation]" in log, log.strip()[-120:])
        rc, log = run("diagram", "--view", "http://not an iri/", "-o", os.path.join(tmp, "v.svg"), *files("workbench"))
        claim("--view that is not a valid IRI exits 1 with a Violation", rc == 1 and "[Violation]" in log
              and not os.path.exists(os.path.join(tmp, "v.svg")), log.strip()[-120:])
        rc, log = run("diagram", "--viewpoint", "LayeredViewpoint", "--model", "procurement/> } #", "-o",
                      os.path.join(tmp, "y.svg"), *files("procurement"))
        claim("--model that is not a plain name is refused (no SPARQL injection)", rc == 1 and "[Violation]" in log
              and not os.path.exists(os.path.join(tmp, "y.svg")), log.strip()[-120:])
        rc, log = run("diagram", "--viewpoint", "LayeredViewpoint", "--model", "noSuchModel", "-o",
                      os.path.join(tmp, "z.svg"), *files("procurement"))
        claim("a view with no element exits 1 instead of writing an empty picture", rc == 1 and "[Violation]" in log
              and not os.path.exists(os.path.join(tmp, "z.svg")), log.strip()[-120:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"SUMMARY diagram-acceptance claims={len(results)} confirmed={sum(results)} result={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
