"""issue #66：被检查提交自带的 aisep-core SHACL-SPARQL 约束（Ctx.shape_hits）在无网络子进程里执行。

改之前，这两种写法都绕过 pyshacl 与 _SERVICE_CLAUSE_RE 的文本识别，在服务进程里由 pyoxigraph 真的外连，其中
`SERVICE#x⏎<url>` 时 gate 照样 PASS。判据是本机回环监听上的连接计数，不只看返回了错误。
"""
import re

import pyoxigraph as ox
import pytest

from aisep import querybox
from aisep import tools as T
from aisep.errors import AisepError
from conftest import commit_all
from test_l4b_entry_validation import cfg, listener

SHAPES = "modules/aisep-core/shapes.ttl"
SELECT = {
    "注释隔开": "SELECT $this WHERE { SERVICE#x\n<http://127.0.0.1:{port}/q> { $this ?b ?c } }",
    "前缀名紧贴": "PREFIX ex: <http://127.0.0.1:{port}/>\nSELECT $this WHERE { SERVICEex:q { $this ?b ?c } }",
}


def _plant(repo, name, port):
    sel = SELECT[name].replace("{port}", str(port))
    with open(repo / SHAPES, "a", encoding="utf-8") as f:
        f.write('\naisepsh:ProbeServiceShape a sh:NodeShape ;\n    sh:targetSubjectsOf arch:inModel ;\n'
                '    sh:sparql [ sh:message "probe" ; sh:prefixes aisepsh:prefixes ;\n'
                f'        sh:select """{sel}""" ] .\n')
    return commit_all(repo, "plant SERVICE in aisep-core")


@pytest.mark.parametrize("name", sorted(SELECT))
def test_constraint_really_connects_in_process(name):
    """前提：同一条约束交给进程内的 pyoxigraph（改之前 shape_hits 的做法）时确实外连。"""
    with listener() as (port, hits):
        try:
            list(ox.Store().query(re.sub(r"\$this\b", "?this", SELECT[name].replace("{port}", str(port)))))
        except Exception:  # noqa: BLE001 — 只看有没有连接
            pass
    assert hits, f"{name}：pyoxigraph 没有外连"


@pytest.mark.parametrize("name", sorted(SELECT))
def test_gate_on_ref_with_service_constraint_fails_without_connecting(repo, name):
    with listener() as (port, hits):
        head = _plant(repo, name, port)
        with pytest.raises(AisepError) as ei:
            T.model_gate(cfg(repo), ref=head)
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()
    assert not hits


def test_no_networkless_child_fails_closed(repo, monkeypatch):
    """建立不了无网络子进程时不退回进程内执行：gate 报错，不 PASS。"""
    monkeypatch.setattr(querybox.sys, "platform", "plan9")
    with pytest.raises(AisepError) as ei:
        T.model_gate(cfg(repo))
    assert ei.value.code == "INTERNAL", ei.value.to_dict()
