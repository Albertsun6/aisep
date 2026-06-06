"""eval harness：对每个任务跑完整流水线 + 四层门禁，导出四个生产指标。

闭环：dataset → Supervisor 流水线 → QualityGateChain → TaskOutcome → compute_metrics。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.eval.dataset import EvalTask, load_dataset
from aiforge.orchestration.agents import AgentContext
from aiforge.orchestration.graph import build_default_pipeline
from aiforge.orchestration.state import PipelineState, Status
from aiforge.quality.gates import build_default_gates
from aiforge.quality.metrics import Metrics, TaskOutcome, compute_metrics


@dataclass
class EvalReport:
    metrics: Metrics
    outcomes: List[TaskOutcome] = field(default_factory=list)
    per_task: List[dict] = field(default_factory=list)


def _run_one(task: EvalTask, config: GovernanceConfig) -> TaskOutcome:
    ctx = AgentContext(config=config)
    supervisor = build_default_pipeline(ctx)
    state = PipelineState(feature_id=task.id, request=task.request, task_type=task.task_type)
    state = supervisor.invoke(state)

    gates = build_default_gates(config)
    gate_results = gates.run(state, dict(task.evidence))
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
