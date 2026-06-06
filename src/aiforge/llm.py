"""可插拔 LLM 客户端（对应宪法 P9 选型可替换）。

默认 ``MockLLM`` 是确定性的、离线可跑的，保证整套系统无需 API key 即可端到端运行与测试。
真实接入时实现 ``LLMClient`` 协议（例如包装 OpenAI / Anthropic / LangGraph 节点）即可替换。
"""

from __future__ import annotations

import hashlib
from typing import List, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """最小 LLM 协议：给定 system + user，返回文本。"""

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - 协议
        ...


class MockLLM:
    """确定性 mock：根据角色 system 提示生成结构化、可预测的产出。

    设计目标不是"像真的"，而是让编排 / 门禁 / eval 的**控制流**可被确定性地测试。
    输出带有稳定指纹，便于断言与回归。
    """

    def __init__(self, seed: str = "aiforge") -> None:
        self.seed = seed
        self.calls: List[dict] = []

    def _fingerprint(self, *parts: str) -> str:
        h = hashlib.sha256((self.seed + "::" + "::".join(parts)).encode()).hexdigest()
        return h[:8]

    def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        role = "generic"
        low = system.lower()
        for candidate in ("analyst", "architect", "developer", "reviewer", "tester", "judge"):
            if candidate in low:
                role = candidate
                break
        fp = self._fingerprint(role, user)
        return f"[{role}:{fp}] {self._role_body(role, user)}"

    @staticmethod
    def _role_body(role: str, user: str) -> str:
        snippet = user.strip().splitlines()[0][:80] if user.strip() else ""
        bodies = {
            "analyst": f"已澄清需求并列出验收标准，基于: {snippet}",
            "architect": f"已给出模块边界与数据流设计，基于: {snippet}",
            "developer": f"已实现功能并补充错误处理/日志，基于: {snippet}",
            "reviewer": f"已审查变更与非功能需求，基于: {snippet}",
            "tester": f"已生成单元/集成测试，基于: {snippet}",
            "judge": f"裁决: 通过(无明显风险)，基于: {snippet}",
        }
        return bodies.get(role, f"已处理: {snippet}")
