"""三文件 review 协议（宪法 P7，治理认知债）。

agent 产出速度远超人类逐行 review，故每次 session 后强制精读 diff 最大的 N 个文件，
其余按风险抽审。本模块产出 review 清单（人读），并标记需全量人审的高风险文件。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.orchestration.state import (
    FileChange,  # 运行期可解析(get_type_hints 不炸)；循环已由 orchestration/__init__ 延迟 graph 破除
)

# 路径命中这些关键字视为高风险，无条件进入人审（无论 diff 大小）
RISKY_PATH_HINTS = ("migration", "auth", "security", "payment", "infra", "secret", "delete")


@dataclass
class ReviewItem:
    path: str
    lines_changed: int
    must_fully_review: bool
    reason: str


@dataclass
class ThreeFileReview:
    items: list[ReviewItem] = field(default_factory=list)

    @property
    def must_review_paths(self) -> list[str]:
        return [i.path for i in self.items if i.must_fully_review]


def review_after_session(
    changes: list[FileChange],
    config: GovernanceConfig = DEFAULT_GOVERNANCE,
) -> ThreeFileReview:
    review = ThreeFileReview()
    # 按改动行数降序：diff 最大的 N 个文件强制精读
    ranked = sorted(changes, key=lambda c: c.total_lines, reverse=True)
    for idx, change in enumerate(ranked):
        risky = any(h in change.path.lower() for h in RISKY_PATH_HINTS)
        top_n = idx < config.review_top_n_files
        must = risky or top_n
        if risky:
            reason = "高风险路径，强制全量人审"
        elif top_n:
            reason = f"diff 第 {idx + 1} 大文件，强制精读"
        else:
            reason = "按风险抽审"
        review.items.append(
            ReviewItem(
                path=change.path,
                lines_changed=change.total_lines,
                must_fully_review=must,
                reason=reason,
            )
        )
    return review
