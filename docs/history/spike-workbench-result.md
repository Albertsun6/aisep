# spike-workbench-result.md：Orchestrator.inc 能否做 AISEP 工作台骨架

日期：2026-11-19 · 执行人：Claude Code（执行会话）· 输入：`spike-workbench-checklist.md`、`workbench-reference.md`、`AISEP 架构原则.md`、`AISEP 方法论总纲（草案1）.md`

环境：macOS 27.2.1，**Apple Silicon（arm64）**，不是清单写的 Intel；Go 1.27.4（本次用 brew 安装）；Node 24.12.0；Claude Code 2.1.318；Orchestrator 桌面版 v0.15.3（stable）；源码 commit `0d322ae`（2026-11-19）。

## 1. 结论：通过（走 fork 路线，有条件）

可以选 Orchestrator.inc 做工作台骨架，但**只能 fork 改前端，插件这条路走不通**。

| 判断标准（清单 §5） | 结果 | 证据 |
|---|---|---|
| Mac 上跑得起来，Claude Code 作为 worker 正常工作 | ✅（arm64）/ ⚪ Intel 未测 | DMG 签名、公证都通过，启动正常；一个任务被拆给 2 个 Claude Code worker，各开一个 PR，最后都已合并 |
| 关口流程（批准 / 驳回 / 聊天）符合预期 | ✅（形态不同，见 §3） | 批准 → squash 合并；驳回 → worker 按意见修改，并把 main 合进自己的分支；问“为什么这么改”能得到一份结构化的自我说明 |
| 插件能加界面面板，或 fork 后加一个面板不超过一天 | ❌ 插件不行 / ✅ fork 可行 | 没有任何 UI 扩展点；fork 后加一个面板共改 16 个文件（全是前端），子代理约 20 分钟完成，测试通过，真机看过，热重载正常 |
| 不通过条件：前端封闭、要动大量核心文件 | 未触发 | 核心文件只动了 `Sidebar.tsx`，其余都是新增文件、生成文件和翻译文件 |
| 不通过条件：关口模型与人工把关有根本冲突 | 未触发，但有落差 | 关口的单位是 PR，批准靠聊天让 agent 合并，没有“批准记录”这种实体（见 §5 建议） |

## 2. 每节执行结果与关键证据

### §0 许可证与活跃度 ✅
- 许可证 **Apache-2.0**（`gh api repos/OrchestratorInc/agent-orchestrator`）。
- 规模：14,917 星，2,057 个 fork，约 4,315 次提交。清单里写的 14.6k / 4,120 已过时。
- 发布：最新正式版 **v0.15.3，2026-11-16**；nightly 每天发（最近一次 2026-11-18）。
- 近 30 天（10-20 起）**922 次提交**；当前开放 issue 464 个、PR 580 个。
- issue 响应：抽了 30 个近期 issue，13 个有维护者回复，**首次回复时间中位数约 0.8 小时**（最慢 1.3 小时）；另外 17 个暂时没有维护者回复。
- 治理：功能类 PR 必须先经核心团队批准（`CONTRIBUTING.md`）；云端控制面是闭源的，在私有仓库 `ao-control-plane`，不在这个仓库里。

### §1 安装试用 ✅
- **DMG**：`Orchestrator-darwin-arm64.dmg`，约 240MB。SHA-256 与 GitHub 记录的 digest 一致；Developer ID 签名，已公证，`spctl` 检查通过。装到 `/Applications/Agent Orchestrator.app`，包标识 `dev.agent-orchestrator.desktop`。
- 首次启动问是否自动更新，选了 Not now / Stable，以便锁定版本。
- 应用自带 `ao` CLI 和守护进程：`Contents/Resources/daemon/ao`，监听 `127.0.0.1:3001`，数据放在 `~/.ao/data`。
- **源码构建**：`go build ./cmd/ao` 通过；`frontend` 下 `npm ci` 通过。typecheck 要先在仓库根目录和 `packages/product-ui` 装依赖，之后 **0 错误**。
- 配 Claude Code 当 worker：AO 通过命令行 `claude` 的登录状态判断 agent 是否可用。本机命令行原先没登录，用户登录后 `ao agent ls` 显示 `authorized`。

### §2 完整流程 ✅
沙盒仓库：私有仓库 `github.com/Albertsun6/aisep-workbench-sandbox`（经用户同意新建）。

1. **下达任务**：用 `ao spawn --kind orchestrator` 给主代理下发“README 加 AISEP 简介 + 目录约定”。
2. **拆分与 worktree**：主代理约 1 分钟内拆成 **2 个 worker**（`-2` 写简介，`-3` 写目录约定）。每个 worker 有独立分支和独立 worktree，位置在 `~/.ao/data/worktrees/...`；主代理自己也有一个 worktree。两个 worker 各开一个 PR：#2、#1。主代理给 worker 的指令里写明了“不要合并、等关口批准”和预期的冲突顺序。
3. **看板**：泳道叫 **Building / Validating / In review / Ready**，和清单写的 Working / Needs you / In review / Ready to merge 不一样（后一套作为 `zone.*` 文案存在于源码，见下方“与清单不符”）。“Needs you”不是一条泳道，而是会话状态 `needs_input`，表现为侧栏红色图标加一条通知。截图：`spike-workbench/evidence/01-board.jpg`、`06-board-final.jpg`。
4. **批准与驳回**：
   - 批准 PR #2：worker 用 squash 合并，并回报合并提交 `720fb9c`，说明合并时锁定了 head、核对过 README。
   - 驳回 PR #1（要求补 `tests/`，并基于新 main 更新）：worker 补了提交。要 force push 时，被用户全局的 git-guardrails hook 拦下，于是弹出一张**结构化提问卡**（截图 `05-needs-you-question.jpg`），选“合并 main、不 force push”后继续。之后在界面里批准，PR 合并为 `90b71da`。最终 README 顺序正确。
   - 期间还自动跑了一个 **reviewer 代理**：通知里有“Review complete for PR #1 … approved it”（截图 `04-notifications.jpg`）。
5. **问“为什么这么改”**：worker 分三部分回答：措辞依据、位置理由、考虑过的替代方案。它主动标出哪半句是自己的推断、哪些是任务原文，并提出可以另开 PR 修改。原文见 `ao session history aisep-workbench-sandbox-2`。

**现在的“关口页”长什么样**（截图 `02-worker-chat-pr2.jpg`、`03-gate-inspector-pr2.jpg`），对照 AISEP 想要的关口页：

| AISEP 关口页要素 | Orchestrator.inc 现状 | 差距 |
|---|---|---|
| 顶部 AI 一段话摘要 | ✅ worker 结束时有结构化报告：PR 链接、改动原文、提交与分支、检查结果、注意事项 | 格式由 agent 自由发挥，不是固定模板 |
| 中间模型差异图 | ❌ 只有“N 个文件变更 + Review”代码 diff | 完全缺失，正是 AISEP 的差异点 |
| 校验结果与未决问题 | ⚠️ 右侧检查器有 PR 卡片：merge readiness、review status、CI、活动时间线 | 没有 CI 的仓库会一直停在 “Checking merge readiness”；没有“未决问题”区 |
| 批准 / 驳回 / 要求修改按钮 | ⚠️ **没有显式按钮**。批准 = 在聊天里让 agent 合并；“要求修改” = 发消息；agent 卡住时有结构化提问卡 | 人工批准不是一等实体，留痕只在聊天记录和 GitHub 合并记录里 |
| 工作台内与 AI 聊天 | ✅ 每个会话都有结构化聊天，可排队、可引导，还有 Reviewer 标签页 | 满足 |

### §3 插件能否加界面面板 ❌（插件不行）→ 必须 fork
方法：一个后台工作流，4 个只读 agent 并行读（文档站、仓库文档、插件契约、前端渲染层），汇总后再由 8 个“反驳型” agent 逐条找反例，**0 条被驳倒**。另加一轮异构评审（GPT 族），结论见本节末尾。

| 问题 | 结论 | 关键证据 |
|---|---|---|
| 插件能注册新的顶级页面 / 侧栏入口吗 | **不能** | npm 插件 API 已移除（`frontend/src/docs/content/plugins/authoring.mdx:3-8`）；“插件”现在指编译进 Go 守护进程的适配器（`plugins/index.mdx:6`）；`docs/stack.md:85` 写明 V1 不做完整插件框架；唯一的注册表 `backend/internal/adapters/registry.go:13-31` 只有 agent / issue-tracker 两种能力，没有 UI 字段；路由由 TanStack 在构建时生成（`frontend/vite.renderer.config.ts:280-285`）；侧栏写死在 `Sidebar.tsx` 里（3801 行） |
| 插件能在现有页面插入区块吗 | **不能** | 检查器视图是一个封闭的联合类型（`stores/ui-store.ts:83`、`SessionInspector.tsx:278`）；没有 slot 或贡献点 API |
| 插件能访问外部数据源（如本地 MCP Server）吗 | **部分** | 没有插件运行时。可行的旁路有：`ao preview http://localhost:…` 能在会话浏览器标签里显示本地服务，但不能调守护进程 API（`docs/architecture.md:1169-1186`）；Claude Code、Codex 等 agent 用各自的 MCP 配置；fork 后前端可以直接请求本机地址，CSP 已放行 `127.0.0.1` 和 `*.localhost`（`vite.renderer.config.ts:150-179`） |
| fork 后加一个面板要改哪些文件、多大工作量 | **只动前端，约半天以内** | 见 §4 实测 |

**异构评审**（GPT 族，`cursor-agent --model gpt-5.3-codex --mode ask`，只读，1 轮；原文见 `spike-workbench/evidence/gpt-review.txt`）：
- C1“不能加页面或侧栏”：**CONFIRMED**。
- C2“不能往现有页面插区块；preview / render 调不了守护进程 API”：**CONFIRMED**。它补了更硬的证据：`httpd/cors.go:177`、`controllers/conversation_render.go:31`、`artifact_files_test.go:307`，这些地方对来自预览 / 渲染来源的请求返回 403。
- C3“fork 只动前端”：**PARTIAL**，理由是主张里漏写了新增的组件和测试文件。→ 接受。§4 的改动清单已经包含这些文件，结论不变。
- 注：codex CLI 未登录（401），所以换用 cursor-agent 调 GPT 模型。

### §4 小规模改造实验 ✅（本地分支，未在 GitHub 建 fork）
- 分支：本地 `aisep/architecture-panel`。改动导出为 `spike-workbench/evidence/architecture-panel.patch`，统计见 `architecture-panel.stat.txt`：**16 个文件，+106 / -1**。
- 改动清单：
  - 新增 `routes/_shell.architecture.tsx`、`components/ArchitectureView.tsx`、`components/ArchitectureView.test.tsx`。
  - 修改 `components/Sidebar.tsx`、`components/Sidebar.test.tsx`。
  - 重新生成 `routeTree.gen.ts`。
  - 10 个语言文件 `i18n/*.json` 各加 2 个 key。
- 执行方式：给一个子代理一段 4 行的最简提示，让它“照仓库自己的 AGENTS.md / DESIGN.md 来做”，**约 15-20 分钟**完成。DESIGN.md 里的“Reference implementation map”直接把它指到了 `Sidebar.tsx` 和 `PageTopbar`。
- 验证：
  - typecheck 0 错误。
  - vitest 6 个文件、256 个测试全过，其中包括“禁止硬编码英文”和“所有语言 key 齐全”两个检查。
  - 用隔离的开发实例（独立数据目录和端口 3500，不碰 `~/.ao`）**真机渲染**，侧栏出现 Architecture，点进去显示占位文字（截图 `07-architecture-panel.jpg`）。
  - **热重载**：改 `en.json` 后 4 秒内界面更新，不用重启。测完已改回。

## 3. 与清单不符之处及调整

| 清单写的 | 实际情况 | 我的调整 |
|---|---|---|
| principles.md / methodology.md | 实际文件名是《AISEP 架构原则.md》《AISEP 方法论总纲（草案1）.md》 | 按内容对应读取；两份总纲取较新的“草案1” |
| spike-workbench-checklist.md | 开工时不存在 | 停下来问，用户补放后开工 |
| Intel 版本 | 本机是 Apple Silicon | 装 arm64 版；**Intel 未验证** |
| 14.6k 星 / 4,120 次提交 | 14,917 星 / 约 4,315 次提交 | 按实测记录 |
| docs.orchestrator.inc/plugins | 文档源文件在仓库 `frontend/src/docs/content/plugins/` 里 | 以仓库内文档为准（与站点同源） |
| “在 AISEP 仓库里”走流程 | AISEP 目录不是 git 仓库，而 PR 类泳道需要 GitHub | 经用户同意，新建私有沙盒仓库 |
| 看板泳道 Working / Needs you / In review / Ready to merge | 看板列是 Building / Validating / In review / Ready；“Needs you”是会话状态加通知 | 按实际记录（两套文案都在 `i18n/en.json:3289-3297`） |
| 在 Needs you 处做批准和驳回 | 界面上没有批准 / 驳回按钮；关口靠聊天消息 | 批准、驳回用消息完成：两次用 `ao send`，一次在界面输入框，效果相同 |
| “fork 仓库地址” | 在 GitHub 上 fork 公开仓库会产生一个公开仓库，这是对外动作，未获授权 | 改在本地分支做，交付 patch 文件；**没有 fork 地址** |
| 用 Claude Code 在 fork 上加面板 | — | 用的是本会话派出的 Claude Code 子代理，同样是 Claude Code，只给最简提示 |

## 4. 坑与解法

1. **命令行 `claude` 未登录**：AO 判断为 needs auth，worker 起不来。→ 用户本人在终端登录后恢复。（本会话的登录是桌面应用自己的，和命令行不通用。）
2. **全屏 Space 下点不到窗口**：AO 窗口在另一个 Space 时，后台点击被拒，截图也是旧画面。→ 用户切回普通桌面；切不了时改用 `ao` CLI 发消息，界面只用来看。
3. **点击后不知道接下来做什么**：项目卡片单击没反应，要点“展开会话”才出看板；聊天框写入有时确认不了。→ 用 `target: focused` 输入后再放大截图核对。
4. **没有 CI 的仓库，PR 面板永远停在 “Checking merge readiness”**，也就不出现合并入口。→ 用聊天让 worker 合并。AISEP 正式仓库应配 CI。
5. **用户全局的 `~/.claude` hook 也作用于 AO 拉起的 worker**：git-guardrails 拦了 force push。→ worker 自己弹出提问卡，选了“合并 main”。这其实是好事：AISEP 的门禁 hook 可以直接复用到 AO 的 worker 上。
6. **源码 typecheck 报 57 个错**：根目录和 `packages/product-ui` 没装依赖。→ 根目录 `npm ci` 加 `packages/product-ui` 下 `npm ci` 后为 0。AGENTS.md 没写这一步。
7. **`routeTree.gen.ts` 没有 npm 脚本能单独生成**，只有 Vite 插件在 dev 或 build 时产出。子代理是临时写脚本调用 `@tanstack/router-generator` 生成的。
8. **`npm run dev:warm` 第一次报 predev 失败**，重跑通过（没查到确切原因，判断为首轮缓存构建的偶发问题，未深究）。
9. **源码开发版需要 tmux**（打包版自带）。开发版启动时会弹窗提示安装；这次是**用户点的安装**，装上了 tmux 3.8，之后用户取消时安装已完成。是否卸载由用户决定（`brew uninstall tmux`）。
10. **硬编码文案与 i18n 测试冲突**：仓库测试禁止硬编码英文。→ 占位文字也要放进 10 个语言文件。

## 5. 对后续设计的启发（以下均为建议，供设计会话决策）

- **建议 1：路线定为“fork + 前端加面板”，不要等官方插件机制。** `docs/stack.md` 明确 V1 不做插件框架。我们的改动集中在新增文件，加上 `Sidebar.tsx` 的几行，rebase 成本可控。建议把改动收拢到 `routes/_shell.aisep.*` 和 `components/aisep/` 下，尽量少碰上游文件。
- **建议 2：AISEP 的“人工批准”要自己做成一等实体。** AO 的关口是“PR 加聊天”，批准只留在聊天记录和 GitHub merge 里，不满足原则五要求的“每个关口必须有人工批准记录”。可以在架构面板里加“批准 / 驳回 / 要求修改”按钮，写入模型仓库的批准记录（关口 ID、批准人、依据的模型版本），再通过 `ao send` 把决定通知 worker。`ao send` 已经证明可以充当这条通道。
- **建议 3：关口摘要模板化。** worker 的结束报告质量很高，但格式不固定。建议在 AISEP 仓库的 AGENTS.md 里规定关口摘要模板（做了什么 / 依据的标准和模型 / 不确定点 / 受影响元素），让 AO worker 照着写，架构面板再解析展示。
- **建议 4：模型差异图从 MCP Server 拉数据。** fork 后前端可以直接请求本机端口（CSP 已放行）。一期的 MCP Server 或 HTTP 服务可以同时服务编码代理和工作台，与 `workbench-reference.md §4` 的设计一致。
- **建议 5：门禁 hook 可以复用。** 用户的 `~/.claude` hook 对 AO 的 worker 生效，所以 AISEP 的“模型校验必过”之类的门禁可以写成 Claude Code hook，在 AO 环境里自动生效，不必改 AO。
- **建议 6：版本锁定加季度合并。** 上游 30 天 900 多次提交、每天发 nightly，fork 务必锁定 stable tag（本次基线是 v0.15.3 和 `0d322ae`）。另外功能类 PR 需要核心团队批准，想往上游贡献的话门槛不低。
- **建议 7：Electron 是单机桌面应用。** 若将来要多人协作，`workbench-reference.md §5` 里的风险依然成立；不过 AO 自带 mobile 和 cloud agents 两个方向，远程访问有现成路径可以评估。

## 6. 未完成项与原因

| 项 | 原因 |
|---|---|
| Intel Mac 验证 | 本机是 Apple Silicon，没有 Intel 机器 |
| GitHub 上的 fork 仓库地址 | 公开 fork 是对外动作，未获授权；以本地分支和 patch 交付。需要的话说一声我来建 |
| 界面里显式点击“批准 / 驳回”按钮 | 产品里不存在这种按钮，关口是聊天形态（见 §2） |
| 驳回在界面里完成 | 驳回那一步窗口在另一个 Space，点不到，改用 `ao send`，通道与界面相同 |
| `dev:warm` 首次失败的根因 | 重跑即通过，对结论没有影响，未深究 |

## 7. 产物与清理

- 目录 `spike-workbench/`（约 2.4GB）：
  - `agent-orchestrator/`：源码，带本地分支 `aisep/architecture-panel`。
  - `dl/`：DMG。
  - `devrun/`：开发实例的隔离数据。
  - `evidence/`：截图、patch、GPT 评审（`gpt-review.txt`；`codex-review.txt` 只是失败记录）。
  - `build.log`、`verify4.log`。
- 留在本机、需要你决定是否清理：
  - `/Applications/Agent Orchestrator.app` 及其数据 `~/.ao/`，里面有沙盒项目和会话，守护进程仍在运行。
  - 私有仓库 `Albertsun6/aisep-workbench-sandbox`，含两个已合并 PR 和残留的远程分支。
  - brew 装的 `go`、`tmux`。
