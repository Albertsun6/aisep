"""模块合约：modules/** 声明的每个属性都要有 rdfs:domain（#67 后续，Albert 2026-11-27 定）。

#153 的 L1 定义域检查（Ctx.l1_property_domains）只强制模块文件里写出的 rdfs:domain；没声明定义域的模块属性
不受约束，可以借用到任意类型的元素上。这里把「声明了就有定义域」做成常驻检查：

1. 每个在模块文件（modules/<名>/*.ttl，不含 tests/ 下的夹具）里声明为 owl:ObjectProperty、owl:DatatypeProperty
   或 rdf:Property 的属性，至少有一条写在模块文件里的 rdfs:domain；owl:AnnotationProperty 是元模型注解，不在此列。
2. 定义域取值是 IRI，或 owl:unionOf 的 IRI 列表（「几类之一」，如 ddd:triggers）；其他空白节点 L1 认不出。
3. L1 对 owl:unionOf 定义域按「主语是其中任一类」判定，不跳过。
4. 检查本身会因篡改而失败：在临时副本里加一个不带定义域的属性，检查要报出它。

vendor/ 上游本体的定义域暂不强制（docs/decisions.md ADR-029）。
"""
import glob, os, shutil

import pyoxigraph as ox

from aisep import core
from conftest import ROOT

RDF, RDFS, OWL = core.NS["rdf"], core.NS["rdfs"], core.NS["owl"]
PROPERTY_KINDS = {OWL + "ObjectProperty", OWL + "DatatypeProperty", RDF + "Property"}
DDD = "https://aisep.example/ont/ddd#"


def module_files(root):
    return sorted(glob.glob(os.path.join(root, "modules", "*", "*.ttl")))


def domain_problems(root):
    """[(property, problem)] over every module file under root."""
    store = ox.Store()
    for f in module_files(root):
        store.load(path=f, format=ox.RdfFormat.TURTLE)
    declared = {r["p"].value for r in store.query(
        f"SELECT DISTINCT ?p WHERE {{ ?p a ?k VALUES ?k {{ {' '.join(f'<{k}>' for k in PROPERTY_KINDS)} }} FILTER(isIRI(?p)) }}")}
    domains = {}  # property -> {domain node: [union members]}
    for r in store.query(f"""SELECT ?p ?d ?m WHERE {{ ?p <{RDFS}domain> ?d
                             OPTIONAL {{ ?d <{OWL}unionOf>/<{RDF}rest>*/<{RDF}first> ?m }} }}"""):
        ms = domains.setdefault(r["p"].value, {}).setdefault(r["d"], [])
        if r["m"] is not None:
            ms.append(r["m"])
    bad = []
    for p in sorted(declared):
        if not domains.get(p):
            bad.append((p, "no rdfs:domain"))
        for d, ms in domains.get(p, {}).items():
            if not isinstance(d, ox.NamedNode) and (not ms or not all(isinstance(m, ox.NamedNode) for m in ms)):
                bad.append((p, "rdfs:domain is neither an IRI nor an owl:unionOf list of IRIs"))
    return bad


def test_every_module_property_declares_a_domain():
    assert domain_problems(ROOT) == []


def test_check_fails_on_a_planted_property_without_domain(tmp_path):
    shutil.copytree(os.path.join(ROOT, "modules"), tmp_path / "modules")
    with open(tmp_path / "modules" / "ddd" / "onto.ttl", "a", encoding="utf-8") as f:
        f.write("\nddd:probeNoDomain a owl:DatatypeProperty .\n"
                "ddd:probeBadDomain a owl:ObjectProperty ; rdfs:domain [ a owl:Class ] .\n")
    assert domain_problems(tmp_path) == [
        (DDD + "probeBadDomain", "rdfs:domain is neither an IRI nor an owl:unionOf list of IRIs"),
        (DDD + "probeNoDomain", "no rdfs:domain"),
    ]


MODEL = """@prefix arch: <https://meta.linked.archi/core#> .
@prefix ddd:  <https://aisep.example/ont/ddd#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix :     <https://aisep.example/model/probe/> .
:m a arch:Model ; skos:prefLabel "探针"@zh .
:subject a ddd:{kind} ; arch:inModel :m ; skos:prefLabel "主语"@zh .
:event a ddd:DomainEvent ; arch:inModel :m ; skos:prefLabel "事件"@zh .
:subject ddd:triggers :event .
"""


def _domain_violations(tmp_path, kind):
    f = tmp_path / f"{kind}.ttl"
    f.write_text(MODEL.replace("{kind}", kind), encoding="utf-8")
    ctx = core.Ctx(core.discover(), [str(f)])
    ctx.l1_property_domains()
    return [t for s, layer, t in ctx.problems if layer == "L1" and "has rdfs:domain" in t]


def test_union_domain_is_enforced(tmp_path):
    """ddd:triggers 的定义域是 owl:unionOf(ddd:DomainService ddd:Policy)：Policy 作主语不报，Entity 作主语报。
    （直写 ddd:triggers 另有「direct triple」违规，这里只看定义域这一条。）"""
    assert _domain_violations(tmp_path, "Policy") == []
    hits = _domain_violations(tmp_path, "Entity")
    assert len(hits) == 1 and "owl:unionOf(ddd:DomainService, ddd:Policy)" in hits[0], hits
