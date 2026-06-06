"""Agent-as-a-Judge：独立 agent 审计产出，替代不可靠的人工逐行 review。

实现调研中的对抗 persona：
- Saboteur：找能被破坏的薄弱点（缺校验 / 边界 / 错误处理）。
- New Hire：能否仅凭代码与文档读懂意图（认知债视角）。
裁决聚合为通过 / 需修改 / 拒绝。LLM 可插拔（默认 MockLLM）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from aiforge.llm import LLMClient, MockLLM

JUDGE_PERSONAS = {
    "saboteur": "你是 Saboteur，对抗式审查者：找出这段变更可被破坏的点——缺失的输入校验、边界条件、错误处理、并发/重试。",
    "new_hire": "你是 New Hire：仅凭代码与文档，你能否说清这段变更的意图？指出认知债（难以理解之处）。",
    "compliance": "你是 Compliance 审查者：检查非功能需求——安全、可观测、审计、PII、限流是否缺失（80% 问题）。",
}


@dataclass
class JudgeVerdict:
    approved: bool
    findings: List[dict] = field(default_factory=list)

    def summary(self) -> str:
        status = "通过" if self.approved else "需修改/拒绝"
        return f"Agent-as-Judge 裁决: {status}（{len(self.findings)} 条意见）"


class AgentAsJudge:
    def __init__(self, llm: LLMClient = None) -> None:
        self.llm = llm or MockLLM()

    def review(self, diff_summary: str, risk_keywords: List[str] = None) -> JudgeVerdict:
        risk_keywords = risk_keywords or []
        findings: List[dict] = []
        for persona, system in JUDGE_PERSONAS.items():
            opinion = self.llm.complete(system + " (judge)", diff_summary)
            findings.append({"persona": persona, "opinion": opinion})

        # 确定性裁决规则（不依赖 LLM 文本解析）：命中高风险关键字即不自动通过，需人审。
        blocking = [k for k in risk_keywords if k in ("security", "migration", "delete", "auth", "payment")]
        approved = len(blocking) == 0
        if blocking:
            findings.append({"persona": "policy", "opinion": f"命中高风险: {blocking}，不予自动通过，转人审"})
        return JudgeVerdict(approved=approved, findings=findings)
