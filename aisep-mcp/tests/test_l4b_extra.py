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


@pytest.mark.parametrize("sparql", [
    "PREFIX service: <https://x.example/> SELECT * WHERE { ?s service:p ?o }",
    "SELECT * WHERE { ?s ?p 'x'@en . _:service ?q ?r }",
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
