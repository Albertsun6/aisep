"""Runtime 抽象基类（宪法 P4/P5/P9）。

所有"写动作 / 跑命令"都必须经 Runtime：它在落盘前做权限检查与 blast-radius 校验，
失败累计达阈值触发安全停机（SafeHaltError）。真实 OpenHands / Devin / Ona 通过子类接入。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.orchestration.state import FileChange   # 运行期可解析(get_type_hints 不炸)；循环已由 orchestration/__init__ 延迟 graph 破除


class SafeHaltError(Exception):
    """无法安全完成 state-mutating 任务时主动停机（宪法 P4），而非改环境/吞错误硬闯。"""


@dataclass
class ExecResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    changes: List[FileChange] = field(default_factory=list)


class Runtime(abc.ABC):
    name = "abstract"

    def __init__(
        self,
        permissions: PermissionBroker,
        config: GovernanceConfig = DEFAULT_GOVERNANCE,
        audit: Optional[AuditTrail] = None,
    ) -> None:
        self.permissions = permissions
        self.config = config
        self.audit = audit
        self._failures = 0

    def _enforce_blast_radius(self, changes: List[FileChange]) -> None:
        files = len({c.path for c in changes})
        lines = sum(c.total_lines for c in changes)
        if files > self.config.max_files_per_change or lines > self.config.max_lines_per_change:
            if self.audit is not None:
                self.audit.record(self.name, "halt", "blast_radius", files=files, lines=lines)
            raise SafeHaltError(
                f"超出 blast radius 上限 (files={files}/{self.config.max_files_per_change}, "
                f"lines={lines}/{self.config.max_lines_per_change})，降级人审"
            )

    def _note_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.config.safe_halt_after_failures:
            if self.audit is not None:
                self.audit.record(self.name, "halt", "runtime", failures=self._failures)
            raise SafeHaltError(
                f"连续失败 {self._failures} 次达到安全停机阈值，停机上报"
            )

    def apply(self, actor: str, changes: List[FileChange], contents: dict) -> ExecResult:
        """应用文件变更。``contents`` 为 path->文本。"""
        self.permissions.check(actor, "write")
        self._enforce_blast_radius(changes)
        if self.audit is not None:
            self.audit.record(actor, "tool_call", "apply", files=[c.path for c in changes])
        return self._apply_impl(changes, contents)

    @abc.abstractmethod
    def _apply_impl(self, changes: List[FileChange], contents: dict) -> ExecResult:
        ...

    @abc.abstractmethod
    def run(self, actor: str, command: str) -> ExecResult:
        ...
