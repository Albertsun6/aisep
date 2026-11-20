# workbench-reference.md

AISEP 工作台（二期）开源参考选型。结论：以 Orchestrator.inc（agent-orchestrator）为工作台骨架，架构建模面板作为自有插件加入。

## 1. 工作台定位

AISEP 工作台是整个体系的驾驶舱：本人从前端做事，AI 在后台干活。它本身是 AISEP 方法论的第一个业务系统，按裁剪后的 ADM 走一遍，吃自己的狗粮。排期为二期（基础设施层之后），但设计现在并行进行。

已确认的需求（采访结论）：

- 首页是仪表盘，包含三块：架构全景、待批准关口、AI 正在干的活。
- 关口页面：顶部 AI 一段话摘要（做了什么、依据什么标准）；中间模型差异图（新增元素/关系高亮、受影响上下游标出）；下方校验结果与未决问题；底部批准 / 驳回 / 要求修改。代码只作为可展开附件，是最不需要看的。
- 需要在工作台内与 AI 聊天，例如在关口页面问"为什么这么设计"。
- 站在巨人肩膀上：用现有开源系统改，不从零到一。优先找源头项目，不用国内大厂的衍生品。

## 2. 主骨架：Orchestrator.inc / agent-orchestrator

仓库：github.com/OrchestratorInc/agent-orchestrator

| 项目 | 情况 |
| --- | --- |
| 许可证 | Apache-2.0（已确认） |
| 热度 | 14.6k 星，2.0k 分支，4,120 次提交，462 个 issue，537 个 PR，活跃 |
| 形态 | 本地桌面工作区（macOS / Windows / Linux）+ iPhone / Android，代码留在本机 |
| 技术栈 | 后端 Go（go.work），前端 Electron + React（frontend/src/renderer），另有 packages、contracts、docs 目录 |
| 支持的代理 | Claude Code、Codex、Cursor、opencode、Aider、Copilot、Goose、Cline 等 35+ |
| 自身规范 | 仓库根目录有 AGENTS.md、CLAUDE.md、DESIGN.md、CONTEXT.md，本身就是 AI 辅助开发的范例 |

核心能力与 AISEP 的对应：

| Orchestrator.inc 能力 | 对应 AISEP 需求 |
| --- | --- |
| 主代理规划任务、为每块工作启动独立 worker，每个 worker 有自己的分支和 worktree，只在需要人时回来 | 原则五：自动执行、人工把关 |
| 看板按状态分泳道：Working / Needs you / In review / Ready to merge，需要你的排最上面 | 仪表盘的"待批准关口"和"AI 正在干的活" |
| CI 失败、评审意见、合并冲突自动路由回负责该分支的 worker；可配置 reviewer 代理在人之前读每个 PR | SDLC 评审关口自动化 |
| 每任务可选代理和模型，结构化聊天或代理原生终端 UI，每个 worker 自带浏览器预览 | 工作台内聊天 |
| 插件架构（docs.orchestrator.inc/plugins），代理适配器以插件方式扩展 | 架构建模面板以插件形式加入 |

它缺的、正是 AISEP 的差异点：

- 没有架构模型概念，看板的单位是任务 / PR，不是业务能力或设计元素。
- 没有模型差异图，评审看的是代码 diff。
- 没有跨阶段追溯（需求 → 架构 → 代码 → 测试）。

## 3. 配套组件

| 组件 | 用途 | 许可证 | 备注 |
| --- | --- | --- | --- |
| CopilotKit | 嵌入式 AI 聊天组件、人在环路、共享状态，代理可直接渲染组件而非只描述（生成式 UI） | MIT | 用于关口页面的聊天与"AI 直接弹出模型差异图" |
| bpmn-js / diagram-js | BPMN 查看与编辑 | MIT（bpmn.io 许可，需保留水印或购买移除） | BPMN 事实标准 |
| React Flow (xyflow) | 通用节点图：ArchiMate 视图、DDD 上下文图、追溯链图 | MIT | 与 Electron + React 技术栈一致 |
| optim-plans | Claude / Codex 的人在环路规划插件：想法 → 评审过的 Markdown 计划 → 记录决策 → 强制执行关口 | 待确认 | 可借鉴其"计划评审关口"的交互设计 |
| TaskHandoff | 自托管控制平面：每任务独立检出、diff 评审关口、规划代理 / 执行代理 / 人工评审交接 | Apache-2.0 | 小而精，作对照参考 |

## 4. 集成架构（草案）

三层对应：

1. 基础设施层（一期）：Linked.Archi 本体 + RDF 存储 + SHACL 校验 + SPARQL，通过 MCP Server 暴露给 AI 和工作台。
2. 工作台（二期）：Orchestrator.inc 骨架 + 自有"架构面板"插件。架构面板读 MCP Server 的模型数据，用 React Flow / bpmn-js 渲染，用 CopilotKit 嵌聊天。关口页面把 Orchestrator.inc 的 PR 评审与模型差异图合在一页。
3. 执行层：Claude Code / Codex 作为 Orchestrator.inc 的 worker，读 AISEP 仓库的 CLAUDE.md / AGENTS.md 和模型文件干活。

关键接口：MCP。基础设施层做 MCP Server，工作台和编码代理都是 MCP Client，模型数据只有一个来源（原则一）。

## 5. 风险

- Orchestrator.inc 迭代很快（4,000+ 提交），自有插件要跟上其插件 API 的变化；建议 fork 后锁定版本，按季度合并上游。
- 它是桌面应用（Electron），不是 Web 服务。如果将来需要多人协作或远程访问，架构要重新评估。
- bpmn-js 免费版带 bpmn.io 水印，商用界面若要去水印需付费。

## 6. 待办

- [ ] 第一验证点：Orchestrator.inc 的插件机制能否添加全新的界面面板（而不只是后台能力）。能 → 走插件路线；不能 → fork 源码改前端（React + Electron），并接受定期合并上游的成本
- [ ] 下载 Orchestrator.inc 试用，重点看看板、关口交互、插件机制和 docs.orchestrator.inc/plugins
- [ ] 读其 DESIGN.md 和 AGENTS.md，评估直接 fork 的可行性
- [ ] 确认 CopilotKit 与 Electron 环境的兼容性
- [ ] 按裁剪后的 ADM 为工作台写架构愿景（本文档第 1 节为输入）
- [ ] 一期 MCP Server 的接口设计要同时满足编码代理和工作台两类客户端
