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
            assert r["notation"] == item["notation"], item
            if "elementCount" in item:
                assert (r["elementCount"], r["relationshipCount"]) == (item["elementCount"], item["relationshipCount"]), item
            if r["notation"] in ("archimate", "c4", "uml"):  # DDD and BPMN counts: test_render_is_the_cli_output_*
                assert r["elementCount"] == len(drawn(r["svg"])) and r["relationshipCount"] == len(drawn(r["svg"], "relationship"))
            ElementTree.fromstring((r["svg"] if r["format"] == "svg" else r["content"]).encode())  # well-formed (strict)


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


def cli(repo, out, *args):
    """The checkout's CLI (its elkjs) on the fixture repo's model files: (process, SVG text or None)."""
    fs = sorted(str(f) for f in (repo / "models").rglob("*.ttl"))
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "aisep.py"), "diagram", *args, "-o", str(out), *fs], cwd=repo,
                       capture_output=True, text=True, timeout=600)
    return p, (out.read_text(encoding="utf-8") if out.exists() else None)


@pytest.mark.parametrize("args, cli_args", [
    ({"viewpoint": "LayeredViewpoint", "model": "procurement"}, ["--viewpoint", "LayeredViewpoint", "--model", "procurement"]),
    ({"view": "procurement:view-probe"}, ["--view", "procurement:view-probe"]),  # declared ArchiMate view
    ({"view": "t:view-c4Probe"}, ["--view", "t:view-c4Probe"]),  # declared C4 view
    ({"c4viewpoint": "SystemContext", "of": "t:orderSys"}, ["--viewpoint", "SystemContext", "--of", "t:orderSys"]),
    ({"c4viewpoint": "C4Deployment", "of": "Production", "model": "t"},
     ["--viewpoint", "C4Deployment", "--of", "Production", "--model", "t"]),
])
def test_render_is_the_cli_svg_byte_for_byte(vrepo, tmp_path, args, cli_args):
    p, svg = cli(vrepo, tmp_path / "cli.svg", *cli_args)
    assert p.returncode == 0, p.stdout + p.stderr
    r = ok(vrepo, "model_render_view", **args)
    assert r["svg"].encode() == svg.encode()
    assert r["elementCount"] == int(re.search(r"elements=(\d+)", p.stdout).group(1)) > 0


def test_view_in_several_models_takes_the_first_by_iri_in_both(vrepo, tmp_path):
    # a view with two arch:inModel (an L1 problem, but L0 is all the view tools need): tool and CLI both take the
    # model IRIs sorted, first one (procurement < t). Its members are procurement elements, so taking `t` draws nothing
    with open(vrepo / "models" / "t" / "c4.ttl", "a", encoding="utf-8") as fh:
        fh.write(f"<{P}view-probe> arch:inModel <{TM}> .\n")
    assert sorted(m for (m,) in rows(vrepo, f"SELECT ?m WHERE {{ <{P}view-probe> arch:inModel ?m }}")) == [P, TM]
    p, svg = cli(vrepo, tmp_path / "cli.svg", "--view", "procurement:view-probe")
    assert p.returncode == 0, p.stdout + p.stderr
    r = ok(vrepo, "model_render_view", view="procurement:view-probe")
    assert drawn(r["svg"]) == {P + x for x in VIEW_MEMBERS} and r["svg"].encode() == svg.encode()



def test_c4_view_in_several_models_takes_the_first_by_iri_in_both(vrepo, tmp_path):
    # the C4 twin of the test above: the declared C4 view also put in procurement, which sorts before t. Both take
    # procurement, which has no C4 element, so the tool draws nothing and the CLI refuses naming procurement; taking
    # the last model (t) would draw the view's members orderDb and buyer
    with open(vrepo / "models" / "procurement" / "am4.ttl", "a", encoding="utf-8") as fh:
        fh.write(f"<{TM}view-c4Probe> arch:inModel <{P}> .\n")
    assert sorted(m for (m,) in rows(vrepo, f"SELECT ?m WHERE {{ <{TM}view-c4Probe> arch:inModel ?m }}")) == [P, TM]
    r = ok(vrepo, "model_render_view", view="t:view-c4Probe")
    assert r["notation"] == "c4" and r["elementCount"] == 0 and not drawn(r["svg"]), r["warnings"]
    p, svg = cli(vrepo, tmp_path / "cli.svg", "--view", "t:view-c4Probe")
    assert p.returncode == 1 and f"no C4 element of {P} " in p.stdout and svg is None, p.stdout + p.stderr

def test_empty_view_tool_draws_title_and_legend_cli_refuses(vrepo, tmp_path):
    with open(vrepo / "models" / "procurement" / "am4.ttl", "a", encoding="utf-8") as fh:
        fh.write(f':view-empty a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel "空视图"@zh .\n')
    r = ok(vrepo, "model_render_view", view="procurement:view-empty")
    assert r["elementCount"] == 0 and "视图里没有元素" in r["warnings"] and not drawn(r["svg"])
    ElementTree.fromstring(r["svg"])
    p, svg = cli(vrepo, tmp_path / "cli.svg", "--view", "procurement:view-empty")
    assert p.returncode == 1 and "[Violation]" in p.stdout and svg is None


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
        p = StdioServerParameters(command=PY, args=["-P", "-m", "aisep.server", "--repo", str(vrepo), "--allow-root",
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
    ({"view": "procurement:" + "x" * 2040}, "INVALID_ARGUMENT", "view"),  # schema maxLength 2048
    ({"c4viewpoint": "SystemContext", "of": "t:" + "x" * 2047}, "INVALID_ARGUMENT", "of"),
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


def _fake_elk(tmp_path, script):
    d = tmp_path / "elk"
    (d / "node_modules" / "elkjs").mkdir(parents=True)
    (d / "layout.cjs").write_text(script, encoding="utf-8")
    return str(d)


@pytest.mark.parametrize("args", [{"view": "procurement:view-probe"}, {"c4viewpoint": "SystemContext", "of": "t:orderSys"},
                                  {"view": "t:view-c4Probe"}])
def test_layout_timeout_and_garbage_are_renderer_unavailable(vrepo, monkeypatch, tmp_path, args):
    # ELK printing something that is not JSON (a JSONDecodeError, a ValueError: it must not read as INVALID_ARGUMENT,
    # on the C4 path no more than on the ArchiMate one), and ELK not finishing in time (not INTERNAL)
    monkeypatch.setattr(diagram, "ELK_DIR", _fake_elk(tmp_path, 'process.stdout.write("not json");\n'))
    e = err(vrepo, "model_render_view", **args)
    assert (e["code"], e["details"]["reason"], e["retryable"]) == ("RENDERER_UNAVAILABLE", "layout-failed", False), e
    monkeypatch.setattr(diagram, "ELK_DIR", _fake_elk(tmp_path / "slow", "setTimeout(() => {}, 30000);\n"))
    monkeypatch.setattr(diagram, "ELK_TIMEOUT", 1)
    e = err(vrepo, "model_render_view", **args)
    assert (e["code"], e["details"]["reason"], e["retryable"]) == ("RENDERER_UNAVAILABLE", "layout-timeout", False), e


def test_parse_failure_draws_nothing(vrepo):
    with open(vrepo / "models" / "procurement" / "broken.ttl", "w", encoding="utf-8") as fh:
        fh.write(":x a <oops .\n")
    for name, args in (("model_render_view", {"view": "procurement:view-probe"}), ("model_list_views", {})):
        e = err(vrepo, name, **args)
        assert e["code"] == "PARSE_FAILED" and e["details"]["files"] == ["models/procurement/broken.ttl"]



@pytest.mark.parametrize("module, args", [(diagram, {"view": "procurement:view-probe"}),
                                          ("c4", {"c4viewpoint": "SystemContext", "of": "t:orderSys"})])
def test_other_renderer_value_error_is_internal_not_text_not_xml(vrepo, monkeypatch, module, args):
    # only check_xml_text's refusal (diagram.TextNotXml) reads as the caller's text-not-xml; any other ValueError
    # inside a renderer is a bug of ours and stays INTERNAL
    from aisep import diagram_c4
    mod = diagram_c4 if module == "c4" else module

    def boom(*a):
        raise ValueError("renderer bug")
    monkeypatch.setattr(mod, "render", boom)
    e = err(vrepo, "model_render_view", **args)
    assert e["code"] == "INTERNAL" and "renderer bug" in e["message"], e
    assert issubclass(diagram.TextNotXml, ValueError)

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


def test_text_xml_cannot_carry_is_refused_not_drawn(vrepo, tmp_path):
    # U+0001 in a label (Turtle escape \u0001): no escape can put it into XML 1.0. Refused like the write tools refuse
    # control characters, in the tool and in the CLI alike; tab and newline are XML characters and still render
    with open(vrepo / "models" / "procurement" / "am4.ttl", "a", encoding="utf-8") as fh:
        fh.write(f':ctrl a am4:Role ; arch:inModel <{P}> ; skos:prefLabel "坏\\u0001字"@zh ; arch:inView :view-ctrl .\n'
                 f':tabbed a am4:Role ; arch:inModel <{P}> ; skos:prefLabel "制\\t表\\n换行"@zh ; arch:inView :view-ok .\n'
                 f':view-ctrl a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel "控制字符"@zh .\n'
                 f':view-ok a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel "制表换行"@zh .\n')
    with open(vrepo / "models" / "t" / "c4.ttl", "a", encoding="utf-8") as fh:
        fh.write(f'<{TM}ctrlSys> a c4:ExternalSoftwareSystem ; arch:inModel <{TM}> ; skos:prefLabel "外\\u0001部"@zh .\n'
                 f'<{TM}rel-ctrl> a c4:Using ; arch:inModel <{TM}> ; arch:source <{TM}orderSys> ; arch:target <{TM}ctrlSys> .\n')
    assert "\x01" in {x for (x,) in rows(vrepo, f"SELECT ?l WHERE {{ <{P}ctrl> skos:prefLabel ?l }}")}.pop()
    for args, field in (({"view": "procurement:view-ctrl"}, "view"), ({"c4viewpoint": "SystemContext", "of": "t:orderSys"}, "of")):
        e = err(vrepo, "model_render_view", **args)
        assert (e["code"], e["details"]["reason"], e["details"]["rejectedFields"]) == ("INVALID_ARGUMENT", "text-not-xml", [field]), e
        assert "U+0001" in e["message"]
    p, svg = cli(vrepo, tmp_path / "cli.svg", "--view", "procurement:view-ctrl")
    assert p.returncode == 1 and "U+0001" in p.stdout and svg is None, p.stdout + p.stderr
    r = ok(vrepo, "model_render_view", view="procurement:view-ok")
    root = ElementTree.fromstring(r["svg"])  # strict parse
    assert r["elementCount"] == 1 and any("制" in (el.text or "") for el in root.iter())


# ---------------------------------------------------------------- BPMN, UML, DDD (the CLI's other renderers)

BPMN_NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
UML_VIEW = f"""
:view-umlProbe a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel "UML 声明视图"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/uml/viewpoints#ClassDiagram> .
:QuotationEntity arch:inView :view-umlProbe .
:view-uc a arch:Diagram ; arch:inModel <{P}> ; skos:prefLabel "用例图"@zh ;
    arch:viewConformsToViewpoint <https://meta.linked.archi/uml/viewpoints#UseCaseDiagram> .
:QuotationEntity arch:inView :view-uc .
"""


@pytest.fixture
def nrepo(vrepo):
    with open(vrepo / "models" / "procurement" / "uml.ttl", "a", encoding="utf-8") as fh:
        fh.write(UML_VIEW)
    commit_all(vrepo, "uml views")
    return vrepo


def test_list_views_bpmn_uml_ddd(nrepo):
    m = ok(nrepo, "model_list_views", model="procurement")["models"][0]
    views = {v["iri"]: v for v in m["views"]}
    assert (views[P + "view-umlProbe"]["notation"], views[P + "view-umlProbe"]["viewpointLabel"],
            views[P + "view-umlProbe"]["memberCount"]) == ("uml", "UML 类图", 1)
    assert views[P + "view-uc"]["notation"] == "uml" and views[P + "view-probe"]["notation"] == "archimate"
    proj = [p for p in m["projections"] if p["notation"] in ("bpmn", "uml", "ddd")]
    # after ArchiMate and C4, in this order: BPMN processes, UML class diagram, DDD context map then aggregate diagrams
    assert [p["notation"] for p in m["projections"]][-len(proj):] == [p["notation"] for p in proj]
    assert [p["notation"] for p in proj] == sorted((p["notation"] for p in proj), key=["bpmn", "uml", "ddd"].index)
    procs = {x for (x,) in rows(nrepo, f"SELECT ?x WHERE {{ ?x a bpmn:Process ; arch:inModel <{P}> }}")}
    nodes = rows(nrepo, f"""SELECT ?p ?n WHERE {{ ?p a bpmn:Process ; arch:inModel <{P}> ; bpmn:flowElements ?n .
        FILTER NOT EXISTS {{ ?n a bpmn:SequenceFlow }} }}""")
    flows = rows(nrepo, f"SELECT ?p ?n WHERE {{ ?p a bpmn:Process ; arch:inModel <{P}> ; bpmn:flowElements ?n . ?n a bpmn:SequenceFlow }}")
    got = {p["render"]["process"]: p for p in proj if p["notation"] == "bpmn"}
    assert set(got) == procs and procs
    for x, p in got.items():
        assert (p["scope"], p["elementCount"], p["relationshipCount"]) == \
               (x, sum(1 for q, _ in nodes if q == x), sum(1 for q, _ in flows if q == x))
    classes = {x for (x,) in rows(nrepo, f"SELECT ?x WHERE {{ ?x a uml:Class ; arch:inModel <{P}> }}")}
    assert [(p["render"], p["elementCount"]) for p in proj if p["notation"] == "uml"] == \
           [({"umldiagram": "ClassDiagram", "model": "procurement"}, len(classes))] and classes
    owners = {x for (x,) in rows(nrepo, f"""SELECT ?x WHERE {{ ?r a ddd:Ownership ; arch:inModel <{P}> ; arch:source ?x .
        ?x a ddd:BoundedContext . ?r arch:target ?a . ?a a ddd:Aggregate }}""")}
    assert [p["render"] for p in proj if p["notation"] == "ddd"] == \
           [{"dddviewpoint": "ContextMap", "model": "procurement"}] + \
           [{"dddviewpoint": "AggregateDiagram", "of": x} for x in sorted(owners)] and owners


@pytest.mark.parametrize("args, cli_args", [
    ({"process": "procurement:bpmnQuoteApproval"}, ["--process", "procurement:bpmnQuoteApproval"]),
    ({"umldiagram": "ClassDiagram", "model": "procurement"}, ["--uml", "ClassDiagram", "--model", "procurement"]),
    ({"view": "procurement:view-umlProbe"}, ["--view", "procurement:view-umlProbe"]),  # declared umlvp: view
    ({"dddviewpoint": "ContextMap", "model": "procurement"}, ["--viewpoint", "ContextMap", "--model", "procurement"]),
    ({"dddviewpoint": "AggregateDiagram", "of": "procurement:quotationBC"},
     ["--viewpoint", "AggregateDiagram", "--of", "procurement:quotationBC"]),
])
def test_render_is_the_cli_output_byte_for_byte(nrepo, tmp_path, args, cli_args):
    bpmn = "process" in args
    p, text = cli(nrepo, tmp_path / ("cli.bpmn" if bpmn else "cli.svg"), *cli_args)
    assert p.returncode == 0, p.stdout + p.stderr
    r = ok(nrepo, "model_render_view", **args)
    if bpmn:
        assert (r["format"], r["notation"], "svg" in r) == ("bpmn-xml", "bpmn", False)
        assert r["content"].encode() == text.encode()
        assert (r["elementCount"], r["relationshipCount"]) == \
               tuple(int(re.search(rf"{k}=(\d+)", p.stdout).group(1)) for k in ("nodes", "flows"))
    else:
        assert (r["format"], "content" in r) == ("svg", False)
        assert r["svg"].encode() == text.encode()
        assert (r["elementCount"], r["relationshipCount"]) == \
               tuple(int(re.search(rf"{k}=(\d+)", p.stdout).group(1)) for k in ("elements", "relationships"))
    assert r["elementCount"] > 0


def test_render_bpmn_is_bpmn_xml_of_the_process(nrepo):
    r = ok(nrepo, "model_render_view", process=P + "bpmnQuoteApproval")
    assert r["title"] == "报价审批流程"
    root = ElementTree.fromstring(r["content"].encode())
    proc = root.find(BPMN_NS + "process")
    assert proc.get("id") == "bpmnQuoteApproval"
    want = {x.rsplit("/", 1)[1] for (x,) in rows(nrepo, f"SELECT ?n WHERE {{ <{P}bpmnQuoteApproval> bpmn:flowElements ?n }}")}
    assert {el.get("id") for el in proc} == want
    assert root.find(".//{http://www.omg.org/spec/BPMN/20100524/DI}BPMNPlane") is not None


def test_existing_entries_keep_svg_and_say_format(vrepo):
    for args in ({"view": "procurement:view-probe"}, {"c4viewpoint": "SystemContext", "of": "t:orderSys"}):
        r = ok(vrepo, "model_render_view", **args)
        assert r["format"] == "svg" and r["svg"].startswith("<svg ") and "content" not in r


def test_uml_view_of_an_unsupported_diagram_is_refused(nrepo, tmp_path):
    e = err(nrepo, "model_render_view", view="procurement:view-uc")
    assert e["code"] == "INVALID_ARGUMENT" and "umlvp:UseCaseDiagram" in e["message"] and e["details"]["rejectedFields"] == ["view"]
    p, _ = cli(nrepo, tmp_path / "cli.svg", "--view", "procurement:view-uc")
    assert p.returncode == 1 and "umlvp:UseCaseDiagram" in p.stdout


@pytest.mark.parametrize("args, code, field", [
    ({"process": "procurement:bpmnQuoteApproval", "model": "procurement"}, "INVALID_ARGUMENT", "model"),
    ({"process": "procurement:bpmnQuoteApproval", "of": "x"}, "INVALID_ARGUMENT", "of"),
    ({"process": "procurement:bpmnQuoteApproval", "view": "procurement:view-probe"}, "INVALID_ARGUMENT", "process"),
    ({"process": "procurement:supplier"}, "INVALID_ARGUMENT", "process"),  # a member, not a bpmn:Process
    ({"process": "procurement:noSuch"}, "ELEMENT_NOT_FOUND", "process"),
    ({"process": "procurement:" + "x" * 2040}, "INVALID_ARGUMENT", "process"),  # schema maxLength 2048
    ({"umldiagram": "ClassDiagram"}, "INVALID_ARGUMENT", "model"),
    ({"umldiagram": "UseCaseDiagram", "model": "procurement"}, "INVALID_ARGUMENT", "umldiagram"),  # schema enum
    ({"umldiagram": "ClassDiagram", "model": "procurement", "of": "x"}, "INVALID_ARGUMENT", "of"),
    ({"umldiagram": "ClassDiagram", "model": "nope"}, "MODEL_NOT_FOUND", None),
    ({"dddviewpoint": "ContextMap"}, "INVALID_ARGUMENT", "model"),
    ({"dddviewpoint": "ContextMap", "model": "procurement", "of": "procurement:quotationBC"}, "INVALID_ARGUMENT", "of"),
    ({"dddviewpoint": "ContextMap", "model": "t"}, "INVALID_ARGUMENT", "dddviewpoint"),  # t has no bounded context
    ({"dddviewpoint": "AggregateDiagram"}, "INVALID_ARGUMENT", "of"),
    ({"dddviewpoint": "AggregateDiagram", "of": "procurement:quotationBC", "model": "procurement"}, "INVALID_ARGUMENT", "model"),
    ({"dddviewpoint": "AggregateDiagram", "of": "procurement:supplier"}, "INVALID_ARGUMENT", "of"),  # not a context
    ({"dddviewpoint": "AggregateDiagram", "of": "procurement:noSuch"}, "ELEMENT_NOT_FOUND", "of"),
    ({"dddviewpoint": "Map", "model": "procurement"}, "INVALID_ARGUMENT", "dddviewpoint"),  # schema enum
])
def test_render_errors_bpmn_uml_ddd(nrepo, args, code, field):
    e = err(nrepo, "model_render_view", **args)
    assert e["code"] == code, e
    if field:
        assert field in e["details"]["rejectedFields"], e


def test_bpmn_uml_ddd_text_xml_cannot_carry_is_refused(vrepo, tmp_path):
    # the #174 rule for every renderer: U+0001 refused with reason text-not-xml naming this call's field, CLI likewise;
    # the BPMN process is not offered by model_list_views either (its selection refuses it)
    with open(vrepo / "models" / "procurement" / "ctrl.ttl", "w", encoding="utf-8") as fh:
        fh.write(f"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix arch: <https://meta.linked.archi/core#> .
@prefix bpmn: <https://meta.linked.archi/bpmn/onto#> . @prefix uml: <https://meta.linked.archi/uml/onto#> .
@prefix ddd: <https://aisep.example/ont/ddd#> . @prefix : <{P}> .
:bpmnCtrl a bpmn:Process ; arch:inModel <{P}> ; skos:prefLabel "坏\\u0001流程"@zh ; bpmn:flowElements :ctrlStart .
:ctrlStart a bpmn:StartEvent ; arch:inModel <{P}> .
:CtrlClass a uml:Class ; arch:inModel <{P}> ; skos:prefLabel "坏\\u0001类"@zh .
:ctrlBC a ddd:BoundedContext ; arch:inModel <{P}> ; skos:prefLabel "坏\\u0001上下文"@zh .
""")
    for args, field, cli_args in (
            ({"process": "procurement:bpmnCtrl"}, "process", ["--process", "procurement:bpmnCtrl"]),
            ({"umldiagram": "ClassDiagram", "model": "procurement"}, "umldiagram", ["--uml", "ClassDiagram", "--model", "procurement"]),
            ({"dddviewpoint": "ContextMap", "model": "procurement"}, "dddviewpoint", ["--viewpoint", "ContextMap", "--model", "procurement"])):
        e = err(vrepo, "model_render_view", **args)
        assert (e["code"], e["details"]["reason"], e["details"]["rejectedFields"]) == ("INVALID_ARGUMENT", "text-not-xml", [field]), e
        assert "U+0001" in e["message"]
        p, out = cli(vrepo, tmp_path / "cli.out", *cli_args)
        assert p.returncode == 1 and "U+0001" in p.stdout and out is None, p.stdout + p.stderr
    listed = ok(vrepo, "model_list_views", model="procurement")["models"][0]["projections"]
    assert P + "bpmnQuoteApproval" in {p["render"].get("process") for p in listed}
    assert P + "bpmnCtrl" not in {p["render"].get("process") for p in listed}


def test_bpmn_uml_ddd_hostile_labels_are_inert(vrepo):
    h = HOSTILE[0] + HOSTILE[1] + HOSTILE[3]
    with open(vrepo / "models" / "procurement" / "evil.ttl", "w", encoding="utf-8") as fh:
        fh.write(f"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix arch: <https://meta.linked.archi/core#> .
@prefix bpmn: <https://meta.linked.archi/bpmn/onto#> . @prefix uml: <https://meta.linked.archi/uml/onto#> .
@prefix ddd: <https://aisep.example/ont/ddd#> . @prefix : <{P}> .
:bpmnEvil a bpmn:Process ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(h)} ; bpmn:flowElements :evilStart .
:evilStart a bpmn:StartEvent ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(h)} .
:EvilClass a uml:Class ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(h)} .
:evilBC a ddd:BoundedContext ; arch:inModel <{P}> ; skos:prefLabel {ttl_str(h)} .
""")
    for args in ({"umldiagram": "ClassDiagram", "model": "procurement"}, {"dddviewpoint": "ContextMap", "model": "procurement"}):
        r = ok(vrepo, "model_render_view", **args)
        assert h in assert_inert(r["svg"]) and "<script" not in r["svg"].replace("&lt;script", "")
    r = ok(vrepo, "model_render_view", process="procurement:bpmnEvil")
    root = ElementTree.fromstring(r["content"].encode())
    assert root.find(BPMN_NS + "process").get("name") == h and r["title"] == h  # an attribute value, not markup
    assert not [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] in ("script", "foreignObject")]


@pytest.mark.parametrize("args", [{"process": "procurement:bpmnQuoteApproval"},
                                  {"umldiagram": "ClassDiagram", "model": "procurement"},
                                  {"dddviewpoint": "AggregateDiagram", "of": "procurement:quotationBC"}])
def test_bpmn_uml_ddd_renderer_unavailable(vrepo, monkeypatch, tmp_path, args):
    monkeypatch.setattr(diagram, "ELK_DIR", _fake_elk(tmp_path, 'process.stdout.write("not json");\n'))
    e = err(vrepo, "model_render_view", **args)
    assert (e["code"], e["details"]["reason"]) == ("RENDERER_UNAVAILABLE", "layout-failed"), e
    monkeypatch.setattr(diagram, "ELK_DIR", str(tmp_path / "none"))
    e = err(vrepo, "model_render_view", **args)
    assert (e["code"], e["details"]["reason"]) == ("RENDERER_UNAVAILABLE", "elkjs-missing"), e
