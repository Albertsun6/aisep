"""最小权限 / 任务感知访问控制（宪法 P4，修 C5）。

agent 默认只有 ``GovernanceConfig.default_capabilities``（通常仅 ``read``）。
修 C5：敏感能力（delete / infra / network）**grant() 默认拒绝且不授予**（原版 bug：返回 False 却仍授予）；
只能由**人审签发的签名 ticket** 经 ``approve()`` 授予——agent 代码路径没有签发密钥，伪造票验签失败。

落地说明：本版保留 grant/check/has 原签名以**最小波及**既有调用方；fix_proposal/improved_permissions.py
还有更强的 per-actor 授权 + 单次 nonce + actor 绑定（更大改动），可作后续增强。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Optional, Set

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail

SENSITIVE_CAPS: Set[str] = {"delete", "infra", "network"}


class PermissionError_(Exception):
    """权限不足 / 审批无效（自定义，避免与内置 PermissionError 混淆）。"""


@dataclass(frozen=True)
class HumanApprovalTicket:
    capability: str
    nonce: str
    expires_at: float
    signature: str

    def _payload(self) -> bytes:
        return f"{self.capability}|{self.nonce}|{self.expires_at:.0f}".encode()


class ApprovalAuthority:
    """人审 / HITL 服务：持签发密钥。**orchestrator 持有，不交给 agent。**"""

    def __init__(self, secret: Optional[bytes] = None) -> None:
        self._secret = secret or os.urandom(32)

    def issue(self, capability: str, ttl: float = 300.0) -> HumanApprovalTicket:
        nonce = os.urandom(8).hex()
        exp = time.time() + ttl
        sig = hmac.new(self._secret, f"{capability}|{nonce}|{exp:.0f}".encode(), hashlib.sha256).hexdigest()
        return HumanApprovalTicket(capability, nonce, exp, sig)

    def broker(self, config: GovernanceConfig = DEFAULT_GOVERNANCE,
               audit: Optional[AuditTrail] = None) -> "PermissionBroker":
        return PermissionBroker(config, audit, secret=self._secret)


class PermissionBroker:
    def __init__(self, config: GovernanceConfig = DEFAULT_GOVERNANCE,
                 audit: Optional[AuditTrail] = None, secret: Optional[bytes] = None) -> None:
        self.config = config
        self.audit = audit
        self._secret = secret
        self.granted: Set[str] = set(config.default_capabilities)
        self._used_nonces: Set[str] = set()

    def grant(self, actor: str, capability: str, reason: str) -> bool:
        """按任务申请能力。非敏感即授予；敏感**默认拒绝且不授予**（需经 approve() 人审）。"""
        if capability in SENSITIVE_CAPS:
            if self.audit is not None:
                self.audit.record(actor, "grant_denied", capability, reason=reason, sensitive=True)
            return False
        self.granted.add(capability)
        if self.audit is not None:
            self.audit.record(actor, "grant", capability, reason=reason, sensitive=False)
        return True

    def approve(self, ticket: object) -> None:
        """凭**人审签名 ticket** 授予敏感能力。验签 + 防重放 + 过期；无密钥/伪造票拒绝。"""
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
        self.granted.add(ticket.capability)
        if self.audit is not None:
            self.audit.record("human", "approve_sensitive", ticket.capability, reason=f"ticket {ticket.nonce}")

    def check(self, actor: str, capability: str) -> None:
        if capability not in self.granted:
            if self.audit is not None:
                self.audit.record(actor, "deny", capability, reason="not granted")
            raise PermissionError_(
                f"actor={actor} 缺少能力 '{capability}'（最小权限默认拒绝，需先 grant/approve）"
            )

    def has(self, capability: str) -> bool:
        return capability in self.granted
