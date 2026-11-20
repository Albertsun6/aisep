# 问题简报：工作台“AI 进行中”区域的数据来源

日期：2026-11-20 · 来源：执行会话 · 交给：设计会话拍板
（按总纲第 111 行的分工，设计决策在设计会话里做，执行会话负责提问并落实文件。）

## 1. 要回答的问题

工作台首页有三块：架构全景、待批准关口、AI 进行中（`workbench-reference.md:11` 原话是“AI 正在干的活”）。前两块已按元模型草案接上假数据。第三块**没有数据来源**：现在只显示“暂无数据来源”（`workbench/frontend/src/renderer/aisep/AisepWorkbenchPage.tsx:42`）。

请设计会话定三件事：
1. **语义**：“AI 正在干的活”指什么？是“哪个代理在跑哪个任务”（运行态），还是“哪些架构元素正在被 AI 改动、改到哪一步”（治理态），还是两者都要？
2. **来源**：数据从哪里读？AO 会话、模型仓库，还是两边各取一部分？
3. **是否改元模型 / MCP 契约**：如果要进模型仓库，需要新增什么实体，以及在 §8.3 加什么工具。

## 2. 已知事实（带出处）

- **元模型 v0.3 没有“AI 活动”实体。** §8.3 的 MCP 工具全是建模和治理操作（add_element / add_relationship / remove / check / validate / query / impact / findings / record_approval）。§6.7 只说“提交、构建、部署的溯源只定义词汇（PROV-O），不做接入”。§6.6 的 `aisep:approvedBy` 允许指向 `prov:Agent`，所以 PROV-O 的 Agent 概念已经在词汇里。
- **§8.3 有硬约束：** “所有写操作都是 Turtle 文件的修改，进 Git；MCP 不保存任何不在文件里的状态。”
- **ADR-008：** 工作台和编码代理都是 MCP Server 的客户端，坚持单一事实来源。**ADR-009：** 批准记录放模型仓库，“更换工作台不丢历史”。
- **AO 已有现成的会话数据。** 守护进程 REST 接口 `GET /api/v1/sessions`，前端用它加 SSE 刷新（`frontend/src/renderer/hooks/useWorkspaceQuery.ts:305`）。会话状态枚举有 15 个值，包括 `working`、`needs_input`、`pr_open`、`review_pending`、`mergeable`、`merged`、`terminated` 等（`frontend/src/api/schema.ts:6507`）。看板列是 Building / Validating / In review / Ready，“Needs you”是会话状态加通知（`spike-workbench-result.md:41`）。
- **AO 的单位是任务 / PR，不是架构元素**（`workbench-reference.md:41`）。AO 会话目前不知道自己改动了哪些模型元素。
- fork 之后，前端可以直接请求本机守护进程和本机 MCP Server（CSP 放行 `127.0.0.1`，`spike-workbench-result.md:65`），技术上两条路都通。

## 3. 方案

### A. 直接读 AO 会话（运行态）
在 `aisep/` 里调用 AO 已有的 sessions 接口，按状态列出正在跑的代理和任务。
- 好处：零元模型改动，实时，现成。
- 代价：数据只存在于 AO（`~/.ao`），不在模型仓库，和 ADR-008/009 的单一事实来源有张力，换工作台就没了；没法回答“它在改哪个架构元素”；上游接触面不变，但要依赖 AO 的 API schema，升级时多一个可能变动的点。

### B. 进模型仓库（治理态）
在元模型里新增 AI 活动实体（比如 `aisep:AgentActivity ⊑ prov:Activity`，带 `prov:wasAssociatedWith` → `prov:Agent`、`prov:startedAtTime`、作用的元素），通过 MCP 写入，工作台用 `model.query` 读。
- 好处：能和架构元素、批准记录关联，可追溯，符合 ADR-008/009。
- 代价：要改元模型（§6.6 / §6.7）和 MCP 契约（§8.3 加工具）。“正在进行中”是高频变化的运行状态，写进 Git 里的 Turtle 文件不自然：会产生大量提交，与 §8.3“MCP 不保存文件外状态”同时成立时就只能这样。

### C. 折中：运行态读 AO，关联与历史进模型仓库
“谁在跑、什么状态”实时读 AO 会话（同 A）；“这次会话动了哪些元素”这层关联，由 MCP 写入时顺带留下溯源（比如写操作带上会话标识，或者提交时由 §6.7 的 PROV-O 词汇记一条 Activity），只记已经发生的事，不记“进行中”。
- 好处：运行态不进 Git；历史和关联留在单一事实来源里；区域能显示“代理 X 正在处理任务 Y，已改动元素 Z1、Z2”。
- 代价：两个数据源要在前端拼接，需要一个共享键（会话 ID 或分支名）；仍然要动 §6.7 和 §8.3，只是改动较小。

## 4. 执行会话的倾向（仅供参考，不是决策）

倾向 C，或者先做 A、把 C 的模型部分推迟到 MCP 接口设计（下一步第 2 项）一起定。理由：“进行中”本质是运行态，B 和 §8.3 的“只有文件、进 Git”冲突最大；而 A 单独用又丢了和架构元素的关联，这正是 AISEP 和 AO 看板的区别所在。

## 5. 拍板后会牵动的文件

- `AISEP 第二步：元模型规范（草案）.md` §6.7、§8.3（选 B 或 C 时）
- `decisions.md`：新增一条 ADR
- `workbench/frontend/src/renderer/aisep/data/client.ts`（PROVISIONAL 接口，选 A 或 C 时需要一个读会话的客户端）
- `workbench/frontend/src/renderer/aisep/AisepWorkbenchPage.tsx`（区域渲染）
- `workbench/UPSTREAM.md`：若依赖 AO sessions API，要登记进接触面清单
- 与第 2 项（MCP 接口设计，ADR-008）的关系：选 B 或 C 时，两项最好一起设计。

## 6. 请设计会话回给执行会话的内容

1. 选 A / B / C（或别的），一句理由；
2. 若涉及元模型：新增的类和属性名、放在哪一节；
3. 若涉及 MCP：新增或修改的工具名和语义；
4. 是否和第 2 项合并处理。
