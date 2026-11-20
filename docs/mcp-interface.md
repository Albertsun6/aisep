# AISEP MCP Server 接口设计

> **状态：草案定稿候选（设计会话已拍板 Q1–Q6，已过两轮评审，其中各含一路 GPT 异构）。** 日期：2026-11-20。第二轮评审（拍板后，GPT `gpt-5.6-sol-high` + Claude Git 语义与安全 lens，22 条）的处置见文末"第二轮（2026-11-20，拍板后）"；其中转设计会话的 2 条（R2-13、R2-15）已于 2026-11-20 拍板，落进 §5.9"合并时校验""批准专用 PR""发布关口"、§9、§11（T38–T40）。拍板结果见 §10.1 与文末"附：设计会话拍板记录"；Q6 的两个附加条件（`model_diff` 比较工作区未提交改动、遗留违规可查可见）已落进 §5.1、§5.4、§5.8、§7.3、§8、§9、§11。
> **合并**：由本会话设计稿与另一会话草案合并（2026-11-20），以前者为底；并入了后者的 `model_set_labels`（§5.10）、关系写入文件规则（§5.1）和工具↔规范↔原型追溯表（附录 D），被替代的说法与理由见文末"附：合并记录"。本文原写在仓库外，路径已改为仓库内路径（`docs/`、`tools/`、`modules/`、`models/`）。文中"规范"指 `docs/metamodel-spec.md`（《元模型规范》），ADR 指 `docs/decisions.md`，"原则五"指 `docs/principles.md`，"原型"指本仓库 `tools/aisep.py` 及其模块与例子。
> 本稿由三份独立草案（编码代理视角、工作台视角、语义视角）合成。冲突的裁决见附录 A。
> **第一轮 4 路评审**：3 路 Claude lens（规范一致性、MCP 协议、Git 语义）+ 1 路异构（GPT 族，`gpt-5.6-sol-high`，经 cursor-agent `--mode ask` 只读）。53 条意见逐条处置，见文末"附：评审与辩论记录"。第一轮异构评审只覆盖修订前的版本；修订后与拍板后的新增内容（§5.9 逐提交校验、目标 worktree 锁、§5.8 worktree 模式、`openViolations`、`preexisting`、禁用 rebase 合并）已由第二轮评审覆盖（含一路 GPT 异构）。
> 分工：设计会话拍板，执行会话写文件（`docs/methodology.md` 第 111 行）。第 10 节记录设计会话的答复（§10.1）和已按推荐定下、可推翻的默认项（§10.2）。拍板后新增的内容（worktree 模式的 diff、`openViolations`、`preexisting` 标记、禁用 rebase 合并）已过第二轮评审；第二轮的修订本身（§3.3 文件集合与路径校验、§5.9 锁内复验与提交后核对等）未再过第三轮评审。

**已用原型只读命令核实的事实**（`PY` 为 `AGENTS.md` 里的共用解释器，2026-11-20；当时在仓库外的原型目录 `metamodel-prototype/` 下执行，本仓库的 `tools/`、`modules/`、`models/` 与之逐文件一致，下文路径均指本仓库）

| # | 事实 | 命令或出处 |
|---|---|---|
| F1 | `check` 采购例子：0 Violation、1 个 L2 Warning（派生捷径），0.07 秒，退出码 0 | `check` |
| F2 | `gate` 采购例子：PASS，1 Warning，5.0 秒 | `gate` |
| F3 | `impact procurement:quotation`：depends 14 个元素，ripple 16 个 | `impact … --mode depends/ripple` |
| F4 | `impact` 遇到不存在的元素：只打一条 Warning，**退出码 0，结果为空** | `impact procurement:noSuchThing` |
| F5 | `query` 收到 `INSERT DATA`：pyoxigraph 抛 `SyntaxError` 堆栈，原型没有包装，退出码 1 | `query 'INSERT DATA {…}'` |
| F6 | `query` 里的 `SERVICE` **会真的发 HTTP 请求**（报错 `OSError: The port 9 is not allowed for HTTP(S)`，说明已尝试连接） | `query 'SELECT * WHERE { SERVICE <http://127.0.0.1:9/sparql> {…} }'` |
| F7 | 采购模型 54 个成员；`arch:approvalState` 有 26 个，值是 IRI：`arch:Proposed` 25 个，`arch:Approved` 1 个 | `query` |
| F8 | 指向 `quoteApproval` 的源三元组 9 条：1 条 `aisep:approves`（批准记录），8 条是关系的 `arch:source`/`arch:target` | `query` |
| F9 | 指向 `quotation` 的源三元组 3 条，都是关系端点（1 条 Realization、2 条 Access） | `query` |
| F10 | 指向 `bpmnReview` 的源三元组：`sf1` 的 target、`sf2` 的 source、`bpmnQuoteApproval bpmn:flowElements` | `query` |
| F11 | `am4:Assignment` 的直连谓词是 `am4:assignedTo`；例子里手写的 IRI 是 `rel-supplier-assigned-…`，不符合 §3 | `query` |
| F12 | `ddd:SubdomainImplementation` → `ddd:implements`，`aisep:Implementation` → `aisep:implements`：本地名都是 `implements`，两端相同时 IRI 会撞名 | `query` |
| F13 | 原型代码：`ROOT`、`MODEL_BASE` 写死（第 26、45 行）；23 处 `print(`；6 处 `sys.exit(`；问题记录是 `(severity, layer, text)` 三元组，没有焦点字段；`impact()` 只记关系类，不记关系 IRI | 读 `tools/aisep.py` |
| F14 | 关口个体：`aisep:GateRequirements`/`GateArchitecture`/`GateDesign`/`GateMerge`/`GateRelease`（`modules/aisep-core/onto.ttl` 第 86–90 行） | 读模块 |
| F15 | `ext-code`、`ext-verification`、`ext-governance` 都**不**声明 `aisep:ownsNamespace`（共用 `aisep#`）；靠命名空间分不出它们 | 读 `modules/*/metamodel.ttl` |
| F16 | 采购例子里没有视图，也没有 `views/*.layout.json` | `query` + `find` |
| F17 | spike venv 里没有装 `mcp` Python SDK；Python 3.12.13，git 2.54 | 本机 |
| F18 | 例子批准记录的 `aisep:evidence` 是占位 commit，不是真实提交 | `models/procurement/governance.ttl` |
| F19 | §5.8 worktree 模式的算法在临时仓库里跑通：25 条断言全部 CONFIRMED（改已跟踪文件、未跟踪新文件、工作区删除文件、坏文件 → `incomplete`、写坏一半的已跟踪文件不报"整文件删除"、忽略文件不参与、符号链接不跟随、任意路径与不存在的分支被拒）；两处变异（去掉 indeterminate 处理、去掉符号链接检查）分别让对应断言 REFUTED，说明断言能失败 | 脚本 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/wtdiff.3CCZ/probe/probe_test.py`（实现在同目录 `wtdiff.py`），`$PY -I probe_test.py <空目录>`（临时目录，可能已清理）；细节见 §11 T35 |

---

## 1. 范围与已决前提

**范围**
- 一期交付物 MCP Server（ADR-008）的全部工具接口。
- 定稿 ADR-013 留下的三处：`model.diff`、`governance.record_approval` 的活动参数、`aisep:AgentActivity`。
- 工作台 `client.ts` 的正式接口，以及 `FixtureClient` 的替换路径。

**已决前提（本文不推翻）**

| # | 前提 | 出处 |
|---|---|---|
| P1 | MCP 不保存任何文件外状态；写操作 = 改 Turtle 文件，进 Git | §8.3、ADR-008 |
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
| 待批准关口的"已在分支批准、待合并"标记 | 对"AI 进行中"里有 `branch` 的行，`model_query(ref=branch)` 查该分支上的批准记录 | 会话分支（Q2=A） | 同"AI 进行中" |
| AI 进行中 | 每个有 `branch` 的行：`model_diff({head: {worktree: branch}, detail:"summary"})`（缺省 worktree 模式，含未提交改动） | 该分支检出的工作区：merge-base 的 Git 对象 vs 工作区磁盘文件 | 行的分支头变化或定时轮询（工作区改动不改分支头） |
| 关口页（新路由，在 `aisep/` 内） | `model_diff({head: <commit>, detail:"items"})`、`model_gate(ref=head.commit)`、按需 `model_impact(ref=head.commit)` | 固定 `head.commit`（只认已提交） | 进入页面一次 |

批准提交写在会话分支上（Q2=A），合并前主分支推导出的状态仍是 Proposed。工作台**不**用 `record_approval` 的返回值改写主分支那一行，只按上表第三行从分支上的记录查出"已批准、待合并"标记。这样显示的每个状态都来自所读那份内容里的批准记录（P4、ADR-009）。

---

## 3. 服务器形态

### 3.1 实现语言与复用原型

| 项 | 设计 | 理由 |
|---|---|---|
| 语言 | Python ≥3.12，官方 `mcp` Python SDK，锁 `mcp==2.3.*`（`MCPServer` API；v1 的 `FastMCP` 导入路径在 v2 已移除） | 原型就是 Python；判定逻辑只此一份，保证 P9 |
| 协议版本 | 目标 MCP **2026-07-28**，兼容 2025-11-25（SDK v2 两版都服务） | 2026-07-28 去掉了 `initialize` 握手和协议层会话，每个请求自带版本与能力，正合 P1；Claude Code 的 v2 运行时协商这一版 |
| 工具入口包装 | 每个工具函数套一个装饰器：捕获 `AisepError` → 手工构造 `CallToolResult(isError=True, structuredContent={error}, content=[message+hint])`；其他异常 → `INTERNAL`，stderr 记摘要 | 两代 SDK 都不会把异常变成 §7 的结构：v1 只给一段 text，v2 变成脱敏的 `-32603`，模型看不到原因 |
| 入参校验 | 每个 `inputSchema` 写 `additionalProperties: false`；入口用 jsonschema 显式校验，不符 → 工具执行错误 `INVALID_ARGUMENT`，`details.rejectedFields` 点名 | SDK v1 `validate_input=False` 且未知键被静默丢弃；v2 只公布 schema 不执行 |
| 位置与依赖 | 新目录 `aisep-mcp/`，自带 venv，pyoxigraph/pyshacl/rdflib 锁定与 spike venv 相同版本，另加 `mcp` | spike venv 没有 `mcp`（F17）；`docs/module-contract.md` 说不要给原型另建 venv，新交付物另建不冲突 |
| 复用方式 | 把 `tools/aisep.py` 拆成库 `aisep/core.py`（Ctx、l1–l4、impact、build，逻辑不变）+ `aisep/report.py`（发现项结构化）；`tools/aisep.py` 留作 CLI 薄壳，输出逐字不变；MCP 新写 `aisep/gitio.py`（读 Git 对象、物化快照）、`aisep/writer.py`（写入层）、`aisep/server.py` | 两个入口不分叉；179 项测试继续守住语义 |

拆库时**必须改**的原型现状（F13）：

| 现状 | 问题 | 改法 |
|---|---|---|
| 23 处 `print` | stdio 传输下 stdout 就是 JSON-RPC 通道 | 函数返回数据，CLI 层打印。兜底：启动时先 `os.dup(1)` 保留原 fd，用它建二进制流显式传给 `stdio_server(stdout=…)`，再 `os.dup2(2, 1)`，遗留的 `print` 和 C 层写入都落到 stderr。**不能**只改 `sys.stdout`：SDK 在进入时取 `sys.stdout.buffer` 当 JSON-RPC 通道，全局重定向会把协议帧一起送进 stderr |
| 6 处 `sys.exit` | `SystemExit` 会杀掉服务器 | 改抛 `AisepError(code, message)`，由上表的入口装饰器转成工具执行错误 |
| `ROOT` 写死 | 不能服务多仓库、多 ref | `Ctx` 接收 `root`（工作区路径或快照目录） |
| `MODEL_BASE` 写死 | 换 base 就错 | v1 保持常量（命名空间第三步才换），但集中到一处，`Ctx` 可传入 |
| 问题是 `(sev, layer, text)` | 工作台没法按元素高亮 | `Ctx.add` 增加可选 `focus`、`rule`、`file`；**展示**去重键仍是 `(sev, layer, text)`，CLI 文本用 golden 测试锁住；写入判定另用实例键（§5.1） |
| `impact()` 路径是拼好的字符串，只记关系类 | 差异图、影响面没法逐跳画 | 边里多存关系 IRI，返回结构化路径（§5.7） |
| `impact` 遇未知元素退出码 0 | 代理会误读成"没有影响"（F4） | MCP 报 `ELEMENT_NOT_FOUND`；建议 CLI 同步改为退出码 1（有意变更，登记） |

### 3.2 传输

| 客户端 | 传输 | 谁起进程 |
|---|---|---|
| 编码代理（Claude Code 等） | stdio | 代理按 `.mcp.json` 起，每个会话一个；cwd = 当前 worktree |
| 工作台 | **Streamable HTTP**（Q1=B，已拍板） | 开发期由开发脚本起一个常驻进程（与 AO daemon 同级），监听 `127.0.0.1` |

- 同一个程序：`aisep-mcp --transport stdio|http`。
- 选 HTTP 的唯一理由是 P10：stdio 要在 Electron 主进程起子进程，再经 preload 暴露给 renderer，要改上游的 `main.ts`、`preload.ts`。HTTP 由 renderer 直接 `fetch`，代码全部留在 `aisep/data/`。renderer 已经在用 `http://127.0.0.1` 访问 AO（`lib/api-client.ts`），注释说明 CSP 的 `connect-src` 放行了 http 127.0.0.1。
- **协议没有会话**（2026-07-28）：没有 `initialize`，没有 `Mcp-Session-Id`；每个 POST 自带 `_meta` 里的协议版本和客户端能力，独立处理，返回 `application/json`。这就是 P1 在传输层的落实。对 2025-11-25 客户端（如部分代理），SDK 的 `stateless_http` 模式照常服务。
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
- 主分支：每次调用可传 `mainRef`；不传取启动参数 `--main-branch`，再缺省 `main`。不引入配置文件。
- **主分支解析顺序**：给的是短名 `<b>` 时，先找 `refs/remotes/<upstream>/<b>`（`upstream` 取 `<b>` 的跟踪远端，没有就 `origin`），有就用；没有才退回 `refs/heads/<b>`。理由：会话分支通常从 `origin/main` 切出，本地 `main` 落后时 merge-base 会落在更老的提交上，diff 会把队友已合入的改动算进本会话（评审实测复现）。AO 读 base 用的也是远端跟踪引用（`workspace.ts` 的 `baseRef`，如 `"origin/main"`）。输出的 `base.mainRef` 给出实际用的完整 ref 名。
- **读哪份内容**：

| 输入 | 读的内容 | 谁用 |
|---|---|---|
| 不传 `ref` | `repo` 这个 worktree 的磁盘文件（含未提交改动） | 编码代理 |
| `ref: "<分支/标签/sha>"` | 该 commit 的快照：先 `git ls-tree <commit> -- models modules vendor` 查哪些路径存在，再 `git archive` 存在的那些，解到系统临时目录，调用结束删除。缺 `modules/` 或 `vendor/`（附录 C 的独立模型仓库）→ `MODULES_NOT_IN_REF`，不静默改用服务器自带模块 | 工作台、`record_approval` 的 gate |

- 快照里的 `modules/`、`vendor/` 也取自同一个 commit，所以"某 commit 上的 gate"可复现（vendor 8.4 MB，modules 0.9 MB；耗时在验收 T10 里量）。
- `model_diff` 不物化快照：Git 引用模式只读 Git 对象；worktree 模式 base 侧读 Git 对象，head 侧读**按分支名定位到的那个工作区**的 `models/**/*.ttl`（§5.8）。它不用上表"不传 `ref` 读 `repo` 磁盘文件"的规则：读谁的工作区由 `head.worktree` 的分支名决定，与调用方从哪个 worktree 调用无关。
- ref 安全：一律 `git rev-parse --verify --end-of-options <ref>^{commit}`；以 `-` 开头的 ref 直接 `INVALID_ARGUMENT`。
- 多 worktree 不需要额外机制：同一仓库的 worktree 共享对象库和 refs，从哪个 worktree 调 `model_diff`（两种模式）、带 `ref` 的读取，结果都一样。
- **按分支名定位出的 worktree 也要过根目录校验**（第二轮评审 R2-2、R2-19）：Git 允许 linked worktree 放在 `--allow-root` 之外，有仓库写权限的进程还能改 `.git/worktrees/<n>/gitdir` 让登记路径指向任意目录。所以 `model_diff` 的 worktree 模式（§5.8 第 0 步）和 `record_approval`（§5.9 第 7 步）定位出 W 后再做两项校验：`realpath(W)` 必须落在某个 `--allow-root` 之下，否则 `PATH_OUTSIDE_ROOT`；`git -C W rev-parse --git-common-dir` 的真实路径必须等于 `repo` 的 common dir，否则 `WORKTREE_NOT_FOUND`。
- **工作区文件集合只有一个口径**（R2-16）：凡读工作区模型文件的地方（`model_check`/`validate`/`findings`/`gate` 不带 `ref` 时、写工具的基线、`model_diff` 的 worktree 模式、§5.9 的脏检查、仓库 pre-commit 钩子），文件集合一律 = `git ls-files -z -- models/`（已跟踪）∪ `git ls-files -z --others --exclude-standard -- models/`（未跟踪且未被忽略），只留 `.ttl`；被忽略的文件和嵌套仓库里的文件不进入。原型缺省的 `glob(models/**/*.ttl, recursive=True)`（`aisep.py` 第 937 行）会读进被忽略文件、嵌套仓库，还会跟随目录链接，服务器不用它；钩子随之改用同一函数，否则 gate 校验的是一份不会被提交的内容。index 只用来确定文件集合，内容一律以磁盘为准。
- **安全打开**（R2-10、R2-12）：工作区里的每个模型文件都从 `realpath` 后的 worktree 根目录描述符出发，逐级 `openat(…, O_NOFOLLOW)` 打开（Python：`os.open(name, flags | os.O_NOFOLLOW, dir_fd=…)`），**任何一级**是符号链接都不跟随；打开后 `fstat` 必须是普通文件。读侧不满足 → 该文件记入解析失败（`error: "symlink"` 或 `"not-regular"`，FIFO、设备文件不会把读阻塞住）；写侧（写工具、`record_approval` 写 governance.ttl）不满足 → `PATH_OUTSIDE_ROOT`。只检查最后一级不够：把 `models/<slug>` 目录换成指向外部的链接，`ls-files` 照样从 index 列出其中的路径，普通 `open()` 会顺着上级目录读写到工作区外（评审实测）。

### 3.4 并发

- 只读调用可并行，不加锁。读 Git 对象的调用（带 `ref`、`model_diff` 的 Git 引用模式）内容不可变，不受并发影响；读工作区的调用没有快照：`model_diff` 的 worktree 模式按 §5.8 第 4 步做前后核对；`model_check` 等诊断类读取不核对，读到保存中途的内容只会让这一次诊断不准，提交时的 gate 才是结论（G10）。
- 写调用（工作台进程、各代理进程是不同服务器进程，所以必须跨进程）：
  1. `flock` 锁**被写入的那个 worktree** 的 `$(git -C <worktree> rev-parse --git-dir)/aisep-write.lock`。`model_*` 写工具的目标就是 `repo`；`record_approval` 的目标是 `branch` 检出所在的 worktree（§5.9 第 7 步），**不是**调用方传的 `repo`。这样工作台对 worktree A 批准时，与 A 里代理的写入抢的是同一把锁。拿不到立即返回 `LOCKED`（可重试），不排队。不同 worktree 互不阻塞。进程死了锁自动释放。
  2. 写前哈希核对：读入时记下目标文件 sha256；rename 前再算一次，不等就 `CONFLICT`（可重试）。**这不是真正的比较并交换**（R2-3）：外部编辑器、普通 `git` 命令不遵守 `aisep-write.lock`，在"核对哈希"与 `rename` 之间写入的内容会被静默覆盖。这个窗口只有毫秒级，v1 接受，列为已知限制（§9 附录 C）；不采用原子交换（Linux `renameat2(RENAME_EXCHANGE)`、macOS `renamex_np(RENAME_SWAP)`）再核对换出旧文件的做法：平台相关，换回时还有同样的窗口。T13 加一例：在核对之后、rename 之前注入外部写入，断言结果如上所述（被覆盖），证明文档如实。
  3. 替换：写临时文件 → `fsync` → `rename`。多个文件先全部写成临时文件，再依次 rename；进程内中途失败用内存里的原字节恢复，恢复前先比对文件仍等于本次写入后的哈希，不等就保留现场、报 `CONFLICT`。
  4. **不是崩溃原子的**：进程在两次 rename 之间被杀（SIGKILL、宿主断开时杀子进程、断电），工作区会停在部分写入。服务器无状态，不做恢复日志；兜底是 pre-commit 的 gate（部分写入通常留下悬空引用，L1 报错）和 `git diff` 人工恢复。验收 T13 注入 SIGKILL 证明 gate 能拦住。
- `record_approval` 的提交另受 Git 自己的 `index.lock` 保护，拿不到报 `COMMIT_FAILED`（可重试）。

### 3.5 无状态的落实

| 服务器进程里的东西 | 是不是"状态" |
|---|---|
| 每次调用重新解析文件或 Git 对象，构建 `Ctx` | 不是 |
| 快照临时目录 | 不是：调用结束即删 |
| 写锁文件 | 不是：只在一次写调用期间存在，在 `.git` 内，不进版本库 |
| 会话、游标、草稿、订阅、"进行中"标记 | **不存在** |

- v1 **不做跨调用缓存**。L0–L2 只要 0.07 秒（F1）；gate 要 5 秒（F2），关口页每次进入等一次，可接受。以后要加缓存，键只能是不可变的 Git 对象 ID，不改接口。
- 列表结果有硬上限，超了截断并返回 `truncated: true`：`model_query` 用 `limit`；`model_impact` 的 `items` 最多 500 条；`model_diff` 的 `items` 最多 2000 条（计数 `counts` 永远完整）。v1 不做续页。续页令牌可以把 commit 和偏移编码进去而保持无状态，等真有大仓库再加，不改现有字段。
- 输出体量参照 Claude Code 的阈值：结果文本超过 50,000 字符会被落盘，错误文本超过约 11,000 字符会被截成首尾各 5,000。`content` 摘要里的发现项行最多 200 行，其余只在 `structuredContent` 里。
- 可证伪断言：两次调用之间杀掉重启服务器，所有只读工具的结果**规范化后**相同（T4）：去掉 `summary.seconds` 等耗时字段；无序集合先排序；`model_query` 只在 SPARQL 带 `ORDER BY` 时承诺行序。

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
| `model_add_element` | `model.add_element` | false | false | true（同参数重放 = 无变化） | 无 | **新实现**（校验复用 `check`） |
| `model_add_relationship` | `model.add_relationship` | false | false | true（同类型同端点 = 返回已有） | 无 | **新实现**（校验复用 `check`） |
| `model_remove` | `model.remove` | false | **true** | true（带 `planDigest` 重放、目标已不在 → 成功，`changed:false, alreadyAbsent:true`，同 add 的 `changed:false`） | 无（§8.2 未原型化） | **新实现** |
| `model_set_labels` | `model.set_labels`（**新增**） | false | **true**（覆盖原值，不是追加；原值留在 Git 历史里） | true（同参数重放 = 无变化） | 无 | **新实现**（校验复用 `check`） |
| `governance_record_approval` | `governance.record_approval` | false | false | true（完全重复的请求不写；去重键含调用方给的 `headCommit`，重放稳定） | 无 | **新实现**（gate 复用） |

**画像**：启动参数 `--profile agent|workbench|all`，决定 `tools/list` 列出哪些工具。按进程定，不按连接变（满足 2026-07-28"`tools/list` 不得随连接变化"）。

| 画像 | 列出 |
|---|---|
| `agent` | 除 `governance_record_approval` 外全部 |
| `workbench` | `model_query`、`model_findings`、`model_gate`、`model_impact`、`model_diff`、`governance_record_approval` |
| `all` | 全部（测试用） |

画像**不是安全边界**：代理可以直接手写 Turtle 伪造批准记录，真正的约束是代码评审和分支保护。画像只防"顺手调用"。

**加了两个规范外的工具**：`model_gate`、`model_set_labels`。`model_gate` 的理由：G10 规定提交和 CI 只认 gate，关口页和代理提交前自检都要这个结论；§8.3 漏列了它。`model_set_labels`：规范 §3 规定"改名只改标签"，§8.3 却没有对应的写工具；用户在另一会话拍板加入（2026-11-20，合并时并入，§5.10）。其他辅助工具（列元素、查词汇）一期不加，见 D4。

---

## 5. 工具详述

### 5.0 公共约定

**公共输入**

| 字段 | 类型 | 说明 |
|---|---|---|
| `repo` | string，绝对路径 | 可省，见 §3.3 |
| `ref` | string | 只读工具可选（`model_diff` 用 `head`/`base`）；写工具**不接受** |
| `mainRef` | string | 只有 `model_diff` 和 `record_approval` 用 |

**IRI 输入**：接受完整 IRI，也接受原型 `short()` 打印的 `slug:local`（如 `procurement:quotation`），展开规则同原型 `expand()`。**输出**一律完整 IRI。

**公共输出**（`structuredContent`；每个工具声明 `outputSchema`）

```jsonc
{
  "source": { "repo": "/abs/path", "ref": "main" | null, "commit": "40hex" | null },
  "findings": [ /* §7.3 Finding */ ],
  // …各工具自己的字段
}
```

**`outputSchema` 是成功与错误两种形状的联合**：`oneOf: [<成功形状>, {type: object, required: ["error"], properties: {error: <ErrorEnvelope>}}]`。规范要求有 `outputSchema` 时 `structuredContent` 必须符合它；TS SDK v1 客户端在 `isError: true` 时照样校验，不符会抛 `InvalidParams`，§7.1 的 `code`、`hint` 就丢了。验收 T34 用 TS SDK 的 `Client.callTool` 对每个错误码各验一例。

`content[0].text` 放同一结果的简短中文摘要，加原型 CLI 格式的发现项行（代理直接读得懂）。**有意偏离**规范的 SHOULD（"同时把 structuredContent 序列化成 JSON 放进 TextContent"）：代理读摘要比读 JSON 省 token，客户端都能读 `structuredContent`。体量上限见 §3.5。

### 5.1 写入流程（四个 `model_*` 写工具共用）

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
| 批准记录、AI 活动 | `governance.ttl` |

- **"声明该类型的模块"怎么判定**：Language 类按命名空间即可（原型 `owner` 第 189–196 行、`Ctx.module_of` 第 266–272 行）。`aisep#` 由 aisep-core 声明 `ownsNamespace`，却被 `ext-code`、`ext-verification`、`ext-governance` 共用（F15），`owner()` 会把这些类都归到 aisep-core；所以对 `aisep#` 的类，按"哪个模块的 `aisep:loads` 文件里声明了这个类"判定（原型按文件分图载入本体，第 220–221 行，图名即文件）。原型没有现成函数，要新写一个小函数。
- **关系规则的核对**（合并时用 `models/procurement/` 的 27 个关系逐一核对，全部符合）：`rel-quoteApproval-realizes-procurementSubdomain`、`rel-procurementSystem-composedOf-quotationBC` 在 `ddd.ttl`，`rel-reqTwoLevelApproval-aggregates-acOver100kSecondLevel` 在 `verification.ttl`，refines 在 `uml.ttl`/`bpmn.ttl`，Implementation 在 `code.ttl`。本稿原写"源端元素所在的文件"，对上面前 3 条不符（源端在 `am4.ttl`），改用另一会话草案的规则。
- 新建模型目录（`arch:Model` 本身）不在 §8.3 范围内，v1 手工建；目标模型目录不存在 → `MODEL_NOT_FOUND`。

### 5.2 `model_add_element`

**输入**

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | ✔ | 模型 IRI 或 slug（`procurement`） |
| `type` | ✔ | 类 IRI 或前缀名；必须是已加载模块的具体类，或模型里的单父类特化（R1、G6） |
| `prefLabel` | ✔ | 写成 `skos:prefLabel "…"@zh` |
| `altLabel` | — | 写成 `skos:altLabel "…"@en` |
| `slug` | 条件 | `^[A-Za-z][A-Za-z0-9]*$`（允许大写开头，例子里已有 UML 类 `QuotationEntity`）。不给时由 `altLabel` 转 camelCase；两者都没有 → `INVALID_ARGUMENT`（不自动拼音） |
| `definition` | — | `skos:definition "…"@zh` |
| `attributes` | — | `[{predicate, value: {iri} \| {value, datatype?, lang?}}]`，用于 `aisep:priority`、`aisep:path` 这类属性。合法与否由候选图上的 L1 闭世界规则（G7）判定，不另写白名单 |
| `file`、`dryRun` | — | §5.1 |

**IRI**：`{model}{slug}`。
- 已存在且三元组完全相同 → 成功，`changed: false`（幂等，代理超时重试安全）。
- 已存在但内容不同 → `IRI_EXISTS`，`details.existing` 给出现有类型和名称。元素的 slug 就是它的身份，**不自动加 `-2`**。

**输出**：`{ iri, file, changed, turtle, filesChanged: [{path, sha256Before, sha256After}], findings, preexistingViolations }`。`turtle` 是实际写入的片段，代理不用再读文件。`findings` 里每条带 `preexisting`（§5.1 第 5 步）。

**错误**：`MODEL_NOT_FOUND`、`UNKNOWN_TYPE`（`details.candidates` 给名字相近的最多 5 个类）、`ABSTRACT_TYPE`、`INVALID_ARGUMENT`、`IRI_EXISTS`、`WRITE_REJECTED`、`PARSE_FAILED`、`EDIT_UNSAFE`、`LOCKED`、`CONFLICT`。

**校验层**：候选图 L0–L2。

### 5.3 `model_add_relationship`

**输入**：`model?`（缺省取源端元素的模型）、`type`（限定关系类）、`source`、`target`、`file?`、`dryRun?`。

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

- **输入**：`sparql`（必填）、`limit`（缺省 1000，最大 10000）、`timeoutMs`（缺省 10000）、公共字段。
- **图**：构建后的图 + 全部本体 + 全部对齐（同原型 `cmd_query`，`use_default_graph_as_union=True`）。原型预声明的前缀都可用。
- **只读的落实**：
  - 只调 `Store.query`，从不调 `Store.update`。Update 语句解析失败（F5）→ `QUERY_NOT_READONLY`，message 写"只接受 SELECT/ASK/CONSTRUCT/DESCRIBE"。
  - 文本里出现 `SERVICE` 关键字（词法判断）→ `QUERY_NOT_READONLY`。原因：pyoxigraph 会真的发 HTTP 请求（F6）。
- **输出**（完整 IRI，不用 CLI 的缩写）：
  - SELECT：`{ kind: "select", variables, rows: [{ var: { type: "iri"|"literal"|"bnode", value, datatype?, lang? } }], truncated }`
  - ASK：`{ kind: "ask", value: boolean }`
  - CONSTRUCT/DESCRIBE：`{ kind: "triples", triples: [[s, p, o]], truncated }`
- **错误**：`QUERY_FAILED`（带解析器原文和行列号）、`QUERY_NOT_READONLY`、`QUERY_TIMEOUT`、`PARSE_FAILED`。
- L0 不过时**默认拒绝**：`PARSE_FAILED`，`details` 列出解析失败的文件。否则查询跑在少了文件的图上，调用方会把部分结果当完整结果。要诊断时传 `allowPartial: true`：照查，结果带 `partial: true` 和 `skippedFiles`，`findings` 里带 L0 违规。**与原型不同**（原型照查不提示），有意变更；P9 约束的是 gate 判定，不涉及查询。

### 5.7 `model_impact`

- **输入**：`focus`（IRI 或 `slug:local`）、`mode`（`depends`|`ripple`，缺省 depends）、`depth`（1–10，缺省 3）、`allowInvalid`（缺省 false）、公共字段。
- **G9**：先跑 L0–L2（同原型 `cmd_impact`）。
  - 有违规且 `allowInvalid: false` → `MODEL_INVALID`，`details.findings` 列出违规。
  - `allowInvalid: true` → 照算，结果带 `invalidModel: { violations: n }`，工作台必须醒目展示（对应原型的横幅）。
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
| `model` | ✔ | 记录写进 `models/<slug>/governance.ttl` |
| `gate` | ✔ | `GateRequirements` / `GateArchitecture` / `GateDesign` / `GateMerge` / `GateRelease`，展开为 `aisep:<gate>`；取值集合来自模块（F14、G2） |
| `decision` | ✔ | `Approved` / `Rejected` |
| `approvedBy` | ✔ | **已有**的 `arch:Stakeholder` 实例 IRI，且**不能**是 `aisep:AIAgent` 的实例（Q4=C 已拍板：AI 不能批准，违反 → `APPROVER_NOT_ALLOWED`）。不自动建人 |
| `approves` | ✔ | IRI 数组，≥1。每个都必须在 `headCommit` 里存在，是元素、模型或 ADR。工作台用 diff 的 added + modified 元素预填，人可以删减 |
| `branch` | ✔ | 记录提交到哪条分支（Q2=A：缺省传会话分支，随 PR 合入；主线上已有提交的批准（发布关口等）传短命批准分支，见下文"发布关口"，R2-15）。必须精确解析为 `refs/heads/<name>`；标签、远端跟踪分支、`HEAD~1` 这类修订表达式 → `INVALID_ARGUMENT`。`branch` 不能是 §3.3 解析出的模型主分支 → `INVALID_ARGUMENT`（`details.reason: "protected-branch"`），hint 指向"发布关口"的批准分支流程。理由：受保护分支禁止直接 push、不开例外（R2-15 已拍板），提交在本地主分支上的批准推不上去。原"本地主分支须等于跟踪远端，否则 `STALE_HEAD`"的同步校验随之取消 |
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
| `sessionRef` | ✔ | 非空字符串，不透明 | AO `session.id` | `aisep:sessionRef` |
| `branch` | — | 给了必须与顶层 `branch` 完全相同，否则 `INVALID_ARGUMENT` | — | `aisep:branch`（取顶层值） |
| `startedAt` | ✔ | 严格 xsd:dateTime（同原型 `parse_xsd_datetime`） | AO 会话创建时间 | `prov:startedAtTime` |
| `endedAt` | — | 缺省 = 服务器当前时间（UTC）；开始不晚于结束 | — | `prov:endedAtTime` |
| `label` | — | 缺省 `"AI 活动：{branch}"@zh`；工作台建议传任务标题 | AO 任务标题 | `skos:prefLabel` |
| — | — | 顶层 `headCommit` | — | `aisep:headCommit` |
| — | — | **服务器算** merge-base(headCommit, mainRef)；多个 → `AMBIGUOUS_MERGE_BASE` | — | `aisep:baseCommit` |

**执行**（一次提交）

1. **分支头校验**（不论有没有 activity）：设 tip = `branch` 当前头。
   - headCommit 必须是 tip 的祖先（或等于 tip），否则 `STALE_HEAD`。
   - headCommit..tip 之间**逐个提交**检查，不看净差异（先加后删的净差异可能为空）。范围内有合并提交（`git rev-list --min-parents=2 headCommit..tip` 非空）→ 直接 `STALE_HEAD`，不去定义"与哪个父提交比"（R2-9：取 first-parent 会漏掉侧分支带进来的代码提交）。其余每个中间提交（恰有一个父提交）必须同时满足：(a) 带 `AISEP-Evidence` trailer；(b) 只改**一个** `models/*/governance.ttl`（不限于本次调用的 `model`：同一分支先批准模型 A、再批准模型 B 时，A 的批准提交也要能过，R2-18）；(c) 该提交与其父提交的**源图差异**（复用 `model_diff` 的分组，§5.8，按 (b) 中那个模型计算）只有新增主语，且新增主语的类型只能是 `aisep:ApprovalRecord` 或 `aisep:AgentActivity`，没有任何修改或删除。
   - 上面"无合并提交 + 每个提交满足 (a)(b)(c)"下称**批准提交判据**。合并时 CI 调用同一个函数（见下文"合并时校验"）。
   - 任何一条不满足 → `STALE_HEAD`，`details: {tip, offendingCommit, reason}`，工作台提示"分支有新提交，请刷新差异后再批"（Q3=A 已拍板）。
   - 只按文件名判断不够：governance.ttl 也放 `arch:Stakeholder` 等元素（§5.1 缺省文件表；例子里就有 `:chiefArchitect a arch:Stakeholder`），代理可以在 headCommit 之后往里加人，再拿这个人当 `approvedBy`。
   - 这样同一会话可以连过多个关口：第一次批准提交满足 (a)(b)(c)。
   - 这一步在无锁状态下先做一遍，是为了在跑 5 秒的 gate 之前尽早拒绝；**真正生效的是第 7 步锁内的复验和提交后核对**。第 1 步到第 7 步之间代理照样可以用自己的 `git commit` 提交（它不碰 `aisep-write.lock`），只做第 1 步会让批准提交叠在一个没人看过的代码提交上（R2-1、R2-13，评审实测）。
   - **主线提交的批准**（R2-15）：`gate = GateRelease` 时 headCommit 必须是 mainRef 的祖先或等于它，否则 `INVALID_ARGUMENT`（`details.reason: "release-head-not-on-main"`）。headCommit 是 mainRef 的祖先或等于它（发布关口即此类）时带 `activity` → `INVALID_ARGUMENT`，`details.rejectedFields: ["activity"]`：此时 baseCommit 就是 headCommit，活动的差异为空；发布不是 AI 活动。
2. **evidence** = headCommit（§6.6 的 L1 规则天然满足）。
3. **gate**：在 headCommit 的快照（§3.3）上跑完整 gate。`decision=Approved` 而 FAIL → `GATE_FAILED`，附违规（Q6=A，第②项）。`Rejected` 不要求 PASS。gate 摘要随结果返回。
4. **去重**：
   - 已有活动的 `(sessionRef, headCommit)` 相同 → 复用该活动，不新建。
   - 已有记录的 `(gate, decision, approvedBy, approves 集合, evidence)` 相同 → 不写、不提交，返回那条记录，`duplicate: true`。evidence 来自调用方给的 headCommit，所以"提交成功但响应丢失"后的重放能命中，不会写第二条。
5. **生成**：
   - 记录 IRI `{model}approval-{yyyymmdd}-{slug}`（§3）；活动 IRI `{model}activity-{yyyymmdd}-{headCommit 前 7 位}`（§3 新增行，Q6=A 第⑥项）；重名加 `-2`。
   - `prov:generatedAtTime` = 服务器当前时间，UTC，`Z` 结尾（测试注入时钟）。
   - 在 `governance.ttl` 末尾追加活动块（如有）和记录块，记录用 `aisep:activity` 指向活动。
6. **校验**：候选图跑 L0–L2，走 §5.1 的新违规判定；另外 `Ctx.approval_problems` 和 `activity_problems` 对新记录、新活动必须为空（G1：与推导用同一个函数）。不合法的记录不参与推导，写入一条注定被忽略的记录没有意义。
7. **Git 落地**（只碰一个路径）：
   - 用 `git worktree list --porcelain` 找 `branch` 检出在哪个 worktree（下称 W）。没有检出 → `BRANCH_NOT_CHECKED_OUT`（v1 不做无检出的底层提交：底层提交不跑钩子，"不跳过 pre-commit"就做不到）。
   - **校验 W**（§3.3）：`realpath(W)` 不在 `--allow-root` 之下 → `PATH_OUTSIDE_ROOT`；common dir 与 `repo` 不同 → `WORKTREE_NOT_FOUND`。否则服务器会对仓库外的目录、甚至另一个仓库执行 `git commit`。
   - **锁 W 的写锁**（§3.4 第 1 步），与 W 里代理的 `model_*` 写入互斥。
   - W 不能是 detached HEAD；W 的模型文件集合（§3.3 统一口径）及其内容必须与 W 的 `HEAD` 完全一致（`git status --porcelain -- models/` 为空只是其必要条件），否则 `DIRTY_WORKTREE`（避免把别人的改动卷进来，也保证 pre-commit 的 gate 看到的模型就是"已提交 + 本次追加"）。若脏的正是 governance.ttl 且多出的内容是一条批准记录，`details.orphanApproval: true`，hint 给出恢复命令（多半是上次调用在提交前被杀）。
   - **锁内复验**：取 `git -C W rev-parse HEAD` 为 tip'，对它**重跑第 1 步的全部校验**（祖先、合并提交、逐提交 (a)(b)(c)、去重），记下 tip'。不过 → `STALE_HEAD`，不写。
   - 记下 governance.ttl 的字节和 sha256 → 追加写入（§3.4）→ `git commit` 前再比一次 sha256，不等 → 恢复原字节、`CONFLICT` → `git commit --only -m "aisep: <gate> <decision> <记录短名>" --trailer "AISEP-Evidence: <evidence>" [--trailer "AISEP-Session: <sessionRef>"] -- models/<slug>/governance.ttl`。
   - **不加 `--no-verify`**，pre-commit 的 gate 照常跑。作者身份取仓库自己的 git 配置，服务器不改。
   - **提交后核对父提交**：新提交记为 A。`A^` 必须等于 tip'。复验到 `git commit` 之间仍有毫秒级窗口，代理在此期间提交的 C 会让历史变成 tip'–C–A。不等时撤回本次提交：`git update-ref refs/heads/<branch> A^ A`（比较并交换，只在分支头仍是 A 时生效，C 原样保留）；governance.ttl 仍等于本次写入后的 sha256 时，用内存里写入前的原字节恢复磁盘（脏检查已保证它就是 `A^` 里的内容），再 `git update-index -- <该路径>` 同步 index（同第 8 步，不用 `git restore`）；然后报 `STALE_HEAD`（`details.reason: "concurrent-commit"`）。`update-ref` 的比较失败（A 之上又有新提交）→ 不再动分支，报 `CONFLICT`（不可重试），`details` 给出 A 和恢复提示，由人处理。不采用"临时 index + `commit-tree` + `update-ref` 原子提交"：它绕开仓库钩子，第一轮 #24 已否决。
8. **回滚**：commit 失败（钩子拒绝、`index.lock` 被占用）→ 文件仍等于本次写入后的 sha256 时，恢复为写入前的原字节；不等（钩子或编辑器改过）→ 保留现场，返回 `CONFLICT`。**不用** `git restore`（会抹掉未知的外部改动）。之后 `COMMIT_FAILED`，附钩子输出最后 50 行。
9. **崩溃窗口如实写明**："追加写入"到"commit 结束"之间进程被杀，会留下一条未提交的批准块。下一次调用在第 7 步以 `DIRTY_WORKTREE` + `orphanApproval` 报出来；pre-commit 不会拦它（记录本身合法），所以代理侧的提交规范要求不用 `git commit -a`。改用临时 index + `commit-tree` 能消除这个窗口，但会绕开仓库钩子，v1 不取。
10. **批准之后再提交代码**（R2-13 已拍板）：第 1、7 步只管到本次提交为止。之后分支上再有代码提交，由合并时 CI 用同一判据拒绝（见下文"合并时校验"），旧批准不会随合并进主线。

**合并时校验**（R2-13 已拍板，与 Q3=A 合为一条规则）

规则：批准记录的 evidence（有活动时就是活动的 headCommit）到所在分支头之间，只允许出现满足批准提交判据（第 1 步）的提交。记录时刻由第 1、7 步核对；合并进受保护分支前由 CI 再核对一次，判据相同、调用同一个函数。evidence 等于分支头是其特例（范围为空）。

CI 设为受保护分支的必需检查，PR 每次更新都跑：

1. **查哪些记录**：本 PR 新增（`merge-base(主分支, PR 头)` 上没有）、且在 PR 头上推导 approvalState 时被采用的批准记录（与推导同一个函数，G1）。已被同关口、同对象的新记录取代的旧记录不查：否则"批准后改代码 → 重新过关口"之后，旧记录会让 PR 永远过不了。
2. **逐条核对**：evidence 必须是 PR 头的祖先；`evidence..PR 头` 跑批准提交判据。范围只含分支这一侧的提交，不含合并时产生的合并提交本身。任一不满足 → 拒绝合并，报出 `offendingCommit`，要求在新的提交上重新过关口。批准后把主分支合进本分支，范围里会出现合并提交，同样被拒。
3. **合并结果 gate**：在合并结果（托管平台的预合并提交，或 CI 本地 `git merge --no-ff`）上跑一次 `model_gate`，FAIL → 拒绝合并。批准期间主线可能前进，两边各自 PASS 不保证合并后 PASS。

**批准专用 PR**（R2-15，防死循环）

批准分支的 PR 若也要求先过关口，就会再产生一条批准、再开一个 PR。CI 先判定：`merge-base(主分支, PR 头)..PR 头` 非空，且整段满足批准提交判据 → 批准专用 PR：只跑上面的合并时校验（含合并结果 gate）和下文的发布标签检查，不要求再过关口。夹带任何其他提交 → 按普通 PR 处理。判定由 CI 执行，负例见 T39。

**发布关口**（R2-15 已拍板：短命批准分支 + PR，受保护分支不开例外）

1. 人在关口页选定**被发布的那个主线提交** R（mainRef 上的某个提交，不一定是最新）。工作台从 R 拉分支并检出：`git worktree add -b approval/release-{R 前 7 位} <目录> R`，目录在 `--allow-root` 之下。**必须从 R 拉**：从主线最新提交拉时，R 之后的主线提交落在 R..分支头之间，第 1 步报 `STALE_HEAD`；绕过 MCP 造出来的分支也会被合并时校验拒绝。
2. 调 `record_approval`：`gate: GateRelease`，`branch` = 该批准分支，`headCommit` = R，不带 `activity`。分支上只有这一个批准提交，evidence = R。合并时校验对它同样适用：R..分支头只有这一个批准提交。
3. 工作台给 R 打标签 `release/{yyyymmdd}-{R 前 7 位}`（批准日期，UTC；带短 hash 避免同日重名；也可另用版本号 `release/v…`），推送标签和分支，开 PR。PR 按批准专用 PR 处理，合并后删分支。标签让 R 不依赖分支存活、不被 GC。
4. **发布标签检查**（CI）：PR 新增的每条 `GateRelease` 记录，远端都要有一个 `refs/tags/release/*` 指向其 evidence，否则失败。
5. MCP 只做第 2 步的一次提交；拉分支、打标签、推送、开 PR 由工作台做，MCP 不推送、不打标签、不开 PR。

**输出**

```jsonc
{ "approval": { "iri": "…/approval-20261120-architecture-9c41e07", "file": "models/procurement/governance.ttl" },
  "activity": { "iri": "…/activity-20261120-9c41e07", "reused": false },
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

- 字段名与 `model_add_element` 一致（§5.2）。三个字段至少给一个，否则 `INVALID_ARGUMENT`；未给出的字段保持不变。别的语言的标签不动。
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

---

## 6. `aisep:AgentActivity` 定稿与 PROV-O

### 6.1 字段表

`aisep:AgentActivity ⊑ arch:Element, prov:Activity`。和批准记录一样不属于任何记法，是具体类。

| 字段 | 基数 | 取值 | 校验层 | 谁填 | 与 v0.4 草案相比 |
|---|---|---|---|---|---|
| `rdf:type aisep:AgentActivity` | 1 | — | L1 | 服务器 | 不变 |
| IRI | — | `{model}activity-{yyyymmdd}-{headCommit 前 7 位}`，重名加 `-2`；必须是 IRI，不能是空白节点 | 写入层；L1 + EG25 | 服务器 | **新增** IRI 规则 |
| `arch:inModel` | 1 | 模型 IRI | L1 | 服务器 | 不变 |
| `skos:prefLabel` | 1 `@zh` | 缺省 `"AI 活动：{branch}"`，工作台传任务标题 | L1 | 客户端可给 | **写明**（元素通则本来就要求） |
| `prov:wasAssociatedWith` | 1 | `arch:Stakeholder` 的实例，或 `aisep:AIAgent` 的实例（Q4=C） | L1 + EG17 | 客户端 | **放宽**：可指向 `aisep:AIAgent` |
| `prov:startedAtTime` | 1 | 严格 xsd:dateTime | L1 + EG24 | 客户端 | 不变 |
| `prov:endedAtTime` | 1 | 同上；开始 ≤ 结束（按时区归一化，不带时区按 UTC） | L1 + EG24 | 客户端或服务器 | 不变 |
| `aisep:sessionRef` | 1 | 非空字符串，对元模型不透明 | L1 | 客户端 | 不变 |
| `aisep:branch` | 1 | 非空字符串 | L1 | 客户端 | 不变 |
| `aisep:headCommit` | 1 | `^[0-9a-f]{40}$`；= 被批准的 commit；批准记录 evidence 为 commit 时必须相等 | L1 | **服务器核对后填** | **写明**来源 |
| `aisep:baseCommit` | 1 | `^[0-9a-f]{40}$`；= merge-base(headCommit, 模型主分支) | L1 只查格式；是否等于 merge-base 由写入层保证（L1 不查 Git） | **只由服务器算** | **写明**来源 |
| 唯一性 | — | 一个 `(sessionRef, headCommit)` 只有一条；同一 head 过多个关口复用 | 写入层 | — | **新增** |
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
4. `retryable` 只对 `LOCKED`、`CONFLICT`（`record_approval` 撤回失败那一种除外）、`WORKTREE_CHANGED`、`COMMIT_FAILED`（锁占用时）、`QUERY_TIMEOUT` 为 true；其他原样重试没有意义。`PLAN_STALE` 不可重试：带同一个旧 `planDigest` 重试永远失败，要先重新 `dryRun`。

`content[0].text` 放同一句 `message` + `hint` + 发现项的 CLI 格式行。

### 7.2 错误码

| 类别 | 错误码 | 可重试 |
|---|---|---|
| 参数 | `INVALID_ARGUMENT`、`UNKNOWN_TYPE`、`ABSTRACT_TYPE`、`INVALID_DATETIME`、`ACTIVITY_TIME_ORDER`、`GATE_UNKNOWN` | 否 |
| 定位 | `MODULES_NOT_IN_REF`、`PATH_OUTSIDE_ROOT`、`NOT_A_GIT_REPO`、`NOT_A_WORKTREE`、`MODEL_NOT_FOUND`、`ELEMENT_NOT_FOUND`、`REF_NOT_FOUND`、`BRANCH_NOT_CHECKED_OUT`、`WORKTREE_NOT_FOUND` | 否 |
| 语义拒绝 | `PLAN_STALE`、`STALE_BASE`、`WRITE_REJECTED`、`REFERENCED`、`CASCADE_REQUIRED`、`PROTECTED_RESOURCE`、`IRI_EXISTS`、`MODEL_INVALID`（G9）、`GATE_FAILED`、`APPROVER_NOT_ALLOWED`、`AGENT_NOT_ALLOWED`、`STALE_HEAD` | 否 |
| Git | `NO_MERGE_BASE`、`AMBIGUOUS_MERGE_BASE`、`DETACHED_HEAD`、`DIRTY_WORKTREE`、`COMMIT_FAILED` | `COMMIT_FAILED` 视原因 |
| 并发 | `LOCKED`、`CONFLICT`、`WORKTREE_CHANGED` | **是**（`record_approval` 提交后撤回失败时的 `CONFLICT` 除外，见 §5.9 第 7 步） |
| 解析 | `PARSE_FAILED`、`EDIT_UNSAFE`、`DIFF_PARSE_FAILED`、`DIFF_BNODE_UNSUPPORTED`、`QUERY_FAILED`、`QUERY_NOT_READONLY`、`QUERY_TIMEOUT` | 只有超时是 |
| 其他 | `INTERNAL`（带 stderr 摘要） | 否 |

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

export interface Target { repo?: string; ref?: string } // 工作台总是传 repo 和 ref

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
export type QueryResult =
	| { kind: "select"; variables: string[]; rows: Record<string, Term>[]; truncated: boolean }
	| { kind: "ask"; value: boolean }
	| { kind: "triples"; triples: [Term, Term, Term][]; truncated: boolean };
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
	items: ImpactItem[];
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
	base: { ref: string | null; commit: Sha; viaMergeBase: boolean; mainRef?: string };
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
	truncated: boolean;
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

/** 工作台用到的 6 个工具；写模型的 4 个工具（model_add_element、model_add_relationship、model_remove、
 *  model_set_labels）不进工作台（一期），所以这里没有对应方法。 */
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
// ELEMENTS_QUERY 保留（D4），但只选**有** arch:approvalState 的主语（去掉 OPTIONAL）：批准记录、AI 活动也是 arch:Element、
// 也有 inModel 和 zh 名称，却没有 approvalState（实测：采购例子里 approval-20261119-arch-baseline 就是这样）。
// 沿用"缺失 → Proposed"会让批准记录以 Proposed 出现在待批准关口，这个状态不是推导给出的，违背 P4。
// elementsFromRows 改为读 Term.value，approvalState 用 APPROVAL_STATE_IRI 映射；缺失或映射不到的 IRI 直接抛错。
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

> 设计会话 2026-11-20 已拍板 Q1–Q6（§10.1），下列改文按拍板结果写，每条仍标出出处是哪一问。偏离规范字面的 8 项（写工具不提交、批准要求 gate PASS、BPMN 成员摘除、受保护资源、不收调用方的 evidence/baseCommit、新增 IRI 规则、写前只拒新增违规、新增 `model.gate`）按 Q6=A 整体接受，附两个条件：条件一 `model.diff` 可比较工作区未提交改动（下文 §8.3、附录 C、ADR-013 三处改文），条件二遗留违规由 `model.findings` 的 openViolations 给出（下文 §8.3）。另有一项不在这 8 项里、由用户在另一会话单独拍板的扩展：新增 `model.set_labels`（下文 §3、§8.3 两处）。

**§0 状态行**，把"AgentActivity 与两个 MCP 工具在 MCP 接口设计时一并定稿"替换为：

> AgentActivity 与 `model.diff`、`governance.record_approval` 已在《MCP Server 接口设计》中定稿（ADR-014）。

**§3 表格**，在"批准记录"一行之后新增（前提 Q6）：

> | AI 活动 | `{model}activity-{yyyymmdd}-{headCommit 前 7 位}`，重名时加 `-2` | `…/procurement/activity-20261120-9c41e07` |

**§3 表格"关系"一行**，在格式后补一句（前提 Q6）：

> 直连谓词本地名取关系类最近的 `arch:unqualifiedForm`；类没有声明时取类本地名，首字母小写。

**§3 列表末尾**，加一条：

> - 现有手写 IRI 不按本表重命名（slug 一经创建不改）；本表只约束写入层新生成的 IRI。

**§3 列表"slug 用可读英文 camelCase……改名只改标签"一条**，在"改名只改标签"之后补（`model.set_labels`，另一会话拍板）：

> 改标签经 `model.set_labels` 写入（§8.3）。

**§6.6**，`aisep:approvedBy` 一条替换为（Q4=C）：

> - `aisep:approvedBy` → 人（必须是 `arch:Stakeholder` 的实例，且不能是 `aisep:AIAgent`；AI 不能批准，原则五）；

**§6.6**，`aisep:evidence` 一条的最后一句"经 MCP 写入时自动填写。"替换为（前提 Q3、Q6）：

> 经 MCP 写入时自动填写：取调用方给出的 headCommit（人评审的那个提交；有活动时等于该活动的 `aisep:headCommit`），写入层核对它与分支头之间只有批准提交：其间不得有合并提交，每个提交都带 `AISEP-Evidence` trailer、只改一个模型的 governance 文件、且源图只新增批准记录或 AI 活动（无修改、无删除）；该核对在提交前持锁复做一次，提交后父提交不是被核对的分支头时撤回。写入前在该提交上运行 `gate`，结论为 Approved 而 gate 未通过时拒绝写入。

**§6.6**，`aisep:evidence` 一条之后新增两段（R2-13、R2-15）：

> 批准提交判据：一个提交只有一个父提交，带 `AISEP-Evidence` trailer，只改一个模型的 governance 文件，且相对父提交源图只新增批准记录或 AI 活动（无修改、无删除）。批准记录的 evidence（有活动时即活动的 headCommit）到所在分支头之间只允许出现满足该判据的提交；evidence 等于分支头是其特例。写入时由写入层核对；合并进受保护分支前由 CI 用同一判据再核对一次（范围 `evidence..分支头`，不含合并提交本身；只查本次合并新增、且推导 approvalState 时被采用的记录），并在合并结果上运行 `gate`，任一不通过即拒绝合并，须在新的提交上重新过关口。只含批准提交的合并请求只做上述核对与 `gate`，不要求再过关口；夹带其他提交的按普通合并请求处理。
>
> 已在主分支上的提交（如发布关口）的批准不直接提交到主分支：从被批准的那个提交拉短命分支，只提交这一条批准记录，经合并请求合入后删分支。这类批准不带 AI 活动。发布关口的 evidence 是被发布的主分支提交，该提交打 `release/{yyyymmdd}-{前 7 位}` 标签（或版本号标签 `release/v…`）。

**§6.7**，`aisep:AgentActivity` 整条替换为（前提 Q4；IRI 与唯一键前提 Q6）：

> - `aisep:AIAgent` ⊑ `arch:Element`、`prov:SoftwareAgent`（aisep-core 另声明 `prov:SoftwareAgent ⊑ prov:Agent`；不加载 PROV-O 本体）：执行任务的 AI 代理，按元素通则写名称和 `arch:inModel`。
> - `aisep:AgentActivity` ⊑ `arch:Element`、`prov:Activity`（ADR-013、ADR-014）：一次**已完成**的 AI 活动。只在任务过关口时由 `governance.record_approval` 写入，与批准记录在同一次提交里；进行中的状态不进模型仓库。一个（sessionRef, headCommit）只有一条，同一 head 过多个关口时复用；IRI 见 §3。字段：
>   - `skos:prefLabel` 恰好一个 `@zh`（缺省"AI 活动：{分支}"，建议写任务标题），`arch:inModel` 恰好一个；
>   - `prov:wasAssociatedWith` → 执行的代理，恰好一个，必须是 `arch:Stakeholder` 或 `aisep:AIAgent` 的实例；
>   - `prov:startedAtTime`、`prov:endedAtTime`，各恰好一个 xsd:dateTime，开始不晚于结束（按时区归一化，不带时区的按 UTC）；
>   - `aisep:sessionRef`：外部编排器的会话标识，非空字符串，恰好一个；对元模型不透明，不绑定 AO；
>   - `aisep:branch`：分支名，非空字符串，恰好一个；
>   - `aisep:baseCommit`、`aisep:headCommit`：各恰好一个 40 位十六进制 commit，**只由写入层填写**：headCommit 是被批准的那个 commit（写入层核对它与分支头之间只有批准提交），baseCommit 是它与模型主分支的 merge-base。L1 只校验格式。
>   - **不存"作用于哪些元素"**：由 `model.diff(baseCommit, headCommit)` 实时算出（§8.3）。

**§8.2**，"**未原型化**……在 MCP Server 里实现。"替换为（前提 Q6）：

> - 删除由 `model.remove` 执行（接口文档 §5.5）。删除集从目标开始，反复加入以删除集成员为 `arch:source` 或 `arch:target`、且与目标同属一个模型的限定关系，直到不变；删除集成员在本模型文件里作为主语的三元组全部删除。判据在模型源文件上算，不用构建后的图。外部引用中，`arch:inView` 与 BPMN 成员属性（flowElements、flowNodeRefs、lanes、laneSets）摘除；其他谓词（含批准、替换、追溯、`bpmn:default`）与跨模型引用（含别的模型里以目标为端点的关系）一律拒绝并列出，提示改用 `owl:deprecated` + `dcterms:isReplacedBy` 退役。批准记录、AI 活动、模型本身不能删除。默认不级联（有牵连即拒绝并返回计划），`cascade` 显式开启；支持 dryRun。删除后不得引入新的 L0–L2 违规，否则整体不写。按主语块编辑文本，编辑后必须与预期的图等价，否则不写。

**§8.3 表格**（前提 Q6）：

- `model.add_element` 一行"对应层"改为：`写入前在候选图上跑 L0–L2，只拒绝新增的违规；结果逐条标明违规是写前已有还是本次新增`。
- `model.check / model.validate` 一行之后插入：

> | `model.gate` | 只读，原子执行 L0–L4，一份合并结论；提交、CI 与关口页只认它（G10） | L0–L4 |

- `model.remove` 一行之后插入（`model.set_labels`，另一会话拍板，合并时并入）：

> | `model.set_labels` | 只改名称（`skos:prefLabel` @zh）、英文名（`skos:altLabel` @en）、定义（`skos:definition` @zh），IRI、类型、关系不变；§3"改名只改标签"的写入口。批准记录、AI 活动不能改 | 写入前在候选图上跑 L0–L2，只拒绝新增的违规 |

- `governance.record_approval` 一行替换为：

> | `governance.record_approval` | 新增一条批准记录（不改状态字段）。顶层必填 branch、headCommit（有无活动都必填）；可选 expectedBaseCommit，只用于核对、不写入（不等于被拒收的 baseCommit）。写入层核对 headCommit 与分支头之间只有批准提交（无合并提交；每个提交带 `AISEP-Evidence` trailer、只改一个模型的 governance 文件、源图只新增批准记录或 AI 活动），提交前持锁复核。branch 不能是主分支；headCommit 已在主分支上时不接受活动信息；发布关口的 headCommit 必须在主分支上。可选活动信息只含代理、sessionRef、起止时间和标签：写入层算出 baseCommit，在同一次提交里写入 `aisep:AgentActivity`（分支、headCommit 取顶层值）并用 `aisep:activity` 关联；evidence 取调用方给出的 headCommit，generatedAtTime、baseCommit 由写入层填，不接受调用方传入 evidence、generatedAtTime、baseCommit。Approved 要求 evidence 处 gate 通过。只提交 `governance.ttl` 一个路径，不跳过 pre-commit | L0–L2 + gate |

- `model.findings` 一行替换为（Q6 条件二）：

> | `model.findings` | L4；另返回 openViolations：同一份内容上 L0–L2 的全部违规（结构化发现项），供查看写入时被放过的遗留违规。openViolations 不新增层级，不计入 gate 结论 | L4（openViolations 复用 L0–L2） |

- `model.diff` 一行**整行替换**为（Q6 条件一；原文"只读 Git 对象"与 worktree 模式冲突，不能只在末尾追加）：

> | `model.diff` | 只读。base 是 Git 引用（不给时取 head 侧 commit 与模型主分支的 merge-base）；head 有两种：Git 引用，或某分支检出的工作区（按分支名经 `git worktree list` 定位，只接受分支名，不接受路径）。工作区内容 = 该工作区模型目录下已跟踪 Turtle 文件的当前内容 + 未跟踪且未被忽略的新 Turtle 文件 − 已在工作区删除的文件。返回新增、修改、删除的元素和关系清单（按 IRI；同一 IRI 的三元组有变化算修改；改关系类型按 §8.2 表现为删除加新增）。比较的是两边模型源文件的并集图（构建前）；三元组在文件间移动、排版和注释变化不算修改。多个 merge-base 时报错，要求显式给 base。结果按 kind（element / relationship / view / governance / schema / other）分组计数；detail 取 summary / items / triples；标明 head 的种类、对应 commit 和工作区是否有未提交改动。工作区里某个文件解析失败时，结果标为不完整并列出失败文件，其余照常比较，失败文件里的主语不判为删除。无状态，不写任何东西，可从任意 worktree 调用 | L0 |

- 表后段落"`model.diff` 同时服务两处：……v1 只比较已提交内容；前提是……（见附录 C）。"一句中，把"v1 只比较已提交内容；"替换为：

> "AI 进行中"缺省比较会话分支的工作区（含未提交改动），关口页差异图和批准只认已提交的 commit；

- 表后"接口的具体设计另写文档。"替换为：

> 接口的具体设计见《MCP Server 接口设计》（`docs/mcp-interface.md`）。线上工具名把点换成下划线（`model.diff` → `model_diff`）。写工具只改工作区、不提交；`governance.record_approval` 例外，自己做一次只含 governance 文件的提交。

**附录 C**：
- 第 1 条"`model.diff` v1 只比较已提交内容：进行中的会话在提交前，"改动元素"一栏为空或滞后。"**删除**（Q6 条件一：worktree 模式取消了这条限制）。在原位置改写为：

> - `model.diff` 的 worktree 模式读的是会话分支检出的工作区：会话的工作区已被清理（只剩分支）时退回只比较已提交内容；工作区里写到一半的文件会让结果标为不完整（失败文件里的主语不计）。index（暂存区）与磁盘不同时以磁盘为准。

- 第 2 条（同仓同分支的前提）**保留不动**。
- "`rm` 级联删除（§8.2）没有原型化"一项删去 `rm` 部分（实现后）。
- PROV-O 一条替换为（Q4=C）：

> - PROV-O 不整体加载；aisep-core 只声明 `aisep:AIAgent`，另在其对齐文件里加 `prov:SoftwareAgent ⊑ prov:Agent` 一条（ADR-010），其余 PROV-O 术语不可用，G7 白名单不变。

- 新增：

> - 历史批准的差异图和 gate 重跑依赖 headCommit 仍可达。模型仓库禁用 squash 合并和 rebase 合并，批准提交只经普通 merge 进受保护分支（ADR-014）；落实要同时做到：托管平台关闭 squash、rebase 两种 PR 合并方式，受保护分支禁止 force push、限制直接 push，PR 合并保留原提交（cherry-pick、rebase 都会生成新的 commit id）。这些是仓库托管平台的设置，元模型和 MCP 不检查；CI 可另加一步检查批准记录的 evidence 是目标受保护分支的祖先。绕过它合入、或分支未合并就删除时，旧 commit 可能被 GC，历史批准无法重跑。
> - 合并时校验（evidence 到分支头之间只有批准提交、合并结果 gate）、批准专用合并请求的判定、发布标签检查由 CI 执行，须设为受保护分支的必需检查；元模型和 MCP 不检查 CI 是否配上。
> - 写入层对工作区文件的"写前哈希核对"不是真正的比较并交换：不遵守写锁的外部编辑器或 Git 命令在核对与替换之间（毫秒级）写入的内容会被覆盖。
> - `model.remove` 只检查本仓库：独立模型仓库里指向被删元素的引用看不到，删除后会在那边悬空。
> - `governance.record_approval` 在"追加写入"与"提交完成"之间被杀，会留下未提交的批准块；下次调用以 DIRTY_WORKTREE 报出，需人工清理。多文件写入同样不是崩溃原子的，由 gate 兜底。
> - `model.remove` 对 BPMN 成员属性以外的引用一律拒绝，放开需要逐条进规范。布局文件出现前，删除不处理布局。

**§13**，删去"不在第一批范围"里的"MCP 接口的具体设计（另写文档）"一项：ADR-008 已定一期交付物是 MCP Server，本文就是它的接口设计。

**`docs/decisions.md`**：新增 ADR-014「MCP Server 接口定稿」，记录第 10 节的拍板结果（Q1–Q6 及 Q6 的两个条件、新增 `model.set_labels`、Q5 的禁用 squash/rebase 合并、R2-13 的合并时校验、R2-15 的短命批准分支与发布标签）。

**ADR-013 的修订文字**（Q6 条件一。设计会话口述为"ADR-010"，核对后"v1 只比较已提交内容"实际写在 **ADR-013** 的"后果"一条和规范附录 C 第 1 条，ADR-010 讲的是对齐文件，与此无关；按 ADR-013 改）：

- "状态"一条中"元模型与 MCP 部分为草案，与 MCP 接口设计一并定稿"替换为：

> 元模型与 MCP 部分已由 ADR-014 定稿；2026-11-20 设计会话拍板时修订"后果"中的 diff 限制（见下）

- "后果"一条末尾"已知限制：v1 只比较已提交内容，且要求模型与代码同仓同分支（规范附录 C）。"替换为：

> 已知限制：要求模型与代码同仓同分支（规范附录 C）。（2026-11-20 修订：原"v1 只比较已提交内容"撤销。MCP 写工具只改工作区不提交，只比已提交内容会让"AI 进行中"在批准前一直为空；`model.diff` 改为也能比较会话分支检出的工作区，按分支名定位、不接受路径，"AI 进行中"缺省用这一模式；关口页差异图和批准仍只认已提交的 commit。）

- "决策"一条不改：改动元素仍由分支差异实时算出、起点仍为 merge-base，worktree 模式只是把 head 侧从"分支头 commit"扩展到"分支的工作区"，不新增状态、不新增上报写工具。

**`docs/module-contract.md`**：AgentActivity 一条去掉"draft"；`impact` 一行补"未知元素退出码 1"（若采纳 §3.1 的建议）。

---

## 10. 设计会话的拍板

> **状态**：Q1–Q6 已由设计会话于 2026-11-20 拍板，全部按推荐，Q5、Q6 带附加条件（下表）。附加条件已落进正文，并已过第二轮评审（含一路 GPT 异构，T33）；第二轮转设计会话的两条（R2-13、R2-15）已于同日拍板，见 §10.1 末两行。§10.2 的默认项设计会话未提异议，维持。

### 10.1 已拍板（6 题 + 第二轮转来 2 条）

| # | 问题 | 结论 | 日期 | 附加条件 | 落点 |
|---|---|---|---|---|---|
| Q1 | 工作台传输与 HTTP 设防 | **B**：本机 Streamable HTTP，只绑 `127.0.0.1`，CORS 精确白名单 | 2026-11-20 | 无新增；维持原附带条款：开发期不加令牌为接受的风险，打包前必须定令牌方案 | §3.2 |
| Q2 | 批准提交写到哪条分支 | **A**：缺省写会话分支；"待批准关口"读主分支，另查分支上的"已批准、待合并"标记 | 2026-11-20 | 无 | §2、§5.9 |
| Q3 | headCommit 落后于分支头时能否批准 | **A**：只允许 headCommit..tip 之间全是批准提交 | 2026-11-20 | 无 | §5.9 第 1 步、T23 |
| Q4 | AI 代理建模、`approvedBy` 是否只收人 | **C**：最小桩 `aisep:AIAgent` + `approvedBy` 排除 AI | 2026-11-20 | 无 | §5.9、§6、§9（§6.6、§6.7、附录 C） |
| Q5 | 历史批准提交的保留策略 | **A**：模型仓库禁用 squash 合并 | 2026-11-20 | **同时禁用 rebase 合并**：批准提交只经普通 merge 进受保护分支。理由：rebase 合并会给每个提交生成新的 commit id，原来的 headCommit 不再在受保护分支的历史里，与 squash 一样使活动的 `aisep:headCommit`、记录的 `aisep:evidence` 指向一个随后可能被 GC 的提交，§5.9 的"evidence = 被批准的 commit"和历史差异图都失效。这是仓库托管平台的分支保护设置，接口不检查 | §5.8 用途表、§9 附录 C |
| Q6 | 是否整体接受 8 项偏离 | **A**：整体接受 | 2026-11-20 | **条件一**：第①项（写工具只改工作区不提交）会让"AI 进行中"在批准前一直为空，要求 `model.diff` 能比较工作区未提交改动，撤销"只比已提交内容"的限制（设计会话说的是 ADR-010，实际在 ADR-013 与规范附录 C 第 1 条，按 ADR-013 改）。**条件二**：第⑦项（写前只拒新增违规）留下的遗留违规要能经 findings 查到，并在工作台可见 | 条件一：§5.8（worktree 模式）、§2、§4、§8、§9、T35–T36；条件二：§5.1、§5.4、§7.3、§8、T37 |
| R2-13 | 批准后再提交代码，旧批准会随合并进主线 | **新增规则**：批准记录的 evidence（= 关联活动的 headCommit）到分支头之间只允许批准提交（§5.9 批准提交判据）；记录时刻（`record_approval`）与合并时刻（CI）用同一判据，与 Q3=A 合为一条；合并时另在合并结果上跑一次 `model_gate` | 2026-11-20 | **澄清**：用户原话为"Q5 已定的合并时分支最新提交必须等于 headCommit"；Q5 实际只定了禁用 squash/rebase 合并，且严格相等与 Q3=A 冲突（第一次批准提交就让分支头前进），统一按"只允许批准提交"表述，相等是其特例。CI 检查范围是 `evidence..分支头`（分支这一侧），不含合并提交本身。旧批准随合并进主线的残余风险已从 §5.9、附录 C 删除 | §5.9 第 1、10 步与"合并时校验"、§9（§6.6、§8.3、附录 C）、T38 |
| R2-15 | 发布关口等主线上已有提交的批准如何与受保护分支共存 | **短命批准分支 + PR**，不给分支保护开例外：从被发布的主线提交拉分支，只含一个批准提交，PR 合入后删分支；主线上的发布批准不带 AI 活动（带了 → `INVALID_ARGUMENT`）；只改批准记录的 PR 只跑 gate、不再过关口，夹带其他改动按普通 PR，由 CI 判定；evidence 指向被发布的提交并打标签；R2-13 的规则对批准分支同样适用 | 2026-11-20 | **澄清**：① 从**被发布的那个提交**拉分支，不是主线最新提交，否则主线前进后 R2-13 的规则会拒绝；② 标签名 `release/{yyyymmdd}-{短hash}` 或版本号，避免同日重名，同时防 GC | §5.9 输入表 `branch` 行、第 1 步与"批准专用 PR""发布关口"、§9（§6.6、§8.3、附录 C）、T23、T39、T40 |

**原问题、选项与推荐理由（存档，供追溯）**

| # | 问题 | 选项 | 推荐与理由 |
|---|---|---|---|
| Q1 | 工作台用什么传输，HTTP 怎么设防 | A：Electron 主进程起 stdio 子进程，经 preload/IPC 给 renderer；B：`--transport http` 只绑 `127.0.0.1`，协议 2026-07-28（无握手、无会话），renderer 直接 `fetch`；CORS 精确白名单（`app://renderer` + 开发期 dev server 源，永不放 `*`/`null`），带 Origin 且不在白名单 → 403；C：工作台不走 MCP，直接调 CLI | **B**。P10 把上游接触面定死了，A 要改 `main.ts`、`preload.ts` 两个上游文件；C 违背 ADR-008。附带要定的一条：**开发期不加令牌**，不带 Origin 的本机进程（如 `curl`）能调到 `record_approval` 并产生批准提交，这是接受的风险，与 AO daemon 同级；**打包前**必须定令牌方案（建议每次启动生成、经已有的受信渠道交给 renderer） |
| Q2 | 批准提交写到哪条分支，"待批准关口"怎么显示 | A：缺省写会话分支（随 PR 合入），发布关口等合并后的批准显式传 `branch: main`（已被 R2-15 取代：发布批准走批准分支）；"待批准关口"读主分支，另对有会话的分支用 `model_query(ref=branch)` 查出"已在分支批准、待合并"标记；B：同 A，但"待批准关口"整体按分支读；C：永远写主分支 | **A**。批准和被批准的版本在同一条分支，合并后历史自然连在一起；C 会让 `approves` 指向主分支上还不存在的元素（G8 那类悬空）。A 的显示方式保证每个状态都出自所读那份内容的批准记录（P4），又不会让人把已批的元素再批一次。代价：分支被放弃时批准记录随之丢失，而被放弃的分支本来不需要批准 |
| Q3 | headCommit 落后于分支头时能否批准 | A：允许，但 headCommit..tip 之间每个提交都必须是批准提交（带 trailer、只改 governance.ttl、源图差异只新增 ApprovalRecord/AgentActivity 主语）；B：任何祖先都可以；C：必须严格等于分支头 | **A**。B 会出现"批准了旧版本，新提交没人看就随合并进主线"；C 让同一会话连过第二个关口时失败（第一次批准提交已让分支头前进）。A 逐提交按语义判，堵住了"往 governance.ttl 里塞新人员或元素"和"先加后删、净差异为空"两条绕过路径，可测（T23） |
| Q4 | AI 代理怎么建模，`approvedBy` 是否只收人 | A：现状（Stakeholder 兼任）；B：vendor 整个 PROV-O；C：`aisep:AIAgent` 最小桩（对齐公理放 aisep-core 对齐文件）+ `approvedBy` 排除 AI；C'：只加桩，不收紧 `approvedBy` | **C**。见 §6.2：改动最小，不打开 G7 的口子，用规则保证原则五"人工把关"。代价：拆 `AGENTS`、改 L1/EG13/EG17、加 2 个非法夹具 |
| Q5 | 历史批准提交的保留策略（squash、删分支后 headCommit 可能被 GC） | A：模型仓库禁用 squash 合并，批准提交经普通合并进受保护分支（分支保护规则）；B：`record_approval` 另写保活 ref `refs/aisep/activity/<id>`；C：接受限制，登记附录 C，不再声称历史可复现 | **A**，做不到就 **C**。A 零新机制；B 多一类 ref 要管理。这是仓库治理规则，不是接口能单方面定的 |
| Q6 | 是否整体接受本文对规范字面的偏离（§9 各条以此为前提） | A：整体接受下列 8 项；B：逐项重议 | **A**。8 项：① 三个 `model_*` 写工具只改工作区、不提交（"进 Git"由代理随代码提交、pre-commit gate 把关），只有 `record_approval` 自己提交；② Approved 要求 evidence 处 gate PASS（`GATE_FAILED`），Rejected 不受限；③ 删除时 BPMN 成员属性（flowElements、flowNodeRefs、lanes、laneSets）摘除、`bpmn:default` 拒绝（§8.2 字面是一律拒绝，那样流程里的节点删不掉）；④ 批准记录、AI 活动、模型不能经 `model_remove` 删除，被批准过的元素只能退役（本文新规则，依据 ADR-009 + 原则五）；⑤ `record_approval` 不收调用方的 evidence、baseCommit、generatedAt（规范原文写"可选传入 baseCommit、headCommit"），headCommit 改为必填；⑥ 新增 IRI 规则：关系类无直连形式时取类本地名，AI 活动 `{model}activity-{yyyymmdd}-{head7}`，唯一键 (sessionRef, headCommit)；⑦ 写工具在写前候选图上跑 L0–L2，只拒绝新增违规（规范写的是"写入后跑"）；⑧ 新增 `model.gate` 工具 |

### 10.2 已按推荐定下的默认项（不合意直接推翻，不改接口其余部分）

| # | 事项 | 采用 | 理由 |
|---|---|---|---|
| D1 | 编码代理画像是否列出 `governance_record_approval` | 不列 | 批准是人的动作（原则五）。画像不是安全边界（§4） |
| D2 | "改动元素"一栏口径 | `changedElementCount`（只数 kind=element 的增删改） | 最贴近"改了哪些元素"；`touchedElementCount` 也返回，改口径不改接口 |
| D3 | 校验工具个数 | 保留 check/validate/findings + 新增 gate，单层结果标 `partial: true` | 只加不改 §8.3 契约。实测代理常选错再改成单一工具 |
| D4 | 辅助工具（列元素、查词汇） | 一期不加；改名工具 `model_set_labels` 已由用户在另一会话拍板加入（§5.10） | §8.3 没有；固定查询超过 5 条，或代理常因"不知道能连什么"反复被拒，再加 |
| D5 | 代理身份映射 | 每种 harness 在模型里有一个固定代理元素，找不到就拒绝并提示先建 | 元素数量稳定，历史能按代理聚合；不让写工具多一个"顺带建元素"的分支 |
| D6 | 工作台的仓库与主分支从哪来 | 服务器启动参数 `--repo`、`--main-branch`，工作台不传 | 不依赖 AO 的 `GET /api/v1/projects`，P10 上游接触面不扩大；v1 本来就只支持单仓库 |
| D7 | 主分支短名怎么解析 | 先远端跟踪引用 `refs/remotes/<upstream>/<b>`，再本地分支 | 本地 main 落后时 merge-base 会落到旧提交，diff 虚高（评审实测） |

---

## 11. 验收：每项主张怎么用可执行测试证明

**环境**：pytest，放在 `aisep-mcp/tests/`。每个测试在 `tmp_path` 里 `git init`，复制 `models/procurement`、`modules/`、`vendor/`；**不碰真实目录**。进程内直接调工具函数，另加一组跑真 stdio、真 HTTP 的冒烟测试。

| # | 主张 | 测试（断言） |
|---|---|---|
| T1 | 工具名兼容 | `tools/list` 每个名字匹配 `^[a-z_]{1,64}$`，`mcp__aisep__` + 名字也匹配 `^[a-zA-Z0-9_-]{1,64}$`；没有 `.` |
| T2 | annotations 与行为一致 | 表驱动比对 §4；readOnlyHint=true 的工具，调用前后工作区文件与 `.git/refs` 的 sha256 快照不变 |
| T3 | 判定与原型一致（P9） | 对原型全部 `modules/*/tests` 夹具和采购例子，`model_gate` 与 `aisep.py gate` 的 `(severity, layer, message)` 集合相等、各层违规数相等；`model_findings` 去掉 `openViolations` 字段后与 `aisep.py findings` 逐条相同；拆库后 `aisep.py test` 仍 179/179，CLI 输出与拆库前逐行相同（golden） |
| T4 | 无状态 | 同一组只读调用 → 杀进程 → 重启 → 再调，`structuredContent` 规范化后相同（去掉耗时字段、无序集合先排序；`model_query` 只比带 `ORDER BY` 的查询的行序）；运行后 `git status --porcelain` 为空、系统临时目录无残留；HTTP 响应不含 `Mcp-Session-Id` |
| T5 | stdout 只有 JSON-RPC | stdio 客户端调全部工具，出现任何非 JSON 行即失败；在 SDK 启动前后各触发一次遗留 `print`：完整的 `tools/call` 仍能收到响应，且 stderr 里有这两行 |
| T6 | 写入拒绝即不写 | 每个写工具的每个拒绝错误码各一例：调用后目标文件 sha256 不变 |
| T7 | 只拒绝新增违规 | 夹具先植入 1 个无关违规：合法写入成功且 `preexistingViolations=1`；非法写入 `WRITE_REJECTED`，`details.findings` 里 `preexisting:false` 的恰好是新违规、`true` 的恰好是植入的那 1 条；基线里对象 A 有一条通用措辞的违规，写入让对象 B 出现同样措辞的违规 → `WRITE_REJECTED`（实例键生效）；同一次写入消除对象 A 的旧违规、同时给对象 B 引入同文案的新违规（多重集计数不变）→ `WRITE_REJECTED`；普查原型全部 L0–L2 Violation 调用点，在夹具上触发后 `focus` 均非空（写工具上线门槛） |
| T8 | 文本编辑保真 | 写入后原文件每一行按顺序仍在（行级子序列断言）；图等价断言成立；人为篡改编辑器输出必须触发 `EDIT_UNSAFE`；两个主语写在一个块里时删除其一 → `EDIT_UNSAFE` |
| T9 | 幂等 | `add_element` 同参数两次，第二次 `changed:false`、文件不变；`add_relationship` 同类型同端点重放返回原 IRI，不生成 `-2` |
| T10 | 带 ref 的读取 | `model_gate(ref=<commit>)` 与在该 commit 的检出上跑 `aisep.py gate` 结果相同；记录快照耗时 |
| T11 | IRI 规则 | 两端相同时新建 `ddd:SubdomainImplementation` 和 `aisep:Implementation`：得到 `…-implements-…` 和 `…-implements-…-2`（F12） |
| T12 | add_relationship 拒绝 | BPMN 任务 ↔ am4 关系 → `WRITE_REJECTED`，文件不变；派生捷径 → 写入且 `findings` 带 Warning |
| T13 | 写并发 | 两个服务器进程同时写同一 worktree：一个成功、一个 `LOCKED`；写入中途外部改文件 → `CONFLICT`，文件保持外部内容；第二个文件 rename 失败时两个文件都恢复原字节；在两次 rename 之间注入 SIGKILL：工作区停在部分写入，随后 `model_gate` 判 FAIL（证明 gate 兜底）；工作台对 worktree A 批准时代理进程同时对 A 的 governance.ttl 写入 → 一方 `LOCKED`，批准提交只含批准块；在哈希核对之后、`rename` 之前注入一次不加锁的外部写入 → 外部内容被覆盖（证明附录 C 的已知限制如实）；`models/<slug>` 被换成指向外部目录的符号链接、`file` 指向其中 → `PATH_OUTSIDE_ROOT`，外部目录无新文件 |
| T14 | diff：merge-base 起点 | 分叉后主分支新增元素 X、分支新增 Y：`diff(head=branch)` 只有 Y，**没有** X 被删除；本地 `main` 落后于 `origin/main`、分支从 `origin/main` 切出：结果只含分支自己的改动，`base.mainRef` = `refs/remotes/origin/main` |
| T15 | diff：语义 | 夹具分支各一例：新增元素；只改 prefLabel → modified 且 `changedPredicates` 只有 prefLabel；按 §8.2 改关系类型 → 1 删 1 增；只改 `rdf:type` → `typeChanged`；元素块搬到别的文件 → 不在增删改里、出现在 `moves`；只改注释或前缀 → 全 0；只把元素加进视图 → `element.modified=0`、`view.modified=1`；模型内自定义视图子类的实例 → kind=view；成环、共享、无人引用的空白节点各一例 → `DIFF_BNODE_UNSUPPORTED`；树形空白节点内改一个值 → 引用方 modified |
| T16 | diff（Git 引用模式）：只看已提交、不碰工作区、可跨 worktree | `head` 为字符串时，工作区未提交改动不影响结果；从 `git worktree add` 的另一目录调用结果相同；前后 `git status --porcelain` 不变 |
| T17 | 级联删除 | `remove(quoteApproval)` → `REFERENCED`，blockers 含 `approval-20261119-arch-baseline`；`remove(quotation)` → `CASCADE_REQUIRED`，计划 3 条关系；`remove(bpmnReview, cascade)` 删 `sf1`、`sf2`、摘除 `flowElements`，之后 gate PASS；`remove(approval-…)` → `PROTECTED_RESOURCE`；双模型夹具：模型 B 里有一条以 T 为端点的**关系资源**（不只是普通谓词）→ `REFERENCED`，blocker `reason=cross-model-relationship`，B 的文件 sha256 不变；关系指向关系的夹具两条都进 `delete`；用构建图会被拒的 `quoteApproval` 端点关系（派生直连谓词）不出现在 blockers 里 |
| T18 | 删除确定性 | 同一 dryRun 跑 10 次结果相同；dryRun 后改文件，带旧 `planDigest` 实删 → `PLAN_STALE`；实删成功后用同一 `planDigest` 重放 → 成功、`alreadyAbsent:true`；不带 `planDigest` 删不存在的 IRI → `ELEMENT_NOT_FOUND` |
| T19 | diff 快速路径 | 只改代码的分支：全 0，且解析器调用计数为 0；两边都没有 `models/` → 两个 `*HasModels` 均为 false、全 0；head 删掉整个 `models/` → 全部 `removed`；带 ref 读取缺 `modules/` 的提交 → `MODULES_NOT_IN_REF` |
| T20 | diff 错误 | 不存在的分支 → `REF_NOT_FOUND`；ref = `--output=/tmp/x` → `INVALID_ARGUMENT` 且该文件未被创建；构造两个 merge-base → `AMBIGUOUS_MERGE_BASE` 带候选；`record_approval` 的 `branch` 传标签、`origin/x`、`x~1` → `INVALID_ARGUMENT` |
| T21 | 批准原子性与字段 | 一次调用恰好 1 个新提交，只改 `governance.ttl`（`git show --name-only`）；含记录和活动两个新主语；`evidence == activity.headCommit`；`baseCommit == git merge-base`；trailer 正确；构建后被批元素 approvalState = Approved，等于返回的 `derivedApprovalState.after` |
| T22 | 批准不污染元素差异 | 批准后同一分支 `diff(summary)` 的 `changedElementCount` 不变，`counts.governance.added` +2 |
| T23 | 分支头校验 | headCommit 之后又有代码提交 → `STALE_HEAD`，无新提交；之后有一个只改 governance.ttl、但新增 `arch:Stakeholder` 的提交 → `STALE_HEAD`；之后先加一个代码文件再删掉（净差异为空）→ `STALE_HEAD`；之后只有批准提交 → 第二个关口成功，活动复用（1 个活动、2 条记录）；`expectedBaseCommit` 与算出的 merge-base 不等 → `STALE_BASE`；headCommit..tip 含合并提交（侧分支带进代码提交）→ `STALE_HEAD`；同一分支先批准模型 A 再批准模型 B → 均成功；在第 1 步与第 7 步之间（钩子里或打桩）让代理提交一个代码提交 C → `STALE_HEAD`（`reason: concurrent-commit`），分支头 = C，C 不丢，governance.ttl 与 index 恢复，无批准提交残留；`branch` 为主分支 → `INVALID_ARGUMENT`（`reason: protected-branch`），无提交；W 的登记路径（改 `.git/worktrees/<n>/gitdir`）指向 `--allow-root` 外或另一个仓库 → `PATH_OUTSIDE_ROOT` / `WORKTREE_NOT_FOUND`，目标目录无提交 |
| T24 | gate 门槛（Q6） | evidence 上植入 L1 违规：Approved → `GATE_FAILED`、无提交；Rejected → 成功 |
| T25 | 去重与不接受字段 | 同输入调两次，第二次 `duplicate:true`、提交数不变；**首次调用提交成功后丢弃响应再重放**（有 activity、无 activity 各一例）→ `duplicate:true`、提交数不变；传 `evidence` 或 `baseCommit` → `isError:true`、`INVALID_ARGUMENT`、`details.rejectedFields` 点名、提交数不变 |
| T26 | 失败回滚 | 装一个总失败的 pre-commit 钩子：`COMMIT_FAILED`，`git status --porcelain` 为空，HEAD 不变；钩子失败前改写 governance.ttl → 文件保留钩子写的内容、`CONFLICT`；`models/` 有未提交改动 → `DIRTY_WORKTREE`；残留一条未提交批准块 → `DIRTY_WORKTREE` 且 `orphanApproval:true` |
| T27 | impact | 采购例子 depends 14、ripple 16，条目集合与 CLI 相同；每个 `path` 末跳的 `to` 等于该条 IRI；植入 L1 违规 → `MODEL_INVALID`；`allowInvalid` → `invalidModel` 非空；未知元素 → `ELEMENT_NOT_FOUND` 带候选 |
| T28 | PROV 最小桩（Q4-C） | 加桩后，`prov:wasAssociatedWith` 指向 `aisep:AIAgent` 实例的夹具 gate PASS；`prov:used` 仍报 `undeclared predicate`；`approvedBy` 指向 AIAgent → L1 与 L3（EG13）都失败、一致；`a prov:SoftwareAgent` 的实例仍报未声明的具体类；原型测试全过 |
| T29 | 查询只读 | `INSERT DATA` → `QUERY_NOT_READONLY`，store 三元组数不变；含 `SERVICE` → `QUERY_NOT_READONLY`，且断网下无网络调用；超 limit → `truncated:true`；有一个文件解析失败 → `PARSE_FAILED`，`allowPartial:true` → `partial:true` 且 `skippedFiles` 含该文件 |
| T30 | HTTP 安全与协议 | 错误 `Origin` → 403；`Host` 非 loopback → 拒绝；从 `Origin: app://renderer` 发 `OPTIONS` 预检成功且 `Access-Control-Allow-Headers` 含 `Mcp-Method`、`Mcp-Name`；从其他源（含 `null`）预检 → 403；按 2026-07-28 形状、不发 `initialize` 直接 `tools/call` 成功；缺 `Mcp-Name` → 400 / `-32020`；头里的版本与 `_meta` 不一致 → 拒绝；用 `mcp==2.3.*` 实测确认服务器确实协商 2026-07-28（本文据评审转述，尚未在本机跑过） |
| T31 | 工作台替换 | `npm run typecheck` 通过；vitest 基线 292 项 + 新用例全绿；`McpModelClient` 把 `isError` 转成 `AisepToolError(code)`；`elementsFromRows` 遇未知或缺失的 approvalState 抛错；采购例子的待批准列表不含 `approval-20261119-arch-baseline`；"改动元素"各状态都渲染（含"含未提交"、incomplete、`WORKTREE_NOT_FOUND` 退回引用模式）；"架构全景"违规徽标在植入 1 个遗留违规时显示 1；`FixtureClient` 与 `McpModelClient` 对同一夹具仓库的结果结构等价（契约测试） |
| T32 | 真客户端端到端 | 复用**一个** `claude -p` 进程挂 `--mcp-config`，让它"给采购模型加一个'报价行'业务对象，并用 Access 连到提交报价单"：工具调用序列无协议错误，最终 gate PASS。只跑一次，控制成本 |
| T33 | 异构评审 | 已做一轮（GPT 族，见文末记录），反例已并入 T5、T7、T15、T19、T23、T25、T26、T29。修订后的新增内容（§5.9 逐提交校验、目标 worktree 锁、§5.8 树形空白节点）和拍板后新增的内容（§5.8 worktree 模式、§5.4 `openViolations`、§5.1 `preexisting`、Q5 禁用 rebase 合并）定稿前再过一次。**第二轮已做**（2026-11-20，GPT `gpt-5.6-sol-high` + Claude Git 语义与安全 lens，22 条，见文末"第二轮"），反例已并入 T7、T13、T23、T35、T36、T37。第二轮引入的修订（锁内复验与提交后撤回、统一文件集合、逐级 `O_NOFOLLOW`、前后核对）只经同模型落文，尚无可执行探针，实现时按上列用例验证。R2-13、R2-15 拍板后新增的内容（§5.9"合并时校验""批准专用 PR""发布关口"、T38–T40）**未经异构评审** |
| T34 | 错误结果符合 outputSchema | 用 TS SDK `Client.callTool` 对每个错误码各触发一例：不抛 `InvalidParams`，`structuredContent.error.code` 原样到达；未捕获异常 → `INTERNAL`，不是 `-32603` |
| T35 | diff worktree 模式：内容口径（Q6 条件一） | 临时仓库 `main` 提交采购例子，`git worktree add -b feat-x`；分支先提交一个新元素，主分支分叉后再新增一个元素；工作区里：(a) 改 `am4.ttl` 中 `supplier` 的 prefLabel → `modified`，`changedPredicates` 只有 prefLabel；(b) 未跟踪的新 `extra.ttl` → 其元素 `added`；(c) 删除已跟踪的 `uml.ttl`（未暂存）→ `QuotationEntity` 与其 refines 关系 `removed`；(d) 语法坏的新 `broken.ttl` → `incomplete:true`、`failedFiles` 点名它，(a)–(c) 照常成立；分支已提交的元素也在（已提交 + 未提交）；主分支后来新增的元素不显示为 removed（merge-base）；`.gitignore` 忽略的 `.ttl` 不参与；指向 `/etc/hosts` 的符号链接 `.ttl` 记入 `failedFiles`（`error: symlink`）、不读目标；把 `models/procurement` 目录换成指向工作区外的符号链接 → 其中文件都记入 `failedFiles`、外部主语不出现在结果里（评审探针实测普通 `open()` 会读到外部的 `SECRET_FROM_OUTSIDE`）；FIFO `.ttl` → `error: not-regular`、不阻塞；`git mv code.ttl code2.ttl` 后截断 code2.ttl → 原 4 个主语进 `indeterminate`、无 removed；对已改的 `am4.ttl` 设 assume-unchanged → 不走快速路径、改动照常报出；skip-worktree 且磁盘缺失的 `uml.ttl` → 不报 removed；被忽略的 `.ttl` 和嵌套仓库里的 `.ttl` 在 `model_check`、写工具基线、diff 里都不出现（统一文件集合）；读取期间持续改写某文件 → 重读后一致则正常返回，始终不一致 → `WORKTREE_CHANGED`；`head.kind=worktree`、`headCommit` = 工作区 HEAD、`dirty:true`；调用前后 `git status --porcelain` 相同；同一分支用 Git 引用模式只含已提交的那一个元素；另一工作区把已跟踪的 `code.ttl` 截掉一半 → `incomplete:true`，它的 4 个主语进 `indeterminate`、**一个都不报 removed**，`items` 为空；干净工作区 → `dirty:false`、结果与 Git 引用模式相同；工作区无改动时走快速路径（解析器调用计数为 0）；暂存但未提交的新文件也算 added。**探针已跑**（F19）：`/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/wtdiff.3CCZ/probe/probe_test.py`（实现 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/wtdiff.3CCZ/probe/wtdiff.py`；`$PY -I probe_test.py <空目录>`；临时目录，可能已清理），15 条内容断言（A1–A15）全部 CONFIRMED，覆盖上列除"快速路径计数""暂存新文件"两条外的各项；把 indeterminate 处理变异掉，截断用例 REFUTED（4 个主语被报成 removed）；把符号链接检查变异掉，符号链接用例 REFUTED |
| T36 | diff worktree 模式：定位与拒绝 | `head.worktree` 传 `/etc`、工作区的真实绝对路径、`../x`、`--output=/tmp/x`、`refs/heads/feat-x`、`@{-1}` → 均 `INVALID_ARGUMENT`；`head` 对象多带 `path` 键 → `INVALID_ARGUMENT` 且 `rejectedFields` 点名；不存在的分支 → `WORKTREE_NOT_FOUND`（`branchExists:false`）；分支存在但没检出 → `WORKTREE_NOT_FOUND`（`branchExists:true`）；工作区目录被删（prunable）→ `WORKTREE_NOT_FOUND`；以上调用均不打开 `models/` 以外的任何文件（打桩 `open` 计数）；分支检出在 `--allow-root` 之外的 linked worktree → `PATH_OUTSIDE_ROOT`；改 `.git/worktrees/<n>/gitdir` 指向另一个仓库 → `WORKTREE_NOT_FOUND`。**探针已跑**：10 条错误码断言 CONFIRMED（`rejectedFields`、`branchExists` 的值与打开文件计数未断言） |
| T37 | 遗留违规可查可见（Q6 条件二） | 夹具用 `--no-verify` 提交一个 L1 违规：`model_findings` 的 `openViolations.count=1`、`items[0]` 是该违规的结构化 Finding（`focus` 非空）、`byLayer.L1=1`；同一内容上 `model_gate` 的 `violationsByLayer` 与不加 openViolations 前相同（不重复计数），`model_findings.summary` 不含它；两个不同 `focus` 的同文案违规 → `items` 两项、`count=2`；随后合法写入成功，`findings` 里该违规 `preexisting:true`；一次会新增违规的写入被拒，`details.findings` 里新违规 `preexisting:false`、旧违规 `true`；只读工具的 Finding 不带 `preexisting` 键；pre-commit 钩子在该违规存在时拦下任何提交（证明已提交内容里的遗留违规只能经 `--no-verify` 或规则升级进入） |
| T38 | 合并时校验（R2-13） | CI 检查对临时仓库：批准后分支上再提交一个代码提交 → 拒绝，`offendingCommit` 是该提交；evidence..分支头只有批准提交（含连过两个关口）→ 通过；批准后把主分支合进本分支（范围含合并提交）→ 拒绝；同一对象先批准、改代码、重新批准 → 通过（旧记录被取代，不查）；新记录只覆盖部分对象、旧记录仍被另一对象采用 → 拒绝；CI 与 `record_approval` 第 1 步调用同一判据函数（打桩计数）；主分支在批准后删掉分支新关系引用的元素（两边各自 gate PASS）→ 合并结果上 `model_gate` FAIL、拒绝合并；检查前后两条分支头不变 |
| T39 | 批准专用 PR（R2-15） | 从被发布提交 R 拉的批准分支只含一个 `GateRelease` 批准提交 → 判为批准专用 PR，只跑合并时校验与合并结果 gate，不要求新的关口批准，通过；同一分支再夹带一个代码提交、或一个往 governance.ttl 加 `arch:Stakeholder` 的提交 → 判为普通 PR（要求过关口）；从主线最新提交 M（R 之后又有代码提交）拉分支、headCommit = R → `record_approval` 报 `STALE_HEAD`、无提交；绕过 MCP 手工造出同样的分支和批准提交 → CI 拒绝（R..分支头含非批准提交） |
| T40 | 发布批准的约束（R2-15） | `gate: GateRelease` 带 `activity` → `INVALID_ARGUMENT`、`rejectedFields` 含 `activity`、无提交；其他关口、headCommit 已在 mainRef 上时带 `activity` → 同样拒绝；`GateRelease` 的 headCommit 只在功能分支上 → `INVALID_ARGUMENT`（`reason: release-head-not-on-main`）；成功时记录 evidence = R、无活动；远端有 `release/{yyyymmdd}-{R 前 7 位}` 标签指向 R → 标签检查通过，缺标签或标签指向别的提交 → CI 失败；合并后删批准分支、`git gc --prune=now` 后 R 仍可读、`model_diff` 历史差异可复现 |
| T41 | `model_set_labels`（§5.10） | 改 `supplier` 的 `prefLabel` → 成功，IRI 不变，`git diff` 只动含该三元组的那一块，`model_diff` 报 `modified`、`changedPredicates` 只有 prefLabel；同参数重放 → `changed:false`、文件不变；`prefLabel` 传空串、三个字段都不给、多带 `type` 键 → `INVALID_ARGUMENT`（`rejectedFields` 点名）；`definition: null` → 删除定义；目标是 `approval-20261119-arch-baseline` → `PROTECTED_RESOURCE`；不存在的 IRI → `ELEMENT_NOT_FOUND`；以上拒绝均不改任何文件（并入 T6）；`@en` 以外语言的标签原样保留 |
| T42 | 缺省写入文件（§5.1） | 对 `models/procurement/` 现有 27 个关系，按 §5.1 规则推算的文件都等于它们实际所在的文件（合并时已用脚本核对一次：27/27；本稿原"源端所在文件"规则只有 24/27）；新建 `ext-code` 类型的元素写进 `code.ttl`、`ext-governance` 类型的写进 `governance.ttl`（`aisep#` 共用命名空间，按 `aisep:loads` 判定） |

**最大的风险**：T15、T17、T21–T23、T35–T37 的期望值是本文自己定的，自写代码加自写测试是循环自证。第一轮异构评审挑出 4 处缺口（文件名判据、重放幂等、跨模型闭包、空白节点）；第二轮又挑出批准竞态、worktree 越出根目录、上级目录符号链接、改名后误报删除等，均已改文并补用例，但第二轮修订本身尚未有探针或第三轮评审验证。

---

## 附录 A：三份草案的冲突与裁决

| 冲突点 | 草案 1（代理） | 草案 2（工作台） | 草案 3（语义） | 本文 | 理由 |
|---|---|---|---|---|---|
| 工作台传输 | stdio + IPC | stdio + IPC | HTTP | HTTP（Q1） | P10 上游接触面固定 |
| 辅助工具 | 加 4 个 | 不加 | 不加 | 只加 `model_gate`（D4）；合并时另并入改名工具 `model_set_labels`（另一会话拍板） | 任务要求只做 §8.3；gate 是 G10 必需 |
| 校验工具 | 合并成 1 个 | 4 个 | 4 个 | 4 个 + `partial`（D3） | 不改 §8.3 契约 |
| 仓库定位 | `--repo` + allow-root | MCP roots | `repo` + allow-root | `repo` + `--allow-root` | roots 支持未核实；启动参数可测 |
| 读已提交内容 | 只有 diff | 所有只读工具带 `ref` | 只有 diff | 所有只读工具带 `ref` | 关口页的 gate、impact 必须在 headCommit 上算 |
| 模块版本 | — | 同 commit | 工作区模块 + Warning | 同 commit 快照 | 结果可复现，不用 Warning |
| diff 种类判定 | 看类型 | 只看三元组 | 沿本体 subClassOf | 只看三元组 | 不加载本体，快，无版本问题 |
| 主分支 | 启动参数 | 每次传 | `aisep.toml` | 每次可传 + 启动参数缺省，短名优先解析成远端跟踪引用 | 不引入配置文件；本地 main 落后时不虚高 |
| 缓存 | 本体缓存 | 按 commit 缓存 | 不缓存 | 不缓存 | 性能够用，最简单 |
| 新违规身份键 | — | (sev, layer, focus, msg) | (layer, rule, focus, msg) | 实例键 (sev, layer, rule, focus, msg) 的多重集；展示仍用 (sev, layer, msg) | 评审后改：展示键会把"同措辞、不同对象"的新违规当旧问题放过 |
| headCommit 校验 | 祖先即可 | 必须等于分支头 | 祖先即可 | 之间逐提交只有批准提交，按源图语义判（Q3） | 既防批旧版本，又能连过多个关口 |
| 批准提交方式 | worktree 内提交 | worktree 内或底层提交 | 当前检出内提交 | 检出的 worktree 内提交，否则报错 | 少一条无钩子的底层路径 |
| 删除 BPMN 成员 | 删谓词行 | 拒绝 | 摘除 | 摘除，default 拒绝（Q6） | 否则删不掉流程里的节点 |
| 删除错误码 | 一个 | 一个 | 两个 | 两个 | 代理能按码决定下一步 |
| 活动 IRI | `{slug}` | `{session}-{head7}` | `{slug}` | `{head7}` | 与唯一键 (session, head) 对齐且无需清洗 sessionRef |
| 改动元素口径 | 含端点 | 只数元素 | 只数元素 | 两个都返回，显示只数元素（D2） | 改口径不改接口 |
| PROV-O | 声明三个 prov 类 | 声明两个 prov 类 | `aisep:AIAgent` 桩 | `aisep:AIAgent` 桩（Q4） | AISEP 自有类为主，只新增一条与 PROV-O 原文同义的对齐公理（放 aisep-core 对齐文件，ADR-010） |

## 附录 B：外部事实出处

**评审后重新抓取并核实（2026-11-20）**：

- MCP 2026-07-28 changelog（modelcontextprotocol.io/specification/2026-07-28/changelog）：去掉 `initialize`/`notifications/initialized` 握手和协议层会话（`Mcp-Session-Id`）；每个请求在 `_meta` 带协议版本与客户端能力；Streamable HTTP POST 必须带 `Mcp-Method`、`Mcp-Name`；`HeaderMismatch` 为 `-32020`；Roots 被标为 Deprecated，建议改用工具参数或服务器配置。
- MCP 2026-07-28 Tools 一节：入参校验错误属于工具执行错误（`isError: true`），协议错误只含未知工具、不符合 `CallToolRequest` 结构的请求和服务器错误；有 `outputSchema` 时服务器必须返回符合它的结构化结果；返回结构化内容的工具 SHOULD 同时给出序列化 JSON 的 TextContent；`tools/list` 不得随连接变化。
- PyPI `mcp` 当前版本 2.3.0（pypi.org/pypi/mcp/json）。

**来自评审转述、本次未重新抓取**：Python SDK v1 `call_tool(validate_input=False)`、未知键静默丢弃；v2 未捕获异常变成脱敏 `-32603`；v1 `stdio_server` 在进入时取 `sys.stdout.buffer`；TS SDK v1 客户端在 `isError` 时仍校验 `structuredContent`；Claude Code 的 50,000 字符落盘与错误文本截断阈值。这些只影响"怎么做更稳"，对应措施（入口校验、入口装饰器、fd 复制、联合 schema）不依赖它们是否精确成立；T5、T30、T34 会实测。

**来自草案，未重新抓取**：

- MCP 工具名格式：SEP-986（modelcontextprotocol.io/seps/986-specify-format-for-tool-names）；MCP 2025-11-25 changelog。
- Cursor 过滤带点号的工具名：forum.cursor.com 相关帖。
- Anthropic API 工具名不允许点号：platform.claude.com「Define tools」。
- MCP 规范：工具执行错误放进结果并设 `isError: true`；annotations 是不可信提示；Streamable HTTP 要校验 Origin、只绑 localhost。

T1 用保守正则（≤64、只含 `[a-zA-Z0-9_-]`）断言，不依赖具体上限。

## 附录 D：工具 ↔ 规范 ↔ 原型追溯表

> 来自另一会话草案，合并时并入。行号指本仓库 `tools/aisep.py` 与 `modules/aisep-core/shapes.ttl` 当前版本，2026-11-20 合并时逐条核对，全部对得上（`tools/aisep.py` 与原型目录里的同名文件逐字节相同）。拆库（§3.1）后行号会失效，届时以函数名为准。**EXISTS** = 原型已有、可直接复用；**GAP** = 要新写。附录 C 指规范附录 C。

| §8.3 逻辑名 | 线上名 | 本文 | `tools/aisep.py` / 规则映射 | 状态 |
|---|---|---|---|---|
| `model.add_element` | `model_add_element` | §5.2 | 校验：`run_check` L948–950；TypeShape / InModelShape / LabelShape（aisep-core `shapes.ttl` L29 / L53 / L73）；R2 `l1_one_notation` L643–655；G7 `l1_closed_predicates` L620–641；抽象类 `ABSTRACT_ROOTS` L64。写入：无 | GAP（校验复用 EXISTS） |
| `model.add_relationship` | `model_add_relationship` | §5.3 | 判定：`l1_notation_mixing` L657–691（§7.3、G5）、`l1_refines` L693–723（§7.2）、`l2` L726–759 + `rt_table` L765–778；IRI：`Ctx.uf` L230、`nearest` L255–259；每个关系类都声明 `arch:unqualifiedForm`（RelationshipShape，`shapes.ttl` L102 起）。写入：无 | GAP（规则 EXISTS） |
| `model.remove` | `model_remove` | §5.5 | 找引用：`Ctx.relationships` L316–319、`src_quads`（L205）；兜底：EndpointShape（`shapes.ttl` L126 起）；`ELEMENT_LINK_OK` L83–88。级联逻辑：无（§8.2"未原型化"） | GAP |
| （扩展）`model.set_labels` | `model_set_labels` | §5.10 | 校验：`run_check` L948–950、LabelShape（`shapes.ttl` L73）。按主语块改写标签：无 | GAP（校验 EXISTS，扩展 §8.3） |
| `model.check` | `model_check` | §5.4 | `cmd_check` L953–962 → `Ctx.__init__` L202–237（L0 在 L207–218）+ `run_check` L948–950（`l1` L491–539、`l2` L726–759） | EXISTS |
| `model.validate` | `model_validate` | §5.4 | `cmd_validate` L965–972、`l3` L819–848 | EXISTS |
| （扩展）`model.gate` | `model_gate` | §5.4 | `cmd_gate` L975–989（G10） | EXISTS（扩展 §8.3） |
| `model.findings` | `model_findings` | §5.4 | `cmd_findings` L1006–1011、`l4` L853–890（含 R4）；`openViolations` 复用 `run_check` | EXISTS；`openViolations` 为新增 |
| `model.query` | `model_query` | §5.6 | `cmd_query` L1014–1033、`onto_files` L179–186（载入 L220–221） | EXISTS（查询核心）；`limit`/`truncated`、拒绝 `SERVICE` 为新增 |
| `model.impact` | `model_impact` | §5.7 | `cmd_impact` L1047–1076（G9 L1060–1071）、`impact` L895–931（依赖方向 `aisep:dependency` L899）、`expand` L1036–1044 | EXISTS；结构化路径、未知元素报错为新增 |
| `governance.record_approval` | `governance_record_approval` | §5.9 | `approval_problems` L396–433（G1；EG11/13/15/16/25/26；ApprovalRecordShape `shapes.ttl` L150 起）、`activity_problems` L435–468（EG17–24；AgentActivityShape `shapes.ttl` L237 起）、R3c `l1` L510–514、`derive_approval_state` L337–380；`AGENTS` L56 要按 Q4=C 拆成两个集合（§6.2）。写入、Git 取值与核对、提交：无 | GAP（校验与推导 EXISTS） |
| `model.diff` | `model_diff` | §5.8 | 只可复用 `ox.parse` 用法（L207–218）、`short` L104–112、`model_graph_of` L470–475 | GAP |

**全部工具共有的新建工作**：MCP 外壳（stdio + 本机 HTTP，§3.2）；把命令函数改为返回结构化结果（`report` L940–945 及各 `cmd_*`，§3.1）；§5.1 的写入流程、文件选择（含 `aisep#` 按 `aisep:loads` 判定的小函数）与新违规判定；§3.3 的仓库定位与统一文件集合（替换 `model_files` L936–937 的 glob）；§7 的错误模型。

---

## 附：评审与辩论记录（2026-11-20）

4 路评审：3 路 Claude lens（规范一致性、MCP 协议、Git 语义）+ 1 路异构（GPT 族 `gpt-5.6-sol-high`，经 cursor-agent `--mode ask` 只读）。共 53 条：**接受 42、部分接受 11、反驳 0**。事实断言的核实：ELEMENTS_QUERY 漏出批准记录用原型 `query` 重跑确认；MCP 2026-07-28 的握手、会话、请求头和入参错误归类重新抓取官方规范确认；PyPI `mcp` 版本重新查询确认；SDK 源码细节未重新抓取（附录 B）。

**各路评审的 steelman（摘要）**：无状态落实彻底；`model_diff` 只读 Git 对象、merge-base 歧义时报错而不静默挑选、比源图不比构建图；approvalState 只能由记录推导，evidence 等由服务器算；G9/G10 落实正确；唯一规范外工具 `model_gate` 有理由；工具名、annotations、stdio/HTTP 的分工符合 MCP 规范；写前校验、未知引用一律拒绝的方向是 fail-closed。主干设计无需推翻，问题集中在批准校验判据、跨 worktree 与崩溃、协议版本与 SDK 行为、diff 边缘情形。

| # | 意见 | 来源 lens | 处置 | 理由 |
|---|---|---|---|---|
| 1 | STALE_HEAD 按文件名判断，governance.ttl 也放 Stakeholder 等元素，可被绕过 | 规范一致性、Git 语义 | 接受 | 例子文件里确有 `:chiefArchitect a arch:Stakeholder`。改为逐提交、按源图语义判（§5.9 第 1 步），T23 补反例 |
| 2 | `derivedApprovalState` 刷新"待批准关口"与它读主分支矛盾 | 规范一致性 | 接受 | 改为只描述分支状态；关口另显示"已在分支批准、待合并"，从分支上的记录查出（§2、Q2） |
| 3 | ELEMENTS_QUERY + "缺失 → Proposed" 会把批准记录显示成 Proposed | 规范一致性 | 接受 | 原型 `query` 重跑确认：采购例子里 `approval-20261119-arch-baseline` 有 inModel、zh 名称而无 approvalState。只选有 approvalState 的主语，缺失即抛错（§8、T31） |
| 4 | 级联闭包把别的模型里的关系吸进删除集，绕过"跨模型拒绝" | 规范一致性 | 接受 | 闭包只收同模型关系，别的模型的作 blocker；第 3 步只删本模型文件里的主语三元组（§5.5） |
| 5 | §9 有 5 处规范改文在 §10 没有对应问题，等于执行会话自己改规范 | 规范一致性 | 部分接受 | 接受"必须交设计会话"；不接受补 Q13–Q16（会超出 6 题上限、把同类问题拆碎）。8 处偏离规范字面的改文合并成 Q6 一次拍板，§9 每条标出前提 |
| 6 | 依赖 `GET /api/v1/projects` 扩大了已决的上游接触面 | 规范一致性 | 接受 | 改为不依赖：仓库路径、主分支由服务器启动参数给出（§3.3、§8、D6），v1 本来只做单仓库，无需拍板 |
| 7 | 附录 A"不对上游术语作新断言"与选项 C 的对齐公理自相矛盾 | 规范一致性 | 接受 | 改为"只新增一条同义对齐公理"，按 ADR-010 放 aisep-core 对齐文件；T28 断言 `prov:SoftwareAgent` 不可直接实例化 |
| 8 | PROTECTED_RESOURCE、"只能追加"不是 ADR-009 的推论 | 规范一致性 | 接受 | ADR-009 只定批准记录放在模型仓库。改称本文新规则（依据 ADR-009 + 原则五），列入 Q6 ④ |
| 9 | 入参校验失败不是协议错误；SDK 也不会因多传字段报 `-32602` | MCP 协议 | 接受 | 重抓规范确认：入参校验错误属工具执行错误。`additionalProperties:false` + 入口显式校验 → `INVALID_ARGUMENT`（§3.1、§7.1、T25） |
| 10 | 错误结果的 `structuredContent` 不符合只描述成功形状的 `outputSchema` | MCP 协议 | 接受 | 规范：有 outputSchema 时 MUST 符合。改为成功、错误两形状的联合（§5.0），新增 T34 |
| 11 | HTTP 设计没处理 CORS 预检，renderer 的 fetch 会被拦 | MCP 协议 | 接受 | 本仓 AO 的 `cors.go` 已有先例（`app://renderer`、拒 `*`/`null`）。§3.2 补 CORS 白名单与预检，T30 补用例 |
| 12 | 没锁协议版本和 SDK 版本，传输措辞停在 2025-11-25 | MCP 协议 | 接受 | 重抓 changelog 与 PyPI 确认：2026-07-28 去掉握手和会话、要求 `Mcp-Method`/`Mcp-Name`；`mcp` 当前 2.3.0。锁 `mcp==2.3.*`，目标 2026-07-28，手写客户端按此形状（§3.1、§3.2、§8） |
| 13 | 两代 SDK 都不会把异常变成设计的结构化错误 | MCP 协议 | 接受 | 加入口装饰器手工构造 `CallToolResult`（§3.1），T34 实测 |
| 14 | 启动时把 `sys.stdout` 重定向到 stderr 会把协议帧一起送走 | MCP 协议 | 接受 | 改为 `os.dup` 保留原 fd 显式交给 `stdio_server`，再 `dup2(2,1)`（§3.1），T5 补用例 |
| 15 | `model_remove` 重放报 `ELEMENT_NOT_FOUND`，与 add 的 `changed:false` 不一致 | MCP 协议 | 接受 | 带 `planDigest` 重放且目标已不在 → 成功 `alreadyAbsent:true`；不带才报 NOT_FOUND（区分"已删"与"写错"）（§4、§5.5、T18） |
| 16 | Host 校验不是规范要求；不带 Origin 的本机进程能调写工具 | MCP 协议 | 接受 | 改措辞；开发期无令牌写成接受的风险，打包前必须定令牌（§3.2、Q1） |
| 17 | `content[0].text` 只放摘要，偏离"同时给序列化 JSON"的 SHOULD；没对照 Claude Code 的输出阈值 | MCP 协议 | 部分接受 | 接受标明偏离和定输出上限（§3.5、§5.0）；不接受再加一块 JSON：代理读摘要更省 token，客户端都读 `structuredContent` |
| 18 | 替换路径第 2 步把 initialize 核实指向 T29，应为 T30 | MCP 协议 | 接受 | 改指 T30，且按 2026-07-28 已无 initialize，T30 改为验证新形状 |
| 19 | 同 #1 | Git 语义 | 接受 | 评审临时仓库实测可绕过。同 #1 |
| 20 | mainRef 用本地短名，本地 main 落后时 merge-base 落到旧提交，diff 虚高且写进活动 | Git 语义 | 接受 | 评审临时仓库实测复现；AO 自己用 `origin/main`。短名优先解析成远端跟踪引用，输出实际 ref（§3.3、D7、T14） |
| 21 | 批准锁的是调用方仓库的 git-dir，与目标 worktree 里代理的写入不互斥；`git restore` 会抹掉别人刚写的内容 | Git 语义 | 接受 | 锁目标 worktree；提交前 CAS；回滚改为"仍等于写后哈希才恢复原字节"（§3.4、§5.9 第 7–8 步、T13） |
| 22 | 无 activity 时 evidence 取分支头，重放写出第二条记录；人看的版本与写入版本无绑定 | Git 语义 | 接受 | `headCommit` 改为顶层必填，evidence 固定取它；去重键稳定（§5.9、T25） |
| 23 | 同 #4；另：仓库外引用看不到 | Git 语义 | 接受 | 同 #4；"仓库外引用不检查"写进 §5.5 和附录 C 改文 |
| 24 | 进程被杀时多文件写入和批准提交都不原子；建议临时 index + `commit-tree` | Git 语义 | 部分接受 | 接受如实写明崩溃窗口、`orphanApproval` 提示、SIGKILL 注入测试（§3.4、§5.9 第 9 步、T13、T26）。不采纳 `commit-tree`：它不跑仓库钩子，违背"不跳过 pre-commit"，要另调 gate 也覆盖不了仓库其他钩子 |
| 25 | `arch:inView` 主语是元素，加进视图会把元素算成修改，视图本身不显示变化 | Git 语义 | 接受 | 成员谓词归宾语（视图）（§5.8 第 6 步、T15） |
| 26 | 级联第 4 步没写外部引用在哪个图上算，用构建图会全被派生谓词拒绝 | Git 语义 | 接受 | 评审实测：构建图 6 条、源图 1 条。明写只用源图（§5.5） |
| 27 | `planDigest` 不一致标 CONFLICT 可重试，但原样重试永远失败 | Git 语义 | 接受 | 新错误码 `PLAN_STALE`，不可重试（§5.5、§7） |
| 28 | 图等价断言在落盘之后，不安全的编辑会短暂出现在磁盘上 | Git 语义 | 接受 | 断言移到写盘前，在内存里做（§5.1 第 6 步） |
| 29 | `git archive`、`rev-parse <c>:models` 在路径缺失时 rc=128 | Git 语义 | 接受 | 先 `ls-tree` 查存在性；缺模块报 `MODULES_NOT_IN_REF`；hasModels 判断提到快速路径之前（§3.3、§5.8） |
| 30 | 空白节点：顶层、共享的情形没定义 | Git 语义 | 部分接受 | 接受"必须有定义"；不采纳另起两个错误码，统一为只支持树形、其余 `DIFF_BNODE_UNSUPPORTED`（与 #40 合并） |
| 31 | 全局重定向 stdout 会让 stdio 失效 | GPT 异构 | 接受 | 同 #14。GPT 建议"删光 print 不做兜底"，本文仍保留 fd 级兜底，二者兼容 |
| 32 | 文件名判据证明不了"之后只有批准提交"；先加后删净差异为空也能过 | GPT 异构 | 接受 | 采纳 GPT 的逐提交检查（比 #1 的净差异方案更严），并加源图语义条件（§5.9、T23） |
| 33 | 无状态 HTTP 没取消生命周期，客户端仍须 initialize | GPT 异构 | 部分接受 | 事实断言**不成立**：重抓 2026-07-28 changelog，握手已删除（2025-11-25 下才成立）。接受其要点"定稿前写清握手、版本、请求头"：§3.1 锁版本，§8 写明请求形状，T30 做互操作测试 |
| 34 | 不带 activity 时 record_approval 不幂等 | GPT 异构 | 接受 | 同 #22 |
| 35 | 锁取自调用方 worktree，两进程拿两把锁 | GPT 异构 | 部分接受 | 接受锁目标 worktree（同 #21）。不加 `--git-common-dir` 仓库级锁：跨 worktree 的共享 Git 操作只有 ref 更新，Git 自己的 ref 锁已覆盖，多一把锁只会让不相干的 worktree 互相阻塞 |
| 36 | 多文件 rename 不是原子事务，也没对目录 fsync | GPT 异构 | 部分接受 | 接受不再称"原子"、写明崩溃后果（§3.4 第 4 步）。不采纳持久化事务日志和启动恢复：违背 P1 无状态，gate 兜底已能拦住部分写入（T13 证明）；不采纳"每次只改一个文件"：`remove(quotation)` 本来就要改 am4.ttl 和 ddd.ttl |
| 37 | 回滚无条件 restore 会抹掉外部改动 | GPT 异构 | 接受 | 同 #21 |
| 38 | 新违规身份键 (sev, layer, message) 会放过同措辞、不同对象的新违规 | GPT 异构 | 部分接受 | 接受改用实例键并加 `rule`、`focus`，按多重集计（§5.1、§7.3、T7）。不加 `file`：搬文件会让旧违规变"新"，误拒合法写入 |
| 39 | head 删掉整个 `models/` 会被报成"仓库无模型" | GPT 异构 | 接受 | 拆成 `baseHasModels`、`headHasModels`，单侧缺失按全增/全删算（§5.8、T19） |
| 40 | 签名相同不进 items，却要每条带 `moved` | GPT 异构 | 接受 | 改为独立的 `moves` 数组，删去 `moved` 字段（§5.8、§8、T15） |
| 41 | 空白节点规范化不稳定，建议首版拒绝或用标准算法 | GPT 异构 | 部分接受 | 不整体拒绝：树形空白节点（嵌套的结构化值）定义清楚，L1 也不禁止手写。其余情形拒绝；真要通用支持再用标准 RDF 数据集规范化，不自写 |
| 42 | 只对 governance 追踪特化链，自定义视图子类会被误判为 element | GPT 异构 | 接受 | view、governance 统一解析特化链（§5.8 第 9 步、T15） |
| 43 | 批准时重算的 baseCommit 可能不是人评审时的起点，应接收 reviewedBaseCommit | GPT 异构 | 部分接受 | 主张大半不成立：merge-base 是分叉点，主分支单纯前进时不变，只有主分支合入了本分支的部分提交才会变。接受"要能发现不一致"：加可选 `expectedBaseCommit` 只做核对（不等 → `STALE_BASE`），写入值仍由服务器算，守住"baseCommit 只由服务器填" |
| 44 | commit 不可变不等于可达；被删或 squash 后历史批准无法重跑 | GPT 异构 | 接受 | 去掉"可复现"的无条件说法，保留策略列为 Q5（仓库治理规则，须人定） |
| 45 | 同 #10 | GPT 异构 | 接受 | 同 #10 |
| 46 | 服务器支持 ASK/CONSTRUCT，TS `QueryResult` 只有 select | GPT 异构 | 接受 | 改为三种 kind 的判别联合；工作台只发 SELECT，收到别的 kind 抛错（§8） |
| 47 | 查询在 L0 失败时跑在不完整的图上却无提示 | GPT 异构 | 接受 | 默认 `PARSE_FAILED`；`allowPartial` 才照查并返回 `partial`、`skippedFiles`（§5.6、T29）。P9 约束 gate 判定，不涉查询 |
| 48 | impact、diff 没有上限；"游标就是服务端状态"不成立 | GPT 异构 | 部分接受 | 接受硬上限 + `truncated`，并更正游标说法（可编码 commit 与偏移而无状态）（§3.5）。续页令牌 v1 不做：没有用例，等真有大仓库再加，不改现有字段 |
| 49 | 没写 CORS 预检；Electron 可能发 `Origin: null`，放行 null 就人人能调 | GPT 异构 | 接受 | 同 #11；正式版令牌列入 Q1 |
| 50 | record_approval 会跑任意 pre-commit 钩子，`openWorldHint:false` 不可靠 | GPT 异构 | 接受 | 该工具改为 `openWorldHint: true`（§4） |
| 51 | gate 输出含耗时，查询无 ORDER BY 时无序，"逐字节相同"不成立 | GPT 异构 | 接受 | 改为规范化后比较（§3.5、T4） |
| 52 | `branch` 只要求能解析成 commit，标签、远端分支、修订表达式都能过；两个 branch 字段没规定一致 | GPT 异构 | 接受 | 必须精确解析为 `refs/heads/<name>`；`activity.branch` 给了必须相同（§5.9、T20） |
| 53 | 规范 §13 仍写"MCP 接口的具体设计不在第一批范围" | GPT 异构 | 接受 | 核实规范第 275 行确有此项。§9 补删除这一项 |

### 第二轮（2026-11-20，拍板后）

2 路评审，覆盖第一轮之后修订与拍板后新增的内容：**GPT 异构**（`gpt-5.6-sol-high`，经 cursor-agent `--print --mode ask` 只读，原始输出 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/gpt-review-2.txt`（临时目录，可能已清理））11 条，编号 R2-1–R2-11；**Claude lens**（`claude-opus-5-5`，Git 语义与安全，带临时仓库实测，现场 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/gitsec.lhpc`）11 条，编号 R2-12–R2-22。共 22 条：**接受 17、部分接受 5、反驳 0**；其中 2 条的一部分**转设计会话**（不推翻已拍板结论，属需要用户另行决定的新规则或取舍），已于 2026-11-20 拍板（§10.1）。

事实核实：`aisep.py` 第 523、586、632 行消息带 `rel(f)`、第 937 行缺省文件发现用 `glob(..., recursive=True)`，本会话重读源码确认；§5.8 kind 表被段落打断，重读本文确认；"提交后父提交不等于复验时的分支头 → `update-ref` 比较并交换撤回、分支头回到并发提交 C、C 不丢、`git status` 干净；A 之上再有提交时比较并交换失败"，本会话在临时仓库探针确认（`/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/rb.S1r6`）。符号链接目录、assume-unchanged/skip-worktree、改名后截断、`gitdir` 篡改、本地 main 落后诸项沿用 Claude lens 的临时仓库实测，未重跑。

**steelman（两路一致）**：worktree 模式仍以 merge-base 为起点、不新增运行态写接口；`incomplete + indeterminate` 避免把半写文件报成整文件删除；拒绝路径参数、不跟随符号链接方向正确；Q3=A 落实为逐提交 + 源图语义，强于净差异；`openViolations` 与 `preexisting` 满足 Q6 条件二且没有放宽提交门槛。问题集中在：校验与提交之间的竞态、路径校验只做了一半、文件集合口径不统一、几处规范改文与正式接口不一致。

| # | 意见 | 来源 | 处置 | 理由与落点 |
|---|---|---|---|---|
| R2-1 | 先校验 headCommit..tip、到第 7 步才加锁提交，期间新增的代码提交会被批准提交叠上（批准绕过） | GPT（blocker） | 部分接受 | 接受问题（与 R2-13 合并，Claude 实测复现）。采纳"锁内重跑全部校验"；不采纳"临时 index + `update-ref` 原子提交"：绕开仓库钩子，第一轮 #24 已否决。改为提交后核对 `A^` = 复验时的 tip，不等用 `update-ref <b> A^ A` 比较并交换撤回并报 `STALE_HEAD`，撤回再失败报 `CONFLICT`（§5.9 第 1、7 步，T23；探针确认撤回可行） |
| R2-2 | linked worktree 可在 `--allow-root` 外，传分支名即可间接读写 | GPT（blocker） | 接受 | 定位出 W 后校验 `realpath(W)` 在根目录下、common dir 与 repo 相同（§3.3、§5.8 第 0 步、§5.9 第 7 步，T23、T36） |
| R2-3 | "读哈希 → rename"不是真正的比较并交换 | GPT | 部分接受 | 接受改称"写前哈希核对"、列为已知限制、补覆盖竞态的测试（§3.4、§9 附录 C、T13）。不采用原子交换再核对：平台相关（`renameat2` / `renamex_np`），换回时有同样窗口 |
| R2-4 | assume-unchanged / skip-worktree / 稀疏检出下 `git status` 为空，快速路径漏报 | GPT | 接受 | 与 R2-17 合并。有这些标志或开了 sparse-checkout 不走快速路径；skip-worktree 且磁盘缺失按 headCommit 的 blob 计（§5.8 第 3、4 步，T35） |
| R2-5 | 读取无稳定快照，可能混合两个时刻 | GPT | 部分接受 | worktree 模式的 diff 接受：前后记 HEAD、文件集合、哈希，不一致重读 3 次，仍变 → 新错误码 `WORKTREE_CHANGED`（可重试）（§5.8 第 4 步、§7.2、T35）。`model_check` 等诊断读取不加核对：结论以提交时的 gate 为准（G10），只在 §3.4 写明 |
| R2-6 | 实例键允许 `focus` 为 null，"一换一同文案违规"计数不变会被放过 | GPT | 接受 | 写工具上线前所有 L0–L2 Violation 调用点必须给出 `focus`（T7 普查）；此前 `focus` 为 null 的键补 `file`；T7 补"一换一"反例（§5.1 第 5 步、§7.3） |
| R2-7 | `openViolations` 沿用展示去重，同文案不同对象被折叠 | GPT | 接受 | `items` 不做展示去重，`count` 为实例数（§5.4、§7.3、§8、T37） |
| R2-8 | §9 规范改文把 branch、headCommit 写成"可选活动信息"，与 Q6 ⑤ 矛盾 | GPT | 接受 | 核对 §5.9 与 Q6 ⑤ 属实。改为顶层必填 branch、headCommit，活动只含代理、sessionRef、起止时间和标签，写明 expectedBaseCommit 只核对（§9 §8.3 改文） |
| R2-9 | 合并提交"其父提交"无定义；§9 没写 Q3=A 的三项条件 | GPT | 接受 | 范围内有合并提交直接 `STALE_HEAD`；三项条件逐字写进 §9 的 §6.6、§8.3 改文（§5.9 第 1 步、T23） |
| R2-10 | 先 lstat 再 open 有替换竞态；FIFO 等可阻塞 | GPT | 接受 | 与 R2-12 合并：从 worktree 根目录描述符逐级 `openat(O_NOFOLLOW)`，`fstat` 须为普通文件（§3.3、§5.8 第 4 步、T35） |
| R2-11 | "禁用 squash/rebase"不足以保证可达：直接 push、force push、cherry-pick 也会丢原提交 | GPT | 接受 | 不改 Q5 结论，只补落实条件：关两种合并方式 + 禁 force push + 限直接 push + 保留原提交，CI 可查 evidence 是受保护分支的祖先（§5.8 用途表、§9 附录 C） |
| R2-12 | 上级目录是符号链接时 `ls-files` 照列、`open()` 穿出工作区；写侧同样 | Claude（blocker） | 接受 | 评审实测读到外部 `SECRET_FROM_OUTSIDE`。逐级 `O_NOFOLLOW`，读侧 `failedFiles`、写侧 `PATH_OUTSIDE_ROOT`；缺省文件发现不再用 glob（§3.3、§5.8 第 4 步、T13、T35） |
| R2-13 | 同 R2-1；另：批准之后再提交代码，旧批准照样随 PR 合入，Q3 理由的"杜绝"只在记录时刻成立 | Claude | 部分接受；**已拍板（2026-11-20）** | 竞态部分同 R2-1。"合并时检查 evidence..分支头之间只有批准提交"是新增规范规则，设计会话已拍板采纳：与 Q3=A 合为同一判据，记录时刻与合并时 CI 共用，合并结果另跑 gate（§5.9 第 10 步与"合并时校验"、§9、§10.1、T38）。原写进 §5.9 第 10 步与附录 C 的残余风险说明已删除 |
| R2-14 | 改名后写坏、未提交搬移后写坏：按路径取 indeterminate 为空，主语被报 removed；视图被误报 modified | Claude | 接受 | 评审实测 4 条 removed。`incomplete` 时 base 或 headCommit 有、成功解析的 head 文件里都没有的主语一律进 `indeterminate`；成员含不可判定主语的视图也进（§5.8 第 4 步、T35） |
| R2-15 | `branch: main`：本地与 origin/main 口径不一致必报 `STALE_HEAD` 或落在未推送提交上；直接往 main 提交与 Q5"只经普通 merge 进受保护分支"冲突 | Claude | 部分接受；**已拍板（2026-11-20）** | 设计会话已拍板：发布关口的批准走短命批准分支经 PR 合入，分支保护不开例外；主线上的批准不带 activity，带了 → `INVALID_ARGUMENT`（§5.9"发布关口"、§10.1、T39、T40）。`branch` 不再接受主分支（`INVALID_ARGUMENT`），原先接受的"本地主分支须等于跟踪远端"同步校验随之取消（§5.9 输入表、T23） |
| R2-16 | 两套文件集合口径：diff/脏检查按 Git，check/gate/基线/钩子按磁盘 glob（含被忽略文件、嵌套仓库） | Claude | 接受 | 评审实测；`aisep.py` 第 937 行重读确认。统一文件集合函数，钩子同用；脏检查改为"集合及内容与 HEAD 一致"，被忽略文件不再进 gate，所以不必改用 `status --ignored`（§3.3、§5.1 第 2 步、§5.9 第 7 步、T35） |
| R2-17 | 同 R2-4；"不读 index"与用 `ls-files` 取集合自相矛盾 | Claude | 接受 | 同 R2-4；措辞改为"index 只定文件集合和标志位，内容以磁盘为准"（§3.3、§5.8 算法总述） |
| R2-18 | (b) 写死本次 `model` 的 governance.ttl，同一分支先后批准两个模型会 `STALE_HEAD` | Claude | 接受 | (b) 改为只改一个 `models/*/governance.ttl`，(c) 按那个模型算；合并提交同 R2-9（§5.9 第 1 步、T23） |
| R2-19 | `.git/worktrees/<n>/gitdir` 可被改成任意目录，W 未校验 | Claude | 接受 | 同 R2-2（评审实测后已改回） |
| R2-20 | "实例键不含 file，搬文件不让旧违规变新"不成立：多条 L1 消息正文带路径 | Claude | 接受 | 重读源码确认。按推荐改为如实说法：带路径的规则改名后视为新违规，方向偏保守，接受（§5.1 第 5 步） |
| R2-21 | kind 表被段落打断，后三行渲染成碎片，判定顺序不明 | Claude | 接受 | 段落移到表后，补判定顺序（§5.8 第 9 步） |
| R2-22 | `includeOpenViolations` 只为测试而加，多一种输出形状 | Claude | 接受 | 删去参数，T3 比对时忽略该字段（§5.4、§8、T3、T37） |

**转设计会话**（不推翻 Q1–Q6，只是需要用户另行决定；2026-11-20 均已拍板，见 §10.1 与"附：设计会话拍板记录"）：
1. R2-13：是否新增规范规则，让 GateMerge 在合并时检查 evidence..合并点之间只有批准提交（堵住"批准后再提交代码，旧批准随合并进主线"）。不加则维持现状：接口只保证记录时刻，残余风险已写进 §5.9 第 10 步与附录 C。→ **已拍板**：新增，与 Q3=A 合为同一判据，合并时 CI 核对并在合并结果上跑 gate。
2. R2-15：发布关口等"合并后的批准"如何与 Q5 的"只经普通 merge 进受保护分支"共存：(a) 走短命批准分支再经 PR 合入；(b) 在分支保护里给批准提交开例外。另需决定主分支上是否允许带 activity（带了 baseCommit 等于 headCommit、差异为空）。→ **已拍板**：(a)，从被发布的提交拉分支；主线上的批准不带 activity。

---

## 附：设计会话拍板记录（2026-11-20）

**设计会话（用户）的答复**

| 题 | 结论 | 附加条件 |
|---|---|---|
| Q1 | B：本机 Streamable HTTP（按推荐） | — |
| Q2 | A：批准提交写会话分支 | — |
| Q3 | A：headCommit 与分支头之间只允许批准提交 | — |
| Q4 | C：最小桩 `aisep:AIAgent`，`approvedBy` 排除 AI | 另一会话曾提议代理用 `arch:Stakeholder`、活动 IRI 用 slug；用户 2026-11-20 在本会话明确选 AIAgent 桩 + 排除 AI，以此为准 |
| Q5 | A：禁用 squash 合并 | **同时禁用 rebase 合并**：批准提交只经普通 merge 进受保护分支。rebase 会改写 commit id，同样使 headCommit 和 evidence 失效 |
| Q6 | A：整体接受 8 项偏离 | **条件一**：第①项让"AI 进行中"在批准前一直为空（`model.diff` 只比已提交内容），要求 diff 能比较工作区未提交改动，撤销"v1 只比已提交内容"的限制。**条件二**：第⑦项留下的遗留违规要能经 findings 查到，并在工作台可见 |
| R2-13 | 新增规则：evidence 到分支头之间只允许批准提交，记录时刻与合并时 CI 用同一判据；合并结果再跑一次 gate | 见下方澄清 ① |
| R2-15 | 短命批准分支 + PR，不给分支保护开例外；主线上的发布批准不带 AI 活动；只改批准记录的 PR 只跑 gate；发布提交打 Git 标签；R2-13 的规则对批准分支同样适用 | 见下方澄清 ②③ |

**执行会话的评估**

- **条件一可行**，不违背 P1、P2：worktree 模式不存状态、不新增上报写工具，只把 diff 的 head 侧从"分支头 commit"扩展到"分支的工作区"，起点仍是 merge-base（ADR-013 的决策不变，只改其"后果"里的限制）。设计要点：按分支名经 `git worktree list --porcelain` 定位，不接受路径（防 HTTP 客户端读任意文件）；工作区内容 = 已跟踪文件当前内容 + 未跟踪未忽略的新 `.ttl` − 已删除文件；解析失败 → `incomplete` + 失败文件清单，其主语记为不可判定，绝不当成"无改动"或"整文件删除"；输出标明 head 种类、headCommit、dirty；关口页差异图与 `record_approval` 仍只认已提交版本；"AI 进行中"缺省用 worktree 模式；同仓同分支的前提保留。落点 §5.8，探针 F19（25/25 CONFIRMED，两处变异各让对应断言 REFUTED）。
- 探针发现并已写进 §5.8 的两个坑：① 失败文件若按"不存在"处理，写到一半的已跟踪文件会把它的全部主语报成 removed，必须取 base 与 headCommit 两个已提交版本里的主语记为 `indeterminate`；② 工作区里的符号链接会让服务器读到工作区外的文件，必须不跟随。另加了 `@{-1}` 这类会被 `check-ref-format --branch` 展开的输入的拒绝。
- **条件二**：`model_findings` 增加 `openViolations`（当前 L0–L2 全部违规，结构化 Finding，不新增层级，gate 不重复计数）；写工具结果的发现项标 `preexisting`；工作台"架构全景"显示违规计数徽标，为此工作台画像加列 `model_findings`。说明：pre-commit 的 gate 遇任何违规即拦提交，已提交内容里的遗留违规只在 `--no-verify` 或规则升级时出现；工作区里未提交的手工违规也会作为写前基线标 `preexisting:true`，提交时照样被拦。落点 §5.1、§5.4、§7.3、§8、T37。
- **更正**：设计会话说"去掉 ADR-010 的限制"，核对后该限制写在 ADR-013 的"后果"和规范附录 C 第 1 条；§9 按 ADR-013 给出可直接替换的修订文字。
- **异构复评**：以上拍板后新增的内容已于 2026-11-20 过第二轮评审（GPT 异构 + Claude lens），处置见下文"第二轮"表。

**R2-13、R2-15 的执行会话澄清**（2026-11-20，已向用户说明）

- ① R2-13：用户原话为"Q5 已定的合并时分支最新提交必须等于 headCommit"。Q5 实际只定了禁用 squash/rebase 合并；严格相等与 Q3=A 冲突（批准提交本身就让分支头前进，同一会话连过第二个关口也会失败）。统一按"evidence 到分支头之间只允许批准提交"表述，相等是其特例。CI 检查范围 `evidence..分支头`，不含合并提交本身。
- ② R2-15：批准分支从**被发布的那个主线提交**拉，不是主线最新提交；否则主线在其后的提交落进 evidence..分支头，被 R2-13 的规则拒绝。
- ③ R2-15：标签名 `release/{yyyymmdd}-{短hash}` 或版本号，避免同日重名；标签同时让被发布的提交不被 GC。
- 落文时补的实现细节（未改结论）：CI 只查本 PR 新增、且推导 approvalState 时被采用的记录（被同关口同对象的新记录取代的旧记录不查，否则重新过关口后 PR 永远过不了）；`branch` 不再接受主分支，原 R2-15 的本地与远端同步校验取消；`GateRelease` 的 headCommit 必须在主分支上；带 activity 的拒绝沿用 `INVALID_ARGUMENT`；标签由工作台创建推送，CI 检查。以上未经异构评审。
- ④ 用户 2026-11-20 确认保留：批准后把主分支合回功能分支，会在 `evidence..分支头` 中引入非批准提交（合并提交），按同一判据批准失效，须重新过关口。这是规则的直接结果，接受其日常操作成本。

## 附：合并记录（2026-11-20）

同一份接口设计被两个会话各写了一份：本会话的设计稿（约 1350 行，已过两轮评审、含 GPT 异构，Q1–Q6、R2-13、R2-15 已拍板），以及另一会话写进本仓库的 212 行草案。用户 2026-11-20 拍板：以前者为底整体替换本文件，并入后者独有且不冲突的内容，冲突以前者为准。

**并入的内容**

| 来源（另一会话草案） | 并到哪里 | 怎么并 |
|---|---|---|
| §3.5 `model.set_labels`（用户已在另一会话拍板为对 §8.3 的扩展） | §5.10；§2 操作清单、§4 工具总表、§8 `client.ts` 注释、§9（§3、§8.3 两处改文）、§10.2 D4、附录 A、T41 | 按本文命名约定改名 `model_set_labels`；字段名改成与 `model_add_element` 一致（`prefLabel`/`altLabel`/`definition`，原为 `labelZh`/`labelEn`/`altLabels`）；补齐本文风格的输入、输出、错误、annotations、验收用例。D4 原"改名一期不加"改为"已由用户在另一会话拍板加入" |
| §2.2 写入哪个文件：关系规则 | §5.1"写到哪个文件"表 | **取代**本文原规则"源端元素所在的文件"。合并时用 `models/procurement/` 的 27 个关系逐一核对：另一会话的规则 27/27 符合，本文原规则 24/27（源端在 `am4.ttl`、目标在 `ddd.ttl`/`verification.ttl` 的 3 条不符）。补 T42 |
| §2.2 写入哪个文件：`aisep#` 被多个 Extension 共用时按 `aisep:loads` 判定 | §5.1 表后说明 | 本文只写了"按模块目录，不按命名空间（F15）"，没写怎么判定；补上判定方法（GAP，新写一个小函数） |
| §2.2"新建模型目录不在 §8.3 范围，v1 手工建" | §5.1 表后说明 | 原样并入，补错误码 `MODEL_NOT_FOUND` |
| §5 工具↔规范↔原型追溯表（含 GAP/EXISTS 与行号） | 附录 D | 工具名统一为下划线名，章节号改指本文；行号逐条对照本仓库 `tools/aisep.py`、`modules/aisep-core/shapes.ttl` 核对，全部一致；补 `model_findings` 的 `openViolations`、`AGENTS` 拆分、HTTP 外壳、统一文件集合等本文新增的工作 |

**被替代的说法**

| 另一会话草案的说法 | 本文 | 理由 |
|---|---|---|
| 传输 v1 只用 stdio，一个 worktree 一个服务器进程 | 代理走 stdio，工作台走本机 Streamable HTTP（§3.2） | Q1=B 已拍板：stdio 要改上游 `main.ts`、`preload.ts`，违背 P10 |
| 并发靠 Git 当锁，服务器不加锁，stdio 天然串行 | `flock` 锁目标 worktree + 写前哈希核对（§3.4） | 工作台 HTTP 进程与各代理进程会写同一 worktree（批准写会话分支，Q2=A），必须跨进程互斥 |
| 写入流程：先改文件、写后跑 L0–L2、有新违规再恢复原字节 | 在内存候选图上判定，拒绝时磁盘一个字节不改；新违规按实例键多重集判定，结果标 `preexisting`（§5.1） | 写后恢复有崩溃窗口；展示键会放过"同措辞、不同对象"的新违规（第一轮评审） |
| 错误码 `UNKNOWN_MODEL`、`NOT_FOUND`、`VALIDATION_FAILED`、`QUERY_ERROR`、`GIT_ERROR`、`PARSE_ERROR_AT_REF` | §7.2 的错误码表 | 本文的错误码更细，代理能按码决定下一步；两套不并存 |
| `model.remove` 用 `mode: refuse \| cascade` | `cascade` 布尔 + `dryRun` + `planDigest`（§5.5） | 计划哈希防止"看过的计划"与实删不一致，且重放幂等 |
| `record_approval`：`approvedBy` 为数组；可传 `evidence`；活动的 `headCommit`、`baseCommit` 可选传入；代理必须是 `arch:Stakeholder` | §5.9：`headCommit` 顶层必填，evidence、baseCommit、generatedAt 由服务器算、传了即 `INVALID_ARGUMENT`；`approvedBy` 只收人 | Q6 第⑤项、Q3、Q4 已拍板 |
| `model.diff` v1 只比较已提交内容 | Git 引用模式 + worktree 模式（§5.8） | Q6 条件一已拍板 |
| §6 第 4 条待决：代理建模为 `arch:Stakeholder`（如 `:agentClaudeCode`），活动 IRI `{model}activity-{yyyymmdd}-{slug}` | 关闭。`aisep:AIAgent` 最小桩 + `approvedBy` 排除 AI；活动 IRI `{model}activity-{yyyymmdd}-{headCommit 前 7 位}`（§5.9、§6） | 用户 2026-11-20 在本会话明确选 Q4=C，以此为准（见"附：设计会话拍板记录"Q4 行） |
| 元素 slug 正则 `^[A-Za-z][A-Za-z0-9]*$`（允许大写开头，如 UML 类 `QuotationEntity`） | `^[a-z][A-Za-z0-9]*$`（§5.2） | 合并时先按本文保留，复核后改采 B：规范 §3 只写"可读英文 camelCase"，例子里已有大写开头的 `QuotationEntity`（`uml.ttl`），本文原正则建不出这种 slug（执行会话 2026-11-20 改，§5.2 已同步） |

两份文档一致、无需取舍的部分（线上名下划线、语义名保留点号；服务器以库方式复用 `tools/aisep.py`，拆库后 `aisep.py test` 仍全绿；新增 `model.gate`）按本文的写法保留。

合并新增的内容（§5.10、§5.1 关系规则与 `aisep:loads` 判定、附录 D、T41、T42）**未经异构评审**；关系规则与附录 D 行号有脚本核对，§5.10 只是按本文已有约定补齐。
