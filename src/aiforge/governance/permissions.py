"""最小权限 / 任务感知访问控制（宪法 P4，修 C5 + 强化）。

修 C5：敏感能力（delete/infra/network）默认拒绝，只能凭**人审签名 ticket**授予。
强化（采纳异构评审 per-actor / actor 绑定 / 防重放）：
- 授权按 **actor** 隔离（granted: actor→caps），批准 developer 的 delete 不等于 reviewer 也有；
- ticket 绑定 **actor + capability + nonce + 过期**，HMAC 签名，**单次**使用（防重放）；
- 签发密钥在 ``ApprovalAuthority``（orchestrator 持有，不交给 agent）。

诚实边界：同进程内若 agent 能读到密钥仍可绕过——真正强制需 HITL 独立进程/认证身份。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail

SENSITIVE_CAPS: set[str] = {"delete", "infra", "network"}


class PermissionError_(Exception):
    """权限不足 / 审批无效（自定义，避免与内置 PermissionError 混淆）。"""


@dataclass(frozen=True)
class HumanApprovalTicket:
    actor: str
    capability: str
    nonce: str
    expires_at: float
    signature: str

    def _payload(self) -> bytes:
        return f"{self.actor}|{self.capability}|{self.nonce}|{self.expires_at:.0f}".encode()


class ApprovalAuthority:
    """人审 / HITL 服务：持签发密钥。**orchestrator 持有，不交给 agent。**"""

    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or os.urandom(32)

    def issue(self, actor: str, capability: str, ttl: float = 300.0) -> HumanApprovalTicket:
        nonce = os.urandom(8).hex()
        exp = time.time() + ttl
        sig = hmac.new(self._secret, f"{actor}|{capability}|{nonce}|{exp:.0f}".encode(),
                       hashlib.sha256).hexdigest()
        return HumanApprovalTicket(actor, capability, nonce, exp, sig)

    def broker(self, config: GovernanceConfig = DEFAULT_GOVERNANCE,
               audit: AuditTrail | None = None) -> PermissionBroker:
        return PermissionBroker(config, audit, secret=self._secret)


class PermissionBroker:
    def __init__(self, config: GovernanceConfig = DEFAULT_GOVERNANCE,
                 audit: AuditTrail | None = None, secret: bytes | None = None) -> None:
        self.config = config
        self.audit = audit
        self._secret = secret
        self._granted: dict[str, set[str]] = {}      # actor -> caps（按 actor 隔离）
        self._used_nonces: set[str] = set()

    def _caps(self, actor: str) -> set[str]:
        return self._granted.setdefault(actor, set(self.config.default_capabilities))

    def _audit(self, actor, action, cap, reason):
        if self.audit is not None:
            self.audit.record(actor, action, cap, reason=reason, sensitive=cap in SENSITIVE_CAPS)

    def grant(self, actor: str, capability: str, reason: str) -> bool:
        """按任务申请能力（授予给该 actor）。敏感能力**默认拒绝且不授予**（需 approve()）。"""
        if capability in SENSITIVE_CAPS:
            self._audit(actor, "grant_denied", capability, reason)
            return False
        self._caps(actor).add(capability)
        self._audit(actor, "grant", capability, reason)
        return True

    def approve(self, ticket: object) -> None:
        """凭人审签名 ticket 授予敏感能力**给票面 actor**。验签 + actor 绑定 + 过期 + 防重放。"""
        if self._secret is None:
            raise PermissionError_("此 broker 无审批密钥（须由 ApprovalAuthority 派生），不能批准敏感能力")
        if not isinstance(ticket, HumanApprovalTicket):
            raise PermissionError_("approve 需要 HumanApprovalTicket")
        expected = hmac.new(self._secret, ticket._payload(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, ticket.signature):
            raise PermissionError_("ticket 签名无效（agent 无密钥，伪造会失败）")
        if time.time() > ticket.expires_at:
            raise PermissionError_("ticket 已过期")
        if ticket.nonce in self._used_nonces:
            raise PermissionError_("ticket 已使用（防重放）")
        self._used_nonces.add(ticket.nonce)
        self._caps(ticket.actor).add(ticket.capability)
        self._audit(ticket.actor, "approve_sensitive", ticket.capability, reason=f"ticket {ticket.nonce}")

    def check(self, actor: str, capability: str) -> None:
        if capability not in self._caps(actor):
            self._audit(actor, "deny", capability, reason="not granted")
            raise PermissionError_(
                f"actor={actor} 缺少能力 '{capability}'（最小权限默认拒绝，需先 grant/approve）"
            )

    def has(self, actor: str, capability: str) -> bool:
        return capability in self._caps(actor)
