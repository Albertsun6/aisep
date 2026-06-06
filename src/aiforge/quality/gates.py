"""四层质量门禁（宪法 P3，不可绕过）。

IDE/pre-commit → PR（覆盖率 + SAST + Agent-as-Judge）→ CI/CD（权威层）→ 生产 canary + 自动回滚。
任一层失败即阻断；CI/CD 层失败任何人不得合并。门禁基于 PipelineState + evidence(证据字典)判定。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.orchestration.state import PipelineState, Status
from aiforge.quality.judge import AgentAsJudge


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


class PreCommitGate(Gate):
    name = "pre-commit"
    layer = "ide"

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        lint_ok = bool(evidence.get("lint_ok", True))
        return GateResult(self.name, self.layer, lint_ok, "" if lint_ok else "lint/静态检查失败")


class PRGate(Gate):
    name = "pull-request"
    layer = "pr"

    def __init__(self, config: GovernanceConfig = DEFAULT_GOVERNANCE, judge: Optional[AgentAsJudge] = None) -> None:
        self.config = config
        self.judge = judge or AgentAsJudge()

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        coverage = float(evidence.get("coverage", 0.0))
        sast_ok = bool(evidence.get("sast_ok", True))
        if coverage < self.config.min_coverage:
            return GateResult(self.name, self.layer, False, f"覆盖率 {coverage:.0%} < {self.config.min_coverage:.0%}")
        if not sast_ok:
            return GateResult(self.name, self.layer, False, "SAST 安全扫描未通过")
        verdict = self.judge.review(
            diff_summary=evidence.get("diff_summary", state.request),
            risk_keywords=[state.task_type],
        )
        if not verdict.approved:
            return GateResult(self.name, self.layer, False, "Agent-as-Judge 未通过（转人审）")
        return GateResult(self.name, self.layer, True)


class CICDGate(Gate):
    name = "ci-cd"
    layer = "cicd"
    bypassable = False  # 权威层，不可绕过

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        tests_ok = bool(evidence.get("tests_ok", False))
        build_ok = bool(evidence.get("build_ok", True))
        ok = tests_ok and build_ok
        reason = "" if ok else "CI 失败（构建/测试未全过），禁止合并"
        return GateResult(self.name, self.layer, ok, reason, bypassable=False)


class CanaryGate(Gate):
    name = "canary"
    layer = "production"

    def __init__(self, max_error_rate: float = 0.02) -> None:
        self.max_error_rate = max_error_rate

    def check(self, state: PipelineState, evidence: Dict[str, object]) -> GateResult:
        error_rate = float(evidence.get("canary_error_rate", 0.0))
        ok = error_rate <= self.max_error_rate
        reason = "" if ok else f"canary 错误率 {error_rate:.2%} 超阈值，自动回滚"
        return GateResult(self.name, self.layer, ok, reason)


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
    return QualityGateChain(
        gates=[PreCommitGate(), PRGate(config, judge), CICDGate(), CanaryGate()]
    )
