"""Agent-as-a-Judge（修 C2）：基于**内容**判定，而非只看 task_type 关键词。

原版缺陷 C2：approved 仅由 task_type ∩ {5 词} 决定，三个 persona 的 LLM 意见被生成后丢弃，
危险代码只要标签是 feature 就自动放行。修复（经异构评审，见挑战评估/fix_proposal）：
- 自动通过的**充要条件** = 可信 LLM 非阻断裁决 且 静态扫描无命中 且 非高风险；
- 可信 = **显式** trust_llm=True 且非 MockLLM——挂真模型不自动可信(STEP 0 v2 首批③翻转原"接通即 trusted"地雷)；
- 无可信 LLM（MockLLM）/ 解析失败 / 扫描命中 / 高风险 → 一律转人审，**绝不自动放行**；
- 静态扫描只"升级到人审"，不据其放行、也不据其硬拒（误报至多多看一眼）；
- 三态 APPROVED / NEEDS_HUMAN / REJECTED。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.llm import LLMClient, MockLLM

APPROVED, NEEDS_HUMAN, REJECTED = "approved", "needs_human", "rejected"


class StaticRiskScanner:
    """确定性危险模式扫描——加速器，不是裁决者（诚实：清单有限、可被绕过、会误报）。"""

    PATTERNS = (
        (r"\beval\s*\(", "blocker", "eval() 可能 RCE"),
        (r"\bexec\s*\(", "blocker", "exec() 可能 RCE"),
        (r"\bos\.system\s*\(", "blocker", "os.system 命令注入"),
        (r"\bos\.popen\s*\(", "blocker", "os.popen 命令注入"),
        (r"\bsubprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True", "major", "subprocess shell=True"),
        (r"(?i)\bpassword\s*==", "major", "疑似明文比较密码"),
        (r"(?is)f['\"][^'\"]*\b(select|insert|update|delete)\b[^'\"]*\{", "blocker", "疑似 f-string 拼接 SQL"),
        (r"\bexcept\s*:\s*(\n\s*)?pass\b", "major", "空 except: pass 吞错误"),
        (r"(?i)\b(api[_-]?key|secret|passwd|password)\s*=\s*['\"][^'\"]{6,}['\"]", "major", "疑似硬编码密钥"),
        (r"(?i)\bverify\s*=\s*False\b", "major", "TLS 校验关闭"),
        (r"\b(pickle|dill)\.loads?\s*\(", "major", "不可信反序列化"),
        (r"\bhashlib\.md5\s*\(", "major", "弱哈希 md5"),
    )

    def __init__(self):
        self._c = [(re.compile(p), sev, msg) for p, sev, msg in self.PATTERNS]

    def scan(self, text: str) -> list[dict]:
        code = "\n".join(ln for ln in (text or "").splitlines() if not ln.lstrip().startswith("#"))
        return [{"source": "static", "severity": sev, "issue": msg} for rx, sev, msg in self._c if rx.search(code)]


_PANEL = {
    "saboteur": "你是 Saboteur：找可被破坏的点（注入/缺校验/边界/错误处理/越权）。最后一行只输出 SEVERITY: blocker|major|minor|ok。",
    "compliance": "你是 Compliance：检查安全/可观测/审计/PII/限流是否缺失。最后一行只输出 SEVERITY: blocker|major|minor|ok。",
    "new_hire": "你是 New Hire：仅凭代码能否读懂意图？指出认知债。最后一行只输出 SEVERITY: blocker|major|minor|ok。",
}
_SEV = re.compile(r"SEVERITY:\s*(blocker|major|minor|ok)", re.IGNORECASE)


@dataclass
class JudgeVerdict:
    decision: str
    findings: list[dict] = field(default_factory=list)
    rationale: str = ""

    @property
    def approved(self) -> bool:
        return self.decision == APPROVED

    @property
    def requires_human(self) -> bool:
        return self.decision == NEEDS_HUMAN

    def summary(self) -> str:
        return f"Agent-as-Judge 裁决: {self.decision}（{self.rationale}; {len(self.findings)} 条意见）"


class AgentAsJudge:
    def __init__(self, llm: LLMClient | None = None, config: GovernanceConfig = DEFAULT_GOVERNANCE,
                 trust_llm: bool | None = None) -> None:
        self.llm = llm or MockLLM()
        self.config = config
        self.scanner = StaticRiskScanner()
        # 默认不可信,显式 opt-in:挂真 LLM 不自动获得放行权(防"接通即 trusted"重开 C2);
        # MockLLM 无真实判断力,即便显式 trust_llm=True 也不信(只会更保守,fail-closed)。
        self.trust_llm = (trust_llm is True) and not isinstance(self.llm, MockLLM)

    def review(self, diff_summary: str, task_type: str | None = None,
               risk_keywords: list[str] | None = None) -> JudgeVerdict:
        findings = list(self.scanner.scan(diff_summary))
        scan_hit = bool(findings)

        llm_blocker = llm_unparseable = False
        if self.trust_llm:
            for name, system in _PANEL.items():
                text = self.llm.complete(system + " (judge)", diff_summary)
                m = _SEV.search(text or "")
                if m is None:
                    llm_unparseable = True
                    findings.append({"source": name, "severity": "major", "issue": "LLM 输出无法解析严重度"})
                else:
                    findings.append({"source": name, "severity": m.group(1).lower(), "issue": (text or "")[:80]})
                    if m.group(1).lower() == "blocker":
                        llm_blocker = True

        risk_keywords = risk_keywords or []
        hi = set(self.config.high_risk_task_types)
        risky = (task_type in hi) or any(k in hi for k in risk_keywords)
        if risky:
            findings.append({"source": "policy", "severity": "major", "issue": f"高风险 {task_type or risk_keywords}，转人审"})

        if llm_blocker:
            return JudgeVerdict(REJECTED, findings, "可信 LLM 判定 blocker")
        if not self.trust_llm:
            return JudgeVerdict(NEEDS_HUMAN, findings, "无可信 LLM，保守转人审")
        if llm_unparseable:
            return JudgeVerdict(NEEDS_HUMAN, findings, "LLM 协议失效，转人审")
        if scan_hit:
            return JudgeVerdict(NEEDS_HUMAN, findings, "静态扫描命中，转人审")
        if risky:
            return JudgeVerdict(NEEDS_HUMAN, findings, "高风险，转人审")
        return JudgeVerdict(APPROVED, findings, "可信 LLM 无阻断 + 扫描无命中 + 非高风险")
