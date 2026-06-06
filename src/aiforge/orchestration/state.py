"""编排共享状态（对应 LangGraph 的 StateGraph state；这里用 dataclass 零依赖实现）。

角色 agent **只**通过 PipelineState 通信，禁止彼此直接耦合（见根 AGENTS.md）。
状态可被 checkpoint（见 graph.py），支持 HITL 中断后恢复。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ArtifactKind(str, Enum):
    SPEC = "spec"
    PLAN = "plan"
    TASKS = "tasks"
    CODE = "code"
    TEST = "test"
    REVIEW = "review"


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_HUMAN = "needs_human"   # HITL 中断
    HALTED = "halted"             # 安全停机
    BLOCKED = "blocked"           # 门禁拒绝
    DONE = "done"


@dataclass
class Artifact:
    kind: ArtifactKind
    content: str
    produced_by: str
    refs: List[str] = field(default_factory=list)  # 可追溯：指向上游 artifact / 需求条目
    created_at: float = field(default_factory=time.time)


@dataclass
class Task:
    id: str
    title: str
    task_type: str = "feature"          # feature / migration / security / ...
    acceptance: List[str] = field(default_factory=list)
    refs: List[str] = field(default_factory=list)  # 满足哪条需求（P2 可追溯）
    done: bool = False


@dataclass
class FileChange:
    path: str
    added_lines: int = 0
    removed_lines: int = 0

    @property
    def total_lines(self) -> int:
        return self.added_lines + self.removed_lines


@dataclass
class PipelineState:
    feature_id: str
    request: str
    task_type: str = "feature"
    status: Status = Status.PENDING
    current_node: Optional[str] = None

    artifacts: List[Artifact] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    file_changes: List[FileChange] = field(default_factory=list)

    gate_results: List[dict] = field(default_factory=list)
    messages: List[dict] = field(default_factory=list)
    consecutive_failures: int = 0
    needs_human_reason: Optional[str] = None

    # ---- helpers ----
    def add_artifact(self, artifact: Artifact) -> Artifact:
        self.artifacts.append(artifact)
        return artifact

    def latest(self, kind: ArtifactKind) -> Optional[Artifact]:
        for a in reversed(self.artifacts):
            if a.kind == kind:
                return a
        return None

    def log(self, node: str, event: str, **data: object) -> None:
        self.messages.append({"node": node, "event": event, "ts": time.time(), **data})

    @property
    def files_changed(self) -> int:
        return len({c.path for c in self.file_changes})

    @property
    def lines_changed(self) -> int:
        return sum(c.total_lines for c in self.file_changes)
