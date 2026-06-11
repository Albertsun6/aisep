"""可插拔 LLM 客户端（对应宪法 P9 选型可替换）。

默认 ``MockLLM`` 是确定性的、离线可跑的，保证整套系统无需 API key 即可端到端运行与测试。
真实接入时实现 ``LLMClient`` 协议（例如包装 OpenAI / Anthropic / LangGraph 节点）即可替换。
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable


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
        self.calls: list[dict] = []

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


class StubCodeLLM:
    """离线确定性"代码生成"替身（修 C1 后供 demo/eval/测试端到端跑**真验证**）。

    与 ``MockLLM`` 的区别：MockLLM 只产指纹串（无法成为代码，改进后的 developer 会对它安全停机）；
    ``StubCodeLLM`` 产出**合法、可执行、可被测试验证**的代码——虽然 trivial，但是真代码（会被沙箱真跑、
    被变异校验）。**不是真 LLM**：真实接入实现 ``LLMClient`` 协议替换即可。
    """

    def complete(self, system: str, user: str) -> str:
        low = system.lower()
        if "analyst" in low:
            # 产出带验收结构的 spec(过 SpecGate/C6)
            req = user.strip().splitlines()[0][:40] if user.strip() else "该功能"
            return (f"User Story: As a user, I want {req}, so that 目标达成。\n"
                    "验收标准: Given 已满足前置条件 When 触发该功能 Then 返回预期结果并记录。")
        if "developer" in low:
            return "```python\ndef solution():\n    return 42\n```"
        if "tester" in low:
            return ("```python\nimport unittest\nfrom solution import solution\n"
                    "class TestSolution(unittest.TestCase):\n"
                    "    def test_value(self):\n        self.assertEqual(solution(), 42)\n```")
        snippet = user.strip().splitlines()[0][:80] if user.strip() else ""
        return f"[stub] 已处理: {snippet}"


class StubReviewerLLM:
    """离线确定性"可信评审"替身（修 C2 后供 demo/eval/测试让干净变更能自动通过 judge）。

    返回结构化 ``SEVERITY: ok``——代表"一个称职评审者看完没发现阻断问题"。**不是真 LLM**；
    真实接入用真模型替换。Judge 仍会叠加静态扫描 + 高风险类型门（命中即转人审，与本替身无关）。
    """

    def complete(self, system: str, user: str) -> str:
        return "审查完毕，未见阻断性问题。\nSEVERITY: ok"
