"""最小权限 / 任务感知访问控制（宪法 P4）。

agent 默认只有 GovernanceConfig.default_capabilities（通常仅 ``read``）。
其余能力（write / exec / network / delete）必须按任务显式申请并记审计。
高风险能力（delete / infra）即使申请也需人审标记。
"""

from __future__ import annotations

from typing import Optional, Set

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail


class PermissionError_(Exception):
    """权限不足（自定义，避免与内置 PermissionError 混淆）。"""


SENSITIVE_CAPS: Set[str] = {"delete", "infra", "network"}


class PermissionBroker:
    def __init__(
        self,
        config: GovernanceConfig = DEFAULT_GOVERNANCE,
        audit: Optional[AuditTrail] = None,
    ) -> None:
        self.config = config
        self.audit = audit
        self.granted: Set[str] = set(config.default_capabilities)

    def grant(self, actor: str, capability: str, reason: str) -> bool:
        """按任务申请能力。敏感能力返回需人审标记（这里仍授予但记审计，由编排决定是否 HITL）。"""
        self.granted.add(capability)
        if self.audit is not None:
            self.audit.record(
                actor, "grant", capability, reason=reason, sensitive=capability in SENSITIVE_CAPS
            )
        return capability not in SENSITIVE_CAPS

    def check(self, actor: str, capability: str) -> None:
        if capability not in self.granted:
            if self.audit is not None:
                self.audit.record(actor, "deny", capability, reason="not granted")
            raise PermissionError_(
                f"actor={actor} 缺少能力 '{capability}'（最小权限默认拒绝，需先 grant）"
            )

    def has(self, capability: str) -> bool:
        return capability in self.granted
