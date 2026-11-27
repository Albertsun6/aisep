"""model_list_views / model_render_view (docs/mcp-interface.md §5.15, §5.16): read-only views for the workbench.

The repo fixture (procurement) gets a C4 model `t` (modules/c4/tests/valid/dual-model-ok.ttl), a declared ArchiMate
view, a declared C4 view and a file of hostile labels. Expected sets come from model_query SPARQL or from the text the
test itself wrote, never from aisep/views.py; the viewpoint SVG is compared byte for byte with `tools/aisep.py diagram`.
Rendering needs elkjs (`npm ci --prefix tools/elk --ignore-scripts`); there is no skip: CI installs it."""
import os, re, shutil, subprocess, sys
from xml.etree import ElementTree

import anyio
import pytest
from mcp import Client, StdioServerParameters

from conftest import ROOT, commit_all
from aisep import diagram, server as S, tools as T

PY = sys.executable
P = "https://aisep.example/model/procurement/"
TM = "https://aisep.example/model/t/"
SVG_NS = "{http://www.w3.org/2000/svg}"
VIEW_MEMBERS = ["supplier", "submitQuotation", "quotation"]
HOSTILE = ['<script>alert(1)</script>', '" onload="alert(2)', "' onmouseover='alert(3)", ']]><script>alert(4)</script>',
           '<img src=x onerror=alert(5)>', '&lt;script&gt;', '<svg onload=alert(6)>', '<foreignObject><iframe/>']


def ttl_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"@zh'


@pytest.fixture
def vrepo(repo):
    os.makedirs(repo / "models" / "t")
    shutil.copy(os.path.join(ROOT, "modules", "c4", "tests", "valid", "dual-model-ok.ttl"), repo / "models" / "t" / "c4.ttl")
    with open(repo / "models" / "t" / "c4.ttl", "a", encoding="utf-8") as fh:
        fh.write("""
:view-c4Probe a arch:Diagram ; arch:inModel :t ; skos:prefLabel "C4 声明视图"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/c4/viewpoints#ContainerDiagram> .
:orderSys arch:inView :view-c4Probe . :orderDb arch:inView :view-c4Probe . :buyer arch:inView :view-c4Probe .
""")
    # the fixture names its model `:t` (= …/model/t/t); a model of this repository is …/model/t/ (models/t/)
    f = repo / "models" / "t" / "c4.ttl"
    f.write_text(re.sub(r"(?<![\w-]):t(?![\w-])", f"<{TM}>", f.read_text(encoding="utf-8")), encoding="utf-8")
    with open(repo / "models" / "procurement" / "am4.ttl", "a", encoding="utf-8") as fh:
        fh.write("""
:view-probe a arch:Diagram ; arch:inModel <https://aisep.example/model/procurement/> ; skos:prefLabel "探针视图"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/archimate4/viewpoints#LayeredViewpoint> .
""" + "".join(f":{x} arch:inView :view-probe .\n" for x in VIEW_MEMBERS))
    commit_all(repo, "views")
    return repo


def cfg(repo):
    return T.Config(allow_roots=(str(repo.parent),), repo=str(repo))


def call(repo, name, **args):
    r = S.call(cfg(repo), name, args)
    return r.is_error, r.structured_content


def ok(repo, name, **args):
    is_err, res = call(repo, name, **args)
    assert not is_err, res
    return res


def err(repo, name, **args):
    is_err, res = call(repo, name, **args)
    assert is_err, res
    return res["error"]


def rows(repo, sparql):
    res = ok(repo, "model_query", sparql=sparql)
    return {tuple(b[v]["value"] for v in res["variables"]) for b in res["rows"]}


def drawn(svg, kind="element"):
    return {m for m in re.findall(rf'data-kind="{kind}" data-iri="([^"]*)"', svg)}


# ---------------------------------------------------------------- listing

def test_list_views_declared_and_projections(vrepo):
    res = ok(vrepo, "model_list_views")
    by = {m["slug"]: m for m in res["models"]}
    assert set(by) == {"procurement", "t"}
    pv = by["procurement"]["views"]
    assert [(v["iri"], v["label"], v["notation"], v["memberCount"], v["render"]) for v in pv] == \
           [(P + "view-probe", "探针视图", "archimate", len(VIEW_MEMBERS), {"view": P + "view-probe"})]
    assert pv[0]["viewpoint"] == "https://meta.linked.archi/archimate4/viewpoints#LayeredViewpoint"
    tv = by["t"]["views"]
    assert [(v["iri"], v["notation"], v["memberCount"], v["viewpointLabel"]) for v in tv] == \
           [(TM + "view-c4Probe", "c4", 3, "容器图")]
    # ArchiMate projections: exactly the vendor viewpoints that admit a type some procurement element has (SPARQL)
    want = {vp.rsplit("#", 1)[1] for (vp,) in rows(vrepo, f"""SELECT DISTINCT ?vp WHERE {{ ?vp arch:includesConcept ?c .
        ?x arch:inModel <{P}> ; a ?c . FILTER NOT EXISTS {{ ?x arch:source ?s }} }}""")}
    got = {p["viewpoint"] for p in by["procurement"]["projections"] if p["notation"] == "archimate"}
    assert got == want and want
    # C4 projections of t: a context per (internal) software system, container/component diagrams where there is
    # something inside, one deployment view per environment
    systems = {x for (x,) in rows(vrepo, f"SELECT ?x WHERE {{ ?x a c4:SoftwareSystem ; arch:inModel <{TM}> }}")}
    envs = {e for (e,) in rows(vrepo, f"SELECT DISTINCT ?e WHERE {{ ?n <https://meta.linked.archi/c4/structurizr#environment> ?e ; arch:inModel <{TM}> }}")}
    c4 = {(p["viewpoint"], p["scope"]) for p in by["t"]["projections"] if p["notation"] == "c4"}
    assert {s for v, s in c4 if v == "SystemContext"} == systems
    assert {s for v, s in c4 if v == "C4Deployment"} == envs and envs
    assert ("ContainerDiagram", TM + "orderSys") in c4 and ("ComponentDiagram", TM + "orderApi") in c4
    # every listed item renders with its own `render` args, and the counts agree with the rendered SVG
    for m in res["models"]:
        for item in m["views"] + m["projections"]:
            r = ok(vrepo, "model_render_view", **item["render"])
            if "elementCount" in item:
                assert (r["elementCount"], r["relationshipCount"]) == (item["elementCount"], item["relationshipCount"]), item
            assert r["elementCount"] == len(drawn(r["svg"])) and r["relationshipCount"] == len(drawn(r["svg"], "relationship"))


def test_list_views_one_model_and_ref(vrepo):
    res = ok(vrepo, "model_list_views", model="procurement", ref="main")
    assert [m["slug"] for m in res["models"]] == ["procurement"] and res["source"]["commit"]
    assert err(vrepo, "model_list_views", model="nope")["code"] == "MODEL_NOT_FOUND"


# ---------------------------------------------------------------- the three render entries

def test_render_declared_view(vrepo):
    r = ok(vrepo, "model_render_view", view="procurement:view-probe")
    assert r["title"] == "探针视图" and r["notation"] == "archimate"
    assert drawn(r["svg"]) == {P + x for x in VIEW_MEMBERS}
    vals = " ".join(f"<{P}{x}>" for x in VIEW_MEMBERS)
    want = {x for (x,) in rows(vrepo, f"""SELECT ?r WHERE {{ ?r arch:source ?s ; arch:target ?t .
        VALUES ?s {{ {vals} }} VALUES ?t {{ {vals} }} FILTER(?s != ?t) }}""")}
    assert drawn(r["svg"], "relationship") == want and want
    c4 = ok(vrepo, "model_render_view", view=TM + "view-c4Probe")
    assert c4["notation"] == "c4" and drawn(c4["svg"]) == {TM + "orderDb", TM + "buyer"}
    assert 'data-kind="boundary" data-iri="' + TM + 'orderSys"' in c4["svg"]


def test_render_viewpoint_is_the_cli_svg_byte_for_byte(vrepo, tmp_path):
    out = tmp_path / "cli.svg"
    p = subprocess.run([PY, "tools/aisep.py", "diagram", "--viewpoint", "LayeredViewpoint", "--model", "procurement",
                        "-o", str(out)], cwd=vrepo, capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stdout + p.stderr
    r = ok(vrepo, "model_render_view", viewpoint="LayeredViewpoint", model="procurement")
    assert r["svg"] == out.read_text(encoding="utf-8")
    assert r["elementCount"] == int(re.search(r"elements=(\d+)", p.stdout).group(1))


def test_render_c4_viewpoints(vrepo):
    r = ok(vrepo, "model_render_view", c4viewpoint="SystemContext", of="t:orderSys")
    down = "(c4:hasContainer|c4:hasComponent)*"
    want = {TM + "orderSys"} | {x for (x,) in rows(vrepo, f"""SELECT DISTINCT ?x WHERE {{ <{TM}orderSys> {down} ?a .
        {{ ?a c4:uses ?b }} UNION {{ ?b c4:uses ?a }} ?x {down} ?b .
        VALUES ?ty {{ c4:Person c4:ExternalPerson c4:SoftwareSystem c4:ExternalSoftwareSystem }} ?x a ?ty
        FILTER(?x != <{TM}orderSys>) }}""")}
    assert drawn(r["svg"]) == want and len(want) > 1
    assert r["title"] == "系统上下文图：订单管理系统"
    d = ok(vrepo, "model_render_view", c4viewpoint="C4Deployment", of="Production", model="t")
    assert d["elementCount"] >= 1 and 'data-kind="deployment-node"' in d["svg"]


def test_render_is_deterministic_and_reads_only(vrepo):
    from test_server import tree_digest
    before = tree_digest(vrepo)
    for args in ({"view": P + "view-probe"}, {"viewpoint": "LayeredViewpoint", "model": "procurement"},
                 {"c4viewpoint": "ContainerDiagram", "of": TM + "orderSys"}):
        a, b = ok(vrepo, "model_render_view", **args), ok(vrepo, "model_render_view", **args)
        assert a["svg"].encode() == b["svg"].encode()
    assert tree_digest(vrepo) == before


def test_registered_for_workbench_and_agent_over_stdio(vrepo):
    async def go(profile):
        p = StdioServerParameters(command=PY, args=["-m", "aisep.server", "--repo", str(vrepo), "--allow-root",
                                                    str(vrepo.parent), "--profile", profile],
                                  cwd=str(vrepo), env=dict(os.environ, PYTHONPATH=ROOT))
        async with Client(p) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            r = await c.call_tool("model_render_view", {"view": "procurement:view-probe"})
            return names, r
    for profile in ("workbench", "agent"):
        names, r = anyio.run(go, profile)
        assert {"model_list_views", "model_render_view"} <= names
        assert not r.is_error and r.structured_content["svg"].startswith("<svg ")
        assert "<svg" not in r.content[0].text  # the text summary never carries the SVG


# ---------------------------------------------------------------- errors

@pytest.mark.parametrize("args, code, field", [
    ({}, "INVALID_ARGUMENT", "view"),
    ({"view": "procurement:view-probe", "viewpoint": "LayeredViewpoint"}, "INVALID_ARGUMENT", "viewpoint"),
    ({"view": "procurement:view-probe", "model": "procurement"}, "INVALID_ARGUMENT", "model"),
    ({"viewpoint": "LayeredViewpoint"}, "INVALID_ARGUMENT", "model"),
    ({"viewpoint": "Layered Viewpoint", "model": "procurement"}, "INVALID_ARGUMENT", "viewpoint"),  # schema pattern
    ({"viewpoint": "NoSuchViewpoint", "model": "procurement"}, "INVALID_ARGUMENT", "viewpoint"),
    ({"viewpoint": "LayeredViewpoint", "model": "nope"}, "MODEL_NOT_FOUND", None),
    ({"c4viewpoint": "SystemContext"}, "INVALID_ARGUMENT", "of"),
    ({"c4viewpoint": "Context", "of": "t:orderSys"}, "INVALID_ARGUMENT", "c4viewpoint"),  # schema enum
    ({"c4viewpoint": "SystemContext", "of": "t:orderSys", "model": "t"}, "INVALID_ARGUMENT", "model"),
    ({"c4viewpoint": "SystemContext", "of": "t:orderApi"}, "INVALID_ARGUMENT", "of"),  # a container, not a system
    ({"c4viewpoint": "SystemContext", "of": "t:noSuch"}, "ELEMENT_NOT_FOUND", "of"),
    ({"c4viewpoint": "C4Deployment", "of": 'Production" } #'}, "INVALID_ARGUMENT", "of"),
    ({"c4viewpoint": "C4Deployment", "of": "Nowhere"}, "INVALID_ARGUMENT", "of"),
    ({"view": "procurement:noSuch"}, "ELEMENT_NOT_FOUND", "view"),
    ({"view": "procurement:supplier"}, "INVALID_ARGUMENT", "view"),  # a member, not an arch:Diagram
    ({"view": "<urn:x y>"}, "INVALID_ARGUMENT", "view"),
    ({"view": "procurement:view-probe", "ref": "no-such-ref"}, "REF_NOT_FOUND", None),
])
def test_render_errors(vrepo, args, code, field):
    e = err(vrepo, "model_render_view", **args)
    assert e["code"] == code, e
    if field:
        assert field in e["details"]["rejectedFields"], e


def test_renderer_unavailable_is_an_error_not_a_partial_svg(vrepo, monkeypatch, tmp_path):
    monkeypatch.setattr(diagram, "ELK_DIR", str(tmp_path))  # no node_modules/elkjs there
    e = err(vrepo, "model_render_view", view="procurement:view-probe")
    assert (e["code"], e["details"]["reason"], e["retryable"]) == ("RENDERER_UNAVAILABLE", "elkjs-missing", False)
    assert "svg" not in e and "npm ci" in e["hint"]
    monkeypatch.undo()
    bindir = tmp_path / "bin"  # elkjs present, node not on PATH (git still is: the tool reads the repository)
    bindir.mkdir()
    os.symlink(shutil.which("git"), bindir / "git")
    monkeypatch.setenv("PATH", str(bindir))
    for args in ({"view": "procurement:view-probe"}, {"c4viewpoint": "SystemContext", "of": "t:orderSys"}):
        e = err(vrepo, "model_render_view", **args)
        assert (e["code"], e["details"]["reason"]) == ("RENDERER_UNAVAILABLE", "node-missing")


def test_parse_failure_draws_nothing(vrepo):
    with open(vrepo / "models" / "procurement" / "broken.ttl", "w", encoding="utf-8") as fh:
        fh.write(":x a <oops .\n")
    for name, args in (("model_render_view", {"view": "procurement:view-probe"}), ("model_list_views", {})):
        e = err(vrepo, name, **args)
        assert e["code"] == "PARSE_FAILED" and e["details"]["files"] == ["models/procurement/broken.ttl"]


# ---------------------------------------------------------------- SVG safety: model text is only ever text

def _hostile_repo(vrepo):
    lines = ["@prefix skos: <http://www.w3.org/2004/02/skos/core#> .", "@prefix arch: <https://meta.linked.archi/core#> .",
             "@prefix am4: <https://meta.linked.archi/archimate4/onto#> .", "@prefix c4: <https://meta.linked.archi/c4/onto#> .",
             f"@prefix : <{P}> ."]
    for i, h in enumerate(HOSTILE):
        lines.append(f":evil{i} a am4:Role ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(h)} ; skos:definition {ttl_str(h)} ;"
                     f" arch:inView :view-evil .")
        if i:
            lines.append(f":rel-evil{i} a am4:Association ; arch:inModel <{P}> ; arch:source :evil{i - 1} ; arch:target :evil{i} .")
    lines.append(f":view-evil a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(HOSTILE[0] + HOSTILE[1])} .")
    with open(vrepo / "models" / "procurement" / "evil.ttl", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(vrepo / "models" / "t" / "c4.ttl", "a", encoding="utf-8") as fh:
        for i, h in enumerate(HOSTILE):
            fh.write(f":evilSys{i} a c4:ExternalSoftwareSystem ; arch:inModel <{TM}> ; skos:prefLabel {ttl_str(h)} ;"
                     f" skos:definition {ttl_str(h)} .\n"
                     f":rel-evil-uses{i} a c4:Using ; arch:inModel <{TM}> ; arch:source :orderSys ; arch:target :evilSys{i} ;"
                     f" skos:prefLabel {ttl_str(h)} ; c4:technology {ttl_str(h)} .\n")
    return vrepo


def assert_inert(svg):
    root = ElementTree.fromstring(svg)  # well-formed XML: nothing escaped its text node or attribute
    text = []
    for el in root.iter():
        tag = el.tag.replace(SVG_NS, "")
        assert tag not in ("script", "foreignObject", "iframe", "img", "a", "use", "image", "animate", "set"), tag
        for k, v in el.attrib.items():
            assert not k.lower().startswith("on") and "href" not in k.lower(), (tag, k)
            assert not v.strip().lower().startswith("javascript:"), (tag, k, v)
        text.append(el.text or "")
    return "".join(text)


def test_hostile_labels_are_inert_text(vrepo):
    r = _hostile_repo(vrepo)
    am = ok(r, "model_render_view", view="procurement:view-evil")
    shown = assert_inert(am["svg"])
    assert am["elementCount"] == len(HOSTILE) and "<script>alert(1)</script>" in shown  # drawn, as text
    assert '" onload="alert(2)' in am["title"] and "<script" not in am["svg"].replace("&lt;script", "")
    c4 = ok(r, "model_render_view", c4viewpoint="SystemContext", of="t:orderSys")
    shown = assert_inert(c4["svg"])
    assert "' onmouseover='alert(3)" in shown and "<script" not in c4["svg"].replace("&lt;script", "")
    listed = ok(r, "model_list_views", model="procurement")
    assert any(v["iri"] == P + "view-evil" for v in listed["models"][0]["views"])
