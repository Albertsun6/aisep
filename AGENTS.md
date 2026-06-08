# AGENTS.md — AIForge 根级事实源

> 跨工具单一事实源（Cursor / Claude Code / Copilot / Codex 等通用）。这是"地图而非百科"：只放可操作规则，不复制 README。大仓中各子目录可放更近的 `AGENTS.md`，就近生效，最近者优先。

## 项目概览
AIForge 是一套"用 AI 工程化方式开发大型企业软件"的参考系统。核心引擎纯标准库实现，Python 3.9+。

## 技术栈
- 语言：Python 3.9+（核心**不引入**第三方运行时依赖）
- 测试：标准库 `unittest`
- 可选：`ruff`（lint/format）、真实 `langgraph` / `openhands`（通过适配层）

## 命令（务必使用这些，不要乱猜）
- 安装可选依赖：`pip install -r requirements-dev.txt`
- 跑全部测试：`make test`（等价 `python3 -m unittest discover -s tests -v`）
- 端到端 demo：`make demo`
- 跑 eval 四指标：`make eval`
- lint：`make lint`（需 ruff）
- 架构契约：`make arch`（import-linter，对照 `.importlinter` 锁分层边界，防 base↔governance 环恶化）

## 代码结构约定
- 业务逻辑放 `src/aiforge/<层>/`，每层职责单一，对应七层架构。
- 编排只通过 `orchestration/state.py` 的共享状态通信，禁止角色 agent 间直接耦合。
- 所有"写动作 / state-mutating"必须经 `governance/permissions.py` 与 `runtime` 沙箱，禁止直接 `os.system` / 裸写磁盘。
- 类型注解统一 `from __future__ import annotations` + `typing`（兼容 3.9，禁用 `X | Y` 运行时联合）。

## 禁改项（Do NOT modify）
- 不要绕过质量门禁（`quality/gates.py`）直接合并。
- 不要修改 `constitution.md` 的核心原则编号（只能追加）。
- 不要在代码中硬编码密钥；不要提交 `.env`。
- 不要让 agent 在缺少安全停机判断时执行 state-mutating 任务。

## 提交/PR 约定
- 单一逻辑改动一个 commit；信息用祈使句。
- 每个 PR 必须过四层门禁；高风险变更（迁移/安全/删除）强制人审（HITL）。
- 每次 agent session 后执行三文件 review（`governance/review.py`）。
