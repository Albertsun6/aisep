## 交接块：AISEP 工作台 fork（第 4、5 步）

**目标**
执行设计会话的“追加任务：fork Orchestrator.inc 并建立升级友好的改造结构”中剩下的第 4、5 步，最后交付 `workbench-fork-result.md` 和一段不超过 200 字的口头摘要。

**已完成（可验证落点）**
- 第 1 步：`~/Desktop/AISEP/decisions.md` 中 ADR-006 已采纳，新增 ADR-008、ADR-009（ADR-010 是另一个会话加的，不要动）。
- 第 2 步：
  - 私有镜像 `github.com/Albertsun6/aisep-workbench`。
  - 本地完整克隆 `~/Desktop/AISEP/workbench/`，分支 `aisep-main` 基于 `v0.15.3`（`dec37bc`）。
  - `upstream` 的 push 地址已设为无效值。
  - `UPSTREAM.md` 已提交 `efa3f0a`，并已推送到 origin/aisep-main（用户批准）。
- 第 3 步：方案见 `~/Desktop/AISEP/workbench-fork-result.md` 的 §3，**用户已批准**。

**当前状态**
`workbench/` 停在 `aisep-main` 的 `efa3f0a`，工作区干净，还没有任何 AISEP 代码。

**下一步**
1. 第 4 步：按方案 §3.1–3.4 实施。**最先验证 i18n 独立命名空间这条路**：`aisep` 命名空间，`addResourceBundle` 注册，`useAisepT()` 包一层。走不通就按 §3.2 的退路，改为在 10 个语言文件末尾追加 key，并登记为冲突点。
2. 第 4 步的验证：
   - 在 `frontend` 下 `npm ci`；同时在仓库根目录和 `packages/product-ui` 也要 `npm ci`，否则 typecheck 会报 57 个错。
   - 跑 typecheck，跑 `aisep/` 的测试，再跑上游的 Sidebar 和 i18n 测试。
   - 用隔离的开发实例真机看面板，并测热重载。
3. 第 5 步：按 §3.5，用 `v0.15.4-nightly.202611182129` 在分支 `sync/<tag>` 上做演练，记录冲突数、耗时、是否由 AISEP 改动引起，写进 `UPSTREAM.md`。**不合回 aisep-main。**
4. 补全 `workbench-fork-result.md`：改动文件清单、演练基线数字、`UPSTREAM.md` 的位置、口头摘要。

**关键文件路径**
- 任务原文：设计会话发来的“追加任务”。新会话里需要你重新粘贴一次，或者以 `workbench-fork-result.md` §3 为准。
- `~/Desktop/AISEP/workbench-fork-result.md`：方案与结果。
- `~/Desktop/AISEP/workbench/UPSTREAM.md`
- `~/Desktop/AISEP/spike-workbench-result.md`：spike 的经验与坑（§4）。
- `~/Desktop/AISEP/spike-workbench/evidence/architecture-panel.patch`：spike 的面板实现，可作参考。
- `~/Desktop/AISEP/AISEP 第二步：元模型规范（草案）.md`：§3 IRI、§6.6 `approvalState`、§9 影响分析口径（假数据字段从这里取）。
- 仓库规则：`workbench/AGENTS.md`、`CLAUDE.md`、`DESIGN.md`、`.agents/skills/ao-desktop-dev/SKILL.md`。

**已决取舍**
- 用私有镜像，不在 GitHub 公开 fork。
- AISEP 代码全部放在 `frontend/src/renderer/aisep/`。上游接触面只有：`Sidebar.tsx` 的 3 处单行改动（`SidebarTopNavRow` 加 `export`、一行 import、一行挂载）、路由壳 `routes/_shell.aisep.$.tsx`、生成文件 `routeTree.gen.ts`。
- 假数据接口 `AisepModelClient` 有 `write`、`check`、`query`、`impact` 四个方法，标为 PROVISIONAL；字段取自元模型草案，不自创。
- 页面只做三个占位区域：架构全景、待批准关口、AI 进行中。不做真实渲染。

**验证方式与注意事项**
- 开发实例必须隔离：`AO_DATA_DIR`、`AO_RUN_FILE`、`AO_DEV_ELECTRON_DIR` 指向独立目录，端口用 3500 段，**绝不碰 `~/.ao`**。已安装的 Orchestrator 应用和它的守护进程（端口 3001）还在运行。
- 本机 `tmux` 已装好（3.8）。`dev:warm` 第一次可能报失败，重跑即可。
- **推送到 origin 前先问用户**（`efa3f0a` 已推送，之后每次推送都要单独问）。
- 执行规则同前：许可证判断、花钱、删除、选型分岔要停下来问；找不到标准就报告；不改 principles、methodology 和任务清单本身。
