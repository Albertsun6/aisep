## 交接块：第 2 项 MCP Server 接口设计（2026-11-20）

**目标**
写出 MCP Server 的接口设计文档（ADR-008；规范 §8.3 说“接口的具体设计另写文档”）。一并定稿 ADR-013 里留下的三处：`model.diff`、`governance.record_approval` 的活动参数、`aisep:AgentActivity`。设计完成后，用真实客户端替换工作台里 PROVISIONAL 的 `AisepModelClient` 和 `FixtureClient`。

**已完成（可验证落点）**
- 第 1 项“AI 进行中”数据来源已落实：ADR-013；元模型规范升到 v0.4；原型 179/179；工作台读 AO 会话。`aisep-main` 已推送，合并提交是 `9cc70d6e0b`。
- 元模型原型就是 MCP 的语义基准：CLI 有 build/check/validate/findings/gate/query/impact/test 这几个子命令，接口约定写在 `CONTRACT.md`。

**当前状态**
- MCP Server 还没开始写，也没有接口文档。
- 工作台三个区域：“架构全景”“待批准关口”读本地假数据（`FixtureClient`）；“AI 进行中”读 AO 会话，“改动元素”一栏显示“暂不可用”，要等 `model.diff`。
- 待设计会话确认：AO 状态归并表（`STATUS_BUCKETS`，标了 PROPOSAL）。这件事和第 2 项无关，可以并行。

**下一步**
1. 读 §8.3 的语义契约表，再对照原型 CLI，按 ADR-008 列出两类客户端（工作台、编码代理）各自要用的操作。
2. 起草接口文档：每个工具的输入、输出、错误、是否只读，以及怎么映射到原型 CLI。重点：
   - `model.diff`：同时服务工作台的“AI 进行中”和关口页的差异图；
   - `record_approval` 的活动参数；
   - `model.remove` 的级联删除（§8.2，原型还没实现）。
3. 拿不准的设计取舍交给设计会话拍板，按总纲第 111 行的分工。
4. 定稿后：改规范 §6.7、§8.3 里标了“草案”的部分；把 `client.ts` 的接口改成正式版；写真实客户端。

**关键文件路径**
- `~/Desktop/AISEP/AISEP 第二步：元模型规范（草案）.md`：§8（写入层，含 §8.2 删除、§8.3 契约）、§6.6、§6.7、§9 影响分析、§10 校验分层、附录 B.3 和 C
- `~/Desktop/AISEP/decisions.md`：ADR-008、009、013
- `~/Desktop/AISEP/metamodel-prototype/CONTRACT.md`、`USAGE.md`、`tools/aisep.py`
- `~/Desktop/AISEP/workbench/frontend/src/renderer/aisep/data/`：`client.ts`、`fixture-client.ts`、`ao-sessions.ts`
- `~/Desktop/AISEP/brief-ai-activity-source.md`：ADR-013 的来龙去脉
- `~/Desktop/AISEP/handoff-workbench-after-fork.md`：工作台总交接

**已决取舍**
- MCP 不保存任何不在文件里的状态；所有写操作都是改 Turtle 文件、进 Git（§8.3）。
- 不提供任何“上报进行中状态”的写工具。运行态读编排器；改动元素由 `model.diff` 算出，起点是 merge-base（ADR-013）。
- `model.diff` v1 只比较已提交内容，前提是模型和代码在同一仓库、同一分支（附录 C）。
- 批准状态由批准记录推导，不能手填；批准记录放在模型仓库，不放在工作台（ADR-009）。
- 提交和 CI 只认 `gate`，`impact` 遇到有违规的模型会拒绝输出（G9、G10）。
- 执行代理暂时允许是 `arch:Stakeholder` 或 `prov:Agent`，因为没有加载 PROV 本体（附录 C）。要不要加载，可以在本项里定。
- 工作台的上游接触面固定：`Sidebar.tsx` 的 3 行、路由壳、`routeTree.gen.ts`、AO sessions 接口（`UPSTREAM.md`）。

**验证方式**
- 原型：`PY=~/Desktop/AISEP/spike-linked-archi/.venv/bin/python`，先 `cd ~/Desktop/AISEP/metamodel-prototype`，再跑 `$PY tools/aisep.py test`（基线 179/179，约 2.5 分钟）和 `$PY tools/aisep.py gate models/procurement/*.ttl`（基线 PASS，1 个已知 Warning）。
- 工作台：在 `frontend/` 下跑 `npm run typecheck`，以及 `npx vitest run --config vite.renderer.config.ts src/renderer/aisep src/renderer/components/Sidebar.test.tsx src/renderer/i18n src/renderer/router.test.tsx`（基线 10 个文件、292 个测试）。
- 改工作台前先建 worktree；依赖要在三处各跑一次 `npm ci`。开发实例必须隔离（`AO_PORT=3500` 加独立的数据目录），**绝不碰 `~/.ao`**。
- 推送前先问用户。`metamodel-prototype/` 和 AISEP 根目录不是 git 仓库，改之前先备份。

**会话命名**
- 本窗口收尾：`/rename AISEP-AI进行中落地`
- 新窗口开头：`/rename AISEP-MCP接口设计`
