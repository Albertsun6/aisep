"""Skills 渐进披露（progressive disclosure）。

每个 skill 有轻量元信息（name + description + triggers）常驻，正文 body 仅在被触发时按需加载，
避免上下文窗口饱和。对应调研：文件系统 + 渐进式披露按需加载领域专长。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    # body 用懒加载：避免一次性把所有 skill 正文塞进上下文
    _loader: Callable[[], str] | None = None
    _cached: str | None = None

    def matches(self, query: str) -> bool:
        low = query.lower()
        return any(t.lower() in low for t in self.triggers)

    def load_body(self) -> str:
        if self._cached is None:
            self._cached = self._loader() if self._loader else ""
        return self._cached


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def manifest(self) -> str:
        """常驻清单：只暴露元信息（渐进披露第一层）。"""
        lines = [f"- {s.name}: {s.description}" for s in self._skills.values()]
        return "\n".join(lines)

    def select(self, query: str) -> list[Skill]:
        """按触发词选中相关 skill（第二层：被选中才 load_body）。"""
        return [s for s in self._skills.values() if s.matches(query)]

    def __len__(self) -> int:
        return len(self._skills)
