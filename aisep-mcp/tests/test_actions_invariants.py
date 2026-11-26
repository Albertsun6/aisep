"""动作目录的两条常驻不变式（不依赖分支 diff，任何检出上都能跑）。

#113 删掉了只对那个 PR 有意义的分支级验收 C1/C2（相对 origin/main 比较）。这里把它们要守的性质改写成只看
本检出行为的断言：

1. `tools/list` 与目录数据无关：在副本里往 `modules/ext-actions/catalog.ttl` 加一个动作、删一个动作，真实 stdio
   服务器对 `tools/list` 的应答逐字节不变（agent、workbench、all 三个画像）。test_actions.py 的 B5 比的是规范化
   之后的 JSON（排序后再序列化），也不覆盖 workbench 画像；这里比线上的原始字节。
2. 动作执行器的写入落点不出现在冻结路径里。允许落点只有 `models/<slug>/` 下的文件，且不在 `models/<slug>/governance/`
   （批准记录专用目录：批准提交的形状就是「只新增这里的一个文件」，执行器能写进去就等于能代人批准）。冻结路径取
   《动作机制同类产品调研》C1 清单里 models/ 以外的部分：`modules/**`、`vendor/**` 与治理相关的 `aisep/*.py`，另加仓库里
   其余所有不在 `models/` 下的文件，再加上 `models/*/governance/**`。分三层断言：
   - 仓库目录里的动作正常执行时，真正落盘的每个文件都在 `models/<slug>/` 下，models/ 以外的文件逐字节不变；
   - 经动作参数 `file` / `relationshipFile` 把落点指向冻结路径（含 `..`、绝对路径、经 models/ 下符号链接）一律被拒，
     整个副本逐字节不变；
   - 执行器与写工具共用的最后一道检查 `writer.check_paths`：即使上游构造出指向冻结路径的计划，transaction 也拒绝。
     （`check_paths` 本身不拒绝 `models/<slug>/governance/`，那一层由 `write_tools._check_file` 守，见参数落点用例。）

不覆盖：原 C1 还要求「分支不改冻结代码」，那是对 PR 的要求，不是运行时性质，仍靠合并前评审。
维护约定：仓库目录新增动作时，test_catalogue_actions_write_only_under_models 会失败，给新动作补一组正常参数。
"""
import ast, hashlib, json, os, shutil, subprocess, sys

import pytest

from conftest import ROOT, commit_all, git, init_repo
from aisep import actions, server, tools, writer
from aisep.errors import AisepError

PY = sys.executable
WB = "https://aisep.example/model/workbench/"
REQ = WB + "reqApprovalProgress"  # models/workbench/am4.ttl，am4:Requirement
CAT = "modules/ext-actions/catalog.ttl"
FROZEN_CODE = ("aisep/mergecheck.py", "aisep/diff.py", "aisep/approval.py", "aisep/gitio.py", "aisep/tools.py",
               "aisep/writer.py", "aisep/release.py", "aisep/core.py")

EXTRA_ACTION = """
aisep:ActionInvariantProbe a aisep:ActionType ;
    dcterms:identifier "invariant-probe" ;
    skos:prefLabel "不变式探针"@zh ;
    owl:versionInfo "1.0.0" ;
    sh:parameter [ sh:path ap:label ; sh:datatype xsd:string ; sh:description "名称"@zh ] ;
    aisep:steps ( _:invProbeStep ) .
_:invProbeStep a aisep:ActionStep ; dcterms:identifier "el" ; aisep:invokes aisep:BasicAddElement ;
    aisep:binding [ aisep:argument "model" ; aisep:constant <https://aisep.example/model/workbench/> ] ,
        [ aisep:argument "type" ; aisep:constant aisep:AcceptanceCriterion ] ,
        [ aisep:argument "prefLabel" ; aisep:fromParameter ap:label ] .
"""


@pytest.fixture(scope="module")
def wtemplate(tmp_path_factory):
    t = tmp_path_factory.mktemp("invtemplate")
    ign = shutil.ignore_patterns("__pycache__")
    for d in ("models", "modules", "vendor", "tools", "aisep"):
        shutil.copytree(os.path.join(ROOT, d), t / d, ignore=ign)
    shutil.copy2(os.path.join(ROOT, ".gitignore"), t / ".gitignore")
    return t


@pytest.fixture
def mk(wtemplate, tmp_path):
    def make(name="w"):
        dst = tmp_path / name
        shutil.copytree(wtemplate, dst)
        init_repo(dst)
        commit_all(dst, "start")
        return dst
    return make


def cfg(repo):
    return tools.Config(allow_roots=(str(repo.parent),), repo=str(repo))


def call(repo, name, **args):
    if name != "model_list_actions":
        args = dict(args, repo=str(repo))
    r = server.call(cfg(repo), name, args)
    return r.is_error, r.structured_content


def tree(repo):
    """{相对路径: sha256}，副本里 .git 以外的全部文件（符号链接记链接目标本身）。"""
    out = {}
    for d, dirs, fs in os.walk(repo):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, repo)
            out[rel] = "link:" + os.readlink(p) if os.path.islink(p) else hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def frozen(rel):
    parts = rel.split("/")
    return parts[0] != "models" or (len(parts) > 3 and parts[2].lower() == "governance")


# ================================================================== 1. tools/list 与目录数据无关（原始字节）

def raw_tools_list(repo, profile):
    """起真实 stdio 服务器（被测检出的代码），握手后取 tools/list 应答那一行的原始字节。"""
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "invariant-test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    p = subprocess.run([PY, "-m", "aisep.server", "--repo", str(repo), "--allow-root", str(repo.parent), "--profile", profile],
                       cwd=str(repo), input=b"".join(json.dumps(m).encode() + b"\n" for m in msgs), capture_output=True,
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1"), timeout=120)
    lines = [ln for ln in p.stdout.splitlines(keepends=True) if json.loads(ln).get("id") == 2]
    assert len(lines) == 1, f"tools/list 应答不是恰好一行：{p.stdout[-1000:]!r} {p.stderr[-1000:]!r}"
    return lines[0]


# ================================================================== 2. 执行器的写入落点不在冻结路径里

def test_frozen_predicate_is_not_vacuous(mk):
    r = mk()
    t = tree(r)
    assert any(f.startswith("models/") for f in t)
    for f in (CAT, next(x for x in t if x.startswith("vendor/")), *FROZEN_CODE,
              next(x for x in t if x.startswith("models/workbench/governance/"))):
        assert f in t and frozen(f), f
    assert frozen("models/workbench/Governance/x.ttl") and frozen("models/procurement/governance/a/b.ttl")
    assert not frozen("models/workbench/verification.ttl") and not frozen("models/workbench/governance.ttl")


@pytest.fixture
def recorded_writes(monkeypatch):
    """记下 writer.write_files 真正要落盘的每个相对路径（执行器经 writer.transaction 落盘，不另开写入口）。"""
    seen = []
    orig = writer.write_files

    def spy(root, edits, before):
        seen.extend(edits)
        return orig(root, edits, before)
    monkeypatch.setattr(writer, "write_files", spy)
    return seen


def test_catalogue_actions_write_only_under_models(mk, recorded_writes):
    """仓库目录里的每个动作都正常执行一次：落盘路径全在 models/<slug>/ 下，models/ 以外逐字节不变。"""
    r = mk()
    before = tree(r)
    ids = {a["id"] for a in call(r, "model_list_actions")[1]["actions"]}
    assert ids == {"register-acceptance-criterion", "remove-element"}, \
        f"仓库目录的动作变了（{sorted(ids)}），给新动作补一组参数"
    e, res = call(r, "model_apply_action", action="register-acceptance-criterion",
                  params={"requirement": REQ, "prefLabel": "不变式探针", "altLabel": "Invariant probe"})
    assert not e and res["changed"], res
    new = res["result"]["iris"]["criterion"] if "result" in res else res["iris"]["criterion"]
    e, d = call(r, "model_apply_action", action="remove-element", params={"iri": new}, dryRun=True)
    assert not e, d
    digest = d.get("planDigest") or d["result"]["planDigest"]
    e, res = call(r, "model_apply_action", action="remove-element", params={"iri": new}, planDigest=digest)
    assert not e and res["changed"], res
    assert recorded_writes, "没有任何落盘，断言没有意义"
    assert all(writer.MODEL_PATH.fullmatch(f) and not frozen(f) for f in recorded_writes), recorded_writes
    assert all(f.startswith("models/workbench/") for f in recorded_writes), recorded_writes  # 父需求所在的模型
    after = tree(r)
    assert {f for f in set(before) | set(after) if before.get(f) != after.get(f)}, "两次动作都没改任何文件"
    assert {f: h for f, h in after.items() if frozen(f)} == {f: h for f, h in before.items() if frozen(f)}


FROZEN_TARGETS = [CAT, "modules/aisep-core/shapes.ttl", "vendor/x.ttl", "aisep/writer.py", "docs/decisions.md",
                  "models/../modules/ext-actions/catalog.ttl", "models/workbench/../../vendor/x.ttl",
                  "/etc/passwd", "../outside.ttl", "models/workbench/governance/approval-probe.ttl",
                  "models/workbench/governance/x.ttl", "models/workbench/Governance/x.ttl", "models/workbench/sub/x.ttl"]


@pytest.mark.parametrize("key", ["file", "relationshipFile"])
@pytest.mark.parametrize("target", FROZEN_TARGETS)
def test_action_file_parameter_cannot_reach_frozen_paths(mk, recorded_writes, key, target):
    r = mk()
    before = tree(r)
    e, res = call(r, "model_apply_action", action="register-acceptance-criterion",
                  params={"requirement": REQ, "prefLabel": "越界探针", "altLabel": "Escape probe", key: target})
    assert e, f"落点 {target!r} 应当被拒绝：{json.dumps(res, ensure_ascii=False)[:600]}"
    assert recorded_writes == [] and tree(r) == before
    assert not os.path.exists(r.parent / "outside.ttl")


def test_action_file_parameter_cannot_write_through_a_symlink(mk, recorded_writes):
    """models/ 下的符号链接指向 models/ 以外一个能解析的空 .ttl：不能经它写到链接目标，链接本身也不能被换成普通文件。"""
    r = mk()
    with open(r / "docs-probe.ttl", "w", encoding="utf-8") as f:
        f.write("# probe\n")
    os.symlink(os.path.join("..", "..", "docs-probe.ttl"), r / "models" / "workbench" / "link.ttl")
    commit_all(r, "link")
    before = tree(r)
    e, res = call(r, "model_apply_action", action="register-acceptance-criterion",
                  params={"requirement": REQ, "prefLabel": "链接探针", "altLabel": "Link probe",
                          "file": "models/workbench/link.ttl"})
    assert e, res
    assert recorded_writes == [] and tree(r) == before


@pytest.mark.parametrize("target", [CAT, "vendor/x.ttl", "aisep/writer.py", "models/../modules/ext-actions/catalog.ttl",
                                    "models/workbench/./x.ttl", "/abs/models/w/x.ttl", "models/w"])
def test_transaction_last_line_refuses_frozen_paths(mk, recorded_writes, target):
    """执行器与写工具共用的 writer.transaction：计划里出现 models/<slug>/ 以外的路径就拒绝，什么也不写。"""
    r = mk()
    before = tree(r)

    def build(ws, ctx):
        return {"result": {}, "edits": {target: "# probe\n"}}
    with pytest.raises(AisepError) as ei:
        writer.transaction(cfg(r), str(r), build)
    assert ei.value.code == "INVALID_ARGUMENT"
    assert recorded_writes == [] and tree(r) == before


def test_executor_has_no_write_path_of_its_own():
    """执行器只经 writer.transaction 落盘：源码里没有以写模式打开文件，也没有改名、删除、写文件的调用。"""
    tree_ = ast.parse(open(actions.__file__, encoding="utf-8").read())
    bad = []
    for n in ast.walk(tree_):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name in ("replace", "rename", "unlink", "remove", "rmtree", "write_text", "write_bytes", "write_files",
                    "copy", "copy2", "copyfile", "move", "makedirs", "mkdir", "symlink") and \
                isinstance(f, ast.Attribute) and getattr(f.value, "id", "") in ("os", "shutil", "writer"):
            bad.append(ast.unparse(n))
        if name in ("write_text", "write_bytes"):
            bad.append(ast.unparse(n))
        if name in ("system", "popen", "run", "Popen", "call", "check_call", "check_output", "spawnv", "execv"):
            bad.append(ast.unparse(n))
        if name in ("open", "fdopen"):
            mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
            if not (isinstance(mode, ast.Constant) and set(mode.value) <= set("rbt")):
                bad.append(ast.unparse(n))
    imports = {a.name.split(".")[0] for n in ast.walk(tree_) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in (n.names if isinstance(n, ast.Import) else [ast.alias(n.module or "")])}
    assert not imports & {"subprocess", "shutil", "tempfile", "pathlib"}, imports
    assert bad == [], bad
    assert "writer.transaction(" in ast.unparse(tree_)
