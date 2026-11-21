"""L4-B 补充回归：先行测试（test_l4b_entry_validation.py）之外、实现时发现或顺带守护的几条。

- SERVICE 判定对 SPARQL 的 \\uXXXX 转义（pyoxigraph 在解析前解码，`\\u0053ERVICE` 就是 SERVICE）
- gitio.read_file / open_dir 拒绝 `.`、`..`、空段
- 批准路径与读工具共用模型 slug 校验
- core.short() 对 `/` 结尾的模型 IRI 保持完整
"""
import os

import pytest

from aisep import approval as A
from aisep import core, gitio
from aisep import tools as T
from aisep.errors import AisepError
from conftest import git
from fixtures.topology import M, Topo
from test_l4b_entry_validation import cfg, listener


U = "\\u"  # built by concatenation: a SPARQL codepoint escape, kept out of Python's own string escapes


@pytest.mark.parametrize("sparql", [
    "SELECT * WHERE { " + U + "0053ERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "SELECT * WHERE { " + U + "0073ervice <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    r"SELECT * WHERE { \U00000053ERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "SELECT * WHERE { ?s ?p " + U + "0027x' . SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } }",
    "SELECT * WHERE { BIND(1 AS ?n) FILTER(1<2)SERVICE<http://127.0.0.1:{port}/q>{ ?a ?b ?c } }",
])
def test_escaped_or_glued_service_is_refused(repo, sparql):
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), sparql.replace("{port}", str(port)))
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()
    assert not hits


# 评审 #56 第一轮（blocker）：粘在关键字后的前缀名、伪 IRI 里的 SERVICE。pyoxigraph 都把它们读成 SERVICE 并真的外连。
GLUED = {
    "SERVICE:q": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "OPTIONAL service:q": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { OPTIONAL{ service:q { ?a ?b ?c } } }",
    "伪IRI": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { FILTER(1<2)SERVICE:q#>\n{ ?a ?b ?c } }",
    "SERVICEex:q": "PREFIX ex: <http://127.0.0.1:{port}/> SELECT * WHERE { SERVICEex:q { ?a ?b ?c } }",
    "伪IRI里的引号": "SELECT * WHERE { FILTER(1<2&&'>'=?x)SERVICE<http://127.0.0.1:{port}/q>{ ?a ?b ?c } #'\n}",
    "真IRI里的引号": "SELECT * WHERE { OPTIONAL { ?s ?p <http://x.example/a'b> } SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } #'\n}",
}


@pytest.mark.parametrize("name", sorted(GLUED))
def test_glued_service_really_connects_without_the_filter(name):
    """前提：这些写法在不加过滤时 pyoxigraph 确实发起连接（否则下面的拒绝测试证明不了什么）。"""
    import pyoxigraph as ox
    with listener() as (port, hits):
        try:
            list(ox.Store().query(GLUED[name].replace("{port}", str(port))))
        except Exception:  # noqa: BLE001 — 没有 HTTP 响应，pyoxigraph 报错；只看有没有连接
            pass
    assert hits, f"{name}：pyoxigraph 没有把它读成 SERVICE"


@pytest.mark.parametrize("name", sorted(GLUED))
def test_glued_service_is_refused(repo, name):
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), GLUED[name].replace("{port}", str(port)))
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()
    assert not hits


@pytest.mark.parametrize("sparql", [
    "SELECT * WHERE { ?s ?p 'x'@en . _:service ?q ?r }",
    "SELECT ?x WHERE { ?x a ?t FILTER(?t = am4:Service || ?t = <https://x.example/aService>) } ORDER BY ?x",
    'SELECT * WHERE { ?s ?p """a "service" b""" }',
])
def test_more_service_mentions_are_not_refused(repo, sparql):
    assert T.model_query(cfg(repo), sparql)["kind"] == "select"


@pytest.mark.parametrize("rel", ["models/../models/procurement/am4.ttl", "./models/procurement/am4.ttl",
                                 "models//procurement/am4.ttl", "models/procurement/.", ".."])
def test_read_file_refuses_unnormalised_paths(repo, rel):
    with pytest.raises(gitio.UnsafeFile):
        gitio.read_file(str(repo), rel)


@pytest.mark.parametrize("rel", ["models/..", "../x", "models/./procurement"])
def test_open_dir_refuses_dot_segments(repo, rel):
    with pytest.raises(gitio.UnsafeFile):
        gitio.open_dir(str(repo), rel)


def test_read_file_and_open_dir_still_work(repo):
    assert gitio.read_file(str(repo), "models/procurement/am4.ttl")
    os.close(gitio.open_dir(str(repo), "models/procurement/"))


@pytest.mark.parametrize("model", ["procurement/", "../procurement", "https://aisep.example/model/procurement/../x/"])
def test_approval_rejects_malformed_model_before_git(template, tmp_path, model):
    t = Topo(template, tmp_path)
    t.checkout("main", new="feat/x")
    head = t.add_element("newThing", "新东西")
    with pytest.raises(AisepError) as ei:
        A.governance_record_approval(T.Config(allow_roots=(str(t.tmp),)), model=model, gate="GateArchitecture",
                                     decision="Approved", approvedBy=M + "chiefArchitect", approves=[M + "newThing"],
                                     branch="feat/x", headCommit=head, repo=str(t.root))
    assert ei.value.code == "INVALID_ARGUMENT" and ei.value.details["rejectedFields"] == ["model"]
    assert t.rev("refs/heads/feat/x") == head


def test_short_keeps_slash_terminated_model_iri():
    assert core.short(M) == M
    assert core.short(M + "supplier") == "procurement:supplier"


# 评审 #56 第一轮（major）：检出里的伪 .git 子目录（普通的嵌套仓库）也不能执行它 config 里的命令
def test_sec3_nested_dotgit_dir_does_not_run_its_config(repo, tmp_path):
    marker = tmp_path / "MARKER"
    evil = repo / "models" / "evil"
    evil.mkdir(parents=True)
    git(evil, "init", "-q")
    git(evil, "config", "core.fsmonitor", f"echo hit >> '{marker}'; false")
    (evil / "x.ttl").write_text("")
    err = None
    for fn in (T.model_check, T.model_gate):
        try:
            fn(cfg(repo), repo=str(evil))
        except Exception as e:  # noqa: BLE001 — 先判标记文件，再判异常类型
            err = e
        assert not marker.exists(), f"{fn.__name__}(repo=<伪 .git 子目录>) 执行了 core.fsmonitor；结果：{err!r}"
        assert err is None or isinstance(err, AisepError), repr(err)
