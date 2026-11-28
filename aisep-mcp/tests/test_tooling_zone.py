"""ADR-030 / issue #169: tool zone (aisep:toolingLoads, Ctx.tool_store) versus domain zone (Ctx.store).

Regression 1: on one snapshot, a Ctx of all modules and one without ext-actions see the same domain (G7 declared
predicates, the write tools' class table, supers, uf, Gates, the impact dependency table, model_query samples,
shape_hits, the L3 domain runs). Regression 2: a wide domain shape (sh:targetSubjectsOf skos:prefLabel) never focuses
an action or catalogue node. Regression 3: model files using tool-zone terms fail L1 with tooling-term-in-model, and
the write tools cannot instantiate aisep:ActionType. (Regression 4, check 9, is in test_merge_check_negatives.py.)
"""
import collections, glob, os, re

import pytest

from aisep import core, tools, write_tools
from aisep.errors import AisepError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = sorted(glob.glob(os.path.join(ROOT, "models", "**", "*.ttl"), recursive=True))
AI = core.AISEP
TOOL_RULE = "tooling-term-in-model"


def full_mods():
    return core.discover(ROOT)


def bare_mods():
    return [m for m in core.discover(ROOT) if m.name != "ext-actions"]


def _norm(v):
    """Blank-node labels differ between two parses: compare them as one placeholder."""
    if isinstance(v, dict):
        return {k: ("_" if isinstance(x, dict) and x.get("type") == "bnode" else _norm(x)) for k, x in v.items()}
    if isinstance(v, list):
        return sorted((_norm(x) for x in v), key=repr)
    return v


QUERIES = ["SELECT (COUNT(*) AS ?n) WHERE { ?s skos:prefLabel ?l }",
           "SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c a owl:Class }",
           "SELECT ?s ?p WHERE { ?s ?p am4:Aggregation }"]


def domain_view(ctx):
    values = " ".join(f"<{k}>" for k in core.PROPERTY_DECL)
    g7 = {p for (p,) in ctx.rows(f"""SELECT DISTINCT ?p WHERE {{ GRAPH ?g {{ ?p a ?k }} {ctx.onto_graph_filter()}
                                     VALUES ?k {{ {values} }} }}""")}
    gates = {g for (g,) in ctx.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x skos:inScheme aisep:Gates }} {ctx.onto_graph_filter()} }}")}
    dep = dict(ctx.rows(f"SELECT ?c ?d WHERE {{ GRAPH ?g {{ ?c aisep:dependency ?d }} {ctx.onto_graph_filter()} }}"))
    hits = collections.Counter((s, sev, msg, tuple(sorted((k, "_" if isinstance(v, core.ox.BlankNode) else v.value)
                                                          for k, v in b.items()))) for s, sev, msg, b in ctx.shape_hits())
    iris = lambda xs: collections.Counter(x if ":" in x else "_" for x in xs)  # a blank-node label has no ":"
    return {"g7": iris(g7), "classes": iris(write_tools._classes(ctx)), "supers": {k: frozenset(v) for k, v in ctx.supers.items()},
            "uf": dict(ctx.uf), "gates": iris(gates), "dep": dep, "hits": hits,
            "query": [_norm(tools._run_query(ctx, q, 100000, 60)["rows"]) for q in QUERIES]}


def l3_domain(ctx):
    core.l3(ctx)
    return collections.Counter(p for p in ctx.problems if p[1] == "L3" and not p[2].startswith("[ext-actions]"))


def test_1_domain_is_the_same_with_and_without_ext_actions():
    full, bare = core.Ctx(full_mods(), SOURCES), core.Ctx(bare_mods(), SOURCES)
    ea = next(m for m in full.mods if m.name == "ext-actions")
    assert {os.path.basename(f) for f in ea.tooling} == {"onto.ttl", "catalog.ttl"}  # not vacuous: the zone exists
    assert any(q.object.value == AI + "ActionType" for q in full.tool_store.quads_for_pattern(None, None, None))
    # each tool file is its own graph urn:aisep:tool:<repository path> (#169 item 2; #198 review)
    assert {q.graph_name.value for q in full.tool_store.quads_for_pattern(None, None, None)} == \
        {core.TOOL_G + full.rel(f) for f in ea.tooling}
    assert not set(ea.tooling) & set(core.onto_files(full.mods, "all") + core.onto_files(full.mods, "hub")
                                     + core.onto_files(full.mods, "none"))
    a, b = domain_view(full), domain_view(bare)
    for k in a:
        assert a[k] == b[k], k
    assert l3_domain(full) == l3_domain(bare)


def test_1_onto_files_drops_a_tool_file_a_manifest_also_loads():
    """The tool filter holds even when a manifest lists the same file under aisep:loads too (#198 review)."""
    mods = full_mods()
    ea = next(m for m in mods if m.name == "ext-actions")
    cat = next(f for f in ea.tooling if f.endswith("catalog.ttl"))
    ea.loads = ea.loads + [cat]
    for scope in ("all", "hub", "none"):
        assert cat not in core.onto_files(mods, scope), scope


WIDE = """@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<urn:test:WideProbe> a sh:NodeShape ; sh:targetSubjectsOf skos:prefLabel ;
    sh:property [ sh:path skos:prefLabel ; sh:maxCount 0 ; sh:severity sh:Info ; sh:message "wide-probe" ] .
"""


def test_2_wide_domain_shape_never_focuses_tool_nodes(tmp_path):
    shp = tmp_path / "wide.ttl"
    shp.write_text(WIDE, encoding="utf-8")
    mods = full_mods()
    runs = {"am4+core"} | {m.name for m in mods if m.shapes and m.name not in core.HUB_MODULES and m.name != "ext-actions"}
    assert {"ddd", "ext-governance"} <= runs  # not vacuous: several per-module domain runs
    for m in mods:  # every domain run: the hub run and each per-module run except the one declaring the tool zone
        if m.shapes and m.name != "ext-actions":
            m.shapes = m.shapes + [str(shp)]
    ctx = core.Ctx(mods, SOURCES)
    core.l3(ctx)
    focus = collections.defaultdict(set)
    for _, layer, text in ctx.problems:
        if layer == "L3" and text.endswith("wide-probe"):
            run, f = re.match(r"^\[([^\]]+)\] (\S+)", text).groups()
            focus[run].add(f)
    assert set(focus) == runs, focus
    tool = {core.short(q.subject.value) for q in ctx.tool_store.quads_for_pattern(None, None, None)
            if isinstance(q.subject, core.ox.NamedNode)}
    assert "aisep:ActionRemoveElement" in tool and "aisep:ActionType" in tool
    for run, fs in focus.items():
        assert any(f.startswith("procurement:") for f in fs), run  # the probe did run over the model
        assert not fs & tool, (run, sorted(fs & tool))


HDR = """@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/t/> .
:t a arch:Model ; skos:prefLabel "测试模型"@zh .
:boss a arch:Stakeholder ; arch:inModel :t ; skos:prefLabel "架构师"@zh .
"""
CASES = {
    "subject": ('aisep:ActionRemoveElement skos:prefLabel "伪造"@zh .', None, "subject"),
    "typed-action": (':x a aisep:ActionType ; arch:inModel :t ; skos:prefLabel "伪动作"@zh .', "x", "rdf:type object"),
    "blank-action": ('[] a aisep:ActionType ; aisep:steps [ a aisep:ActionStep ; aisep:invokes aisep:BasicRemove ] .',
                     None, "rdf:type object"),
    "argument-on-element": (':x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh ; aisep:argument "k" .',
                            "x", "predicate"),
    "approves-action": (''':x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .
:recMeta a aisep:ApprovalRecord ; arch:inModel :t ; skos:prefLabel "记录 recMeta"@zh ;
    aisep:gate aisep:GateArchitecture ; aisep:decision aisep:DecisionApproved ; aisep:approvedBy :boss ;
    aisep:approves aisep:ActionRemoveElement ;
    aisep:evidence "89abcdef0123456789abcdef0123456789abcdef" ; prov:generatedAtTime "2026-11-20T12:00:00Z"^^xsd:dateTime .''',
                        "recMeta", "aisep:approves object"),
}


def _l1(tmp_path, body):
    f = tmp_path / "m.ttl"
    f.write_text(HDR + body + "\n", encoding="utf-8")
    ctx = core.Ctx(full_mods(), [str(f)])
    assert not [p for p in ctx.problems if p[1] == "L0"]
    core.run_check(ctx)
    return ctx


def test_3_control_model_has_no_tooling_finding(tmp_path):
    ctx = _l1(tmp_path, ':x a am4:ApplicationComponent ; arch:inModel :t ; skos:prefLabel "组件"@zh .')
    assert not [i for i in ctx.instances if i[0] == "Violation" and i[1] == "L1"], ctx.problems


@pytest.mark.parametrize("case", sorted(CASES))
def test_3_model_using_tool_terms_fails_l1_by_rule(tmp_path, case):
    body, who, where = CASES[case]
    ctx = _l1(tmp_path, body)
    hits = [i for i in ctx.instances if i[0] == "Violation" and i[1] == "L1" and i[4] == TOOL_RULE]
    assert hits and all(TOOL_RULE in i[2] for i in hits), ctx.problems
    assert any(f"used as {where}" in i[2] for i in hits), [i[2] for i in hits]
    if who:  # focus is the model subject using the term (a stable instance key for the write tools)
        assert any(i[3] == "https://aisep.example/model/t/" + who for i in hits if f"used as {where}" in i[2]), hits


def test_3_tool_term_the_domain_also_declares_is_not_a_tooling_term(tmp_path):
    """A tool-zone IRI that the domain zone declares too is a domain term: using it in a model is no
    tooling-term-in-model finding (#198 review). Twin: the same model without the domain declaration is one."""
    body = CASES["argument-on-element"][0]
    f = tmp_path / "m.ttl"
    f.write_text(HDR + body + "\n", encoding="utf-8")
    for declared in (True, False):
        ctx = core.Ctx(full_mods(), [str(f)])
        if declared:
            ctx.store.add(core.ox.Quad(core.ox.NamedNode(AI + "argument"), core.ox.NamedNode(core.A),
                                       core.ox.NamedNode(core.NS["owl"] + "DatatypeProperty"),
                                       core.ox.NamedNode(core.ONTO_G + "modules/aisep-core/onto.ttl")))
        core.run_check(ctx)
        hits = [i for i in ctx.instances if i[1] == "L1" and i[4] == TOOL_RULE]
        assert bool(hits) != declared, (declared, hits)


def test_3_write_tools_cannot_instantiate_action_type():
    ctx = core.Ctx(full_mods(), SOURCES)
    assert AI + "ActionType" not in write_tools._classes(ctx)
    with pytest.raises(AisepError) as e:
        write_tools._resolve_class(ctx, "aisep:ActionType")
    assert e.value.code == "UNKNOWN_TYPE"
