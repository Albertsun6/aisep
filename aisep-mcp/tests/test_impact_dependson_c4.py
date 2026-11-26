"""model_impact follows arch:DependsOn (core 0.7.0), arch:HasPart, the C4 relationships, the UML relationships and
ad:IncludesConcept (spec §9; directions are data in modules/aisep-core/impact.ttl, modules/c4/impact.ttl,
modules/uml/impact.ttl and modules/ext-governance/impact.ttl).

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
:order a uml:Class ; arch:inModel :t ; skos:prefLabel "订单"@zh .
:line a uml:Class ; arch:inModel :t ; skos:prefLabel "订单行"@zh .
:customer a uml:Class ; arch:inModel :t ; skos:prefLabel "客户"@zh .
:assoc-order-customer a uml:Association ; arch:inModel :t ; skos:prefLabel "下单"@zh ; arch:source :order ; arch:target :customer .
:agg-order-invoice a uml:Aggregation ; arch:inModel :t ; skos:prefLabel "含发票"@zh ; arch:source :order ; arch:target :invoice .
:comp-order-line a uml:Composition ; arch:inModel :t ; skos:prefLabel "含订单行"@zh ; arch:source :order ; arch:target :line .
:ucPay a uml:UseCase ; arch:inModel :t ; skos:prefLabel "付款"@zh .
:ucAuth a uml:UseCase ; arch:inModel :t ; skos:prefLabel "身份验证"@zh .
:ucCoupon a uml:UseCase ; arch:inModel :t ; skos:prefLabel "用优惠券"@zh .
:inc-pay-auth a uml:Include ; arch:inModel :t ; arch:source :ucPay ; arch:target :ucAuth .
:ext-coupon-pay a uml:Extend ; arch:inModel :t ; arch:source :ucCoupon ; arch:target :ucPay .
:actCheck a uml:Action ; arch:inModel :t ; skos:prefLabel "核对"@zh .
:actBill a uml:Action ; arch:inModel :t ; skos:prefLabel "开票"@zh .
:actSend a uml:Action ; arch:inModel :t ; skos:prefLabel "寄送"@zh .
:cf-check-bill a uml:ControlFlow ; arch:inModel :t ; arch:source :actCheck ; arch:target :actBill .
:of-bill-send a uml:ObjectFlow ; arch:inModel :t ; arch:source :actBill ; arch:target :actSend .
:if-taxCalc-customer a uml:InformationFlow ; arch:inModel :t ; arch:source :taxCalc ; arch:target :customer .
:pkgSales a uml:Package ; arch:inModel :t ; skos:prefLabel "销售"@zh .
:pkgCommon a uml:Package ; arch:inModel :t ; skos:prefLabel "公共"@zh .
:pkgBase a uml:Package ; arch:inModel :t ; skos:prefLabel "基础"@zh .
:imp-sales-common a uml:PackageImport ; arch:inModel :t ; arch:source :pkgSales ; arch:target :pkgCommon .
:merge-common-base a uml:PackageMerge ; arch:inModel :t ; arch:source :pkgCommon ; arch:target :pkgBase .
"""
DECISION = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix ad:   <https://meta.linked.archi/arch-decision#> .
@prefix :     <https://aisep.example/model/t/> .
:optLedger a ad:Option ; arch:inModel :t ; skos:prefLabel "沿用总账"@zh .
:inc-optLedger-ledger a ad:IncludesConcept ; arch:inModel :t ; arch:source :optLedger ; arch:target :ledger .
"""


def _model(repo):
    with open(os.path.join(ROOT, "modules/c4/tests/valid/dual-model-ok.ttl"), encoding="utf-8") as fh:
        text = fh.read()
    os.makedirs(repo / "models/t")
    (repo / "models/t/c4.ttl").write_text(text + DEPENDS_ON, encoding="utf-8")
    (repo / "models/t/uml.ttl").write_text(UML, encoding="utf-8")
    (repo / "models/t/decision.ttl").write_text(DECISION, encoding="utf-8")


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


def test_uml_association_family(repo):
    """Association None (related at hop 1 only); Aggregation Backward and Composition Both, both drawn whole -> part."""
    _model(repo)
    order, cust = hits(repo, "order"), hits(repo, "customer")
    assert order["customer"][1] and cust["order"][1]                       # Association: related, not traversed
    assert "invoice" not in cust and "customer" not in hits(repo, "invoice")
    assert traversed(hits(repo, "invoice"), "order", 1, "Aggregation")      # the whole depends on the shared part
    assert "invoice" not in order                                           # ... the part not on the whole
    assert traversed(order, "line", 1, "Composition") and traversed(hits(repo, "line"), "order", 1, "Composition")
    rip = hits(repo, "order", "ripple")                                     # ripple never traverses Association: customer
    assert traversed(rip, "customer", 3, "InformationFlow")                 # is reached only via invoice -> taxCalc
    assert traversed(rip, "invoice", 1, "Aggregation")


def test_uml_include_extend_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "ucAuth"), "ucPay", 1, "Include")           # the base depends on the included case
    assert traversed(hits(repo, "ucPay"), "ucCoupon", 1, "Extend")          # the extension depends on the extended case
    assert "ucAuth" not in hits(repo, "ucPay") and "ucPay" not in hits(repo, "ucCoupon")
    assert traversed(hits(repo, "ucAuth"), "ucCoupon", 2)                   # chains: auth -> pay -> coupon
    assert traversed(hits(repo, "ucPay", "ripple"), "ucAuth", 1, "Include")


def test_uml_flows_forward(repo):
    _model(repo)
    chk = hits(repo, "actCheck")
    assert traversed(chk, "actBill", 1, "ControlFlow") and traversed(chk, "actSend", 2, "ObjectFlow")
    assert "actCheck" not in hits(repo, "actBill") and "actBill" not in hits(repo, "actSend")
    assert traversed(hits(repo, "taxCalc"), "customer", 1, "InformationFlow")
    assert "taxCalc" not in hits(repo, "customer")
    assert traversed(hits(repo, "actSend", "ripple"), "actBill", 1, "ObjectFlow")


def test_uml_package_import_merge_backward(repo):
    _model(repo)
    base = hits(repo, "pkgBase")
    assert traversed(base, "pkgCommon", 1, "PackageMerge") and traversed(base, "pkgSales", 2, "PackageImport")
    assert "pkgCommon" not in hits(repo, "pkgSales") and "pkgBase" not in hits(repo, "pkgCommon")
    assert traversed(hits(repo, "pkgSales", "ripple"), "pkgCommon", 1, "PackageImport")


def test_decision_includes_concept_backward(repo):
    _model(repo)
    assert traversed(hits(repo, "ledger"), "optLedger", 1, "IncludesConcept")  # the Option depends on its concept
    assert "ledger" not in hits(repo, "optLedger")
    assert traversed(hits(repo, "optLedger", "ripple"), "ledger", 1, "IncludesConcept")


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
    family = ("Dependency", "Abstraction", "Realization", "InterfaceRealization", "Usage", "Deployment")
    got = {c: (ctx.nearest("https://meta.linked.archi/uml/onto#" + c, dep) or "").replace(core.AISEP, "") for c in family}
    assert set(got.values()) == {"Backward"}, got
    uml = {c: (ctx.nearest("https://meta.linked.archi/uml/onto#" + c, dep) or "").replace(core.AISEP, "")
           for c in ("Association", "Aggregation", "Composition", "Include", "Extend", "InformationFlow", "ControlFlow",
                     "ObjectFlow", "PackageImport", "PackageMerge")}
    assert uml == {"Association": "None", "Aggregation": "Backward", "Composition": "Both", "Include": "Backward",
                   "Extend": "Backward", "InformationFlow": "Forward", "ControlFlow": "Forward", "ObjectFlow": "Forward",
                   "PackageImport": "Backward", "PackageMerge": "Backward"}, uml
    assert (ctx.nearest("https://meta.linked.archi/arch-decision#IncludesConcept", dep) or "").endswith("Backward")
