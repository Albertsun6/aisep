"""治理配置（对应宪法 P4/P5/P7）。

集中放"把失败模式吸收进架构"的硬阈值：最小权限默认、blast radius 上限、
高风险任务类型（强制 HITL）、认知债 three-file review 触发条件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


# 调研中 state-mutating 任务（bug fix / 配置 / 迁移）占 65%+ 的高危事件，默认强制人审。
HIGH_RISK_TASK_TYPES: FrozenSet[str] = frozenset(
    {"migration", "security", "delete", "infra", "config", "payment", "auth"}
)


@dataclass(frozen=True)
class GovernanceConfig:
    # P5 blast radius：单次自主变更的文件数 / 改动行数硬上限，超限降级人审
    max_files_per_change: int = 10
    max_lines_per_change: int = 400

    # P3 质量门禁：PR 层覆盖率阈值（AI 触碰代码常用 80%）
    min_coverage: float = 0.80

    # P4 最小权限：默认授予的能力（其余按任务申请）
    default_capabilities: FrozenSet[str] = frozenset({"read"})

    # P7 认知债：每次 session 后精读 diff 最大的 N 个文件
    review_top_n_files: int = 3

    # P4 安全停机：连续失败次数达到阈值即 safe-halt（避免改环境/吞错误硬闯）
    safe_halt_after_failures: int = 2

    high_risk_task_types: FrozenSet[str] = field(default_factory=lambda: HIGH_RISK_TASK_TYPES)

    def requires_human_review(self, task_type: str, files_changed: int, lines_changed: int) -> bool:
        """是否必须人审（HITL）。高风险类型或超 blast radius 上限即触发。"""
        if task_type in self.high_risk_task_types:
            return True
        if files_changed > self.max_files_per_change:
            return True
        if lines_changed > self.max_lines_per_change:
            return True
        return False


DEFAULT_GOVERNANCE = GovernanceConfig()
