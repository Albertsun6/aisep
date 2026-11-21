# MCP 接口设计：评审与拍板记录（历史）

本文件的内容从 `docs/mcp-interface.md` 原样移来（L6-P2），`BEGIN-MOVED` / `END-MOVED` 标记之间逐字未改。这些是 2026-11-20 前后的设计状态说明、事实核实表、拍板与评审记录，供追溯；现行契约以 `docs/mcp-interface.md` 为准。

文中提到的 §10、附录 A、附录 B 与文末各「附」在本文件内；§3.1、§9、§11、附录 D 在 [`mcp-interface-mirrors.md`](mcp-interface-mirrors.md)；其余节号指 `docs/mcp-interface.md`。

## 文首状态与事实表

<!-- BEGIN-MOVED TOP -->
> **状态：草案定稿候选（设计会话已拍板 Q1–Q6、R2-13、R2-15、U1–U4、R4-1/R4-2/R4-5/R4-7/G4-4，已过四轮评审，其中各含一路 GPT 异构，第四轮另含 Grok 红队）。** 日期：2026-11-20。第二轮评审（拍板后，GPT `gpt-5.6-sol-high` + Claude Git 语义与安全 lens，22 条）的处置见文末"第二轮（2026-11-20，拍板后）"；其中转设计会话的 2 条（R2-13、R2-15）已于 2026-11-20 拍板，落进 §5.9"合并时校验""批准专用 PR""发布关口"、§9、§11（T38–T40）。第三轮评审（R2-13/R2-15 拍板后，GPT + Claude Git 语义 lens + Claude 对抗绕过 lens，归并为 18 簇）的处置与设计会话拍板 U1–U4 见文末"第三轮（2026-11-20，R2-13/R2-15 拍板后）"，落进 §3.3、§5.1、§5.9、§9、§10.1、§11（T13、T21、T23、T26、T38–T40、T43）、附录 D。第四轮评审（只评第三轮修订，GPT 14 条 + Grok 7 条）的处置与用户拍板（R4-1、R4-2、R4-5、R4-7、G4-4，见 ADR-016）见文末"第四轮（2026-11-20，第三轮修订后）"。拍板结果见 §10.1 与文末"附：设计会话拍板记录"；Q6 的两个附加条件（`model_diff` 比较工作区未提交改动、遗留违规可查可见）已落进 §5.1、§5.4、§5.8、§7.3、§8、§9、§11。
> **合并**：由本会话设计稿与另一会话草案合并（2026-11-20），以前者为底；并入了后者的 `model_set_labels`（§5.10）、关系写入文件规则（§5.1）和工具↔规范↔原型追溯表（附录 D），被替代的说法与理由见文末"附：合并记录"。本文原写在仓库外，路径已改为仓库内路径（`docs/`、`tools/`、`modules/`、`models/`）。文中"规范"指 `docs/metamodel-spec.md`（《元模型规范》），ADR 指 `docs/decisions.md`，"原则五"指 `docs/principles.md`，"原型"指本仓库 `tools/aisep.py` 及其模块与例子。
> 本稿由三份独立草案（编码代理视角、工作台视角、语义视角）合成。冲突的裁决见附录 A。
> **第一轮 4 路评审**：3 路 Claude lens（规范一致性、MCP 协议、Git 语义）+ 1 路异构（GPT 族，`gpt-5.6-sol-high`，经 cursor-agent `--mode ask` 只读）。53 条意见逐条处置，见文末"附：评审与辩论记录"。第一轮异构评审只覆盖修订前的版本；修订后与拍板后的新增内容（§5.9 逐提交校验、目标 worktree 锁、§5.8 worktree 模式、`openViolations`、`preexisting`、禁用 rebase 合并）已由第二轮评审覆盖（含一路 GPT 异构）。
> 分工：设计会话拍板，执行会话写文件（`docs/methodology.md` 第 111 行）。第 10 节记录设计会话的答复（§10.1）和已按推荐定下、可推翻的默认项（§10.2）。拍板后新增的内容（worktree 模式的 diff、`openViolations`、`preexisting` 标记、禁用 rebase 合并）已过第二轮评审；第二轮的修订与 R2-13、R2-15 的落文已过第三轮评审；第三轮的修订本身（U1–U4 与各簇改文）已过第四轮评审（GPT + Grok 红队，21 条，每条经文档对照与可执行探针两路核实）；第四轮的修订只经同模型落文，未再过评审。

**已用原型只读命令核实的事实**（`PY` 为 `AGENTS.md` 里的共用解释器，2026-11-20；当时在仓库外的原型目录 `metamodel-prototype/` 下执行，本仓库的 `tools/`、`modules/`、`models/` 与之逐文件一致，下文路径均指本仓库）

| # | 事实 | 命令或出处 |
|---|---|---|
| F1 | `check` 采购例子：0 Violation、1 个 L2 Warning（派生捷径），0.07 秒，退出码 0 | `check` |
| F2 | `gate` 采购例子：PASS，1 Warning，5.0 秒 | `gate` |
| F3 | `impact procurement:quotation`：depends 14 个元素，ripple 16 个 | `impact … --mode depends/ripple` |
| F4 | `impact` 遇到不存在的元素：只打一条 Warning，**退出码 0，结果为空** | `impact procurement:noSuchThing` |
| F5 | `query` 收到 `INSERT DATA`：pyoxigraph 抛 `SyntaxError` 堆栈，原型没有包装，退出码 1 | `query 'INSERT DATA {…}'` |
| F6 | `query` 里的 `SERVICE` **会真的发 HTTP 请求**（报错 `OSError: The port 9 is not allowed for HTTP(S)`，说明已尝试连接） | `query 'SELECT * WHERE { SERVICE <http://127.0.0.1:9/sparql> {…} }'` |
| F7 | 采购模型 54 个成员；`arch:approvalState` 有 26 个，值是 IRI：`arch:Proposed` 25 个，`arch:Approved` 1 个（其中 1 个 Proposed 是 `arch:Stakeholder` 首席架构师；推导范围按 R4-5 收窄后为 25 个：Proposed 24 个，Approved 1 个） | `query` |
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
<!-- END-MOVED TOP -->

<!-- BEGIN-MOVED §10 -->
## 10. 设计会话的拍板

> **状态**：Q1–Q6 已由设计会话于 2026-11-20 拍板，全部按推荐，Q5、Q6 带附加条件（下表）。附加条件已落进正文，并已过第二轮评审（含一路 GPT 异构，T33）；第二轮转设计会话的两条（R2-13、R2-15）已于同日拍板，见 §10.1 R2-13、R2-15 两行；第三轮评审（3 路）转设计会话的四题（U1–U4）已于同日拍板、均选推荐项，见 §10.1 末四行与文末"第三轮"。§10.2 的默认项设计会话未提异议，维持。

### 10.1 已拍板（6 题 + 第二轮转来 2 条 + 第三轮 4 题）

| # | 问题 | 结论 | 日期 | 附加条件 | 落点 |
|---|---|---|---|---|---|
| Q1 | 工作台传输与 HTTP 设防 | **B**：本机 Streamable HTTP，只绑 `127.0.0.1`，CORS 精确白名单 | 2026-11-20 | 无新增；维持原附带条款：开发期不加令牌为接受的风险，打包前必须定令牌方案 | §3.2 |
| Q2 | 批准提交写到哪条分支 | **A**：缺省写会话分支；"待批准关口"读主分支，另查分支上的"已批准、待合并"标记 | 2026-11-20 | 无 | §2、§5.9 |
| Q3 | headCommit 落后于分支头时能否批准 | **A**：只允许 headCommit..tip 之间全是批准提交 | 2026-11-20 | 无 | §5.9 第 1 步、T23 |
| Q4 | AI 代理建模、`approvedBy` 是否只收人 | **C**：最小桩 `aisep:AIAgent` + `approvedBy` 排除 AI | 2026-11-20 | 无 | §5.9、§6、§9（§6.6、§6.7、附录 C） |
| Q5 | 历史批准提交的保留策略 | **A**：模型仓库禁用 squash 合并 | 2026-11-20 | **同时禁用 rebase 合并**：批准提交只经普通 merge 进受保护分支。理由：rebase 合并会给每个提交生成新的 commit id，原来的 headCommit 不再在受保护分支的历史里，与 squash 一样使活动的 `aisep:headCommit`、记录的 `aisep:evidence` 指向一个随后可能被 GC 的提交，§5.9 的"evidence = 被批准的 commit"和历史差异图都失效。这是仓库托管平台的分支保护设置，接口不检查 | §5.8 用途表、§9 附录 C |
| Q6 | 是否整体接受 8 项偏离 | **A**：整体接受 | 2026-11-20 | **条件一**：第①项（写工具只改工作区不提交）会让"AI 进行中"在批准前一直为空，要求 `model.diff` 能比较工作区未提交改动，撤销"只比已提交内容"的限制（设计会话说的是 ADR-010，实际在 ADR-013 与规范附录 C 第 1 条，按 ADR-013 改）。**条件二**：第⑦项（写前只拒新增违规）留下的遗留违规要能经 findings 查到，并在工作台可见 | 条件一：§5.8（worktree 模式）、§2、§4、§8、§9、T35–T36；条件二：§5.1、§5.4、§7.3、§8、T37 |
| R2-13 | 批准后再提交代码，旧批准会随合并进主线 | **新增规则**：批准记录的 evidence（= 关联活动的 headCommit）到分支头之间只允许批准提交（§5.9 批准提交判据）；记录时刻（`record_approval`）与合并时刻（CI）用同一判据，与 Q3=A 合为一条；合并时另在合并结果上跑一次 `model_gate` | 2026-11-20 | **澄清**：用户原话为"Q5 已定的合并时分支最新提交必须等于 headCommit"；Q5 实际只定了禁用 squash/rebase 合并，且严格相等与 Q3=A 冲突（第一次批准提交就让分支头前进），统一按"只允许批准提交"表述，相等是其特例。CI 检查范围是 `evidence..分支头`（分支这一侧），不含合并提交本身。旧批准随合并进主线的残余风险已从 §5.9、附录 C 删除 | §5.9 第 1、10 步与"合并时校验"、§9（§6.6、§8.3、附录 C）、T38 |
| R2-15 | 发布关口等主线上已有提交的批准如何与受保护分支共存 | **短命批准分支 + PR**，不给分支保护开例外：从被发布的主线提交拉分支，只含一个批准提交，PR 合入后删分支；主线上的发布批准不带 AI 活动（带了 → `INVALID_ARGUMENT`）；只改批准记录的 PR 只跑 gate、不再过关口，夹带其他改动按普通 PR，由 CI 判定；evidence 指向被发布的提交并打标签；R2-13 的规则对批准分支同样适用 | 2026-11-20 | **澄清**：① 从**被发布的那个提交**拉分支，不是主线最新提交，否则主线前进后 R2-13 的规则会拒绝；② 标签名 `release/{yyyymmdd}-{短hash}` 或版本号，避免同日重名，同时防 GC（"防 GC"已由第三轮 N 更正：R 是主线提交，可达性由主线保证，标签只是对外发布指针）；③ "只跑 gate"已由第三轮 U4② 收紧：批准专用 PR 照跑全部合并时校验，合并按 ADR-021 第 1 款机械核对（原为「仍须人工 PR 批准」） | §5.9 输入表 `branch` 行、第 1 步与"批准专用 PR""发布关口"、§9（§6.6、§8.3、附录 C）、T23、T39、T40 |
| U1 | 旧批准漂移：普通 PR 修改已批准元素，旧批准仍让它显示为 Approved（第三轮对抗绕过-2、GPT R3-8 的一半） | **CI 拦截，不改元模型**：普通 PR 中，`目标分支头..PR 头` 的模型差异里被修改的、在目标分支头上 approvalState=Approved 的元素，同一 PR 里必须有一条新增且通过逐条核对的合法批准覆盖它，否则拒绝合并；删除已批准元素按 Q6④ 一律拒绝（核对轮 1） | 2026-11-20 | 落文口径："`目标分支头..PR 头` 的模型差异"按合并结果相对目标分支头的源图差异计算，避免主线分叉后新增的内容被误报为删除（执行会话补，未改结论）；第四轮补：覆盖记录须为 Approved、关口不限，且须是合并结果中生效的记录（R4-2 用户拍板、R4-3） | §5.9 第 10 步与"合并时校验"检查项 6、§9（§6.6）、T38、ADR-015 |
| U2 | `governance.ttl` 追加冲突：两条分支各批准一次，合并必冲突（第三轮 git-1） | **一条记录一个文件**：`record_approval` 新建 `models/<slug>/governance/<记录本地名>.ttl`（活动块（如有）+ 记录块），只提交这一个新路径；判据 (b) 改为只在**一个**模型的 `governance/` 目录下**新增**文件，不修改、不删除任何已有文件 | 2026-11-20 | 已有 `governance.ttl` 里的记录与人员不搬迁（IRI 不变），它仍是 Stakeholder 等 governance 类元素的缺省写入文件；§3.3 统一文件集合包含 `models/<slug>/governance/*.ttl`（原型 `model_files` 一项记入附录 D，核对结果见附录 D） | §3.3、§5.1、§5.9 输入表与第 1、5、7、8、9 步、输出、§9（§6.6、§8.3、附录 C）、T13、T21、T23、T26、T43、附录 D、ADR-015 |
| U3 | 合并结果 gate 失效：CI 通过后主线前进，平台不自动重跑必需检查（第三轮 GPT R3-7、git-2、对抗绕过-5） | **合并前重算**：不开"要求分支最新"、不用合并队列（个人 private 仓库不可用）；执行合并的人（目前是 AI 按「批准 #N」代合并（2026-11-21 注：已改为 `AGENTS.md`「分支与合并」第 2 条的自动合并，必需检查通过且独立评审通过后由协调会话合并，不再逐个等「批准 #N」））在 `gh pr merge` 之前，用同一个检查脚本对**当前**目标分支头重跑合并时校验与合并结果 gate，不过不合 | 2026-11-20 | 残余风险登记规范附录 C：绕过脚本直接点网页合并按钮时，合并结果 gate 可能对旧主线有效；脚本未实现前记为 GAP（2026-11-21 注：已实现，见附录 D） | §5.9 第 10 步与"合并前重算"、§9（§6.6、附录 C）、T38、附录 D、ADR-015 |
| U4 | 批准专用 PR 可伪造、主线旧提交可补批非发布关口（第三轮 GPT R3-1/R3-2、git-7、对抗绕过-6） | **两项都收紧**：① 主线提交（headCommit 的有效内容提交是 mainRef 的祖先或等于它，定义见 §5.9 第 1 步，核对轮 4、第四轮 R4-13；`GateRelease` 的 headCommit 本身仍须在主线上）上的批准只允许 `GateRelease`，其他关口 → `INVALID_ARGUMENT`（`details.reason: "mainline-head-gate-not-release"`）；② 批准专用 PR 只免"再过 AISEP 关口"，**仍须人工 PR 批准**（AGENTS.md「批准 #N」） | 2026-11-20 | 信任模型维持 §4（真正的约束是代码评审和分支保护），不引入签名 | §5.9 第 1 步"主线提交的批准"、"合并时校验"检查项 3、"批准专用 PR"、§9（§6.6、§8.3）、T39、T40、ADR-015 |

**原问题、选项与推荐理由（存档，供追溯）**

| # | 问题 | 选项 | 推荐与理由 |
|---|---|---|---|
| Q1 | 工作台用什么传输，HTTP 怎么设防 | A：Electron 主进程起 stdio 子进程，经 preload/IPC 给 renderer；B：`--transport http` 只绑 `127.0.0.1`，协议 2026-07-28（无握手、无会话），renderer 直接 `fetch`；CORS 精确白名单（`app://renderer` + 开发期 dev server 源，永不放 `*`/`null`），带 Origin 且不在白名单 → 403；C：工作台不走 MCP，直接调 CLI | **B**。P10 把上游接触面定死了，A 要改 `main.ts`、`preload.ts` 两个上游文件；C 违背 ADR-008。附带要定的一条：**开发期不加令牌**，不带 Origin 的本机进程（如 `curl`）能调到 `record_approval` 并产生批准提交，这是接受的风险，与 AO daemon 同级；**打包前**必须定令牌方案（建议每次启动生成、经已有的受信渠道交给 renderer） |
| Q2 | 批准提交写到哪条分支，"待批准关口"怎么显示 | A：缺省写会话分支（随 PR 合入），发布关口等合并后的批准显式传 `branch: main`（已被 R2-15 取代：发布批准走批准分支）；"待批准关口"读主分支，另对有会话的分支用 `model_query(ref=branch)` 查出"已在分支批准、待合并"标记；B：同 A，但"待批准关口"整体按分支读；C：永远写主分支 | **A**。批准和被批准的版本在同一条分支，合并后历史自然连在一起；C 会让 `approves` 指向主分支上还不存在的元素（G8 那类悬空）。A 的显示方式保证每个状态都出自所读那份内容的批准记录（P4），又不会让人把已批的元素再批一次。代价：分支被放弃时批准记录随之丢失，而被放弃的分支本来不需要批准 |
| Q3 | headCommit 落后于分支头时能否批准 | A：允许，但 headCommit..tip 之间每个提交都必须是批准提交（带 trailer、只改 governance.ttl、源图差异只新增 ApprovalRecord/AgentActivity 主语；判据 (b) 已由 U2 改为只在一个模型的 `governance/` 下新增一个记录文件，见 §5.9 第 1 步）；B：任何祖先都可以；C：必须严格等于分支头 | **A**。B 会出现"批准了旧版本，新提交没人看就随合并进主线"；C 让同一会话连过第二个关口时失败（第一次批准提交已让分支头前进）。A 逐提交按语义判，堵住了"往 governance.ttl 里塞新人员或元素"和"先加后删、净差异为空"两条绕过路径，可测（T23） |
| Q4 | AI 代理怎么建模，`approvedBy` 是否只收人 | A：现状（Stakeholder 兼任）；B：vendor 整个 PROV-O；C：`aisep:AIAgent` 最小桩（对齐公理放 aisep-core 对齐文件）+ `approvedBy` 排除 AI；C'：只加桩，不收紧 `approvedBy` | **C**。见 §6.2：改动最小，不打开 G7 的口子，用规则保证原则五"人工把关"。代价：拆 `AGENTS`、改 L1/EG13/EG17、加 2 个非法夹具 |
| Q5 | 历史批准提交的保留策略（squash、删分支后 headCommit 可能被 GC） | A：模型仓库禁用 squash 合并，批准提交经普通合并进受保护分支（分支保护规则）；B：`record_approval` 另写保活 ref `refs/aisep/activity/<id>`；C：接受限制，登记附录 C，不再声称历史可复现 | **A**，做不到就 **C**。A 零新机制；B 多一类 ref 要管理。这是仓库治理规则，不是接口能单方面定的 |
| Q6 | 是否整体接受本文对规范字面的偏离（§9 各条以此为前提） | A：整体接受下列 8 项；B：逐项重议 | **A**。8 项：① 三个 `model_*` 写工具只改工作区、不提交（"进 Git"由代理随代码提交、pre-commit gate 把关），只有 `record_approval` 自己提交；② Approved 要求 evidence 处 gate PASS（`GATE_FAILED`），Rejected 不受限；③ 删除时 BPMN 成员属性（flowElements、flowNodeRefs、lanes、laneSets）摘除、`bpmn:default` 拒绝（§8.2 字面是一律拒绝，那样流程里的节点删不掉）；④ 批准记录、AI 活动、模型不能经 `model_remove` 删除，被批准过的元素只能退役（本文新规则，依据 ADR-009 + 原则五）；⑤ `record_approval` 不收调用方的 evidence、baseCommit、generatedAt（规范原文写"可选传入 baseCommit、headCommit"），headCommit 改为必填；⑥ 新增 IRI 规则：关系类无直连形式时取类本地名，AI 活动 `{model}activity-{yyyymmdd}-{head7}`，唯一键 (sessionRef, headCommit)；⑦ 写工具在写前候选图上跑 L0–L2，只拒绝新增违规（规范写的是"写入后跑"）；⑧ 新增 `model.gate` 工具 |

### 10.2 已按推荐定下的默认项（不合意直接推翻，不改接口其余部分）

| # | 事项 | 采用 | 理由 |
|---|---|---|---|
| D1 | 编码代理画像是否列出 `governance_record_approval` | 不列 | 批准是人的动作（原则五）。画像不是安全边界（§4） |
| D2 | "改动元素"一栏口径 | `changedElementCount`（只数 kind=element 的增删改） | 最贴近"改了哪些元素"；`touchedElementCount` 也返回，改口径不改接口 |
| D3 | 校验工具个数 | 保留 check/validate/findings + 新增 gate，单层结果标 `partial: true` | 只加不改 §8.3 契约。实测代理常选错再改成单一工具 |
| D4 | 辅助工具（列元素、查词汇） | 一期不加；改名工具 `model_set_labels` 已由用户在另一会话拍板加入（§5.10）。工作台的列元素、待批准列表用固定查询 `ELEMENTS_QUERY`、`PENDING_QUERY`（§8），不是工具 | §8.3 没有；固定查询超过 5 条，或代理常因"不知道能连什么"反复被拒，再加 |
| D5 | 代理身份映射 | 每种 harness 在模型里有一个固定代理元素，找不到就拒绝并提示先建 | 元素数量稳定，历史能按代理聚合；不让写工具多一个"顺带建元素"的分支 |
| D6 | 工作台的仓库与主分支从哪来 | 服务器启动参数 `--repo`、`--main-branch`，工作台不传 | 不依赖 AO 的 `GET /api/v1/projects`，P10 上游接触面不扩大；v1 本来就只支持单仓库 |
| D7 | 主分支短名怎么解析 | 先远端跟踪引用 `refs/remotes/<upstream>/<b>`，再本地分支 | 本地 main 落后时 merge-base 会落到旧提交，diff 虚高（评审实测） |
<!-- END-MOVED §10 -->

<!-- BEGIN-MOVED 附录 A -->
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
<!-- END-MOVED 附录 A -->

<!-- BEGIN-MOVED 附录 B -->
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
<!-- END-MOVED 附录 B -->

<!-- BEGIN-MOVED 附：评审与辩论记录 -->
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

### 第三轮（2026-11-20，R2-13/R2-15 拍板后）

3 路评审，覆盖第二轮修订与 R2-13、R2-15 的落文（§5.9"合并时校验""批准专用 PR""发布关口"、§9、T38–T40）：

- **GPT 异构**（`gpt-5.6-sol-high`，经 cursor-agent `--print --mode ask` 只读）13 条，编号 R3-1–R3-13。原始输出 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-QOofDR/9d4f8803-c7b5-437e-bee2-7bb8f331cde5/scratchpad/gpt-review-3.txt`（临时目录，可能已清理）。
- **Claude lens：Git 语义**（`claude-opus-5-5`，临时仓库实测）9 条，编号 git-1–git-9。
- **Claude lens：对抗绕过**（`claude-opus-5-5`，在原型副本上实测）10 条，编号 对抗绕过-1–10。

共 32 条，按问题归并为 18 簇（A–R）与 4 道转设计会话的题（U1–U4）：**接受 15 簇、部分接受 3 簇（A、K、M）、反驳 0**；U1–U4 设计会话均选推荐项。

**平台事实核查**（GitHub 官方文档与 API；结论据核查转述，本文落文时未重新抓取）：

| 事实 | 结论 | 出处 |
|---|---|---|
| 合并队列 | 个人账号的 private 仓库不能用（只有组织的 public 仓库或 GHEC 组织的 private 仓库可用）→ U3 不用合并队列 | GitHub Docs：管理合并队列（Managing a merge queue） |
| `.gitattributes` 的 `merge=union` | 服务端合并大概率不遵守：无官方支持声明，社区讨论 #9288 五年未处理 → U2 不靠 union 合并 | GitHub Community discussion #9288 |
| 网页 Resolve conflicts | 把整个 base 分支合进 head 分支 → `evidence..PR 头` 出现合并提交，按判据拒绝（§5.9 检查项 3） | GitHub Docs：在 GitHub 上解决合并冲突（Resolving a merge conflict on GitHub） |
| 不开"要求分支最新"时 | base 前进不会自动重跑必需检查（推断，中高置信）→ U3 合并前重算 | GitHub Docs：关于受保护分支（About protected branches） |
| tag ruleset | private 仓库需 GitHub Pro 及以上 → release 标签保护登记为附录 C 残余风险；2026-11-20 本仓库已配置成功（规则集 `release-tags-immutable`），见附录 C | GitHub Docs：关于规则集（About rulesets） |
| 本仓库 `main` 的分支保护 | 2026-11-20 实测无分支保护（API 返回 `Branch not protected`）→ 落实 Q5 前须先配置，登记附录 C；同日已配置（见附录 C） | GitHub REST API：获取分支保护（`GET /repos/{owner}/{repo}/branches/main/protection`） |

**逐条处置**

| 簇 | 意见 | 来源 | 处置 | 理由与落点 |
|---|---|---|---|---|
| A | 批准专用 PR 可伪造：手写合法形状的 `GateRelease` 记录、任意 trailer，即可跳过关口 | GPT R3-1、对抗绕过-6 | 部分接受 | 接受：判据 (a) 加"trailer 值等于该提交新增记录的 evidence"；批准专用 PR 仍须人工 PR 批准（U4②）。不采纳签名或托管平台审批证明：信任模型见 §4（画像不是安全边界，真正的约束是代码评审和分支保护）（§5.9 第 1 步与"批准专用 PR"、T23、T39） |
| B | 批准专用 PR 结构过宽：多条记录、非发布关口、只含活动都能过 | GPT R3-2 | 接受 | 至少一条新增 ApprovalRecord；每个新增 AgentActivity 都被本 PR 新增的记录引用；主线提交上的记录只能是 GateRelease 且不带活动（U4①）（§5.9"批准专用 PR"、T39） |
| C | sha256 evidence 无法做祖先判断；生成时间可倒填为未来 | GPT R3-3、git-8、对抗绕过-3 | 接受 | 本 PR 新增记录的 evidence 必须是 40 位 commit；`generatedAtTime` 晚于引入提交的 committer 时间 5 分钟以上 → 拒绝（核对轮 6 改为与检查时的当前 UTC 时间比，committer 时间可伪造）；规范 §6.6 与附录 C 注明 sha256 形式不能经合并进受保护分支（§5.9 检查项 3、§9、T38） |
| D | "被采用"口径与 approvalState 推导不一致，跨关口新记录可让旧关口记录不被检查 | GPT R3-4、对抗绕过-4 | 接受 | 查本 PR 新增的全部合法记录；唯一豁免：同一 PR 内被同关口、approves 为超集、时间更晚的新记录取代。不引用推导函数的 tie-break；approvalState 单值语义不变，跨关口覆盖的其余绕过由 U1 兜住（§5.9 检查项 2、§9、T38） |
| E | 已有批准记录可被改写或删除 | GPT R3-5、对抗绕过-1（原型副本实测 gate PASS） | 接受 | 所有 PR：PR 带进来的模型差异里，目标分支上已有的 ApprovalRecord、AgentActivity 出现 modified/removed → 拒绝，体现 ADR-009"批准只能新增"（§5.9 检查项 1、§9、T38） |
| F | 单数 merge-base 在交叉合并下有歧义 | GPT R3-6、git-4（实测交叉合并） | 接受 | "本 PR 新增" = PR 头上有、目标分支当前头上没有的主语；批准专用判定范围 = `git rev-list <PR头> ^<目标分支头>`，与 merge-base 个数无关（§5.9"口径"、T38） |
| G | CI 的 ref 口径未写死：测试合并提交、浅克隆 | git-3（实测） | 接受 | PR 头 = `pull_request.head.sha`；目标 = 当前 `refs/heads/<主分支>`；合并结果 = `refs/pull/N/merge` 或本地 `merge --no-ff`；完整克隆；git 命令非零退出一律判失败（§5.9"口径"、T38、附录 D） |
| H | 合并结果 gate 可能只对旧主线有效 | GPT R3-7、git-2、对抗绕过-5 | 接受 | 转设计会话，U3（§5.9"合并前重算"、§9 附录 C） |
| I | 发布批准把对旧 R 的批准套到主线新内容上 | GPT R3-8 | 接受 | 批准专用 PR 里每条新增记录：approves 对象在 `evidence..目标分支头` 的模型差异中不得为 modified/removed（核对轮 5 并入所有 PR 共用的检查项 7）（§5.9"批准专用 PR"、§9、T39） |
| J | Rejected 的发布批准也打 release 标签 | GPT R3-9 | 接受 | 只有 decision=Approved 的 GateRelease 才打、才检查 release 标签；Rejected 不得创建（§5.9"发布关口"第 3、4 步、§9、T40） |
| K | 标签可伪造、移动、预占，PR 失败后遗留 | GPT R3-10、对抗绕过-7、git-9（实测附注标签） | 部分接受 | 接受：名字须为 `release/{yyyymmdd}-{evidence 前 7 位}` 或 `release/v…`；按剥离到 commit 的值比较；~~PR 关闭未合并时工作台删除其新建的标签~~（核对轮 7 取消：不自动删，遗留标签由人清理，登记附录 C）；附录 C 登记 tag ruleset 保护（private 仓库需 GitHub Pro 及以上），未配置为残余风险。不采纳"合并后由可信流程原子创建标签"：增加新机制（§5.9"发布关口"、§9 附录 C、T40） |
| L | 分支名、标签名会冲突 | GPT R3-11、对抗绕过-10（实测） | 接受 | 批准分支名 `approval/release-{R 前 7 位}-{yyyymmddHHMMSS}`（UTC）；同名标签剥离后指向同一 R → 幂等复用，指向别的提交 → 报错由人处理（§5.9"发布关口"、T40） |
| M | evidence 可达性只是"可另加"的检查 | GPT R3-12 | 部分接受 | 必需检查已含"evidence 是 PR 头的祖先"；附录 C 增补管理员绕过、force push 后重开 PR 的风险，以及本仓库 `main` 当前无分支保护的事实（落实 Q5 须先配置）。定期巡检不加（§9 附录 C） |
| N | "标签让 R 不被 GC"论证错误，T40 的 GC 断言是空证 | git-5（实测）、对抗绕过-7④ | 接受 | 改为"标签是对外发布指针；R 的可达性由主线保证"；T40 改为可证伪形式：只在已合并分支侧的旧 evidence H1 在删分支 + `gc --prune=now` 后仍可达，squash 对照不可达（§5.9"发布关口"、T40） |
| O | GateRelease 的 evidence 可以不在主线上 | git-6、对抗绕过-8 | 接受 | 新增 GateRelease 记录的 evidence 必须是目标分支当前头的祖先，且只能出现在批准专用 PR（§5.9 检查项 3、T39） |
| P | 非发布关口可以批准主线旧提交 | git-7 | 接受 | 同 U4①（§5.9 第 1 步"主线提交的批准"、T40） |
| Q | 活动的 baseCommit、branch 可伪造 | 对抗绕过-9 | 接受 | CI 对新增活动重算 `merge-base(headCommit, 目标分支头)` 与 baseCommit 比较，`aisep:branch` 须等于 PR 源分支名（§5.9 检查项 4、§9、T38） |
| R | T38–T40 不足以证伪上述主张 | GPT R3-13 | 接受 | T38/T39/T40 补上列各簇的负例，修正 T40 的 GC 断言；新增 T43（§11） |

**设计会话拍板 U1–U4**（2026-11-20，四题均选推荐项；详见 §10.1 末四行与 ADR-015）

| 题 | 来源 | 结论 | 落点 |
|---|---|---|---|
| U1 旧批准漂移 | 对抗绕过-2、GPT R3-8 的一半 | **CI 拦截，不改元模型**：普通 PR 中被修改、在目标分支头上 Approved 的元素，同一 PR 里须有一条新增且通过逐条核对的合法批准覆盖它，否则拒绝合并；删除已批准元素按 Q6④ 一律拒绝（核对轮 1） | §5.9 第 10 步、检查项 6、§9、T38 |
| U2 governance.ttl 追加冲突 | git-1 | **一条记录一个文件**：新建 `models/<slug>/governance/<记录本地名>.ttl`，只提交这一个新路径；判据 (b) 改为只在一个模型的 `governance/` 下新增文件、不改不删已有文件；已有 `governance.ttl` 的记录与人员不搬迁 | §3.3、§5.1、§5.9、§9、T13、T21、T23、T26、T43、附录 D |
| U3 合并结果 gate | GPT R3-7、git-2、对抗绕过-5 | **合并前重算**：不开"要求分支最新"、不用合并队列；执行合并的人在 `gh pr merge` 前用同一脚本对当前目标分支头重跑，不过不合；绕过脚本点网页合并的残余风险登记附录 C；脚本未实现前为 GAP（2026-11-21 注：已实现，见附录 D） | §5.9"合并前重算"、§9 附录 C、T38、附录 D |
| U4 批准专用 PR 与主线提交批准 | GPT R3-1/R3-2、git-7、对抗绕过-6 | **两项都收紧**：① 主线提交上的批准只允许 GateRelease，其他关口 → `INVALID_ARGUMENT`（`mainline-head-gate-not-release`）；② 批准专用 PR 只免"再过 AISEP 关口"，仍须人工 PR 批准；信任模型维持 §4，不引入签名 | §5.9 第 1 步、"批准专用 PR"、§9、T39、T40 |

**落文时补的实现细节**（执行会话，未改结论）：

- "`目标分支头..PR 头` 的模型差异"（E、U1）按"合并结果相对目标分支头的源图差异"计算：直接比较两个头，主线在分叉后新增的记录会被误报为删除。
- 新建的记录文件是未跟踪文件，`git commit --only -- <路径>` 会报 pathspec 不匹配，须先 `git add`（临时仓库实测）；回滚与提交后撤回因此改为 `git rm --cached` + 按 sha256 删除文件（§5.9 第 7、8 步）。
- 矩阵所记"原型 `model_files` 的 glob 不含 governance/ 子目录"与实测不符：`glob(models/**/*.ttl, recursive=True)` 会匹配子目录。U2 的结论不受影响，附录 D 按实测写 GAP。（S5，PR #24 合入后附录 D 该行已改为 EXISTS。）
- C 的"所在提交"取 `目标分支头..PR 头` 中首个含该记录主语的提交；一条记录一个文件后，它就是新增该文件的提交。（核对轮 6 精确化为 `git rev-list --reverse --topo-order H ^T` 中第一个在其树中含该主语的提交；时间比较改为与检查时的当前时间比，它只用于报出 `offendingCommit`。）
- 按模型批准时，模型成员不含批准记录与 AI 活动（它们也带 `arch:inModel`，否则每条新批准都会让模型"被修改"）；ADR 的 `ad:relatedConcept` 指向的模型元素不展开（核对轮 3 落文时补）。

**核对轮（同模型）发现与处置**（2026-11-20，执行会话落文后；来源：Claude 可实现性 / 一致性 / 覆盖核对。8 条中 7 条接受并落文，第 1 条与已拍板的 Q6④ 冲突，暂缓、转设计会话）

| # | 发现 | 处置 | 落点 |
|---|---|---|---|
| 1 | U1 删除死锁：普通 PR 删除已批准元素须重批，但 `record_approval` 要求 `approves` 在 headCommit 上存在，删除永远批不了 | **按已拍板的 Q6④ 落文**：不放开删除。删除目标分支上已批准的元素在 CI 一律拒绝、提示退役；U1 只对修改要求重批（执行会话按 Q6④ 处理，未新增拍板） | §5.9 检查项 6、§9（§6.6）、规范 §6.6、ADR-015 |
| 2 | 可预先批准一个不存在的 IRI，之后再创建它，新内容未经评审即显示 Approved | 接受：检查项 3 要求 `approves` 每个 IRI 在 evidence 快照中存在；检查项 6 对 T 上推导为 Approved、T 源图中不存在、本 PR 新增的 IRI 同样要求重批 | §5.9 检查项 3、6，§9（§6.6），T38 |
| 3 | 模型、ADR 作 `approves` 对象时，I 规则与 U1 的"被修改"没有比较范围 | 接受：模型按全部成员（不含批准记录、AI 活动）及以成员为端点的限定关系判定；ADR 按其主语及直接引用的 Option、Force 等节点判定 | §5.9"口径"、检查项 6、7，§9（§6.6），T39 |
| 4 | U4① 可绕过：在发布批准分支的批准提交上补批 `GateArchitecture`，headCommit 不在主线上 | 接受：定义"有效内容提交"（沿第一父提交跳过批准提交），主线判定统一用它；`GateRelease` 的 headCommit 本身仍须在主线上 | §5.9 第 1 步、检查项 3、批准专用 PR 判定第 4 条，§9（§6.6、§8.3），T39 |
| 5 | 被批准内容与合入内容可以不同：普通 PR 批准后主线改了同一对象，合并结果里的对象未经评审 | 接受：所有 PR 的新增记录，`approves` 对象在 evidence 快照与合并结果中的源图三元组必须相同；第三轮 I 并入此条。后果：主线改了同一对象时须基于新主线重开分支再批 | §5.9 检查项 7 与"批准专用 PR"，§9（§6.6），T38、T39 |
| 6 | 判据不够精确：committer 时间可伪造；"引入该记录的提交"未定义；判据 (a)(b) 不限文件类型、个数与模式 | 接受：未来时间与检查时的当前 UTC 时间比；引入提交按 `rev-list --reverse --topo-order H ^T` 定义；(a)(b)(c) 改为恰好一个 `.ttl` 普通文件、恰好一条记录（可带至多一条被引用的活动）、恰好一个 trailer | §5.9 第 1 步、"口径"、检查项 3，§9（§6.6、§8.3），T23、T38、T39 |
| 7 | 第三轮 K 的"PR 关闭未合并时工作台删除其新建的标签" | 接受：取消自动删除，附录 C 登记"遗留 release 标签由人清理" | §5.9"发布关口"第 3、5 步，§9 附录 C，T40 |
| 8 | 一致性：a) 关口模板与提示词仍写"写入 `governance.ttl`"；b) 输入表 `branch` 行"（发布关口等）"与 U4① 不符；c) §10.1 R2-15 行"只跑 gate"未注明已被 U4② 收紧；d) 存档表 Q3 行未注明判据 (b) 已被 U2 改；e) §6.6"已在主分支上的提交"段未写明这类记录只能经批准专用合并请求合入 | 接受，逐项改 | `docs/adm/governance/template.md`、`prompt.md`，§5.9 输入表，§10.1，§9（§6.6） |

### 第四轮（2026-11-20，第三轮修订后）

范围：只评第三轮修订本身（PR #4 的 5 个文件，含 §5.9、§10.1 U1–U4、§11 T38–T40/T43、附录 D、规范 §6.6/§8.3/附录 C、ADR-015）。评审：GPT `gpt-5.6-sol-high`（cursor-agent 只读，R4-1..14）；Grok `grok-4.7-high` 红队（只读，排除 GPT 已报，G4-1..7）。核实：每条由两个独立视角（文档对照、临时仓库可执行探针）各判一次，默认怀疑。结果：21 条无一被判不成立；多数严重度下调（门槛是绕过 MCP 手写记录，或是失败关闭的误杀）。

| # | 问题 | 核实（文档 / 探针） | 处置 | 落点 |
|---|---|---|---|---|
| R4-1 | 普通 PR 不带任何批准记录能过全部检查项，与治理模板"没有批准记录的变更不进主分支"矛盾 | 部分成立 medium / 成立 high（实测 gate PASS） | **用户拍板：允许 Proposed 进主线**（维持 Q2=A）。改模板；检查项前写明普通 PR 不要求记录；"主线 Proposed 补批须先有内容提交"登记附录 C 为已知限制 | §5.9 检查项前、governance/template.md 第 5 节、附录 C、T38 正例、ADR-016 |
| R4-2 | U1 覆盖记录不限 decision 与关口 | 部分成立 low / low | **用户拍板：只认 Approved**；关口不限（"须原关口"无依据，不采纳） | 检查项 6、§9（§6.6）、§10.1 U1、T38、ADR-016 |
| R4-3 | 覆盖记录可回填到旧批准之前，合并后旧批准仍生效 | 成立 medium / high | 接受：检查项 6 在 M 上核对生效记录须为覆盖记录 | 检查项 6、§9（§6.6）、T38 |
| R4-4 | CI 不在 evidence 上重跑 gate，手写 Approved 可批准 gate FAIL 的版本 | 部分成立 / 成立 medium | 接受：检查项 3 对 Approved 记录在 evidence 上跑 `model_gate` | 检查项 3、§9（§6.6）、T38 |
| R4-5 | `approves` 目标类型未校验 | 成立 / 部分成立 medium | **用户拍板：元素（不含 ApprovalRecord、AgentActivity、Stakeholder）+ 模型 + ADR**；关系、视图不可批准 | §5.9 输入表、规范 §6.6、附录 D GAP、T38、ADR-016 |
| R4-6 | 模型比较范围缺模型主语自身 | 成立 medium | 接受 | "对象的比较范围"、§9（§6.6）、T38 |
| R4-7 | 同一天同一 R 同一关口跨分支批准同名 | 部分成立 medium | **用户拍板：只加秒级时间**；同一秒并发撞名登记残余 | §5.9 第 5 步、§6.1 表、§9（§3）、规范 §3、template.md、T43、ADR-016 |
| R4-8 | 新文件可复制已有记录，图差异看不出 | 部分成立 low | 接受：判据直接解析新文件形状 | §5.9 第 1 步、§9（§6.6）、附录 D GAP、T23 |
| R4-9 | 手写流程缺 trailer 与单文件要求，模板允许 sha256 | 成立 medium | 接受：补手工提交配方，evidence 只用 40 位 commit | governance/prompt.md、template.md |
| R4-10 | CI 的 M 取 `refs/pull/N/merge`，可能基于旧 T | 部分成立 low / medium | 接受：M 一律在本次 T 上本地生成 | "口径"、T38 |
| R4-11 | 重算与合并非原子 | 成立 / 部分成立 medium | 接受：合并串行、`--match-head-commit`、合并前再比对、合并后核验父提交；余下登记残余 | "合并前重算"、§9 附录 C、T38 |
| R4-12 | 附录 D 写"检查项 1–6" | 部分成立 low | 接受 | 附录 D |
| R4-13 | §10.1 U4 行未按有效内容提交判定 | 部分成立 / 成立 low | 接受：U4 行与 ADR-015 补注 | §10.1、ADR-015 |
| R4-14 | ADR-015 后果仍写"无分支保护、标签未保护" | 部分成立 / 成立 low | 接受：更新为现状 | ADR-015 |
| G4-1 | 豁免的"更晚"未写时区归一化 | 成立 / 部分成立 medium | 接受：凡比较 generatedAtTime 一律归一化 | "口径"、§9（§6.6）、规范 §6.6 推导、T38 |
| G4-2 | 检查项 6 对 removed 允许覆盖，与第 10 步矛盾 | 成立 / 部分成立 medium | 接受：removed 一律拒绝（核对轮 1 漏改） | 检查项 6、T38 |
| G4-3 | 豁免与"普通 PR 不能把主线合进分支"矛盾 | 部分成立 low / 成立 medium | 接受：改散文，合并后以合并提交为 evidence 重批可通过 | 检查项 3、7，T38 |
| G4-4 | 只改关系端点不触发对端点元素的重批 | 部分成立 medium / low | **用户拍板：不算元素修改**，写明口径、登记附录 C、T38 正例固定 | "对象的比较范围"、附录 C、T38、ADR-016 |
| G4-5 | `branch` 存短名还是完整 ref 未定，完整 ref 会被检查项 4 误杀 | 成立 / 部分成立 medium | 接受：只收短名（同 §5.8 第 0 步） | §5.9 输入表、活动表、规范 §6.7、T38 |
| G4-6 | 主线合入本分支祖先后活动 baseCommit 重算不等，无出路 | 成立 medium | 接受（按推荐 A）：只核对被选出记录引用的活动，被取代记录的活动不重算 | 检查项 4、T38 |
| G4-7 | 附录 D 仍写 CI 浅克隆 | 成立 low | 接受：更新现状 | 附录 D |

反驳：0 条。未采纳的建议：R4-2"须原关口重批"、R4-1 评审原改法"至少一条 Approved"、G4-4 评审原改法（扩元素比较范围）、R4-7 随机量。
<!-- END-MOVED 附：评审与辩论记录 -->

<!-- BEGIN-MOVED 附：设计会话拍板记录 -->
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
- ③ R2-15：标签名 `release/{yyyymmdd}-{短hash}` 或版本号，避免同日重名；标签同时让被发布的提交不被 GC（第三轮 N 更正：R 的可达性由主线保证，标签只是对外发布指针）。
- 落文时补的实现细节（未改结论）：CI 只查本 PR 新增、且推导 approvalState 时被采用的记录（被同关口同对象的新记录取代的旧记录不查，否则重新过关口后 PR 永远过不了）；`branch` 不再接受主分支，原 R2-15 的本地与远端同步校验取消；`GateRelease` 的 headCommit 必须在主分支上；带 activity 的拒绝沿用 `INVALID_ARGUMENT`；标签由工作台创建推送，CI 检查。以上未经异构评审。（第三轮已评审："只查被采用的记录"改为查全部合法新记录（D），标签检查按剥离到 commit 的值比较（K），见"第三轮"。）
- ④ 用户 2026-11-20 确认保留：批准后把主分支合回功能分支，会在 `evidence..分支头` 中引入非批准提交（合并提交），按同一判据批准失效，须重新过关口。这是规则的直接结果，接受其日常操作成本。
<!-- END-MOVED 附：设计会话拍板记录 -->

<!-- BEGIN-MOVED 附：合并记录 -->
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
<!-- END-MOVED 附：合并记录 -->
