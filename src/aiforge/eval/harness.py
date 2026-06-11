"""eval harness：对每个任务跑完整流水线 + 四层门禁，导出四个生产指标。

闭环：dataset → Supervisor 流水线 → QualityGateChain → TaskOutcome → compute_metrics。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.eval.dataset import EvalTask, load_dataset
from aiforge.llm import StubCodeLLM, StubReviewerLLM
from aiforge.orchestration.agents import AgentContext
from aiforge.orchestration.graph import build_default_pipeline
from aiforge.orchestration.state import ArtifactKind, PipelineState, Status
from aiforge.quality.gates import build_default_gates
from aiforge.quality.judge import AgentAsJudge
from aiforge.quality.metrics import Metrics, TaskOutcome, compute_metrics


@dataclass
class EvalReport:
    metrics: Metrics
    outcomes: List[TaskOutcome] = field(default_factory=list)
    per_task: List[dict] = field(default_factory=list)
    # 落地评审修正：在输出层(而非仅注释)标明这是合成自测，防止把指标误读为生产能力。
    kind: str = "synthetic_gate_routing"
    uses_stub_reviewer: bool = True
    not_production_metric: bool = True


def _run_one(task: EvalTask, config: GovernanceConfig) -> TaskOutcome:
    # 用产代码的 StubCodeLLM，使 developer 真产出代码（MockLLM 会安全停机）。
    # 注：门禁仍按 dataset.evidence 判定（C3：tests_ok 等仍是合成证据，未接 verifier 真结果）。
    ctx = AgentContext(config=config, llm=StubCodeLLM())
    supervisor = build_default_pipeline(ctx)
    state = PipelineState(feature_id=task.id, request=task.request, task_type=task.task_type)
    state = supervisor.invoke(state)

    # 落地评审修正：撤销"verifier 自测覆盖 dataset.tests_ok"——自生成测试(与代码同源)会掩盖 dataset
    # 的回归信号(如 F007)，属循环自证。dataset oracle 仍权威；verifier 真实结果已在 state.verification
    # 供 PipelineHealthGate 用(不得 HALTED/verifier 未过)。给 judge 喂**真实生成代码**而非 request 文本。
    evidence = dict(task.evidence)
    code_art = state.latest(ArtifactKind.CODE)
    evidence["diff_summary"] = ctx.file_contents.get(code_art.content, "") if code_art else ""

    # ⚠️ eval 是**合成门禁路由自测**(显式注入 StubReviewerLLM 可信评审替身 + 合成 evidence)，
    # **不是生产能力指标**——真实能力需真实 LLM + 独立 oracle 测试。
    gates = build_default_gates(config, judge=AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True))
    gate_results = gates.run(state, evidence)
    cicd = next((g for g in gate_results if g.layer == "cicd"), None)
    passed_ci = bool(cicd and cicd.passed)
    all_gates_passed = all(g.passed for g in gate_results) and len(gate_results) == len(gates.gates)

    needs_human = state.status == Status.NEEDS_HUMAN or not all_gates_passed
    review_loops = int(task.evidence.get("review_loops", 1 if not needs_human else 2))

    return TaskOutcome.make(
        task_id=task.id,
        passed_ci=passed_ci,
        needed_human_edit=needs_human,
        introduced_regression=bool(task.evidence.get("introduced_regression", False)),
        review_loops=review_loops,
        files_changed=state.files_changed,
    )


def run_eval(
    dataset_path: Optional[str] = None,
    tasks: Optional[List[EvalTask]] = None,
    config: GovernanceConfig = DEFAULT_GOVERNANCE,
) -> EvalReport:
    if tasks is None:
        if dataset_path is None:
            raise ValueError("需要 dataset_path 或 tasks")
        tasks = load_dataset(dataset_path)
    outcomes = [_run_one(t, config) for t in tasks]
    metrics = compute_metrics(outcomes)
    per_task = [o.__dict__ for o in outcomes]
    return EvalReport(metrics=metrics, outcomes=outcomes, per_task=per_task)
