"""model_impact follows arch:DependsOn (core 0.7.0), arch:HasPart, the C4 relationships and the UML Dependency family
(spec §9; directions are data in modules/aisep-core/impact.ttl, modules/c4/impact.ttl and modules/uml/impact.ttl).

Model: modules/c4/tests/valid/dual-model-ok.ttl (a valid C4 + am4 dual model, with one arch:HasPart) plus one
arch:DependsOn between two am4 components and a small UML part, copied into models/t/ of the temp repo. Each relationship class gets a positive case (a change to the
depended-on end reaches the dependent end) and a negative one (the other way is not traversed, nor listed as related).
"""
import os

from conftest import ROOT
from aisep import core
from aisep import tools as T

CFG = T.Config()
DEPENDS_ON = """
:billing a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "计费"@zh .
:ledger a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "总账"@zh .
:rel-billing-dependson-ledger a arch:DependsOn ; arch:inModel :t ; arch:source :billing ; arch:target :ledger .
"""
UML = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix uml:  <https://meta.linked.archi/uml/onto#> .
@prefix :     <https://aisep.example/model/t/> .
:invoice a uml:Class ; arch:inModel :t ; skos:prefLabel "发票"@zh .
:taxCalc a uml:Class ; arch:inModel :t ; skos:prefLabel "计税"@zh .
:priceable a uml:Interface ; arch:inModel :t ; skos:prefLabel "可计价"@zh .
:use-invoice-taxCalc a uml:Usage ; arch:inModel :t ; arch:source :invoice ; arch:target :taxCalc .
:real-invoice-priceable a uml:InterfaceRealization ; arch:inModel :t ; arch:source :invoice ; arch:target :priceable .
"""


def _model(repo):
    with open(os.path.join(ROOT, "modules/c4/tests/valid/dual-model-ok.ttl"), encoding="utf-8") as fh:
        text = fh.read()
    os.makedirs(repo / "models/t")
    (repo / "models/t/c4.ttl").write_text(text + DEPENDS_ON, encoding="utf-8")
    (repo / "models/t/uml.ttl").write_text(UML, encoding="utf-8")


def hits(repo, focus, mode="depends", depth=3):
    """{short name: (depth, related, first-hop class)} of model_impact(t:<focus>)."""
    r = T.model_impact(CFG, "t:" + focus, mode=mode, depth=depth, repo=str(repo))
    assert r["invalidModel"] is None
    return {it["iri"].rsplit("/", 1)[1]: (it["depth"], it["related"], it["path"][-1]["via"].rsplit("#", 1)[1])
            for it in r["items"]}


def traversed(h, name, depth=None, via=None):
    return name in h and not h[name][1] and (depth is None or h[name][0] == depth) and (via is None or h[name][2] == via)


def test_dependson_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "ledger"), "billing", 1, "DependsOn")       # the dependent end is reached
    assert "ledger" not in hits(repo, "billing")                           # the depended-on end is not
    assert traversed(hits(repo, "billing", "ripple"), "ledger", 1, "DependsOn")


def test_c4_using_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "orderSys"), "buyer", 1, "Using")           # buyer uses orderSys
    assert traversed(hits(repo, "payment"), "orderSys", 1, "Using")         # orderSys uses payment
    assert "orderSys" not in hits(repo, "buyer")
    assert "payment" not in hits(repo, "orderSys")
    assert traversed(hits(repo, "orderSys", "ripple"), "payment", 1, "Using")


def test_c4_containment_both(repo):
    _model(repo)
    sys_, api, val = hits(repo, "orderSys"), hits(repo, "orderApi"), hits(repo, "validator")
    assert traversed(sys_, "orderApi", 1, "ContainerContainment") and traversed(sys_, "orderDb", 1, "ContainerContainment")
    assert traversed(api, "orderSys", 1, "ContainerContainment")
    assert traversed(api, "validator", 1, "ComponentContainment") and traversed(val, "orderApi", 1, "ComponentContainment")
    assert traversed(val, "orderSys", 2)                                    # containment chains upward
    assert "k8s" not in val                                                 # ... but does not carry deployment across


def test_structurizr_deployment_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "k8s"), "orderApi", 1, "Deployment")        # orderApi is deployed on k8s
    assert "k8s" not in hits(repo, "orderApi")
    assert traversed(hits(repo, "orderApi", "ripple"), "k8s", 1, "Deployment")


def test_core_haspart_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "k8s"), "euWest", 1, "HasPart")             # euWest (whole) has part k8s
    assert "k8s" not in hits(repo, "euWest")                                # the part does not depend on the whole
    assert traversed(hits(repo, "euWest", "ripple"), "k8s", 1, "HasPart")


def test_uml_dependency_family_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "taxCalc"), "invoice", 1, "Usage")          # client invoice uses supplier taxCalc
    assert traversed(hits(repo, "priceable"), "invoice", 1, "InterfaceRealization")
    inv = hits(repo, "invoice")
    assert "taxCalc" not in inv and "priceable" not in inv                  # suppliers do not depend on the client
    assert traversed(hits(repo, "invoice", "ripple"), "taxCalc", 1, "Usage")


def test_declared_direction_agrees_with_core_dependency_property():
    """A qualified class whose unqualified form is a subproperty of arch:dependsOn (source depends on target) must not
    be declared Forward, nor one under arch:dependencyOf (target depends on source) Backward: e.g. am4:Serving
    (am4:serves ⊑ arch:dependencyOf) is Forward, arch:DependsOn Backward. Classes left undeclared are not judged here."""
    ctx = core.Ctx(core.discover(ROOT), [], root=ROOT)
    dep = dict(ctx.rows(f"SELECT ?c ?d WHERE {{ GRAPH ?g {{ ?c aisep:dependency ?d }} {ctx.onto_graph_filter()} }}"))
    wrong = {core.ARCH + "dependsOn": "Forward", core.ARCH + "dependencyOf": "Backward"}
    rows = ctx.rows("""SELECT DISTINCT ?c ?root WHERE { GRAPH ?g1 { ?c arch:unqualifiedForm ?p }
        GRAPH ?g2 { ?p rdfs:subPropertyOf* ?root } VALUES ?root { arch:dependsOn arch:dependencyOf } }""")
    judged = {}
    for c, root in rows:
        d = (ctx.nearest(c, dep) or "").replace(core.AISEP, "")
        if d:
            judged[core.short(c)] = d
            assert d != wrong[root], f"{core.short(c)} is {d} but its unqualified form is under {core.short(root)}"
    assert judged.get("arch:DependsOn") == "Backward" and judged.get("am4:Serving") == "Forward", judged
    assert {judged.get("uml:" + c) for c in ("Dependency", "Usage")} == {"Backward"}, judged
