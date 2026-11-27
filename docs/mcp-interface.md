# AISEP MCP Server 接口设计

> 已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「文首状态与事实表」，原文未改。正文里的 F1–F19 指那张表。

---

## 1. 范围与已决前提

**范围**
- 一期交付物 MCP Server（ADR-008）的全部工具接口。
- 定稿 ADR-013 留下的三处：`model.diff`、`governance.record_approval` 的活动参数、`aisep:AgentActivity`。
- 工作台 `client.ts` 的正式接口，以及 `FixtureClient` 的替换路径。

**已决前提（本文不推翻；P1 由 ADR-031 修订）**

| # | 前提 | 出处 |
|---|---|---|
| P1 | MCP 不保存任何文件外状态；写操作 = 改 Turtle 文件，进 Git。唯一例外是服务端调用日志（§3.6）：本机运维记录，不是模型或治理状态，不参与任何判定 | §8.3、ADR-008、ADR-031 |
| P2 | 不提供上报"进行中"状态的写工具；运行态读编排器；改动元素由 `model.diff` 算 | ADR-013、§8.3 |
| P3 | `model.diff` base 缺省取 merge-base；前提是模型与代码同仓、同分支。~~v1 只比较已提交内容~~：设计会话 2026-11-20 拍板 Q6 时撤销这条限制（条件一），改为 head 也可以是某分支检出的工作区（§5.8）；规范 §8.3、附录 C 与 ADR-013 的对应文字见 §9 | §8.3、附录 C、ADR-013 |
| P4 | approvalState 只由合法批准记录推导，手填是 L1 违规 | §6.6、R3、G1 |
| P5 | 批准记录在模型仓库，工作台只展示和触发 | ADR-009 |
| P6 | 提交和 CI 只认 `gate` | G10、§10.1 |
| P7 | 模型有 L0–L2 违规时 impact 拒绝输出，除非显式 `allowInvalid` | G9、§9 |
| P8 | 作者只写限定关系；IRI 由写入层生成；slug 一经创建不改 | §8.1、§3 |
| P9 | 原型 `aisep.py` 是语义基准：MCP 的判定必须与 `aisep.py gate` 一致 | 交接块 |
| P10 | 工作台的上游接触面固定（`Sidebar.tsx` 3 行、路由壳、`routeTree.gen.ts`、AO sessions 接口） | 交接块、`UPSTREAM.md` |

**一条隐含前提，写明**：MCP 写工具**不是唯一写入途径**。人和代理照样可以直接编辑 `.ttl`，最后都由 pre-commit 和 CI 的 `gate` 兜底。写工具的价值只有三点：生成 IRI、拒绝不合法的写入、级联删除。所以服务器不能假设文件只被自己改过。

**不在本版**：视图与布局的写工具；改元素类型；diff 比较任意目录或 index（暂存区）内容（worktree 模式只按分支名定位工作区，见 §5.8）；跨仓库的模型差异；多仓库 AO 项目（`kind=workspace`）。

---

## 2. 两类客户端的操作清单

| 操作 | 工作台 | 编码代理 | 工具 | §8.3 行 |
|---|---|---|---|---|
| 架构全景：列元素和推导出的批准状态 | ✔ 读主分支 | 可选 | `model_query`（固定查询 `ELEMENTS_QUERY`） | `model.query` |
| 待批准关口：Proposed 元素、已有批准记录 | ✔ | — | `model_query` | `model.query` |
| AI 进行中：每个会话按分支算改动元素数（含未提交改动） | ✔ `head:{worktree: branch}`、`detail:"summary"` | — | `model_diff`（worktree 模式） | `model.diff` |
| 关口页：差异图 | ✔ `head:<commit>`、`detail:"items"`（只认已提交） | — | `model_diff`（Git 引用模式） | `model.diff` |
| 关口页：校验结论 | ✔ `ref=headCommit` | — | `model_gate` | **新增**（G10） |
| 关口页：影响面 | ✔ `ref=headCommit` | ✔ 改之前评估 | `model_impact` | `model.impact` |
| 触发批准（唯一写操作） | ✔ | ✘ 不列出（D1） | `governance_record_approval` | `governance.record_approval` |
| 新增元素、关系 | 一期不做 | ✔ | `model_add_element`、`model_add_relationship` | 同名 |
| 删除 | 一期不做 | ✔（先 `dryRun`） | `model_remove` | `model.remove` |
| 改名称、英文名、定义（IRI 不变） | 一期不做 | ✔ | `model_set_labels`（§5.10） | **新增**（§3"改名只改标签"的写入口） |
| 改其他属性（IRI、类型、端点不变） | 一期不做 | ✔ | `model_set_attributes`（§5.12） | **新增** |
| 写完快速自查 | — | ✔ | `model_check`（L0–L2） | `model.check` |
| L3、L4 单层诊断 | — | ✔ | `model_validate`、`model_findings` | `model.validate`、`model.findings` |
| 遗留违规清单（写前判定放过的旧违规） | ✔ "架构全景"违规计数徽标 | ✔ | `model_findings` 的 `openViolations`（§5.4） | `model.findings` |
| 提交前统一结论 | — | ✔ | `model_gate` | 新增 |
| 看自己分支改了什么（含未提交） | — | ✔ | `model_diff`（worktree 模式） | `model.diff` |

**工作台：只读 + 1 个写操作。编码代理：读写模型，不碰治理。**

工作台三个区域的调用：

| 区域 | 调用 | 读哪份内容 | 刷新时机 |
|---|---|---|---|
| 架构全景 | `model_query(ELEMENTS_QUERY)`；违规计数徽标：`model_findings` 的 `openViolations`（§5.4） | `repo`、`ref` 都不传，取服务器启动参数 `--repo`、`--main-branch`（§3.3） | 打开页面 |
| 待批准关口 | `model_query`（Proposed 元素 + 批准记录） | 同上：主分支 | 同上 |
| 待批准关口的"已在分支批准、待合并"标记 | 对"AI 进行中"里有 `branch` 的行，`model_query(ref=branch)` 读该分支上推导出的 `arch:approvalState`，与主分支比较（见下文"怎么查已有批准记录"） | 会话分支（Q2=A） | 同"AI 进行中" |
| AI 进行中 | 每个有 `branch` 的行：`model_diff({head: {worktree: branch}, detail:"summary"})`（缺省 worktree 模式，含未提交改动） | 该分支检出的工作区：merge-base 的 Git 对象 vs 工作区磁盘文件 | 行的分支头变化或定时轮询（工作区改动不改分支头） |
| 关口页（新路由，在 `aisep/` 内） | `model_diff({head: <commit>, detail:"items"})`、`model_gate(ref=head.commit)`、按需 `model_impact(ref=head.commit)` | 固定 `head.commit`（只认已提交） | 进入页面一次 |

批准提交写在会话分支上（Q2=A），合并前主分支推导出的状态仍是 Proposed。工作台**不**用 `record_approval` 的返回值改写主分支那一行，只按上表第三行从分支上推导出的状态得出"已批准、待合并"标记。这样显示的每个状态都来自所读那份内容里的批准记录（P4、ADR-009）。

**怎么查已有批准记录**（"待批准关口"用；口径与推导函数 `aisep/core.py` 的 `derive_approval_state`、`approval_problems` 一致）：

- **查询条件**：`model_query` 在所读那份内容上（主分支：`ref` 不传；分支标记：`ref=branch`）选 `?rec a/rdfs:subClassOf* aisep:ApprovalRecord`；按模型筛时按**被批准的对象**筛，即 `?rec aisep:approves ?x` 且 `?x arch:inModel <模型 IRI>` 或 `?x` 就是该模型本身，与推导一致（推导不看记录自己的 `arch:inModel`；按 `?rec arch:inModel` 筛会漏掉 inModel 指向别的模型、或没写 inModel 的记录，它们照样参与推导）。其余属性 `aisep:gate`、`aisep:decision`、`aisep:approvedBy`、`aisep:evidence`、`prov:generatedAtTime`、`aisep:activity` **全部用 `OPTIONAL`**，缺了某个属性的记录（多半不合法）照样列出；不按模型筛时 `aisep:approves` 也用 `OPTIONAL`。`aisep:approves`、`aisep:approvedBy` 都可多值，结果行是它们的组合，调用方按 `?rec` 聚合。记录可能在 `governance.ttl` 里，也可能在 `models/<slug>/governance/` 下一条一个文件（U2）；统一文件集合（§3.3，`aisep/gitio.py` 的 `model_files`）含子目录，查询不按文件区分。
- **分支上的"已批准、待合并"**：**不**用记录查询判定。用 `model_query(ref=branch)` 读该分支上推导出的 `arch:approvalState`（与 `ELEMENTS_QUERY` 同一选法，**另加 `arch:Model` 实例本身**：模型没有 `arch:inModel`，`ELEMENTS_QUERY` 选不到它，整模型批准会漏标），在分支上为 `arch:Approved`、在主分支上不是 `arch:Approved` 的对象，就标"已批准、待合并"。这个标记**只是提示**：批准之后分支上可能又有新提交，能不能合并以合并时校验（§5.9"合并时校验"）的结果为准。这样记录是否合法、decision 是否为 Approved、是不是该对象生效的最晚一条，都由推导函数决定，客户端不重算（分支上新增的 Rejected 记录、不合法记录、已被更晚记录覆盖的旧批准都不会被误标）。要列出分支新增了哪些记录，按 `?rec` 的 IRI 减去主分支上已有的记录，只作列表展示。
- **口径**：这样查出的是**全部**记录。哪条不合法以 `approval_problems` 的结果为准（记录 → 未通过的检查），它同时用于两处：推导忽略这些记录（并给 build Warning），L1 把它们报成 Violation（工作台经 `model_findings` 的 `openViolations` 可读到，§5.4）。`model_query` 本身不返回这个结果。推导只用合法记录：对象的状态取各关口合法记录中 `prov:generatedAtTime`（时区归一，无时区按 UTC）最晚的一条，**不分关口**（§6.6），把它的 `aisep:decision` 映射成状态（`aisep:DecisionApproved` → `arch:Approved`，`aisep:DecisionRejected` → `aisep:Rejected`，`aisep/core.py` 的 `DECISION_STATE`），不是 decision 本身；同一最晚时刻有决定不同的合法记录 → 歧义，状态留在 `arch:Proposed`；有合法的 `dcterms:isReplacedBy` → `aisep:Superseded`。批准记录、AI 活动、`arch:Stakeholder` 自身不推导 approvalState（口径 A，PR #29）。
- **用法**：工作台显示的状态只读推导出的 `arch:approvalState`（`ELEMENTS_QUERY`、`PENDING_QUERY`，§8），不用记录查询的结果自己重算；记录查询只用来列出"已有批准记录"（谁、哪个关口、批了什么、基于哪个提交）。

---

## 3. 服务器形态

### 3.1 实现语言与复用原型

已移至 [`docs/history/mcp-interface-mirrors.md`](history/mcp-interface-mirrors.md) 的「§3.1」，原文未改。

### 3.2 传输

| 客户端 | 传输 | 谁起进程 |
|---|---|---|
| 编码代理（Claude Code 等） | stdio | 代理按 `.mcp.json` 起，每个会话一个；cwd = 当前 worktree |
| 工作台 | **Streamable HTTP**（Q1=B，已拍板） | 开发期由开发脚本起一个常驻进程（与 AO daemon 同级），监听 `127.0.0.1` |

- 同一个程序：`aisep-mcp --transport stdio|http`。
- 选 HTTP 的唯一理由是 P10：stdio 要在 Electron 主进程起子进程，再经 preload 暴露给 renderer，要改上游的 `main.ts`、`preload.ts`。HTTP 由 renderer 直接 `fetch`，代码全部留在 `aisep/data/`。renderer 已经在用 `http://127.0.0.1` 访问 AO（`lib/api-client.ts`），注释说明 CSP 的 `connect-src` 放行了 http 127.0.0.1。
- **协议没有会话**（2026-07-28）：没有 `initialize`，没有 `Mcp-Session-Id`；每个 POST 自带 `_meta` 里的协议版本和客户端能力（客户端还可以带 clientInfo，键为 MCP Python SDK 的 `CLIENT_INFO_META_KEY`，即 `io.modelcontextprotocol/clientInfo`；调用日志把它记为调用方声明，§3.6），独立处理，返回 `application/json`。这就是 P1 在传输层的落实。调用日志不构成会话：它只追加，服务器从不读它。对 2025-11-25 客户端（如部分代理），SDK 的 `stateless_http` 模式照常服务。
- **安全面**：

| 项 | 做法 | 出处 |
|---|---|---|
| 绑定 | 只绑 `127.0.0.1` | MCP 规范 |
| Origin | 请求带 `Origin` 且不在白名单 → 403 | MCP 规范要求的只有这一条 |
| Host | 非 loopback → 拒绝 | SDK 的 DNS 重绑定防护，不是规范要求 |
| CORS | 精确白名单：`app://renderer`（打包后的 renderer）+ 开发期 Vite dev server 源；**永不**放 `*`、`null`（每个 `file://` 页和沙箱 iframe 都是 `null`）。应答 `OPTIONS` 预检，`Access-Control-Allow-Headers` 含 `Content-Type, Accept, MCP-Protocol-Version, Mcp-Method, Mcp-Name`。同 AO 的 `backend/internal/httpd/cors.go` | 不处理预检，renderer 的 `fetch` 会被浏览器拦下 |
| 白名单来源 | `--allow-origin`（可重复），同一份列表同时喂 CORS 中间件和 SDK 的 `transport_security.allowed_origins` | 两处不分叉 |
| 不带 Origin 的本机进程 | 放行（`curl` 等）。开发期不加令牌是**接受的风险**，与 AO daemon 同级；打包前必须定令牌（Q1=B 的附带条款） | 规范只说 SHOULD 认证 |

### 3.3 仓库与 worktree 的定位

- **每个工具都收可选参数 `repo`**：仓库内任意路径（主 checkout 或某个 worktree）。服务器用 `git -C <repo> rev-parse --show-toplevel` 规范化。
- `repo` 必须落在启动参数 `--allow-root`（可重复）之下，否则 `PATH_OUTSIDE_ROOT`。不依赖 MCP roots（客户端是否声明 roots 未核实，靠启动参数更可验证）。
- 不传 `repo`：取服务器的 `--repo`，再缺省取 cwd 所在仓库。编码代理一般不传；**工作台也不传**：v1 只支持单仓库项目（§1"不在本版"），工作台的服务器进程由开发脚本带 `--repo` 起。这样工作台不依赖 AO 的 `GET /api/v1/projects`，P10 的上游接触面不扩大。
- **调用日志写到哪里**（§3.6）只看启动参数，不看调用方传的 `repo`：第一个 `--allow-root` 在某个 Git 仓库里时取该仓库的 common dir，否则取 `--repo` 的 common dir；都取不到就不写、在 stderr 报警告。所以还没定位到仓库就被拒的调用（如 `PATH_OUTSIDE_ROOT`）也有地方记。
- 主分支：每次调用可传 `mainRef`；不传取启动参数 `--main-branch`，再缺省 `main`。不引入配置文件。
- **主分支解析顺序**：给的是短名 `<b>` 时，先找 `refs/remotes/<upstream>/<b>`（`upstream` 取 `<b>` 的跟踪远端，没有就 `origin`），有就用；没有才退回 `refs/heads/<b>`。理由：会话分支通常从 `origin/main` 切出，本地 `main` 落后时 merge-base 会落在更老的提交上，diff 会把队友已合入的改动算进本会话（评审实测复现）。AO 读 base 用的也是远端跟踪引用（`workspace.ts` 的 `baseRef`，如 `"origin/main"`）。输出的 `base.mainRef` 给出实际用的完整 ref 名。
- **读哪份内容**：

| 输入 | 读的内容 | 谁用 |
|---|---|---|
| 不传 `ref` | `repo` 这个 worktree 的磁盘文件（含未提交改动）。缺 `modules/` 或 `vendor/` 目录 → `MODULES_NOT_IN_REF`（目录在但内容不全仍可能报 `INTERNAL`） | 编码代理 |
| `ref: "<分支/标签/sha>"` | 该 commit 的快照：先 `git ls-tree <commit> -- models modules vendor` 查哪些路径存在，再 `git archive` 存在的那些，解到系统临时目录，调用结束删除。缺 `modules/` 或 `vendor/`（附录 C 的独立模型仓库）→ `MODULES_NOT_IN_REF`，不静默改用服务器自带模块 | 工作台、`record_approval` 的 gate |

- 快照里的 `modules/`、`vendor/` 也取自同一个 commit，所以"某 commit 上的 gate"可复现（vendor 8.4 MB，modules 0.9 MB；耗时在验收 T10 里量）。
- `model_diff` 不物化快照：Git 引用模式只读 Git 对象；worktree 模式 base 侧读 Git 对象，head 侧读**按分支名定位到的那个工作区**的 `models/**/*.ttl`（§5.8）。它不用上表"不传 `ref` 读 `repo` 磁盘文件"的规则：读谁的工作区由 `head.worktree` 的分支名决定，与调用方从哪个 worktree 调用无关。
- ref 安全：一律 `git rev-parse --verify --end-of-options <ref>^{commit}`；以 `-` 开头的 ref 直接 `INVALID_ARGUMENT`。
- **`repo` 指向检出里伪造的仓库目录**（SEC-3）：形似 git 目录的普通目录（有 `HEAD`、`objects/`、`refs/`、`config`）不会被当成仓库（每次 git 调用都带 `-c safe.bareRepository=explicit`）：只读工具 → `NOT_A_GIT_REPO`，写工具 → `NOT_A_WORKTREE`。启动带 `--allow-root` 时，定位出的工作区顶层还必须是它所在仓库**登记过的工作区**：主工作区，或 `git worktree list` 列出的某个 linked worktree（realpath 比较）；主工作区又不能落在 `--allow-root` 之下另一个仓库的工作区里。否则 `NOT_A_GIT_REPO`（`details.reason`：`unregistered-worktree` 或 `nested-repository`）。这样挡住的有：检出里伪造的 `.git` 目录（嵌套仓库）、指回伪仓库的 `gitdir:` 文件（多层嵌套）、伪造的 linked worktree 管理目录（`commondir` 指向真 `.git`）、子模块。被拒之前，服务器在它里面只跑过 `rev-parse` 和 `worktree list`，这两条命令不执行任何配置里的命令。放在主检出里、登记过的 linked worktree（如 `.claude/worktrees/*`）照常可用。`--allow-root` 设成更大的外层仓库时，里面的仓库都会被当成嵌套仓库拒绝，应把它收窄到要用的仓库。不带 `--allow-root` 时不做这项检查（同根目录校验）。另外每次 git 调用都带 `-c core.fsmonitor=false`，作第二道防线。被接受的仓库自己配置的过滤器、钩子照常生效（`git archive` 快照、`model_diff` 的 `git status`、`governance_record_approval` 的提交）。
- 多 worktree 不需要额外机制：同一仓库的 worktree 共享对象库和 refs，从哪个 worktree 调 `model_diff`（两种模式）、带 `ref` 的读取，结果都一样。
- **按分支名定位出的 worktree 也要过根目录校验**（第二轮评审 R2-2、R2-19）：Git 允许 linked worktree 放在 `--allow-root` 之外，有仓库写权限的进程还能改 `.git/worktrees/<n>/gitdir` 让登记路径指向任意目录。所以 `model_diff` 的 worktree 模式（§5.8 第 0 步）和 `record_approval`（§5.9 第 7 步）定位出 W 后再做两项校验：`realpath(W)` 必须落在某个 `--allow-root` 之下，否则 `PATH_OUTSIDE_ROOT`；`git -C W rev-parse --git-common-dir` 的真实路径必须等于 `repo` 的 common dir，否则 `WORKTREE_NOT_FOUND`。
- **工作区文件集合只有一个口径**（R2-16）：凡读工作区模型文件的地方（`model_check`/`validate`/`findings`/`gate` 不带 `ref` 时、写工具的基线、`model_diff` 的 worktree 模式、§5.9 的脏检查、仓库 pre-commit 钩子），文件集合一律 = `git ls-files -z -- models/`（已跟踪）∪ `git ls-files -z --others --exclude-standard -- models/`（未跟踪且未被忽略），只留 `.ttl`，含子目录里的文件（如每条批准记录一个文件的 `models/<slug>/governance/*.ttl`，§5.9 第 5 步，U2）；被忽略的文件和嵌套仓库里的文件不进入。原型缺省的 `glob(models/**/*.ttl, recursive=True)`（`aisep.py` 第 937 行）会读进被忽略文件、嵌套仓库，还会跟随目录链接，服务器不用它；钩子随之改用同一函数，否则 gate 校验的是一份不会被提交的内容。index 只用来确定文件集合，内容一律以磁盘为准。
- **安全打开**（R2-10、R2-12）：工作区里的每个模型文件都从 `realpath` 后的 worktree 根目录描述符出发，逐级 `openat(…, O_NOFOLLOW)` 打开（Python：`os.open(name, flags | os.O_NOFOLLOW, dir_fd=…)`），**任何一级**是符号链接都不跟随；打开后 `fstat` 必须是普通文件。读侧不满足 → 该文件记入解析失败（`error: "symlink"` 或 `"not-regular"`，FIFO、设备文件不会把读阻塞住）；写侧（写工具、`record_approval` 新建 `governance/` 下的记录文件）不满足 → `PATH_OUTSIDE_ROOT`。只检查最后一级不够：把 `models/<slug>` 目录换成指向外部的链接，`ls-files` 照样从 index 列出其中的路径，普通 `open()` 会顺着上级目录读写到工作区外（评审实测）。

### 3.4 并发

- 只读调用可并行，不加锁。读 Git 对象的调用（带 `ref`、`model_diff` 的 Git 引用模式）内容不可变，不受并发影响；读工作区的调用没有快照：`model_diff` 的 worktree 模式按 §5.8 第 4 步做前后核对；`model_check` 等诊断类读取不核对，读到保存中途的内容只会让这一次诊断不准，提交时的 gate 才是结论（G10）。
- 写调用（工作台进程、各代理进程是不同服务器进程，所以必须跨进程）：
  1. `flock` 锁**被写入的那个 worktree** 的 `$(git -C <worktree> rev-parse --git-dir)/aisep-write.lock`。`model_*` 写工具的目标就是 `repo`；`record_approval` 的目标是 `branch` 检出所在的 worktree（§5.9 第 7 步），**不是**调用方传的 `repo`。这样工作台对 worktree A 批准时，与 A 里代理的写入抢的是同一把锁。拿不到立即返回 `LOCKED`（可重试），不排队。不同 worktree 互不阻塞。进程死了锁自动释放。
  2. 写前哈希核对：读入时记下目标文件 sha256；rename 前再算一次，不等就 `CONFLICT`（可重试）。**这不是真正的比较并交换**（R2-3）：外部编辑器、普通 `git` 命令不遵守 `aisep-write.lock`，在"核对哈希"与 `rename` 之间写入的内容会被静默覆盖。这个窗口只有毫秒级，v1 接受，列为已知限制（§9 附录 C）；不采用原子交换（Linux `renameat2(RENAME_EXCHANGE)`、macOS `renamex_np(RENAME_SWAP)`）再核对换出旧文件的做法：平台相关，换回时还有同样的窗口。T13 加一例：在核对之后、rename 之前注入外部写入，断言结果如上所述（被覆盖），证明文档如实。
  3. 替换：写临时文件 → `fsync` → `rename`。多个文件先全部写成临时文件，再依次 rename；进程内中途失败用内存里的原字节恢复，恢复前先比对文件仍等于本次写入后的哈希，不等就跳过（保留现场），其余文件照常回滚完，最后报 `CONFLICT`，**不可重试**，`details.kept: true`，`details.keptFiles` 列出所有因此未回滚、停在半写入状态的文件，`details.file` 为其中第一个（PR #34；`aisep/writer.py` 回滚处）。
  4. **不是崩溃原子的**：进程在两次 rename 之间被杀（SIGKILL、宿主断开时杀子进程、断电），工作区会停在部分写入。服务器无状态，不做恢复日志（调用日志 §3.6 不用于恢复）；兜底是 pre-commit 的 gate（部分写入通常留下悬空引用，L1 报错）和 `git diff` 人工恢复。验收 T13 注入 SIGKILL 证明 gate 能拦住。
- 调用日志（§3.6）用仓库级锁 `<git-common-dir>/aisep/calls.lock`，与上面按 worktree 加的写锁分开：各 worktree 的服务器进程写同一个文件，拿锁后串行追加，阻塞等待而不报 `LOCKED`。
- `record_approval` 的提交另受 Git 自己的 `index.lock` 保护，拿不到报 `COMMIT_FAILED`；只在回滚完成、且输出含 `index.lock` 时可重试，回滚未完成（`orphanApproval`）不可重试（§7.2）。`git add --intent-to-add` 失败时记录若已被别的提交带走（taken），不报 `COMMIT_FAILED`，报 `CONFLICT`（`taken-by-other-commit`），不可重试。

### 3.5 无状态的落实

| 服务器进程里的东西 | 是不是"状态" |
|---|---|
| 每次调用重新解析文件或 Git 对象，构建 `Ctx` | 不是 |
| 快照临时目录 | 不是：调用结束即删 |
| 写锁文件 | 不是：只在一次写调用期间存在，在 `.git` 内，不进版本库 |
| 调用日志 `<git-common-dir>/aisep/calls.jsonl`（§3.6） | 是跨调用存在的本机文件，但不是模型或治理状态：在 `.git` 内，不进版本库，服务器从不读它，不参与任何判定（ADR-031） |
| 会话、游标、草稿、订阅、"进行中"标记 | **不存在** |

- v1 **不做跨调用缓存**。L0–L2 只要 0.07 秒（F1）；gate 要 5 秒（F2），关口页每次进入等一次，可接受。以后要加缓存，键只能是不可变的 Git 对象 ID，不改接口。
- 列表结果有硬上限，超了截断并返回 `truncated: true`：`model_query` 用 `limit`；`model_impact` 的 `items` 最多 500 条；`model_diff` 的 `items` 最多 2000 条（计数 `counts` 永远完整）。v1 不做续页。续页令牌可以把 commit 和偏移编码进去而保持无状态，等真有大仓库再加，不改现有字段。
- 输出体量参照 Claude Code 的阈值：结果文本超过 50,000 字符会被落盘，错误文本超过约 11,000 字符会被截成首尾各 5,000。`content` 摘要里的发现项行最多 200 行，其余只在 `structuredContent` 里。
- 可证伪断言：两次调用之间杀掉重启服务器，所有只读工具的结果**规范化后**相同（T4）：去掉 `summary.seconds` 等耗时字段；无序集合先排序；`model_query` 只在 SPARQL 带 `ORDER BY` 时承诺行序。

### 3.6 调用日志（ADR-031，A 层）

服务器对**被审计的调用**各追加一行 JSON 到本机文件，供事后排查诚实代理的误调用与被拒情况。它是 P1 的唯一例外（ADR-031），只是本机运维记录。

- **挂钩点**：`aisep/server.py` 的 `on_call_tool`。被审计的工具：五个 `model_*` 写工具、`model_apply_action`（`dryRun` 也记）、`governance_record_approval`。成功与被拒都记：参数校验（`INVALID_ARGUMENT`）、guard（`PRECONDITION_FAILED`）、删除两段式（`PLAN_REQUIRED`、`PLAN_STALE`）、`PATH_OUTSIDE_ROOT` 等，结果值即 §7.2 的错误码。调用名属于审计集合、但当前画像没有列出的（如 `agent` 画像调用 `governance_record_approval`），`on_call_tool` 仍以 JSON-RPC「Unknown tool」拒绝，日志结果记 `UNKNOWN_TOOL`：这是日志专用值，不是错误码，不进 §7.2。只读工具不记，既不在审计集合、也不在画像里的未知工具名也不记，所以 T4 照样成立。
- **位置**：`<git-common-dir>/aisep/calls.jsonl`，按 §3.3 所述只由启动参数决定（第一个 `--allow-root` 所在仓库 → `--repo` → 都没有则不写、启动时与每次被审计调用时在 stderr 警告）；不用 cwd 兜底。不进工作区、不进模型图（`model_query` 查不到）、不推远端，不做轮转。
- **并发**：追加前拿仓库级 `flock`（`<git-common-dir>/aisep/calls.lock`），再用 `O_APPEND` 一次写入一整行。
- **字段**：每行 `{"measured": {…}, "declared": {…}}`。
  - `measured`（服务端测得）：`time`（UTC）、`server`（`pid`、`profile`、`transport`、`allowRoots`）、`tool`、`outcome`（`ok`、错误码或 `UNKNOWN_TOOL`）、`dryRun`、`argsSha256`（参数按键排序的紧凑 JSON 的 sha256）、结构性字段 `targetIri`（参数 `iri`；新增元素、关系成功时取生成的 IRI）与 `actionId`、`action`（动作的 `owl:versionInfo` 与 `definitionDigest`，找到定义后才有）、`worktree`（目标工作区的 `path`、`branch`、`head`，定位到工作区后才有）、`files`（每个被写文件的 `path`、`sha256Before`、`sha256After`，只在真的写了文件时有；新建文件的 `sha256Before` 为 `null`）、`durationMs`；`governance_record_approval` 成功时另有 `commit` 与 `activityIri`，只用来关联。不记标签、定义这类正文。
  - `declared`（调用方声明）：`clientInfo`（stdio 取 `initialize` 的；HTTP 取每次请求 `params._meta` 的，§3.2）、`governance_record_approval` 的 `activity.agent` 与 `activity.sessionRef`。声明字段只用来关联，任何判定都不能用；调用方的声明值不进 `measured`。
- **失败策略**：fail-open。日志写不进去（目录只读、磁盘满等）时工具结果逐字节不变，只在 stderr 警告。
- **威胁模型**：只保证服务进程按仓库里经过评审的代码诚实运行时，它经手的每次被审计调用都留一行。**不防代理篡改**：同一 macOS 用户下的代理能改服务端代码、换解释器、直接删改日志或绕过 MCP 改文件；不做哈希链（没有外部锚点挡不住重算）。日志不证明调用方身份，不代替 AgentActivity、`AISEP-Session` trailer 或批准记录。服务端写完文件、还没写日志时进程崩溃，这一行会丢。防篡改的 B 层及其触发条件见 ADR-031 决策第 7 款。

---

## 4. 工具总表

**命名**：线上名一律小写加下划线（`model_diff`）。Anthropic API 的工具名不允许点号；MCP 规范虽允许点号，已有客户端会过滤带点的名字（三份草案各自查证，出处见附录 B）。规范 §8.3 的点号名保留为逻辑名，一一对应（§9 改文）。

**annotations**：除 `governance_record_approval` 外 `openWorldHint: false`（只操作本地仓库；`model_query` 拒绝 `SERVICE`，见 F6）。`governance_record_approval` 为 `true`：它会跑仓库里任意的 pre-commit 钩子，钩子可能访问外部。annotations 只是提示，不代替服务端校验。

| 工具（线上名） | §8.3 逻辑名 | readOnly | destructive | idempotent | 原型 CLI | 实现 |
|---|---|---|---|---|---|---|
| `model_query` | `model.query` | true | — | true | `query` | 复用；补结构化输出、限行、超时、拒绝 `SERVICE` |
| `model_check` | `model.check` | true | — | true | `check` | 复用 |
| `model_validate` | `model.validate` | true | — | true | `validate` | 复用 |
| `model_findings` | `model.findings` | true | — | true | `findings` | 复用；新增 `openViolations`（当前 L0–L2 全部违规，§5.4） |
| `model_gate` | `model.gate`（**新增**） | true | — | true | `gate` | 复用 |
| `model_impact` | `model.impact` | true | — | true | `impact` | 复用；路径结构化；未知元素报错（有意变更） |
| `model_diff` | `model.diff` | true | — | true（Git 引用模式结果只随 commit 变；worktree 模式结果随工作区内容变，但调用本身不改任何东西） | 无 | **新实现**；`head` 可为 Git 引用或 `{worktree: <分支名>}`（§5.8） |
| `model_branches` | 无（工作台专用，不对应规范 §8.3 的操作） | true | — | true（结果只随引用变；调用本身不改任何东西，不 fetch） | 无 | **新实现**：列本地分支及其 Git 事实，供工作台进关口页（§5.11） |
| `model_add_element` | `model.add_element` | false | false | true（同参数重放 = 无变化） | 无 | **新实现**（校验复用 `check`） |
| `model_add_relationship` | `model.add_relationship` | false | false | true（同类型同端点 = 返回已有） | 无 | **新实现**（校验复用 `check`） |
| `model_remove` | `model.remove` | false | **true** | true（带 `planDigest` 重放、目标已不在 → 成功，`changed:false, alreadyAbsent:true`，同 add 的 `changed:false`） | 无（§8.2 未原型化） | **新实现** |
| `model_set_labels` | `model.set_labels`（**新增**） | false | **true**（覆盖原值，不是追加；原值留在 Git 历史里） | true（同参数重放 = 无变化） | 无 | **新实现**（校验复用 `check`） |
| `model_set_attributes` | `model.set_attributes`（**新增**） | false | **true**（按谓词整体替换原值；原值留在 Git 历史里） | true（同参数重放 = 无变化） | 无 | **新实现**（校验复用 `check`，§5.12） |
| `model_list_actions` | 无（规范外） | true | — | true | 无 | **新实现**：列动作目录（§5.13） |
| `model_apply_action` | 无（规范外） | false | **true**（目录里有含删除步骤的动作；按目录内容逐个变就会让 `tools/list` 随数据变，所以固定按最坏情形标） | true（各步互不覆盖的动作同参数重放 = 无变化，边界见 §5.14） | 无 | **新实现**：把现有写工具的计划函数按目录组合，交给一次 §5.1 写入（§5.14） |
| `governance_record_approval` | `governance.record_approval` | false | false | true（完全重复的请求不写；去重键含调用方给的 `headCommit`，重放稳定） | 无 | **新实现**（gate 复用） |

**画像**：启动参数 `--profile agent|workbench|all`，决定 `tools/list` 列出哪些工具。按进程定，不按连接变（满足 2026-07-28"`tools/list` 不得随连接变化"）。

| 画像 | 列出 |
|---|---|
| `agent` | 除 `governance_record_approval`、`model_branches` 外全部 |
| `workbench` | `model_query`、`model_findings`、`model_gate`、`model_impact`、`model_diff`、`model_branches`、`governance_record_approval` |
| `all` | 全部（测试用） |

画像**不是安全边界**：代理可以直接手写 Turtle 伪造批准记录，真正的约束是代码评审和分支保护。画像只防"顺手调用"。

**加了五个规范外的工具**：`model_gate`、`model_set_labels`、`model_set_attributes`、`model_list_actions`、`model_apply_action`。`model_gate` 的理由：G10 规定提交和 CI 只认 gate，关口页和代理提交前自检都要这个结论；§8.3 漏列了它。`model_set_labels`：规范 §3 规定"改名只改标签"，§8.3 却没有对应的写工具；用户在另一会话拍板加入（2026-11-20，合并时并入，§5.10）。其他辅助工具（列元素、查词汇）一期不加，见 D4。`model_set_attributes`：补上非标签属性的修改入口（Albert 2026-11-25 放行阶段 A 时随之加入，§5.12）。`model_list_actions`、`model_apply_action`：动作目录的两个固定入口，把几次写工具调用合成一次写入（§5.13、§5.14）。

---

## 5. 工具详述

### 5.0 公共约定

**公共输入**

| 字段 | 类型 | 说明 |
|---|---|---|
| `repo` | string，绝对路径 | 可省，见 §3.3 |
| `ref` | string | 只读工具可选（`model_diff` 用 `head`/`base`）；写工具**不接受** |
| `mainRef` | string | 只有 `model_diff` 和 `record_approval` 用 |

**IRI 输入**：接受完整 IRI，也接受原型 `short()` 打印的 `slug:local`（如 `procurement:quotation`），展开规则同原型 `expand()`。展开结果必须是合法 IRI（含空格、`<>{}` 等字符的不算），否则 `INVALID_ARGUMENT`；IRI 先校验再用，不拼进 SPARQL 文本。**输出**一律完整 IRI。

**模型名 `model`**（写工具、四个只读工具、`governance_record_approval` 共用一个口径）：裸 slug（`^[A-Za-z0-9][A-Za-z0-9_-]*$`）或完整模型 IRI（末尾 `/` 可有可无）。其他形状（`procurement/`、`./procurement`、`../x`、`…/procurement/../x/`）→ `INVALID_ARGUMENT`，`details.rejectedFields` 含 `model`，不可重试；形状合法但没有 `models/<slug>/`（含大小写不符）→ `MODEL_NOT_FOUND`。

**公共输出**（`structuredContent`；每个工具声明 `outputSchema`）

```jsonc
{
  "source": { "repo": "/abs/path", "ref": "main" | null, "commit": "40hex" | null },
  "findings": [ /* §7.3 Finding */ ],
  // …各工具自己的字段
}
```

**`outputSchema` 是成功与错误两种形状的联合**：`oneOf: [<成功形状>, {type: object, required: ["error"], properties: {error: <ErrorEnvelope>}}]`。规范要求有 `outputSchema` 时 `structuredContent` 必须符合它；TS SDK v1 客户端在 `isError: true` 时照样校验，不符会抛 `InvalidParams`，§7.1 的 `code`、`hint` 就丢了。验收 T34 用 TS SDK 的 `Client.callTool` 对每个错误码各验一例。

`content[0].text` 放同一结果的简短中文摘要，加原型 CLI 格式的发现项行（代理直接读得懂）。文本内容里的控制字符与行分隔符按 `\n`、`\uXXXX` 转义（模型文本不能在摘要里伪造独立的一行），`structuredContent` 保持原文。**有意偏离**规范的 SHOULD（"同时把 structuredContent 序列化成 JSON 放进 TextContent"）：代理读摘要比读 JSON 省 token，客户端都能读 `structuredContent`。体量上限见 §3.5。

### 5.1 写入流程（五个 `model_*` 写工具共用）

1. 定位 `repo`；不是 worktree（裸仓库）→ `NOT_A_WORKTREE`。加锁（拿不到 → `LOCKED`）。
2. 按 §3.3 的统一文件集合和安全打开读当前工作区内容，记下每个文件的 sha256。
3. **基线**：在当前文件上跑 L0–L2，得到问题集合 B。L0 不过 → `PARSE_FAILED`（文件已坏，先修）。
4. 在内存里生成新文本，跑 L0–L2，得到集合 C。
5. **判定**：`C \ B` 里有 Violation → 拒绝，`WRITE_REJECTED`，附新增的违规，**磁盘一个字节不改**。比较按**问题实例**，身份键 = `(severity, layer, rule, focus, message)`，且按多重集计数（同一键在 C 里比 B 多出的次数算新增）。**不能**用展示去重键 `(severity, layer, message)`：基线里对象 A 已有一条通用措辞的错误，这次写入让对象 B 出现同样文字的错误，展示键会把它当旧问题放过。`file` 字段不进键；但原型有几条 L1 消息正文带文件路径（`aisep.py` 第 523、586、632 行的 `rel(f)`），这些规则在文件改名后会被视为新违规，方向偏保守，接受（写工具不搬文件，影响很小）（R2-20）。**实例键要求 `focus` 非空**（R2-6）：`focus` 为 null 时，"一次写入消除对象 A 的旧违规、同时给对象 B 引入同文案的新违规"会让多重集计数不变，新违规被当成旧的放过。所以写工具上线前，原型里所有 L0–L2 Violation 调用点都必须经 `Ctx.add` 给出 `focus`（T7 普查断言）；在此之前，`focus` 为 null 的 Violation 键里补上 `file`。基线已有的违规不阻塞（否则一个历史违规就让所有写入卡死），在结果的 `preexistingViolations` 里报数量。
   **标记 `preexisting`**（Q6 条件二）：不论接受还是拒绝，结果里候选图 C 的每条发现项都带 `preexisting`（§7.3）：按同一实例键的多重集，B 里已有的那几次计为 `true`，多出的计为 `false`。接受时 `findings` 里的 Violation 必然全是 `true`；拒绝时 `details.findings` 列出 C 的全部 Violation，`preexisting:false` 的就是本次新增、导致拒绝的那些，`true` 的是遗留违规，代理能一眼分清"我造成的"和"本来就有的"。遗留违规的完整清单另由 `model_findings` 的 `openViolations` 给出（§5.4），工作台"架构全景"显示计数徽标。
   **遗留违规从哪来**：pre-commit 的 gate 遇任何违规（不分新旧）都拦提交，所以正常流程下主分支和已提交内容里没有违规；已提交内容里的遗留违规只在两种情形出现：有人 `git commit --no-verify` 绕过钩子，或规则升级（新版本模块让原来合法的内容变成违规）。另外，写工具的基线读的是工作区，同一工作区里人或代理直接编辑 Turtle 造成、尚未提交的违规也会算进 B、标 `preexisting:true`；它们到提交时照样被 gate 拦下。写前只拒新增违规，是为了这两种情形下写工具不被一条无关的旧违规卡死，不是放宽提交门槛。
6. **图等价断言（写盘前）**：在内存里解析候选文本，得到的图必须等于"旧图 − 计划删除的三元组 + 计划新增的三元组"。不等 → `EDIT_UNSAFE`，不写（例如作者把两个主语写在一个块里）。磁盘上只会出现通过断言的内容。
7. `dryRun: true` 到此返回，不写。
8. 落盘（§3.4 的比较并交换 + 替换）。
9. **不 `git add`、不提交**（§8.3 改文；Q6=A 已拍板，第①项）。结果列出改动的文件和前后 sha256，由代理随代码一起提交，pre-commit 的 gate 把关。提交前这些改动对工作台也看得见：`model_diff` 的 worktree 模式直接比较工作区（§5.8，Q6 条件一）。
10. 解锁。

**为什么写前不跑 L3**：L3 要 5 秒（F2），§8.3 写的就是 L1/L2；L3 由 pre-commit 的 gate 负责。

**文本怎么改（新实现）**：按主语块做文本编辑，**不整文件重新序列化**（例子文件注释很多，重序列化会冲掉注释、放大 diff 噪声）。
- 新增：在目标文件末尾追加一个主语块，格式同 `models/procurement`（`:slug a T ;` 换行缩进 4 格）。前缀用文件里已有的；缺的插到最后一条 `@prefix` 之后。
- 删除、摘除：一个小型 Turtle 词法器（识别字符串、IRI、注释，按顶层 `.` 切主语块）定位受影响的块，只重写这些块；其他块逐字节保留。
- 目标文件不存在时新建，写标准前缀头。

**写到哪个文件**（可选参数 `file` 覆盖，必须是 `models/<slug>/` 下的 `.ttl`）：

| 写什么 | 缺省文件 |
|---|---|
| 元素 | 按**声明该类型的模块目录**（不是按命名空间，F15）：`am4`→`am4.ttl`，`bpmn`→`bpmn.ttl`，`uml`→`uml.ttl`，`ddd`→`ddd.ttl`，`ext-code`→`code.ttl`，`ext-verification`→`verification.ttl`，其余（`ext-governance`、`aisep-core`、上游 core 的类，如 `arch:Stakeholder`）→`governance.ttl`；模型内的特化类跟随父类 |
| 关系 | 两端在同一文件 → 该文件；否则写**不在 `am4.ttl` 的那一端**所在的文件；两端都不在 `am4.ttl` → 源端所在文件 |
| 批准记录、AI 活动 | 每条记录新建一个文件 `models/<slug>/governance/<记录本地名>.ttl`，同次新建的活动写在同一文件（§5.9 第 5 步，U2）；已有 `governance.ttl` 里的记录不搬迁 |

- **"声明该类型的模块"怎么判定**：Language 类按命名空间即可（原型 `owner` 第 189–196 行、`Ctx.module_of` 第 266–272 行）。`aisep#` 由 aisep-core 声明 `ownsNamespace`，却被 `ext-code`、`ext-verification`、`ext-governance` 共用（F15），`owner()` 会把这些类都归到 aisep-core；所以对 `aisep#` 的类，按"哪个模块的 `aisep:loads` 文件里声明了这个类"判定（原型按文件分图载入本体，第 220–221 行，图名即文件）。原型没有现成函数，要新写一个小函数。
- **关系规则的核对**（合并时用 `models/procurement/` 的 27 个关系逐一核对，全部符合）：`rel-quoteApproval-realizes-procurementSubdomain`、`rel-procurementSystem-composedOf-quotationBC` 在 `ddd.ttl`，`rel-reqTwoLevelApproval-aggregates-acOver100kSecondLevel` 在 `verification.ttl`，refines 在 `uml.ttl`/`bpmn.ttl`，Implementation 在 `code.ttl`。本稿原写"源端元素所在的文件"，对上面前 3 条不符（源端在 `am4.ttl`），改用另一会话草案的规则。
- 新建模型目录（`arch:Model` 本身）不在 §8.3 范围内，v1 手工建；目标模型目录不存在 → `MODEL_NOT_FOUND`。

### 5.2 `model_add_element`

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | ✔ | 模型 IRI 或 slug（`procurement`），口径见 §5.0 |
| `type` | ✔ | 类 IRI 或前缀名；必须是已加载模块的具体类，或模型里的单父类特化（R1、G6）。批准记录、AI 活动（`aisep:ApprovalRecord`、`aisep:AgentActivity` 及其子类）→ `PROTECTED_RESOURCE` |
| `prefLabel` | ✔ | 写成 `skos:prefLabel "…"@zh`。prefLabel/altLabel 不含控制字符、换行与 U+2028/2029，≤200 字符；definition 只允许 `\n`（`\r\n`、`\t` 都拒绝），≤4000 字符；违反 → `INVALID_ARGUMENT` |
| `altLabel` | — | 写成 `skos:altLabel "…"@en` |
| `slug` | 条件 | `^[A-Za-z][A-Za-z0-9]*$`（允许大写开头，例子里已有 UML 类 `QuotationEntity`）。不给时由 `altLabel` 转 camelCase；两者都没有 → `INVALID_ARGUMENT`（不自动拼音） |
| `definition` | — | `skos:definition "…"@zh` |
| `attributes` | — | `[{predicate, value: {iri} \| {value, datatype?, lang?}}]`，用于 `aisep:priority`、`aisep:path` 这类属性。合法与否由候选图上的 L1 闭世界规则（G7）判定，不另写白名单。不能含 `rdf:type`（类型只由 `type` 给出）、`arch:inModel`（所属模型由 `model` 给出）、`arch:source`、`arch:target`（关系端点只由 `model_add_relationship` 写入）、`arch:inView`（视图成员关系归视图，视图写工具不在本版，§1），违反 → `INVALID_ARGUMENT`，不留给 L1 兜底；与 §5.12 的不接受谓词同口径、给同一条拒绝理由（服务器里只有一份清单），只有标签三谓词例外：写 skos:prefLabel / altLabel / definition 时受同样的标签约束；不合法的 IRI、语言标签或值 → `INVALID_ARGUMENT`。值的形状另有五条，违反也是 `INVALID_ARGUMENT`：字面量不含 C0/C1 控制字符（制表、换行、回车除外）与 U+2028/2029；`lang` 与 `datatype` 不能同时给；`lang` 不能为空（给了 `lang` 键就不能是空串或 null）；`datatype` 不能为空（给了 `datatype` 键就不能是空串或 null，不会退成普通字面量）；`predicate`、`iri`、`datatype` 不能用 `_:` 开头的空白节点名（否则会被展开成 IRI） |
| `file`、`dryRun` | — | §5.1 |

**IRI**：`{model}{slug}`。
- 已存在且三元组完全相同 → 成功，`changed: false`（幂等，代理超时重试安全）。
- 已存在但内容不同 → `IRI_EXISTS`，`details.existing` 给出现有类型和名称。元素的 slug 就是它的身份，**不自动加 `-2`**。

**输出**：`{ iri, file, changed, turtle, filesChanged: [{path, sha256Before, sha256After}], findings, preexistingViolations }`。`turtle` 是实际写入的片段，代理不用再读文件。`findings` 里每条带 `preexisting`（§5.1 第 5 步）。

**错误**：`MODEL_NOT_FOUND`、`UNKNOWN_TYPE`（`details.candidates` 给名字相近的最多 5 个类）、`ABSTRACT_TYPE`、`INVALID_ARGUMENT`、`IRI_EXISTS`、`WRITE_REJECTED`、`PARSE_FAILED`、`EDIT_UNSAFE`、`LOCKED`、`CONFLICT`。

**校验层**：候选图 L0–L2。

### 5.3 `model_add_relationship`

**输入**：`model?`（缺省取源端元素的模型）、`type`（限定关系类；为批准记录、AI 活动时 `PROTECTED_RESOURCE`）、`source`、`target`、`file?`、`dryRun?`。

**IRI（§3）**：`{model}rel-{源slug}-{直连谓词本地名}-{目标slug}`。
- 直连谓词取该类最近的 `arch:unqualifiedForm`（同原型 `Ctx.nearest`）。
- 类没有声明直连形式：取类本地名，首字母小写（§3 补一句，§9；Q6=A 已拍板，第⑥项）。
- 重名加 `-2`、`-3`。真实撞名例子：F12。
- 存量 IRI 不改（F11），规则只约束新生成的 IRI。

**幂等**：已有**同类型、同端点**的关系 → 成功，`changed: false`，返回已有 IRI，不生成 `-2`。`-2` 只在不同关系类撞同一个本地名时出现（F12）。

**写前检查**：
- 端点不存在 → `ELEMENT_NOT_FOUND`（这一项在候选图之前直接查）。
- 记法混用（§7.3）、refines 层级（§7.2）、am4 矩阵（L2）：**由候选图上的 L1/L2 判定，不另写一套规则**（避免两套判定标准，G1 的教训）。违反 → `WRITE_REJECTED`，附原型原文（原文本身带修法，例如"改用 refines"）。
- 派生捷径只是 Warning：照写，放在 `findings` 里。
- 只写限定关系资源，绝不写直连三元组（§8.1）。

**输出**：同 `model_add_element`。

### 5.4 `model_check` / `model_validate` / `model_findings` / `model_gate`

| 工具 | 层 | 原型 | 耗时（采购例子） |
|---|---|---|---|
| `model_check` | L0–L2 | `cmd_check` | 0.07 秒 |
| `model_validate` | L0 + L3 | `cmd_validate` | ≈5 秒 |
| `model_findings` | L4（永不判 FAIL） | `cmd_findings` | <1 秒 |
| `model_gate` | L0–L4 在**同一次构建**上原子执行 | `cmd_gate` | 5.0 秒 |

- **输入**：公共字段 + `model?`（只看一个模型，缺省全部）。
- **输出**：

```jsonc
{ "result": "PASS" | "FAIL",            // 只有 model_gate 有
  "partial": true,                       // check/validate/findings 固定为 true：不是门禁结论（G10）
  "summary": { "violations": 0, "warnings": 1, "infos": 0,
               "violationsByLayer": { "L0":0, "build":0, "L1":0, "L2":0, "L3":0, "L4":0 }, "seconds": 5.0 },
  "findings": [ ... ], "source": { ... } }
```

- gate FAIL **不是工具错误**（`isError: false`），是正常结果。
- aisep-core 的 SHACL-SPARQL 约束（L1 与批准核对用，取自被检查内容自己的 `modules/`）在 §5.6 的同一种无网络子进程里执行（issue #66）：约束尝试建立网络连接 → `QUERY_NOT_READONLY`，无网络子进程建立不了 → `INTERNAL`。两者都是工具错误，gate 不会给出 PASS。
- `modules/` 下被读到的 `.ttl` 不能解析（模块清单 `aisep:loads` 的文件，或 L3 才读的形状文件）→ `PARSE_FAILED`，`details.file` 是该文件的仓库相对路径。这是工具错误，不给部分结果；模型文件的解析失败仍是 L0 发现项。只有用到该文件的工具才报：形状文件坏了，`model_check`（L0–L2）照常返回，`model_validate`、`model_gate` 报错。
- 判定逻辑就是原型的那几个函数，只把 `report()` 改成返回数据。

**`model_findings` 的 `openViolations`**（Q6 条件二：写前只拒新增违规留下的遗留违规要查得到）

```jsonc
{ "partial": true,
  "summary": { … },                 // 仍只统计 L4，与原型 findings 一致
  "findings": [ /* L4 发现项 */ ],
  "openViolations": {
    "count": 1,
    "byLayer": { "L0": 0, "build": 0, "L1": 1, "L2": 0 },
    "items": [ /* Finding，severity 恒为 Violation，layer ∈ L0/build/L1/L2 */ ] },
  "source": { … } }
```

- 内容 = 在同一份内容（`ref` 或工作区，§3.3）上跑 L0–L2 得到的**全部** Violation 实例，结构化 Finding（§7.3），排序同 `model_check`，**不做展示去重**（R2-7）：两个不同 `focus` 的同文案违规是两项，`count` 数的是实例数，工作台才能逐个高亮。不新增层级，不新增严重度。
- **gate 不重复计数**：`openViolations` 只挂在 `model_findings` 的结果上，`model_gate` 的 `summary`、`violationsByLayer` 不读它，L4 仍"永不判 FAIL"。`model_findings` 的 `summary` 也不把它算进去。同一条违规在 `model_check` 和 `openViolations` 里都出现，是同一判定的两次展示，不是两条。
- 为什么挂在 `findings` 而不是只靠 `model_check`：工作台画像不列 `model_check`（§4），"架构全景"本来就要读一次诊断；代理也能用一次调用同时拿到 L4 提示和遗留违规。L0–L2 只要 0.07 秒（F1），附带算不影响 `findings` 的耗时量级。
- 没有开关参数，`openViolations` 总是返回（R2-22：原先为测试加的 `includeOpenViolations` 已删去；L0–L2 只要 0.07 秒，没有性能理由多一种输出形状。T3 与原型比对时忽略这个字段）。
- 工作台"架构全景"在标题旁显示违规计数徽标（`openViolations.count > 0` 时显示，点开列 `items`，按 `focus` 高亮元素）。主分支正常应为 0；不为 0 说明有人绕过了钩子或规则升级了（§5.1 第 5 步）。

### 5.5 `model_remove`（重点：级联）

**输入**

| 字段 | 缺省 | 说明 |
|---|---|---|
| `iri` | 必填 | 元素、关系或视图 |
| `cascade` | `false` | `false`：会牵连其他资源就拒绝，返回完整计划；`true`：按下面的算法级联 |
| `dryRun` | `false` | 只返回计划 |
| `planDigest` | — | 上次 `dryRun` 返回的计划哈希；不一致 → `PLAN_STALE`（不可重试，hint："先用 `dryRun: true` 取新计划"）。带 `planDigest` 且计划里的删除集已全部不在 → 成功，`changed: false, alreadyAbsent: true`（实删成功但响应丢失后的重放）。不带 `planDigest` 而目标不在 → `ELEMENT_NOT_FOUND`（多半是 IRI 写错） |

**受保护的资源**：目标是 `aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Model` → `PROTECTED_RESOURCE`。这是**本文新增的规则**（依据：ADR-009 批准记录是模型仓库里的治理实体、单一事实来源 + 原则五人工把关），不是 ADR-009 的直接推论；Q6=A 已拍板采纳（第④项）。

**源图**：本节所有判据（闭包、外部引用、blockers 的 `file`）都在 `models/**/*.ttl` 解析出的**源图**上算，不加载本体、不构建。构建图里有派生直连三元组（`am4:assignedTo`、`arch:refines` 等），用它会让任何有关系的元素都落进"其他谓词 → 拒绝"（评审实测：指向 `quoteApproval` 的非端点三元组，构建图 6 条，源图只有 1 条）。

**级联算法**（目标 T，所在模型 M_T；范围 = 当前仓库全部模型源文件）：

1. 删除集 D = {T}。
2. **关系闭包**：反复把"`arch:source` 或 `arch:target` 属于 D、且 `arch:inModel` 为 M_T 的限定关系资源"加入 D，直到不变。属于**别的模型**的这类关系不进 D，记为 blocker（`reason: "cross-model-relationship"`）。这一步覆盖 §8.2 的"以它为端点的关系"和"它作为 refines 目标的关系"，也覆盖"指向关系的关系"（上游允许关系指向关系）。判据只看源三元组，不依赖本体。
3. D 中每个成员：删除它作为主语、位于 `models/<M_T 的 slug>/` 文件里的全部三元组，含它自己的 `arch:inView`；挂在下面的空白节点一并删除。D 的成员在别的模型目录里也作主语出现 → blocker，不删。
4. **外部引用** E = 源图上所有 `?s ?p ?d`，`d ∈ D`、`s ∉ D`。按谓词处理：

| 外部引用 | 处理 | 理由 |
|---|---|---|
| `arch:inView`（d 是视图） | 摘除这条三元组，成员元素保留 | §8.2 "指向它的 inView" |
| `bpmn:flowElements`、`bpmn:flowNodeRefs`、`bpmn:lanes`、`bpmn:laneSets` | 摘除这条三元组 | 纯成员关系，主语含义不变（Q6=A，第③项） |
| `bpmn:default` | **拒绝** | 会改网关语义（Q6=A，第③项） |
| `aisep:approves`、`aisep:approvedBy`、`aisep:activity`、`prov:wasAssociatedWith` | **拒绝** | 不能改写批准历史 |
| `dcterms:isReplacedBy` | **拒绝** | 删掉替换目标会让 Superseded 推导失效（G8） |
| `ad:relatedConcept`、`aisep:resultOf`、`ddd:payload`、`ddd:exposedAggregate`、`arch:hasQualityMeasure` | **拒绝**，列出引用方 | 语义引用，拿不准时拒绝；放开要逐条进规范 |
| 其他任何谓词 | **拒绝** | 未知谓词按拒绝处理 |
| s 属于**另一个模型**（任何谓词，含上面"摘除"的谓词） | **拒绝** | 写入方不改别人的模型（§3：悬空即 L1 报错）；第 2、3 步已保证跨模型的关系和主语也走这一条 |

**仓库外引用不检查**：附录 C 的独立模型仓库里指向 T 的引用看不到，删除后会在那边悬空。hint 和附录 C 写明这一点。

5. **布局**：一期没有 `views/*.layout.json`（F16），v1 不处理。出现布局文件后，再加"删除以它为键的条目"。
6. **判定**：
   - 有拒绝项 → `REFERENCED`，`details.plan.blockers` 列出 `{subject, predicate, file}`，hint："改用 `owl:deprecated true` + `dcterms:isReplacedBy` 退役，元素会推导为 Superseded（§6.6、§7.2）"。
   - `cascade: false` 且计划不只 T 本身（`|D| > 1` 或有摘除）→ `CASCADE_REQUIRED`，返回完整计划，hint："确认后传 `cascade: true` 和 `planDigest`"。
   - 其余走 §5.1。候选图出现新违规 → 整体不写，`WRITE_REJECTED`；正常情况下级联不该引入悬空引用，出现说明实现有 bug。
7. **确定性**：计划里所有列表按 IRI 字典序排序；同一输入结果逐字节相同。

**推论**：被批准过的元素删不掉，只能退役（由上表"`aisep:approves` 拒绝"这条本文新规则得出，Q6=A 已拍板）。

**输出**（`dryRun` 与实删相同，实删 `written: true`）

```jsonc
{ "target": "…/bpmnReview",
  "plan": {
    "delete": [ { "iri": "…/sf1", "kind": "relationship", "reason": "endpoint" },
                { "iri": "…/sf2", "kind": "relationship", "reason": "endpoint" } ],
    "detach": [ { "subject": "…/bpmnQuoteApproval", "predicate": "bpmn:flowElements", "object": "…/bpmnReview", "file": "models/procurement/bpmn.ttl" } ],
    "blockers": [] },
  "planDigest": "sha256:…", "written": false, "filesChanged": [], "findings": [] }
```

**按采购例子推算**（验收 T17）：
- `remove(quoteApproval)`：1 个拒绝项（`approval-20261119-arch-baseline aisep:approves`，F8）→ `REFERENCED`。
- `remove(quotation)`：3 条关系可级联（F9）；`cascade:false` → `CASCADE_REQUIRED`。
- `remove(bpmnReview, cascade:true)`：删 `sf1`、`sf2`，摘除 `flowElements`（F10）。

### 5.6 `model_query`

- **输入**：`sparql`（必填）、`limit`（缺省 1000，最大 10000）、`timeoutMs`（缺省 10000，最大 60000）、公共字段。
- **图**：构建后的图 + 全部本体 + 全部对齐（同原型 `cmd_query`，`use_default_graph_as_union=True`）。原型预声明的前缀都可用。
- **只读的落实**：
  - 只调 `Store.query`，从不调 `Store.update`。Update 语句解析失败（F5）→ `QUERY_NOT_READONLY`，message 写"只接受 SELECT/ASK/CONSTRUCT/DESCRIBE"。
  - 不访问网络（F6，issue #60）：pyoxigraph 遇到 `SERVICE` 会真的发 HTTP 请求，所以查询在一个无网络的子进程里执行（`aisep/querybox.py`）。Linux 用 seccomp、macOS 用 sandbox，限制在读入查询之前生效，查询一旦尝试建立网络连接，子进程即被终止，不发出请求 → `QUERY_NOT_READONLY`。这条保证不看查询文本。限制建立不了或确认不了（其他平台、内核不支持）时不执行查询 → `INTERNAL`。超时后子进程被杀掉。
  - 文本里有 `SERVICE` 子句的写法（关键字单独成词，后接 IRI、变量或冒号，或隔空白后接 `SILENT`、前缀名）→ 不执行，直接 `QUERY_NOT_READONLY`。这条词法判断只决定错误码，不承担安全；它拒的写法都在原先 `\bSERVICE\b` 所拒的范围内，`am4:Service`、`?service`、`servicedesk:id` 这类前缀名照常放行。字面量或注释里出现形如子句的 `service <…`、`service: …` 仍会被拒。
  - `timeoutMs` 从启动子进程算起，含子进程启动与载入模型（本机约 0.05–0.1 秒），过小的值会让本来很快的查询超时。
- **输出**（完整 IRI，不用 CLI 的缩写）：
  - SELECT：`{ kind: "select", variables, rows: [{ var: { type: "iri"|"literal"|"bnode", value, datatype?, lang? } }], truncated }`
  - ASK：`{ kind: "ask", value: boolean }`
  - CONSTRUCT/DESCRIBE：`{ kind: "triples", triples: [[s, p, o]], truncated }`
- **错误**：`QUERY_FAILED`（带解析器原文和行列号）、`QUERY_NOT_READONLY`、`QUERY_TIMEOUT`、`PARSE_FAILED`、`INTERNAL`（无网络子进程建立不了）。
- L0 不过时**默认拒绝**：`PARSE_FAILED`，`details` 列出解析失败的文件。否则查询跑在少了文件的图上，调用方会把部分结果当完整结果。要诊断时传 `allowPartial: true`：照查，结果带 `partial: true` 和 `skippedFiles`，`findings` 里带 L0 违规。**与原型不同**（原型照查不提示），有意变更；P9 约束的是 gate 判定，不涉及查询。

### 5.7 `model_impact`

- **输入**：`focus`（IRI 或 `slug:local`）、`mode`（`depends`|`ripple`，缺省 depends）、`depth`（1–10，缺省 3）、`allowInvalid`（缺省 false）、公共字段。
- **G9**：先跑 L0–L2（同原型 `cmd_impact`）。
  - 有违规且 `allowInvalid: false` → `MODEL_INVALID`，`details.findings` 列出违规。
  - `allowInvalid: true` → 照算，结果带 `invalidModel: { violations: n }`，工作台必须醒目展示（对应原型的横幅）。
- **focus 不是合法 IRI 或前缀名**（§5.0）→ `INVALID_ARGUMENT`，`details.rejectedFields` 含 `focus`。
- **focus 不是元素** → `ELEMENT_NOT_FOUND`，`details.candidates` 给名称或 slug 最接近的最多 5 个。**与原型不同**（F4），有意变更。
- **输出**：

```jsonc
{ "focus": { "iri": "…/quotation", "label": "报价单", "types": ["…am4…#BusinessObject"] },
  "mode": "depends", "depth": 3, "invalidModel": null,
  "items": [ { "iri": "…/quotationAggregate", "label": "报价单聚合", "types": ["…ddd#Aggregate"],
               "depth": 1, "related": false,
               "path": [ { "from": "…/quotation", "relationship": "…/rel-quotationAggregate-realizes-quotation",
                           "via": "…am4…#Realization", "direction": "backward", "to": "…/quotationAggregate" } ] } ] }
```

- `direction`：`forward`（原型 `→`）、`backward`（`←`）、`related`（`~`，只出现在第 1 跳）。
- `items` 最多 500 条，超了带 `truncated: true`（§3.5）。
- 结果条目集合与原型 CLI 相同（采购例子 depends 14 个、ripple 16 个，F3）。

### 5.8 `model_diff`（重点）

**输入**

| 字段 | 缺省 | 说明 |
|---|---|---|
| `head` | 必填 | 两种形状之一。① **Git 引用**（字符串）：分支名、标签或 commit，只比已提交内容。② **worktree 模式**（对象）`{ "worktree": "<分支名>" }`：比该分支检出的工作区当前内容，含未提交、未跟踪的改动（Q6 条件一）。对象只接受 `worktree` 一个键（`additionalProperties: false`）；值只接受分支短名，**不接受路径**。会话行传分支名（ADR-013 的共享键） |
| `base` | merge-base(head 侧 commit, mainRef) | 显式给出时原样解析（只接受 Git 引用）。worktree 模式下"head 侧 commit"= 该工作区的 `HEAD` |
| `mainRef` | §3.3 | 工作台不传，取启动参数；短名优先解析成远端跟踪引用 |
| `detail` | `"summary"` | `summary` / `items` / `triples` |
| `model` | 全部 | 只看一个模型 |
| `repo` | §3.3 | — |

**算法**（无状态；Git 引用模式只读 Git 对象；worktree 模式 head 侧读一个工作区的磁盘文件，index 只用来确定文件集合和标志位，内容以磁盘为准。两种模式都不写任何东西）

0. **worktree 模式的定位**（`head` 是对象时，先于第 1 步）：
   - **校验分支名**：以 `-`、`/`、`refs/` 开头，含 `\` 或 NUL → `INVALID_ARGUMENT`；再跑 `git check-ref-format --branch <名>`，失败或输出不等于原文（`@{-1}` 一类会被展开）→ `INVALID_ARGUMENT`。绝对路径、相对路径（`../x`）、工作区真实路径都在这一步被拒。
   - **定位**：`git worktree list --porcelain -z`，找 `branch refs/heads/<名>` **完全相等**的那一项，取它的 `worktree` 路径 W。服务器只读 Git 自己登记的路径，调用方给的字符串从不拼进文件路径，HTTP 客户端借此读不到任意文件。
   - 没有这一项（分支不存在，或存在但没检出）→ `WORKTREE_NOT_FOUND`，`details.branchExists` 区分两种情形；该项带 `prunable` 或 W 目录已不存在 → 同样 `WORKTREE_NOT_FOUND`。
   - **校验 W**（§3.3）：`realpath(W)` 不在 `--allow-root` 之下 → `PATH_OUTSIDE_ROOT`；W 的 common dir 与 `repo` 不同 → `WORKTREE_NOT_FOUND`。"调用方给的字符串不拼进路径"只防住了直接传路径，防不住登记在 Git 里的外部路径。
   - head 侧 commit = `git -C W rev-parse HEAD`，记为 `headCommit`。
1. **解析**：`rev-parse --verify --end-of-options <ref>^{commit}`，失败 → `REF_NOT_FOUND`。base 缺省时跑 `git merge-base --all <head 侧 commit> <mainRef>`：
   - 没有结果 → `NO_MERGE_BASE`；
   - 多于 1 个（交叉合并）→ `AMBIGUOUS_MERGE_BASE`，列出候选，要求显式传 `base`。不静默挑一个。
2. **有没有模型**：先用 `git ls-tree <commit> -- models` 判断两边各有没有 `models/`（`rev-parse <commit>:models` 在缺失时 rc=128，不能放在这一步之前）。分别返回 `baseHasModels`、`headHasModels`：
   - 两边都没有 → 全 0，不报错（附录 C 的独立模型仓库情形）；
   - base 有、head 没有 → 正常算，全部 `removed`（整个 `models/` 被删是要看见的灾难，不能报成"无模型"）；
   - base 没有、head 有 → 全部 `added`。
   worktree 模式下 head 侧"有没有模型"看工作区第 4 步读到的文件集合是否为空。
3. **快速路径**：两边都有时比 `git rev-parse <commit>:models` 的 tree 哈希，相等 → 直接返回全 0，不解析。大多数编码会话不改模型，这一栏几乎不花时间。只对 tree 哈希不同的模型目录继续。worktree 模式没有 tree 哈希可比：先跑 `git -C W ls-files -v -z -- models/`，只要有文件带 assume-unchanged（标志字母小写）或 skip-worktree（`S`）标志，或 W 开了 sparse-checkout，**不走快速路径**，直接进第 4 步逐文件读（R2-4、R2-17：这两种标志下 `git status` 会对已改的磁盘内容保持沉默，评审实测输出为空）。没有这些标志时，用 `git --no-optional-locks -C W status --porcelain --untracked-files=all -- models/` 判断工作区相对 `headCommit` 是否有改动，没有就退化成 Git 引用模式（`head = headCommit`）走快速路径。必须带 `--no-optional-locks`：普通 `git status` 会顺手刷新并回写 `.git/index`，会与代理自己的 git 操作抢 `index.lock`，也违背"只读"。输出里的 `dirty` 以第 4 步读到的内容与 `headCommit` 的逐文件比较为准（探针做法），不依赖 status 的 stat 缓存。
4. **读取**：
   - Git 对象一侧（base；Git 引用模式的 head）：`git ls-tree -r -z <commit> -- models/` 过滤 `.ttl`，`git cat-file --batch` 读 blob。
   - **工作区一侧**（worktree 模式的 head）：文件集合按 §3.3 的统一口径（已跟踪，含已暂存的新文件 ∪ 未跟踪且未被忽略，只留 `.ttl`，嵌套仓库不进入）；逐个读**磁盘当前内容**；磁盘上已不存在的（工作区删除，不论是否暂存）不进集合。即：已跟踪文件的当前内容 + 未跟踪未忽略的新 `.ttl` − 已删除的文件。被 `.gitignore` 忽略的文件不参与（它们本来就不会被提交）。例外：带 skip-worktree 标志、磁盘上不存在的文件（稀疏检出）按 `headCommit` 里的 blob 计入，不当作删除。
   - **符号链接与非普通文件不跟随**：按 §3.3 的安全打开逐级 `O_NOFOLLOW`，**任何一级**路径（文件本身或 `models/<slug>` 这类上级目录）是符号链接，或打开后不是普通文件（或提交里 mode 为 `120000`）→ 不读，当作该文件解析失败处理（`error: "symlink"` / `"not-regular"`），防止借链接读工作区外的文件。
   - **前后核对**（R2-5）：读之前记下 W 的 `HEAD` 和文件集合，读的同时算每个文件的 sha256；全部读完后再取一次 `HEAD`、文件集合并重算哈希。不一致（期间有保存、删除或提交）→ 整体重读，最多 3 次；仍不一致 → `WORKTREE_CHANGED`（可重试）。一次 `status` 不是快照边界。
   **L0 解析**：pyoxigraph 解析每个文件。
   - Git 对象一侧有文件解析失败 → `DIFF_PARSE_FAILED`，`details: {side, commit, file, error}`。不返回部分结果（已提交内容是坏的，结果没法解释）。
   - **工作区一侧**有文件解析失败（代理写到一半、手工编辑出错）→ **不报错**：结果带 `incomplete: true` 和 `failedFiles: [{file, error}]`，其余文件照常比较。失败文件里的主语**不可判定**：取该路径在 base 与 `headCommit` 两个已提交版本里出现过的全部主语 IRI，记入 `indeterminate`，这些主语不进 `items`、不进任何计数。绝不能把失败文件当成"不存在"——那样它的主语全部变成 `removed`，一次写到一半的保存就会显示成"整文件删除"（探针 F19 用变异验证过这个坑：去掉 indeterminate 处理后，写坏一半的 `code.ttl` 的 4 个主语全被报成 removed）。失败文件是新文件时，按路径取不到已提交版本，它里面的新主语看不到，`incomplete: true` 已如实表明。
     **按路径取不够**（R2-14）：文件改名后写坏（不论是否暂存），新路径没有历史、旧路径已不在工作区，按路径得到的 `indeterminate` 为空，旧文件的主语全被报成 removed（评审实测：`git mv code.ttl code2.ttl` 后截断，4 条 removed）；未提交时把主语从别的文件搬进失败文件也一样。所以 `incomplete` 为 true 时再加一条兜底：凡在 base 或 `headCommit` 里出现过、却在 head 侧所有**成功解析**的文件里都找不到的主语，一律进 `indeterminate`，不报 removed（宁可少报，不可误报删除）；`arch:inView` 成员里含 `indeterminate` 主语的视图也进 `indeterminate`（它的成员三元组可能就在失败文件里）。代价：`incomplete` 时真正的删除也只显示为不可判定，修好文件后重调即可。
5. **比较源图，不比较构建后的图**。理由：直连三元组、`aisep:notation` 由源三元组决定，比它们是重复计算；approvalState 由批准记录推导，比构建图会让"新增一条批准记录"把被批准元素显示成"修改"，混淆治理变化和设计变化。
6. **按主语 IRI 分组**：每个三元组归到主语名下。以某 IRI 为**宾语**的三元组变化，不算它被修改。两条例外：
   - **成员谓词归宾语**：`arch:inView` 的主语是元素、宾语是视图（`:customer … arch:inView :orgView`）。它的增删归到**视图**名下，不计入元素的签名，也不进 `changedElementCount`。否则只调整视图的会话会显示成"改了 N 个元素"，而真正变了的视图不显示。
   - **空白节点只支持树形**：一个空白节点恰好被一个三元组引用、且不成环时，把它的 `(p, o)` 递归排序后嵌进引用方的签名。其余情形——成环、被两个以上三元组共享、无人引用的顶层空白节点——一律 `DIFF_BNODE_UNSUPPORTED`，`details` 给文件和位置。不自写通用规范化；真要支持再用标准 RDF 数据集规范化算法。例子模型里没有空白节点（评审 grep 为空），这条眼下影响小。
7. **签名** = 主语名下全部三元组的集合，**与文件无关**。RDF 项按相等性比较（词法形式、数据类型、语言标签都相同才算相同）。
8. **分类**：只在 head = `added`；只在 base = `removed`；两边都有、签名不同 = `modified`；签名相同不出现。
9. **种类 `kind`**（**不加载本体**，只看模型三元组，所以快，也没有"用哪个版本的模块"的问题）：

| kind | 判据（新增、修改取 head 侧；删除取 base 侧） |
|---|---|
| `relationship` | 同时有 `arch:source` 和 `arch:target` |
| `view` | 类型是 `arch:Diagram`/`arch:Catalog`/`arch:Matrix`，或经模型文件里的单父类特化链（R1）回到它们 |
| `governance` | 类型是 `aisep:ApprovalRecord`、`aisep:AgentActivity`，或经特化链回到它们 |
| `schema` | 模型文件里的 `rdfs:subClassOf` 声明（R1） |
| `element` | 其余带 `arch:inModel` 的主语 |
| `other` | 其余（如模型 IRI 本身） |

按表中顺序判定，先命中的算（relationship → view → governance → schema → element → other）。特化链对 view、governance 统一解析（只看模型文件里的 `rdfs:subClassOf`，仍不加载本体）。否则模型里自定义的视图子类会被误判成 element。

10. **文件移动**：三元组在文件间搬动、拆分、合并、调顺序、改注释、改前缀，**都不算修改**，不进 `items`、不进计数。签名相同但所在文件变了的主语单列在 `moves: [{iri, files: {base, head}}]`（只在 `detail` 为 items/triples 时返回），只作提示。`items` 里每条照样带 `files`，不再有 `moved` 字段。
11. **改关系类型**：按 §8.2 新建 IRI 的，自然是一删一增。IRI 没变只改了 `rdf:type`（违反 §8.2，但 diff 如实报告）→ `modified` 并标 `typeChanged: true`。
12. 代码文件、`views/*.layout.json` 一概不看。

**两个计数**：
- `changedElementCount` = kind 为 `element` 的增 + 删 + 改。"AI 进行中"一栏显示它（D2）。
- `touchedElementCount` = 上面那些元素 ∪ 被增删改的关系的两个端点（删除的关系取 base 侧端点，新增的取 head 侧），只取 kind 为 element 的。关口页用它高亮。

**输出**

```jsonc
{
  "base": { "ref": null, "commit": "40hex", "viaMergeBase": true, "mainRef": "refs/remotes/origin/main" },
  "head": { "kind": "ref", "ref": "feat/x", "commit": "40hex" },
  // worktree 模式时：
  // "head": { "kind": "worktree", "branch": "feat/x", "headCommit": "40hex", "dirty": true },
  "baseHasModels": true, "headHasModels": true,
  "incomplete": false, "failedFiles": [], "indeterminate": [],   // 只有 worktree 模式可能为 true / 非空
  "counts": {
    "element":      { "added": 2, "modified": 1, "removed": 0 },
    "relationship": { "added": 3, "modified": 0, "removed": 1 },
    "view":         { "added": 0, "modified": 0, "removed": 0 },
    "governance":   { "added": 0, "modified": 0, "removed": 0 },
    "schema":       { "added": 0, "modified": 0, "removed": 0 },
    "other":        { "added": 0, "modified": 0, "removed": 0 }
  },
  "changedElementCount": 3,
  "touchedElementCount": 5,
  // detail = items | triples 才有：
  "items": [
    { "iri": "…/quoteApproval", "kind": "element", "change": "modified",
      "types": ["…am4…#Process"], "label": "报价审批",
      "files": { "base": ["models/procurement/am4.ttl"], "head": ["models/procurement/am4.ttl"] },
      "changedPredicates": ["http://www.w3.org/2004/02/skos/core#prefLabel"] },
    { "iri": "…/rel-supplier-assignedTo-quoteApproval", "kind": "relationship", "change": "added",
      "types": ["…am4…#Assignment"],
      "source": { "iri": "…/supplier", "label": "供应商" }, "target": { "iri": "…/quoteApproval", "label": "报价审批" },
      "files": { "base": [], "head": ["models/procurement/am4.ttl"] } }
  ],
  "touchedElements": ["…/quoteApproval", "…/supplier"],
  "moves": [], "truncated": false
  // detail = triples 时，每个 item 另带 "triples": { "added": [[p,o]], "removed": [[p,o]] }
}
```

- `base.mainRef`：base 缺省时是实际用来求 merge-base 的完整 ref 名（§3.3）；显式给出 `base` 时不涉及主分支，为 `null`。`truncated` 与 `items`、`touchedElements`、`moves` 同在，`detail: "summary"` 时不返回（计数永远完整，§3.5）。
- `head.kind` 标明比的是什么：`ref` 时 `head.commit` 是被比较的 commit；`worktree` 时 `head.headCommit` 是该工作区的 `HEAD`，`dirty` 表示工作区 `models/` 下的 `.ttl` 相对 `headCommit` 是否有改动（含未跟踪新文件、删除、读不了的文件）。`dirty: false` 时结果与 `{head: headCommit}` 相同。
- `files.head` 在 worktree 模式下是工作区里的相对路径；`moves` 照常计算。
- 删除项的 `types`、`label` 取 base 侧。关系端点的 `label` 取对应一侧（端点本身没变也给），差异图不用再查。
- 违规不阻止 diff（与 impact 不同）：违规的改动正是关口要看的，合法性由同页的 gate 负责。
- **校验层**：只有 L0。

**两个用途怎么调**

| 用途 | 调法 | 读哪些字段 |
|---|---|---|
| AI 进行中（每个会话一行） | **缺省 worktree 模式**：`{ head: { worktree: row.branch }, detail: "summary" }`，不传 base | `changedElementCount`；`head.dirty` 为 true 时数字旁标"含未提交"；`incomplete` 为 true 时标"部分文件解析失败"并悬停列出 `failedFiles`；悬停显示 `counts` 明细和 `base.commit` 前 7 位。`WORKTREE_NOT_FOUND`（会话的工作区已清理、分支只在远端等）→ 退回 Git 引用模式 `{ head: row.branch }` 再调一次 |
| 关口页差异图（批准前） | `{ head: <当前分支头 sha>, detail: "items" }`（**只用 Git 引用模式**） | `items` 画节点和边（绿增、黄改、红删），`touchedElements` 高亮 |
| 关口页回看历史批准 | `{ base: 活动.baseCommit, head: 活动.headCommit, detail: "items" }` | 同上；commit 内容不可变，但**只在仍可达时**能复现。Q5=A 已拍板：模型仓库禁用 squash 合并和 rebase 合并，批准提交经普通 merge 进受保护分支，headCommit 因此保持可达（§9 附录 C 改文；落实要同时禁止 force push、限制直接 push，见该条）；分支被删而尚未合并的批准随分支一起丢弃 |

- **批准只针对 commit**：关口页差异图、`record_approval` 的 `headCommit` 都只认已提交版本。worktree 模式的结果会随工作区每次保存而变，不能作为"人看过的那一版"的证据；工作台关口页不提供 worktree 模式。
- 批准提交只增加 `governance` 类变化，所以批准之后"改动元素"数不变（T22）。
- 没有 `branch` 的行不调用。worktree 模式下分支还没有提交也能看到改动；只有工作区找不到、退回 Git 引用模式时，"分支还没有提交 → 结果为 0"的旧限制才出现。
- 前提不变：模型文件与会话改动的代码在同一仓库、同一分支（附录 C）。worktree 模式不解决"模型仓库独立"的情形。

**错误**

| 错误码 | 情形 | 工作台显示 |
|---|---|---|
| `REF_NOT_FOUND` | 分支不在这个仓库（未推送、已删除） | "—（分支不在模型仓库）" |
| `NO_MERGE_BASE` | 没有共同祖先 | "无法比较" |
| `AMBIGUOUS_MERGE_BASE` | 交叉合并 | "无法比较" |
| `WORKTREE_NOT_FOUND` | worktree 模式：分支不存在、存在但没有检出的工作区、工作区目录已删除（`details.branchExists`）、登记的工作区不属于本仓库 | 退回 Git 引用模式重调；仍失败按 `REF_NOT_FOUND` 显示 |
| `PATH_OUTSIDE_ROOT` | worktree 模式：分支检出的工作区在 `--allow-root` 之外 | 退回 Git 引用模式重调 |
| `WORKTREE_CHANGED` | worktree 模式：读取期间工作区一直在变（重读 3 次仍不一致），可重试 | 保留上次的数字，下一轮刷新再调 |
| `DIFF_PARSE_FAILED` | Git 对象一侧（base，或 Git 引用模式的 head）L0 失败。工作区一侧的解析失败**不是错误**，见上文 `incomplete` | "模型解析失败" |
| `DIFF_BNODE_UNSUPPORTED` | 空白节点成环、共享或无人引用 | "模型解析失败" |
| `INVALID_ARGUMENT` | ref 以 `-` 开头；`head.worktree` 不是合法分支短名（路径、`refs/…`、`@{-1}` 等）；`head` 对象带 `worktree` 以外的键；`base` 传了对象 | — |

### 5.9 `governance_record_approval`（重点：活动参数）

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | ✔ | 记录写进新建的 `models/<slug>/governance/<记录本地名>.ttl`，一条记录一个文件（U2，第 5 步） |
| `gate` | ✔ | `GateRequirements` / `GateArchitecture` / `GateDesign` / `GateMerge` / `GateRelease`，展开为 `aisep:<gate>`；取值集合来自模块（F14、G2） |
| `decision` | ✔ | `Approved` / `Rejected` |
| `approvedBy` | ✔ | **已有**的 `arch:Stakeholder` 实例 IRI，且**不能**是 `aisep:AIAgent` 的实例（Q4=C 已拍板：AI 不能批准，违反 → `APPROVER_NOT_ALLOWED`）；还须是被批模型 `model` 的成员（`arch:inModel` 指向它），否则 → `APPROVER_NOT_ALLOWED`（`details.reason: "approver-not-in-model"`，#73：别的模型的干系人在全仓库视图里算数，在被批模型自己的视图里不算；只约束新记录，主干上已有的跨模型记录不动）。不自动建人 |
| `approves` | ✔ | IRI 数组，≥1。每个都必须在 `headCommit` 里存在，是元素、模型或 ADR：元素不含 `aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Stakeholder`；限定关系、视图不可被批准，它们的改动只计入所属模型的比较范围、不计入端点元素（规范 §6.6，第四轮 R4-5、G4-4）。工作台用 diff 的 added + modified 元素预填，人可以删减 |
| `branch` | ✔ | 记录提交到哪条分支（Q2=A：缺省传会话分支，随 PR 合入；主线上已有提交的批准只有发布关口（U4①），传短命批准分支，见下文"发布关口"，R2-15）。只收分支短名，校验同 §5.8 第 0 步：以 `-`、`/`、`refs/` 开头或含 `\`、NUL → `INVALID_ARGUMENT`；`git check-ref-format --branch <名>` 失败或输出不等于原文 → `INVALID_ARGUMENT`；`refs/heads/<名>` 必须存在。`feat/x` 可以，`refs/heads/feat/x` 不行（第四轮 G4-5：存完整 ref 会让合并时检查项 4 与 `pull_request.head.ref` 比较失败）。标签、远端跟踪分支、`HEAD~1` 这类修订表达式 → `INVALID_ARGUMENT`。`branch` 不能是模型主分支（按短名比：mainRef 的分支短名，即解析前的短名，或远端跟踪引用去掉 `refs/remotes/<remote>/` 后的部分；第四轮复查）→ `INVALID_ARGUMENT`（`details.reason: "protected-branch"`），hint 指向"发布关口"的批准分支流程。理由：受保护分支禁止直接 push、不开例外（R2-15 已拍板），提交在本地主分支上的批准推不上去。原"本地主分支须等于跟踪远端，否则 `STALE_HEAD`"的同步校验随之取消 |
| `headCommit` | ✔ | 40 位十六进制；**人在差异图上看到的那个 commit**（diff 结果的 `head.commit`）。evidence 固定取它，服务器不再读"当前分支头"来定 evidence。有没有 `activity` 都必填 |
| `expectedBaseCommit` | — | diff 结果的 `base.commit`。给了就核对：服务器算出的 merge-base 不等 → `STALE_BASE`。只用于核对，不写入；baseCommit 仍由服务器算 |
| `slug` | — | 缺省 `{关口短名}-{headCommit 前 7 位}`，如 `architecture-9c41e07` |
| `prefLabel` | — | 缺省 `"{关口中文名}{批准\|驳回}：{第一个被批准对象的中文名}{等 n 项}"@zh` |
| `activity` | — | 见下表 |
| `mainRef` | — | §3.3 |

**不接受**的字段：`evidence`、`generatedAt`、`baseCommit`。`inputSchema` 写 `additionalProperties: false`，入口显式校验，传了就是工具执行错误 `INVALID_ARGUMENT`，`details.rejectedFields` 点名（§3.1；不是协议错误，规范把入参校验错误归为工具执行错误）。理由：evidence 和 baseCommit 由服务器算才不会错（附录 B.3 的"起点错误"）；时间由服务器给才不能倒填。Q6=A 已拍板采纳（第⑤项）。

**为什么 baseCommit 不收调用方的值**（异构评审提出"批准时主分支已移动，重算的 base 不是人看到的那个"）：`merge-base(headCommit, 主分支)` 是分叉点。主分支只往前走、没有合入这条分支的任何提交时，它不变；会变的只有"主分支合入了本分支的一部分"这类情形。这类情形用 `expectedBaseCommit` 核对兜住即可，不需要让调用方决定写入值。

**`activity` 对象**

| 字段 | 必填 | 规则 | 工作台从哪取 | 写成 |
|---|---|---|---|---|
| `agent` | ✔ | 已有模型元素 IRI，判定同 `prov:wasAssociatedWith`（§6） | AO `harness` 映射到模型里的代理元素（D5） | `prov:wasAssociatedWith` |
| `sessionRef` | ✔ | 不透明，1–200 个可见 ASCII 字符（`!`–`~`，不含空白与换行；它原样进提交的 `AISEP-Session` trailer），否则 `INVALID_ARGUMENT` | AO `session.id` | `aisep:sessionRef` |
| `branch` | — | 给了必须与顶层 `branch` 完全相同，否则 `INVALID_ARGUMENT` | — | `aisep:branch`（取顶层值，即分支短名，不含 `refs/heads/`，与 `pull_request.head.ref` 同形） |
| `startedAt` | ✔ | 严格 xsd:dateTime（同原型 `parse_xsd_datetime`） | AO 会话创建时间 | `prov:startedAtTime` |
| `endedAt` | — | 缺省 = 服务器当前时间（UTC）；开始不晚于结束 | — | `prov:endedAtTime` |
| `label` | — | 缺省 `"AI 活动：{branch}"@zh`；工作台建议传任务标题 | AO 任务标题 | `skos:prefLabel` |
| — | — | 顶层 `headCommit` | — | `aisep:headCommit` |
| — | — | **服务器算** merge-base(headCommit, mainRef)；多个 → `AMBIGUOUS_MERGE_BASE` | — | `aisep:baseCommit` |

**执行**（一次提交）

1. **分支头校验**（不论有没有 activity）：设 tip = `branch` 当前头。
   - headCommit 必须是 tip 的祖先（或等于 tip），否则 `STALE_HEAD`。
   - headCommit..tip 之间**逐个提交**检查，不看净差异（先加后删的净差异可能为空）。范围内有合并提交（`git rev-list --min-parents=2 headCommit..tip` 非空）→ 直接 `STALE_HEAD`，不去定义"与哪个父提交比"（R2-9：取 first-parent 会漏掉侧分支带进来的代码提交）。其余每个中间提交（恰有一个父提交）必须同时满足：(a) 恰好一个 `AISEP-Evidence` trailer，其值等于该提交新增的那条批准记录的 `aisep:evidence`（第三轮 A）；(b) 相对父提交**恰好新增一个文件**，不修改、不删除、不改名任何已有文件（含 `governance.ttl`；U2），新文件路径匹配 `models/<slug>/governance/[^/]+\.ttl`（只收 `.ttl`，不进子目录），文件模式为 `100644`（符号链接 `120000`、可执行 `100755` 都不算）（不限于本次调用的 `model`：同一分支先批准模型 A、再批准模型 B 时，A 的批准提交也要能过，R2-18）；(c) 该提交与其父提交的**源图差异**（复用 `model_diff` 的分组，§5.8，按 (b) 中那个模型计算）只有新增主语：**恰好一条** `aisep:ApprovalRecord`，另可带至多一个被它经 `aisep:activity` 引用的 `aisep:AgentActivity`，没有任何修改或删除（核对轮 6）。另直接解析 (b) 中的新文件本身（不靠并集图差异）：其中的主语只能是 (c) 中那条记录及其可选活动，每个主语的全部三元组都在该文件里，且文件名去掉 `.ttl` 等于记录 IRI 去掉 `{model}` 前缀的本地名（第四轮 R4-8：新文件复制一条已有记录、再加一条新记录，复制部分在图差异里消失）。新文件里有空白节点（作主语或宾语）或 RDF 1.2 三元组项 → 不是批准提交；空白节点无人引用、被共享或成环，使源图差异本身算不出（`DIFF_BNODE_UNSUPPORTED`，§5.8）时，同样判为不是批准提交，不抛异常。合并时校验在 PR 头、目标分支头、合并结果任一侧图差异算不出时都失败关闭：报一条 `check-error`，另对 `T..H` 中每个带 `AISEP-Evidence` trailer 的提交跑本判据，不合格的报 `not-approval-commit`（`aisep/mergecheck.py` 的 `_bnode_fallback`）；检查项 3、7 为记录的 evidence 提交另建的一侧算不出时，同样失败关闭，但只报一条 `check-error`，不跑逐提交判据。
   - 上面"无合并提交 + 每个提交满足 (a)(b)(c)"下称**批准提交判据**。合并时 CI 调用同一个函数（见下文"合并时校验"）。
   - **有效内容提交**（核对轮 4）：从某个提交沿第一个父提交回溯，跳过满足 (a)(b)(c) 的提交，得到的第一个提交。它是 mainRef（CI 中为 T）的祖先或等于它时，按"主线提交"处理。本步的"主线提交的批准"、合并时校验检查项 3、批准专用 PR 判定统一用它。理由：发布批准分支上的批准提交 A 不在主线上，但它只比 R 多一条记录；不这样算，对 A 补批 `GateArchitecture` 就绕过了 U4①。
   - 任何一条不满足 → `STALE_HEAD`，`details: {tip, offendingCommit, reason}`，工作台提示"分支有新提交，请刷新差异后再批"（Q3=A 已拍板）。
   - 只按文件路径判断不够：`governance/` 下的新文件里同样能写 `arch:Stakeholder` 等元素（governance 类元素本就写在这一带，§5.1 缺省文件表；例子里就有 `:chiefArchitect a arch:Stakeholder`），代理可以在 headCommit 之后加人，再拿这个人当 `approvedBy`。
   - 这样同一会话可以连过多个关口：第一次批准提交满足 (a)(b)(c)。
   - 这一步在无锁状态下先做一遍，是为了在跑 5 秒的 gate 之前尽早拒绝；**真正生效的是第 7 步锁内的复验和提交后核对**。第 1 步到第 7 步之间代理照样可以用自己的 `git commit` 提交（它不碰 `aisep-write.lock`），只做第 1 步会让批准提交叠在一个没人看过的代码提交上（R2-1、R2-13，评审实测）。
   - **主线提交的批准**（R2-15、U4①）：headCommit 的有效内容提交是 mainRef 的祖先或等于它（下称主线提交）时，**只允许 `gate = GateRelease`**，其他关口 → `INVALID_ARGUMENT`（`details.reason: "mainline-head-gate-not-release"`）。理由：非发布关口批准的是分支上待合入的改动；对主线上的旧提交补批，会把对旧内容的批准套到主线当前同 IRI 的元素上（第三轮 P）。反过来，`gate = GateRelease` 时 headCommit 本身必须是 mainRef 的祖先或等于它（不按有效内容提交放宽，evidence 就是被发布的 R），否则 `INVALID_ARGUMENT`（`details.reason: "release-head-not-on-main"`）。主线提交上带 `activity` → `INVALID_ARGUMENT`，`details.rejectedFields: ["activity"]`：此时 baseCommit 就是 headCommit，活动的差异为空；发布不是 AI 活动。
2. **evidence** = headCommit（§6.6 的 L1 规则天然满足）。
3. **gate**：在 headCommit 的快照（§3.3）上跑完整 gate。`decision=Approved` 而 FAIL → `GATE_FAILED`，附违规（Q6=A，第②项）。`Rejected` 不要求 PASS。gate 摘要随结果返回。
4. **去重**：
   - 已有活动的 `(sessionRef, headCommit, branch)` 都相同 → 复用该活动，不新建；branch 不同则新建（否则活动的 `aisep:branch` 是旧分支，合并时检查项 4 拒绝；第四轮复查）。
   - 已有记录的 `(gate, decision, approvedBy, approves 集合, evidence)` 相同 → 不写、不提交，返回那条记录，`duplicate: true`。evidence 来自调用方给的 headCommit，所以"提交成功但响应丢失"后的重放能命中，不会写第二条。
5. **生成**：
   - 记录 IRI `{model}approval-{yyyymmddHHMMSS}-{slug}`（§3）；活动 IRI `{model}activity-{yyyymmddHHMMSS}-{headCommit 前 7 位}`（§3 新增行，Q6=A 第⑥项）；时间取 `prov:generatedAtTime` 的 UTC 年月日时分秒；重名加 `-2`。`-2` 只看得到本分支：两条分支对同一提交、同一关口批准时，跨分支不重名靠秒级时间；同一秒内并发仍会撞名，合并时 add/add 冲突，登记为残余风险（第四轮 R4-7，用户拍板只加秒级时间）。
   - `prov:generatedAtTime` = 服务器当前时间，UTC，`Z` 结尾（测试注入时钟）。
   - **新建一个记录文件**（U2）`models/<slug>/governance/<记录本地名>.ttl`，记录本地名即记录 IRI 去掉 `{model}` 前缀的部分（如 `approval-20261120093015-architecture-9c41e07.ttl`；重名加 `-2` 时文件名同步）。内容 = 标准前缀头 + 活动块（本次新建活动时）+ 记录块，记录用 `aisep:activity` 指向活动。`governance/` 目录不存在时先建。
   - 已有 `governance.ttl` 不动：其中的记录与人员不搬迁（IRI 不变），它仍是 `arch:Stakeholder` 等 governance 类元素的缺省写入文件（§5.1）。理由：两条分支各往 `governance.ttl` 末尾追加记录，合并必冲突；托管平台的服务端合并大概率不遵守 `.gitattributes` 的 `merge=union`（第三轮 git-1，平台事实见文末"第三轮"）。每条记录一个新文件，两条分支各批准一次后都能干净合入（T43）。
6. **校验**：候选图跑 L0–L2，走 §5.1 的新违规判定；另外 `Ctx.approval_problems` 和 `activity_problems` 对新记录、新活动必须为空（G1：与推导用同一个函数）。不合法的记录不参与推导，写入一条注定被忽略的记录没有意义。
7. **Git 落地**（只碰一个路径）：
   - 用 `git worktree list --porcelain` 找 `branch` 检出在哪个 worktree（下称 W）。没有检出 → `BRANCH_NOT_CHECKED_OUT`（v1 不做无检出的底层提交：底层提交不跑钩子，"不跳过 pre-commit"就做不到）。
   - **校验 W**（§3.3）：`realpath(W)` 不在 `--allow-root` 之下 → `PATH_OUTSIDE_ROOT`；common dir 与 `repo` 不同 → `WORKTREE_NOT_FOUND`。否则服务器会对仓库外的目录、甚至另一个仓库执行 `git commit`。
   - **锁 W 的写锁**（§3.4 第 1 步），与 W 里代理的 `model_*` 写入互斥。
   - **加锁后的分支核对**：W 不能是 detached HEAD（→ `DETACHED_HEAD`）；W 的 `HEAD` 必须仍指向 `refs/heads/<branch>`，定位 W 到加锁之间 W 被切到别的分支 → `CONFLICT`（`details.reason: "worktree-switched"`，未写，可重试）。W 的模型文件集合（§3.3 统一口径）及其内容必须与 W 的 `HEAD` 完全一致（`git status --porcelain -- models/` 为空只是其必要条件），否则 `DIRTY_WORKTREE`（避免把别人的改动卷进来，也保证 pre-commit 的 gate 看到的模型就是"已提交 + 本次新建的记录文件"）。若与 `HEAD` 的差别恰好是 `governance/` 下一个未提交的新文件（未跟踪、只暂存，或 intent-to-add 登记：`git status --porcelain` 显示 ` A`；判定按磁盘文件与 `HEAD` 比较，三种都覆盖）、内容是一条批准记录（可含活动），`details.orphanApproval: true`，hint 给出恢复命令（`git rm --cached -q --ignore-unmatch -- <文件> && rm -- <文件>`；多半是上次调用在提交前被杀）。
   - **锁内复验**：取 `git -C W rev-parse HEAD` 为 tip'，对它**重跑第 1 步的全部校验**（祖先、合并提交、逐提交 (a)(b)(c)、去重），记下 tip'。不过 → `STALE_HEAD`，不写。
   - 新建记录文件（经 §3.3 安全打开，`O_CREAT | O_EXCL`，目标已存在 → `CONFLICT`），记下所写内容的 sha256 → `git add --intent-to-add -- <记录文件>`（只登记路径、不暂存内容；未跟踪的新文件不先登记，`git commit --only` 会报 pathspec 不匹配，执行会话实测）。登记失败（如 `index.lock` 被占用）→ 已被别的提交带走则报 `CONFLICT`（taken，见下文"风险"），文件未被改动则删除它、报 `COMMIT_FAILED`（含 `index.lock` 时可重试），已被改动则保留、报 `CONFLICT`（不可重试，`details.fileKept`）→ `git commit` 前再比一次 sha256，不等 → 从 index 移除该路径（`git rm --cached -q -f --ignore-unmatch -- <记录文件>`）、保留文件、`CONFLICT`（不可重试，`details.fileKept`；`git rm --cached` 本身失败 → `COMMIT_FAILED`，`orphanApproval`，不可重试；文件已被别人删掉 → 移出 index 后现场已干净，`CONFLICT`，`details.reason: "file-deleted-before-commit"`，可重试，不带 `fileKept`）→ `git -c trailer.ifexists=add commit -q --only -m "aisep: <gate> <decision> <记录本地名>" --trailer "AISEP-Evidence: <evidence>" [--trailer "AISEP-Session: <sessionRef>"] -- models/<slug>/governance/<记录本地名>.ttl`（提交的是文件此刻的内容，钩子照常跑）。
   - **为什么用 intent-to-add**（提交 `6b2d340`，测试 `aisep-mcp/tests/test_record_approval_review.py` 的 `test_agent_commit_between_add_and_commit`）：intent-to-add 条目不进 `write-tree`，登记到提交之间代理在 W 里用普通的 `git add <自己的文件>` + `git commit`，不会把批准记录一起带走；之后按下文"提交后核对父提交"撤回本次提交、报 `STALE_HEAD`。普通 `git add` 会让记录进入暂存区，被代理的普通提交带走（26e7f7e 上实测）。
   - **风险**：intent-to-add 的路径算作已跟踪。登记到提交之间，代理执行任何按目录或"全部已跟踪文件"暂存、提交的命令，如 `git add -A`、`git add -u`、`git add .`、`git commit -a`、`git commit -- <目录>`，都会把这个尚未完成的记录文件一起提交进代理自己的提交（测试覆盖了 `commit-a` 一例）。服务器不回滚别人的提交：登记失败、提交前核对、提交失败（第 8 步）、提交后核对、落错分支的撤回这几处回滚之前，先看 W 的 `HEAD` 是否已跟踪该文件，是 → 不动 index 和文件，报 `CONFLICT`（`details.reason: "taken-by-other-commit"`，**不可重试**：带走它的提交还含代理的改动，要人判断；原样重试在第 1 步的无锁预检就报 `STALE_HEAD`：带走它的提交 C 不是批准提交，`headCommit..tip` 不再全是批准提交，走不到锁内复验，`aisep/approval.py` 的 `_stale`）。`details.takenByCommit` 为带走它的提交，hint 给出它的短 SHA；`details.commit` 只表示本次调用自己的批准提交 A，只在已有 A 时给出（提交后核对、落错分支的撤回两处）。代理侧的提交规范因此要求：有批准进行时，只按具体文件路径暂存和提交（同第 9 步）。
   - **不加 `--no-verify`**，pre-commit 的 gate 照常跑。作者身份取仓库自己的 git 配置，服务器不改。
   - **提交后核对父提交**：新提交记为 A。`A^` 必须等于 tip'。复验到 `git commit` 之间仍有毫秒级窗口，代理在此期间提交的 C 会让历史变成 tip'–C–A。不等时撤回本次提交：`git update-ref refs/heads/<branch> A^ A`（比较并交换，只在分支头仍是 A 时生效，C 原样保留）；从 index 移除记录文件（`git rm --cached -q -f --ignore-unmatch -- <记录文件>`），文件仍等于本次写入的 sha256 时删除它（不用 `git restore`）；然后报 `STALE_HEAD`（`details.reason: "concurrent-commit"`）。与第 8 步不同：文件被改动而保留时**仍报 `STALE_HEAD`**（`concurrent-commit`），不报 `CONFLICT`，但带 `details.fileKept: true` 和 `details.recover`，消息写明文件仍在；不清理的话下一次调用会报 `DIRTY_WORKTREE` + `orphanApproval`；`git rm --cached` 本身失败时也报 `STALE_HEAD`，但带 `details.orphanApproval: true` 和恢复命令。`update-ref` 的比较失败（A 之上又有新提交）→ 不再动分支，报 `CONFLICT`（不可重试），`details` 给出 A 和恢复提示，由人处理。不采用"临时 index + `commit-tree` + `update-ref` 原子提交"：它绕开仓库钩子，第一轮 #24 已否决。
   - **提交没落在 `branch` 顶端**（`aisep/approval.py` 的 `_landed`、`_misplaced`）：`git commit` 之后按提交内容（只新增这一个记录文件、blob 与所写内容一致）判断 `refs/heads/<branch>` 的头是不是本次提交。不是，多半是在上文"加锁后的分支核对"之后、`git commit` 之前 W 被切到了别的分支：按 SHA 找到本次提交，在**头恰好是它**的其他分支上用 `update-ref <ref> A^ A` 比较并交换撤回（从不动 `refs/heads/<branch>`），再按第 8 步移出 index、删除或保留文件，报 `CONFLICT`（`details.reason: "worktree-switched"`，`details.landedOn`）。本次提交不在任何分支头上（之上又被叠了提交，如 post-commit 钩子：`commit-stacked`；或找不到：`commit-not-found`）→ 不动 index 和文件，报 `CONFLICT`（不可重试）；落错的分支撤回失败、撤回后 `git rm --cached` 失败 → `CONFLICT`（不可重试）。各情形的 retryable 见 §7.2。
8. **回滚**：commit 失败（钩子拒绝、`index.lock` 被占用）→ 从 index 移除记录文件（`git rm --cached -q -f --ignore-unmatch -- <记录文件>`，`-f` 只动 index）；文件仍等于本次写入的 sha256 时删除它；不等（钩子或编辑器改过）→ 保留文件，返回 `CONFLICT`，**不可重试**（保留的文件会让原样重试先撞上第 7 步的 `DIRTY_WORKTREE`，§7.2）。凡保留文件的出口（第 7 步登记失败、提交前核对、提交后核对、落错分支的撤回，以及本步）`details` 一律带 `fileKept: true` 和 `recover`（人工清理命令），hint 写明文件被改过、未删除。W 的 `HEAD` 已跟踪该文件时不回滚（第 7 步"风险"）；`git rm --cached` 本身失败时文件留在 index 和磁盘上，报 `COMMIT_FAILED`（`details.orphanApproval: true`，不可重试）。**不用** `git restore`（会抹掉未知的外部改动）。只有记录已移出 index、文件已删除这一支报"已回滚"的 `COMMIT_FAILED`（输出含 `index.lock` 时可重试）。`details.output`（git 输出最后 50 行）只在有 git 输出可附的出口给出：第 7 步 `git add --intent-to-add` 失败的各出口（taken、kept、`COMMIT_FAILED`）和本步 `git commit` 失败的各出口（taken、`orphanApproval`、kept、已回滚）；第 7 步提交前核对、提交后核对、落错分支撤回这几处的出口（含其中的 kept 出口）不带 `output`。
9. **崩溃窗口如实写明**："新建记录文件"到"commit 结束"之间进程被杀，会留下一个未提交的记录文件。下一次调用在第 7 步以 `DIRTY_WORKTREE` + `orphanApproval` 报出来；pre-commit 不会拦它（记录本身合法），所以代理侧的提交规范要求只按具体文件路径暂存和提交（第 7 步"风险"）。改用临时 index + `commit-tree` 能消除这个窗口，但会绕开仓库钩子，v1 不取。
10. **批准之后再提交代码**（R2-13、U1、U3 已拍板）：第 1、7 步只管到本次提交为止，合并前的核对全部在下文"合并时校验"：
   - 之后分支上再有代码提交 → 合并时用同一判据拒绝，旧批准不会随合并进主线；
   - PR 修改了目标分支上已是 Approved 的元素，而本 PR 没有新增覆盖它的、结论为 Approved 的合法批准记录（关口不限，且须是该对象在合并结果中生效的那条；第四轮 R4-2、R4-3）→ 拒绝（U1，"改动已批准元素须重批"）；PR 删除了目标分支上已是 Approved 的元素 → 一律拒绝，提示改用 `owl:deprecated` + `dcterms:isReplacedBy` 退役（Q6④、§5.5"被批准过的元素删不掉，只能退役"；核对轮 1）；
   - PR 改写或删除了目标分支上已有的批准记录、AI 活动 → 拒绝（第三轮 E）；
   - CI 的结论可能对应旧的目标分支头：执行合并的人在合并前用同一脚本对**当前**目标分支头重算，不过不合（U3）。

**合并时校验**（R2-13 已拍板，与 Q3=A 合为一条规则；第三轮按 C–G、I、O、Q 与 U1、U3 收紧）

规则：批准记录的 evidence（有活动时就是活动的 headCommit）到所在分支头之间，只允许出现满足批准提交判据（第 1 步）的提交。记录时刻由第 1、7 步核对；合并进受保护分支前由 CI 再核对一次，判据相同、调用同一个函数。evidence 等于分支头是其特例（范围为空）。

CI 设为受保护分支的必需检查，PR 每次更新都跑；合并前由执行合并的人对当前目标分支头再跑一次（见下文"合并前重算"）。两处是同一个检查脚本。

**口径**（第三轮 F、G，写死）：

- PR 头 H = `pull_request.head.sha`（`refs/pull/N/head`），不用 `GITHUB_SHA`（那是测试合并提交）；目标分支头 T = 检查时远端 `refs/heads/<主分支>` 的当前值；合并结果 M = 在本次取得的 T 上本地 `git merge --no-ff --no-commit H` 的结果，CI 与合并前重算相同；合并冲突 → 判失败，提示先解决冲突。不用 `refs/pull/N/merge`：它可能基于旧的目标分支头生成，手动重跑 CI 也沿用旧的 `GITHUB_SHA`（第四轮 R4-10）。
- 完整克隆（`actions/checkout` 设 `fetch-depth: 0`）。任何 git 命令非零退出一律判失败，不得跳过；浅克隆下 `rev-list`、`merge-base` 出错同样判失败。
- "本 PR 新增"的主语 = H 的模型源图里有、T 的模型源图里没有的主语；PR 的提交范围 = `git rev-list H ^T`。两者都与 merge-base 个数无关，交叉合并产生多个 merge-base 时结论不变。
- "PR 带进来的模型差异" = M 相对 T 的源图差异（`model_diff` 分组，§5.8）。不用 T 与 H 直接比：主线在分叉后新增的内容会被误报为删除。
- "引入该记录的提交" = `git rev-list --reverse --topo-order H ^T` 中第一个在其树中含该记录主语的提交（核对轮 6）。逐条核对不过时，报出的 `offendingCommit` 就是它。
- **时间比较**（第四轮 G4-1）：凡比较 `prov:generatedAtTime`（检查项 2 的"更晚"、检查项 3 的未来时间、检查项 6 的生效记录、推导的"最近"与平局），一律先用 `parse_xsd_datetime` 归一化为 UTC 瞬间（不带时区的按 UTC）再比，不按字面串比；归一化后相同即为同时。
- **对象的比较范围**（核对轮 3；检查项 6、7 共用）：`approves` 中的对象是元素时，比较以它为主语的源图三元组；元素的批准不覆盖以它为端点的限定关系（与 §5.8 第 6 步"作宾语不算修改"一致），只改关系的端点不触发对端点元素的重批；要约束连接，按模型批准（第四轮 G4-4，用户拍板；残余见附录 C）；是模型时，比较以模型 IRI 为主语的源图三元组（第四轮 R4-6：改模型名称、`arch:modelConformsToMetamodel` 也算修改）、该模型全部成员（`arch:inModel` 指向它的主语）以及以这些成员为端点的限定关系，成员不含 `aisep:ApprovalRecord`、`aisep:AgentActivity`（否则任何一条新批准都会让模型"被修改"）；是 ADR 时，比较 ADR 主语及以它为主语的三元组直接引用的 Option、Force 等节点（`ad:relatedConcept` 指向的模型元素不展开）。范围内任一三元组不同，该对象即按 modified 计。元素的 `arch:inView` 三元组计入视图、不计入元素（与 §5.8 第 6 步"成员谓词归宾语"一致）：只改已批准元素的视图从属（把它放进或移出某张视图）不算修改该元素，不触发重批；视图不可被批准，视图属于已批准模型时由模型的比较范围看到（第四轮复评 R3，Albert 2026-11-21 拍板，ADR-017；残余见附录 C）。

**普通 PR 不要求带批准记录**（第四轮 R4-1，2026-11-20 用户拍板，ADR-016）：未经批准的模型改动可以进主线，在主线上推导为 Proposed，由"待批准关口"列出（Q2=A）。下列检查项只管带进来的批准记录是否合法（1–4、7）、合并结果（5）与已批准内容被改动（6）。已知限制：按 U4①，主线提交只能批 `GateRelease`；主线上的 Proposed 元素要过其他关口，须从主线拉分支、先有一个非批准提交（可以是空提交，使有效内容提交不在主线上）再批；被批准对象与主线一致由检查项 7 保证，所以这一步只是形式门槛。登记附录 C。

**检查项**（所有 PR，不分批准专用与普通；任一不满足 → 拒绝合并，报出 `offendingCommit` 或对象 IRI）：

1. **已有治理记录不可改**（第三轮 E，ADR-009"批准只能新增"）：PR 带进来的模型差异里，T 上已有的 `aisep:ApprovalRecord`、`aisep:AgentActivity` 主语出现 modified 或 removed → 拒绝。删一条 Rejected 记录同样拒绝。
2. **查哪些记录**（第三轮 D）：本 PR 新增的**全部合法**批准记录（合法 = `approval_problems` 为空，与推导同一个函数，G1）。唯一豁免：同一 PR 内被一条"同关口、`approves` 为其超集、`prov:generatedAtTime` 更晚"的新记录取代的记录。不按"推导时是否被采用"挑，也不引用推导函数的 tie-break：approvalState 按对象取各关口中最新的一条，跨关口的新记录会让旧关口的记录"不被采用"，按采用与否挑会放过它。approvalState 的单值语义不变，跨关口覆盖的其余绕过由第 6 项（U1）兜住。
3. **逐条核对**（对第 2 项选出的每条记录）：
   - evidence 必须是 40 位十六进制 commit；`sha256:` 形式 → 拒绝（第三轮 C：它无法做 `evidence..H` 的祖先判断，不能经合并进受保护分支）。
   - `prov:generatedAtTime` 晚于检查执行时（CI 运行时，或合并前重算时）的当前 UTC 时间加 5 分钟 → 拒绝（第三轮 C，防倒填为"未来时间"抢占最新；核对轮 6）。不与提交的 committer 时间比：它由提交者本地设置，可以伪造。
   - `approves` 中每个 IRI 必须在 evidence 快照的源图中存在，否则拒绝（核对轮 2：先批准一个还不存在的 IRI、之后再创建它，会让新内容未经评审就显示为 Approved）。
   - `decision = Approved` 的记录：在 evidence 快照上跑 `model_gate`（与第 3 步同一函数、同一快照口径 §3.3），FAIL → 拒绝，报出记录 IRI 与违规；Rejected 不查。同一 evidence 的结果可缓存（第四轮 R4-4：第 3 步只拦经 MCP 的写入，手写记录可以批准一个 gate 不通过的版本，主线随后修好无关违规，合并结果 gate 就通过了）。
   - evidence 必须是 H 的祖先；`evidence..H` 跑批准提交判据。范围只含分支这一侧的提交，不含合并时产生的合并提交本身。批准后把主分支合进本分支（含网页上的 Resolve conflicts，它把整个目标分支合进 PR 分支），范围里会出现合并提交，同样被拒，要求在新的提交上重新过关口：以合并后的提交为 evidence 的新记录按第 2 项取代旧记录后可以通过（合并提交不在新记录的 `evidence..H` 内；第四轮 G4-3）。
   - evidence 的有效内容提交（第 1 步）是 T 的祖先或等于 T（主线提交）→ 只能是 `GateRelease`、不带 `aisep:activity`（U4①；核对轮 4）。新增的 `GateRelease` 记录：evidence 必须是 T 的祖先或等于 T，且只能出现在批准专用 PR 里（第三轮 O）。
4. **新增活动核对**（第三轮 Q）：本 PR 新增的每条 `aisep:AgentActivity`，重算 `merge-base(aisep:headCommit, T)`（多个 → 拒绝）必须等于其 `aisep:baseCommit`，`aisep:branch` 必须等于 PR 源分支名（`pull_request.head.ref`）。只核对被第 2 项选出的记录经 `aisep:activity` 引用的活动；只被已取代记录引用的活动不重算 baseCommit，`aisep:branch` 仍须相等（第四轮 G4-6：批准后另一个 PR 把本分支的祖先提交合进主线，重算值会变，活动文件又不能改，只能在新提交上重批）。
5. **合并结果 gate**（U3）：在 M 上跑一次 `model_gate`，FAIL → 拒绝合并。批准期间主线可能前进，两边各自 PASS 不保证合并后 PASS。
6. **改动已批准元素须重批**（U1，普通 PR）：PR 带进来的模型差异里 removed 的元素若在 T 上推导为 Approved → 一律拒绝，不论有无覆盖记录，提示改用 `owl:deprecated` + `dcterms:isReplacedBy` 退役（Q6④、核对轮 1；第四轮 G4-2：原文把 removed 与 modified 并列，与第 10 步矛盾）。退役本身给元素加了三元组，按 modified 处理，同样须同 PR 内一条 Approved 覆盖记录；推导为 Superseded 时，生效记录仍按"各关口合法记录中时间最晚的一条"取（第四轮复查）。modified 的元素，若在 T 上推导的 approvalState = Approved，本 PR 必须有一条新增、且通过第 3 项逐条核对的合法批准记录覆盖它（`approves` 含它），否则拒绝。覆盖记录须为 `decision = Approved`，关口不限（approvalState 不分关口，§6.6）：Rejected 记录不算重批（第四轮 R4-2，用户拍板）。另在 M 上用推导同一函数（`derive_approval_state`）核对：该对象的生效记录（各关口合法记录中 `prov:generatedAtTime` 最晚、非歧义的一条）必须是这类覆盖记录之一，否则拒绝，须在分支头上重新批准、让新记录晚于 M 上已有的记录（第四轮 R4-3：防把新记录回填到旧批准之前，合并后旧批准仍生效）。在 T 上推导为 Approved、但 T 的源图里不存在的 IRI（预先批准），若本 PR 新增（added）它，同样须重批（核对轮 2）。模型、ADR 按上文"对象的比较范围"判定是否被修改（核对轮 3）。不改元模型，只在 CI 拦截。
7. **被批准内容与合并结果一致**（核对轮 5；所有 PR 共用，并入原批准专用 PR 的第三轮 I 规则）：第 2 项选出的每条记录，其 `approves` 中每个对象（按"对象的比较范围"展开）在 evidence 快照中与在 M 中的源图三元组必须相同，不同 → 拒绝，要求在新的提交上重新批准。后果：普通 PR 把主线合进分支后，合并前的批准因第 3 项失效，须以合并后的提交为 evidence 重批（第四轮 G4-3 更正原句"普通 PR 不能把主线合进分支"）；主线改了同一对象时，须基于新主线重开分支再批，或接受拒绝。
8. **治理记录不能是空白节点**（2026-11-22 取证疑点一）：PR 头 H 与合并结果 M 的模型源文件里，凡空白节点的 `rdf:type` 是 `aisep:ApprovalRecord`、`aisep:AgentActivity` 或其子类（子类按 M 上的模块与模型文件取闭包，同一文件里作子类的空白节点也算），本身就是这样的空白节点子类，或带这两类定义域的谓词（M 上声明 `rdfs:domain` 为这两类或其子类的谓词，至少含 `aisep:gate`、`aisep:decision`、`aisep:approvedBy`、`aisep:approves`、`aisep:evidence`、`aisep:activity`、`aisep:sessionRef`、`aisep:branch`、`aisep:baseCommit`、`aisep:headCommit`）→ 拒绝（`governance-blank-node`）。这里说的是被恰好一个三元组引用、不成环的空白节点；无人引用、被共享或成环的空白节点使图差异算不出，按第 1 步末尾的失败关闭报 `check-error`，不报本项原因码。理由：图差异把被引用的空白节点并进引用方的签名（§5.8），这样的记录不会被第 2 项选出，第 3、4 项都不执行，第 1 项也保护不到它。本项不依赖 gate：L1 另把空白节点的记录、活动，以及 `arch:inModel` 不指向 `arch:Model` 的记录、活动判为违规并让推导忽略它（元模型规范 §6.6、§6.7），第 5 项因此也会拒绝；两者各自成立。
9. **治理记录的类型只能写在 `models/` 下**（#105 评审）：合并结果 M 载入的模块或 vendor 文件里（即推导能看到的那些），凡给某个主语声明 `rdf:type` 为 `aisep:ApprovalRecord`、`aisep:AgentActivity` 或其子类 → 拒绝（`governance-type-outside-models`）。理由：推导在全部图的并集上认类型，第 1–4 项只读 `models/` 下的源图，类型写在模块或 vendor 里的记录不会被第 2 项选出，第 1、3、4 项都不执行。第 1–4 项识别记录与活动时，类按 T 与 M 上下文（模块、vendor、模型文件）的 `rdfs:subClassOf*` 闭包取，与推导同口径（#105）。本项不依赖 gate：模型文件不能给元模型术语加三元组的 R1 规则另会让第 5 项拒绝；两者各自成立。
10. **已有记录的批准人不能改类型或删除**（PR #132 评审 N1，Albert 2026-11-26 同意）：目标分支 T 的模型源文件里被任一 `aisep:approvedBy` 引用的 IRI，若在 M 的模型源文件里不再作主语出现 → 拒绝（`governance-approver-removed`）；仍在、但推导判定它能否当批准人的结论（`rdf:type` 连同这些类沿 `rdfs:subClassOf` 的全部祖先：是 `arch:Stakeholder` 且不是 `aisep:AIAgent`；模型源文件、模块与 vendor 里写的都算）与 T 上不同 → 拒绝（`governance-approver-retyped`），例如改成 `aisep:AIAgent`、去掉 `arch:Stakeholder`、在模块里给它加类型 `aisep:AIAgent`、给它的类加父类 `aisep:AIAgent`。不改变这一结论的类型改动不拒，例如追加一个合法子类型、在模块里给 `arch:Stakeholder` 加无害的父类（#136 评审）。理由：这类改动让引用它的已有记录变为不合法，推导不再认它，已有的 Rejected 可能因此失效、状态变成 Approved；它不改记录本身，第 1 项管不到。改标签等不动类型的改动、新增干系人和新增记录都不受影响。本项不依赖 gate：第 5 项另会因记录不合法而拒绝；两者各自成立。本项属于 ADR-019 第 2 款治理加固冻结的例外，经 Albert 2026-11-26 同意（见 ADR-024 补记）。

**合并前重算**（U3）

不开"要求分支最新"，不用合并队列（个人账号的 private 仓库用不了合并队列，平台事实见文末"第三轮"）。不开"要求分支最新"时，目标分支前进不会让必需检查自动重跑，CI 的通过结论可能只对旧的 T 成立。所以：执行合并的人（按 AGENTS.md「分支与合并」第 2 条，目前由协调会话代合并）在 `gh pr merge` 之前，先 fetch，取当前 `refs/heads/<主分支>` 为 T，用同一个检查脚本重跑上面全部检查项（含合并结果 gate），不过不合。脚本已实现（`aisep/mergecheck.py`，附录 D）；重算、复核目标分支、合并后核验的具体命令写在 AGENTS.md 合并条款（ADR-017）。残余风险：绕过脚本直接点网页合并按钮时，合并结果 gate 可能只对旧主线有效（§9 附录 C）。

重算与合并之间没有原子绑定（第四轮 R4-11）：平台的合并接口只能锁 PR 头（`gh pr merge --match-head-commit H`），锁不了目标分支头，重算通过后、合并执行前目标分支仍可能前进。按以下流程把窗口压到最小，余下的登记为残余风险（§9 附录 C）：① 合并串行，同一时刻只有一个执行合并的会话；② 合并命令带 `--match-head-commit H`，执行前再 `git ls-remote` 一次目标分支，不等于重算用的 T 就重来；③ 合并后核验：取新的主线头 M'，确认其第一父等于 T、第二父等于 H；不等则对 M' 重跑合并结果 gate 与检查项 6、7、8、9（第 8、9 项只扫 M'），不过就立即开 revert PR 并报告。

**批准专用 PR**（R2-15，防死循环；第三轮 B、U4② 收紧）

批准分支的 PR 若也要求先过关口，就会再产生一条批准、再开一个 PR。CI 先判定，以下全部满足 → 批准专用 PR：

1. 范围 `git rev-list H ^T` 非空，且整段满足批准提交判据（无合并提交；每个提交满足第 1 步的 (a)(b)(c)）；
2. 至少一条新增 `aisep:ApprovalRecord`；
3. 每个新增的 `aisep:AgentActivity` 都被本 PR 新增的某条记录经 `aisep:activity` 引用（只含活动的提交不算）；
4. evidence 为主线提交（按有效内容提交判定，第 1 步）的新增记录只能是 `GateRelease`、不带活动（U4①；核对轮 4）。

批准专用 PR **只免"再过 AISEP 关口"**：上面"合并时校验"的全部检查项、合并前重算和下文的发布标签检查照跑。第三轮 I（只能批准与主线当前内容一致的版本，内容已变须重新选 R）已并入检查项 7：批准专用 PR 的 M 只比 T 多记录文件，"evidence 快照与 M 一致"即被批准对象在 `evidence..T` 之间未被修改或删除（核对轮 5）。不满足判定条件的按普通 PR 处理。判定由 CI 执行，负例见 T39。

批准专用 PR 按 ADR-021 第 1 款合并：协调会话机械核对它只含一个从被批准提交拉出的合法批准提交、`mergecheck` 通过后即合并，不需要独立评审（原为「仍须人工 PR 批准」，U4②）。信任模型同 §4：判据只验证提交的形状，不验证批准是否真由工作台和真人做出；有写权限的人或代理照样能手写一个合法形状的批准提交，挡住它的是「AI 不得新增批准记录」的硬规则与分支保护。不引入签名或托管平台审批证明（第三轮 A 部分接受）。

**发布关口**（R2-15 已拍板：短命批准分支 + PR，受保护分支不开例外；第三轮 J、K、L、N 修订）

1. 人在关口页选定**被发布的那个主线提交** R（mainRef 上的某个提交，不一定是最新）。工作台（或会话脚本，见第 5 步）从 R 拉分支并检出：`git worktree add -b approval/release-{R 前 7 位}-{yyyymmddHHMMSS} <目录> R`（时间取 UTC，第三轮 L），目录在 `--allow-root` 之下；同名分支已存在 → `worktree add` 失败，报错由人处理。**必须从 R 拉**：从主线最新提交拉时，R 之后的主线提交落在 R..分支头之间，第 1 步报 `STALE_HEAD`；绕过 MCP 造出来的分支也会被合并时校验拒绝。
2. 调 `record_approval`：`gate: GateRelease`，`branch` = 该批准分支，`headCommit` = R，不带 `activity`。分支上只有这一个批准提交，evidence = R。合并时校验对它同样适用：R..分支头只有这一个批准提交。
3. **只有 `decision = Approved` 才打标签**（第三轮 J）：工作台（或会话脚本）给 R 打 `release/{yyyymmdd}-{R 前 7 位}`（批准日期，UTC；也可另用版本号 `release/v…`）。同名标签已存在：剥离到 commit 后指向 R → 幂等复用，不重建；指向别的提交 → 报错由人处理（第三轮 L）。`Rejected` 不得创建 release 标签。推送分支（和新建的标签），开 PR。PR 按批准专用 PR 处理（ADR-021 第 1 款：机械核对通过后合并，不需要独立评审），合并后删分支。PR 关闭未合并时不自动删标签：遗留的 release 标签由人清理，登记为残余风险（§9 附录 C；核对轮 7 取消第三轮 K 的"自动删除"）。标签是对外的发布指针；R 的可达性由主线保证（R 是主线提交），不靠标签防 GC（第三轮 N）。
4. **发布标签检查**（CI，合并前重算同跑）：PR 新增的每条 `decision = Approved` 的 `GateRelease` 记录，远端都要有一个名字合规（`release/{yyyymmdd}-{evidence 前 7 位}` 或 `release/v…`）、**剥离到 commit 后**等于其 evidence 的标签（取 `git ls-remote` 的 `^{}` 行，或 `git rev-parse <tag>^{commit}`；附注标签直接比较标签对象 sha 会误判），否则失败。`Rejected` 记录不要求标签。标签可被移动、删除：`release/*` 应以 tag ruleset 禁止删除与移动（private 仓库需 GitHub Pro 及以上），未配置时为残余风险（§9 附录 C）。不采纳"合并后由可信流程原子创建标签"：要新增一套机制（第三轮 K 部分接受）。
5. MCP 只做第 2 步的一次提交；拉分支、打标签、推送、开 PR 由工作台或会话脚本做，MCP 不推送、不打标签、不开 PR。工作台模型现行做法（ADR `workbench:adrReleaseStepsBySessionScript`，2026-11-25）：工作台前端不做 git 写操作，这几步由会话经 `$PY -P tools/pyrun.py aisep.release prepare|publish` 调用 `aisep/release.py` 完成；R 取 prepare 时 origin/main 的最新提交，分支在进入关口页前拉好（第 1 步「人选定 R」由此收窄为只能发布最新提交，关口页比对钉住的头与 origin/main 最新提交）；publish 打标签前对分支头跑与合并时相同的 `mergecheck.merge_check`；脚本只在记录 `decision = Approved` 且 evidence 等于 R 时打标签，批准记录仍只由人在关口页做出。

**输出**

```jsonc
{ "approval": { "iri": "…/approval-20261120093015-architecture-9c41e07", "file": "models/procurement/governance/approval-20261120093015-architecture-9c41e07.ttl" },
  "activity": { "iri": "…/activity-20261120093015-9c41e07", "reused": false },
  "evidence": "40hex", "baseCommit": "40hex", "commit": "新提交 sha", "branch": "feat/x",
  "duplicate": false,
  "gate": { "result": "PASS", "summary": { … } },
  "derivedApprovalState": [ { "iri": "…/quoteApproval", "before": "Proposed", "after": "Approved" } ],
  "findings": [] }
```

`derivedApprovalState`：在新提交上推导一次，**只描述 `branch` 上的状态**，供关口页显示"本次批准生效"。主分支要等合并后才变；工作台"待批准关口"不用它改写主分支那一行（§2）。

**错误**：`MODEL_NOT_FOUND`、`GATE_UNKNOWN`、`APPROVER_NOT_ALLOWED`、`AGENT_NOT_ALLOWED`、`ELEMENT_NOT_FOUND`（approves 目标在 headCommit 上不存在）、`INVALID_ARGUMENT`、`REF_NOT_FOUND`、`STALE_HEAD`、`STALE_BASE`、`AMBIGUOUS_MERGE_BASE`、`NO_MERGE_BASE`、`INVALID_DATETIME`、`ACTIVITY_TIME_ORDER`、`GATE_FAILED`、`WRITE_REJECTED`、`BRANCH_NOT_CHECKED_OUT`、`WORKTREE_NOT_FOUND`、`PATH_OUTSIDE_ROOT`、`DETACHED_HEAD`、`DIRTY_WORKTREE`、`CONFLICT`、`COMMIT_FAILED`、`LOCKED`、`MODULES_NOT_IN_REF`。

### 5.10 `model_set_labels`（对 §8.3 的扩展）

用户在另一会话拍板加入（2026-11-20），合并时并入，原草案名 `model.set_labels`。规范 §3"slug 一经创建不改：改名只改标签"的唯一写入口：只改名称、英文名和定义，不动 IRI、类型和关系。改类型仍是"不在本版"（§1）。

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `iri` | ✔ | 元素或关系的 IRI（完整 IRI 或 `slug:local`，§5.0） |
| `prefLabel` | — | 新的 `skos:prefLabel "…"@zh`，替换现有的全部 `@zh` 名称；不接受空串（LabelShape 要求恰好一个 `@zh` 名称） |
| `altLabel` | — | 新的 `skos:altLabel "…"@en`，替换现有的全部 `@en` 别名；传 `null` 表示删除 |
| `definition` | — | 新的 `skos:definition "…"@zh`，替换现有的 `@zh` 定义；传 `null` 表示删除 |
| `dryRun` | — | §5.1 |

- 字段名与标签约束都与 `model_add_element` 一致（§5.2）。三个字段至少给一个，否则 `INVALID_ARGUMENT`；未给出的字段保持不变。别的语言的标签不动。
- 不接受 `file`：改的是主语已有的三元组，位置由现有文件决定。被替换的三元组在哪个文件，新值就写回哪个文件；要新增一个原来没有的属性（如第一次加定义）时，写进该主语 `rdf:type` 三元组所在的文件。

**前置检查**
- `iri` 是本仓库某个模型的成员 → 否则 `ELEMENT_NOT_FOUND`（`details.candidates` 同 §5.7）。
- 目标是 `aisep:ApprovalRecord` 或 `aisep:AgentActivity` → `PROTECTED_RESOURCE`：批准历史只追加不修改，改结论要写一条更晚的记录（§6.6、R3）。
- 要改的三元组在别的模型目录里 → `PROTECTED_RESOURCE`（写入方不改别人的模型，同 §5.5 第 4 步）。

**执行**：走 §5.1 第 1–10 步。文本编辑用 §5.1 的主语块词法器，只重写含被替换三元组的那几个块；第 6 步的图等价断言照常生效。

**幂等**：给出的值与现有值完全相同 → 成功，`changed: false`，文件不变。

**输出**：`{ iri, changed, before: {prefLabel, altLabel, definition}, after: {prefLabel, altLabel, definition}, filesChanged: [{path, sha256Before, sha256After}], findings, preexistingViolations }`。`findings` 里每条带 `preexisting`（§5.1 第 5 步）。

**错误**：`ELEMENT_NOT_FOUND`、`PROTECTED_RESOURCE`、`INVALID_ARGUMENT`、`WRITE_REJECTED`、`PARSE_FAILED`、`EDIT_UNSAFE`、`NOT_A_WORKTREE`、`LOCKED`、`CONFLICT`。

**校验层**：候选图 L0–L2。会用到的规则：LabelShape（`modules/aisep-core/shapes.ttl` 第 73 行，恰好一个 `@zh` 名称）、G7 闭世界谓词（`l1_closed_predicates`）。

**对 diff 的影响**：改名后 `model_diff` 报该元素 `modified`，`changedPredicates` 只含被改的标签谓词（T15 已覆盖"只改 prefLabel"）。

### 5.11 `model_branches`（工作台入口）

2026-11-21 加入（L7）。工作台首页「待批准关口」区据此列出有模型改动的分支，整行链接到该分支的关口页。只返回 Git 事实，不算差异、不跑 gate；进度阶段由工作台自己推导。实现在 `aisep/branches.py`，契约测试 `aisep-mcp/tests/test_l7_model_branches.py`。

**输入**：只有通用的 `repo`（§5.0）。主分支取服务器的 `--main-branch`，按 §3.3 的规则解析（先远端跟踪分支）。

**输出**：`{ branches: [{branch, head, remoteHead, unpushed, mergedIntoMain, hasModelChanges}], main: {ref, commit} }`。`branches` 是全部本地分支（`refs/heads/*`），按名字排序，主分支自己也在里面；工作台自己筛选。

| 字段 | 说明 |
|---|---|
| `branch` | 本地分支短名（不带 `refs/heads/`），与 `governance_record_approval` 的 `branch` 入参同一写法 |
| `head` | 本地分支头，40 位十六进制 |
| `remoteHead` | `refs/remotes/origin/<branch>` 的提交；没有这个远端跟踪分支时为 `null` |
| `unpushed` | 本地分支头不是 `remoteHead` 的祖先（本地有远端没有的提交）时为 `true`；没有远端跟踪分支也算 `true` |
| `mergedIntoMain` | 本地分支头是主分支（`main.commit`）的祖先 |
| `hasModelChanges` | 从主分支与分支头的 merge-base 到分支头，改动了 `models/` 下的 `.ttl`（`diff-tree`，不认改名）；两者没有共同祖先时看分支头是否含 `models/` 下的 `.ttl`。已合入的分支通常为 `false` |
| `main` | 解析出的主分支：`ref` 为完整引用名，`commit` 为其提交 |

**只读、离线**：只用 plumbing 命令（`for-each-ref`、`merge-base`、`diff-tree`、`ls-tree`），不改工作区、索引和引用，**不 fetch**。远端跟踪分支是上次 fetch 留下的样子；要看远端最新状态，由调用方先 fetch。分支 worktree 里未提交的改动不算（看 `model_diff` 的 worktree 模式）。

**错误**：`NOT_A_GIT_REPO`、`PATH_OUTSIDE_ROOT`、`REF_NOT_FOUND`（找不到主分支）。

### 5.12 `model_set_attributes`（对 §8.3 的扩展）

Albert 2026-11-25 放行动作机制阶段 A，本工具随之加入：新增为独立工具，不改 `model_set_labels` 的契约，多值谓词按整体替换（这几点是调研报告的推荐，Albert 尚未逐条复核）。改已存在元素或关系的非标签属性（如 `aisep:priority`、`aisep:gherkin`、`aisep:path`）的写入口，是 `model_set_labels` 模式的平移。不动 IRI、类型、所属模型和关系端点；改类型仍是"不在本版"（§1）。用法与组合见 `docs/actions.md`。

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `iri` | ✔ | 元素或关系的 IRI（完整 IRI 或 `slug:local`，§5.0） |
| `set` | 条件 | `[{predicate, value: {iri} \| {value, datatype?, lang?}}]`，`value` 的形状与 `model_add_element` 的 `attributes` 相同（§5.2）。**按谓词整体替换**：写入后，该主语在这个谓词上的值恰好是 `set` 里这个谓词的那几项。多值谓词把每个值各写一项、`predicate` 相同；重复的项只算一次 |
| `unset` | 条件 | `[predicate]`，删除该主语在这个谓词上的全部值 |
| `dryRun` | — | §5.1 |

- `set`、`unset` 至少给一个且不能都为空，否则 `INVALID_ARGUMENT`。同一个谓词同时出现在 `set` 和 `unset` 里 → `INVALID_ARGUMENT`。没有出现的谓词保持不变。
- **不接受的谓词**（出现在 `set` 或 `unset` 里 → `INVALID_ARGUMENT`，`details.rejectedFields` 为所在字段）：`rdf:type`、`arch:inModel`、`arch:source`、`arch:target`，以及 `skos:prefLabel`、`skos:altLabel`、`skos:definition`（这三个走 `model_set_labels`，那里有语言与长度约束）；还有 `arch:inView`：视图成员关系的增删归视图（§5.8 第 6 步"成员谓词归宾语"），视图写工具不在本版（§1）。
- **其余谓词合不合法不另写白名单**，由候选图上的 L1 规则判定，与 `model_add_element` 的 `attributes` 同一口径：闭世界不允许的谓词（G7）、手写的 `arch:approvalState`（§6.6）都表现为新增违规 → `WRITE_REJECTED`。
- 不合法的 IRI、语言标签或值，以及违反 §5.2 `attributes` 那五条值形状规则（控制字符、`lang` 与 `datatype` 同给、空 `lang`、空 `datatype`、`_:` 空白节点名）→ `INVALID_ARGUMENT`。没有声明过的前缀不在此列：`x:y` 按 `slug:local` 展开（§5.0），得到的谓词没有声明，结果是 `WRITE_REJECTED`。
- `value.value` 给 JSON 数或布尔值时与 §5.2 的 `attributes` 一样，写成 `xsd:integer`、`xsd:double`、`xsd:boolean` 字面量。字符串里的换行与回车（U+000D）转义后写入，读回来逐字相同。
- 不接受 `file`：值没有变的三元组留在原处；新值写进被替换的三元组所在的文件，被替换的值分布在多个文件里时，写进其中第一个文件（按仓库相对路径的字符串顺序排在最前的那个）；这个谓词原来没有被替换的值时，写进该主语 `rdf:type` 三元组所在的文件。

**前置检查**
- 目标是 `arch:Model` → `PROTECTED_RESOURCE`（模型本身不经写工具修改，同 §5.5）。
- `iri` 是本仓库某个模型的成员 → 否则 `ELEMENT_NOT_FOUND`（`details.candidates` 同 §5.7）。
- 目标是 `aisep:ApprovalRecord` 或 `aisep:AgentActivity` → `PROTECTED_RESOURCE`：批准历史只追加不修改（§6.6、R3）。
- 该主语的三元组有一部分在别的模型目录里 → `PROTECTED_RESOURCE`（写入方不改别人的模型，同 §5.10）。

参数错误先于目标检查报出。

**执行**：走 §5.1 第 1–10 步。文本编辑用 §5.1 的主语块词法器，只重写含被替换三元组的语句，或（新增一个原来没有的谓词时）该主语 `rdf:type` 所在的语句；第 6 步的图等价断言照常生效。被替换的值挂着空白节点、或语句不能安全改写 → `EDIT_UNSAFE`，不写。新写入的谓词、IRI 或数据类型在目标文件里没有对应前缀时写成完整 IRI，不往文件头加 `@prefix`。

**幂等**：每个给出的谓词的现有值集合都与要求的相同（`unset` 的谓词本来就没有值）→ 成功，`changed: false`，文件不变。

**输出**：`{ iri, changed, before, after, filesChanged: [{path, sha256Before, sha256After}], findings, preexistingViolations }`。`before`、`after` 以谓词的完整 IRI 为键，值是该谓词写入前、写入后的全部值，每个值的形状同输入的 `value`（IRI 展开为完整 IRI；`xsd:string` 的字面量不带 `datatype`），按固定顺序排列。只列 `set`、`unset` 里出现的谓词。`findings` 里每条带 `preexisting`（§5.1 第 5 步）。

**错误**：`ELEMENT_NOT_FOUND`、`PROTECTED_RESOURCE`、`INVALID_ARGUMENT`、`WRITE_REJECTED`、`PARSE_FAILED`、`EDIT_UNSAFE`、`NOT_A_WORKTREE`、`LOCKED`、`CONFLICT`。

**校验层**：候选图 L0–L2。

**对已批准元素**：写工具不拦，`gate` 照常 PASS；把关在合并，`mergecheck` 按图差异报 `unapproved-change-to-approved`（§5.9 的合并判据不因本工具改变）。

**对 diff 的影响**：`model_diff` 报该元素 `modified`，`changedPredicates` 只含值有变化的谓词。

### 5.13 `model_list_actions`（动作目录，规范外）

出处：Albert 2026-11-25 确认动作机制走「薄封装」方向，2026-11-26 放行阶段 C 时改选：动作定义建进元模型（新模块 `modules/ext-actions/`，参照 Palantir Foundry 的 Action type，只建定义、不建执行记录），目录从 RDF 读。本节与 §5.14 随之加入。字段名、错误码名、词汇细节是实现时的取舍，Albert 没有逐条定过。用法见 `docs/actions.md`「动作目录」一节。

**动作是什么**：现有写工具的具名组合，写成元模型里的 `aisep:ActionType` 个体，放在扩展模块 `modules/ext-actions/` 的 `catalog.ttl`（词汇在 `onto.ttl`，L3 形状 EA1–EA10 在 `shapes.ttl`）。`catalog.ttl` 列在模块清单的 `aisep:loads` 里，所以 `gate` 会用 `shapes.ttl` 校验它，`model_query` 也能查到有哪些动作。动作有 IRI（形如 `aisep:Action<名>`），调用时用短 id（`dcterms:identifier`）。动作个体不是模型元素：不在 `arch:Element` 之下，没有 `arch:inModel`，也没有批准状态。动作是**推荐通道**，不是唯一通道：逐个调写工具、直接编辑 `.ttl` 照旧允许，`gate` 与合并核对不知道改动是否经动作做的。动作不产生审批项，不在模型里留执行记录；`model_apply_action` 的每次调用（含 `dryRun` 与被拒）由服务端调用日志记一行（§3.6，ADR-031），那不是模型对象，不可经 MCP 查询。

**两个工具的形状是固定的**：目录增删改动作，`tools/list` 都不变（参数 schema 由本工具返回，不进 `inputSchema`）。

**输入**：无（`inputSchema` 为空对象）。读服务器所服务工作区（`--repo`，缺省为当前目录）里的 `modules/ext-actions/catalog.ttl`。

**输出**：`{ catalogVersion, operations, actions: [...] }`。`catalogVersion` 是模块清单的 `owl:versionInfo`。`operations` 是执行器认识的基本动作对应的写工具，固定为 `model_add_element`、`model_add_relationship`、`model_remove`、`model_set_attributes`、`model_set_labels`（按名称排序；用的是 §5.2、§5.3、§5.5、§5.12、§5.10 的计划函数）。`actions` 按动作 IRI 排序，每项：

- 有效的定义：`{ id, iri, title, description, version, valid: true, params, iriParams, destructive, requiresPlanDigest, guards: [{id, hint}], steps: [{id, op}], definitionDigest }`。`params` 是由 `sh:parameter` 推出的 JSON Schema（`type: object`、`additionalProperties: false`，每个参数都是字符串，没标 `sh:optional true` 的进 `required`）；`iriParams` 列出带 `sh:nodeKind sh:IRI` 的参数；`steps[].op` 是该步基本动作对应的写工具名；`destructive` 与 `requiresPlanDigest` 都由执行器按「含删除步骤」推导，目录里没有能改低它的字段；`definitionDigest` 见下，计入 §5.14 的 `planDigest`。
- 无效的定义：`{ id, iri, valid: false, problems: [中文原因…] }`（取不到唯一的字符串 id 时 `id` 为 `null`，空白节点的动作 `iri` 为 `null`）。每条原因以规则号开头（EA*、X*）。一条定义坏了只影响它自己：执行器逐条校验，单条校验里的任何异常只把这一条判无效；其他动作照常列出、照常可执行，两个工具都不因此报 `INTERNAL`。

目录每次调用都从磁盘重读，不缓存。`catalog.ttl` 不是合法 Turtle → `PARSE_FAILED`（`details.file` 点名文件；这时 `gate`、pre-commit 同样失败）。`modules/ext-actions/` 不存在（很老的检出）→ `actions: []`，不报错。

**定义的写法**（`catalog.ttl`，前缀 `ap:` = `https://aisep.example/ont/ext-actions#`，参数键在这里，不声明为属性）：

| 部分 | 写法 | 规则 |
|---|---|---|
| 动作 | `aisep:Action<名> a aisep:ActionType` | IRI 形如 `aisep:Action<驼峰名>`（EA1） |
| id | `dcterms:identifier` | 恰好一个，`^[a-z][a-z0-9-]{0,63}` 且到此为止（不放过结尾换行），目录内唯一（重复的都判无效）（EA2、X9） |
| 标题、说明 | `skos:prefLabel`@zh 恰好一个、`skos:definition`@zh 至多一个 | EA3；列表输出里叫 `title`、`description` |
| 版本 | `owl:versionInfo` | 恰好一个，形如 `1.0.0`（EA4）；历史靠 Git |
| 参数 | `sh:parameter [ sh:path ap:<名> ; sh:datatype xsd:string 或 sh:nodeKind sh:IRI ; sh:optional true? ; sh:description "…"@zh? ]` | 参数名 = `sh:path` 的本地名（SHACL 的约定），本动作内唯一；只认这几个键（EA8、X7）。IRI 参数只接受完整 IRI，且在 `https://aisep.example/model/<模型>/<本地名>` 之下（本地名限 `[A-Za-z0-9._~%-]`），不接受 `slug:local` 短写 |
| 前置检查 | `aisep:guard [ a sh:SPARQLAskValidator ; dcterms:identifier "…" ; sh:ask "ASK { … }" ; sh:message "…"@zh ]` | `sh:ask` 是只读 SPARQL ASK 正文（不带 `PREFIX`，前缀由执行器补；不许 `SERVICE`），**结果为 true 即通过**（SHACL 原义）；查询里写作 `$名` 的本动作参数被预绑定（SHACL-SPARQL 的约定），预绑定的变量须出现在图模式里（只出现在 `FILTER` 或 `FILTER NOT EXISTS { … }` 里都不行，例如 `ASK { FILTER(isLiteral($label)) }` 判无效；要写成 `$x a ?type . FILTER NOT EXISTS { … }`）；加载时用哑值试跑一次，跑不了即判无效（EA9、X8）。`sh:message` 是中文修法，列表与错误里叫 `hint` |
| 步骤 | `aisep:steps ( <步骤> … )`，每步 `[ a aisep:ActionStep ; dcterms:identifier "…" ; aisep:invokes <基本动作> ; aisep:binding … ]` | 非空的良构 `rdf:List`，按表的顺序执行；步骤 id 本动作内唯一；基本动作只能是 `aisep:BasicAddElement`、`aisep:BasicAddRelationship`、`aisep:BasicSetLabels`、`aisep:BasicSetAttributes`、`aisep:BasicRemove` 之一（EA5、EA6、X2、X3） |
| 绑定 | `aisep:binding [ aisep:argument "<入参名>" ; <取值来源> ; aisep:attributePredicate <谓词>? ]` | 取值来源恰好一个：`aisep:constant <IRI 或字面量>`、`aisep:fromParameter ap:<名>`（本动作的参数）、`aisep:fromStep <前面某步>`（取该步产出的 IRI，删除步骤不产出）、`aisep:modelOf ap:<名>`（该 IRI 参数所指成员的 `arch:inModel`）（EA7、X4、X5） |

入参名与必填入参同对应写工具的参数（删除步骤只有 `iri`，执行器固定按级联规划；`model_set_attributes` 的 `set`、`unset` 至少绑定一项）。标量入参每个名字至多一个绑定；`attributes`、`set` 每项一个绑定，须带 `aisep:attributePredicate`，值是字面量还是 IRI 由参数类型或常量本身推出；`unset` 每项是 `aisep:constant <谓词 IRI>`。列表项按（谓词，值）排序后交给写工具，与书写顺序无关。可选参数没给时，引用它的标量入参或列表项省略（X3）。

所有嵌套节点（表节点、步骤、绑定、参数、guard）都须是空白节点，一个空白节点只能属于一个动作（X10）。**`definitionDigest`** = sha256（从动作 IRI 出发、沿宾语里的空白节点展开得到的三元组，空白节点按 RDF 规范化，N-Triples 行排序）。IRI 宾语不展开，所以改 `onto.ttl` 里基本动作的标签不会让 `planDigest` 失效；定义本身的任何改动（包括只改标题或说明）都会。

**加载校验同时拒绝「两步作用于同一个目标」的定义**（X6，判 `valid: false`，原因写进 `problems`），因为这类动作重放会被拒（§5.14「幂等」）：改已有资源的步骤（`BasicSetLabels`、`BasicSetAttributes`、`BasicRemove`）的 `iri` 取自本动作前一步的产出（`aisep:fromStep`）；两个这类步骤的 `iri` 取自同一个参数或同一个常量；删除步骤的 `iri` 与某个 `BasicAddRelationship` 步骤的 `source` 或 `target` 取自同一个参数或常量（级联会删掉那条新关系）。这一校验只看绑定本身：两个**不同**参数在调用时被填成同一个 IRI、`add_element` 的 slug 恰好等于同一动作里被删的 IRI，取决于调用时的值，加载时判不出来。X6 只由执行器判，`gate` 不知道它；仓库里的目录靠 CI 的 pytest（「仓库目录每条定义都有效」）挡在合并前。

`gate` 的 L3 用 `shapes.ttl` 判 EA1–EA10（SHACL Core 能说的结构）；执行器每次读目录都自己再判一遍同样的结构（X1，它不能假定 `gate` 跑过），再加 SHACL Core 说不了的 X2–X10。EA10 管模型文件：动作词汇（`aisep:steps`、`aisep:binding`、`aisep:argument` 等）写在模型元素上会在 L3 报 EA10。

**校验层**：无（只读目录，不读模型）。

**错误**：`INVALID_ARGUMENT`（多传了参数）、`PARSE_FAILED`（`catalog.ttl` 不能解析），以及定位工作区的 `NOT_A_GIT_REPO`、`PATH_OUTSIDE_ROOT`。

### 5.14 `model_apply_action`（执行一个动作，规范外）

出处同 §5.13。

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `action` | ✔ | 动作 id（`dcterms:identifier` 的短 id，不是 IRI） |
| `params` | — | 对象，按该动作的 `params` schema 校验；缺省为 `{}` |
| `dryRun` | — | §5.1 |
| `planDigest` | — | 上次 `dryRun` 返回的计划哈希。含删除步骤的动作实际执行时必填；其他动作给了也核对 |
| `repo` | — | §3.3 |

**执行顺序**

1. 读目录（`repo` 所指工作区的 `modules/ext-actions/catalog.ttl`）。没有这个动作 → `INVALID_ARGUMENT`（`details.available` 列出可用的 id）；定义无效 → `INVALID_ARGUMENT`（`details.problems`）。
2. 按 `params` schema 校验参数，再校验 IRI 参数（`iriParams`）的形状；不合规 → `INVALID_ARGUMENT`，`details.rejectedFields` 形如 `params.<名>`。参数只作为预绑定的项进入 guard 查询，不拼进查询文本。
3. 进入一次 §5.1 写入（加锁、读工作区、基线）。依次跑各步的计划函数；后一步在前一步结果的内存叠加上规划，与第二次工具调用看到的相同。中间结果只检查能否解析，不能 → `EDIT_UNSAFE`。步骤自己的拒绝原样抛出（`ELEMENT_NOT_FOUND`、`IRI_EXISTS`、`UNKNOWN_TYPE`、`PROTECTED_RESOURCE`、`REFERENCED` 等），`details.step` 标出是哪一步。可选参数没给时，引用它的入参或列表项省略；某步的必填入参因此缺失 → `INVALID_ARGUMENT`。
4. **判重放**：各步合并后的计划在当前工作区上无变化（每一步都无变化，或各步改动相互抵消、每个文件合并后的文本与工作区逐字节相同）→ 成功，`changed: false`，不重写文件，**不跑 guard**。只有部分文件相互抵消时，这些文件不计入改动。
5. **跑 guard**：每条 guard 的 ASK 结果为 false 即失败 → `PRECONDITION_FAILED`，零写入，`hint` 是第一条失败 guard 的修法（`sh:message`），`details.failedGuards: [{id, hint}]`。IRI 参数预绑定为 IRI，字符串参数预绑定为普通字面量。guard 与 `aisep:modelOf` 都看动作开始时的工作区，不看前面步骤的产出。查询用到的可选参数没给时这条 guard 跳过。每条 guard 在 §5.6 的同一种无网络子进程里执行，限时 10 秒（同 `model_query` 的缺省 `timeoutMs`）：超时 → `QUERY_TIMEOUT`，零写入，`retryable: false`（guard 写法有问题，例如笛卡尔积，原样重试没有用，要改 `catalog.ttl`），`details: {action, guard}`；尝试联网 → `QUERY_NOT_READONLY`；子进程建立不了 → `INTERNAL`。
6. 算 `planDigest` = sha256（动作 id、`definitionDigest`、`params`、计划触及的每个文件改前与改后的 sha256）。带了 `planDigest` 而不等 → `PLAN_STALE`（相关模型文件、动作定义或参数在 `dryRun` 之后变了；定义的任何改动，包括只改标题或说明，都会让旧哈希失效）。含删除步骤、不是 `dryRun`、也没带 `planDigest` → `PLAN_REQUIRED`。这两种错误的 `details` 带 `planDigest`、`steps`、`files`，含删除步骤时另带 `cascade` 和 `impact`。它们在候选图判定之前抛出，所以不含 L0–L2 结论。
7. 把各步合并后的计划交回 §5.1 第 5–10 步：图等价断言、候选图 L0–L2 判定（只拒新增违规）、落盘。**一次动作就是一次写入**：工作区内全有或全无，不 `git add`、不提交。

**只判最终候选图，比逐步调用宽**：逐个调写工具时每一步的中间状态都要过 L0–L2；动作只把合并后的候选图判一次。中间状态有违规、最终合法的组合，动作能过，逐步调用不能。动作层不另写合法性判断：guard 只是提示，不是不变式，直接编辑或逐步调用不受它约束，`gate` 也不知道它。

**破坏性动作（含删除步骤，即 `aisep:BasicRemove`）**：删除步骤固定按级联规划（同 `model_remove` 带 `cascade: true`），有阻塞引用仍是 `REFERENCED`。必须两段式：先 `dryRun: true` 取 `planDigest`，再带它执行。`dryRun` 的返回附 `cascade`（级联闭包，`[{step, target, delete, detach, blockers}]`）和 `impact`（依赖闭包摘要：对每个删除目标跑 `model_impact`，`mode: depends`、`depth: 3`，最多 50 项，`[{focus, mode, depth, count, truncated, invalidModel, items}]`；`model_impact` 报错时该项为 `{focus, error}`）；`PLAN_REQUIRED`、`PLAN_STALE`、`REFERENCED` 的 `details` 也附 `impact`。**影响摘要只是提示**：它不计入 `planDigest`，在写入锁之外另读一次工作区，与计划不是同一份快照。`planDigest` 只保证执行的就是看过的那份计划，不代表批准；人的把关仍在关口。

**幂等（重放边界）**：重放判定是「合并后的计划在当前工作区上无变化」（第 4 步，按文件逐字节比较），所以同参数重放返回 `changed: false` 对各步互不覆盖的动作成立，对各步改动在最终文本上相互抵消的动作也成立。同一动作里先删后加同一 IRI、加元素后再改它这类组合，首次执行正常，重放会被拒（`PLAN_STALE`、`PLAN_REQUIRED` 或 `IRI_EXISTS`）。§5.13 的加载校验（X6）把能从定义上判出的这类组合判为无效，目录里不会出现。判不出的只有两类，都取决于调用时的值：调用方把两个**不同**参数填成同一个 IRI；`add_element` 的 `slug` 恰好等于同一动作里被删的 IRI。这两类首次执行的结果与依次调用写工具相同。重放时，合并后的文本与工作区逐字节相同（例如几步先后改同一 IRI 的名称，后一步覆盖前一步）就返回 `changed: false`，不重写文件；否则（例如涉及新增元素或删除步骤）重放可能被拒（`IRI_EXISTS`、`PLAN_STALE`、`PLAN_REQUIRED` 之一），零写入，不保证返回 `changed: false`。破坏性动作重放沿用 `model_remove` 的约定：目标已不在且带了 `planDigest` → `changed: false`，删除步骤的结果里 `alreadyAbsent: true`（此时不核对哈希的值）；不带 → `ELEMENT_NOT_FOUND`。

**输出**：在 §5.1 的通用字段（`changed`、`dryRun`、`filesChanged`、`findings`、`preexistingViolations`）之上：`action`（短 id）、`actionIri`（动作的 IRI）、`definitionDigest`、`destructive`、`steps: [{id, op, changed, result}]`（`op` 是写工具名；`result` 是对应写工具的结果：`iri`/`file`/`turtle`，改名称是 `iri`/`before`/`after`，改属性同 §5.12，删除步骤是 `target`/`plan`/`alreadyAbsent`）、`iris: {步骤 id: 产出的 IRI}`、`planDigest`（重放时回显入参）；含删除步骤时另有 `cascade`，`dryRun` 且有变化时另有 `impact`。

**参数里的特殊字符**：`}`、`>`、`;`、引号等只会得到 `INVALID_ARGUMENT` 或正常的 guard 结论，不会改变查询含义。字符串参数不另加限制，交给步骤对应写工具原有的检查；例如 `register-acceptance-criterion` 的 `gherkin` 经 `model_add_element` 的 `attributes` 写入，值里含回车（U+000D）时与直接调 `model_add_element` 一样返回 `EDIT_UNSAFE`，不写。

**错误**：`INVALID_ARGUMENT`、`PRECONDITION_FAILED`、`PLAN_REQUIRED`、`PLAN_STALE`、`QUERY_TIMEOUT`（guard 超时，不可重试），步骤对应写工具的全部错误（见 §5.2、§5.3、§5.5、§5.10、§5.12），以及 §5.1 的 `WRITE_REJECTED`、`PARSE_FAILED`、`EDIT_UNSAFE`、`NOT_A_WORKTREE`、`LOCKED`、`CONFLICT`。

**校验层**：候选图 L0–L2（只判最终状态）。

---

## 6. `aisep:AgentActivity` 定稿与 PROV-O

### 6.1 字段表

`aisep:AgentActivity ⊑ arch:Element, prov:Activity`。和批准记录一样不属于任何记法，是具体类。

| 字段 | 基数 | 取值 | 校验层 | 谁填 | 与 v0.4 草案相比 |
|---|---|---|---|---|---|
| `rdf:type aisep:AgentActivity` | 1 | — | L1 | 服务器 | 不变 |
| IRI | — | `{model}activity-{yyyymmddHHMMSS}-{headCommit 前 7 位}`（UTC，第四轮 R4-7），重名加 `-2`；必须是 IRI，不能是空白节点 | 写入层；L1 + EG25 | 服务器 | **新增** IRI 规则 |
| `arch:inModel` | 1 | 模型 IRI | L1 | 服务器 | 不变 |
| `skos:prefLabel` | 1 `@zh` | 缺省 `"AI 活动：{branch}"`，工作台传任务标题 | L1 | 客户端可给 | **写明**（元素通则本来就要求） |
| `prov:wasAssociatedWith` | 1 | `arch:Stakeholder` 的实例，或 `aisep:AIAgent` 的实例（Q4=C） | L1 + EG17 | 客户端 | **放宽**：可指向 `aisep:AIAgent` |
| `prov:startedAtTime` | 1 | 严格 xsd:dateTime | L1 + EG24 | 客户端 | 不变 |
| `prov:endedAtTime` | 1 | 同上；开始 ≤ 结束（按时区归一化，不带时区按 UTC） | L1 + EG24 | 客户端或服务器 | 不变 |
| `aisep:sessionRef` | 1 | 非空字符串，对元模型不透明 | L1 | 客户端 | 不变 |
| `aisep:branch` | 1 | 非空字符串 | L1 | 客户端 | 不变 |
| `aisep:headCommit` | 1 | `^[0-9a-f]{40}$`；= 被批准的 commit；批准记录 evidence 为 commit 时必须相等 | L1 | **服务器核对后填** | **写明**来源 |
| `aisep:baseCommit` | 1 | `^[0-9a-f]{40}$`；= merge-base(headCommit, 模型主分支) | L1 只查格式；是否等于 merge-base 由写入层保证（L1 不查 Git） | **只由服务器算** | **写明**来源 |
| 唯一性 | — | 一个 `(sessionRef, headCommit, branch)` 只有一条；同一 head 过多个关口复用 | 写入层 | — | **新增** |
| 不存 | — | 作用于哪些元素（由 `model_diff(baseCommit, headCommit)` 算）；进行中状态；编排器的其他字段 | — | — | 不变 |

### 6.2 PROV-O 怎么处理（Q4=C，已拍板）

| 选项 | 做法 | 好处 | 问题 |
|---|---|---|---|
| A 现状 | 不加载；AI 代理也建模成 `arch:Stakeholder` | 零改动 | 把 AI 写成利益相关方，语义不对；`approvedBy` 也接受 AI |
| B 整体 vendor PROV-O | 加载 W3C `prov-o.ttl` | 标准齐全 | G7 把"已加载本体声明的谓词"视为合法，`prov:used` 等全部放行，要另加黑名单；`prov:Agent` 实例不是 `arch:Element`，骨架规则要开例外 |
| **C 最小桩（已拍板）** | aisep-core 声明 `aisep:AIAgent ⊑ arch:Element, prov:SoftwareAgent`，再加一条对齐公理 `prov:SoftwareAgent rdfs:subClassOf prov:Agent`（与 PROV-O 原文同义，是对上游术语的断言，所以按 ADR-010 放在 aisep-core 的**对齐文件**里，不放 `metamodel.ttl`；aisep-core 的 `ownsNamespace` 不含 prov#）；**不**加载 PROV-O | `a aisep:AIAgent` 可直接写（AISEP 自有具体类，满足闭世界）；祖先链含 `prov:Agent`，原型 `AGENTS` 判定按祖先求交（`self.ancestors`），**接受侧不用改代码**；G7 白名单不变 | 只能用 PROV-O 的一个类子集 |

C 的附带决定（同在 Q4，已拍板收紧）：`aisep:approvedBy` **只接受人**（`arch:Stakeholder` 且不是 `aisep:AIAgent`），理由是原则五"人工把关"。代价：`approval_problems` 与 `activity_problems` 现在共用 `AGENTS`，要拆成两个集合；G1 要求每个谓词各自只有一个定义，L1、L3（EG13、EG17）和推导三处共用。新增 2 个非法夹具。

以上"接受侧不用改代码"是读代码得出的，**没有跑过**（只读边界不允许建夹具），列为验收 T28。T28 另断言：这条公理不会让 `prov:SoftwareAgent` 自己成为可直接实例化的类（`a prov:SoftwareAgent` 仍报未声明的具体类）。

---

## 7. 统一错误模型与发现项格式

### 7.1 两类错误

| 类别 | 载体 | 何时用 |
|---|---|---|
| 协议错误 | JSON-RPC `error`（`-32602` 等） | 只用于未知工具、请求本身不符合 `CallToolRequest` 结构。SDK 处理 |
| 工具执行错误 | 正常 `result`，`isError: true`，`structuredContent.error` | 其余全部：**入参校验失败（含传了不接受的字段）**、业务拒绝、引用不存在、违规、Git 失败。MCP 规范（2025-11-25 起）把入参校验错误明确归在这一类，模型才能读到原因并自我修正。由 §3.1 的入口装饰器产出，SDK 不会自动产出这个结构 |

```jsonc
{ "error": {
    "code": "WRITE_REJECTED",
    "message": "写入会新增 1 个 L1 违规，已拒绝：procurement:bpmnReview（bpmn:Task）不能用 am4:Serving 连接",
    "hint": "改用 arch:Refines 连到 am4 节点；或换一个同记法的关系类",
    "retryable": false,
    "details": { "findings": [ /* Finding */ ] } } }
```

**让代理能自我修正的四条规则**
1. `message`：中文一句话，点名对象（短名 + 类型），不写"invalid input"。
2. `hint`：下一次调用怎么改，点名工具和参数，不写"请检查"。没有可行建议时省略。
3. 有候选值就放进 `details.candidates`，省一次查询。
4. `retryable` 只对 `LOCKED`、`CONFLICT`（回滚时保留了文件（kept）、记录已被别的提交带走（taken）、撤回失败这三类除外，见 §7.2）、`WORKTREE_CHANGED`、`COMMIT_FAILED`（`index.lock` 被占用且已回滚时）、`QUERY_TIMEOUT`（`model_apply_action` 的 guard 超时除外，§5.14）为 true；其他原样重试没有意义。`PLAN_STALE` 不可重试：带同一个旧 `planDigest` 重试永远失败，要先重新 `dryRun`。

`content[0].text` 放同一句 `message` + `hint` + 发现项的 CLI 格式行，控制字符与行分隔符的转义同 §5.0。

### 7.2 错误码

| 类别 | 错误码 | 可重试 |
|---|---|---|
| 参数 | `INVALID_ARGUMENT`、`UNKNOWN_TYPE`、`ABSTRACT_TYPE`、`INVALID_DATETIME`、`ACTIVITY_TIME_ORDER`、`GATE_UNKNOWN` | 否 |
| 定位 | `MODULES_NOT_IN_REF`、`PATH_OUTSIDE_ROOT`、`NOT_A_GIT_REPO`、`NOT_A_WORKTREE`、`MODEL_NOT_FOUND`、`ELEMENT_NOT_FOUND`、`REF_NOT_FOUND`、`BRANCH_NOT_CHECKED_OUT`、`WORKTREE_NOT_FOUND` | 否 |
| 语义拒绝 | `PLAN_STALE`、`PLAN_REQUIRED`（§5.14）、`PRECONDITION_FAILED`（§5.14）、`STALE_BASE`、`WRITE_REJECTED`、`REFERENCED`、`CASCADE_REQUIRED`、`PROTECTED_RESOURCE`、`IRI_EXISTS`、`MODEL_INVALID`（G9）、`GATE_FAILED`、`APPROVER_NOT_ALLOWED`、`AGENT_NOT_ALLOWED`、`STALE_HEAD` | 否 |
| Git | `NO_MERGE_BASE`、`AMBIGUOUS_MERGE_BASE`、`DETACHED_HEAD`、`DIRTY_WORKTREE`、`COMMIT_FAILED` | `COMMIT_FAILED` 只在 `index.lock` 被占用、且已回滚时是；回滚未完成（`orphanApproval`）为否；`git add --intent-to-add` 失败遇到 taken 时不报 `COMMIT_FAILED`，报 `CONFLICT`（不可重试），见本表下 `COMMIT_FAILED` 一段 |
| 并发 | `LOCKED`、`CONFLICT`、`WORKTREE_CHANGED` | `LOCKED`、`WORKTREE_CHANGED` 是；`CONFLICT` 见表下 |
| 解析 | `PARSE_FAILED`、`EDIT_UNSAFE`、`DIFF_PARSE_FAILED`、`DIFF_BNODE_UNSUPPORTED`、`QUERY_FAILED`、`QUERY_NOT_READONLY`、`QUERY_TIMEOUT` | 只有超时是 |
| 其他 | `INTERNAL`（带 stderr 摘要） | 否 |

各工具 `outputSchema` 里 `error.code` 的枚举是上表全部错误码，只有 `PLAN_REQUIRED`、`PRECONDITION_FAILED` 例外：它们只由 `model_apply_action` 返回，只出现在它的枚举里（`aisep/errors.py` 的 `ACTION_CODES`），所以加入动作工具后，其余工具在 `tools/list` 里的条目与加入前相同。

**`CONFLICT` 的 retryable**：缺省为 true（`aisep/errors.py` 的 `RETRYABLE`）。三类为 false（已拍板）：**回滚时保留了文件**（kept：文件被钩子或编辑器改过而保留，原样重试会先撞上 `DIRTY_WORKTREE`，没有意义，§5.9 第 8 步）；**记录已被别的提交带走**（taken：带走它的提交还含代理的改动，要人判断，§5.9 第 7 步"风险"）；**撤回失败**（提交或 index 条目留在原处，要人处理）。kept 出口 `details` 带 `fileKept: true` 和 `recover`；taken 出口 `details` 带 `takenByCommit`（带走记录的提交），`details.commit` 只在已有本次批准提交 A 时给出 A。`record_approval`（`aisep/approval.py`）逐项：

| 情形 | 现场 | 可重试 |
|---|---|---|
| 记录文件已存在（`O_EXCL`）；加锁后发现 W 已切到别的分支（`worktree-switched`，未写） | 未动 | 是 |
| 记录被代理的提交带走（`taken-by-other-commit`，§5.9 第 7 步"风险"；各回滚处都可能出现，含 `git add --intent-to-add` 失败处） | 不动 index 和文件 | **否** |
| W 在校验期间被切走，落错的提交已撤回、记录文件已删除（`worktree-switched`） | 已清理 | 是 |
| W 在校验期间被切走，落错的提交已撤回、记录文件已被改动而保留（`worktree-switched`） | 保留文件 | **否** |
| `git add --intent-to-add` 失败（§5.9 第 7 步）或 `git commit` 失败（§5.9 第 8 步），记录文件已被改动、保留 | 保留文件 | **否** |
| `git commit` 前 sha256 核对不等，已移出 index、保留文件（§5.9 第 7 步） | 保留文件 | **否** |
| `git commit` 前发现记录文件已被别人删掉，已移出 index（`file-deleted-before-commit`，§5.9 第 7 步） | 已干净 | 是 |
| 提交后撤回失败：`update-ref` 比较失败（A 之上又有新提交）；提交不在任何分支顶端（`commit-stacked`、`commit-not-found`）；落错的分支撤回失败；落错的分支撤回后 `git rm --cached` 失败（`worktree-switched` 路径；`concurrent-commit` 路径的同一情形报 `STALE_HEAD` + `orphanApproval`，§5.9 第 7 步） | 留在分支或 index 上 | **否** |

`COMMIT_FAILED`：`git commit` 失败且已回滚（记录已移出 index、文件已删除）时，输出含 `index.lock` 为可重试；`git rm --cached` 失败、回滚未完成（`orphanApproval`）为否。`git add --intent-to-add` 失败的出口分三支：记录已被别的提交带走 → 上表 taken 的 `CONFLICT`（不可重试）；文件被改动 → 上表 kept 的 `CONFLICT`；文件已删除 → `COMMIT_FAILED`"已删除新建的记录文件"，含 `index.lock` 时可重试。

五个 `model_*` 写工具（`aisep/writer.py`，§3.4）：rename 前哈希核对不等 → `CONFLICT`，未覆盖，可重试；进程内回滚时发现文件又被改动、保留现场（其余文件回滚完）→ `CONFLICT`，**不可重试**，`details.kept: true`、`details.keptFiles`（PR #34，§3.4 第 3 步）。

### 7.3 发现项 Finding

```ts
interface Finding {
  severity: "Violation" | "Warning" | "Info";   // 原型行首 [Violation]/[Warning]/[Info]
  layer: "L0" | "build" | "L1" | "L2" | "L3" | "L4";
  rule: string | null;    // "EG24"、"G7"、"R3"、"§7.3"、SHACL 形状短名；原型多数消息没有编号，v1 允许 null，逐步补
  focus: string | null;   // 焦点完整 IRI；工作台用它高亮节点
  file: string | null;    // 相对仓库根的路径
  message: string;        // 原型原文（英文），去掉行首 "[Violation] L1 "，不翻译
  preexisting?: boolean;  // 只在写工具结果（含 WRITE_REJECTED 的 details.findings）里出现：true = 写前基线已有，false = 本次写入新增（§5.1 第 5 步）
}
```

- CLI 行 `[Violation] L1 text` ⇔ `{severity:"Violation", layer:"L1", message:"text"}`。CLI 和 MCP 用同一个 `report` 函数产出，措辞只有一份，可逐条比对（T3）。
- `focus`：由 `Ctx.add` 的新参数直接给出；旧调用点暂未补参数的，解析消息开头的 `slug:local:` 再展开，解析不到为 null。
- 展示时的排序、去重同原型 `report()`：严重度 → 层 → 消息；去重键 `(severity, layer, message)`。§5.1 的"新违规"判定**不用**这个键，用实例键 `(severity, layer, rule, focus, message)` 的多重集（`focus` 为 null 时另加 `file`）。`model_findings` 的 `openViolations.items` 不做展示去重（§5.4）。
- 写工具新增的错误不是 Finding，是 §7.1 的错误对象；所以不需要 `layer: "write"`。
- `preexisting`（Q6 条件二）：按实例键多重集计算，同一实例键在基线里出现 k 次、候选图里出现 n 次时，前 min(k, n) 条标 `true`，其余标 `false`。只读工具不带这个字段（不是缺省 false）：它们没有"写前"可比。`model_findings` 的 `openViolations.items` 也不带——那里列的是当前全部违规，不分新旧。

---

## 8. 工作台 `client.ts` 正式接口草图

```ts
// aisep/data/client.ts — 正式版（替换 PROVISIONAL）。依据：docs/mcp-interface.md §5。
// 工作台不写模型（§2）：删除 write()、WriteOperation、WriteResult。
export type Iri = string;
export type Sha = string; // 40 位十六进制
export type ApprovalState = "Proposed" | "Approved" | "Rejected" | "Superseded";
export type ImpactMode = "depends" | "ripple";
export type GateId = "GateRequirements" | "GateArchitecture" | "GateDesign" | "GateMerge" | "GateRelease";
export type Layer = "L0" | "build" | "L1" | "L2" | "L3" | "L4";
export type DiffKind = "element" | "relationship" | "view" | "governance" | "schema" | "other";
export type Change = "added" | "modified" | "removed";

export interface Target { repo?: string; ref?: string } // 工作台不传 repo（§3.3）；ref 按 §2 表：架构全景、待批准关口不传（读主分支），
                                                        // "已在分支批准"标记传会话分支，关口页传 head.commit

export interface Finding {
	severity: "Violation" | "Warning" | "Info";
	layer: Layer;
	rule: string | null;
	focus: Iri | null;
	file: string | null;
	message: string;
	preexisting?: boolean; // 只在写工具结果里出现（§7.3）；工作台不调写工具，读到也忽略
}

export interface Term { type: "iri" | "literal" | "bnode"; value: string; datatype?: string; lang?: string }
export type QueryResult = (
	| { kind: "select"; variables: string[]; rows: Record<string, Term>[]; truncated: boolean }
	| { kind: "ask"; value: boolean }
	| { kind: "triples"; triples: [Term, Term, Term][]; truncated: boolean }
) & {
	source: { repo: string; ref: string | null; commit: Sha | null }; // §5.0 公共输出
	findings: Finding[]; // §5.0；只有 allowPartial 时非空（工作台不传 allowPartial，所以也不会收到 partial、skippedFiles）
};
// 工作台只发 SELECT：query() 收到别的 kind 直接抛 AisepToolError("UNEXPECTED_RESULT_KIND")。

export interface GateResult {
	result: "PASS" | "FAIL";
	summary: { violations: number; warnings: number; infos: number; violationsByLayer: Record<Layer, number>; seconds: number };
	findings: Finding[];
	source: { repo: string; ref: string | null; commit: Sha | null };
}

export interface ImpactHop { from: Iri; relationship: Iri; via: Iri; direction: "forward" | "backward" | "related"; to: Iri }
export interface ImpactItem { iri: Iri; label?: string; types: Iri[]; depth: number; related: boolean; path: ImpactHop[] }
export interface ImpactResult {
	focus: { iri: Iri; label?: string; types: Iri[] };
	mode: ImpactMode;
	depth: number;
	invalidModel: { violations: number } | null;
	items: ImpactItem[]; // 最多 500 条（§3.5）
	truncated: boolean;  // items 超上限被截断
	findings: Finding[]; // §5.0；allowInvalid 时为 L0–L2 违规，否则为空
	source: { repo: string; ref: string | null; commit: Sha | null };
}

/** model_findings 结果（§5.4）。工作台只用 openViolations 画"架构全景"的违规计数徽标。 */
export interface OpenViolations {
	count: number;
	byLayer: Record<"L0" | "build" | "L1" | "L2", number>;
	items: Finding[]; // severity 恒为 Violation
}
export interface FindingsResult {
	partial: true;
	summary: GateResult["summary"];
	findings: Finding[];               // L4
	openViolations: OpenViolations;       // 总是返回；items 不做展示去重，count 为实例数
	source: { repo: string; ref: string | null; commit: Sha | null };
}

export type Counts = Record<Change, number>;
export interface Endpoint { iri: Iri; label?: string }
export interface DiffItem {
	iri: Iri; kind: DiffKind; change: Change; types: Iri[]; label?: string;
	source?: Endpoint; target?: Endpoint;
	files: { base: string[]; head: string[] }; typeChanged?: boolean;
	changedPredicates?: Iri[];
	triples?: { added: [string, Term][]; removed: [string, Term][] };
}
export interface DiffResult {
	base: { ref: string | null; commit: Sha; viaMergeBase: boolean; mainRef: string | null }; // base 显式给出时 mainRef 为 null（§5.8）
	head:
		| { kind: "ref"; ref: string | null; commit: Sha }
		| { kind: "worktree"; branch: string; headCommit: Sha; dirty: boolean };
	baseHasModels: boolean;
	headHasModels: boolean;
	incomplete: boolean;                       // 只有 worktree 模式可能为 true
	failedFiles: { file: string; error: string }[];
	indeterminate: Iri[];                      // 失败文件里的主语，不进 items 与计数
	counts: Record<DiffKind, Counts>;
	changedElementCount: number;
	touchedElementCount: number;
	items?: DiffItem[];           // detail = items | triples
	touchedElements?: Iri[];
	moves?: { iri: Iri; files: { base: string[]; head: string[] } }[];
	truncated?: boolean;          // 与 items 同在：detail = summary 时没有（§5.8）
}

export interface ActivityInput {
	agent: Iri; sessionRef: string; branch?: string; // 给了必须等于 ApprovalInput.branch
	startedAt: string; endedAt?: string; label?: string;
}
export interface ApprovalInput {
	repo?: string; model: string; gate: GateId; decision: "Approved" | "Rejected";
	approvedBy: Iri; approves: Iri[]; branch: string; headCommit: Sha; expectedBaseCommit?: Sha; mainRef?: string;
	slug?: string; prefLabel?: string; activity?: ActivityInput;
}
export interface ApprovalResult {
	approval: { iri: Iri; file: string };
	activity?: { iri: Iri; reused: boolean };
	evidence: string; baseCommit?: Sha; commit: Sha; branch: string; duplicate: boolean;
	gate: { result: "PASS" | "FAIL"; summary: GateResult["summary"] };
	derivedApprovalState: { iri: Iri; before: ApprovalState; after: ApprovalState }[];
	findings: Finding[];
}

/** 工作台用到的 6 个工具；写模型的 5 个工具（model_add_element、model_add_relationship、model_remove、
 *  model_set_labels、model_set_attributes）不进工作台（一期），所以这里没有对应方法。 */
export interface AisepModelClient {
	query(sparql: string, target?: Target & { limit?: number }): Promise<QueryResult>;
	gate(target?: Target & { model?: string }): Promise<GateResult>;
	findings(target?: Target & { model?: string }): Promise<FindingsResult>;
	impact(focus: Iri, options?: Target & { mode?: ImpactMode; depth?: number; allowInvalid?: boolean }): Promise<ImpactResult>;
	diff(input: { repo?: string; head: string | { worktree: string }; base?: string; mainRef?: string; model?: string;
	              detail?: "summary" | "items" | "triples" }): Promise<DiffResult>;
	recordApproval(input: ApprovalInput): Promise<ApprovalResult>;
}

/** isError: true 的工具结果统一抛成它；code 取 §7.2。 */
export class AisepToolError extends Error {
	constructor(readonly code: string, message: string, readonly retryable: boolean,
	            readonly hint?: string, readonly details?: { findings?: Finding[] } & Record<string, unknown>) {
		super(message);
	}
}

/** F7：approvalState 是 IRI，不是字符串。 */
export const APPROVAL_STATE_IRI: Record<string, ApprovalState> = {
	"https://meta.linked.archi/core#Proposed": "Proposed",
	"https://meta.linked.archi/core#Approved": "Approved",
	"https://aisep.example/ont/aisep#Rejected": "Rejected",
	"https://aisep.example/ont/aisep#Superseded": "Superseded",
};
// 推导范围是口径 A（Albert 已定，#29 已实现，见规范 §6.6）：aisep:ApprovalRecord、aisep:AgentActivity、arch:Stakeholder 都没有 approvalState。
// 两条固定查询（D4：只是工作台的固定 SPARQL，不是新工具），缺省读主分支（"已批准、待合并"标记另按 ref=branch 读会话分支：选法同 ELEMENTS_QUERY，另加 arch:Model 实例本身，§2）、都排除 aisep:ApprovalRecord 与 aisep:AgentActivity 的实例
// （它们也是 arch:Element、也有 inModel 和 zh 名称，实测：采购例子里 approval-20261119-arch-baseline）：
// - ELEMENTS_QUERY（架构全景）：选有 arch:inModel 和 zh 名称的主语；arch:approvalState 用 OPTIONAL。缺失 → 显示"无批准状态"
//   （如 Stakeholder），**不**当作 Proposed：那个状态不是推导给出的，违背 P4。
// - PENDING_QUERY（待批准关口）：只选 arch:approvalState 为 arch:Proposed 的主语。
// elementsFromRows 改为读 Term.value，approvalState 有值时用 APPROVAL_STATE_IRI 映射；映射不到的 IRI 直接抛错。
```

`ao-sessions.ts` 的 `AgentSessionRow` 不变，**不新增任何 AO 接口或字段**：仓库路径和主分支由工作台的服务器进程启动参数 `--repo`、`--main-branch` 给出（§3.3），工作台调用时不传。P10 的上游接触面（`GET /api/v1/sessions` 及 `UPSTREAM.md` 已登记的字段）不扩大。代价：v1 一个工作台服务器进程只服务一个仓库，与 §1"不做多仓库项目"一致。

**替换路径**（每步一个可验证落点）

| 步 | 动作 | 验证 |
|---|---|---|
| 1 | `client.ts` 换成正式接口。`FixtureClient` 跟着实现新接口：`write()` 删掉，`recordApproval` 抛 `AisepToolError("READ_ONLY_FIXTURE", …)`；新增 `fixtures/diff-*.json`。fixture **由真实服务器对采购例子输出后落盘**，不手写 | `npm run typecheck`；基线 292 项 + fixture 测试 |
| 2 | 新增 `aisep/data/mcp-client.ts`：`McpModelClient`，用 `fetch` 向 `127.0.0.1` 发 JSON-RPC `tools/call`，按 **2026-07-28** 的形状：不发 `initialize`；请求头 `Content-Type: application/json`、`Accept: application/json, text/event-stream`、`MCP-Protocol-Version: 2026-07-28`、`Mcp-Method: tools/call`、`Mcp-Name: <工具名>`；`params._meta` 带 `io.modelcontextprotocol/protocolVersion`、`clientCapabilities`、`clientInfo`。把 `structuredContent` 转成类型，`isError` 转成 `AisepToolError`。**不加 npm 依赖**：`@modelcontextprotocol/sdk` 会改上游的 `package.json` 和锁文件（P10）。手写客户端只服务这一个版本；SDK 升级时由 T30 的契约测试先报警 | 单测：用录制的真实响应喂假 `fetch` |
| 3 | `AisepWorkbenchPage` 缺省 client：配置了服务器地址就用 `McpModelClient`，否则 `FixtureClient` 并保留"示例数据"提示 | 页面测试覆盖两条分支 |
| 4 | "改动元素"一栏：`AiActivitySection` 对每个有 `branch` 的行调 `diff({head: {worktree: row.branch}, detail:"summary"})`（缺省 worktree 模式），TanStack Query 键 `["aisep","diff","wt",branch]`，按固定间隔重取（工作区改动不改分支头，没有别的失效信号）；`WORKTREE_NOT_FOUND` → 改调 `diff({head: row.branch})`；`head.dirty` 显示"含未提交"，`incomplete` 显示"部分文件解析失败"；`REF_NOT_FOUND` 显示"分支不在模型仓库"，`baseHasModels` 与 `headHasModels` 都为 false 显示"此仓库无模型"，其他错误显示"暂不可用" | 页面测试覆盖 6 种状态（正常、含未提交、incomplete、退回引用模式、分支不在、无模型）+ 错误 |
| 4b | "架构全景"违规计数徽标：页面打开时调 `findings()`，`openViolations.count > 0` 显示徽标，点开列 `items` 并按 `focus` 高亮 | 页面测试：夹具植入 1 个遗留 L1 违规 → 徽标显示 1；0 违规不显示 |
| 5 | 关口页（新路由，在 `aisep/` 目录内，经已有的 `_shell.aisep.$.tsx` 壳）：差异图 + gate + 批准按钮 | 端到端：在临时仓库里批准，再查询到记录 |

---

## 9. 需要改动的规范条文（可直接替换）

已移至 [`docs/history/mcp-interface-mirrors.md`](history/mcp-interface-mirrors.md) 的「§9」，原文未改。这些改文已落入元模型规范（`docs/metamodel-spec.md`），现行条文以它为准。

---

## 10. 设计会话的拍板

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「§10（含 §10.1、§10.2）」，原文未改。

---

## 11. 验收：每项主张怎么用可执行测试证明

已移至 [`docs/history/mcp-interface-mirrors.md`](history/mcp-interface-mirrors.md) 的「§11（验收表 T1–T43）」，原文未改。

---

## 附录 A：三份草案的冲突与裁决

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「附录 A」，原文未改。

## 附录 B：外部事实出处

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「附录 B」，原文未改。

## 附录 D：工具 ↔ 规范 ↔ 原型追溯表

已移至 [`docs/history/mcp-interface-mirrors.md`](history/mcp-interface-mirrors.md) 的「附录 D」，原文未改。

---

## 附：评审与辩论记录（2026-11-20）

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「附：评审与辩论记录（含第二、三、四轮）」，原文未改。

---

## 附：设计会话拍板记录（2026-11-20）

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「附：设计会话拍板记录」，原文未改。

## 附：合并记录（2026-11-20）

已移至 [`docs/history/mcp-interface-records.md`](history/mcp-interface-records.md) 的「附：合并记录」，原文未改。
