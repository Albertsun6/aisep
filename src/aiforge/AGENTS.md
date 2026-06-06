# AGENTS.md — src/aiforge（就近生效，覆盖根级补充约定）

> 本文件比根 AGENTS.md 更靠近源码，编辑此目录文件时优先参考这里。

## 本目录约定
- 每个子包对应七层架构中的一层，职责单一；新增能力先归位到正确的层。
- 角色 agent 间禁止直接 import 彼此；只经 `orchestration/state.PipelineState` 通信。
- 任何写磁盘 / 跑命令必须走 `runtime.Runtime` 子类，禁止裸 `open(...,'w')` / `os.system`。
- 新增公共类型放对应层的模块顶部，并在该层 `__init__.py` 导出。
- 兼容 Python 3.9：`from __future__ import annotations` + `typing`，禁用 `X | Y` 运行时联合与 `match`。

## 测试
- 每个层至少一个 `tests/test_<层>.py`；跑 `make test`。
