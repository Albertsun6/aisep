"""L4-B「MCP 入口校验 B」的先行回归测试（gitio.py、tools.py、core.py、approval.py 那一半）。

每条对应评估（~/code/AISEP/_backup/archive-rescue/评估-20261121/findings.json）里的一条缺陷，在 9430999 上应当失败。标记方式见
fixtures/defect.py：只有测试明确认出那条缺陷时才是 XFAIL；函数不存在、改名、抛别的异常都按失败报出。
L4-B 修好了除 MCP-1 以外的全部缺陷并摘掉了对应的 `@L4B` 标记；MCP-1 由 issue #60 的 PR（查询在无网络子进程里执行）修好并摘标记。名字带 guard 的是护栏。

- MCP-1：model_query 的 SERVICE 词法过滤误杀 am4:Service、字面量、变量名、注释
- CORE-1 / SEC-5 / CORE-V1：model_impact 的 focus 拼进 SPARQL，可注入 SERVICE
- MCP-2：governance_record_approval 接受带换行的 sessionRef
- CORE-2：畸形但可解析的模型让 gate 抛异常（INTERNAL）而不是报违规
- SEC-3：repo 指向检出内的伪仓库目录时执行它的 core.fsmonitor
- MCP-5（读工具那一半）：非法模型名报 MODEL_NOT_FOUND 或被悄悄当成别的模型
"""
import contextlib, os, socket, threading

import pytest

from aisep import approval as A
from aisep import tools as T
from aisep.errors import AisepError
from conftest import git
from fixtures.defect import expect, open_defect
from fixtures.topology import M, PREFIXES, Topo

L4B = lambda ids: open_defect("L4-B", ids)
AM4_NS = "https://meta.linked.archi/archimate4/onto#"


def cfg(root):
    return T.Config(allow_roots=(str(root),), repo=str(root))


@contextlib.contextmanager
def listener():
    """127.0.0.1 上的随机端口：记录每次连接，接受后立刻关闭（不回 HTTP 响应，调用方很快报错而不是挂住）。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    s.settimeout(0.1)
    hits, stop = [], threading.Event()

    def loop():
        while not stop.is_set():
            try:
                c, _ = s.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            hits.append(1)
            c.close()

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    try:
        yield s.getsockname()[1], hits
    finally:
        stop.set()
        th.join(2)
        s.close()


def rejected(e):
    return e.details.get("rejectedFields", []) if isinstance(e.details, dict) else []


# ================================================================== MCP-1：SERVICE 误杀

# 参照查询：同样的语义，用拆开的字符串绕过词法过滤，得到 am4:Service 的实例
SERVICE_REF = 'SELECT ?x WHERE { ?x a ?t FILTER(STR(?t) = CONCAT("%s", "Serv", "ice")) } ORDER BY ?x' % AM4_NS

TEXT_WITH_SERVICE = {
    "前缀名am4:Service": "SELECT ?x WHERE { ?x a am4:Service } ORDER BY ?x",
    "完整IRI": f"SELECT ?x WHERE {{ ?x a <{AM4_NS}Service> }} ORDER BY ?x",
    "字符串字面量": "SELECT ?x WHERE { ?x skos:prefLabel ?l FILTER(CONTAINS(LCASE(STR(?l)), 'service')) }",
    "变量名": "SELECT ?service WHERE { ?service a am4:BusinessActor }",
    "注释": "# every service actor\nSELECT ?x WHERE { ?x a am4:BusinessActor }",
}


@pytest.mark.parametrize("name", sorted(TEXT_WITH_SERVICE))
def test_mcp1_query_mentioning_service_is_not_refused(repo, name):
    q = TEXT_WITH_SERVICE[name]
    try:
        r = T.model_query(cfg(repo), q)
    except AisepError as e:
        expect(e.code != "QUERY_NOT_READONLY", f"只读查询因为文本里有 service 被拒：{e.message}")
        raise
    assert r["kind"] == "select" and not r["truncated"]
    if name in ("前缀名am4:Service", "完整IRI"):
        want = T.model_query(cfg(repo), SERVICE_REF)["rows"]
        assert want, "夹具前提：采购示例里有 am4:Service 实例"
        assert r["rows"] == want


REAL_SERVICE = {
    "大写": "SELECT * WHERE { SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "小写": "SELECT * WHERE { service <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "SILENT": "SELECT * WHERE { SERVICE SILENT <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "紧贴尖括号": "SELECT * WHERE { ?s ?p ?o . SERVICE<http://127.0.0.1:{port}/q>{ ?a ?b ?c } }",
    "注释之后": "SELECT * WHERE { # service\n SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "字面量之后": "SELECT * WHERE { ?s ?p 'service' . SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "变量端点": "SELECT * WHERE { BIND(<http://127.0.0.1:{port}/q> AS ?e) SERVICE ?e { ?a ?b ?c } }",
}


@pytest.mark.parametrize("name", sorted(REAL_SERVICE))
def test_mcp1_guard_real_service_clause_still_refused(repo, name):
    """护栏：修 MCP-1 时不能把真正的 SERVICE 子句放进来（pyoxigraph 会真的发 HTTP 请求）。"""
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), REAL_SERVICE[name].replace("{port}", str(port)))
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()
    assert not hits


# ================================================================== CORE-1 / SEC-5 / CORE-V1：focus 注入

def test_core1_impact_focus_cannot_inject_service(repo):
    fn = T.model_impact
    with listener() as (port, hits):
        focus = f"{M}supplier> a ?t . SERVICE <http://127.0.0.1:{port}/q> {{ ?a ?b ?c }} }} #"
        err = None
        try:
            fn(cfg(repo), focus=focus)
        except Exception as e:  # noqa: BLE001 — main 上是 pyoxigraph 的连接错误；连接次数先判，其余异常下面原样抛出
            err = e
    expect(not hits, f"focus 里注入的 SERVICE 真的连到了 127.0.0.1:{port}（{len(hits)} 次）；调用结果：{err!r}")
    if not isinstance(err, AisepError):
        raise AssertionError(f"注入的 focus 应被拒为 INVALID_ARGUMENT，实际：{err!r}") from err
    assert err.code == "INVALID_ARGUMENT" and "focus" in rejected(err), err.to_dict()


@pytest.mark.parametrize("focus", ["https://x.example/a b", "https://x.example/a>b", "https://x.example/{a}"])
def test_core1_impact_malformed_focus_is_invalid_argument(repo, focus):
    fn = T.model_impact
    try:
        fn(cfg(repo), focus=focus)
    except SyntaxError as e:  # main：拼出来的 SPARQL 解析失败，经 MCP 是 INTERNAL
        expect(False, f"非法 IRI 进了 SPARQL：{e!r}")
    except AisepError as e:
        assert e.code == "INVALID_ARGUMENT" and "focus" in rejected(e), e.to_dict()
        return
    raise AssertionError("非法 focus 没有被拒")


def test_core1_guard_valid_focus_still_works(repo):
    """护栏：校验 focus 后，slug:local 和完整 IRI 两种合法写法照常可用。"""
    for focus in ("procurement:supplier", f"{M}supplier"):
        r = T.model_impact(cfg(repo), focus=focus)
        assert r["focus"]["iri"] == f"{M}supplier"


# ================================================================== MCP-2：sessionRef 换行

BOSS, BOT = M + "chiefArchitect", M + "codingBot"


def _approve_with_session(template, tmp_path, session):
    """→ (Topo, feat/x 的头, 调用结果或 AisepError)。"""
    t = Topo(template, tmp_path)
    t.checkout("main", new="feat/x")
    head = t.add_element("newThing", "新东西")
    fn = A.governance_record_approval
    try:
        return t, head, fn(T.Config(allow_roots=(str(t.tmp),)), model="procurement", gate="GateArchitecture",
                           decision="Approved", approvedBy=BOSS, approves=[M + "newThing"], branch="feat/x",
                           headCommit=head, repo=str(t.root),
                           activity=dict(agent=BOT, sessionRef=session, startedAt="2026-11-20T09:00:00Z"))
    except AisepError as e:
        return t, head, e


def test_mcp2_session_ref_with_newline_refused(template, tmp_path):
    t, head, r = _approve_with_session(template, tmp_path, "s1\nAISEP-Evidence: " + "0" * 40)
    expect(isinstance(r, AisepError), f"带换行的 sessionRef 被接受，提交了 {r.get('commit') if isinstance(r, dict) else r}")
    assert r.code == "INVALID_ARGUMENT", r.to_dict()
    assert t.rev("refs/heads/feat/x") == head, "被拒时不能留下提交"


def test_mcp2_guard_session_ref_with_cr_refused(template, tmp_path):
    """护栏：含 CR 的 sessionRef 在 main 上已因记录文件解析失败被拒（WRITE_REJECTED）；修 MCP-2 后报 INVALID_ARGUMENT 也行，
    但不能被接受，也不能留下提交。"""
    t, head, r = _approve_with_session(template, tmp_path, "s1\r\nX-Note: y")
    assert isinstance(r, AisepError) and r.code in ("INVALID_ARGUMENT", "WRITE_REJECTED"), r
    assert t.rev("refs/heads/feat/x") == head


# ================================================================== CORE-2：畸形模型让 gate 崩溃

_MI = f"<{M}>"
MALFORMED = {  # 名称: (Turtle 主体, 出错的主语 local name, main 上抛出的异常类型, 其消息里的关键字)
    "inModel字面量": (':zz1 a am4:BusinessActor ; arch:inModel "some model" ; skos:prefLabel "x"@zh .', "zz1", ValueError,
                  "Invalid IRI"),
    "source字面量": (f':zz2 a am4:Serving ; arch:inModel {_MI} ; arch:source "lit" ; arch:target :supplier .', "zz2",
                   TypeError, "NamedNode | BlankNode"),
    "时间溢出": (f':zz4 a aisep:ApprovalRecord ; arch:inModel {_MI} ; aisep:approves :supplier ; '
             f'prov:generatedAtTime "0001-01-01T00:00:00+13:00"^^xsd:dateTime .', "zz4", OverflowError,
             "out of range"),
}
BAD_FILE = "models/procurement/zz.ttl"


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_core2_malformed_model_gives_violation_not_internal(repo, name):
    body, local, crash, words = MALFORMED[name]
    with open(os.path.join(str(repo), BAD_FILE), "w", encoding="utf-8") as f:
        f.write(PREFIXES + body + "\n")
    fn = T.model_gate
    try:
        r = fn(cfg(repo))
    except crash as e:
        if words not in str(e):
            raise
        expect(False, f"gate 抛出 {type(e).__name__}: {e}（经 MCP 是 INTERNAL），没有报违规")
    assert r["result"] == "FAIL"
    hit = [f for f in r["findings"] if f["severity"] == "Violation" and (f["file"] == BAD_FILE or f["focus"] == M + local)]
    assert hit, f"没有指向 {BAD_FILE} 或 :{local} 的违规：{r['findings']}"


# ================================================================== SEC-3：伪仓库目录的 core.fsmonitor

def test_sec3_repo_param_does_not_run_nested_git_config(repo, tmp_path):
    """通过条件：不执行伪仓库 config 里的 fsmonitor，并且只能抛 AisepError（main 上的 FileNotFoundError 也算失败）。"""
    marker = tmp_path / "MARKER"
    evil = repo / "models" / "evil"
    for d in ("objects", "refs"):
        (evil / d).mkdir(parents=True)
    (evil / "HEAD").write_text("ref: refs/heads/main\n")
    (evil / "config").write_text("[core]\n\trepositoryformatversion = 0\n\tbare = false\n\tworktree = .\n"
                                 f"\tfsmonitor = \"echo hit >> '{marker}'; false\"\n")
    # 夹具前提：不加防护的 git 确实把这个目录当成仓库（与本机 safe.bareRepository 设置无关）
    assert git(evil, "-c", "safe.bareRepository=all", "rev-parse", "--absolute-git-dir") == str(os.path.realpath(evil))
    fn = T.model_gate
    err = None
    try:
        fn(cfg(repo), repo=str(evil))
    except Exception as e:  # noqa: BLE001 — main 上把伪仓库当成根，随后缺 vendor/ 抛 FileNotFoundError；先判标记文件
        err = e
    expect(not marker.exists(), f"model_gate(repo=<检出内的伪仓库>) 执行了它 config 里的 core.fsmonitor；调用结果：{err!r}")
    if err is not None and not isinstance(err, AisepError):
        raise err


# ================================================================== MCP-5（读工具）：非法模型名

READ_TOOLS = ("model_check", "model_validate", "model_findings", "model_gate")
BAD_MODELS = ["procurement/", "procurement/../procurement", "../modules/am4", "./procurement",
              "https://aisep.example/model/procurement/../evil/"]


@pytest.mark.parametrize("model", BAD_MODELS)
@pytest.mark.parametrize("tool", READ_TOOLS)
def test_mcp5_read_tools_reject_malformed_model_name(repo, tool, model):
    fn = getattr(T, tool)
    try:
        r = fn(cfg(repo), model=model)
    except AisepError as e:
        expect(e.code != "MODEL_NOT_FOUND", f"{model!r} 报成「没有这个模型」，不是参数错误")
        assert e.code == "INVALID_ARGUMENT" and "model" in rejected(e) and not e.retryable, e.to_dict()
        return
    expect(False, f"{model!r} 被接受并加载了 {sorted({f['file'] for f in r['findings'] if f['file']}) or '某个模型'}")


@pytest.mark.parametrize("model", ["Procurement", "https://aisep.example/model/Procurement/"])
@pytest.mark.parametrize("tool", READ_TOOLS)
def test_mcp5_guard_case_mismatch_is_a_clear_error(repo, tool, model):
    """护栏：大小写不符的模型名在 main 上已是不可重试的 MODEL_NOT_FOUND（读工具按字符串过滤，不受文件系统大小写影响）；
    L4-B 加统一 slug 校验后报 INVALID_ARGUMENT 也行，但不能被当成 procurement 加载。"""
    with pytest.raises(AisepError) as ei:
        getattr(T, tool)(cfg(repo), model=model)
    assert ei.value.code in ("INVALID_ARGUMENT", "MODEL_NOT_FOUND") and not ei.value.retryable, ei.value.to_dict()


def test_mcp5_guard_valid_model_names_still_load(repo):
    for model in ("procurement", M, M.rstrip("/")):
        assert T.model_check(cfg(repo), model=model)["summary"]["violations"] == 0
