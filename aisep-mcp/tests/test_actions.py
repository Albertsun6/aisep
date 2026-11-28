"""动作目录（docs/mcp-interface.md §5.13、§5.14，modules/ext-actions/）的独立验收测试。

覆盖《动作机制同类产品调研》第 4 节的断言 B1–B8，以及阶段 C（动作定义改为 RDF）的定义校验、坏定义隔离、
模块夹具实跑。测试者没有参与实现；期望值只来自三处：设计断言与接口文档、现有写工具（model_add_element /
model_add_relationship / model_set_labels / model_remove / model_impact）在对照副本上的实际行为、模型文件里本来就有
的事实。实现的输出不作期望值。

每个用例都在 tmp_path 下的全新 git 仓库里操作（models/ 全部、modules/、vendor/、tools/、aisep/ 的副本），真实检出
不动。要换动作定义的用例直接改副本里的 modules/ext-actions/catalog.ttl（执行器读所服务工作区里的这个文件）。
C1、C2 是只对本 PR 有意义的分支级验收（相对 origin/main 比较），已在 PR #113 上核对，不放进常驻测试：
合入后它们在 main 上必然失败，后续改到 models/ 或新增工具的 PR 也会被误判。
"""
import fcntl, hashlib, json, os, re, shutil, subprocess, sys

import anyio
import pyoxigraph as ox
import pytest
from mcp import Client, StdioServerParameters

from conftest import ROOT, commit_all, git, init_repo
from aisep import actions, core, server, tools

PY = sys.executable
WB = "https://aisep.example/model/workbench/"
PC = "https://aisep.example/model/procurement/"
AISEP = "https://aisep.example/ont/aisep#"
REQ = WB + "reqApprovalProgress"            # models/workbench/am4.ttl，am4:Requirement
REQ2 = WB + "reqRejectRelease"              # models/workbench/am4.ttl，am4:Requirement
AC = WB + "acProgressFourStages"            # models/workbench/verification.ttl，aisep:AcceptanceCriterion
BPMN_NODE = WB + "bpmnApvChooseModel"       # models/workbench/bpmn.ttl，bpmn:UserTask
OTHER_TC = WB + "tcNestedScanDepthLimited"  # models/workbench/verification.ttl，aisep:TestCase
APPROVAL = WB + "approval-20261121092334-architecture-58e5129"  # 批准记录（受保护）
PC_REQ = PC + "reqTwoLevelApproval"
VER = "models/workbench/verification.ttl"
AM4 = "models/workbench/am4.ttl"
GOV = "models/workbench/governance.ttl"
CAT = "modules/ext-actions/catalog.ttl"
OWL_DEPRECATED = "<http://www.w3.org/2002/07/owl#deprecated>"
UNDECLARED = "https://example.invalid/undeclared"
REGISTER, REMOVE = "register-acceptance-criterion", "remove-element"
P0 = {"requirement": REQ, "prefLabel": "探针验收标准", "altLabel": "Probe criterion",
      "definition": "独立测试用的验收标准。", "gherkin": "Given a\nWhen b\nThen c"}
ZERO = "sha256:" + "0" * 64


# ------------------------------------------------------------------ 夹具与工具

@pytest.fixture(scope="session", autouse=True)
def _executor_reads_the_served_worktree():
    assert actions.CATALOG_PATH is None, "测试要求执行器读所服务工作区里的 catalog.ttl"
    assert os.path.abspath(actions.__file__).startswith(os.path.abspath(ROOT) + os.sep)


@pytest.fixture(scope="session")
def wtemplate(tmp_path_factory):
    """被测检出的 models/（全部模型）、modules/、vendor/、tools/、aisep/ 与 .gitignore 的副本。"""
    t = tmp_path_factory.mktemp("wtemplate")
    ign = shutil.ignore_patterns("__pycache__", "node_modules")
    for d in ("models", "modules", "vendor", "tools", "aisep"):
        shutil.copytree(os.path.join(ROOT, d), t / d, ignore=ign)
    shutil.copy2(os.path.join(ROOT, ".gitignore"), t / ".gitignore")
    return t


@pytest.fixture
def mk(wtemplate, tmp_path):
    """mk(name) -> 一份全新的工作副本（单个提交的 git 仓库，分支 main）。"""
    def make(name="w"):
        dst = tmp_path / name
        shutil.copytree(wtemplate, dst)
        init_repo(dst)
        commit_all(dst, "start")
        assert git(dst, "status", "--porcelain") == ""
        return dst
    return make


def cfg(repo):
    return tools.Config(allow_roots=(str(repo.parent),), repo=str(repo))


def call(repo, name, **args):
    """经 MCP 层（参数先过 inputSchema）调一次工具 -> (is_error, structuredContent)。"""
    if name != "model_list_actions":
        args = dict(args, repo=str(repo))
    r = server.call(cfg(repo), name, args)
    return r.is_error, r.structured_content


def ok(repo, name, **args):
    is_err, res = call(repo, name, **args)
    assert not is_err, f"{name} 应当成功，却被拒绝：{json.dumps(res, ensure_ascii=False)[:800]}"
    return res


def err(repo, name, **args):
    is_err, res = call(repo, name, **args)
    assert is_err, f"{name} 应当被拒绝，却成功了：{json.dumps(res, ensure_ascii=False)[:800]}"
    return res["error"]


def code_of(repo, name, **args):
    is_err, res = call(repo, name, **args)
    return res["error"]["code"] if is_err else "OK"


def apply(repo, action, params, **kw):
    return ok(repo, "model_apply_action", action=action, params=params, **kw)


def apply_err(repo, action, params, **kw):
    return err(repo, "model_apply_action", action=action, params=params, **kw)


def listing(repo):
    return {a["iri"]: a for a in ok(repo, "model_list_actions")["actions"]}


def by_id(repo):
    return {a["id"]: a for a in ok(repo, "model_list_actions")["actions"] if a["id"] is not None}


def snap(repo):
    """{相对路径: sha256}，models/ 下所有文件。"""
    out = {}
    for d, _, fs in os.walk(repo / "models"):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, repo)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def raw(repo):
    out = {}
    for d, _, fs in os.walk(repo / "models"):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, repo)] = open(p, "rb").read()
    return out


def assert_same_models(a, b):
    ra, rb = raw(a), raw(b)
    assert sorted(ra) == sorted(rb), "两个副本 models/ 下的文件集合不同"
    diff = [f for f in ra if ra[f] != rb[f]]
    assert not diff, f"逐字节不一致的文件：{diff}"


def append(repo, rel, text):
    with open(repo / rel, "a", encoding="utf-8") as f:
        f.write(text)


def read(repo, rel):
    with open(repo / rel, encoding="utf-8") as f:
        return f.read()


def write(repo, rel, text):
    with open(repo / rel, "w", encoding="utf-8") as f:
        f.write(text)


def model_iri(iri):
    m = re.fullmatch(r"(https://aisep\.example/model/[^/]+/)[^/]+", iri)
    assert m
    return m.group(1)


def sequential(repo, p):
    """登记验收标准的「依次调两个写工具」写法，参数与动作相同。返回 [(is_error, 结果)]，第一步被拒就不调第二步。"""
    a = {"model": model_iri(p["requirement"]), "type": "aisep:AcceptanceCriterion", "prefLabel": p["prefLabel"]}
    for k in ("altLabel", "slug", "definition", "file"):
        if k in p:
            a[k] = p[k]
    if "gherkin" in p:
        a["attributes"] = [{"predicate": "aisep:gherkin", "value": {"value": p["gherkin"]}}]
    out = [call(repo, "model_add_element", **a)]
    if out[0][0]:
        return out
    b = {"type": "am4:Aggregation", "source": p["requirement"], "target": out[0][1]["iri"]}
    if "relationshipFile" in p:
        b["file"] = p["relationshipFile"]
    out.append(call(repo, "model_add_relationship", **b))
    return out


def gate(repo):
    p = subprocess.run([PY, "tools/aisep.py", "gate"], cwd=str(repo), capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    summary = [ln for ln in p.stdout.splitlines() if ln.startswith("SUMMARY")]
    assert summary, f"gate 没有 SUMMARY 行：{p.stdout[-800:]}{p.stderr[-800:]}"
    if "result=PASS" in summary[-1]:
        assert p.returncode == 0
        return "PASS", p.stdout
    assert p.returncode != 0
    return "FAIL", p.stdout


def literal_values(repo, rel, subject, predicate):
    with open(repo / rel, "rb") as f:
        return [q.object.value for q in ox.parse(f, format=ox.RdfFormat.TURTLE, base_iri=WB)
                if q.subject.value == subject and q.predicate.value == predicate]


# ------------------------------------------------------------------ 往目录里写测试动作（Turtle）

def b(arg, src, val, pred=None):
    """一个绑定。src: constant / fromParameter / fromStep / modelOf；fromStep 的 val 写 STEP(步骤 id)。"""
    return f'[ aisep:argument "{arg}" ; aisep:{src} {val}' + (f" ; aisep:attributePredicate {pred}" if pred else "") + " ]"


def sp(name, iri=False, optional=False):
    kind = "sh:nodeKind sh:IRI" if iri else "sh:datatype xsd:string"
    return f"[ sh:path ap:{name} ; {kind}" + (" ; sh:optional true" if optional else "") + " ]"


def guard(gid, ask, msg="测试用的修法提示。"):
    return f'[ a sh:SPARQLAskValidator ; dcterms:identifier {json.dumps(gid)} ; sh:ask "{ask}" ; sh:message "{msg}"@zh ]'


def act(local, ident, steps, params=(), guards=(), version="1.0.0", extra="", order=None):
    """一个 aisep:ActionType 的 Turtle。steps: [(步骤 id, 基本动作本地名, [绑定])]。步骤是带标签的空白节点
    （_:t<local>_<n>），order 给出表里的成员顺序（下标，可重复），缺省按 steps 的顺序。"""
    labels = [f"_:t{local}_{n}" for n in range(len(steps))]
    first = {}
    for n, (sid, _, _) in enumerate(steps):
        first.setdefault(sid, labels[n])
    ident_lit = json.dumps(ident, ensure_ascii=False)
    lines = [f"aisep:{local} a aisep:ActionType ;", f"    dcterms:identifier {ident_lit} ;",
             '    skos:prefLabel "测试动作"@zh ;', f'    owl:versionInfo "{version}" ;']
    if params:
        lines.append("    sh:parameter " + " ,\n        ".join(params) + " ;")
    if guards:
        lines.append("    aisep:guard " + " ,\n        ".join(guards) + " ;")
    if extra:
        lines.append("    " + extra + " ;")
    members = [labels[i] for i in (order if order is not None else range(len(steps)))]
    lines.append("    aisep:steps ( " + " ".join(members) + " ) .")
    for n, (sid, op, binds) in enumerate(steps):
        bs = [re.sub(r"STEP\(([^)]*)\)", lambda m: first[m.group(1)], x) for x in binds]
        lines.append(f"{labels[n]} a aisep:ActionStep ; dcterms:identifier {json.dumps(sid)} ; aisep:invokes aisep:{op}"
                     + (" ;\n    aisep:binding " + " ,\n        ".join(bs) if bs else "") + " .")
    return "\n" + "\n".join(lines) + "\n"


def add_actions(repo, *ttl):
    """把测试动作追加进副本的 catalog.ttl 并提交（之后 `git status` 只反映模型文件的改动）。"""
    append(repo, CAT, "\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + "".join(ttl))
    commit_all(repo, "test actions")


def new_criterion_step(sid="el", slug_const=None, label_param="label", typ="aisep:AcceptanceCriterion", extra=()):
    binds = [b("model", "constant", f"<{WB}>"), b("type", "constant", typ),
             b("prefLabel", "fromParameter", f"ap:{label_param}")]
    if slug_const:
        binds.append(b("slug", "constant", f'"{slug_const}"'))
    return (sid, "BasicAddElement", binds + list(extra))


# ================================================================== RDF 目录：仓库现状与对齐

def test_json_catalog_is_gone():
    assert not os.path.exists(os.path.join(ROOT, "aisep", "action_catalog.json"))
    assert not os.path.exists(os.path.join(ROOT, "aisep", "actions", "catalog.json"))
    # 扫文件系统而不是 git ls-files：非 git 副本（如解压的源码包）里也要能跑
    found = [os.path.relpath(os.path.join(d, f), ROOT)
             for d, _, fs in os.walk(os.path.join(ROOT, "aisep")) for f in fs]
    assert not [f for f in found if f.endswith(".json") and "action" in f], found
    assert os.path.isfile(os.path.join(ROOT, CAT))


def _rdf(path):
    with open(path, "rb") as f:
        return list(ox.parse(f, format=ox.RdfFormat.TURTLE))


def test_basic_actions_agree_in_onto_shapes_and_executor():
    """onto.ttl 的 aisep:BasicAction 个体（及其 skos:notation）、shapes.ttl 里 EA6 的 sh:in、执行器的 OPS 三处一致，
    且 notation 就是 model_list_actions 报的 operations、也是 server 里真实存在的写工具。"""
    onto = _rdf(os.path.join(ROOT, "modules", "ext-actions", "onto.ttl"))
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    basics = {q.subject.value for q in onto if q.predicate.value == rdf_type and q.object.value == AISEP + "BasicAction"}
    notation = {q.subject.value: q.object.value for q in onto
                if q.subject.value in basics and q.predicate.value == "http://www.w3.org/2004/02/skos/core#notation"}
    assert len(basics) == 5 and set(notation) == basics
    st = ox.Store()
    st.load(path=os.path.join(ROOT, "modules", "ext-actions", "shapes.ttl"), format=ox.RdfFormat.TURTLE)
    rows = st.query("""PREFIX sh: <http://www.w3.org/ns/shacl#> PREFIX aisep: <https://aisep.example/ont/aisep#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?m WHERE { ?ps sh:path aisep:invokes ; sh:in ?l . ?l rdf:rest*/rdf:first ?m }""")
    in_list = {r["m"].value for r in rows}
    assert in_list == basics
    assert set(actions.OPS) == basics
    assert {k: v["tool"] for k, v in actions.OPS.items()} == notation
    assert set(notation.values()) == {"model_add_element", "model_add_relationship", "model_set_labels",
                                      "model_set_attributes", "model_remove"}
    assert set(notation.values()) <= set(server.TOOLS)


def test_repository_catalogue_every_definition_is_valid(mk):
    """接口文档 §5.13：仓库里的目录靠这条 pytest 挡住 X 规则（gate 不知道 X6 等）。"""
    r = mk()
    res = ok(r, "model_list_actions")
    bad = [a for a in res["actions"] if not a["valid"]]
    assert not bad, json.dumps(bad, ensure_ascii=False)
    # 与目录文件本身逐条对上（期望来自 catalog.ttl 的三元组，不来自执行器）
    q = _rdf(os.path.join(ROOT, CAT))
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    subjects = sorted(x.subject.value for x in q if x.predicate.value == rdf_type and x.object.value == AISEP + "ActionType")
    assert [a["iri"] for a in res["actions"]] == subjects       # 按 IRI 排序
    ids = {x.subject.value: x.object.value for x in q
           if x.subject.value in subjects and x.predicate.value == "http://purl.org/dc/terms/identifier"}
    assert {a["iri"]: a["id"] for a in res["actions"]} == ids
    assert {a["id"] for a in res["actions"]} == {REGISTER, REMOVE}
    reg, rm = (next(a for a in res["actions"] if a["id"] == i) for i in (REGISTER, REMOVE))
    assert [s["op"] for s in reg["steps"]] == ["model_add_element", "model_add_relationship"]
    assert reg["destructive"] is False and reg["requiresPlanDigest"] is False
    assert [s["op"] for s in rm["steps"]] == ["model_remove"]
    assert rm["destructive"] is True and rm["requiresPlanDigest"] is True
    assert sorted(reg["params"]["required"]) == ["prefLabel", "requirement"] and reg["iriParams"] == ["requirement"]
    assert reg["params"]["additionalProperties"] is False
    assert sorted(res["operations"]) == sorted(["model_add_element", "model_add_relationship", "model_set_labels",
                                                "model_set_attributes", "model_remove"])
    mf = _rdf(os.path.join(ROOT, "modules", "ext-actions", "metamodel.ttl"))
    assert res["catalogVersion"] == next(x.object.value for x in mf if x.predicate.value == "http://www.w3.org/2002/07/owl#versionInfo")


def catalogue_reference_problems(root):
    """G4：目录里每个 aisep:constant、aisep:attributePredicate 引用的 IRI 都要在当前元模型（全部模块清单 aisep:loads
    的文件，含 vendor，不含 catalog.ttl 自己）里有 rdf:type 声明，且没有 owl:deprecated true。返回 [(IRI, 原因)]。"""
    mods = core.discover(str(root))
    cat = os.path.realpath(os.path.join(str(root), CAT))
    meta = []
    for f in core.onto_files(mods, "all"):
        if os.path.realpath(f) != cat:
            meta += _rdf(f)
    rdf_type, dep = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://www.w3.org/2002/07/owl#deprecated"
    declared = {q.subject.value for q in meta if q.predicate.value == rdf_type and isinstance(q.subject, ox.NamedNode)}
    deprecated = {q.subject.value for q in meta if q.predicate.value == dep and q.object.value == "true"}
    refs = sorted({q.object.value for q in _rdf(os.path.join(str(root), CAT))
                   if q.predicate.value in (AISEP + "constant", AISEP + "attributePredicate")
                   and isinstance(q.object, ox.NamedNode)})
    out = [(i, "undeclared") for i in refs if i not in declared]
    return out + [(i, "deprecated") for i in refs if i in deprecated]


def test_catalogue_references_are_declared_and_not_deprecated(mk):
    """元模型改名、删除、弃用了目录引用的类或属性时，这条 pytest 变红（gate 与执行器都不查这一点）。"""
    r = mk()
    refs = {q.object.value for q in _rdf(os.path.join(str(r), CAT))
            if q.predicate.value in (AISEP + "constant", AISEP + "attributePredicate")}
    assert {AISEP + "AcceptanceCriterion", AISEP + "gherkin", "https://meta.linked.archi/archimate4/onto#Aggregation"} <= refs
    assert catalogue_reference_problems(r) == []


def test_catalogue_reference_check_catches_undeclared_and_deprecated_terms(mk):
    """上一条的变异对照：引用一个不存在的类、弃用目录引用的属性，各自被点名。"""
    r = mk()
    write(r, CAT, read(r, CAT).replace("aisep:constant am4:Aggregation", "aisep:constant am4:AggregationGone"))
    append(r, "modules/ext-verification/onto.ttl", "\naisep:gherkin owl:deprecated true .\n")
    assert catalogue_reference_problems(r) == [
        ("https://meta.linked.archi/archimate4/onto#AggregationGone", "undeclared"), (AISEP + "gherkin", "deprecated")]


def triples_outside_action_closures(path):
    """G7：catalog.ttl 里主语不在任何 aisep:ActionType 闭包（动作 IRI 及沿宾语可达的空白节点）里的三元组。"""
    qs = _rdf(path)
    rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    out = {}
    for q in qs:
        out.setdefault(q.subject, []).append(q.object)
    seen = set()
    todo = [q.subject for q in qs if q.predicate.value == rdf_type and q.object.value == AISEP + "ActionType"]
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += [o for o in out.get(n, ()) if isinstance(o, ox.BlankNode)]
    return [q for q in qs if q.subject not in seen]


def test_catalogue_has_no_triples_outside_action_closures():
    """目录文件只放动作定义：类声明、子类公理、游离的步骤或绑定片段都不许出现（ADR-026 补记 2026-11-27）。"""
    assert triples_outside_action_closures(os.path.join(ROOT, CAT)) == []


def test_catalogue_closure_check_catches_tbox_and_orphan_triples(mk):
    """上一条的变异对照：一条子类公理、一个游离的步骤片段，都被点名。"""
    r = mk()
    append(r, CAT, "\nam4:Requirement <http://www.w3.org/2000/01/rdf-schema#subClassOf> aisep:ActionType .\n"
                   '_:orphan a aisep:ActionStep ; dcterms:identifier "orphan" .\n')
    found = triples_outside_action_closures(os.path.join(str(r), CAT))
    assert sorted(q.predicate.value.rsplit("#", 1)[-1].rsplit("/", 1)[-1] for q in found) == ["identifier", "subClassOf", "type"]


def test_gate_checks_the_catalogue_with_the_module_shapes(mk):
    """catalog.ttl 在 aisep:loads 里，gate 的 L3 用 EA 形状校验它：未知基本动作写进目录，gate FAIL 且点名 EA6。"""
    r = mk()
    assert gate(r)[0] == "PASS"
    write(r, CAT, read(r, CAT).replace("aisep:invokes aisep:BasicRemove", "aisep:invokes aisep:BasicRemoveX"))
    result, out = gate(r)
    assert result == "FAIL" and "EA6" in out, out[-1500:]


RM_PARAM = "sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ;"
DEPRECATED_GUARD = '[ a sh:SPARQLAskValidator ; dcterms:identifier "parent-is-not-deprecated" ;'
RM_STEP = '[ a aisep:ActionStep ; dcterms:identifier "remove" ;'


def _to_iri_node(pattern, iri, body="{0}"):
    """把目录里唯一匹配 pattern 的空白节点换成 <iri>，其内容（body 按捕获组填）原样写成该 IRI 的描述，追加在文件末尾。"""
    def edit(t):
        found = list(re.finditer(pattern, t))
        assert len(found) == 1, (pattern, len(found))
        m = found[0]
        return t[:m.start()] + f"<{iri}>" + t[m.end():] + f"\n<{iri}> {body.format(*m.groups())} .\n"
    return edit


@pytest.mark.parametrize("defect, edit, expect", [
    # 每个缺陷都写在空白节点上（sh:nodeKind sh:BlankNode 满足），所以只有文件名所说的那条约束能报出这条规则：
    # ParameterShape 的 sh:xone / sh:closed、GuardShape 的 sh:message、sh:class sh:SPARQLAskValidator、EA5 成员形状的 sh:class。
    ("ea8-parameter-two-types", lambda t: t.replace(RM_PARAM, RM_PARAM + " sh:datatype xsd:string ;"), "EA8:"),
    ("ea8-parameter-unsupported-key", lambda t: t.replace(RM_PARAM, RM_PARAM + " sh:maxLength 10 ;"), "EA8:"),
    ("ea9-guard-without-message",
     lambda t: re.sub(r'(dcterms:identifier "parent-is-not-deprecated" ;\s*sh:ask "[^"]*") ;\s*sh:message "[^"]*"@zh', r"\1", t),
     "EA9:"),
    ("ea9-guard-not-a-validator",
     lambda t: t.replace(DEPRECATED_GUARD, '[ dcterms:identifier "parent-is-not-deprecated" ;'), "EA9:"),
    ("ea5-member-not-a-step", lambda t: t.replace(RM_STEP, '[ dcterms:identifier "remove" ;'), "EA5: every member"),
    # issue #140 ②：内容原样、只把节点从空白节点改写成 IRI 节点，其余约束都满足，只有 sh:nodeKind sh:BlankNode 能报出这条规则
    # （模型文件里的负例做不到：空白节点会先被 G7 拒绝）。五处 nodeKind 各一例。
    ("nodekind-parameter-iri-node",
     _to_iri_node(r'\[ (sh:path ap:iri ; sh:nodeKind sh:IRI ; sh:description "[^"]*"@zh) \]', "urn:x-test:parameter"),
     "EA8:"),
    ("nodekind-guard-iri-node",
     _to_iri_node(r'\[ (a sh:SPARQLAskValidator ; dcterms:identifier "parent-is-not-deprecated" ;\s*sh:ask "[^"]*" ;'
                  r'\s*sh:message "[^"]*"@zh) \]', "urn:x-test:guard"), "EA9:"),
    ("nodekind-binding-iri-node",
     _to_iri_node(r'\[ (aisep:argument "iri" ; aisep:fromParameter ap:iri) \]', "urn:x-test:binding"), "EA7:"),
    ("nodekind-step-member-iri-node",
     _to_iri_node(r'\[ (a aisep:ActionStep ; dcterms:identifier "remove" ; aisep:invokes aisep:BasicRemove ;'
                  r'\s*aisep:binding \[ aisep:argument "iri" ; aisep:fromParameter ap:iri \]) \]', "urn:x-test:step"),
     "EA5: every member"),
    ("nodekind-steps-list-iri-node",
     _to_iri_node(r'\( (_:criterion) (_:aggregation) \)', "urn:x-test:list",
                  "<http://www.w3.org/1999/02/22-rdf-syntax-ns#first> {0} ; "
                  "<http://www.w3.org/1999/02/22-rdf-syntax-ns#rest> ( {1} )"),
     "EA5: an action type needs"),
    # G5：EA2、EA3、EA4、EA7、EA10 在真实目录副本上也要被 gate 点名（此前只有模型文件负例与执行器一侧的 pytest）
    ("ea2-identifier-uppercase", lambda t: t.replace('"remove-element"', '"Remove-element"'), "EA2:"),
    ("ea3-preflabel-not-zh", lambda t: t.replace('"删除元素"@zh', '"删除元素"@en'), "EA3:"),
    ("ea4-version-not-semver",
     lambda t: re.sub(r'(dcterms:identifier "remove-element" ;[^.]*?owl:versionInfo )"1\.0\.0"', r'\1"1.0"', t), "EA4:"),
    ("ea7-binding-two-sources",
     lambda t: t.replace('[ aisep:argument "iri" ; aisep:fromParameter ap:iri ]',
                         '[ aisep:argument "iri" ; aisep:fromParameter ap:iri ; aisep:modelOf ap:iri ]'), "EA7:"),
    ("ea10-steps-on-a-step",
     lambda t: t.replace('dcterms:identifier "remove" ; aisep:invokes aisep:BasicRemove ;',
                         'dcterms:identifier "remove" ; aisep:invokes aisep:BasicRemove ; aisep:guard [] ;'),
     "EA10: aisep:steps / aisep:guard"),
    ("ea10-invokes-on-an-action",
     lambda t: t.replace('owl:versionInfo "1.0.0" ;\n    sh:parameter [ sh:path ap:iri',
                         'owl:versionInfo "1.0.0" ; aisep:invokes aisep:BasicRemove ;\n    sh:parameter [ sh:path ap:iri'),
     "EA10: aisep:invokes / aisep:binding"),
    ("ea10-argument-outside-a-binding",
     lambda t: t.replace('dcterms:identifier "remove" ; aisep:invokes aisep:BasicRemove ;',
                         'dcterms:identifier "remove" ; aisep:invokes aisep:BasicRemove ; aisep:argument "iri" ;'),
     "EA10: aisep:argument"),
    # G7：动作个体另带领域类型（EA11）；动作上写 TBox 三元组（ActionTypeShape 封闭，报 EA1）
    ("ea11-action-with-domain-type",
     lambda t: t.replace("aisep:ActionRemoveElement a aisep:ActionType ;", "aisep:ActionRemoveElement a aisep:ActionType , am4:Requirement ;"),
     "EA11:"),
    ("ea1-action-subclass-of-element",
     lambda t: t.replace("aisep:ActionRemoveElement a aisep:ActionType ;",
                         "aisep:ActionRemoveElement a aisep:ActionType ;\n    "
                         "<http://www.w3.org/2000/01/rdf-schema#subClassOf> <https://meta.linked.archi/core#Element> ;"),
     "EA1:"),
])
def test_gate_names_the_shape_of_each_catalogue_defect(mk, defect, edit, expect):
    """followups-20261126 第 8 项：tests/invalid 里同名负例只能写成 IRI 节点（模型文件里的空白节点会先被 G7 拒绝），
    只证伪 sh:nodeKind；文件名所说的缺陷在这里写进真实目录（模块文件，不受 G7 约束）的副本，gate FAIL 并报出该规则。
    变异对照（去掉对应约束后本测试变红）记在 PR #133 正文。"""
    r = mk()
    before = read(r, CAT)
    after = edit(before)
    assert after != before, defect
    write(r, CAT, after)
    result, out = gate(r)
    assert result == "FAIL", out[-1500:]
    assert any(expect in ln for ln in out.splitlines() if ln.startswith("[Violation] L3 [ext-actions]")), out[-1500:]


# ================================================================== 模块夹具实跑（tests/valid 通过、tests/invalid 被 shapes 判违规）

FIXTURE_SCRIPT = r"""
import glob, json, os, runpy, sys
cli = runpy.run_path(sys.argv[1], run_name="aisep_cli_under_test")
discover, dependencies, run_fixture = cli["discover"], cli["dependencies"], cli["run_fixture"]
Ctx, run_check, l3 = cli["Ctx"], cli["run_check"], cli["l3"]
mods = discover()
names = {m.name for m in mods}
m = next(x for x in mods if x.name == "ext-actions")
out = []
for kind in ("valid", "invalid"):
    for fx in sorted(glob.glob(os.path.join(m.dir, "tests", kind, "*.ttl"))):
        head = open(fx, encoding="utf-8").read().splitlines()[:5]
        extra = [n for l in head if l.startswith("# modules:") for n in l.split(":", 1)[1].split()]
        want = {d.name for n in [m.name] + extra for d in dependencies(mods, n)}
        sub = mods if any(l.startswith("# uses:") for l in head) else [d for d in mods if d.name in want]
        ok, detail = run_fixture(sub, fx)
        ctx = Ctx(sub, [fx])      # 自己再跑一遍：L1/L2 与 L3 分开记录，看违规出自哪一层
        run_check(ctx)
        pre = [(l, t) for s, l, t in ctx.problems if s == "Violation"]
        l3(ctx)
        allv = [(l, t) for s, l, t in ctx.problems if s == "Violation"]
        expect = head[0].split("# expect:", 1)[1].strip() if head and head[0].startswith("# expect:") else None
        out.append({"kind": kind, "file": os.path.basename(fx), "ok": ok, "detail": detail, "expect": expect,
                    "pre": pre, "all": allv})
print(json.dumps(out, ensure_ascii=False))
"""


# 这个 session 夹具起一个子进程跑全部模块夹具（CI 上约 45–95 s）。session 夹具在每个 xdist worker 各建一次、每个分片各建一次，
# 三个用户分散时这笔钱要付好几遍：xdist_group 标记让 conftest.assign_shards 把它们分进同一片；片内各 worker 经文件锁共用
# 第一个算出的结果（pytest-xdist 文档 "Making session-scoped fixtures execute only once" 的做法）。不用 --dist loadgroup：
# 本仓钉的 pytest 9.2 + xdist 3.8 下它给 nodeid 加组名后缀不生效，同组用例照样分到不同 worker。
FIXTURE_GROUP = pytest.mark.xdist_group("module_fixture_results")


@pytest.fixture(scope="session")
def module_fixture_results(wtemplate, tmp_path_factory):
    base = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent                  # 各 worker 的 basetemp 同在本次会话的 basetemp 下
    out = base / "module_fixture_results.json"
    with open(base / "module_fixture_results.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)    # 进程退出即释放；先到的 worker 算，其余等它写完再读
        if not out.exists():
            script = tmp_path_factory.mktemp("fxscript") / "run_fixtures.py"
            script.write_text(FIXTURE_SCRIPT, encoding="utf-8")
            p = subprocess.run([PY, str(script), str(wtemplate / "tools" / "aisep.py")], cwd=str(wtemplate),
                               capture_output=True, text=True, timeout=600, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            assert p.returncode == 0, p.stderr[-3000:]
            out.write_text(p.stdout.strip().splitlines()[-1], encoding="utf-8")
    return json.loads(out.read_text(encoding="utf-8"))


@FIXTURE_GROUP
def test_module_fixtures_exist(module_fixture_results):
    kinds = [r["kind"] for r in module_fixture_results]
    assert kinds.count("valid") >= 1 and kinds.count("invalid") >= 10
    rules = {re.match(r"(ea\d+)-", r["file"]).group(1) for r in module_fixture_results if r["kind"] == "invalid"}
    assert rules == {f"ea{i}" for i in range(1, 12)}, rules     # EA1–EA11 每条都有负例


@FIXTURE_GROUP
def test_module_valid_fixtures_pass(module_fixture_results):
    for r in module_fixture_results:
        if r["kind"] == "valid":
            assert r["ok"], r
            assert r["all"] == [], r


@FIXTURE_GROUP
def test_module_invalid_fixtures_are_violations_of_the_ext_actions_shapes(module_fixture_results):
    for r in module_fixture_results:
        if r["kind"] != "invalid":
            continue
        assert r["ok"], r                                      # 与 `tools/aisep.py test` 同一判据
        rule = re.match(r"(ea\d+)-", r["file"]).group(1).upper()
        assert r["expect"] and r["expect"].startswith(rule), r  # 夹具声明的期望就是文件名里的那条规则
        hits = [(l, t) for l, t in r["all"] if r["expect"] in t]
        assert hits and all(l == "L3" for l, _ in hits), r      # 期望的违规由 L3（shapes）报出
        assert not any(r["expect"] in t for _, t in r["pre"]), r


# ================================================================== 坏定义隔离（RDF 定义）

GOOD_EXTRA = act("ActionTestGood", "test-good", [new_criterion_step(slug_const="acGoodOne")], params=[sp("label")])

BAD_DEFS = {
    # 未知基本动作（封闭集合之外）
    "unknown-basic-action": act("ActionTestBadOp", "test-bad-op", [("s", "BasicRename", [b("iri", "fromParameter", "ap:iri")])],
                                params=[sp("iri", iri=True)]),
    # 动作个体另带领域类型（EA11）、动作上写 TBox 三元组（EA1 封闭）
    "action-with-domain-type": act("ActionTestBadDomainType", "test-bad-domain-type", [new_criterion_step(slug_const="acDt1")],
                                   params=[sp("label")], extra="a am4:Requirement"),
    "action-subclass-of-element": act("ActionTestBadSubclass", "test-bad-subclass", [new_criterion_step(slug_const="acSc1")],
                                      params=[sp("label")],
                                      extra="<http://www.w3.org/2000/01/rdf-schema#subClassOf> <https://meta.linked.archi/core#Element>"),
    # 标识符带结尾换行：动作 id、步骤 id、guard id
    "action-id-trailing-newline": act("ActionTestBadIdNl", "test-bad-nl\n", [new_criterion_step(slug_const="acNl1")],
                                      params=[sp("label")]),
    "step-id-trailing-newline": act("ActionTestBadStepNl", "test-bad-step-nl",
                                    [new_criterion_step(sid="el\n", slug_const="acNl2")], params=[sp("label")]),
    "guard-id-trailing-newline": act("ActionTestBadGuardNl", "test-bad-guard-nl", [new_criterion_step(slug_const="acNl3")],
                                     params=[sp("label")], guards=[guard("g\n", "ASK { ?s ?p ?o }")]),
    # 步骤顺序：表里同一步出现两次（重复）；两个步骤用同一个 id（重复）
    "list-member-repeated": act("ActionTestBadRepeat", "test-bad-repeat",
                                [("lab", "BasicSetLabels", [b("iri", "fromParameter", "ap:iri"),
                                                            b("definition", "constant", '"x"')])],
                                params=[sp("iri", iri=True)], order=[0, 0]),
    "step-id-duplicated": act("ActionTestBadDupId", "test-bad-dup-id",
                              [new_criterion_step(sid="el", slug_const="acDup1"),
                               ("el", "BasicSetLabels", [b("iri", "fromParameter", "ap:iri"),
                                                         b("definition", "constant", '"x"')])],
                              params=[sp("label"), sp("iri", iri=True)]),
    # 两步作用于同一目标（X6）
    "same-target-same-param": act("ActionTestBadSameParam", "test-bad-same-param",
                                  [("a", "BasicSetLabels", [b("iri", "fromParameter", "ap:iri"), b("definition", "constant", '"x"')]),
                                   ("b", "BasicSetLabels", [b("iri", "fromParameter", "ap:iri"), b("prefLabel", "constant", '"y"')])],
                                  params=[sp("iri", iri=True)]),
    "same-target-from-step": act("ActionTestBadFromStep", "test-bad-from-step",
                                 [new_criterion_step(slug_const="acFromStep"),
                                  ("lab", "BasicSetLabels", [b("iri", "fromStep", "STEP(el)"), b("definition", "constant", '"x"')])],
                                 params=[sp("label")]),
    "remove-endpoint-of-new-relationship": act(
        "ActionTestBadRmEndpoint", "test-bad-rm-endpoint",
        [("rel", "BasicAddRelationship", [b("type", "constant", "am4:Aggregation"), b("source", "fromParameter", "ap:req"),
                                          b("target", "fromParameter", "ap:iri")]),
         ("rm", "BasicRemove", [b("iri", "fromParameter", "ap:iri")])],
        params=[sp("req", iri=True), sp("iri", iri=True)]),
    "same-constant-target": act("ActionTestBadSameConst", "test-bad-same-const",
                                [("a", "BasicSetLabels", [b("iri", "constant", f"<{REQ}>"), b("definition", "constant", '"x"')]),
                                 ("b", "BasicRemove", [b("iri", "constant", f"<{REQ}>")])]),
    # 参数缺 sh:path
    "parameter-without-path": act("ActionTestBadNoPath", "test-bad-no-path", [new_criterion_step(slug_const="acNoPath")],
                                  params=[sp("label"), "[ sh:datatype xsd:string ]"]),
    # 参数两种类型都写
    "parameter-two-kinds": act("ActionTestBadTwoKinds", "test-bad-two-kinds", [new_criterion_step(slug_const="acTwoK")],
                               params=["[ sh:path ap:label ; sh:datatype xsd:string ; sh:nodeKind sh:IRI ]"]),
    # guard 缺 sh:message
    "guard-without-message": act("ActionTestBadGuardMsg", "test-bad-guard-msg", [new_criterion_step(slug_const="acGm")],
                                 params=[sp("label")],
                                 guards=['[ a sh:SPARQLAskValidator ; dcterms:identifier "g" ; sh:ask "ASK { ?s ?p ?o }" ]']),
    # guard 不是 ASK / 带 SERVICE / 语法错
    "guard-not-ask": act("ActionTestBadGuardSel", "test-bad-guard-sel", [new_criterion_step(slug_const="acGs")],
                         params=[sp("label")], guards=[guard("g", "SELECT * WHERE { ?s ?p ?o }")]),
    "guard-service": act("ActionTestBadGuardSvc", "test-bad-guard-svc", [new_criterion_step(slug_const="acGv")],
                         params=[sp("label")], guards=[guard("g", "ASK { SERVICE <http://example.invalid/> { ?s ?p ?o } }")]),
    "guard-syntax": act("ActionTestBadGuardSyn", "test-bad-guard-syn", [new_criterion_step(slug_const="acGx")],
                        params=[sp("label")], guards=[guard("g", "ASK { ?s ?p }")]),
    # 绑定引用未声明的参数 / fromStep 指向后面的步骤
    "binding-undeclared-param": act("ActionTestBadUndecl", "test-bad-undecl", [new_criterion_step(slug_const="acUd")],
                                    params=[sp("other")]),
    "from-step-forward": act("ActionTestBadForward", "test-bad-forward",
                             [("rel", "BasicAddRelationship", [b("type", "constant", "am4:Aggregation"),
                                                               b("source", "constant", f"<{REQ}>"),
                                                               b("target", "fromStep", "STEP(el)")]),
                              new_criterion_step(slug_const="acFwd")],
                             params=[sp("label")]),
    # 步骤缺必填入参；写工具没有的入参
    "step-missing-required": act("ActionTestBadMissing", "test-bad-missing",
                                 [("el", "BasicAddElement", [b("model", "constant", f"<{WB}>"),
                                                             b("prefLabel", "constant", '"x"')])]),
    "step-unknown-argument": act("ActionTestBadUnkArg", "test-bad-unk-arg",
                                 [new_criterion_step(slug_const="acUa", extra=[b("cascade", "constant", '"true"')])],
                                 params=[sp("label")]),
    # 想把两段式改低的字段（目录里没有这样的字段，多出来的谓词判无效）
    "risk-level-field": act("ActionTestBadRisk", "test-bad-risk", [("rm", "BasicRemove", [b("iri", "fromParameter", "ap:iri")])],
                            params=[sp("iri", iri=True)], extra='aisep:riskLevel "low"'),
    # 版本不合 semver；中文标题缺失由 EA3 管，这里只测版本
    "version-not-semver": act("ActionTestBadVer", "test-bad-ver", [new_criterion_step(slug_const="acVer")],
                              params=[sp("label")], version="v1"),
}

RAW_BAD = {
    # 表不以 rdf:nil 结尾（表断在半截，接到一个 IRI 上）
    "list-not-terminated": """
aisep:ActionTestBadOpenList a aisep:ActionType ; dcterms:identifier "test-bad-open-list" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ] ;
    aisep:steps [ rdf:first [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                              aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ;
                  rdf:rest <https://aisep.example/model/workbench/notNil> ] .
""",
    # 表的一个节点有两个 rdf:first（同一位置两个步骤）
    "list-node-two-firsts": """
aisep:ActionTestBadTwoFirst a aisep:ActionType ; dcterms:identifier "test-bad-two-first" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ] ;
    aisep:steps [ rdf:first [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                              aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ,
                            [ a aisep:ActionStep ; dcterms:identifier "rm2" ; aisep:invokes aisep:BasicRemove ;
                              aisep:binding [ aisep:argument "iri" ; aisep:constant <https://aisep.example/model/workbench/acNone> ] ] ;
                  rdf:rest rdf:nil ] .
""",
    # 表节点缺 rdf:first（中间缺一步）
    "list-node-without-first": """
aisep:ActionTestBadHole a aisep:ActionType ; dcterms:identifier "test-bad-hole" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ] ;
    aisep:steps [ rdf:first [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                              aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ;
                  rdf:rest [ rdf:rest [ rdf:first [ a aisep:ActionStep ; dcterms:identifier "rm2" ; aisep:invokes aisep:BasicRemove ;
                                                     aisep:binding [ aisep:argument "iri" ; aisep:constant <https://aisep.example/model/workbench/acNone> ] ] ;
                                        rdf:rest rdf:nil ] ] ] .
""",
    # 表成环
    "list-cycle": """
aisep:ActionTestBadCycle a aisep:ActionType ; dcterms:identifier "test-bad-cycle" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ] ;
    aisep:steps _:cyc1 .
_:cyc1 rdf:first [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                   aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ;
       rdf:rest _:cyc1 .
""",
    # 空表
    "empty-steps": """
aisep:ActionTestBadEmpty a aisep:ActionType ; dcterms:identifier "test-bad-empty" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; aisep:steps () .
""",
    # 步骤写成 IRI 节点（会逃出 definitionDigest）
    "step-is-iri": """
aisep:ActionTestBadIriStep a aisep:ActionType ; dcterms:identifier "test-bad-iri-step" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter [ sh:path ap:iri ; sh:nodeKind sh:IRI ] ;
    aisep:steps ( <https://aisep.example/model/workbench/stepX> ) .
<https://aisep.example/model/workbench/stepX> a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
    aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] .
""",
    # 动作是空白节点
    "action-is-blank": """
[] a aisep:ActionType ; dcterms:identifier "test-bad-blank" ; skos:prefLabel "测试动作"@zh ; owl:versionInfo "1.0.0" ;
    aisep:steps ( [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                    aisep:binding [ aisep:argument "iri" ; aisep:constant <https://aisep.example/model/workbench/acNone> ] ] ) .
""",
    # 两个动作共用同一个空白节点（X10）
    "shared-blank-node": """
aisep:ActionTestBadShareA a aisep:ActionType ; dcterms:identifier "test-bad-share-a" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter _:sharedParam ;
    aisep:steps ( [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                    aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ) .
aisep:ActionTestBadShareB a aisep:ActionType ; dcterms:identifier "test-bad-share-b" ; skos:prefLabel "测试动作"@zh ;
    owl:versionInfo "1.0.0" ; sh:parameter _:sharedParam ;
    aisep:steps ( [ a aisep:ActionStep ; dcterms:identifier "rm" ; aisep:invokes aisep:BasicRemove ;
                    aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ] ) .
_:sharedParam sh:path ap:iri ; sh:nodeKind sh:IRI .
""",
    # steps 的宾语是字面量、版本是整数、标题不是 @zh：执行器预料之外的形状也只能判这一条无效
    "odd-literals": """
aisep:ActionTestBadOdd a aisep:ActionType ; dcterms:identifier 42 ; skos:prefLabel "no tag" ;
    owl:versionInfo 1 ; sh:parameter "x" ; aisep:guard "y" ; aisep:steps "z" .
""",
    # 与已有动作 id 重复：两条都无效（X9）
    "duplicate-action-id": act("ActionTestBadSameId", "test-dup-id", [new_criterion_step(slug_const="acDi1")], params=[sp("label")])
                           + act("ActionTestBadSameIdToo", "test-dup-id", [new_criterion_step(slug_const="acDi2")],
                                 params=[sp("label")]),
    # 绑定常量是 RDF 1.2 三元组项：pyoxigraph 能解析，规则 EA/X 都没预料到，definitionDigest 重新解析时才出错，
    # 只能靠 load_catalog 的兜底分支判这一条无效（原因以「定义校验出错」开头，见 FALLBACK_CASES）
    "triple-term-constant": act("ActionTestBadTripleTerm", "test-bad-triple-term",
                                [new_criterion_step(slug_const="acTt", extra=[
                                    b("definition", "constant", f"<<( <{WB}a> <{WB}b> <{WB}c> )>>")])],
                                params=[sp("label")]),
}
FALLBACK_CASES = {"triple-term-constant"}

ALL_BAD = dict(BAD_DEFS, **RAW_BAD)
BAD_IRIS = {k: sorted(AISEP + m for m in re.findall(r"^aisep:(ActionTest\w+) a aisep:ActionType", v, re.M))
            for k, v in ALL_BAD.items()}


def test_bad_definition_fixtures_are_well_formed():
    """坏定义只坏在要测的那一点：每个片段本身是合法 Turtle（否则测到的是 PARSE_FAILED）。"""
    head = "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + open(os.path.join(ROOT, CAT), encoding="utf-8").read()
    for k, v in ALL_BAD.items():
        list(ox.parse(input=(head + GOOD_EXTRA + v).encode("utf-8"), format=ox.RdfFormat.TURTLE))
        assert BAD_IRIS[k] or k == "action-is-blank", k


@pytest.fixture
def good_extra_repo(mk):
    """控制组：只加一条好的测试动作，它和两个真实动作都有效。"""
    r = mk()
    add_actions(r, GOOD_EXTRA)
    lst = listing(r)
    assert lst[AISEP + "ActionTestGood"]["valid"] is True, lst[AISEP + "ActionTestGood"]
    return r


def test_good_extra_action_is_valid_and_runs(good_extra_repo):
    r = good_extra_repo
    res = apply(r, "test-good", {"label": "好动作"})
    assert res["changed"] is True and res["iris"]["el"] == WB + "acGoodOne"


@pytest.mark.parametrize("case", sorted(ALL_BAD))
def test_bad_definition_is_isolated(mk, case):
    r = mk()
    add_actions(r, GOOD_EXTRA, ALL_BAD[case])
    before = snap(r)
    is_err, res = call(r, "model_list_actions")
    assert not is_err, res
    entries = res["actions"]
    lst = {a["iri"]: a for a in entries if a["iri"]}
    # 坏的这条（或几条）判无效，带以规则号开头的原因
    if case == "action-is-blank":
        bad = [a for a in entries if a["iri"] is None]
        assert len(bad) == 1
    else:
        bad = [lst[i] for i in BAD_IRIS[case]]
    for a in bad:
        assert a["valid"] is False, (case, a)
        rule = r"定义校验出错：" if case in FALLBACK_CASES else r"(EA|X)\d+\b"
        assert a["problems"] and all(re.match(rule, p) for p in a["problems"]), (case, a["problems"])
        assert "definitionDigest" not in a
    # 其余照常：两个真实动作和控制组的好动作都有效
    for iri in (AISEP + "ActionRegisterAcceptanceCriterion", AISEP + "ActionRemoveElement", AISEP + "ActionTestGood"):
        assert lst[iri]["valid"] is True, (case, lst[iri])
    # 坏的不能执行：INVALID_ARGUMENT，绝不 INTERNAL
    for a in bad:
        name = a["id"] if a["id"] is not None else "test-bad-blank"
        for kw in ({}, {"dryRun": True}, {"planDigest": ZERO}):
            is_err, out = call(r, "model_apply_action", action=name, params={}, **kw)
            assert is_err and out["error"]["code"] == "INVALID_ARGUMENT", (case, name, out)
    for name in ("test-bad-nl", "test-bad-nl\n"):
        assert code_of(r, "model_apply_action", action=name, params={"label": "x"}) == "INVALID_ARGUMENT"
    assert snap(r) == before
    # 其余照常可执行
    assert apply(r, REGISTER, P0, dryRun=True)["changed"] is True
    assert apply(r, "test-good", {"label": "好动作"})["changed"] is True


@pytest.mark.parametrize("ident", ["test-nl\n", "test-nl\r\n", "Test-upper", "1test", "test nl", "a" * 65])
def test_action_identifier_must_match_to_the_end(mk, ident):
    r = mk()
    add_actions(r, act("ActionTestIdent", ident, [new_criterion_step(slug_const="acIdent")], params=[sp("label")]))
    a = listing(r)[AISEP + "ActionTestIdent"]
    assert a["valid"] is False and a["id"] is None, a
    assert code_of(r, "model_apply_action", action=ident, params={"label": "x"}) == "INVALID_ARGUMENT"
    assert code_of(r, "model_apply_action", action=ident.strip(), params={"label": "x"}) == "INVALID_ARGUMENT"


def test_unparsable_catalogue_is_parse_failed_not_internal(mk):
    r = mk()
    append(r, CAT, "\naisep:Broken a aisep:ActionType ; dcterms:identifier \"x\" \n")   # 少一个句点
    before = snap(r)
    assert err(r, "model_list_actions")["code"] == "PARSE_FAILED"
    for kw in ({}, {"dryRun": True}):
        assert apply_err(r, REGISTER, P0, **kw)["code"] == "PARSE_FAILED"
    assert snap(r) == before


def test_missing_catalogue_lists_no_actions(mk):
    r = mk()
    shutil.rmtree(r / "modules" / "ext-actions")
    res = ok(r, "model_list_actions")
    assert res["actions"] == []
    assert apply_err(r, REGISTER, P0)["code"] == "INVALID_ARGUMENT"


def test_catalogue_is_reread_on_every_call(mk):
    r = mk()
    assert AISEP + "ActionTestGood" not in listing(r)
    add_actions(r, GOOD_EXTRA)
    assert listing(r)[AISEP + "ActionTestGood"]["valid"] is True
    write(r, CAT, read(r, CAT).replace('"test-good"', '"test-good-renamed"'))
    assert listing(r)[AISEP + "ActionTestGood"]["id"] == "test-good-renamed"


# ------------------------------------------------------------------ 目录只读所服务的工作区，不随 repo 参数切换

def feature_worktree(r, tmp_path):
    """r 的一个 linked worktree（未合并的特性分支），放在 cfg(r) 的 allow-root 之下。"""
    w = tmp_path / "feature"
    git(r, "worktree", "add", "-q", "-b", "feature", str(w))
    return w


def call_in(served, repo, name, **args):
    """服务器服务 served（--repo），调用方用 repo 参数指向另一个工作区。"""
    r = server.call(cfg(served), name, dict(args, repo=str(repo)))
    return r.is_error, r.structured_content


def test_action_added_in_an_unmerged_worktree_does_not_run_there(mk, tmp_path):
    """特性分支 worktree 的目录副本里新增的动作：调用方带 repo 指向那个 worktree 也执行不了，与 model_list_actions 一致。"""
    r = mk()
    w = feature_worktree(r, tmp_path)
    append(w, CAT, "\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + GOOD_EXTRA)
    assert AISEP + "ActionTestGood" not in listing(r)
    is_err, res = call_in(r, w, "model_apply_action", action="test-good", params={"label": "未合并的动作"})
    assert is_err and res["error"]["code"] == "INVALID_ARGUMENT", res
    assert "test-good" not in res["error"]["details"]["available"]
    assert git(w, "status", "--porcelain", "--", "models") == ""


def test_guard_removed_in_an_unmerged_worktree_still_applies(mk, tmp_path):
    """worktree 副本里删掉动作的 guard：带 repo 指向它执行，仍按所服务工作区里的定义判 guard。"""
    r = mk()
    w = feature_worktree(r, tmp_path)
    text = read(w, CAT)
    cut = re.sub(r"aisep:guard\s*\[.*?\]\s*,\s*\[.*?\]\s*;", "", text, count=1, flags=re.S)
    assert cut != text and "parent-is-not-a-criterion" not in cut
    write(w, CAT, cut)
    is_err, res = call_in(r, w, "model_apply_action", action=REGISTER, params=dict(P0, requirement=AC))
    assert is_err and res["error"]["code"] == "PRECONDITION_FAILED", res
    assert [g["id"] for g in res["error"]["details"]["failedGuards"]] == ["parent-is-not-a-criterion"]
    assert git(w, "status", "--porcelain", "--", "models") == ""


def test_served_catalogue_runs_against_the_callers_worktree(mk, tmp_path):
    """反方向：动作只在所服务工作区的目录里（worktree 副本没有它），带 repo 指向 worktree 照样执行，写进那个 worktree。"""
    r = mk()
    w = feature_worktree(r, tmp_path)
    append(r, CAT, "\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + GOOD_EXTRA)
    assert "ActionTestGood" not in read(w, CAT)
    is_err, res = call_in(r, w, "model_apply_action", action="test-good", params={"label": "所服务目录里的动作"})
    assert not is_err, res
    assert res["changed"] is True and res["iris"]["el"] == WB + "acGoodOne"
    assert git(w, "status", "--porcelain", "--", "models") != ""
    assert git(r, "status", "--porcelain", "--", "models") == ""


# ================================================================== B1 结果等价

B1_CASES = {
    "default-files": P0,
    "split-files": dict(P0, file=GOV, relationshipFile=AM4),          # 两步落在不同文件，且都不是默认落点
    "element-elsewhere": dict(P0, file=AM4),                           # 只改元素落点，关系按默认规则
    "slug-no-optional": {"requirement": REQ, "prefLabel": "只给必填项", "slug": "acProbeMinimal"},
    "quotes-and-newlines": dict(P0, prefLabel="含\"引号\"与 'x' 的名称", altLabel="Probe; with } > chars",
                                gherkin="Given \"a\" ; }\nWhen <b> \\ c\nThen '''d'''"),
    "other-model": {"requirement": PC_REQ, "prefLabel": "采购模型的验收标准", "altLabel": "Procurement probe criterion",
                    "gherkin": "Given x\nWhen y\nThen z"},
}


@pytest.mark.parametrize("case", sorted(B1_CASES))
def test_B1_action_equals_sequential_write_tools(mk, case):
    p = B1_CASES[case]
    a, b_ = mk("action"), mk("sequential")
    start = snap(a)
    assert start == snap(b_)
    res = apply(a, REGISTER, p)
    seq = sequential(b_, p)
    assert [e for e, _ in seq] == [False, False], f"对照写法本身失败，用例构造有误：{seq}"
    el, rel = seq[0][1], seq[1][1]
    assert el["changed"] is True and rel["changed"] is True
    assert snap(b_) != start                       # 对照确实写了东西，等价不是空等价
    assert_same_models(a, b_)
    assert res["changed"] is True
    assert sorted(res["iris"].values()) == sorted([el["iri"], rel["iri"]])
    want_files = {f["path"] for r in (el, rel) for f in r["filesChanged"]}
    assert {f["path"] for f in res["filesChanged"]} == want_files
    if case == "split-files":
        assert want_files == {GOV, AM4}             # 两步确实落在两个不同文件
    assert git(a, "diff", "--cached", "--name-only") == ""   # 不 git add


def test_B1_partly_existing_start_state(mk):
    """元素已经由写工具加过、关系还没有：动作补上的关系与单独调 model_add_relationship 逐字节相同。"""
    a, b_ = mk("action"), mk("sequential")
    for r in (a, b_):
        e = ok(r, "model_add_element", model=WB, type="aisep:AcceptanceCriterion", prefLabel=P0["prefLabel"],
               altLabel=P0["altLabel"], definition=P0["definition"],
               attributes=[{"predicate": "aisep:gherkin", "value": {"value": P0["gherkin"]}}])
    assert_same_models(a, b_)
    res = apply(a, REGISTER, P0)
    rel = ok(b_, "model_add_relationship", type="am4:Aggregation", source=REQ, target=e["iri"])
    assert res["changed"] is True and rel["changed"] is True
    assert_same_models(a, b_)


def test_B1_dry_run_writes_nothing_and_predicts_the_same_bytes(mk):
    a, b_ = mk("action"), mk("sequential")
    start = snap(a)
    d = apply(a, REGISTER, dict(P0, file=GOV, relationshipFile=AM4), dryRun=True)
    assert snap(a) == start
    seq = sequential(b_, dict(P0, file=GOV, relationshipFile=AM4))
    assert [e for e, _ in seq] == [False, False]
    after = snap(b_)
    predicted = {f["path"]: f["sha256After"] for f in d["filesChanged"]}
    changed = {f: h for f, h in after.items() if start[f] != h}
    assert {f: h.removeprefix("sha256:") for f, h in predicted.items()} == changed


def test_B1_set_attributes_step_equals_model_set_attributes(mk):
    """新加入的基本动作 BasicSetAttributes：经动作调用与直接调 model_set_attributes 逐字节相同。"""
    a, b_ = mk("action"), mk("control")
    add_actions(a, act("ActionTestSetGherkin", "test-set-gherkin",
                       [("s", "BasicSetAttributes", [b("iri", "fromParameter", "ap:iri"),
                                                     b("set", "fromParameter", "ap:text", pred="aisep:gherkin")])],
                       params=[sp("iri", iri=True), sp("text")]))
    assert by_id(a)["test-set-gherkin"]["valid"] is True
    text = "Given 新的\nWhen 改\nThen 好"
    res = apply(a, "test-set-gherkin", {"iri": AC, "text": text})
    ctl = ok(b_, "model_set_attributes", iri=AC, set=[{"predicate": "aisep:gherkin", "value": {"value": text}}])
    assert res["changed"] is True and ctl["changed"] is True
    assert_same_models(a, b_)
    assert literal_values(a, VER, AC, AISEP + "gherkin") == [text]


# ================================================================== B2 拒绝零写入

def test_B2_guard_failure_parent_is_a_criterion(mk):
    r = mk()
    before = snap(r)
    e = apply_err(r, REGISTER, dict(P0, requirement=AC))
    assert e["code"] == "PRECONDITION_FAILED"
    assert snap(r) == before
    assert e.get("hint")
    assert [g["id"] for g in e["details"]["failedGuards"]] == ["parent-is-not-a-criterion"]
    assert git(r, "status", "--porcelain") == ""


def test_B2_guard_failure_parent_is_deprecated(mk):
    r = mk()
    append(r, AM4, f"\n:reqRejectRelease {OWL_DEPRECATED} true .\n")
    before = snap(r)
    e = apply_err(r, REGISTER, dict(P0, requirement=REQ2))
    assert e["code"] == "PRECONDITION_FAILED"
    assert [g["id"] for g in e["details"]["failedGuards"]] == ["parent-is-not-deprecated"]
    assert snap(r) == before
    r2 = mk("control")                              # 没退役的需求上同样的参数能成功（拒绝确实来自这条 guard）
    assert apply(r2, REGISTER, dict(P0, requirement=REQ2))["changed"] is True


B2_STEP_REFUSALS = {
    "step1-iri-exists": (dict(P0, slug="reqApprovalProgress"), 0),
    "step1-bad-file": (dict(P0, file="models/procurement/am4.ttl"), 0),
    "step2-bad-file": (dict(P0, relationshipFile="models/procurement/am4.ttl"), 1),
    "step2-file-not-ttl": (dict(P0, relationshipFile="models/workbench/requirements-release.md"), 1),
}


@pytest.mark.parametrize("case", sorted(B2_STEP_REFUSALS))
def test_B2_step_refused_writes_nothing(mk, case):
    p, failing_step = B2_STEP_REFUSALS[case]
    a, b_ = mk("action"), mk("sequential")
    before = snap(a)
    seq = sequential(b_, p)
    assert len(seq) == failing_step + 1 and seq[-1][0], f"对照写法没有在第 {failing_step + 1} 步被拒，用例构造有误：{seq}"
    want = seq[-1][1]["error"]["code"]
    assert want != "WRITE_REJECTED"
    if failing_step == 1:
        assert snap(b_) != before                   # 顺序调用确实留下了第一步
    e = apply_err(a, REGISTER, p)
    assert e["code"] == want
    assert e["details"].get("step") == ["criterion", "aggregation"][failing_step]
    assert snap(a) == before
    assert git(a, "status", "--porcelain") == ""


def test_B2_step_refused_endpoint_missing(mk):
    r = mk()
    before = snap(r)
    e = apply_err(r, REGISTER, dict(P0, requirement=WB + "noSuchRequirement"))
    assert e["code"] == "ELEMENT_NOT_FOUND"
    assert snap(r) == before


def test_B2_candidate_graph_violation_writes_nothing(mk):
    """父对象是 BPMN 节点：第一步合法，第二步（am4:Aggregation 跨记法）使候选图新增 L1 违规。"""
    p = dict(P0, requirement=BPMN_NODE)
    a, b_ = mk("action"), mk("sequential")
    before = snap(a)
    seq = sequential(b_, p)
    assert [e for e, _ in seq] == [False, True], f"用例构造有误：{seq}"
    assert seq[1][1]["error"]["code"] == "WRITE_REJECTED"
    assert snap(b_) != before
    assert apply_err(a, REGISTER, p)["code"] == "WRITE_REJECTED"
    assert snap(a) == before
    assert git(a, "status", "--porcelain") == ""
    assert apply_err(a, REGISTER, p, dryRun=True)["code"] == "WRITE_REJECTED"
    assert snap(a) == before


def test_B2_bad_params_write_nothing(mk):
    r = mk()
    before = snap(r)
    for p in ({"prefLabel": "缺 requirement"}, dict(P0, extra="x"), dict(P0, prefLabel=7), dict(P0, requirement=None)):
        assert apply_err(r, REGISTER, p)["code"] == "INVALID_ARGUMENT", p
    assert err(r, "model_apply_action", action="no-such-action", params={})["code"] == "INVALID_ARGUMENT"
    assert snap(r) == before


# ================================================================== B3 guard 不是不变式

HANDWRITTEN_AC = """
:acHandWritten a aisep:AcceptanceCriterion ;
    arch:inModel <https://aisep.example/model/workbench/> ;
    skos:prefLabel "手写的验收标准"@zh ;
    skos:altLabel "Hand-written criterion"@en ;
    aisep:gherkin "Given a\\nWhen b\\nThen c" .

:rel-%(parent)s-aggregates-acHandWritten a am4:Aggregation ;
    arch:inModel <https://aisep.example/model/workbench/> ;
    arch:source :%(parent)s ;
    arch:target :acHandWritten .
"""
B3_GUARDS = {  # guard id -> (父对象本地名, 先手写进 am4.ttl 的前置内容)
    "parent-is-not-a-criterion": ("acProgressFourStages", ""),
    "parent-is-not-deprecated": ("reqRejectRelease", f"\n:reqRejectRelease {OWL_DEPRECATED} true .\n"),
}


def test_B3_every_guard_of_the_catalogue_is_covered():
    """目录里的 guard（从 catalog.ttl 的三元组直接取，不经执行器）与本文件 B3 覆盖的一致。"""
    st = ox.Store()
    st.load(path=os.path.join(ROOT, CAT), format=ox.RdfFormat.TURTLE)
    rows = st.query("""PREFIX aisep: <https://aisep.example/ont/aisep#> PREFIX dcterms: <http://purl.org/dc/terms/>
        SELECT ?id WHERE { ?a a aisep:ActionType ; aisep:guard ?g . ?g dcterms:identifier ?id }""")
    assert sorted(r["id"].value for r in rows) == sorted(B3_GUARDS)


def test_B3_control_gate_passes_untouched_and_sees_worktree_edits(mk):
    r = mk()
    assert gate(r)[0] == "PASS"
    append(r, VER, "\n:acProgressFourStages am4:aggregates :reqApprovalProgress .\n")  # 直连三元组：L1 违规
    assert gate(r)[0] == "FAIL", "gate 没有看到工作区里的手写违规，B3 的 PASS 就不能说明问题"


@pytest.mark.parametrize("guard_id", sorted(B3_GUARDS))
@pytest.mark.parametrize("how", ["handwritten", "write-tools"])
def test_B3_guard_refused_content_passes_gate(mk, guard_id, how):
    parent, setup = B3_GUARDS[guard_id]
    r = mk()
    if setup:
        append(r, AM4, setup)
    p = dict(P0, requirement=WB + parent, slug="acHandWritten")
    e = apply_err(r, REGISTER, p)                       # 动作确实拒绝这份内容，且拒绝来自这条 guard
    assert e["code"] == "PRECONDITION_FAILED"
    assert [g["id"] for g in e["details"]["failedGuards"]] == [guard_id]
    before = snap(r)
    if how == "handwritten":
        append(r, VER, HANDWRITTEN_AC % {"parent": parent})
    else:                                               # 原子写工具不受 guard 约束
        seq = sequential(r, p)
        assert [x for x, _ in seq] == [False, False], seq
    assert snap(r) != before
    result, out = gate(r)
    assert result == "PASS", f"guard {guard_id} 与已有规则重复（gate 对它拒绝的内容判 FAIL）：\n{out[-1500:]}"


# ================================================================== B4 动作层不放宽合法性

def test_B4_step_introducing_l1_violation_is_write_rejected(mk):
    a, b_ = mk("action"), mk("control")
    add_actions(a, act("ActionTestBadL1", "test-bad-l1",
                       [new_criterion_step(slug_const="acBadL1",
                                           extra=[b("attributes", "constant", '"x"', pred=f"<{UNDECLARED}>")])],
                       params=[sp("label")]))
    assert by_id(a)["test-bad-l1"]["valid"] is True     # 定义本身合规，违规只在候选图里
    before = snap(a)
    assert code_of(b_, "model_add_element", model=WB, type="aisep:AcceptanceCriterion", prefLabel="坏的", slug="acBadL1",
                   attributes=[{"predicate": UNDECLARED, "value": {"value": "x"}}]) == "WRITE_REJECTED"
    for kw in ({}, {"dryRun": True}):
        assert apply_err(a, "test-bad-l1", {"label": "坏的"}, **kw)["code"] == "WRITE_REJECTED"
    assert snap(a) == before
    assert git(a, "status", "--porcelain") == ""


def test_B4_violation_in_a_later_step_rolls_back_earlier_steps(mk):
    a, b_ = mk("action"), mk("control")
    add_actions(a, act("ActionTestBadSecond", "test-bad-second",
                       [new_criterion_step(slug_const="acBadSecond"),
                        ("rel", "BasicAddRelationship", [b("type", "constant", "am4:Assignment"),
                                                         b("source", "constant", f"<{BPMN_NODE}>"),
                                                         b("target", "fromStep", "STEP(el)")])],
                       params=[sp("label")]))
    assert by_id(a)["test-bad-second"]["valid"] is True
    before = snap(a)
    el = ok(b_, "model_add_element", model=WB, type="aisep:AcceptanceCriterion", prefLabel="第二步坏", slug="acBadSecond")
    assert code_of(b_, "model_add_relationship", type="am4:Assignment", source=BPMN_NODE, target=el["iri"]) == "WRITE_REJECTED"
    assert apply_err(a, "test-bad-second", {"label": "第二步坏"})["code"] == "WRITE_REJECTED"
    assert snap(a) == before


@pytest.mark.parametrize("ptype", ["aisep:ApprovalRecord", "aisep:AgentActivity", "aisep:ActionType"])
def test_B4_step_adding_protected_type_is_refused(mk, ptype):
    a, b_ = mk("action"), mk("control")
    add_actions(a, act("ActionTestProtected", "test-protected",
                       [("el", "BasicAddElement", [b("model", "constant", f"<{WB}>"), b("type", "constant", ptype),
                                                   b("prefLabel", "constant", '"伪造的记录"'),
                                                   b("slug", "constant", '"forgedRecord"')])]))
    assert by_id(a)["test-protected"]["valid"] is True
    before = snap(a)
    # ADR-030: aisep:ActionType is a tool-zone class, not in the write tools' (domain) class table -> UNKNOWN_TYPE
    want = "UNKNOWN_TYPE" if ptype == "aisep:ActionType" else "PROTECTED_RESOURCE"
    assert code_of(b_, "model_add_element", model=WB, type=ptype, prefLabel="伪造的记录", slug="forgedRecord") == want
    for kw in ({}, {"dryRun": True}):
        assert apply_err(a, "test-protected", {}, **kw)["code"] == want
    assert snap(a) == before


@pytest.mark.parametrize("op", ["set_labels", "set_attributes"])
def test_B4_change_step_on_approval_record_is_refused(mk, op):
    a, b_ = mk("action"), mk("control")
    if op == "set_labels":
        step = ("s", "BasicSetLabels", [b("iri", "fromParameter", "ap:iri"), b("prefLabel", "constant", '"改掉的名字"')])
        want = code_of(b_, "model_set_labels", iri=APPROVAL, prefLabel="改掉的名字")
    else:
        step = ("s", "BasicSetAttributes", [b("iri", "fromParameter", "ap:iri"),
                                            b("set", "constant", '"x"', pred="aisep:gherkin")])
        want = code_of(b_, "model_set_attributes", iri=APPROVAL, set=[{"predicate": "aisep:gherkin", "value": {"value": "x"}}])
    assert want == "PROTECTED_RESOURCE"
    add_actions(a, act("ActionTestRelabel", "test-relabel", [step], params=[sp("iri", iri=True)]))
    assert by_id(a)["test-relabel"]["valid"] is True
    before = snap(a)
    assert apply_err(a, "test-relabel", {"iri": APPROVAL})["code"] == want
    assert snap(a) == before


def test_B4_remove_action_on_protected_resources_is_refused(mk):
    a, b_ = mk("action"), mk("control")
    before = snap(a)
    assert code_of(b_, "model_remove", iri=APPROVAL, cascade=True, dryRun=True) == "PROTECTED_RESOURCE"
    for kw in ({"dryRun": True}, {}, {"planDigest": ZERO}):
        assert apply_err(a, REMOVE, {"iri": APPROVAL}, **kw)["code"] == "PROTECTED_RESOURCE", kw
    for kw in ({"dryRun": True}, {}):
        assert apply_err(a, REMOVE, {"iri": WB}, **kw)["code"] in ("PROTECTED_RESOURCE", "INVALID_ARGUMENT")
    assert snap(a) == before


def test_B4_any_action_with_a_remove_step_is_two_phase(mk):
    """两段式由执行器从步骤推导：remove 放在别的步骤后面，照样不带 planDigest 就不执行。"""
    r = mk()
    add_actions(r, act("ActionTestRelabelThenRemove", "test-relabel-then-remove",
                       [("lab", "BasicSetLabels", [b("iri", "constant", f"<{REQ}>"), b("definition", "constant", '"顺手改一下"')]),
                        ("rm", "BasicRemove", [b("iri", "fromParameter", "ap:iri")])],
                       params=[sp("iri", iri=True)]))
    T, _ = plant(r)
    commit_all(r, "planted")
    before = snap(r)
    a = by_id(r)["test-relabel-then-remove"]
    assert a["valid"] is True and a["destructive"] is True and a["requiresPlanDigest"] is True
    e = apply_err(r, "test-relabel-then-remove", {"iri": T})
    assert e["code"] == "PLAN_REQUIRED", e
    assert snap(r) == before
    d = apply(r, "test-relabel-then-remove", {"iri": T}, dryRun=True)
    assert d["planDigest"] == e["details"]["planDigest"]
    assert apply(r, "test-relabel-then-remove", {"iri": T}, planDigest=d["planDigest"])["changed"] is True


# ================================================================== B5 契约不随数据变

LIST_SCRIPT = r"""
import json, os, sys, anyio
from mcp import Client, StdioServerParameters
repo, root, profile = sys.argv[1:4]
async def go():
    p = StdioServerParameters(command=sys.executable, cwd=repo, env=dict(os.environ),
                              args=["-m", "aisep.server", "--repo", repo, "--allow-root", root, "--profile", profile])
    async with Client(p) as c:
        tl = (await c.list_tools()).tools
        la = await c.call_tool("model_list_actions", {}) if any(t.name == "model_list_actions" for t in tl) else None
        return {"tools": [t.model_dump(mode="json", by_alias=True) for t in tl],
                "actions": None if la is None else la.structured_content}
print(json.dumps(anyio.run(go), sort_keys=True, ensure_ascii=False))
"""


def stdio_listing(repo, profile, script):
    """真实 stdio 服务器（被测检出的代码，PYTHONPATH=ROOT），服务的是副本。返回 (规范化的 tools/list, 动作目录)。"""
    p = subprocess.run([PY, str(script), str(repo), str(repo.parent), profile], capture_output=True, text=True,
                       cwd=str(repo), env=dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1"), timeout=180)
    assert p.returncode == 0, p.stderr[-2000:]
    doc = json.loads(p.stdout.strip().splitlines()[-1])
    return json.dumps(sorted(doc["tools"], key=lambda t: t["name"]), sort_keys=True, ensure_ascii=False), doc["actions"]


@pytest.mark.parametrize("profile", ["agent", "all"])
def test_B5_tools_list_does_not_change_with_the_catalogue(mk, tmp_path, profile):
    script = tmp_path / "list_tools.py"
    script.write_text(LIST_SCRIPT, encoding="utf-8")
    r = mk()
    before, actions_before = stdio_listing(r, profile, script)
    names = [t["name"] for t in json.loads(before)]
    assert "model_list_actions" in names and "model_apply_action" in names
    # 往 modules/ext-actions 的定义文件里加一个好动作、一个坏动作，并删掉一个现有动作
    text = read(r, CAT)
    start = text.index("aisep:ActionRemoveElement a aisep:ActionType")
    write(r, CAT, text[:start])
    add_actions(r, GOOD_EXTRA, BAD_DEFS["unknown-basic-action"])
    after, actions_after = stdio_listing(r, profile, script)
    assert after == before, "tools/list 随目录数据变了"
    ids_before = [a["id"] for a in actions_before["actions"]]
    ids_after = [a["id"] for a in actions_after["actions"]]
    assert "test-good" in ids_after and "test-good" not in ids_before     # 目录的变化确实被服务器读到了
    assert REMOVE in ids_before and REMOVE not in ids_after


def test_B5_in_process_tool_table_is_fixed_and_new_action_is_usable(mk):
    r = mk()

    def table():
        return json.dumps({n: [server.TOOLS[n][1], server.TOOLS[n][2], server.TOOLS[n][3], server.TOOLS[n][4]]
                           for n in server.listed("all")}, sort_keys=True, ensure_ascii=False)
    before = table()
    add_actions(r, GOOD_EXTRA)
    assert table() == before
    schema = server.TOOLS["model_apply_action"][2]
    assert set(schema["properties"]) == {"action", "params", "dryRun", "planDigest", "repo"}
    assert "label" not in json.dumps(schema)
    assert server.TOOLS["model_list_actions"][2]["properties"] == {}
    assert apply(r, "test-good", {"label": "经通用入口加的"})["changed"] is True


# ================================================================== B6 幂等

@pytest.mark.parametrize("case", ["default-files", "split-files", "slug-no-optional"])
def test_B6_replay_returns_unchanged(mk, case):
    p = B1_CASES[case]
    r = mk()
    first = apply(r, REGISTER, p)
    assert first["changed"] is True
    after = snap(r)
    for kw in ({}, {"dryRun": True}, {}):
        is_err, res = call(r, "model_apply_action", action=REGISTER, params=p, **kw)
        assert not is_err, f"重放被拒绝：{res}"
        assert res["changed"] is False
        assert snap(r) == after
    assert sorted(res["iris"].values()) == sorted(first["iris"].values())


def test_B6_replay_does_not_run_guards(mk):
    r = mk()
    p = dict(P0, requirement=REQ2)
    assert apply(r, REGISTER, p)["changed"] is True
    append(r, AM4, f"\n:reqRejectRelease {OWL_DEPRECATED} true .\n")
    after = snap(r)
    is_err, res = call(r, "model_apply_action", action=REGISTER, params=p)
    assert not is_err, f"重放返回了拒绝：{res['error']['code']}"
    assert res["changed"] is False
    assert snap(r) == after
    assert apply_err(r, REGISTER, dict(p, slug="acNotAReplay"))["code"] == "PRECONDITION_FAILED"
    assert snap(r) == after


def test_B6_replay_of_remove_action(mk):
    """接口文档 §5.14：目标已不在且带了 planDigest -> changed:false、alreadyAbsent；不带 -> ELEMENT_NOT_FOUND。"""
    r = mk()
    T, _ = plant(r)
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    assert apply(r, REMOVE, {"iri": T}, planDigest=d["planDigest"])["changed"] is True
    after = snap(r)
    is_err, res = call(r, "model_apply_action", action=REMOVE, params={"iri": T}, planDigest=d["planDigest"])
    assert not is_err, f"重放被拒绝：{res}"
    assert res["changed"] is False
    assert res["steps"][0]["result"].get("alreadyAbsent") is True
    assert snap(r) == after
    assert apply_err(r, REMOVE, {"iri": T})["code"] == "ELEMENT_NOT_FOUND"
    assert snap(r) == after


def test_B6_replay_of_set_attributes_action(mk):
    r = mk()
    add_actions(r, act("ActionTestSetGherkin", "test-set-gherkin",
                       [("s", "BasicSetAttributes", [b("iri", "fromParameter", "ap:iri"),
                                                     b("set", "fromParameter", "ap:text", pred="aisep:gherkin")])],
                       params=[sp("iri", iri=True), sp("text")]))
    p = {"iri": AC, "text": "Given 重放\nWhen x\nThen y"}
    assert apply(r, "test-set-gherkin", p)["changed"] is True
    after = snap(r)
    assert apply(r, "test-set-gherkin", p)["changed"] is False
    assert snap(r) == after


def test_B6_replay_two_params_same_iri_is_unchanged(mk):
    """评审阻塞问题：两个不同参数在调用时填成同一 IRI（X6 判不出），各步先改后改回，合并后字节与磁盘相同。
    重放必须 changed:false、filesChanged 为空、不重写文件（mtime 不变），与依次调两次 model_set_labels 一致。"""
    r = mk()
    add_actions(r, act("ActionTestTwoSame", "test-two-same",
                       [("a", "BasicSetLabels", [b("iri", "fromParameter", "ap:t1"), b("prefLabel", "constant", '"甲名称"')]),
                        ("b", "BasicSetLabels", [b("iri", "fromParameter", "ap:t2"), b("prefLabel", "constant", '"乙名称"')])],
                       params=[sp("t1", iri=True), sp("t2", iri=True)]))
    p = {"t1": REQ, "t2": REQ}
    assert apply(r, "test-two-same", p)["changed"] is True
    after = snap(r)
    mtimes = {f: os.stat(r / f).st_mtime_ns for f in after}
    for kw in ({"dryRun": True}, {}):
        is_err, res = call(r, "model_apply_action", action="test-two-same", params=p, **kw)
        assert not is_err, f"重放被拒绝：{res}"
        assert res["changed"] is False
        assert res["filesChanged"] == []
    assert snap(r) == after
    assert {f: os.stat(r / f).st_mtime_ns for f in after} == mtimes


# ================================================================== B7 破坏性动作绑定计划

def plant(repo, slug="acDoomed"):
    """用现有写工具加一条没被批准记录引用的验收标准并挂到需求上，作删除目标。返回 (元素 IRI, 聚合关系 IRI)。"""
    seq = sequential(repo, {"requirement": REQ, "prefLabel": "待删除的验收标准 " + slug, "slug": slug,
                            "gherkin": "Given a\nWhen b\nThen c"})
    assert [e for e, _ in seq] == [False, False], seq
    return seq[0][1]["iri"], seq[1][1]["iri"]


def remove_plan(repo, iri):
    return ok(repo, "model_remove", iri=iri, cascade=True, dryRun=True)["plan"]


def test_B7_blocked_target_like_model_remove(mk):
    a, b_ = mk("action"), mk("control")
    before = snap(a)
    want = code_of(b_, "model_remove", iri=AC, cascade=True, dryRun=True)
    assert want != "OK"
    for kw in ({"dryRun": True}, {}, {"planDigest": ZERO}):
        is_err, res = call(a, "model_apply_action", action=REMOVE, params={"iri": AC}, **kw)
        assert is_err and res["error"]["code"] == want, (kw, res)
    assert snap(a) == before


def test_B7_dry_run_returns_plan_and_impact_and_writes_nothing(mk):
    r = mk()
    T, REL = plant(r)
    before = snap(r)
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    assert snap(r) == before
    assert isinstance(d["planDigest"], str) and d["planDigest"]
    want = remove_plan(r, T)
    assert {x["iri"] for x in want["delete"]} == {T, REL} and not want["blockers"]
    assert len(d["cascade"]) == 1
    got = d["cascade"][0]
    assert got["target"] == T
    assert got["delete"] == want["delete"] and got["detach"] == want["detach"] and got["blockers"] == want["blockers"]
    imp = ok(r, "model_impact", focus=T, mode="depends", depth=3)
    assert imp["items"], "夹具有误：目标应当有依赖它的元素"
    assert len(d["impact"]) == 1 and d["impact"][0]["focus"] == T
    assert [i["iri"] for i in d["impact"][0]["items"]] == [i["iri"] for i in imp["items"]][:50]
    assert d["impact"][0]["count"] == len(imp["items"])


def test_B7_execution_with_fresh_digest_equals_model_remove(mk):
    a, b_ = mk("action"), mk("control")
    T, _ = plant(a)
    assert plant(b_)[0] == T
    assert_same_models(a, b_)
    start = snap(a)
    d = apply(a, REMOVE, {"iri": T}, dryRun=True)
    res = apply(a, REMOVE, {"iri": T}, planDigest=d["planDigest"])
    assert res["changed"] is True
    dr = ok(b_, "model_remove", iri=T, cascade=True, dryRun=True)
    assert ok(b_, "model_remove", iri=T, cascade=True, planDigest=dr["planDigest"]).get("written") is True
    assert snap(b_) != start
    assert_same_models(a, b_)


def test_B7_without_plan_digest_is_refused_with_plan_and_impact(mk):
    r = mk()
    T, REL = plant(r)
    before = snap(r)
    e = apply_err(r, REMOVE, {"iri": T})
    assert e["code"] == "PLAN_REQUIRED"
    assert snap(r) == before
    det = e["details"]
    want = remove_plan(r, T)
    assert det["cascade"][0]["target"] == T and det["cascade"][0]["delete"] == want["delete"]
    assert {x["iri"] for x in det["cascade"][0]["delete"]} == {T, REL}
    assert det["impact"][0]["focus"] == T and "items" in det["impact"][0]
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    assert det["planDigest"] == d["planDigest"]
    assert snap(r) == before
    assert apply(r, REMOVE, {"iri": T}, planDigest=det["planDigest"])["changed"] is True
    assert snap(r) != before


def stale(repo, digest, params, action=REMOVE):
    before = snap(repo)
    e = apply_err(repo, action, params, planDigest=digest)
    assert e["code"] == "PLAN_STALE", e
    assert snap(repo) == before
    return e


def test_B7_wrong_digest_is_stale(mk):
    r = mk()
    T, _ = plant(r)
    stale(r, ZERO, {"iri": T})
    stale(r, "x", {"iri": T})


@pytest.mark.parametrize("change", ["new-reference", "comment-in-touched-file", "label-of-target"])
def test_B7_model_file_changed_after_dry_run(mk, change):
    r, c = mk(), mk("control")
    T, _ = plant(r)
    assert plant(c)[0] == T
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    dr = ok(c, "model_remove", iri=T, cascade=True, dryRun=True)
    touched = {f["path"] for f in d["filesChanged"]}
    assert touched == {f["path"] for f in dr["filesChanged"]} and touched
    f0 = sorted(touched)[0]
    for x in (r, c):
        if change == "new-reference":
            ok(x, "model_add_relationship", type="aisep:Verification", source=OTHER_TC, target=T)
        elif change == "comment-in-touched-file":
            append(x, f0, "\n# 评审后有人加了一行注释\n")
        else:
            ok(x, "model_set_labels", iri=T, definition="dryRun 之后改了定义")
    assert code_of(c, "model_remove", iri=T, cascade=True, planDigest=dr["planDigest"]) == "PLAN_STALE"
    stale(r, d["planDigest"], {"iri": T})
    d2 = apply(r, REMOVE, {"iri": T}, dryRun=True)
    assert d2["planDigest"] != d["planDigest"]
    assert apply(r, REMOVE, {"iri": T}, planDigest=d2["planDigest"])["changed"] is True


RM_BLOCK_END = 'aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ]\n    ) .'


def _edit_remove_action(text, change, t2):
    """改 catalog.ttl 里 aisep:ActionRemoveElement 的定义（文本替换，每种改动只动一处）。"""
    assert RM_BLOCK_END in text
    if change == "definition":
        return text.replace("再带 planDigest 执行。\"@zh", "再带 planDigest 执行（改过）。\"@zh")
    if change == "title":
        return text.replace('skos:prefLabel  "删除元素"@zh', 'skos:prefLabel  "删除元素（改过）"@zh')
    if change == "version":
        start = text.index("aisep:ActionRemoveElement")
        return text[:start] + text[start:].replace('owl:versionInfo "1.0.0"', 'owl:versionInfo "1.0.1"', 1)
    if change == "param-description":
        return text.replace('"要删除的资源的完整 IRI"@zh', '"要删除的资源的完整 IRI（改过）"@zh')
    if change == "add-guard":
        start = text.index("aisep:ActionRemoveElement")
        g = ('    aisep:guard [ a sh:SPARQLAskValidator ; dcterms:identifier "always-ok" ; '
             'sh:ask "ASK { $iri a ?t }" ; sh:message "不会失败的检查"@zh ] ;\n')
        i = text.index("    aisep:steps (", start)
        return text[:i] + g + text[i:]
    assert change == "add-step"   # 评审过的是「只删这一个」，定义被改成「顺带再删一个」
    extra = (f'aisep:binding [ aisep:argument "iri" ; aisep:fromParameter ap:iri ] ]\n'
             f'        [ a aisep:ActionStep ; dcterms:identifier "remove-more" ; aisep:invokes aisep:BasicRemove ;\n'
             f'          aisep:binding [ aisep:argument "iri" ; aisep:constant <{t2}> ] ]\n    ) .')
    return text.replace(RM_BLOCK_END, extra)


@pytest.mark.parametrize("change", ["definition", "title", "version", "param-description", "add-guard", "add-step"])
def test_B7_action_definition_changed_after_dry_run(mk, change):
    r = mk()
    T, _ = plant(r)
    T2, _ = plant(r, "acDoomedToo")
    orig = read(r, CAT)
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    # 只改格式与注释、不改三元组：不算改动，digest 仍然有效（不靠文件字节或时间戳）
    write(r, CAT, "# 前面多了一行注释\n" + orig.replace("aisep:ActionRemoveElement a aisep:ActionType ;",
                                                       "aisep:ActionRemoveElement  a  aisep:ActionType ;\n"))
    assert apply(r, REMOVE, {"iri": T}, dryRun=True)["planDigest"] == d["planDigest"]
    new = _edit_remove_action(orig, change, T2)
    assert new != orig
    write(r, CAT, new)
    listed = by_id(r)
    assert listed[REMOVE]["valid"] is True, listed[REMOVE]
    assert listed[REGISTER]["valid"] is True
    stale(r, d["planDigest"], {"iri": T})
    write(r, CAT, orig)                     # 改回原定义，旧 digest 重新有效并可执行
    assert apply(r, REMOVE, {"iri": T}, planDigest=d["planDigest"])["changed"] is True


def test_B7_definition_digest_changes_with_definition_only(mk):
    """definitionDigest 只随本动作的定义变：改另一条动作不影响它。"""
    r = mk()
    before = by_id(r)
    write(r, CAT, read(r, CAT).replace('skos:prefLabel  "删除元素"@zh', 'skos:prefLabel  "删除元素（改过）"@zh'))
    after = by_id(r)
    assert after[REMOVE]["definitionDigest"] != before[REMOVE]["definitionDigest"]
    assert after[REGISTER]["definitionDigest"] == before[REGISTER]["definitionDigest"]


def test_B7_digest_is_bound_to_parameters():
    """只换参数、动作 / 定义 / 文件前后字节都相同时，planDigest 也必须不同。"""
    files = {VER: {"before": "sha256:" + "1" * 64, "after": "sha256:" + "2" * 64}}
    ddigest = "sha256:" + "3" * 64
    a = actions._plan_digest(REMOVE, ddigest, {"iri": WB + "acA"}, files)
    b = actions._plan_digest(REMOVE, ddigest, {"iri": WB + "acB"}, files)
    assert a != b
    assert a == actions._plan_digest(REMOVE, ddigest, {"iri": WB + "acA"}, files)


def test_B7_digest_of_one_target_is_stale_for_another(mk):
    r = mk()
    T, _ = plant(r)
    T2, _ = plant(r, "acDoomedToo")
    d = apply(r, REMOVE, {"iri": T}, dryRun=True)
    stale(r, d["planDigest"], {"iri": T2})


def test_B7_non_destructive_action_does_not_need_a_digest_but_checks_one(mk):
    r = mk()
    before = snap(r)
    d = apply(r, REGISTER, P0, dryRun=True)
    e = apply_err(r, REGISTER, P0, planDigest=ZERO)
    assert e["code"] == "PLAN_STALE" and snap(r) == before
    assert apply(r, REGISTER, P0, planDigest=d["planDigest"])["changed"] is True


def test_B7_register_digest_stale_after_definition_change(mk):
    r = mk()
    d = apply(r, REGISTER, P0, dryRun=True)
    write(r, CAT, read(r, CAT).replace('"登记验收标准并挂到需求"@zh', '"登记验收标准并挂到需求（改过）"@zh'))
    stale(r, d["planDigest"], P0, action=REGISTER)


# ================================================================== B8 不产生新状态、参数不可注入

MODEL_TTL = re.compile(r"models/(?:[^/]+/)+[^/]+\.ttl")


def worktree_files(repo):
    out = set()
    for d, dirs, fs in os.walk(repo):
        if ".git" in dirs:
            dirs.remove(".git")
        out.update(os.path.relpath(os.path.join(d, f), repo) for f in fs)
    return out


def gitdir_files(repo):
    gd = repo / ".git"
    return {os.path.relpath(os.path.join(d, f), gd) for d, _, fs in os.walk(gd) for f in fs}


def test_B8_no_state_besides_model_files(mk):
    a, b_ = mk("action"), mk("control")
    head = git(a, "rev-parse", "HEAD")
    wt_before, gd_before = worktree_files(a), gitdir_files(a)
    ok(a, "model_list_actions")
    apply(a, REGISTER, P0, dryRun=True)
    r1 = apply(a, REGISTER, P0)
    apply(a, REGISTER, P0)
    apply(a, REGISTER, dict(P0, slug="acSecond", file=GOV, relationshipFile=AM4))
    apply_err(a, REGISTER, dict(P0, requirement=AC, slug="acRefused"))
    apply_err(a, REGISTER, dict(P0, requirement=BPMN_NODE, slug="acRejected"))
    target = r1["iris"]["criterion"]
    apply_err(a, REMOVE, {"iri": target})
    apply_err(a, REMOVE, {"iri": target}, planDigest=ZERO)
    apply_err(a, REMOVE, {"iri": AC}, dryRun=True)
    apply(a, REMOVE, {"iri": target}, planDigest=apply(a, REMOVE, {"iri": target}, dryRun=True)["planDigest"])
    e = ok(b_, "model_add_element", model=WB, type="aisep:AcceptanceCriterion", prefLabel="对照", slug="acControl")
    ok(b_, "model_add_relationship", type="am4:Aggregation", source=REQ, target=e["iri"])
    dr = ok(b_, "model_remove", iri=e["iri"], cascade=True, dryRun=True)
    ok(b_, "model_remove", iri=e["iri"], cascade=True, planDigest=dr["planDigest"])
    assert gitdir_files(a) - gd_before <= gitdir_files(b_) - gd_before   # .git 里新出现的文件不比写工具多
    new = worktree_files(a) - wt_before
    assert all(MODEL_TTL.fullmatch(f) for f in new), new
    for flags in (("--untracked-files=all",), ("--untracked-files=all", "--ignored")):
        lines = git(a, "status", "--porcelain", *flags).splitlines()
        assert lines, "连续调用后应当有模型文件改动"
        for ln in lines:   # git() 去掉了首行行首的空格，所以按空白切分取路径
            assert MODEL_TTL.fullmatch(ln.split(maxsplit=1)[1]), f"git status 里出现了模型 .ttl 之外的东西：{ln!r}"
    assert git(a, "rev-parse", "HEAD") == head
    assert git(a, "diff", "--cached", "--name-only") == ""
    assert git(a, "branch", "--format=%(refname:short)").split() == ["main"]


IRI_INJECTIONS = [
    REQ + "> } ; ", REQ + "> a aisep:AcceptanceCriterion } #", REQ + '"', REQ + ";", REQ + "}", REQ + " ", REQ + "\n",
    REQ + "> . <urn:x> <urn:y> <urn:z", "<" + REQ + ">", AC + "> } UNION { ?s ?p ?o", "?requirement", "$requirement",
    "workbench:reqApprovalProgress } #", "urn:x", "https://evil.example/model/workbench/reqApprovalProgress", "",
]


@pytest.mark.parametrize("i", range(len(IRI_INJECTIONS)))
def test_B8_iri_parameter_injection_is_invalid_argument(mk, i):
    r = mk()
    before = snap(r)
    for kw in ({}, {"dryRun": True}):
        e = apply_err(r, REGISTER, dict(P0, requirement=IRI_INJECTIONS[i]), **kw)
        assert e["code"] == "INVALID_ARGUMENT", (IRI_INJECTIONS[i], e)
        e = apply_err(r, REMOVE, {"iri": IRI_INJECTIONS[i]}, dryRun=True)
        assert e["code"] == "INVALID_ARGUMENT", (IRI_INJECTIONS[i], e)
    assert snap(r) == before


def test_B8_guard_meaning_survives_hostile_iri(mk):
    r = mk()
    before = snap(r)
    assert apply_err(r, REGISTER, dict(P0, requirement=AC))["code"] == "PRECONDITION_FAILED"
    for v in (AC + "%3E", AC + "%20%7D", AC + ".", AC + "~"):
        is_err, res = call(r, "model_apply_action", action=REGISTER, params=dict(P0, requirement=v))
        assert is_err and res["error"]["code"] in ("INVALID_ARGUMENT", "ELEMENT_NOT_FOUND"), (v, res)
    assert snap(r) == before


NASTY = ['x" } ; DROP ALL', "a > b ; c } d", "'''", '"""', "\\", "x\\\"y", "} UNION { ?s ?p ?o }",
         "> . :reqApprovalProgress a aisep:AcceptanceCriterion . <x", '"@zh ; owl:deprecated true ; skos:altLabel "',
         "${param} {{x}} %s {0}", "# 注释 \n :a :b :c .", "a\tb", "a\rb", " x", "\x00", "\x07", "$requirement"]
STRING_PARAMS = ["prefLabel", "altLabel", "definition", "gherkin", "slug", "file", "relationshipFile"]


def _reset_models(repo):
    git(repo, "checkout", "--", "models")
    for f in git(repo, "ls-files", "--others", "--exclude-standard", "--", "models").splitlines():
        os.remove(repo / f)


@pytest.mark.parametrize("param", STRING_PARAMS)
def test_B8_string_parameters_behave_like_the_write_tools(mk, param):
    """字符串参数带 } > ; 引号等：动作的结论与同参数的顺序写工具调用相同（成功则逐字节相同、值原样落盘；拒绝则同一个
    错误码），绝不是 INTERNAL、SPARQL 解析错误或 guard 误判。"""
    a, b_ = mk("action"), mk("sequential")
    successes = 0
    for n, v in enumerate(NASTY):
        p = dict(P0, slug=f"acNasty{n}")
        p[param] = v
        before_a = snap(a)
        seq = sequential(b_, p)
        is_err, res = call(a, "model_apply_action", action=REGISTER, params=p)
        if seq[-1][0]:
            want = seq[-1][1]["error"]["code"]
            assert is_err and res["error"]["code"] == want, (param, v, want, res)
            assert want not in ("INTERNAL", "PRECONDITION_FAILED"), (param, v, want)
            assert snap(a) == before_a
            if len(seq) == 2:          # 顺序调用留下了第一步：两边都退回起点
                _reset_models(a)
                _reset_models(b_)
            assert_same_models(a, b_)
            continue
        assert not is_err, (param, v, res)
        successes += 1
        assert_same_models(a, b_)
        el_iri = seq[0][1]["iri"]
        pred = {"prefLabel": "http://www.w3.org/2004/02/skos/core#prefLabel",
                "altLabel": "http://www.w3.org/2004/02/skos/core#altLabel",
                "definition": "http://www.w3.org/2004/02/skos/core#definition",
                "gherkin": AISEP + "gherkin"}.get(param)
        if pred:
            assert literal_values(a, seq[0][1]["file"], el_iri, pred) == [v], (param, v)
    if param in ("prefLabel", "definition", "gherkin"):
        assert successes >= 5, "带特殊字符的文本应当大多能正常写入"


def test_B8_literal_bound_guard_cannot_be_injected(mk):
    """一条把字符串参数预绑定进 guard 的动作：ASK「没有元素的 gherkin 恰好等于参数值」（true 即通过）。
    参数若被拼进查询文本，敌意值会改变查询含义；按值绑定则只是一个不存在的字面量。"""
    r = mk()
    add_actions(r, act("ActionTestDedupe", "test-dedupe",
                       [("el", "BasicAddElement", [b("model", "constant", f"<{WB}>"),
                                                   b("type", "constant", "aisep:AcceptanceCriterion"),
                                                   b("prefLabel", "constant", '"去重探针"'),
                                                   b("slug", "fromParameter", "ap:slug"),
                                                   b("attributes", "fromParameter", "ap:gherkin", pred="aisep:gherkin")])],
                       params=[sp("gherkin"), sp("slug")],
                       guards=[guard("gherkin-not-used", "ASK { OPTIONAL { ?s aisep:gherkin $gherkin } FILTER(!BOUND(?s)) }",
                                     "已有验收标准用了完全相同的 gherkin")]))
    listed = by_id(r)
    assert listed["test-dedupe"]["valid"] is True, listed["test-dedupe"]
    existing = literal_values(r, VER, AC, AISEP + "gherkin")
    assert len(existing) == 1 and "\n" in existing[0]
    before = snap(r)
    e = apply_err(r, "test-dedupe", {"gherkin": existing[0], "slug": "acDup"})
    assert e["code"] == "PRECONDITION_FAILED", e
    assert snap(r) == before
    hostile = ['x" } UNION { ?s ?p ?o', '" } UNION { ?s a aisep:AcceptanceCriterion } #', "?g", "?s", "$gherkin",
               existing[0] + '"', '"' + existing[0], 'x"^^<http://www.w3.org/2001/XMLSchema#string> } UNION { ?a ?b ?c } #',
               "} ; > <", "'''x'''", "x\\"]
    for n, v in enumerate(hostile):
        assert apply(r, "test-dedupe", {"gherkin": v, "slug": f"acHostile{n}"})["changed"] is True, v
    after = snap(r)
    for n, v in enumerate(hostile):            # 同一个值再来（换 slug，不是重放）：guard 现在失败，说明按值比较
        assert apply_err(r, "test-dedupe", {"gherkin": v, "slug": f"acHostileAgain{n}"})["code"] == "PRECONDITION_FAILED", v
    assert snap(r) == after


def test_slow_guard_times_out_without_writing(mk, monkeypatch):
    """followups-20261126 第 7 项：写坏的 guard（三重笛卡尔积、过滤条件永不成立）不能让 model_apply_action 卡死：
    超时 -> QUERY_TIMEOUT（不可重试，details 点名动作与 guard），零写入。超时值调小只为测试快。"""
    r = mk()
    add_actions(r, act("ActionTestSlowGuard", "test-slow-guard", [new_criterion_step(slug_const="acSlowGuard")],
                       params=[sp("label")],
                       guards=[guard("slow", "ASK { ?a ?b ?c . ?d ?e ?f . ?g ?h ?i . "
                                             "FILTER(STRLEN(STR(?c)) + STRLEN(STR(?f)) + STRLEN(STR(?i)) < 0) }")]))
    assert by_id(r)["test-slow-guard"]["valid"] is True
    monkeypatch.setattr(actions, "GUARD_TIMEOUT_S", 1)
    before = snap(r)
    e = apply_err(r, "test-slow-guard", {"label": "超时探针"})
    assert e["code"] == "QUERY_TIMEOUT" and e["retryable"] is False, e
    assert e["details"] == {"action": "test-slow-guard", "guard": "slow"}, e
    assert snap(r) == before


def test_B8_action_name_and_params_shape_cannot_be_abused(mk):
    r = mk()
    before = snap(r)
    for name in ("../catalog", REGISTER + "\n", "remove-element; rm -rf", "", "REMOVE-ELEMENT",
                 AISEP + "ActionRemoveElement", "aisep:ActionRemoveElement"):
        assert err(r, "model_apply_action", action=name, params={})["code"] == "INVALID_ARGUMENT", name
    for args in ({"action": REGISTER, "params": P0, "catalog": "/tmp/x.ttl"},
                 {"action": REGISTER, "params": P0, "catalogPath": "/tmp/x.ttl"},
                 {"action": REGISTER, "params": [1]}, {"action": REGISTER, "params": "x"},
                 {"action": {"id": REGISTER}, "params": P0}, {"params": P0}):
        is_err, res = call(r, "model_apply_action", **args)
        assert is_err and res["error"]["code"] == "INVALID_ARGUMENT", (args, res)
    assert err(r, "model_list_actions", catalog="/tmp/x.ttl")["code"] == "INVALID_ARGUMENT"
    assert snap(r) == before
