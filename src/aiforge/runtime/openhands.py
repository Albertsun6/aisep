"""OpenHands 自托管 runtime 适配（Phase 3）。

把企业私有化执行层接到 OpenHands（开源、可自托管 Docker/K8s、Large Codebase SDK、多 agent 并行）。
本适配实现 Runtime 接口：未配置 endpoint 时安全降级（不静默改环境），配置后委托给真实 API。

真实接入步骤见 deploy/openhands/README.md。这里保留接口与 Large Codebase 并行调度的占位语义。
"""

from __future__ import annotations

import os
from typing import List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.orchestration.state import FileChange
from aiforge.runtime.base import ExecResult, Runtime, SafeHaltError


class OpenHandsRuntime(Runtime):
    """OpenHands 适配。endpoint 为空时所有写动作安全停机，避免"未配置却静默执行"。"""

    name = "openhands"

    def __init__(
        self,
        permissions: PermissionBroker,
        config: GovernanceConfig = DEFAULT_GOVERNANCE,
        audit: Optional[AuditTrail] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        max_parallel_agents: int = 4,
    ) -> None:
        super().__init__(permissions, config, audit)
        self.endpoint = endpoint or os.environ.get("OPENHANDS_ENDPOINT")
        self.api_key = api_key or os.environ.get("OPENHANDS_API_KEY")
        self.max_parallel_agents = max_parallel_agents

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    def _require_configured(self) -> None:
        if not self.configured:
            raise SafeHaltError(
                "OpenHands runtime 未配置 endpoint，按宪法 P4 安全停机，"
                "不静默执行 state-mutating 操作（见 deploy/openhands/README.md）"
            )

    def _apply_impl(self, changes: List[FileChange], contents: dict) -> ExecResult:
        self._require_configured()
        # 真实实现：调用 OpenHands API 在隔离 sandbox 内应用 patch。
        raise NotImplementedError("接通 OpenHands API 后在此实现 patch 应用")

    def run(self, actor: str, command: str) -> ExecResult:
        self.permissions.check(actor, "exec")
        self._require_configured()
        raise NotImplementedError("接通 OpenHands API 后在此实现命令执行")

    def plan_parallel_batches(self, tasks: List[str], dependencies: dict) -> List[List[str]]:
        """Large Codebase SDK 语义占位：按依赖把任务分批，批内可并行、批间按序。

        这是一个零依赖的拓扑分层实现，便于本地推演并行调度，不依赖真实 OpenHands。
        ``dependencies``: task -> 其依赖的 task 列表。
        """
        remaining = set(tasks)
        done: set = set()
        batches: List[List[str]] = []
        guard = 0
        while remaining and guard <= len(tasks):
            ready = sorted(
                t for t in remaining if all(d in done for d in dependencies.get(t, []))
            )
            if not ready:  # 存在环
                raise ValueError(f"任务依赖存在环，无法分批: {sorted(remaining)}")
            batch = ready[: self.max_parallel_agents]
            batches.append(batch)
            for t in batch:
                remaining.discard(t)
                done.add(t)
            guard += 1
        return batches
