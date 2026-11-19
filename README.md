# AISEP

AI 驱动的软件工程平台：统一模型仓库（ArchiMate 4.0 枢纽 + BPMN / UML / DDD）+ AI 接入。一期交付物是 MCP Server（ADR-008），本仓库目前包含元模型、校验工具原型、示例模型和各 ADM 阶段的模板。

| 目录 | 内容 |
|---|---|
| `docs/` | 原则、方法论、元模型规范、决策记录（ADR）、MCP 接口设计、ADM 阶段模板 `docs/adm/`、历史证据 `docs/history/` |
| `vendor/` | 上游 Linked.Archi 本体（只读） |
| `modules/` | AISEP 模块：本体、shapes、对齐、测试 |
| `models/` | 模型（一个目录一个模型），`procurement/` 为示例 |
| `tools/aisep.py` | CLI：`gate` / `check` / `validate` / `findings` / `query` / `impact` / `build` / `test` |

使用方法见 `USAGE.md`，代理规则见 `AGENTS.md`。
