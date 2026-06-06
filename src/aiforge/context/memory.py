"""上下文管理三件套（对应 Anthropic 一方 API：compaction / tool-result clearing / memory）。

这里用纯 Python 复刻其语义，便于在零依赖下演示与测试控制流；真实接入时换成 API 调用。
- compaction：token（这里用近似字符数）超阈值时，把旧消息摘要成一条 compaction block。
- tool-result clearing：清理可重新获取的大体积 tool 结果，保留引用。
- memory：跨会话持久化的键值笔记（/memories）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _approx_tokens(text: str) -> int:
    # 粗略近似：4 字符 ≈ 1 token
    return max(1, len(text) // 4)


@dataclass
class ContextWindow:
    messages: List[dict] = field(default_factory=list)
    memory: Dict[str, str] = field(default_factory=dict)  # 跨会话 /memories
    compact_trigger_tokens: int = 50_000  # 与 Anthropic compact 最小阈值一致
    _compactions: int = 0

    def add(self, role: str, content: str, kind: str = "text") -> None:
        self.messages.append({"role": role, "content": content, "kind": kind})
        self.maybe_compact()

    def total_tokens(self) -> int:
        return sum(_approx_tokens(m["content"]) for m in self.messages)

    def clear_tool_results(self, keep_last: int = 1) -> int:
        """tool-result clearing：清掉较早的、可重取的大块 tool 结果，保留最近 keep_last 条。"""
        tool_idx = [i for i, m in enumerate(self.messages) if m["kind"] == "tool_result"]
        to_clear = tool_idx[:-keep_last] if keep_last > 0 else tool_idx
        cleared = 0
        for i in to_clear:
            self.messages[i] = {
                "role": self.messages[i]["role"],
                "content": "[tool_result cleared — 可按引用重新获取]",
                "kind": "cleared",
            }
            cleared += 1
        return cleared

    def maybe_compact(self) -> bool:
        """compaction：超阈值时把早期消息摘要为单条 compaction block。"""
        if self.total_tokens() < self.compact_trigger_tokens:
            return False
        if len(self.messages) <= 2:
            return False
        head = self.messages[:-2]
        summary = f"[compaction#{self._compactions + 1}] 摘要了 {len(head)} 条早期消息"
        self.messages = [{"role": "system", "content": summary, "kind": "compaction"}] + self.messages[-2:]
        self._compactions += 1
        return True

    def remember(self, key: str, value: str) -> None:
        self.memory[key] = value

    def recall(self, key: str) -> Optional[str]:
        return self.memory.get(key)
