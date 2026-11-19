# workbench-fork-result.md：fork Orchestrator.inc 与升级友好改造

状态：**第 1–5 步全部完成**（2026-11-20）。第 4 步已在 `aisep-main` 本地提交，第 5 步演练分支未合回；两个提交（`989d4cf`、`eb0b74c`）已于 2026-11-20 推送到 origin/aisep-main（用户批准）；演练分支未推送。

## 已完成

| 步骤 | 结果 |
|---|---|
| 1. decisions.md | ADR-006 已采纳，正文同步改成“私有镜像 + 独立目录 + fork 改前端”；新增 ADR-008（MCP Server）、ADR-009（批准记录是治理实体） |
| 2. Fork 与基线 | 私有仓库 `github.com/Albertsun6/aisep-workbench`，完整克隆在 `~/Desktop/AISEP/workbench/`；分支 `aisep-main` 基于 `v0.15.3`（`dec37bc`，与已安装的应用同一提交）；`upstream` 只拉不推（push 地址设成了无效值） |
| UPSTREAM.md | `~/Desktop/AISEP/workbench/UPSTREAM.md`，已提交 `efa3f0a`，已推送到 `origin/aisep-main` |

## 第 3 步：改造结构方案（已批准）

### 3.1 目录约定

| 位置 | 放什么 |
|---|---|
| `frontend/src/renderer/aisep/` | AISEP 全部前端代码：页面、组件、测试、文案、数据客户端、假数据 |
| `frontend/src/renderer/routes/_shell.aisep.$.tsx` | **唯一**一个放在上游目录里的路由文件，3 行，只把渲染转交给 `aisep/` |
| 仓库根 `UPSTREAM.md` | 同步记录 |

用 splat 路由（`/aisep/*`）的好处：以后 AISEP 加页面（架构、关口、追溯……）都在 `aisep/` 里用 TanStack 的路由能力或一个简单的分发组件处理，**不用再往 `routes/` 加文件**。

### 3.2 上次 spike 的 16 个文件怎么收敛

| spike 里的文件 | 新方案 | 类型 |
|---|---|---|
| `routes/_shell.architecture.tsx`（新增） | 换成 `routes/_shell.aisep.$.tsx`，只此一个，永久不变 | 上游目录里的新增文件，合并时不冲突 |
| `components/ArchitectureView.tsx`、`ArchitectureView.test.tsx`（新增） | 移到 `aisep/` | 收敛 |
| `components/Sidebar.tsx`（约 20 行改动） | **3 处单行改动**：① `function SidebarTopNavRow` 前加 `export`；② 加一行 import；③ 在 Artifacts 行后加一行 `<AisepSidebarItems isCollapsed={isCollapsed} />`。路由跳转和高亮判断都放进 AISEP 组件自己做 | **不可避免的核心改动**（已压到最小） |
| `components/Sidebar.test.tsx`（加 2 个测试） | 不改；AISEP 的测试放 `aisep/` | 收敛 |
| `routeTree.gen.ts`（生成文件） | 仍会变化；冲突时**重新生成，不手工合** | 不可避免，但不需要人解决 |
| 10 个 `i18n/*.json` | **目标是 0 处改动**：AISEP 用自己的 i18next 命名空间 `aisep`，文案放 `aisep/i18n/*.json`，在 `aisep/` 模块加载时用 `appI18n.addResourceBundle` 注册。上游的语言齐全测试只检查默认命名空间，硬编码检查只拦 JSX 里的字面英文，两个都不受影响 | 收敛，**实施时第一个验证** |

结果：从 16 个文件变成 **改上游 1 个文件（3 行）+ 1 个生成文件 + 1 个新增的路由壳**，其余全在 `aisep/`。

**风险与退路**：i18n 的类型声明把命名空间锁成了 `translation`。用 `aisep` 命名空间时，AISEP 要用自己的 `useAisepT()` 包一层，绕开类型限制。如果这条路走不通（测试或类型过不去），就退回 spike 的做法：在 10 个语言文件末尾追加带 `aisep.` 前缀的 key，并把这 10 个文件登记为已知冲突点。

### 3.3 构建、测试、热重载：不改任何上游脚本

- **构建 / 热重载**：`aisep/` 在 `src/renderer` 下，Vite 和 HMR 自动覆盖。
- **路由生成**：TanStack 插件扫描 `routes/` 时会自动收录那个路由壳。
- **测试**：vitest 默认收录 `**/*.test.tsx`，`aisep/` 下的测试随 `npm test` 一起跑；单跑用 `npx vitest run --config vite.renderer.config.ts src/renderer/aisep`。
- **类型检查**：`tsconfig.json` 已经包含 `src`，`npm run typecheck` 自动覆盖。
- **一个前提**：上游的“禁止硬编码英文”检查同样扫描 `aisep/`，所以 AISEP 的界面文字一律走 `useAisepT()`。

### 3.4 第 4 步的假数据与接口（按“标准优先”收紧）

- 在 `aisep/data/client.ts` 定义 `AisepModelClient` 接口，四个方法对应 ADR-008 的四项能力：`write`、`check`、`query`、`impact`。全部标注 **PROVISIONAL**：在 MCP Server 接口正式设计之前，它只是占位，不是标准。
- 字段名、取值**取自《元模型规范（草案）》，不自创**：
  - 元素 ID 用 §3 的 IRI 格式；
  - 关口状态用 §6.6 的 `approvalState` ∈ {Proposed, Approved, Rejected, Superseded}；
  - 影响分析结果按 §9 的口径，带 `dependency` 方向和跳数。
- 用 `FixtureClient` 读 `aisep/data/fixtures/*.json`。假数据沿用 spike 里的采购模型（供应商、报价审批、报价单……），这样以后切到真实 MCP Server 时可以直接对照。
- 三个占位区域：架构全景、待批准关口、AI 进行中。每个区域只显示 client 返回数据的条数和标题，不做图形渲染。

### 3.5 升级演练流程

1. `git fetch upstream --tags`，用选定的 tag（这次用 `v0.15.4-nightly.202611182129`）建分支 `sync/<tag>`。
2. 从 `aisep-main` 切出 `sync/<tag>` 后 `git merge --no-ff <tag>`，记下开始时间。
3. `git diff --name-only --diff-filter=U` 列出冲突文件，**逐个归类**：在 AISEP 接触面清单（`Sidebar.tsx`、`routeTree.gen.ts`、可能的 i18n）里的，算“AISEP 引起”；其余算“上游自身或环境”。
4. 解决冲突：`routeTree.gen.ts` 直接重新生成；`Sidebar.tsx` 按“3 处单行改动”重放。
5. 验证：在 `frontend` 下 `npm ci`、typecheck、`aisep/` 测试加上游 Sidebar 和 i18n 测试，再启动隔离的开发实例看面板和热重载。
6. 往 UPSTREAM.md 记录冲突数、耗时、归类和每个冲突点的解法。
7. **演练分支不合回 `aisep-main`**：nightly 不是 stable，基线不升；等 stable 发布再正式同步。

### 3.6 需要你确认的

1. 以上目录和挂载方案是否同意（尤其是 splat 路由，以及 i18n 走独立命名空间）。
2. 演练用 `v0.15.4-nightly.202611182129`，演练分支不合回 `aisep-main`。
3. UPSTREAM.md 的本地提交是否推送到私有仓库。

## 第 4 步：实施结果

提交：`aisep-main` 上的 `989d4cf`（已推送）。

**i18n 走独立命名空间：通过，不需要退路。** 上游语言文件一行没改。

改动文件清单（相对 `v0.15.3`）：

| 类别 | 文件 |
|---|---|
| 改上游文件（1 个，+3/−1） | `frontend/src/renderer/components/Sidebar.tsx`：`export` + 1 行 import + 1 行挂载 |
| 新增路由壳 | `frontend/src/renderer/routes/_shell.aisep.$.tsx`（4 行） |
| 生成文件 | `frontend/src/renderer/routeTree.gen.ts`（+21，纯新增） |
| `aisep/` 内（20 个） | `AisepRoot.tsx`（splat 分发）、`AisepWorkbenchPage.tsx`（三个占位区）、`AisepSidebarItems.tsx`；`i18n/index.ts`（`aisep` 命名空间、`addResourceBundle` 注册、`useAisepT()`）+ 9 个语言 json；`data/client.ts`（`AisepModelClient`：`write`/`check`/`query`/`impact`，PROVISIONAL）、`data/fixture-client.ts`、`data/fixtures/elements.json`、`impact-quotation.json`；4 个测试文件 |

假数据来源：元素取自 `metamodel-prototype/models/procurement/am4.ttl` 的 8 个元素（IRI 按 §3）；`approvalState` 用 §6.6 的四个取值；影响分析夹具是“改报价单”在 `depends` 模式下的 5 个元素，与规范 §9 的数字一致。

验证：

| 项 | 结果 |
|---|---|
| typecheck | 0 错误 |
| `aisep/` 测试 | 4 个文件 13 个测试全过 |
| aisep + 上游 Sidebar + i18n + router 测试 | 9 个文件 266 个全过（v0.15.3 上是 263 个） |
| 变异检查 | 删掉一个语言 key → typecheck 和测试都报错；在 aisep 的 JSX 里写死英文 → 上游的“禁止硬编码”测试拦住 |
| 全量 vitest | 808 个文件中 3 个失败（共 4 个测试），都与 AISEP 无关：时区、better-sqlite3 被编成 Electron ABI、负载下计时偶发（详见 UPSTREAM.md 注释） |
| 实机 | 隔离开发实例（端口 3500，数据在 `~/Desktop/AISEP/workbench-devrun/`，没碰 `~/.ao`），侧栏出现 AISEP，页面三区正常；改 `aisep/i18n/en.json` 后约 5 秒热更新。截图：`~/Desktop/AISEP/workbench-fork-evidence/01`、`02` |

与方案不同的地方：

1. **“AI 进行中”没有接数据。** 元模型草案里没有定义 AI 活动这个实体，按“找不到标准就报告”，这一区只显示“暂无数据来源”。真正的来源可能是 AO 自己的会话，而不是模型仓库，这件事需要设计会话决定。
2. **页面只用了 `query`。** 架构全景和待批准关口都来自同一条 SPARQL（`ELEMENTS_QUERY`），待批准 = `approvalState` 为 Proposed。`FixtureClient` 只认这一条查询，其他查询一律报错。
3. 图标用上游已有的 `Workflow`，没往上游 `app-icons.tsx` 里加新图标，否则会多一个接触点。

## 第 5 步：升级演练基线

演练分支 `sync/v0.15.4-nightly.202611182129`，在独立 worktree `~/Desktop/AISEP/workbench-sync/` 里做，**未合回 `aisep-main`**。

| 指标 | 数值 |
|---|---|
| 上游跨度 | 111 个提交，1301 个文件 |
| git 冲突 | **0** |
| 语义冲突 | **1**：上游新增语言 `tr`。AISEP 的语言表有类型约束，typecheck 当场报错，补一个 `tr.json` 就好（提交 `0b694e8`，只在演练分支上） |
| 由 AISEP 引起 | 这 1 个算是。它是 AISEP 有意设的门：不补的话应用启动时会崩，而 typecheck 能提前拦住 |
| `Sidebar.tsx` | 上游改了 35 行，与 AISEP 的 3 行不相邻，自动合并 |
| `routeTree.gen.ts` | 上游没改；重新生成后无差异 |
| 耗时 | 从合并到测试全绿约 8 分钟（npm ci 占约 5 分钟）；加上实机验证共约 33 分钟，多出来的时间都花在本机环境坑上（开发实例退不掉、iCloud 桌面导致 codesign 偶发失败） |
| 验证 | typecheck 0 错；9 个文件 266 个测试全过；实机页面和热重载正常（截图 `03`） |

记录写在 `~/Desktop/AISEP/workbench/UPSTREAM.md` 的“AISEP 接触面”“已知冲突点”“同步记录”三节（提交 `eb0b74c`，已推送）。

## 口头摘要

AISEP 工作台骨架已落在 aisep-main：代码全在 aisep/ 目录，对上游只改 Sidebar 的 3 行，外加一个路由壳和一个生成文件；文案走独立命名空间，上游语言文件没动。三个占位区的假数据字段取自元模型草案；“AI 进行中”草案未定义，暂时空着。nightly 演练：git 冲突 0 个，只有上游新增语言引起 1 个类型报错，补一个文件解决，约 8 分钟测试全绿。已推送。

<!-- 未经异构评审：本次结论只由可执行测试（含变异检查）和实机截图验证，没有做跨模型评审。 -->

