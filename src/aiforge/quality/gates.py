"""质量门禁（宪法 P1/P2/P3，修 C6 后真正强制）。

链路：spec(P1) → pre-commit → PR(覆盖率+SAST+Agent-as-Judge) → traceability(P2) → CI/CD → canary。
修 C6：
- SpecGate(P1)：无冻结/无验收结构的 spec → 拒绝（原系统无此门，无 spec 照样过）。
- TraceabilityGate(P2)：CODE/TEST 的 refs 必须解析到存在的上游 artifact（原系统从不校验）。
- 全部证据型门 **fails-closed**：缺证据=失败（原 PreCommit lint_ok 默认 True 是 fails-open）。
- 风险表单一来源 = config.high_risk_task_types（judge 已统一用它，见 quality/judge.py）。
"""
from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.llm import StubReviewerLLM
from aiforge.orchestration.state import ArtifactKind, PipelineState, Status
from aiforge.quality.judge import AgentAsJudge


def unified_high_risk(config: GovernanceConfig = DEFAULT_GOVERNANCE) -> FrozenSet[str]:
    """风险表单一来源——judge 与 reviewer 都用它（消除两套不一致的表）。"""
    return config.high_risk_task_types


def risk_requires_human(task_type: str, config: GovernanceConfig = DEFAULT_GOVERNANCE) -> bool:
    return task_type in unified_high_risk(config)


@dataclass
class GateResult:
    name: str
    layer: str
    passed: bool
    reason: str = ""
    bypassable: bool = True


class Gate(abc.ABC):
    name = "gate"
    layer = "generic"
    bypassable = True

    @abc.abstractmethod
    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        ...


def _spec_has_acceptance(text: str) -> bool:
    t = (text or "").lower()
    gherkin = ("given" in t and "when" in t and "then" in t) or ("给定" in t and "当" in t and ("那么" in t or "则" in t))
    ears = "shall" in t and any(w in t for w in ("when", "if", "while", "where"))
    story = ("as a" in t or "作为" in t) and ("i want" in t or "我希望" in t or "想要" in t)
    return (gherkin or ears or story) and len((text or "").strip()) >= 40


class SpecGate(Gate):
    """P1：无 spec / spec 空 / 缺真实验收结构 → 拒绝（不可绕过）。"""
    name = "spec"
    layer = "spec"
    bypassable = False

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        spec = state.latest(ArtifactKind.SPEC)
        if spec is None or not (spec.content or "").strip():
            return GateResult(self.name, self.layer, False, "P1: 无冻结 spec，拒绝实现", bypassable=False)
        if not _spec_has_acceptance(spec.content):
            return GateResult(self.name, self.layer, False, "P1: spec 缺验收结构(需 Gherkin/EARS/User Story)", bypassable=False)
        return GateResult(self.name, self.layer, True, bypassable=False)


class PreCommitGate(Gate):
    """P3 fails-closed：缺 lint 证据 = 不通过（原版默认 True 是 fails-open）。"""
    name = "pre-commit"
    layer = "ide"

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        if "lint_ok" not in evidence:
            return GateResult(self.name, self.layer, False, "P3: 缺 lint 证据，fails-closed")
        return GateResult(self.name, self.layer, bool(evidence["lint_ok"]), "" if evidence["lint_ok"] else "lint 未通过")


class PRGate(Gate):
    """覆盖率 + SAST(均 fails-closed) + Agent-as-Judge(C2)。"""
    name = "pull-request"
    layer = "pr"

    def __init__(self, config: GovernanceConfig = DEFAULT_GOVERNANCE, judge: Optional[AgentAsJudge] = None) -> None:
        self.config = config
        # 离线默认用 StubReviewerLLM(可信评审替身)；生产应注入真实 LLM 的 judge。
        self.judge = judge or AgentAsJudge(llm=StubReviewerLLM())

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        if "coverage" not in evidence:
            return GateResult(self.name, self.layer, False, "P3: 缺 coverage 证据，fails-closed")
        if float(evidence["coverage"]) < self.config.min_coverage:
            return GateResult(self.name, self.layer, False, f"覆盖率 {float(evidence['coverage']):.0%} < {self.config.min_coverage:.0%}")
        if "sast_ok" not in evidence:
            return GateResult(self.name, self.layer, False, "P3: 缺 sast 证据，fails-closed")
        if not evidence["sast_ok"]:
            return GateResult(self.name, self.layer, False, "SAST 安全扫描未通过")
        verdict = self.judge.review(diff_summary=evidence.get("diff_summary", state.request),
                                    risk_keywords=[state.task_type])
        if not verdict.approved:
            return GateResult(self.name, self.layer, False, "Agent-as-Judge 未通过（转人审）")
        return GateResult(self.name, self.layer, True)


class TraceabilityGate(Gate):
    """P2：CODE/TEST 的 refs 必须解析到存在的上游 artifact 种类；有 CODE 必有 SPEC。"""
    name = "traceability"
    layer = "trace"
    bypassable = False
    _UP_CODE = {"spec", "plan", "tasks"}
    _UP_TEST = {"code", "spec"}

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        present = {a.kind.value for a in state.artifacts}
        code = state.latest(ArtifactKind.CODE)
        test = state.latest(ArtifactKind.TEST)
        if code is not None:
            if not code.refs or not any(r in self._UP_CODE and r in present for r in code.refs):
                return GateResult(self.name, self.layer, False, "P2: CODE.refs 未解析到存在的上游(spec/plan/tasks)", bypassable=False)
        if test is not None:
            if not test.refs or not any(r in self._UP_TEST and r in present for r in test.refs):
                return GateResult(self.name, self.layer, False, "P2: TEST.refs 未解析到存在的 CODE/SPEC", bypassable=False)
        if ArtifactKind.CODE in {a.kind for a in state.artifacts} and ArtifactKind.SPEC.value not in present:
            return GateResult(self.name, self.layer, False, "P2: 有代码但无 spec，追溯链断", bypassable=False)
        return GateResult(self.name, self.layer, True, bypassable=False)


class CICDGate(Gate):
    """权威层，fails-closed：缺 tests_ok / build_ok 证据即失败，不可绕过。"""
    name = "ci-cd"
    layer = "cicd"
    bypassable = False

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        for k in ("tests_ok", "build_ok"):
            if k not in evidence:
                return GateResult(self.name, self.layer, False, f"P3: 缺 {k} 证据，fails-closed", bypassable=False)
        ok = bool(evidence["tests_ok"]) and bool(evidence["build_ok"])
        return GateResult(self.name, self.layer, ok, "" if ok else "CI 失败（构建/测试未全过），禁止合并", bypassable=False)


class CanaryGate(Gate):
    name = "canary"
    layer = "production"

    def __init__(self, max_error_rate: float = 0.02) -> None:
        self.max_error_rate = max_error_rate

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        error_rate = float(evidence.get("canary_error_rate", 0.0))
        ok = error_rate <= self.max_error_rate
        return GateResult(self.name, self.layer, ok, "" if ok else f"canary 错误率 {error_rate:.2%} 超阈值，自动回滚")


@dataclass
class QualityGateChain:
    gates: List[Gate] = field(default_factory=list)

    def run(self, state: PipelineState, evidence: Dict[str, object]) -> List[GateResult]:
        results: List[GateResult] = []
        for gate in self.gates:
            res = gate.check(state, evidence)
            results.append(res)
            state.gate_results.append(res.__dict__)
            if not res.passed:
                state.status = Status.BLOCKED
                state.log("quality", "gate_failed", gate=res.name, layer=res.layer, reason=res.reason)
                break
        return results


def build_default_gates(config: GovernanceConfig = DEFAULT_GOVERNANCE, judge: Optional[AgentAsJudge] = None) -> QualityGateChain:
    """硬化门禁链（修 C6）：spec → pre-commit → PR → traceability → CI/CD → canary。"""
    return QualityGateChain(gates=[
        SpecGate(), PreCommitGate(), PRGate(config, judge),
        TraceabilityGate(), CICDGate(), CanaryGate(),
    ])
