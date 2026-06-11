# AIForge — AI 工程化软件开发系统

用工程化方式组织 AI（规格驱动 + 多 Agent 编排 + 上下文/知识工程 + 质量门禁 + 治理审计）来开发大型企业软件的参考实现。

本仓库是 [`ai工程化开发系统方案`](.cursor/plans/) 调研方案的可运行落地骨架。核心引擎**零第三方依赖**（纯 Python 标准库，3.9+），开箱即测；真实 LangGraph / OpenHands / LLM 通过适配层接入。

> 🚀 **第一次用?** 看手把手教程 [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md)（15 分钟从零跑通一个特性）。要查命令看参考手册 [docs/USER-GUIDE.md](docs/USER-GUIDE.md)。

## 七层架构

```
治理层 Governance      —— constitution + AGENTS.md + 最小权限 + 安全停机 + 审计
规格驱动 SDD           —— specify → plan → tasks（可追溯产物）
编排层 Orchestration   —— supervisor + 角色 agent（Analyst/Architect/Developer/Reviewer/Tester）
上下文/知识工程         —— 嵌套 AGENTS.md + Skills 渐进披露 + 上下文管理三件套
执行层 Runtime         —— 沙箱 runtime（local / OpenHands 自托管适配）
质量门禁 Quality        —— 四层门禁 + Agent-as-Judge + 四个生产指标
可观测/审计 Observability —— 决策/工具调用全量 trail + 指标看板
```

## 快速开始

```bash
# 1. 不需要任何安装即可跑核心引擎与测试（纯标准库）
make test

# 2. 端到端跑一次规格驱动 + 多 agent 编排（mock LLM，离线可跑）
make demo

# 3. 跑 eval 集，计算四个生产指标
make eval

# 4. 静态检查与格式（可选，需 ruff）
make lint
```

## 目录

| 路径 | 说明 |
|---|---|
| `constitution.md` | 项目宪法：不可逾越的工程原则（规格驱动四阶段第 0 步） |
| `AGENTS.md` | 跨工具单一事实源（根级 + 关键目录嵌套，就近生效） |
| `docs/` | **决策与方案文档**（ADR / STEP 0 方案 / 调研 / 架构图）——见 [`docs/README.md`](docs/README.md) 导航 |
| `specs/` | 规格驱动产物：模板 + 示例 feature（spec/plan/tasks）+ `specs/contracts/`（10 条冻结接口契约） |
| `.claude/` `.githooks/` `.github/` | STEP 0 harness：角色 agent / 阶段 skill / 会话护栏；本地 pre-commit；CI 强制层（required check `gates`） |
| `src/aiforge/harness.py` | 门禁 CLI 适配层（`python -m aiforge gate-*`，永不调模型，退出码 0/1/2/3） |
| `src/aiforge/orchestration/` | 编排引擎：state / graph(supervisor) / 角色 agent |
| `src/aiforge/context/` | 上下文工程：AGENTS.md 加载、Skills、记忆管理 |
| `src/aiforge/quality/` | 质量门禁：四层 gate、Agent-as-Judge、四指标 |
| `src/aiforge/runtime/` | 执行 runtime：抽象基类 + 本地沙箱 + OpenHands 适配 |
| `src/aiforge/governance/` | 治理：审计 trail、最小权限、三文件 review |
| `src/aiforge/eval/` | eval harness + 数据集 |
| `deploy/openhands/` | OpenHands 自托管部署配置 |
| `dashboard/` | 四指标看板 |
| `tests/` | 单元/集成测试（`python -m unittest`，无需安装） |

## 工程决策

- **核心零依赖**：编排引擎复刻 LangGraph 的 supervisor + checkpoint 心智模型，但用标准库实现，确保任何环境都能跑通和测试。
- **LLM 可插拔**：默认 `MockLLM`（确定性，离线），通过 `LLMClient` 协议可换成真实模型 / LangGraph。
- **失败模式内建到架构**：最小权限、blast-radius 上限、安全停机、state-mutating 强制 HITL、三文件 review，直接对应调研中 60% 高危事件与"80% 问题/认知债"。
