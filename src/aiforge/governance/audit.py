"""全量审计 trail（宪法 P8）。

每个决策、工具调用、权限授予都追加为一条结构化记录，可写入磁盘（JSONL），可复现可审查。
默认写到 ``.aiforge/audit/``。内存模式（path=None）便于测试。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class AuditEvent:
    actor: str            # 哪个 agent / 人
    action: str           # decision / tool_call / grant / gate / halt ...
    target: str           # 作用对象
    detail: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class AuditTrail:
    def __init__(self, path: Optional[str] = ".aiforge/audit/trail.jsonl") -> None:
        self.path = path
        self.events: List[AuditEvent] = []
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def record(self, actor: str, action: str, target: str, **detail: object) -> AuditEvent:
        ev = AuditEvent(actor=actor, action=action, target=target, detail=dict(detail))
        self.events.append(ev)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(ev), ensure_ascii=False) + "\n")
        return ev

    def filter(self, action: Optional[str] = None, actor: Optional[str] = None) -> List[AuditEvent]:
        out = self.events
        if action is not None:
            out = [e for e in out if e.action == action]
        if actor is not None:
            out = [e for e in out if e.actor == actor]
        return list(out)

    def __len__(self) -> int:
        return len(self.events)
