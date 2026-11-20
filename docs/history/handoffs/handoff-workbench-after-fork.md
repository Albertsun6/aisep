## 交接块：AISEP 工作台 fork 收尾之后（2026-11-20）

**目标**
fork Orchestrator.inc 并建立升级友好改造结构的追加任务（第 1–5 步）已全部完成。新窗口从下面的“下一步”中选一项继续。

**已完成（可验证落点）**
- 第 4 步：`~/Desktop/AISEP/workbench/` 的 `aisep-main` 分支，提交 `989d4cf`，已推送。AISEP 代码全在 `frontend/src/renderer/aisep/`。
- 第 5 步：演练分支 `sync/v0.15.4-nightly.202611182129`（提交 `0b694e8`，补了 `tr` 语言），worktree 已删除，分支保留在 `workbench/` 仓库里。**未合回、未推送。**
- `UPSTREAM.md` 已更新：接触面清单、同步步骤、已知冲突点、同步记录。提交 `eb0b74c`，已推送。
- 结果文档 `~/Desktop/AISEP/workbench-fork-result.md`：第 4、5 步结果和口头摘要。

**当前状态**
- `aisep-main` 与 `origin/aisep-main` 一致（含 ADR-013 工作台部分），工作区干净；锁定版本仍是 `v0.15.3`。
- 没有正在运行的开发实例；已安装的 Orchestrator（端口 3001）没动过。
- 2026-11-20 已清理：演练 worktree `workbench-sync/`（用 `git worktree remove`，分支 `sync/v0.15.4-nightly.202611182129` 保留，`tr` 修复 `0b694e8` 还在）以及开发数据目录 `workbench-devrun/`、`workbench-devrun-sync/`。

**下一步（待选）**
1. ~~“AI 进行中”数据来源~~ 设计会话已拍板（ADR-013），2026-11-20 落实：规范 v0.4（§4/§6.6/§6.7/§8.3/B.3/C）；原型 179/179；工作台 `aisep-main` 合并提交 `9cc70d6e0b`（已推送），区域读 AO 会话，“改动元素”一栏待 `model.diff`。**待设计会话确认**：状态归并表（`aisep/data/ao-sessions.ts` 的 `STATUS_BUCKETS`，标 PROPOSAL）。简报：`brief-ai-activity-source.md`。
2. MCP Server 接口设计（ADR-008）。设计完成后，用真实客户端替换 PROVISIONAL 的 `AisepModelClient` 和 `FixtureClient`。
3. 上游发布下一个 stable 时：按 `UPSTREAM.md` 的“同步步骤”正式同步，重放 `0b694e8`（`tr.json`），合回 `aisep-main` 并更新锁定版本。
4. 可选：对第 4 步做一次跨模型评审（这次标注了“未经异构评审”）。

**关键文件路径**
- `~/Desktop/AISEP/workbench-fork-result.md`（§3 方案、§4 实施结果、§5 演练基线）
- `~/Desktop/AISEP/workbench/UPSTREAM.md`（HTML 注释里写了本机的环境坑）
- `~/Desktop/AISEP/workbench/frontend/src/renderer/aisep/data/client.ts`（接口，PROVISIONAL）
- `~/Desktop/AISEP/workbench-fork-evidence/`（3 张实机截图）
- `~/Desktop/AISEP/AISEP 第二步：元模型规范（草案）.md`（现为 v0.3：§3、§6.6、§8.3、§9）
- `~/Desktop/AISEP/decisions.md`（ADR-006、008、009）

**已决取舍**
- 私有镜像，不在 GitHub 上公开 fork。上游只拉不推。
- 上游接触面只有：`Sidebar.tsx` 的 3 行、路由壳 `_shell.aisep.$.tsx`、生成文件 `routeTree.gen.ts`。i18n 用独立命名空间 `aisep`，上游语言文件不改。
- AISEP 的语言表按上游 `AppLocale` 做类型约束：上游新增语言时 typecheck 会报错，这是有意设的门。
- nightly 只演练，不合回；只有 stable 才升级基线。
- 环境坑不靠改上游脚本解决（避免新增冲突点）：codesign 失败就重跑；开发实例按确切 PID 停止。

**验证方式与注意事项**
- 依赖要装三处：仓库根、`packages/product-ui`、`frontend` 各跑一次 `npm ci`。
- 在 `frontend/` 下运行：`npm run typecheck`；`npx vitest run --config vite.renderer.config.ts src/renderer/aisep src/renderer/components/Sidebar.test.tsx src/renderer/i18n src/renderer/router.test.tsx`（基线是 9 个文件 266 个测试，v0.15.3 上是 263 个）。
- 开发实例必须隔离：`AO_PORT=3500` 加上独立的 `AO_DATA_DIR`、`AO_RUN_FILE`、`AO_DEV_ELECTRON_DIR`，**绝不碰 `~/.ao`**。窗口在全屏 Space 时无法后台点击，需要请用户切到普通桌面。
- 推送前先问用户；删除前先问用户。
