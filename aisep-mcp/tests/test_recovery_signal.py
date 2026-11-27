"""ADR-024 恢复条件②的机械信号（#126 后续 F3）：同一模型里声明了两个及以上能当批准人的干系人（按
`Ctx._approver` 判定：arch:Stakeholder 及其子类，且不是 aisep:AIAgent）时，L4 给一条 Info，指向追踪 issue #141。
只是提示，不影响 gate 结论。"""
import glob, os

from conftest import ROOT
from aisep import core

HDR = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix : <https://aisep.example/model/t/> .
@prefix u: <https://aisep.example/model/u/> .
:  a arch:Model ; skos:prefLabel "测试模型"@zh .
u: a arch:Model ; skos:prefLabel "另一个模型"@zh .
"""


def signals(tmp_path, body):
    p = tmp_path / "t.ttl"
    p.write_text(HDR + body, encoding="utf-8")
    ctx = core.Ctx(core.discover(), [str(p)])
    core.l4(ctx)
    return [(s, t) for s, layer, t in ctx.problems if layer == "L4" and "#141" in t]


def stakeholder(name, model=":", extra=""):
    return f':{name} a arch:Stakeholder {extra}; arch:inModel {model} ; skos:prefLabel "{name}"@zh .\n'


def test_two_approvers_in_one_model_give_one_info(tmp_path):
    got = signals(tmp_path, stakeholder("a") + stakeholder("b"))
    assert len(got) == 1, got
    sev, text = got[0]
    assert sev == "Info" and "ADR-024" in text and ":a" in text and ":b" in text, text


def test_one_approver_gives_none(tmp_path):
    assert signals(tmp_path, stakeholder("a")) == []


def test_ai_agent_is_not_counted(tmp_path):
    assert signals(tmp_path, stakeholder("a") + stakeholder("bot", extra=", aisep:AIAgent ")) == []


def test_approvers_in_different_models_are_not_counted_together(tmp_path):
    assert signals(tmp_path, stakeholder("a") + stakeholder("b", model="u:")) == []


def test_repository_models_give_none_today():
    files = sorted(glob.glob(os.path.join(ROOT, "models", "**", "*.ttl"), recursive=True))
    ctx = core.Ctx(core.discover(), files)
    core.l4(ctx)
    assert [t for s, layer, t in ctx.problems if "#141" in t] == []
