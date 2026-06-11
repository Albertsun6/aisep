# docs/ — 决策与方案文档导航

本目录收纳 AISEP × Claude Code 工程 harness 的**决策日志、实施方案、前期调研、架构图**。
代码与运行态资产不在这里:契约见 [`../specs/contracts/`](../specs/contracts/),门禁 CLI 见 [`../src/aiforge/harness.py`](../src/aiforge/harness.py),项目总览见 [`../README.md`](../README.md)。

> 衍生渲染(`.html`)与音频(`.m4a`)版本已归档至 repo 外 `../AISEP6-6-archive/`(ADR-013),不入库。

## decisions/ — 架构决策日志

| 文档 | 是什么 | 状态 |
|---|---|---|
| [AISEP-ClaudeCode架构决策文档.md](decisions/AISEP-ClaudeCode架构决策文档.md) | ADR-001~014 + 关键事实速查(平台选型、编排主干、复用核、异构验证、成本、模型策略、就地实施、权威层级…) | 活文档,随实施更新 |

> 项目宪法在 repo 根 [`../constitution.md`](../constitution.md)(P1~P9,受 CODEOWNERS 保护,只能人改)。

## plans/ — STEP 0 实施方案

| 文档 | 是什么 | 状态 |
|---|---|---|
| [有头先行实施方案-v2.md](plans/AISEP-ClaudeCode有头先行实施方案-v2.md) | **现行方案**:就地实施 / 冻 10 契约 / Fable 5=少建设;经异构评审 + 对抗证伪 | **已完整实施(2026-06-11)** |
| [有头先行实施方案.md](plans/AISEP-ClaudeCode有头先行实施方案.md) | v1 原方案 | 已被 v2 取代,留作历史 |

## research/ — 前期调研与可行性

| 文档 | 是什么 |
|---|---|
| [harness 可行性与实施设计-完整报告.md](research/AISEP移植ClaudeCode作为企业工程harness-可行性与实施设计-完整报告.md) | "aiforge 当 CC 企业工程 harness"的可行性裁决(HYBRID)+ 实施设计 |
| [harness 完整实施方案.md](research/AISEP移植ClaudeCode作为企业工程harness-完整实施方案.md) | 前期完整实施方案(STEP 0 v2 的上游输入) |
| [AISEP6-6-健康度报告.md](research/AISEP6-6-健康度报告.md) | `/project-health` 对本 repo 的健康度评估 |

## diagrams/ — 架构图

| 文档 | 是什么 |
|---|---|
| [功能版架构图.html](diagrams/AISEP-ClaudeCode功能版架构图.html) | 七层 → CC 扩展面映射的可视化(三视角:分层/管线/时序) |

## 阅读顺序建议

1. 想知道**怎么用**这套 harness → repo 根 [`../README.md`](../README.md) + 本目录之外的 `USAGE`(HTML 使用手册)。
2. 想知道**为什么这么设计** → `decisions/` 的 ADR。
3. 想知道**实施怎么落的** → `plans/` v2 + `../specs/contracts/`(10 条接口契约)。
4. 想追**前期怎么论证的** → `research/`。
