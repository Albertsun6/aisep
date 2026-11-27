"""model_set_attributes 与 docs/actions.md 的验收测试（动作机制阶段 A，断言 A1、A3、A4、A5、A6 与边界用例）。

由没有参与实现的测试者编写。期望值来自阶段 A 的断言表、docs/mcp-interface.md §5.12 与现有写工具的既有行为
（§5.1 拒绝零写入、§5.10 model_set_labels），不取自实现的输出。

每个用例都在 conftest 的 `repo`（采购例子的临时 `git init` 副本）或 fixtures.topology.Topo（带裸 origin 的临时仓库）
里操作，不碰真实检出。图级断言一律用「写入前的全部三元组 − 应删 + 应增 == 写入后的全部三元组」，
所以任何多写、少写、写到别的主语上的情况都会失败。

断言 A7（既有四个写工具的测试不改一行仍通过）是一次性的分支核对，不写成常驻用例：常驻的话，以后任何改到
别的测试文件的 PR 都会被它拦下。
"""
import hashlib, json, os, re
from datetime import datetime, timezone

import pyoxigraph as ox
import pytest

from conftest import ROOT, commit_all, git, run_cli
from fixtures.topology import Topo, activity_ttl
from aisep import diff, mergecheck, server as S, tools as T, write_tools as W
from aisep.errors import CODES, AisepError

M = "https://aisep.example/model/procurement/"
AM4 = "models/procurement/am4.ttl"
GOVTTL = "models/procurement/governance.ttl"
VERIF = "models/procurement/verification.ttl"

AISEP = "https://aisep.example/ont/aisep#"
ARCH = "https://meta.linked.archi/core#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD = "http://www.w3.org/2001/XMLSchema#"
PRIORITY = AISEP + "priority"
GHERKIN = AISEP + "gherkin"
NOTE = SKOS + "note"
DEPRECATED = "http://www.w3.org/2002/07/owl#deprecated"
REPLACED_BY = "http://purl.org/dc/terms/isReplacedBy"
APPROVAL_STATE = ARCH + "approvalState"
UNDECLARED = "https://example.invalid/undeclared"

REQ = M + "reqTwoLevelApproval"          # am4:Requirement with aisep:priority aisep:Must; no approval record covers it
AC = M + "acOver100kSecondLevel"         # aisep:AcceptanceCriterion with aisep:gherkin (verification.ttl)
REL = M + "rel-quoteApproval-realizes-reqTwoLevelApproval"
RECORD = M + "approval-20261119-arch-baseline"
SUPPLIER = M + "supplier"
TRUE = {"value": "true", "datatype": "xsd:boolean"}
WRITE_TOOLS = ["model_add_element", "model_add_relationship", "model_set_labels", "model_set_attributes", "model_remove"]


# ------------------------------------------------------------------ helpers

def cfg(repo):
    return T.Config(allow_roots=(str(repo.parent),))


def sa(repo, iri, **kw):
    return W.model_set_attributes(cfg(repo), iri, repo=str(repo), **kw)


def one(predicate, *values):
    return [{"predicate": predicate, "value": v} for v in values]


def snap(repo):
    """{repo-relative path: sha256} of every file under models/."""
    out = {}
    for d, _, fs in os.walk(os.path.join(str(repo), "models")):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, str(repo))] = hashlib.sha256(fh.read()).hexdigest()
    return out


def text(repo, rel):
    with open(os.path.join(str(repo), rel), encoding="utf-8") as f:
        return f.read()


def append(repo, rel, s):
    with open(os.path.join(str(repo), rel), "a", encoding="utf-8") as f:
        f.write(s)


def file_triples(repo, rel):
    with open(os.path.join(str(repo), rel), "rb") as f:
        return {(q.subject, q.predicate, q.object) for q in ox.parse(f, format=ox.RdfFormat.TURTLE)}


def graph(repo):
    """Every triple of every .ttl under models/ (parsing also proves each file is still valid Turtle)."""
    out = set()
    for rel in snap(repo):
        if rel.endswith(".ttl"):
            out |= file_triples(repo, rel)
    return out


def tr(s, p, o):
    return (ox.NamedNode(s), ox.NamedNode(p), o)


def n(iri):
    return ox.NamedNode(iri)


def lit(v, lang=None, dt=None):
    return ox.Literal(v, language=lang) if lang else ox.Literal(v, datatype=ox.NamedNode(dt)) if dt else ox.Literal(v)


def git_state(repo):
    return git(repo, "rev-parse", "HEAD"), git(repo, "diff", "--cached", "--name-only")


def refused(repo, code, iri, **kw):
    """The call must raise AisepError(code) and leave models/ byte-identical, nothing staged, HEAD where it was."""
    s, g = snap(repo), git_state(repo)
    with pytest.raises(AisepError) as e:
        sa(repo, iri, **kw)
    assert e.value.code == code, (e.value.code, e.value.message, e.value.details)
    assert snap(repo) == s, "被拒绝的写入改了文件"
    assert git_state(repo) == g
    return e.value


def applied(repo, iri, minus=(), plus=(), **kw):
    """The call succeeds with changed:true and the graph changes by exactly −minus +plus; nothing staged or committed."""
    g0, state, s0 = graph(repo), git_state(repo), snap(repo)
    r = sa(repo, iri, **kw)
    assert r["changed"] is True, r
    assert graph(repo) == (g0 - set(minus)) | set(plus)
    assert git_state(repo) == state, "写工具不应 git add 或提交"
    s1 = snap(repo)
    changed_files = sorted(f for f in s1 if s1[f] != s0.get(f))
    assert sorted(f["path"] for f in r["filesChanged"]) == changed_files
    for f in r["filesChanged"]:
        assert (f["sha256Before"], f["sha256After"]) == (s0[f["path"]], s1[f["path"]])
    assert set(s1) == set(s0), "不应新建或删除文件"
    return r


def vals(xs):
    """before/after value lists as an order-free set (§5.12: each value has the shape of the input `value`)."""
    return {tuple(sorted(v.items())) for v in xs}


def violations(repo):
    return T.model_check(cfg(repo), repo=str(repo))["summary"]["violations"]


def worktree_diff(repo):
    d = diff.model_diff(cfg(repo), {"worktree": "main"}, detail="items", repo=str(repo))
    return [(i["iri"], i["change"], i["changedPredicates"]) for i in d["items"]]


# ------------------------------------------------------------------ A1: docs/actions.md against the agent profile

DOC = os.path.join(ROOT, "docs", "actions.md")
# Back-quoted lower-case words of the document that are NOT tool arguments (reviewed by hand): result fields of the
# write tools (§5.5, §5.10, §5.12), enum values of model_impact.mode, JSON literals and two command names.
DOC_NOT_ARGUMENTS = {"after", "before", "changed", "plan", "delete", "detach",   # result fields
                     "depends", "ripple",                                        # values of model_impact.mode
                     "null", "true", "false", "gate", "mergecheck"}


def _doc():
    with open(DOC, encoding="utf-8") as f:
        return f.read()


def _schema(tool):
    return S.TOOLS[tool][2]


def _props(tool):
    return set(_schema(tool)["properties"])


def _doc_calls():
    """Every ```json block of the document: [(tool, arguments)]."""
    blocks = re.findall(r"```json\n(.*?)```", _doc(), re.S)
    assert blocks, "docs/actions.md 里没有 JSON 示例"
    calls = [json.loads(b) for b in blocks]
    assert all(set(c) == {"tool", "arguments"} for c in calls), calls
    return [(c["tool"], c["arguments"]) for c in calls]


def test_A1_every_tool_named_in_actions_doc_is_in_agent_profile():
    agent = set(S.listed("agent"))
    named = set(re.findall(r"\b(?:model|governance)_[a-z_]+\b", _doc()))
    assert set(WRITE_TOOLS) <= named, "文档应覆盖五个写工具"
    assert named <= agent, f"文档里出现了 agent 画像没有的工具：{sorted(named - agent)}"
    assert {t for t, _ in _doc_calls()} <= agent


def test_A1_every_json_example_in_actions_doc_matches_the_input_schema():
    for tool, args in _doc_calls():
        assert set(args) <= _props(tool), (tool, sorted(set(args) - _props(tool)))
        S.validate_args(tool, args)  # nested shapes, enums and required fields (raises INVALID_ARGUMENT)
        for field in ("set", "attributes"):
            item = _schema(tool)["properties"].get(field, {}).get("items", {})
            for a in args.get(field, ()):
                assert set(a) <= set(item["properties"]), (tool, field, a)


def test_A1_every_argument_name_in_actions_doc_prose_exists():
    doc = _doc()
    prose = re.sub(r"```.*?```", "", doc, flags=re.S)
    agent = S.listed("agent")
    known = set().union(*(_props(t) for t in agent))
    for t in agent:  # argument names one level down ({predicate, value} of set / attributes)
        for p in _schema(t)["properties"].values():
            known |= set(p.get("items", {}).get("properties", {}))
    words = {w for w in re.findall(r"`([^`]+)`", prose) if re.fullmatch(r"[a-z][A-Za-z]*", w)}
    unknown = words - known - DOC_NOT_ARGUMENTS
    assert not unknown, f"文档里的参数名不在任何 agent 工具的 inputSchema 里：{sorted(unknown)}"
    # keys of inline JSON fragments such as `"unset": ["aisep:priority"]`
    inline = {k for frag in re.findall(r"`([^`]*\"[^`]*)`", prose) for k in re.findall(r'"(\w+)"\s*:', frag)}
    value_keys = {"iri", "value", "lang", "datatype"}  # the `value` object (§5.2), exercised by the value-form tests below
    assert inline <= known | value_keys, sorted(inline - known - value_keys)


def test_A1_basic_action_table_rows_name_arguments_of_their_own_tool():
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in _doc().splitlines()
            if line.startswith("|") and re.search(r"\| `model_[a-z_]+` \|", line)]
    assert sorted(r[1].strip("`") for r in rows) == sorted(WRITE_TOOLS), "基本动作表应恰好列出五个写工具"
    for r in rows:
        tool = r[1].strip("`")
        args = {w for cell in r[2:4] for w in re.findall(r"`([^`]+)`", cell)
                if re.fullmatch(r"[a-z][A-Za-z]*", w)} - DOC_NOT_ARGUMENTS
        assert args <= _props(tool), (tool, sorted(args - _props(tool)))
    for tool in WRITE_TOOLS:  # 「五个动作共同的行为：dryRun」
        assert "dryRun" in _props(tool), tool


def test_A1_error_codes_in_actions_doc_exist():
    codes = set(re.findall(r"`([A-Z][A-Z_]+[A-Z])`", _doc()))
    assert codes and codes <= CODES, sorted(codes - CODES)


def test_actions_doc_signal_table_makes_no_commitment_about_future_mechanisms():
    """回归（评审阻塞问题）：升级信号一节只列信号。它不得写成「信号出现之前不新增动作机制」之类对后续阶段的
    否定式承诺（与 Albert 已确认的阶段安排冲突），也不得替 Albert 定记账流程（「记录」列、由谁开 issue）。"""
    section = _doc().split("\n## 4. 升级信号\n", 1)[1]
    assert not re.search(r"不新增|在那之前|不得新增|不再新增", section), section
    rows = [line for line in section.splitlines() if re.match(r"\| S\d \|", line)]
    assert [r.split("|")[1].strip() for r in rows] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    header = next(line for line in section.splitlines() if line.startswith("| # |"))
    assert [c.strip() for c in header.strip("|").split("|")] == ["#", "信号", "怎么观测"]
    assert all(r.count("|") == header.count("|") for r in rows)
    assert "待 Albert 确认" in section


def test_actions_doc_recipe_examples_do_not_collide_with_existing_elements():
    """回归（评审与 A2 试跑）：配方一的示例显式给 slug，且这个 IRI 在仓库里还不存在；配方三删的就是它，
    不是一个已批准、只会返回 REFERENCED 的现有元素。"""
    calls = _doc_calls()
    add = next(a for t, a in calls if t == "model_add_element")
    new = f"{add['model']}:{add['slug']}"
    removed = {a["iri"] for t, a in calls if t == "model_remove"}
    assert removed == {new}
    assert {a["focus"] for t, a in calls if t == "model_impact"} == {new}
    model_dir = os.path.join(ROOT, "models", add["model"])
    assert os.path.isdir(model_dir)
    for name in sorted(os.listdir(model_dir)):
        if name.endswith(".ttl"):
            with open(os.path.join(model_dir, name), encoding="utf-8") as f:
                assert not re.search(rf"\b{re.escape(add['slug'])}\b", f.read()), name


def test_tool_registration_profiles_annotations_and_schema():
    assert "model_set_attributes" in S.listed("agent") and "model_set_attributes" in S.listed("all")
    assert "model_set_attributes" not in S.listed("workbench")
    assert S.TOOLS["model_set_attributes"][4] == S.TOOLS["model_set_labels"][4]  # same annotations as set_labels
    schema = _schema("model_set_attributes")
    assert set(schema["properties"]) == {"iri", "set", "unset", "dryRun", "repo"}
    assert schema["required"] == ["iri"] and schema["additionalProperties"] is False


# ------------------------------------------------------------------ A3: unapproved element, aisep:priority

def test_A3_priority_change_stays_inside_the_subject_block(repo):
    before = text(repo, AM4)
    start = before.index("\n:reqTwoLevelApproval a ") + 1
    end = before.index("\n\n", start)                     # the block ends at the next blank line
    block = before[start:end]
    assert "aisep:priority aisep:Must" in block and block.count("\n:") == 0   # fixture: one subject in the block
    others = {f: h for f, h in snap(repo).items() if f != AM4}

    r = applied(repo, "procurement:reqTwoLevelApproval", set=one("aisep:priority", {"iri": "aisep:Should"}),
                minus=[tr(REQ, PRIORITY, n(AISEP + "Must"))], plus=[tr(REQ, PRIORITY, n(AISEP + "Should"))])

    after = text(repo, AM4)
    assert after[:start] == before[:start], "主语块之前的字节变了"
    assert after.endswith(before[end:]), "主语块之后的字节变了"
    assert {f: h for f, h in snap(repo).items() if f != AM4} == others
    assert [f["path"] for f in r["filesChanged"]] == [AM4]
    assert r["iri"] == REQ
    assert vals(r["before"][PRIORITY]) == vals([{"iri": AISEP + "Must"}])
    assert vals(r["after"][PRIORITY]) == vals([{"iri": AISEP + "Should"}])
    assert set(r["before"]) == set(r["after"]) == {PRIORITY}
    assert worktree_diff(repo) == [(REQ, "modified", [PRIORITY])]
    assert violations(repo) == 0


# ------------------------------------------------------------------ A4: refused predicates, files unchanged

NOT_SETTABLE = [  # (prefixed name, full IRI, a plausible value, target)
    ("rdf:type", RDF_TYPE, {"iri": "am4:BusinessObject"}, REQ),
    ("arch:inModel", ARCH + "inModel", {"iri": M}, REQ),
    ("arch:source", ARCH + "source", {"iri": M + "supplier"}, REL),
    ("arch:target", ARCH + "target", {"iri": M + "supplier"}, REL),
    ("skos:prefLabel", SKOS + "prefLabel", {"value": "新名称", "lang": "zh"}, REQ),
    ("skos:altLabel", SKOS + "altLabel", {"value": "New name", "lang": "en"}, REQ),
    ("skos:definition", SKOS + "definition", {"value": "定义", "lang": "zh"}, REQ),
]


@pytest.mark.parametrize("short,full,value,target", NOT_SETTABLE, ids=[x[0] for x in NOT_SETTABLE])
@pytest.mark.parametrize("spelling", ["prefixed", "full", "angle"])
def test_A4_not_settable_predicates_are_invalid_argument(repo, short, full, value, target, spelling):
    p = {"prefixed": short, "full": full, "angle": f"<{full}>"}[spelling]
    e = refused(repo, "INVALID_ARGUMENT", target, set=one(p, value))
    assert e.details["rejectedFields"] == ["set"]
    e = refused(repo, "INVALID_ARGUMENT", target, unset=[p])
    assert e.details["rejectedFields"] == ["unset"]
    # a legal change in the same call does not get written either
    refused(repo, "INVALID_ARGUMENT", target, set=one("skos:note", {"value": "备注", "lang": "zh"}) + one(p, value))
    refused(repo, "INVALID_ARGUMENT", target, set=one("skos:note", {"value": "备注", "lang": "zh"}), unset=[p])
    refused(repo, "INVALID_ARGUMENT", target, set=one(p, value), dryRun=True)


def test_A4_rdf_type_shorthand_a_cannot_change_the_type(repo):
    """`a` is Turtle's spelling of rdf:type; whatever the tool makes of it, the type must not change."""
    s, g = snap(repo), graph(repo)
    try:
        sa(repo, REQ, set=one("a", {"iri": "am4:BusinessObject"}))
    except AisepError as e:
        assert e.code in ("INVALID_ARGUMENT", "WRITE_REJECTED"), e.code
        assert snap(repo) == s
    else:
        pytest.fail("set 里写 predicate='a' 被接受了")
    assert {o for s_, p, o in graph(repo) if s_ == n(REQ) and p == n(RDF_TYPE)} == \
        {o for s_, p, o in g if s_ == n(REQ) and p == n(RDF_TYPE)}


@pytest.mark.parametrize("predicate,value", [
    (UNDECLARED, {"value": "x"}),
    (f"<{UNDECLARED}>", {"iri": M + "supplier"}),
    ("skos:related", {"iri": M + "supplier"}),              # declared by SKOS, but not allowed in a model file
    ("arch:approvalState", {"iri": "arch:Approved"}),
    (APPROVAL_STATE, {"iri": ARCH + "Approved"}),
    ("arch:approvalState", {"iri": "arch:Proposed"}),
], ids=["undeclared", "undeclared-iri-value", "skos-related", "approvalState", "approvalState-full", "approvalState-proposed"])
@pytest.mark.parametrize("target", [REQ, M + "quoteApproval", REL], ids=["element", "approved-element", "relationship"])
def test_A4_closed_world_and_hand_written_approval_state_are_write_rejected(repo, predicate, value, target):
    e = refused(repo, "WRITE_REJECTED", target, set=one(predicate, value))
    new = [f for f in e.details["findings"] if f["severity"] == "Violation" and not f.get("preexisting")]
    assert new, e.details
    # together with a legal change: nothing at all is written
    refused(repo, "WRITE_REJECTED", target, set=one("skos:note", {"value": "备注", "lang": "zh"}) + one(predicate, value))
    refused(repo, "WRITE_REJECTED", target, set=one(predicate, value), dryRun=True)


def test_A4_same_refusals_through_the_server_entry(repo):
    s = snap(repo)
    for args, code in [({"iri": REQ, "set": one("rdf:type", {"iri": "am4:BusinessObject"})}, "INVALID_ARGUMENT"),
                       ({"iri": REQ, "unset": ["skos:prefLabel"]}, "INVALID_ARGUMENT"),
                       ({"iri": REQ, "set": one("arch:approvalState", {"iri": "arch:Approved"})}, "WRITE_REJECTED"),
                       ({"iri": REQ, "set": one(UNDECLARED, {"value": "x"})}, "WRITE_REJECTED"),
                       ({"iri": RECORD, "set": one("aisep:decision", {"iri": "aisep:DecisionRejected"})}, "PROTECTED_RESOURCE"),
                       ({"iri": REQ, "set": one("aisep:priority", {"iri": "aisep:Should"}), "file": AM4}, "INVALID_ARGUMENT"),
                       ({"iri": REQ, "set": [{"predicate": "aisep:priority"}]}, "INVALID_ARGUMENT"),
                       ({"iri": REQ, "set": [{"predicate": "aisep:priority", "value": "aisep:Should"}]}, "INVALID_ARGUMENT"),
                       ({"iri": REQ, "unset": "aisep:priority"}, "INVALID_ARGUMENT"),
                       ({"set": one("aisep:priority", {"iri": "aisep:Should"})}, "INVALID_ARGUMENT")]:
        res = S.call(cfg(repo), "model_set_attributes", dict(args, repo=str(repo)))
        assert res.is_error and res.structured_content["error"]["code"] == code, (args, res.structured_content)
        assert snap(repo) == s
    ok = S.call(cfg(repo), "model_set_attributes",
                {"iri": "procurement:reqTwoLevelApproval", "set": one("aisep:priority", {"iri": "aisep:Should"}), "repo": str(repo)})
    assert not ok.is_error and ok.structured_content["changed"] is True and ok.structured_content["iri"] == REQ
    assert tr(REQ, PRIORITY, n(AISEP + "Should")) in graph(repo)


# ------------------------------------------------------------------ A5: approved element -> the merge check still bites

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
MAIN = "refs/heads/main"
AUDIT = M + "auditTrail"


def _topo(template, tmp_path):
    t = Topo(template, tmp_path)
    assert ":auditTrail a " in t.read(AM4)   # baseline: :auditTrail is Approved on main (see test_merge_check_inview)
    assert "aisep:approves :auditTrail" in t.read("models/procurement/governance/approval-20261119120000-architecture-audittrail.ttl")
    return t, T.Config(allow_roots=(str(tmp_path),))


def _gate_passes(t):
    rc, out, err = run_cli(t.root, "gate")
    assert rc == 0 and "result=PASS" in out, (rc, out[-600:], err[-600:])


@pytest.mark.parametrize("change", [
    {"set": one("skos:note", {"value": "补充说明", "lang": "zh"})},
    {"set": one("owl:deprecated", TRUE) + one("dcterms:isReplacedBy", {"iri": M + "quotation"})},   # retirement (actions.md 配方三)
], ids=["note", "retire"])
def test_A5_attribute_change_on_approved_element_is_caught_by_mergecheck(template, tmp_path, change):
    t, c = _topo(template, tmp_path)
    t.checkout("main", new="feat/attr")
    r = W.model_set_attributes(c, "procurement:auditTrail", repo=str(t.root), **change)
    assert r["changed"] is True and r["iri"] == AUDIT
    assert t.git("diff", "--name-only") == AM4 and t.git("diff", "--cached", "--name-only") == ""   # written, not staged
    assert t.git("status", "--porcelain", "--untracked-files=all").split() == ["M", AM4]              # nothing else touched
    _gate_passes(t)
    head = t.commit_all("change attributes of approved :auditTrail")
    problems = mergecheck.merge_check(str(t.root), head, MAIN, head_ref="feat/attr", now=NOW)
    hits = [p for p in problems if p["reason"] == "unapproved-change-to-approved"]
    assert hits, problems
    assert AUDIT in {p.get("iri") for p in hits}, hits


def test_A5_control_attribute_change_on_unapproved_element_is_not_reported(template, tmp_path):
    """Control twin: the same tool on an element no record approves -> no unapproved-change-to-approved (no false red)."""
    t, c = _topo(template, tmp_path)
    t.checkout("main", new="feat/attr")
    r = W.model_set_attributes(c, "procurement:reqTwoLevelApproval", repo=str(t.root),
                               set=one("aisep:priority", {"iri": "aisep:Should"}))
    assert r["changed"] is True
    _gate_passes(t)
    head = t.commit_all("change priority of unapproved requirement")
    problems = mergecheck.merge_check(str(t.root), head, MAIN, head_ref="feat/attr", now=NOW)
    assert [p for p in problems if p["reason"] == "unapproved-change-to-approved"] == [], problems


# ------------------------------------------------------------------ A6: protected targets; replay

def test_A6_approval_record_is_protected(repo):
    for kw in ({"set": one("aisep:decision", {"iri": "aisep:DecisionRejected"})},
               {"set": one("aisep:approves", {"iri": M + "supplier"})},
               {"set": one("aisep:evidence", {"value": "0" * 40})},
               {"unset": ["aisep:approves"]},
               {"set": one("skos:note", {"value": "备注", "lang": "zh"})},
               {"set": one("skos:note", {"value": "备注", "lang": "zh"}), "dryRun": True}):
        refused(repo, "PROTECTED_RESOURCE", RECORD, **kw)
        refused(repo, "PROTECTED_RESOURCE", "procurement:approval-20261119-arch-baseline", **kw)


def test_A6_agent_activity_is_protected(repo):
    append(repo, GOVTTL, f"\n:codingBot a arch:Stakeholder ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"编码代理\"@zh .\n"
           + activity_ttl("activity-20261119100000-abc1234", "a" * 40, "b" * 40, "feat/x"))
    assert violations(repo) == 0                      # the fixture itself is a legal model
    commit_all(repo, "an AI activity")
    act = M + "activity-20261119100000-abc1234"
    assert tr(act, RDF_TYPE, n(AISEP + "AgentActivity")) in graph(repo)
    for kw in ({"set": one("aisep:headCommit", {"value": "c" * 40})}, {"unset": ["aisep:sessionRef"]},
               {"set": one("skos:note", {"value": "备注", "lang": "zh"})},
               {"set": one("aisep:branch", {"value": "feat/y"}), "dryRun": True}):
        refused(repo, "PROTECTED_RESOURCE", act, **kw)


def test_A6_model_resource_is_protected(repo):
    assert tr(M, RDF_TYPE, n(ARCH + "Model")) in graph(repo)
    for iri in (M, M.rstrip("/")):
        if tr(iri, RDF_TYPE, n(ARCH + "Model")) not in graph(repo):
            continue
        for kw in ({"set": one("skos:note", {"value": "备注", "lang": "zh"})}, {"unset": ["skos:note"]},
                   {"set": one("owl:deprecated", TRUE), "dryRun": True}):
            refused(repo, "PROTECTED_RESOURCE", iri, **kw)


def _other_model(repo, extra):
    b = "https://aisep.example/model/other/"
    os.makedirs(os.path.join(str(repo), "models", "other"))
    with open(os.path.join(str(repo), "models/other/am4.ttl"), "w", encoding="utf-8") as f:
        f.write(f"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix : <{b}> .
<{b}> a arch:Model ; skos:prefLabel "其他"@zh .
:auditor a am4:Role ; arch:inModel <{b}> ; skos:prefLabel "审计员"@zh .
{extra}""")
    commit_all(repo, "model B")
    return b


def test_A6_subject_with_triples_in_another_model_directory_is_protected(repo):
    _other_model(repo, f'<{SUPPLIER}> skos:note "别的模型写的备注"@zh .\n')
    assert tr(SUPPLIER, NOTE, lit("别的模型写的备注", "zh")) in file_triples(repo, "models/other/am4.ttl")
    for kw in ({"set": one("skos:note", {"value": "改掉它", "lang": "zh"})},   # would rewrite the other model's file
               {"unset": ["skos:note"]},
               {"set": one("owl:deprecated", TRUE)},                            # touches only its own directory
               {"set": one("skos:note", {"value": "改掉它", "lang": "zh"}), "dryRun": True}):
        e = refused(repo, "PROTECTED_RESOURCE", SUPPLIER, **kw)
        assert e.details.get("files") == ["models/other/am4.ttl"]


def test_A6_other_models_own_member_is_writable_only_in_its_own_directory(repo):
    """Positive twin: a member of the other model whose triples are all in its own directory is an ordinary target."""
    b = _other_model(repo, "")
    s = {f: h for f, h in snap(repo).items() if f.startswith("models/procurement/")}
    applied(repo, b + "auditor", set=one("skos:note", {"value": "备注", "lang": "zh"}),
            plus=[tr(b + "auditor", NOTE, lit("备注", "zh"))])
    assert {f: h for f, h in snap(repo).items() if f.startswith("models/procurement/")} == s


REPLAYS = [
    (REQ, {"set": one("aisep:priority", {"iri": "aisep:Should"})}),
    (REQ, {"unset": ["aisep:priority"]}),
    (REQ, {"set": one("skos:note", {"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}), "unset": ["aisep:priority"]}),
    (AC, {"set": one("aisep:gherkin", {"value": 'Given "引号"\nWhen \\ 反斜杠\nThen 结束'})}),
    (REL, {"set": one("owl:deprecated", TRUE)}),
]


@pytest.mark.parametrize("target,kw", REPLAYS, ids=["set", "unset", "set+unset", "multiline", "relationship"])
def test_A6_replay_with_same_arguments_is_changed_false(repo, target, kw):
    first = sa(repo, target, **kw)
    assert first["changed"] is True
    s, g = snap(repo), git_state(repo)
    for _ in range(2):
        again = sa(repo, target, **kw)
        assert again["changed"] is False and again["filesChanged"] == [], again
        assert again["iri"] == first["iri"]
        assert snap(repo) == s and git_state(repo) == g
        assert vals(sum(again["before"].values(), [])) == vals(sum(again["after"].values(), []))


def test_replay_is_spelling_independent(repo):
    """Prefixed name, full IRI, item order and repeated items all describe the same value set."""
    sa(repo, "procurement:reqTwoLevelApproval",
       set=one("skos:note", {"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}) + one("aisep:priority", {"iri": "aisep:Should"}))
    s = snap(repo)
    again = sa(repo, REQ, set=one(PRIORITY, {"iri": AISEP + "Should"})
               + one(NOTE, {"value": "b", "lang": "en"}, {"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}))
    assert again["changed"] is False and snap(repo) == s
    assert sa(repo, REQ, unset=["owl:deprecated"])["changed"] is False and snap(repo) == s


# ------------------------------------------------------------------ boundaries: whole-predicate replacement

def test_multi_value_set_replaces_all_values_of_the_predicate(repo):
    a, b, c = lit("甲", "zh"), lit("b", "en"), lit("丙", "zh")
    r = applied(repo, REQ, set=one("skos:note", {"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}),
                plus=[tr(REQ, NOTE, a), tr(REQ, NOTE, b)])
    assert r["before"][NOTE] == [] and vals(r["after"][NOTE]) == vals([{"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}])
    # keep b, drop 甲, add 丙: afterwards exactly {b, 丙}
    r = applied(repo, REQ, set=one("skos:note", {"value": "b", "lang": "en"}, {"value": "丙", "lang": "zh"}),
                minus=[tr(REQ, NOTE, a)], plus=[tr(REQ, NOTE, c)])
    assert vals(r["before"][NOTE]) == vals([{"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}])
    assert vals(r["after"][NOTE]) == vals([{"value": "b", "lang": "en"}, {"value": "丙", "lang": "zh"}])
    # one item only: one value left
    r = applied(repo, REQ, set=one("skos:note", {"value": "丙", "lang": "zh"}), minus=[tr(REQ, NOTE, b)])
    assert vals(r["after"][NOTE]) == vals([{"value": "丙", "lang": "zh"}])
    # other predicates of the subject were never touched
    assert tr(REQ, PRIORITY, n(AISEP + "Must")) in graph(repo)
    assert violations(repo) == 0
    assert worktree_diff(repo) == [(REQ, "modified", [NOTE])]


def test_duplicate_items_count_once(repo):
    r = applied(repo, REQ, set=one("skos:note", {"value": "甲", "lang": "zh"}, {"value": "甲", "lang": "zh"}),
                plus=[tr(REQ, NOTE, lit("甲", "zh"))])
    assert r["after"][NOTE] == [{"value": "甲", "lang": "zh"}]
    assert text(repo, AM4).count('"甲"@zh') == 1


def test_same_text_with_different_language_or_datatype_are_different_values(repo):
    applied(repo, REQ, set=one("skos:note", {"value": "x", "lang": "zh"}), plus=[tr(REQ, NOTE, lit("x", "zh"))])
    applied(repo, REQ, set=one("skos:note", {"value": "x", "lang": "en"}),
            minus=[tr(REQ, NOTE, lit("x", "zh"))], plus=[tr(REQ, NOTE, lit("x", "en"))])
    applied(repo, REQ, set=one("skos:note", {"value": "x"}),
            minus=[tr(REQ, NOTE, lit("x", "en"))], plus=[tr(REQ, NOTE, lit("x"))])


def test_unset_removes_every_value_and_nothing_else(repo):
    applied(repo, REQ, set=one("skos:note", {"value": "甲", "lang": "zh"}, {"value": "b", "lang": "en"}),
            plus=[tr(REQ, NOTE, lit("甲", "zh")), tr(REQ, NOTE, lit("b", "en"))])
    commit_all(repo, "notes")
    r = applied(repo, REQ, unset=["skos:note", "aisep:priority"],
                minus=[tr(REQ, NOTE, lit("甲", "zh")), tr(REQ, NOTE, lit("b", "en")), tr(REQ, PRIORITY, n(AISEP + "Must"))])
    assert r["after"] == {NOTE: [], PRIORITY: []}
    assert vals(r["before"][PRIORITY]) == vals([{"iri": AISEP + "Must"}]) and len(r["before"][NOTE]) == 2
    assert sorted(worktree_diff(repo)[0][2]) == sorted([NOTE, PRIORITY])
    assert violations(repo) == 0


def test_unset_of_a_predicate_the_subject_does_not_have_is_a_no_op(repo):
    s = snap(repo)
    for p in ("owl:deprecated", "skos:note", UNDECLARED, "aisep:gherkin"):
        r = sa(repo, REQ, unset=[p])
        assert r["changed"] is False and r["filesChanged"] == [] and snap(repo) == s
        assert list(r["before"].values()) == [[]] and list(r["after"].values()) == [[]]


def test_set_and_unset_of_the_same_predicate_is_invalid(repo):
    for unset in ("aisep:priority", PRIORITY, f"<{PRIORITY}>"):
        e = refused(repo, "INVALID_ARGUMENT", REQ, set=one("aisep:priority", {"iri": "aisep:Should"}), unset=[unset])
        assert sorted(e.details["rejectedFields"]) == ["set", "unset"]


def test_set_and_unset_of_different_predicates_in_one_call(repo):
    applied(repo, REQ, set=one("skos:note", {"value": "甲", "lang": "zh"}), unset=["aisep:priority"],
            minus=[tr(REQ, PRIORITY, n(AISEP + "Must"))], plus=[tr(REQ, NOTE, lit("甲", "zh"))])


@pytest.mark.parametrize("kw", [{}, {"set": []}, {"unset": []}, {"set": [], "unset": []}, {"set": None, "unset": None}],
                         ids=["none", "empty-set", "empty-unset", "both-empty", "both-null"])
def test_neither_set_nor_unset_is_invalid(repo, kw):
    e = refused(repo, "INVALID_ARGUMENT", REQ, **kw)
    assert sorted(e.details["rejectedFields"]) == ["set", "unset"]


MALFORMED = {
    "set-not-a-list": {"set": {"predicate": "aisep:priority", "value": {"iri": "aisep:Should"}}},
    "unset-not-a-list": {"unset": "aisep:priority"},
    "item-not-an-object": {"set": ["aisep:priority"]},
    "item-without-value": {"set": [{"predicate": "aisep:priority"}]},
    "item-without-predicate": {"set": [{"value": {"iri": "aisep:Should"}}]},
    "item-extra-key": {"set": [{"predicate": "aisep:priority", "value": {"iri": "aisep:Should"}, "file": AM4}]},
    "value-not-an-object": {"set": [{"predicate": "aisep:priority", "value": "aisep:Should"}]},
    "value-empty": {"set": one("aisep:priority", {})},
    "value-iri-and-value": {"set": one("skos:note", {"iri": "aisep:Should", "value": "x"})},
    "value-extra-key": {"set": one("skos:note", {"value": "x", "language": "zh"})},
    "value-null": {"set": one("skos:note", {"value": None})},
    "value-list": {"set": one("skos:note", {"value": ["a", "b"]})},
    "iri-not-a-string": {"set": one("aisep:priority", {"iri": 5})},
    "iri-with-turtle": {"set": one("aisep:priority", {"iri": "http://x/> . <http://evil/"})},
    "iri-with-space": {"set": one("aisep:priority", {"iri": "http://x/a b"})},
    "bad-language-tag": {"set": one("skos:note", {"value": "x", "lang": "not a lang"})},
    "bad-datatype": {"set": one("skos:note", {"value": "x", "datatype": "http://x/> <http://y"})},
    "predicate-with-turtle": {"set": one("http://x/p> <http://y", {"value": "x"})},
    "predicate-with-space": {"set": one("http://x/ y", {"value": "x"})},
    "predicate-not-a-string": {"set": one(5, {"value": "x"})},
    "unset-item-not-a-string": {"unset": [5]},
    "unset-item-with-turtle": {"unset": ["http://x/p> ; a <http://y"]},
    "extra-argument-file": {"set": one("aisep:priority", {"iri": "aisep:Should"}), "file": AM4},
    "extra-argument-model": {"set": one("aisep:priority", {"iri": "aisep:Should"}), "model": "procurement"},
}


@pytest.mark.parametrize("kw", list(MALFORMED.values()), ids=list(MALFORMED))
def test_malformed_arguments_are_invalid_argument_and_write_nothing(repo, kw):
    e = refused(repo, "INVALID_ARGUMENT", REQ, **kw)
    assert e.details.get("rejectedFields"), e.details


def test_unknown_prefix_is_refused_and_writes_nothing(repo):
    """§5.12 says an unknown prefix name is INVALID_ARGUMENT; core.expand reads `nope:thing` as slug:local of a model
    `nope`, so the closed world refuses it instead. Either way nothing may be written (the code difference is reported
    to the coordinator, not asserted here)."""
    s = snap(repo)
    with pytest.raises(AisepError) as e:
        sa(repo, REQ, set=one("nope:thing", {"value": "x"}))
    assert e.value.code in ("INVALID_ARGUMENT", "WRITE_REJECTED") and snap(repo) == s


def test_unknown_target_and_argument_errors_come_first(repo):
    e = refused(repo, "ELEMENT_NOT_FOUND", M + "noSuchThing", set=one("aisep:priority", {"iri": "aisep:Should"}))
    assert e.details["rejectedFields"] == ["iri"]
    refused(repo, "ELEMENT_NOT_FOUND", "procurement:noSuchThing", unset=["aisep:priority"])
    refused(repo, "ELEMENT_NOT_FOUND", AISEP + "Must", set=one("skos:note", {"value": "x", "lang": "zh"}))  # a module term
    # §5.12「参数错误先于目标检查报出」
    refused(repo, "INVALID_ARGUMENT", M + "noSuchThing", set=one("rdf:type", {"iri": "am4:BusinessObject"}))
    refused(repo, "INVALID_ARGUMENT", RECORD, unset=["skos:prefLabel"])
    refused(repo, "INVALID_ARGUMENT", M, set=one("arch:inModel", {"iri": M}))


# ------------------------------------------------------------------ boundaries: value forms

def test_value_forms_iri_plain_language_and_datatype(repo):
    r = applied(repo, REQ,
                set=one("skos:note", {"value": "备注", "lang": "zh"}) + one("rdfs:comment", {"value": "plain"})
                + one("owl:deprecated", TRUE) + one("dcterms:isReplacedBy", {"iri": "procurement:supplier"})
                + one("aisep:priority", {"iri": AISEP + "Could"}),
                minus=[tr(REQ, PRIORITY, n(AISEP + "Must"))],
                plus=[tr(REQ, NOTE, lit("备注", "zh")), tr(REQ, "http://www.w3.org/2000/01/rdf-schema#comment", lit("plain")),
                      tr(REQ, DEPRECATED, lit("true", dt=XSD + "boolean")), tr(REQ, REPLACED_BY, n(SUPPLIER)),
                      tr(REQ, PRIORITY, n(AISEP + "Could"))])
    # §5.12: values come back in the shape of the input, IRIs expanded, xsd:string without datatype, keys = full IRIs
    assert r["after"][NOTE] == [{"value": "备注", "lang": "zh"}]
    assert r["after"]["http://www.w3.org/2000/01/rdf-schema#comment"] == [{"value": "plain"}]
    assert r["after"][DEPRECATED] == [{"value": "true", "datatype": XSD + "boolean"}]
    assert r["after"][REPLACED_BY] == [{"iri": SUPPLIER}]
    assert r["after"][PRIORITY] == [{"iri": AISEP + "Could"}] and r["before"][PRIORITY] == [{"iri": AISEP + "Must"}]
    assert violations(repo) == 0


def test_no_prefix_line_is_added_and_only_the_subject_block_changes(repo):
    """am4.ttl declares neither owl: nor dcterms: (§5.12: the new terms are written as full IRIs, no @prefix added)."""
    before = text(repo, AM4)
    assert "owl:" not in before and "dcterms:" not in before
    start = before.index("\n:reqTwoLevelApproval a ") + 1
    end = before.index("\n\n", start)
    applied(repo, REQ, set=one("owl:deprecated", TRUE) + one("dcterms:isReplacedBy", {"iri": SUPPLIER}),
            plus=[tr(REQ, DEPRECATED, lit("true", dt=XSD + "boolean")), tr(REQ, REPLACED_BY, n(SUPPLIER))])
    after = text(repo, AM4)
    assert after[:start] == before[:start] and after.endswith(before[end:])
    assert [l for l in after.splitlines() if l.startswith("@prefix")] == [l for l in before.splitlines() if l.startswith("@prefix")]


SPECIAL = {
    "quotes": 'He said "hi" and \'bye\'',
    "triple-quotes": 'a """ b \'\'\' c',
    "backslashes": "C:\\path\\n not a newline \\u0041 \\",
    "newline-tab": "第一行\n第二行\t制表\n\n空行之后",
    "turtle-injection": '" .\n:evil a am4:BusinessObject ; arch:inModel <https://aisep.example/model/procurement/> .\n:x skos:note "',
    "statement-terminators": "end . ; , # not a comment <iri> @zh ^^xsd:string [] ()",
    "unicode": "中文 émoji 🙂 \u00a0 零宽\u200b结束",
    "leading-trailing-space": "  两端空格  ",
    "empty": "",
    "long": "行\n" * 400,
}


@pytest.mark.parametrize("value", list(SPECIAL.values()), ids=list(SPECIAL))
def test_special_characters_round_trip_exactly(repo, value):
    old = next(o for s, p, o in file_triples(repo, VERIF) if s == n(AC) and p == n(GHERKIN))
    r = applied(repo, AC, set=one("aisep:gherkin", {"value": value}), minus=[tr(AC, GHERKIN, old)], plus=[tr(AC, GHERKIN, lit(value))])
    assert r["after"][GHERKIN] == [{"value": value}] and r["before"][GHERKIN] == [{"value": old.value}]
    assert [f["path"] for f in r["filesChanged"]] == [VERIF]
    assert violations(repo) == 0
    s = snap(repo)
    assert sa(repo, AC, set=one("aisep:gherkin", {"value": value}))["changed"] is False and snap(repo) == s
    res = S.call(cfg(repo), "model_set_attributes", {"iri": AC, "set": one("aisep:gherkin", {"value": value}), "repo": str(repo)})
    assert not res.is_error and res.structured_content["after"][GHERKIN] == [{"value": value}]


@pytest.mark.parametrize("value", ["a\r\nb\rc", "只有一个回车\r", "反斜杠后跟回车\\\r尾", '引号"与\r\n"""三引号'],
                         ids=["crlf", "cr", "backslash-cr", "quotes-crlf"])
def test_carriage_return_round_trips_exactly(repo, value):
    old = next(o for s, p, o in file_triples(repo, VERIF) if s == n(AC) and p == n(GHERKIN))
    r = applied(repo, AC, set=one("aisep:gherkin", {"value": value}), minus=[tr(AC, GHERKIN, old)], plus=[tr(AC, GHERKIN, lit(value))])
    assert r["after"][GHERKIN] == [{"value": value}]
    assert violations(repo) == 0
    s = snap(repo)
    assert sa(repo, AC, set=one("aisep:gherkin", {"value": value}))["changed"] is False and snap(repo) == s
    # a value with U+000D can be replaced again (the escaped form in the file is found and removed)
    applied(repo, AC, set=one("aisep:gherkin", {"value": "后续"}), minus=[tr(AC, GHERKIN, lit(value))], plus=[tr(AC, GHERKIN, lit("后续"))])


@pytest.mark.parametrize("value", ["a\r\nb\rc", "只有一个回车\r"], ids=["crlf", "cr"])
def test_carriage_return_never_corrupts_the_file(repo, value):
    """Whatever the tool does with U+000D, it is either written exactly or refused with nothing written."""
    s, g0 = snap(repo), graph(repo)
    try:
        sa(repo, AC, set=one("aisep:gherkin", {"value": value}))
    except AisepError:
        assert snap(repo) == s
    else:
        assert tr(AC, GHERKIN, lit(value)) in graph(repo) and len(graph(repo)) == len(g0)


def test_non_string_json_value_is_typed_like_model_add_element_attributes(repo):
    """§5.12: `value` has the shape of model_add_element's `attributes` (§5.2). The existing tool turns a JSON number
    into a typed literal; whatever it does, model_set_attributes must do the same (no second口径)."""
    added = W.model_add_element(cfg(repo), "procurement", "am4:BusinessObject", "对照", slug="twin",
                                attributes=one("skos:note", {"value": 5}), repo=str(repo))
    twin = {o for s, p, o in graph(repo) if s == n(added["iri"]) and p == n(NOTE)}
    assert len(twin) == 1
    commit_all(repo, "twin")
    applied(repo, REQ, set=one("skos:note", {"value": 5}), plus=[tr(REQ, NOTE, o) for o in twin])


def test_special_characters_with_language_tag_next_to_other_values(repo):
    a, b = 'x "q" \\ \n y', "plain"
    applied(repo, REQ, set=one("skos:note", {"value": a, "lang": "zh-Hans"}, {"value": b, "lang": "en"}),
            plus=[tr(REQ, NOTE, lit(a, "zh-hans")), tr(REQ, NOTE, lit(b, "en"))])
    applied(repo, REQ, set=one("skos:note", {"value": b, "lang": "en"}), minus=[tr(REQ, NOTE, lit(a, "zh-hans"))])


# ------------------------------------------------------------------ boundaries: dryRun

@pytest.mark.parametrize("kw", [
    {"set": one("aisep:priority", {"iri": "aisep:Should"})},
    {"unset": ["aisep:priority"]},
    {"set": one("skos:note", {"value": "甲\n乙", "lang": "zh"}, {"value": "b", "lang": "en"}) + one("owl:deprecated", TRUE)},
], ids=["set", "unset", "multi"])
def test_dry_run_writes_nothing_and_predicts_the_real_result(repo, kw):
    s, g = snap(repo), git_state(repo)
    dry = sa(repo, REQ, dryRun=True, **kw)
    assert snap(repo) == s and git_state(repo) == g and git(repo, "status", "--porcelain") == ""
    assert dry["changed"] is True and dry.get("dryRun") is True
    again = sa(repo, REQ, dryRun=True, **kw)                 # a dry run does not make the next one a no-op
    assert again["changed"] is True and snap(repo) == s
    real = sa(repo, REQ, **kw)
    assert real["changed"] is True and real.get("dryRun") is False
    assert {k: v for k, v in dry.items() if k != "dryRun"} == {k: v for k, v in real.items() if k != "dryRun"}
    assert [f["sha256After"] for f in real["filesChanged"]] == [snap(repo)[f["path"]] for f in real["filesChanged"]]
    after = sa(repo, REQ, dryRun=True, **kw)                 # dry run of an already applied change
    assert after["changed"] is False and after["filesChanged"] == []


# ------------------------------------------------------------------ boundaries: where the text goes

def test_value_in_a_separate_statement_is_replaced(repo):
    append(repo, AM4, '\n:supplier skos:note "旧备注"@zh .\n')
    assert violations(repo) == 0
    commit_all(repo, "a note in its own statement")
    applied(repo, SUPPLIER, set=one("skos:note", {"value": "新备注", "lang": "zh"}),
            minus=[tr(SUPPLIER, NOTE, lit("旧备注", "zh"))], plus=[tr(SUPPLIER, NOTE, lit("新备注", "zh"))])
    assert worktree_diff(repo) == [(SUPPLIER, "modified", [NOTE])]
    applied(repo, SUPPLIER, unset=["skos:note"], minus=[tr(SUPPLIER, NOTE, lit("新备注", "zh"))])
    assert violations(repo) == 0


def test_unchanged_values_stay_in_their_file_and_new_values_follow_5_12(repo):
    """§5.12: 值没有变的三元组留在原处；新值写进被替换的三元组所在的文件，没有被替换的值时写进 rdf:type 所在的文件。"""
    append(repo, GOVTTL, '\n:supplier skos:note "保留"@zh .\n')
    assert violations(repo) == 0
    commit_all(repo, "a note of :supplier in governance.ttl")
    keep, new, repl = tr(SUPPLIER, NOTE, lit("保留", "zh")), tr(SUPPLIER, NOTE, lit("新增", "zh")), tr(SUPPLIER, NOTE, lit("替换", "zh"))
    assert tr(SUPPLIER, RDF_TYPE, n("https://meta.linked.archi/archimate4/onto#BusinessActor")) in file_triples(repo, AM4) \
        or any(s == n(SUPPLIER) and p == n(RDF_TYPE) for s, p, _ in file_triples(repo, AM4))
    gov = snap(repo)[GOVTTL]
    r = applied(repo, SUPPLIER, set=one("skos:note", {"value": "保留", "lang": "zh"}, {"value": "新增", "lang": "zh"}), plus=[new])
    assert snap(repo)[GOVTTL] == gov and keep in file_triples(repo, GOVTTL)       # the kept value did not move
    assert new in file_triples(repo, AM4) and [f["path"] for f in r["filesChanged"]] == [AM4]
    commit_all(repo, "second note")
    am4 = snap(repo)[AM4]
    r = applied(repo, SUPPLIER, set=one("skos:note", {"value": "新增", "lang": "zh"}, {"value": "替换", "lang": "zh"}),
                minus=[keep], plus=[repl])
    assert repl in file_triples(repo, GOVTTL) and snap(repo)[AM4] == am4          # written where the replaced one was
    assert [f["path"] for f in r["filesChanged"]] == [GOVTTL]
    assert violations(repo) == 0


def test_replaced_values_in_several_files_new_value_goes_to_the_first_file_by_path(repo):
    """§5.12: 被替换的值分布在多个文件里时，新值写进其中按仓库相对路径排在最前的那个文件
    （不是 rdf:type 所在的 am4.ttl，也不是后追加的、路径更靠后的 verification.ttl）。"""
    append(repo, VERIF, '\n:supplier skos:note "旧二"@zh .\n')     # appended first, but sorts after governance.ttl
    append(repo, GOVTTL, '\n:supplier skos:note "旧一"@zh .\n')
    assert GOVTTL < VERIF and violations(repo) == 0
    commit_all(repo, "notes of :supplier in two files other than am4.ttl")
    old1, old2, new = (tr(SUPPLIER, NOTE, lit(v, "zh")) for v in ("旧一", "旧二", "新"))
    am4 = snap(repo)[AM4]
    r = applied(repo, SUPPLIER, set=one("skos:note", {"value": "新", "lang": "zh"}), minus=[old1, old2], plus=[new])
    assert new in file_triples(repo, GOVTTL) and new not in file_triples(repo, VERIF)
    assert snap(repo)[AM4] == am4
    assert sorted(f["path"] for f in r["filesChanged"]) == sorted([GOVTTL, VERIF])
    assert violations(repo) == 0


RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"


def _bnode_value(repo):
    append(repo, AM4, f'\n:supplier <{RDFS_COMMENT}> [ <{RDFS_COMMENT}> "嵌套" ] .\n')
    assert violations(repo) == 0
    commit_all(repo, "a blank-node value")
    assert any(s == n(SUPPLIER) and p == n(RDFS_COMMENT) and isinstance(o, ox.BlankNode) for s, p, o in graph(repo))


@pytest.mark.parametrize("kw", [{"unset": ["rdfs:comment"]}, {"set": one("rdfs:comment", {"value": "x"})}], ids=["unset", "set"])
def test_blank_node_value_is_edit_unsafe_and_untouched(repo, kw):
    _bnode_value(repo)
    refused(repo, "EDIT_UNSAFE", SUPPLIER, **kw)


@pytest.mark.parametrize("kw", [{"unset": ["rdfs:comment"]}, {"set": one("rdfs:comment", {"value": "x"})}], ids=["unset", "set"])
def test_blank_node_value_result_matches_the_graph(repo, kw):
    """Weaker than the previous test and independent of the error code: a successful result must tell the truth."""
    _bnode_value(repo)
    try:
        r = sa(repo, SUPPLIER, **kw)
    except AisepError:
        return
    left = [o for s, p, o in graph(repo) if s == n(SUPPLIER) and p == n(RDFS_COMMENT)]
    assert len(left) == len(r["after"][RDFS_COMMENT]), (left, r["after"])


def test_blank_node_value_on_another_predicate_does_not_block(repo):
    """The EDIT_UNSAFE refusal is per replaced predicate: a blank-node value elsewhere on the subject is left alone."""
    _bnode_value(repo)
    g0 = graph(repo)                       # blank-node labels differ between parses, so compare without them
    r = sa(repo, SUPPLIER, set=one("skos:note", {"value": "旁边", "lang": "zh"}))
    assert r["changed"] is True and [f["path"] for f in r["filesChanged"]] == [AM4]
    g1 = graph(repo)
    named = lambda g: {t for t in g if not any(isinstance(x, ox.BlankNode) for x in t)}
    assert tr(SUPPLIER, NOTE, lit("旁边", "zh")) in g1 and len(g1) == len(g0) + 1
    assert named(g1) - named(g0) == {tr(SUPPLIER, NOTE, lit("旁边", "zh"))} and named(g0) <= named(g1)
    assert violations(repo) == 0
    assert any(s == n(SUPPLIER) and p == n(RDFS_COMMENT) and isinstance(o, ox.BlankNode) for s, p, o in graph(repo))


def test_inline_comment_after_the_statement_survives(repo):
    """The priority line of :reqTwoLevelApproval ends in a `# …` comment; the rewritten file must still parse and keep it."""
    assert "# MoSCoW" in text(repo, AM4)
    applied(repo, REQ, unset=["aisep:priority"], minus=[tr(REQ, PRIORITY, n(AISEP + "Must"))])
    assert "# ── Relationships" in text(repo, AM4)       # the section comment right after the block is intact


# ------------------------------------------------------------------ boundaries: relationship and view as target

def test_relationship_as_target_keeps_its_ends(repo):
    ends = {(p, o) for s, p, o in graph(repo) if s == n(REL) and p.value in (ARCH + "source", ARCH + "target", RDF_TYPE)}
    assert len(ends) == 3
    r = applied(repo, "procurement:rel-quoteApproval-realizes-reqTwoLevelApproval",
                set=one("skos:note", {"value": "关系备注", "lang": "zh"}), plus=[tr(REL, NOTE, lit("关系备注", "zh"))])
    assert r["iri"] == REL and [f["path"] for f in r["filesChanged"]] == [AM4]
    assert {(p, o) for s, p, o in graph(repo) if s == n(REL) and p.value in (ARCH + "source", ARCH + "target", RDF_TYPE)} == ends
    assert worktree_diff(repo) == [(REL, "modified", [NOTE])]
    assert violations(repo) == 0
    applied(repo, REL, unset=["skos:note"], minus=[tr(REL, NOTE, lit("关系备注", "zh"))])
    assert worktree_diff(repo) == []


def test_view_as_target(repo):
    """A view is a model member (arch:inModel) and is not on §5.12's protected list, so it is an ordinary target
    (tester's assumption; §5.12 only says「元素或关系」). Membership of other elements in the view is not touched."""
    vp = "<https://meta.linked.archi/archimate4/viewpoints#ApplicationCooperationViewpoint>"
    append(repo, AM4, f"\n:v1 a arch:Diagram ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"视图\"@zh ;\n"
                      f"    arch:viewConformsToViewpoint {vp} .\n:supplier arch:inView :v1 .\n")
    assert violations(repo) == 0
    commit_all(repo, "a view")
    applied(repo, "procurement:v1", set=one("skos:note", {"value": "视图备注", "lang": "zh"}),
            plus=[tr(M + "v1", NOTE, lit("视图备注", "zh"))])
    assert tr(SUPPLIER, ARCH + "inView", n(M + "v1")) in graph(repo)
    refused(repo, "INVALID_ARGUMENT", M + "v1", set=one("rdf:type", {"iri": "arch:Catalog"}))
    assert violations(repo) == 0


def test_adr032_view_facts_today(repo):
    """ADR-032 背景所述现状（PR #179 评审 B1、B2、B4）：① 视图缺 arch:inModel 已是 L1 Violation；② ArchiMate 视图的
    视点不符已由 L3 给 Warning；③ model_set_attributes 现在就能改视图的视点（arch:viewConformsToViewpoint 不在不接受表）。"""
    vp = "<https://meta.linked.archi/archimate4/viewpoints#ApplicationCooperationViewpoint>"
    append(repo, AM4, f"\n:v1 a arch:Diagram ;\n    skos:prefLabel \"视图\"@zh ;\n"
                      f"    arch:viewConformsToViewpoint {vp} .\n:supplier arch:inView :v1 .\n")
    fs = T.model_check(cfg(repo), repo=str(repo))["findings"]
    assert any(f["severity"] == "Violation" and f["layer"] == "L1" and "no arch:inModel" in f["message"] for f in fs), fs
    git(repo, "checkout", "--", AM4)
    append(repo, AM4, f"\n:v1 a arch:Diagram ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"视图\"@zh ;\n"
                      f"    arch:viewConformsToViewpoint {vp} .\n:supplier arch:inView :v1 .\n")
    fs = T.model_validate(cfg(repo), repo=str(repo))["findings"]
    assert any(f["severity"] == "Warning" and "not allowed in viewpoint" in f["message"] for f in fs), fs
    commit_all(repo, "a view")
    vp2 = "https://meta.linked.archi/archimate4/viewpoints#ApplicationUsageViewpoint"
    applied(repo, "procurement:v1", set=one("arch:viewConformsToViewpoint", {"iri": vp2}),
            minus=[tr(M + "v1", ARCH + "viewConformsToViewpoint", n(vp[1:-1]))],
            plus=[tr(M + "v1", ARCH + "viewConformsToViewpoint", n(vp2))])


# ------------------------------------------------------------------ followup 6: one value口径 with model_add_element

BAD_VALUES = {
    "nul": {"value": "a\x00b"}, "esc": {"value": "a\x1bb"}, "c1-nel": {"value": "a\x85b"}, "line-separator": {"value": "a b"},
    "control-in-lang-literal": {"value": "a\x07b", "lang": "zh"}, "control-in-typed-literal": {"value": "1\x00", "datatype": "xsd:integer"},
    "lang-and-datatype": {"value": "x", "lang": "zh", "datatype": "xsd:string"}, "empty-lang": {"value": "x", "lang": ""},
    "bnode-iri": {"iri": "_:b"}, "bnode-datatype": {"value": "x", "datatype": "_:dt"},
    "null-lang": {"value": "x", "lang": None},
    "empty-datatype": {"value": "x", "datatype": ""}, "null-datatype": {"value": "x", "datatype": None},  # issue #138
}


def add_twin(repo, attributes):
    return W.model_add_element(cfg(repo), "procurement", "am4:BusinessObject", "对照", slug="twin",
                               attributes=attributes, repo=str(repo))


@pytest.mark.parametrize("value", BAD_VALUES.values(), ids=BAD_VALUES.keys())
def test_bad_value_is_refused_by_both_tools(repo, value):
    e = refused(repo, "INVALID_ARGUMENT", REQ, set=one("skos:note", value))
    assert e.details["rejectedFields"] == ["set"]
    s = snap(repo)
    with pytest.raises(AisepError) as e:
        add_twin(repo, one("skos:note", value))
    assert e.value.code == "INVALID_ARGUMENT" and e.value.details["rejectedFields"] == ["attributes"]
    assert snap(repo) == s


def test_bnode_predicate_is_refused_by_both_tools(repo):
    e = refused(repo, "INVALID_ARGUMENT", REQ, set=one("_:p", {"value": "x"}))
    assert e.details["rejectedFields"] == ["set"]
    assert refused(repo, "INVALID_ARGUMENT", REQ, unset=["_:p"]).details["rejectedFields"] == ["unset"]
    s = snap(repo)
    with pytest.raises(AisepError) as e:
        add_twin(repo, one("_:p", {"value": "x"}))
    assert e.value.code == "INVALID_ARGUMENT" and e.value.details["rejectedFields"] == ["attributes"]
    assert snap(repo) == s


@pytest.mark.parametrize("value, term", [
    ({"value": "第一行\n第二行\t尾", "lang": "zh"}, lit("第一行\n第二行\t尾", "zh")),
    ({"value": "true", "datatype": "xsd:boolean"}, lit("true", dt=XSD + "boolean")),
    ({"value": "无标签"}, lit("无标签")),
    ({"value": "回车\r\n与\r单独"}, lit("回车\r\n与\r单独")),
], ids=["multiline-lang", "typed", "plain", "carriage-return"])
def test_good_value_is_written_the_same_by_both_tools(repo, value, term):
    added = add_twin(repo, one("skos:note", value))
    assert tr(added["iri"], NOTE, term) in graph(repo)
    commit_all(repo, "twin")
    applied(repo, REQ, set=one("skos:note", value), plus=[tr(REQ, NOTE, term)])
    assert violations(repo) == 0


# ------------------------------------------------------------------ followup 13: arch:inView belongs to view tools

@pytest.mark.parametrize("kw", [
    {"set": one("arch:inView", {"iri": "procurement:v1"})},
    {"set": one(ARCH + "inView", {"iri": M + "v1"})},
    {"unset": ["arch:inView"]},
], ids=["set", "set-full-iri", "unset"])
def test_in_view_is_not_settable(repo, kw):
    vp = "<https://meta.linked.archi/archimate4/viewpoints#ApplicationCooperationViewpoint>"
    append(repo, AM4, f"\n:v1 a arch:Diagram ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"视图\"@zh ;\n"
                      f"    arch:viewConformsToViewpoint {vp} .\n:supplier arch:inView :v1 .\n")
    commit_all(repo, "a view")
    field = next(iter(kw))
    assert refused(repo, "INVALID_ARGUMENT", SUPPLIER, **kw).details["rejectedFields"] == [field]
    assert tr(SUPPLIER, ARCH + "inView", n(M + "v1")) in graph(repo)


@pytest.mark.parametrize("predicate", ["arch:inView", ARCH + "inView"], ids=["prefixed", "full-iri"])
def test_in_view_is_refused_by_add_element(repo, predicate):
    """Issue #138: model_add_element's attributes take the same stand as model_set_attributes on arch:inView."""
    vp = "<https://meta.linked.archi/archimate4/viewpoints#ApplicationCooperationViewpoint>"
    append(repo, AM4, f"\n:v1 a arch:Diagram ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"视图\"@zh ;\n"
                      f"    arch:viewConformsToViewpoint {vp} .\n")
    commit_all(repo, "a view")
    s = snap(repo)
    with pytest.raises(AisepError) as e:
        add_twin(repo, one(predicate, {"iri": M + "v1"}))
    assert e.value.code == "INVALID_ARGUMENT" and e.value.details["rejectedFields"] == ["attributes"]
    assert snap(repo) == s
    added = add_twin(repo, one("skos:note", {"value": "不进视图", "lang": "zh"}))  # the same call without inView is written
    assert tr(added["iri"], NOTE, lit("不进视图", "zh")) in graph(repo)
    assert not any(p.value == ARCH + "inView" and s.value == added["iri"] for s, p, _ in graph(repo))


# ------------------------------------------------------------------ issue #164: one list of reserved predicates

RESERVED = [  # (predicate as written, a value, the model_set_attributes target that carries it)
    ("rdf:type", {"iri": "am4:BusinessObject"}, REQ),
    ("arch:inModel", {"iri": M}, REQ),  # the element's own model: written twice before #164
    ("arch:inModel", {"iri": "https://aisep.example/model/other/"}, REQ),
    (ARCH + "inModel", {"iri": M}, REQ),
    ("arch:source", {"iri": SUPPLIER}, REL),
    ("arch:target", {"iri": REQ}, REL),
    (ARCH + "target", {"iri": REQ}, REL),
    ("arch:inView", {"iri": M + "v1"}, REQ),
]
RESERVED_IDS = ["type", "inModel-own", "inModel-other", "inModel-full-iri", "source", "target", "target-full-iri", "inView"]


@pytest.mark.parametrize("predicate,value,target", RESERVED, ids=RESERVED_IDS)
def test_reserved_predicates_are_refused_by_add_element(repo, predicate, value, target):
    """Issue #164: model_add_element's attributes refuse what model_set_attributes refuses (bar the three labels), as
    an argument error up front, not left to L1 (WRITE_REJECTED) or, for the element's own model, written twice."""
    s = snap(repo)
    with pytest.raises(AisepError) as e:
        add_twin(repo, one(predicate, value))
    assert e.value.code == "INVALID_ARGUMENT" and e.value.details["rejectedFields"] == ["attributes"]
    assert snap(repo) == s


@pytest.mark.parametrize("predicate,value,target", RESERVED, ids=RESERVED_IDS)
def test_both_tools_give_one_reason_for_a_reserved_predicate(repo, predicate, value, target):
    """Issue #164: the reason a reserved predicate is refused is written once and both tools give it word for word."""
    with pytest.raises(AisepError) as e:
        add_twin(repo, one(predicate, value))
    by_add = e.value.message
    by_set = refused(repo, "INVALID_ARGUMENT", target, set=one(predicate, value)).message
    assert by_add.startswith("attributes 不能含 ") and by_set.startswith("set 不能含 ")
    assert by_add.removeprefix("attributes ") == by_set.removeprefix("set ")
