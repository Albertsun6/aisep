# feat-aisep-console — 意图简报(R1)

track: standard
source: /survey 调研报告「多项目AI开发控制台形态-完整报告.md」(51 源,GPT-5.5 终审收敛)+ 2026-06-13 会话原型与范围裁决 + auction pilot-log 高严重度摩擦「聊天内 R1 问答认知负荷过高」

## problem
跑 AISEP R1-R5 管线时,人类决策点(R1 意图六问 / R2 圈范围 / R3 答红卡 / R4 定优先级)只活在聊天流里,认知负荷过高——用户要在对话中同时记住六个问题、流程语境与已答内容。auction pilot 因此被阻塞(用户拒答 R1,要求"前端 ready 后再答")。缺一个把决策点结构化呈现 + 引导的前端,且要在多个本地仓之间看清"哪个项目在哪步、等我决策什么"。

## users
单人开发者(本人),同时管理方法论仓 AISEP + 业务仓 auction(未来更多本地仓);在多个 Claude Code 会话间并行工作,既造工具又用工具。

## 成功指标
v1 的可观察成功 = 用户能在前端上完成 auction-mvp 的 R1 意图填写(六字段结构化表单 + 引导),产出的 intent.md **一次性通过 gate-intent(exit 0)**,无需在聊天里逐问回答;换会话开 auction 即可直接从该产物推进 R2,不再被 R1 认知负荷阻塞。

## non-goals
- v1 不做实时多仓扫描 server(Portfolio/Inbox 实时数据 = v1.1;v1 总览为外壳 + 本仓快照,显式标注)
- v1 不做前端直写 SSOT 文件(表单直写 intent.md/clarifications.md = v1.5,需先补写动作审计设计)
- 不采用任何现成 AI 看板二开(vibe-kanban 等已 sunset + 自管 SQLite 与 SSOT 冲突,调研已证伪)
- 不做 R2-R5 的填表引导(v1 仅 R1 表单——R1 是最开放、认知负荷最重的环节;R2-R5 反应式决策暂留聊天)
- 不做云端 / 多人协作 / 权限体系
- 不替代 Claude Desktop / Conductor 等执行台(并用,不承载)

## appetite
半天到一天(单文件零构建 HTML 为主);v1 不引入新运行时依赖、不引入 server。超出此 appetite 的部分(server、直写)显式推迟到 v1.1/v1.5。
