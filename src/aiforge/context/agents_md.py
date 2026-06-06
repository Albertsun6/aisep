"""嵌套 AGENTS.md 加载：从目标文件所在目录向上找最近的 AGENTS.md，最近者优先。

对应调研结论：大仓用嵌套 AGENTS.md（OpenAI 主仓 88 个），就近生效。
返回从根到最近一路的内容（最近的排最后，优先级最高）。
"""

from __future__ import annotations

import os
from typing import List, Optional


def find_agents_md_chain(start_path: str, repo_root: str) -> List[str]:
    """返回从 repo_root 到 start_path 目录链上所有 AGENTS.md 的绝对路径（根在前）。"""
    start_path = os.path.abspath(start_path)
    repo_root = os.path.abspath(repo_root)
    if os.path.isfile(start_path):
        start_path = os.path.dirname(start_path)

    chain: List[str] = []
    current = start_path
    while True:
        candidate = os.path.join(current, "AGENTS.md")
        if os.path.isfile(candidate):
            chain.append(candidate)
        if os.path.abspath(current) == repo_root:
            break
        parent = os.path.dirname(current)
        if parent == current:  # 到达文件系统根
            break
        current = parent
    chain.reverse()  # 根在前，最近的在后（优先级最高）
    return chain


def load_nearest_agents_md(
    target_path: str, repo_root: str, separator: str = "\n\n---\n\n"
) -> Optional[str]:
    """加载链上所有 AGENTS.md 并拼接（最近者在末尾，覆盖语义靠提示词中"后者优先"约定）。"""
    chain = find_agents_md_chain(target_path, repo_root)
    if not chain:
        return None
    parts = []
    for path in chain:
        with open(path, encoding="utf-8") as f:
            rel = os.path.relpath(path, repo_root)
            parts.append(f"# <<from {rel}>>\n{f.read().strip()}")
    return separator.join(parts)
