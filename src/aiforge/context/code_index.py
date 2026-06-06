"""代码索引 + 依赖图（Phase 3，让 agent"看得懂大仓"）。

零依赖、基于标准库 ``ast`` 的 Python 符号索引与模块依赖图。给 agent 提供"去哪找"的检索，
减少大仓中 tool-thrashing。真实大仓可换成专用索引/知识图谱（如 Potpie）服务。
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class Symbol:
    name: str
    kind: str  # function / class
    module: str
    lineno: int


@dataclass
class CodeIndex:
    symbols: List[Symbol] = field(default_factory=list)
    imports: Dict[str, Set[str]] = field(default_factory=dict)  # module -> 依赖模块集合

    def search(self, query: str) -> List[Symbol]:
        q = query.lower()
        return [s for s in self.symbols if q in s.name.lower()]

    def dependents_of(self, module: str) -> List[str]:
        """谁依赖了 module（反向依赖，用于评估改动 blast radius）。"""
        return sorted(m for m, deps in self.imports.items() if module in deps)


def _module_name(path: str, root: str) -> str:
    rel = os.path.relpath(path, root)
    return rel[:-3].replace(os.sep, ".") if rel.endswith(".py") else rel


def build_index(root: str) -> CodeIndex:
    index = CodeIndex()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git", ".venv", "venv"}]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            module = _module_name(path, root)
            try:
                with open(path, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=path)
            except (SyntaxError, UnicodeDecodeError):
                continue
            deps: Set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    index.symbols.append(Symbol(node.name, "function", module, node.lineno))
                elif isinstance(node, ast.ClassDef):
                    index.symbols.append(Symbol(node.name, "class", module, node.lineno))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        deps.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    deps.add(node.module)
            index.imports[module] = deps
    return index
