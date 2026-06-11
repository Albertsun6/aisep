"""四个生产指标（比 SWE-bench 等基准更贴近真实工程，来自调研 Adaline 等多源）。

1. task_completion_rate  —— diff 过 CI 且**无需人工修改**才算完成
2. regression_introduction_rate —— 引入回归（弄坏既有测试）的任务占比
3. avg_review_loop_count —— 平均人工修正轮次（>1 说明 prompt/上下文质量差）
4. avg_blast_radius_on_failure —— 失败时的平均改动文件数
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskOutcome:
    task_id: str
    passed_ci: bool                 # 构建 + 单测 + 集成测试是否全过
    needed_human_edit: bool         # 合并前是否需要人工修改
    introduced_regression: bool     # 是否弄坏既有测试
    review_loops: int               # 达到 merge-ready 的人工修正轮次
    files_changed: int              # 本任务改动文件数
    succeeded: bool                 # 最终是否成功（过 CI 且无需人改）

    @classmethod
    def make(cls, task_id: str, **kw: object) -> TaskOutcome:
        passed_ci = bool(kw.get("passed_ci", False))
        needed_human_edit = bool(kw.get("needed_human_edit", False))
        succeeded = passed_ci and not needed_human_edit
        return cls(
            task_id=task_id,
            passed_ci=passed_ci,
            needed_human_edit=needed_human_edit,
            introduced_regression=bool(kw.get("introduced_regression", False)),
            review_loops=int(kw.get("review_loops", 1)),
            files_changed=int(kw.get("files_changed", 0)),
            succeeded=succeeded,
        )


@dataclass
class Metrics:
    n: int = 0
    task_completion_rate: float = 0.0
    regression_introduction_rate: float = 0.0
    avg_review_loop_count: float = 0.0
    avg_blast_radius_on_failure: float = 0.0
    details: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "task_completion_rate": round(self.task_completion_rate, 4),
            "regression_introduction_rate": round(self.regression_introduction_rate, 4),
            "avg_review_loop_count": round(self.avg_review_loop_count, 4),
            "avg_blast_radius_on_failure": round(self.avg_blast_radius_on_failure, 4),
        }


def compute_metrics(outcomes: list[TaskOutcome]) -> Metrics:
    n = len(outcomes)
    if n == 0:
        return Metrics()
    completed = sum(1 for o in outcomes if o.succeeded)
    regressions = sum(1 for o in outcomes if o.introduced_regression)
    review_total = sum(o.review_loops for o in outcomes)
    failures = [o for o in outcomes if not o.succeeded]
    blast = (sum(o.files_changed for o in failures) / len(failures)) if failures else 0.0
    return Metrics(
        n=n,
        task_completion_rate=completed / n,
        regression_introduction_rate=regressions / n,
        avg_review_loop_count=review_total / n,
        avg_blast_radius_on_failure=blast,
        details=[o.__dict__ for o in outcomes],
    )
