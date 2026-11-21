# MCP 接口设计：实现镜像与规范改文（历史）

本文件的内容从 `docs/mcp-interface.md` 原样移来（L6-P2），`BEGIN-MOVED` / `END-MOVED` 标记之间逐字未改。

- §3.1（实现语言与复用原型）、§11（验收表）、附录 D（追溯表）是实现镜像，**以代码与测试为准**。
- §9 是当时提交的规范改文，现行条文以 `docs/metamodel-spec.md` 为准。

文中提到的 §3.1、§9、§11、附录 D 在本文件内；文首事实表（F1–F19）、§10、附录 A、附录 B 与文末各「附」在 [`mcp-interface-records.md`](mcp-interface-records.md)；其余节号指 `docs/mcp-interface.md`。

<!-- BEGIN-MOVED §3.1 -->
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
<!-- END-MOVED §3.1 -->

<!-- BEGIN-MOVED §9 -->
## 9. 需要改动的规范条文（可直接替换）

> 设计会话 2026-11-20 已拍板 Q1–Q6（§10.1），下列改文按拍板结果写，每条仍标出出处是哪一问。偏离规范字面的 8 项（写工具不提交、批准要求 gate PASS、BPMN 成员摘除、受保护资源、不收调用方的 evidence/baseCommit、新增 IRI 规则、写前只拒新增违规、新增 `model.gate`）按 Q6=A 整体接受，附两个条件：条件一 `model.diff` 可比较工作区未提交改动（下文 §8.3、附录 C、ADR-013 三处改文），条件二遗留违规由 `model.findings` 的 openViolations 给出（下文 §8.3）。另有一项不在这 8 项里、由用户在另一会话单独拍板的扩展：新增 `model.set_labels`（下文 §3、§8.3 两处）。第三轮评审后的设计会话拍板 U1–U4（§10.1）落在下文 §6.6（两段修订与新增"文件"一条）、§8.3 `governance.record_approval` 一行、附录 C 与 `docs/decisions.md`（ADR-015），各条标"第三轮"。

**§0 状态行**，把"AgentActivity 与两个 MCP 工具在 MCP 接口设计时一并定稿"替换为：

> AgentActivity 与 `model.diff`、`governance.record_approval` 已在《MCP Server 接口设计》中定稿（ADR-014）。

**§3 表格**，"批准记录"一行替换为（第四轮 R4-7，ADR-016）：

> | 批准记录 | `{model}approval-{yyyymmddHHMMSS}-{slug}`（UTC；2026-11-20 前的存量记录按 `{yyyymmdd}` 命名，不改） | `…/procurement/approval-20261119-arch-baseline` |

**§3 表格**，在"批准记录"一行之后新增（前提 Q6）：

> | AI 活动 | `{model}activity-{yyyymmddHHMMSS}-{headCommit 前 7 位}`（UTC），重名时加 `-2` | `…/procurement/activity-20261120093015-9c41e07` |

**§3 表格"关系"一行**，在格式后补一句（前提 Q6）：

> 直连谓词本地名取关系类最近的 `arch:unqualifiedForm`；类没有声明时取类本地名，首字母小写。

**§3 列表末尾**，加一条：

> - 现有手写 IRI 不按本表重命名（slug 一经创建不改）；本表只约束写入层新生成的 IRI。

**§3 列表"slug 用可读英文 camelCase……改名只改标签"一条**，在"改名只改标签"之后补（`model.set_labels`，另一会话拍板）：

> 改标签经 `model.set_labels` 写入（§8.3）。

**§6.6**，`aisep:approves` 一条替换为（第四轮 R4-5、G4-4，ADR-016）：

>   - `aisep:approves` → 一个或多个元素、模型或 ADR。允许集合：带 `arch:inModel` 的元素（不含 `aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Stakeholder`）、`arch:Model` 实例、ADR（`ad:Decision`）；限定关系和视图不可被批准，它们的改动只计入所属模型、不计入端点元素。目标存在但类型不在集合内的记录不合法（L1 报错，不参与推导；ADR-016）；目标不存在的按原口径处理（不因此报 L1）；

**§6.6**，"`arch:approvalState` 由构建推导"一条中"取最近一条**合法**批准记录的结论"改为（第四轮 G4-1）：

> 取（按时区归一化，不带时区的按 UTC）最近一条**合法**批准记录的结论

**§6.6**，`aisep:approvedBy` 一条替换为（Q4=C）：

> - `aisep:approvedBy` → 人（必须是 `arch:Stakeholder` 的实例，且不能是 `aisep:AIAgent`；AI 不能批准，原则五）；

**§6.6**，`aisep:evidence` 一条的最后一句"经 MCP 写入时自动填写。"替换为（前提 Q3、Q6；第三轮 A、U2 修订；核对轮 6 修订）：

> 经 MCP 写入时自动填写：取调用方给出的 headCommit（人评审的那个提交；有活动时等于该活动的 `aisep:headCommit`），写入层核对它与分支头之间只有批准提交：其间不得有合并提交，每个提交都恰好带一个值等于所新增记录 evidence 的 `AISEP-Evidence` trailer、恰好新增一个 `models/<slug>/governance/` 下的 `.ttl` 普通文件（不进子目录，不修改、不删除已有文件）、且源图只新增一条批准记录（可另带一条被它引用的 AI 活动；无修改、无删除）；该核对在提交前持锁复做一次，提交后父提交不是被核对的分支头时撤回。写入前在该提交上运行 `gate`，结论为 Approved 而 gate 未通过时拒绝写入。

**§6.6**，`aisep:evidence` 一条之后新增两段（R2-13、R2-15；2026-11-20 第三轮按 U1–U4 与 A–Q 修订，核对轮按 2–6、8e 修订；第四轮按 R4-2/3/4/6/8、G4-1 修订，ADR-016）：

> 批准提交判据：一个提交只有一个父提交，恰好带一个 `AISEP-Evidence` trailer 且其值等于该提交新增记录的 evidence，相对父提交恰好新增一个文件（路径为 `models/<slug>/governance/<文件名>.ttl`，不在子目录，文件模式 100644），不修改、不删除已有文件，且相对父提交源图只新增一条批准记录，另可带至多一条被它引用的 AI 活动（无修改、无删除）；新文件里只能有这条记录及其活动，文件名等于记录 IRI 的本地名。批准记录的 evidence（有活动时即活动的 headCommit）到所在分支头之间只允许出现满足该判据的提交；evidence 等于分支头是其特例。写入时由写入层核对；合并进受保护分支前由 CI 用同一判据再核对一次（范围 `evidence..分支头`，不含合并提交本身），查本次合并新增的全部合法记录（同一合并请求内被同关口、`approves` 为其超集、时间（按时区归一化）更晚的新记录取代的除外）。合并时另要求：新记录的 evidence 必须是 40 位 commit，结论为 Approved 的新记录在 evidence 上运行 `gate` 须通过，生成时间不得晚于检查时的当前时间 5 分钟以上（不与可伪造的提交时间比）；被批准对象必须在 evidence 中存在，且其内容（模型按它自身、全部成员及以成员为端点的关系，ADR 按它及其直接引用的组成节点）在 evidence 与合并结果中必须相同；目标分支上已有的批准记录和 AI 活动不得修改或删除；修改目标分支上已批准的元素，或新增目标分支上已显示为批准但尚不存在的元素，须在同一合并请求里有新的、结论为 Approved 的合法批准记录覆盖（关口不限），且它须是该对象在合并结果中生效的那条记录；删除目标分支上已批准的元素一律拒绝（被批准过的元素只能退役，Q6④）；新增 AI 活动的 baseCommit、branch 须与按目标分支重算的值一致；在合并结果上运行 `gate`。任一不通过即拒绝合并，须在新的提交上重新过关口。CI 通过后目标分支可能前进，执行合并的人在合并前用同一检查对当前目标分支头重算，不过不合。只含批准提交、至少新增一条批准记录、且新增的 AI 活动都被新记录引用的合并请求不要求再过关口，上述核对、`gate` 与人工合并批准照常；夹带其他提交的按普通合并请求处理。
>
> 已在主分支上的提交只能批准发布关口，其他关口拒绝；判断时从被批准的提交沿第一父提交回溯、跳过批准提交，取得到的第一个提交（有效内容提交）。这类批准不直接提交到主分支：从被批准的那个提交拉短命分支，只提交这一条批准记录，经合并请求合入后删分支；这类记录只能经只含批准提交的合并请求合入，夹带其他提交的合并请求中出现即拒绝。这类批准不带 AI 活动；evidence 是被发布的主分支提交，必须是目标分支头的祖先，被批准对象在 evidence 到目标分支当前头之间不得被修改或删除（内容已变须重新选被发布的提交）。只有结论为 Approved 时被发布的提交才打 `release/{yyyymmdd}-{前 7 位}` 标签（或版本号标签 `release/v…`），Rejected 不打；标签是对外的发布指针，被发布提交的可达性由主线保证。

**§6.6**，`aisep:activity` 一条之后新增（第三轮 U2）：

> - 文件：每条批准记录单独一个文件 `models/<slug>/governance/<记录本地名>.ttl`（同次写入的 AI 活动在同一文件）；批准只新增文件，不改已有文件。早先写在 `governance.ttl` 里的记录与人员不搬迁，`governance.ttl` 仍放 `arch:Stakeholder` 等治理类元素。

**§6.7**，`aisep:AgentActivity` 整条替换为（前提 Q4；IRI 与唯一键前提 Q6）：

> - `aisep:AIAgent` ⊑ `arch:Element`、`prov:SoftwareAgent`（aisep-core 另声明 `prov:SoftwareAgent ⊑ prov:Agent`；不加载 PROV-O 本体）：执行任务的 AI 代理，按元素通则写名称和 `arch:inModel`。
> - `aisep:AgentActivity` ⊑ `arch:Element`、`prov:Activity`（ADR-013、ADR-014）：一次**已完成**的 AI 活动。只在任务过关口时由 `governance.record_approval` 写入，与批准记录在同一次提交里；进行中的状态不进模型仓库。一个（sessionRef, headCommit, branch）只有一条，同一 head 过多个关口时复用；IRI 见 §3。字段：
>   - `skos:prefLabel` 恰好一个 `@zh`（缺省"AI 活动：{分支}"，建议写任务标题），`arch:inModel` 恰好一个；
>   - `prov:wasAssociatedWith` → 执行的代理，恰好一个，必须是 `arch:Stakeholder` 或 `aisep:AIAgent` 的实例；
>   - `prov:startedAtTime`、`prov:endedAtTime`，各恰好一个 xsd:dateTime，开始不晚于结束（按时区归一化，不带时区的按 UTC）；
>   - `aisep:sessionRef`：外部编排器的会话标识，非空字符串，恰好一个；对元模型不透明，不绑定 AO；
>   - `aisep:branch`：分支短名（不含 `refs/heads/`），非空字符串，恰好一个；
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

- `governance.record_approval` 一行替换为（第三轮 A、U2、U4① 修订）：

> | `governance.record_approval` | 新增一条批准记录（不改状态字段）。顶层必填 branch、headCommit（有无活动都必填）；可选 expectedBaseCommit，只用于核对、不写入（不等于被拒收的 baseCommit）。写入层核对 headCommit 与分支头之间只有批准提交（无合并提交；每个提交恰好带一个值等于记录 evidence 的 `AISEP-Evidence` trailer、恰好新增一个 governance 目录下的 `.ttl` 普通文件、源图只新增一条批准记录（可另带一条它引用的 AI 活动）），提交前持锁复核。branch 不能是主分支；headCommit 已在主分支上（按有效内容提交判定，§6.6）时只接受发布关口、不接受活动信息；发布关口的 headCommit 必须在主分支上。可选活动信息只含代理、sessionRef、起止时间和标签：写入层算出 baseCommit，在同一次提交里写入 `aisep:AgentActivity`（分支、headCommit 取顶层值）并用 `aisep:activity` 关联；evidence 取调用方给出的 headCommit，generatedAtTime、baseCommit 由写入层填，不接受调用方传入 evidence、generatedAtTime、baseCommit。Approved 要求 evidence 处 gate 通过。每条记录新建一个 `governance/<记录本地名>.ttl`，只提交这一个路径，不跳过 pre-commit | L0–L2 + gate |

- `model.findings` 一行替换为（Q6 条件二）：

> | `model.findings` | L4；另返回 openViolations：同一份内容上 L0–L2 的全部违规（结构化发现项），供查看写入时被放过的遗留违规。openViolations 不新增层级，不计入 gate 结论 | L4（openViolations 复用 L0–L2） |

- `model.diff` 一行**整行替换**为（Q6 条件一；原文"只读 Git 对象"与 worktree 模式冲突，不能只在末尾追加）：

> | `model.diff` | 只读。base 是 Git 引用（不给时取 head 侧 commit 与模型主分支的 merge-base）；head 有两种：Git 引用，或某分支检出的工作区（按分支名经 `git worktree list` 定位，只接受分支名，不接受路径）。工作区内容 = 该工作区模型目录下已跟踪 Turtle 文件的当前内容 + 未跟踪且未被忽略的新 Turtle 文件 − 已在工作区删除的文件。返回新增、修改、删除的元素和关系清单（按 IRI；同一 IRI 的三元组有变化算修改；改关系类型按 §8.2 表现为删除加新增）。比较的是两边模型源文件的并集图（构建前）；三元组在文件间移动、排版和注释变化不算修改。多个 merge-base 时报错，要求显式给 base。结果按 kind（element / relationship / view / governance / schema / other）分组计数；detail 取 summary / items / triples；标明 head 的种类、对应 commit 和工作区是否有未提交改动。工作区里某个文件解析失败时，结果标为不完整并列出失败文件，其余照常比较，失败文件里的主语不判为删除。无状态，不写任何东西，可从任意 worktree 调用 | L0 |

- 表后段落"`model.diff` 同时服务两处：……v1 只比较已提交内容；前提是……（见附录 C）。"一句中，把"v1 只比较已提交内容；"替换为：

> "AI 进行中"缺省比较会话分支的工作区（含未提交改动），关口页差异图和批准只认已提交的 commit；

- 表后"接口的具体设计另写文档。"替换为：

> 接口的具体设计见《MCP Server 接口设计》（`docs/mcp-interface.md`）。线上工具名把点换成下划线（`model.diff` → `model_diff`）。写工具只改工作区、不提交；`governance.record_approval` 例外，自己做一次只含 governance 文件的提交。

**附录 C**（第三轮修订：Q5 一条补可达性风险与分支保护现状，CI 一条补合并前重算与残余风险，新增 sha256 evidence、release 标签保护两条，`record_approval` 崩溃一条改为记录文件；核对轮新增遗留 release 标签一条；第四轮：CI 一条补重算与合并非原子，新增主线 Proposed 补批限制、关系端点不触发元素重批两条，ADR-016）：
- 第 1 条"`model.diff` v1 只比较已提交内容：进行中的会话在提交前，"改动元素"一栏为空或滞后。"**删除**（Q6 条件一：worktree 模式取消了这条限制）。在原位置改写为：

> - `model.diff` 的 worktree 模式读的是会话分支检出的工作区：会话的工作区已被清理（只剩分支）时退回只比较已提交内容；工作区里写到一半的文件会让结果标为不完整（失败文件里的主语不计）。index（暂存区）与磁盘不同时以磁盘为准。

- 第 2 条（同仓同分支的前提）**保留不动**。
- "`rm` 级联删除（§8.2）没有原型化"一项删去 `rm` 部分（实现后）。
- PROV-O 一条替换为（Q4=C）：

> - PROV-O 不整体加载；aisep-core 只声明 `aisep:AIAgent`，另在其对齐文件里加 `prov:SoftwareAgent ⊑ prov:Agent` 一条（ADR-010），其余 PROV-O 术语不可用，G7 白名单不变。

- 新增：

> - 历史批准的差异图和 gate 重跑依赖 headCommit 仍可达。模型仓库禁用 squash 合并和 rebase 合并，批准提交只经普通 merge 进受保护分支（ADR-014）；落实要同时做到：托管平台关闭 squash、rebase 两种 PR 合并方式，受保护分支禁止 force push、限制直接 push，PR 合并保留原提交（cherry-pick、rebase 都会生成新的 commit id）。这些是仓库托管平台的设置，元模型和 MCP 不检查；合并时校验已要求新记录的 evidence 是合并请求头的祖先（发布批准还须是目标分支头的祖先）。绕过它合入、或分支未合并就删除时，旧 commit 可能被 GC，历史批准无法重跑；管理员绕过分支保护、force push 后重开合并请求，同样可能让已合入记录的 evidence 不再可达。本仓库已于 2026-11-20 配置：只允许普通合并（关闭 squash、rebase），`main` 受保护（必需检查 `gate`、`mergecheck`、`pytest`，不要求分支最新、禁止 force push 与删除、管理员同样受约束）；未要求平台上的 PR 评审批准（个人仓库没有第二人评审）。合并条件见 AGENTS.md「分支与合并」第 2 条：必需检查通过，且由没参与实现的 agent 独立评审通过。
> - 合并时校验（evidence 到分支头之间只有批准提交、已有记录不可改、已批准元素改动须重批、合并结果 gate 等）、批准专用合并请求的判定、发布标签检查由 CI 的 `mergecheck` 执行（脚本 `aisep/mergecheck.py`），本仓库已把它设为受保护分支的必需检查；元模型和 MCP 不检查 CI 是否配上。不开"要求分支最新"、不用合并队列（个人账号的 private 仓库用不了合并队列），目标分支前进后必需检查不会自动重跑，所以合并前由执行合并的人用同一检查对当前目标分支头重算；绕过它直接在网页上点合并时，合并结果 gate 可能只对旧主线有效，这是残余风险。重算与合并之间也没有原子绑定：平台合并只能锁合并请求头、锁不了目标分支头，重算通过后目标分支仍可能前进；由合并串行、合并前再比对目标分支头、合并后核验父提交并在不过时回滚来压缩，余下为残余风险。重算、复核、合并后核验三步已写进 AGENTS.md 的合并条款（ADR-017），但只靠执行合并的人照做，没有机制强制；第四轮负例（`test_merge_check_negatives.py`）不在 CI 里，涉及 mergecheck 的合并请求是否在本地跑过，同样只靠执行合并的人核对。
> - 普通合并请求不要求带批准记录，未经批准的模型改动可以进主分支（推导为 Proposed，ADR-016）。主线提交只能批准发布关口，所以主线上的 Proposed 元素要过其他关口，须从主分支拉分支、先有一个非批准提交（可以是空提交）再批；这是已拍板规则组合（ADR-015 U4①、ADR-016）的已知限制。
> - 元素级批准不覆盖以它为端点的限定关系：合并请求只改一条关系的端点（如换掉 target）时，被连接的已批准元素不须重批，合并后仍显示 Approved。要约束连接，须按模型批准（模型的比较范围含以成员为端点的关系）。这是有意的口径（第四轮 G4-4，用户拍板），否则每加一条代码追溯都会触发对设计元素的重批。
> - 视图从属不计入元素：`arch:inView` 三元组计入视图、不计入元素（与接口文档 §5.8 一致），所以合并请求只改已批准元素的 `arch:inView`（把它放进或移出某张视图）时，该元素不须重批。视图不可被批准（R4-5）：视图属于某个已批准模型时，模型的比较范围能看到这个改动；视图在其他模型里时，没有检查项能看到。这是有意的口径（第四轮复评 R3，Albert 2026-11-21 拍板，ADR-017）。
> - 进入受保护分支的批准记录 evidence 只能是 40 位 commit：`sha256:<64 位十六进制>` 形式 L1 合法，但合并时校验判断不了它与分支的祖先关系，一律拒绝；它只适用于不经合并进受保护分支的场合。
> - `release/*` 标签由托管平台的 tag ruleset 禁止删除与移动（本仓库 2026-11-20 已配置规则集 `release-tags-immutable`：规则 deletion、update、non_fast_forward，无绕过者，管理员同样受约束；探针实测创建可以、强推移动与删除均被 GH013 拒绝）。规则集被停用或修改时，标签可被移动、删除，发布标签检查又只在合并时看一次，此时为残余风险。
> - 发布批准的合并请求关闭未合并时，已推送的 `release/*` 标签不自动删除，由人清理；清理前它指向一个未合入主线的发布批准。因规则集禁止删除，清理须由仓库管理员临时停用规则集、删标签、再启用；规则集不设绕过者，是为了不让与人共用账号凭据的 AI 也能绕过。
> - 写入层对工作区文件的"写前哈希核对"不是真正的比较并交换：不遵守写锁的外部编辑器或 Git 命令在核对与替换之间（毫秒级）写入的内容会被覆盖。
> - `model.remove` 只检查本仓库：独立模型仓库里指向被删元素的引用看不到，删除后会在那边悬空。
> - `governance.record_approval` 在"新建记录文件"与"提交完成"之间被杀，会留下未提交的记录文件；下次调用以 DIRTY_WORKTREE 报出，需人工清理。多文件写入同样不是崩溃原子的，由 gate 兜底。
> - `model.remove` 对 BPMN 成员属性以外的引用一律拒绝，放开需要逐条进规范。布局文件出现前，删除不处理布局。

**§13**，删去"不在第一批范围"里的"MCP 接口的具体设计（另写文档）"一项：ADR-008 已定一期交付物是 MCP Server，本文就是它的接口设计。

**`docs/decisions.md`**：新增 ADR-014「MCP Server 接口定稿」，记录第 10 节的拍板结果（Q1–Q6 及 Q6 的两个条件、新增 `model.set_labels`、Q5 的禁用 squash/rebase 合并、R2-13 的合并时校验、R2-15 的短命批准分支与发布标签）。第三轮（2026-11-20）另新增 ADR-015「第三轮评审拍板：批准记录分文件、合并前重算、批准专用 PR 收紧、改动已批准元素须重批」，记录 U1–U4；ADR-014 不改。

**ADR-013 的修订文字**（Q6 条件一。设计会话口述为"ADR-010"，核对后"v1 只比较已提交内容"实际写在 **ADR-013** 的"后果"一条和规范附录 C 第 1 条，ADR-010 讲的是对齐文件，与此无关；按 ADR-013 改）：

- "状态"一条中"元模型与 MCP 部分为草案，与 MCP 接口设计一并定稿"替换为：

> 元模型与 MCP 部分已由 ADR-014 定稿；2026-11-20 设计会话拍板时修订"后果"中的 diff 限制（见下）

- "后果"一条末尾"已知限制：v1 只比较已提交内容，且要求模型与代码同仓同分支（规范附录 C）。"替换为：

> 已知限制：要求模型与代码同仓同分支（规范附录 C）。（2026-11-20 修订：原"v1 只比较已提交内容"撤销。MCP 写工具只改工作区不提交，只比已提交内容会让"AI 进行中"在批准前一直为空；`model.diff` 改为也能比较会话分支检出的工作区，按分支名定位、不接受路径，"AI 进行中"缺省用这一模式；关口页差异图和批准仍只认已提交的 commit。）

- "决策"一条不改：改动元素仍由分支差异实时算出、起点仍为 merge-base，worktree 模式只是把 head 侧从"分支头 commit"扩展到"分支的工作区"，不新增状态、不新增上报写工具。

**`docs/module-contract.md`**：AgentActivity 一条去掉"draft"；`impact` 一行补"未知元素退出码 1"（若采纳 §3.1 的建议）。
<!-- END-MOVED §9 -->

<!-- BEGIN-MOVED §11 -->
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
| T13 | 写并发 | 两个服务器进程同时写同一 worktree：一个成功、一个 `LOCKED`；写入中途外部改文件 → `CONFLICT`，文件保持外部内容；第二个文件 rename 失败时两个文件都恢复原字节；在两次 rename 之间注入 SIGKILL：工作区停在部分写入，随后 `model_gate` 判 FAIL（证明 gate 兜底）；工作台对 worktree A 批准时代理进程同时对 A 的 governance.ttl 写入（如加 Stakeholder）→ 一方 `LOCKED`，批准提交只含新建的记录文件、不含 governance.ttl；在哈希核对之后、`rename` 之前注入一次不加锁的外部写入 → 外部内容被覆盖（证明附录 C 的已知限制如实）；`models/<slug>` 被换成指向外部目录的符号链接、`file` 指向其中 → `PATH_OUTSIDE_ROOT`，外部目录无新文件 |
| T14 | diff：merge-base 起点 | 分叉后主分支新增元素 X、分支新增 Y：`diff(head=branch)` 只有 Y，**没有** X 被删除；本地 `main` 落后于 `origin/main`、分支从 `origin/main` 切出：结果只含分支自己的改动，`base.mainRef` = `refs/remotes/origin/main` |
| T15 | diff：语义 | 夹具分支各一例：新增元素；只改 prefLabel → modified 且 `changedPredicates` 只有 prefLabel；按 §8.2 改关系类型 → 1 删 1 增；只改 `rdf:type` → `typeChanged`；元素块搬到别的文件 → 不在增删改里、出现在 `moves`；只改注释或前缀 → 全 0；只把元素加进视图 → `element.modified=0`、`view.modified=1`；模型内自定义视图子类的实例 → kind=view；成环、共享、无人引用的空白节点各一例 → `DIFF_BNODE_UNSUPPORTED`；树形空白节点内改一个值 → 引用方 modified |
| T16 | diff（Git 引用模式）：只看已提交、不碰工作区、可跨 worktree | `head` 为字符串时，工作区未提交改动不影响结果；从 `git worktree add` 的另一目录调用结果相同；前后 `git status --porcelain` 不变 |
| T17 | 级联删除 | `remove(quoteApproval)` → `REFERENCED`，blockers 含 `approval-20261119-arch-baseline`；`remove(quotation)` → `CASCADE_REQUIRED`，计划 3 条关系；`remove(bpmnReview, cascade)` 删 `sf1`、`sf2`、摘除 `flowElements`，之后 gate PASS；`remove(approval-…)` → `PROTECTED_RESOURCE`；双模型夹具：模型 B 里有一条以 T 为端点的**关系资源**（不只是普通谓词）→ `REFERENCED`，blocker `reason=cross-model-relationship`，B 的文件 sha256 不变；关系指向关系的夹具两条都进 `delete`；用构建图会被拒的 `quoteApproval` 端点关系（派生直连谓词）不出现在 blockers 里 |
| T18 | 删除确定性 | 同一 dryRun 跑 10 次结果相同；dryRun 后改文件，带旧 `planDigest` 实删 → `PLAN_STALE`；实删成功后用同一 `planDigest` 重放 → 成功、`alreadyAbsent:true`；不带 `planDigest` 删不存在的 IRI → `ELEMENT_NOT_FOUND` |
| T19 | diff 快速路径 | 只改代码的分支：全 0，且解析器调用计数为 0；两边都没有 `models/` → 两个 `*HasModels` 均为 false、全 0；head 删掉整个 `models/` → 全部 `removed`；带 ref 读取缺 `modules/` 的提交 → `MODULES_NOT_IN_REF` |
| T20 | diff 错误 | 不存在的分支 → `REF_NOT_FOUND`；ref = `--output=/tmp/x` → `INVALID_ARGUMENT` 且该文件未被创建；构造两个 merge-base → `AMBIGUOUS_MERGE_BASE` 带候选；`record_approval` 的 `branch` 传标签、`origin/x`、`x~1` → `INVALID_ARGUMENT` |
| T21 | 批准原子性与字段 | 一次调用恰好 1 个新提交，只新增一个 `models/<slug>/governance/<记录本地名>.ttl`（`git show --name-status` 恰一行 `A`），文件名等于记录 IRI 的本地名，已有 `governance.ttl` 字节不变；含记录和活动两个新主语；`evidence == activity.headCommit`；`baseCommit == git merge-base`；trailer 正确且值等于记录 evidence；构建后被批元素 approvalState = Approved，等于返回的 `derivedApprovalState.after` |
| T22 | 批准不污染元素差异 | 批准后同一分支 `diff(summary)` 的 `changedElementCount` 不变，`counts.governance.added` +2 |
| T23 | 分支头校验 | headCommit 之后又有代码提交 → `STALE_HEAD`，无新提交；之后有一个只在 `governance/` 下新增文件、但文件里新增 `arch:Stakeholder` 的提交 → `STALE_HEAD`；之后有一个往 `governance.ttl` 追加一条合法批准记录（修改已有文件）的提交 → `STALE_HEAD`（U2）；之后有一个批准提交、但 trailer 值不等于其记录 evidence → `STALE_HEAD`（第三轮 A）；之后有一个批准提交，新增的是 `governance/` 下的非 `.ttl` 文件、`governance/` 子目录里的 `.ttl`、模式 `120000` 的符号链接、一个文件里两条批准记录、或带两个 `AISEP-Evidence` trailer → 各自 `STALE_HEAD`（核对轮 6）；之后先加一个代码文件再删掉（净差异为空）→ `STALE_HEAD`；之后只有批准提交 → 第二个关口成功，活动复用（1 个活动、2 条记录）；`expectedBaseCommit` 与算出的 merge-base 不等 → `STALE_BASE`；headCommit..tip 含合并提交（侧分支带进代码提交）→ `STALE_HEAD`；同一分支先批准模型 A 再批准模型 B → 均成功；在第 1 步与第 7 步之间（钩子里或打桩）让代理提交一个代码提交 C → `STALE_HEAD`（`reason: concurrent-commit`），分支头 = C，C 不丢，记录文件已删除、index 里没有该路径，无批准提交残留；`branch` 为主分支 → `INVALID_ARGUMENT`（`reason: protected-branch`），无提交；W 的登记路径（改 `.git/worktrees/<n>/gitdir`）指向 `--allow-root` 外或另一个仓库 → `PATH_OUTSIDE_ROOT` / `WORKTREE_NOT_FOUND`，目标目录无提交。**第四轮负例**：之后有一个批准提交，新文件复制了一条已有记录的全部三元组、再加一条新记录（图差异仍只新增一条）→ `STALE_HEAD`；新文件名与记录 IRI 本地名不符 → `STALE_HEAD`（R4-8） |
| T24 | gate 门槛（Q6） | evidence 上植入 L1 违规：Approved → `GATE_FAILED`、无提交；Rejected → 成功 |
| T25 | 去重与不接受字段 | 同输入调两次，第二次 `duplicate:true`、提交数不变；**首次调用提交成功后丢弃响应再重放**（有 activity、无 activity 各一例）→ `duplicate:true`、提交数不变；传 `evidence` 或 `baseCommit` → `isError:true`、`INVALID_ARGUMENT`、`details.rejectedFields` 点名、提交数不变 |
| T26 | 失败回滚 | 装一个总失败的 pre-commit 钩子：`COMMIT_FAILED`，`git status --porcelain` 为空，HEAD 不变；钩子失败前改写新记录文件 → 文件保留钩子写的内容、index 里没有该路径、`CONFLICT`；`models/` 有未提交改动 → `DIRTY_WORKTREE`；残留一个未提交的记录文件（未跟踪、已暂存各一例）→ `DIRTY_WORKTREE` 且 `orphanApproval:true` |
| T27 | impact | 采购例子 depends 14、ripple 16，条目集合与 CLI 相同；每个 `path` 末跳的 `to` 等于该条 IRI；植入 L1 违规 → `MODEL_INVALID`；`allowInvalid` → `invalidModel` 非空；未知元素 → `ELEMENT_NOT_FOUND` 带候选 |
| T28 | PROV 最小桩（Q4-C） | 加桩后，`prov:wasAssociatedWith` 指向 `aisep:AIAgent` 实例的夹具 gate PASS；`prov:used` 仍报 `undeclared predicate`；`approvedBy` 指向 AIAgent → L1 与 L3（EG13）都失败、一致；`a prov:SoftwareAgent` 的实例仍报未声明的具体类；原型测试全过 |
| T29 | 查询只读 | `INSERT DATA` → `QUERY_NOT_READONLY`，store 三元组数不变；含 `SERVICE` → `QUERY_NOT_READONLY`，且断网下无网络调用；超 limit → `truncated:true`；有一个文件解析失败 → `PARSE_FAILED`，`allowPartial:true` → `partial:true` 且 `skippedFiles` 含该文件 |
| T30 | HTTP 安全与协议 | 错误 `Origin` → 403；`Host` 非 loopback → 拒绝；从 `Origin: app://renderer` 发 `OPTIONS` 预检成功且 `Access-Control-Allow-Headers` 含 `Mcp-Method`、`Mcp-Name`；从其他源（含 `null`）预检 → 403；按 2026-07-28 形状、不发 `initialize` 直接 `tools/call` 成功；缺 `Mcp-Name` → 400 / `-32020`；头里的版本与 `_meta` 不一致 → 拒绝；用 `mcp==2.3.*` 实测确认服务器确实协商 2026-07-28（本文据评审转述，尚未在本机跑过） |
| T31 | 工作台替换 | `npm run typecheck` 通过；vitest 基线 292 项 + 新用例全绿；`McpModelClient` 把 `isError` 转成 `AisepToolError(code)`；`elementsFromRows` 遇映射不到的 approvalState 抛错，缺失时显示"无批准状态"；采购例子的架构全景与待批准列表都不含 `approval-20261119-arch-baseline` 和 AI 活动，待批准列表只含 Proposed 元素；"改动元素"各状态都渲染（含"含未提交"、incomplete、`WORKTREE_NOT_FOUND` 退回引用模式）；"架构全景"违规徽标在植入 1 个遗留违规时显示 1；`FixtureClient` 与 `McpModelClient` 对同一夹具仓库的结果结构等价（契约测试） |
| T32 | 真客户端端到端 | 复用**一个** `claude -p` 进程挂 `--mcp-config`，让它"给采购模型加一个'报价行'业务对象，并用 Access 连到提交报价单"：工具调用序列无协议错误，最终 gate PASS。只跑一次，控制成本 |
| T33 | 异构评审 | 已做一轮（GPT 族，见文末记录），反例已并入 T5、T7、T15、T19、T23、T25、T26、T29。修订后的新增内容（§5.9 逐提交校验、目标 worktree 锁、§5.8 树形空白节点）和拍板后新增的内容（§5.8 worktree 模式、§5.4 `openViolations`、§5.1 `preexisting`、Q5 禁用 rebase 合并）定稿前再过一次。**第二轮已做**（2026-11-20，GPT `gpt-5.6-sol-high` + Claude Git 语义与安全 lens，22 条，见文末"第二轮"），反例已并入 T7、T13、T23、T35、T36、T37。第二轮引入的修订（锁内复验与提交后撤回、统一文件集合、逐级 `O_NOFOLLOW`、前后核对）只经同模型落文，尚无可执行探针，实现时按上列用例验证。R2-13、R2-15 拍板后新增的内容（§5.9"合并时校验""批准专用 PR""发布关口"、T38–T40）由第三轮覆盖。**第三轮已做**（2026-11-20，3 路：GPT `gpt-5.6-sol-high` + Claude Git 语义 lens + Claude 对抗绕过 lens，另做平台事实核查，归并为 18 簇，见文末"第三轮"），反例已并入 T13、T21、T23、T26、T38–T40、T43；第三轮的修订（U1–U4 与各簇改文）只经同模型落文，未再过异构评审 |
| T34 | 错误结果符合 outputSchema | 用 TS SDK `Client.callTool` 对每个错误码各触发一例：不抛 `InvalidParams`，`structuredContent.error.code` 原样到达；未捕获异常 → `INTERNAL`，不是 `-32603` |
| T35 | diff worktree 模式：内容口径（Q6 条件一） | 临时仓库 `main` 提交采购例子，`git worktree add -b feat-x`；分支先提交一个新元素，主分支分叉后再新增一个元素；工作区里：(a) 改 `am4.ttl` 中 `supplier` 的 prefLabel → `modified`，`changedPredicates` 只有 prefLabel；(b) 未跟踪的新 `extra.ttl` → 其元素 `added`；(c) 删除已跟踪的 `uml.ttl`（未暂存）→ `QuotationEntity` 与其 refines 关系 `removed`；(d) 语法坏的新 `broken.ttl` → `incomplete:true`、`failedFiles` 点名它，(a)–(c) 照常成立；分支已提交的元素也在（已提交 + 未提交）；主分支后来新增的元素不显示为 removed（merge-base）；`.gitignore` 忽略的 `.ttl` 不参与；指向 `/etc/hosts` 的符号链接 `.ttl` 记入 `failedFiles`（`error: symlink`）、不读目标；把 `models/procurement` 目录换成指向工作区外的符号链接 → 其中文件都记入 `failedFiles`、外部主语不出现在结果里（评审探针实测普通 `open()` 会读到外部的 `SECRET_FROM_OUTSIDE`）；FIFO `.ttl` → `error: not-regular`、不阻塞；`git mv code.ttl code2.ttl` 后截断 code2.ttl → 原 4 个主语进 `indeterminate`、无 removed；对已改的 `am4.ttl` 设 assume-unchanged → 不走快速路径、改动照常报出；skip-worktree 且磁盘缺失的 `uml.ttl` → 不报 removed；被忽略的 `.ttl` 和嵌套仓库里的 `.ttl` 在 `model_check`、写工具基线、diff 里都不出现（统一文件集合）；读取期间持续改写某文件 → 重读后一致则正常返回，始终不一致 → `WORKTREE_CHANGED`；`head.kind=worktree`、`headCommit` = 工作区 HEAD、`dirty:true`；调用前后 `git status --porcelain` 相同；同一分支用 Git 引用模式只含已提交的那一个元素；另一工作区把已跟踪的 `code.ttl` 截掉一半 → `incomplete:true`，它的 4 个主语进 `indeterminate`、**一个都不报 removed**，`items` 为空；干净工作区 → `dirty:false`、结果与 Git 引用模式相同；工作区无改动时走快速路径（解析器调用计数为 0）；暂存但未提交的新文件也算 added。**探针已跑**（F19）：`/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/wtdiff.3CCZ/probe/probe_test.py`（实现 `/private/tmp/claude-501/-Users-yongqian--claude-spares-spare-VE0kPl/6e08d12c-e1c6-4dc7-8f37-a2df50bfea94/scratchpad/wtdiff.3CCZ/probe/wtdiff.py`；`$PY -I probe_test.py <空目录>`；临时目录，可能已清理），15 条内容断言（A1–A15）全部 CONFIRMED，覆盖上列除"快速路径计数""暂存新文件"两条外的各项；把 indeterminate 处理变异掉，截断用例 REFUTED（4 个主语被报成 removed）；把符号链接检查变异掉，符号链接用例 REFUTED |
| T36 | diff worktree 模式：定位与拒绝 | `head.worktree` 传 `/etc`、工作区的真实绝对路径、`../x`、`--output=/tmp/x`、`refs/heads/feat-x`、`@{-1}` → 均 `INVALID_ARGUMENT`；`head` 对象多带 `path` 键 → `INVALID_ARGUMENT` 且 `rejectedFields` 点名；不存在的分支 → `WORKTREE_NOT_FOUND`（`branchExists:false`）；分支存在但没检出 → `WORKTREE_NOT_FOUND`（`branchExists:true`）；工作区目录被删（prunable）→ `WORKTREE_NOT_FOUND`；以上调用均不打开 `models/` 以外的任何文件（打桩 `open` 计数）；分支检出在 `--allow-root` 之外的 linked worktree → `PATH_OUTSIDE_ROOT`；改 `.git/worktrees/<n>/gitdir` 指向另一个仓库 → `WORKTREE_NOT_FOUND`。**探针已跑**：10 条错误码断言 CONFIRMED（`rejectedFields`、`branchExists` 的值与打开文件计数未断言） |
| T37 | 遗留违规可查可见（Q6 条件二） | 夹具用 `--no-verify` 提交一个 L1 违规：`model_findings` 的 `openViolations.count=1`、`items[0]` 是该违规的结构化 Finding（`focus` 非空）、`byLayer.L1=1`；同一内容上 `model_gate` 的 `violationsByLayer` 与不加 openViolations 前相同（不重复计数），`model_findings.summary` 不含它；两个不同 `focus` 的同文案违规 → `items` 两项、`count=2`；随后合法写入成功，`findings` 里该违规 `preexisting:true`；一次会新增违规的写入被拒，`details.findings` 里新违规 `preexisting:false`、旧违规 `true`；只读工具的 Finding 不带 `preexisting` 键；pre-commit 钩子在该违规存在时拦下任何提交（证明已提交内容里的遗留违规只能经 `--no-verify` 或规则升级进入） |
| T38 | 合并时校验（R2-13；第三轮 C–H、Q、U1、U3） | CI 检查对临时仓库：批准后分支上再提交一个代码提交 → 拒绝，`offendingCommit` 是该提交；evidence..分支头只有批准提交（含连过两个关口）→ 通过；批准后把主分支合进本分支（范围含合并提交）→ 拒绝；同一对象先批准、改代码、重新批准（同关口、`approves` 为超集、时间更晚）→ 通过（旧记录被取代，不查）；新记录只覆盖部分对象 → 旧记录仍被查 → 拒绝；CI 与 `record_approval` 第 1 步调用同一判据函数（打桩计数）；主分支在批准后删掉分支新关系引用的元素（两边各自 gate PASS）→ 合并结果上 `model_gate` FAIL、拒绝合并；检查前后两条分支头不变。**第三轮负例**：PR 改写目标分支上已有的一条批准记录（如改 `approves`）→ 拒绝（E；对抗绕过 lens 在原型副本上实测这类改写 gate PASS，所以只能靠本检查）；PR 删除一条已有的 Rejected 记录 → 拒绝（E）；新记录 evidence 为 `sha256:` 形式 → 拒绝（C）；新记录 `generatedAtTime` 比检查时的当前时间（注入时钟）晚 6 分钟 → 拒绝，晚 4 分钟 → 不因此拒绝；把 committer 时间也伪造成同一未来时刻 → 结论不变（C；核对轮 6）；跨关口取代：旧 `GateMerge` 批准后改代码，再加一条更晚的 `GateRequirements` 覆盖同一对象 → 旧 `GateMerge` 记录仍被查 → 拒绝（D）；同一对象两条 `generatedAtTime` 相同的新记录 → 两条都查（D）；交叉合并造出两个 merge-base → 结论与 merge-base 的选择无关，与只有一个 merge-base 的同内容拓扑相同（F）；`fetch-depth: 1` 的浅克隆 → 失败关闭（拒绝），不跳过（G）；把测试合并提交（`GITHUB_SHA`）传成 PR 头 → 脚本不采用，取 `pull_request.head.sha`（G）；普通 PR 修改主线上 Approved 的元素且无新批准 → 拒绝，补一条覆盖它的合法批准后通过（U1）；新增活动的 `baseCommit` 被手改为别的提交、或 `aisep:branch` 不等于 PR 源分支名 → 拒绝（Q）；CI 在主线 T1 上通过后主线前进到 T2（删掉被引用的元素）→ 合并前重算对 T2 报合并结果 gate FAIL、不合并（U3）。**核对轮负例**：新记录 `approves` 一个在 evidence 上不存在的 IRI X → 拒绝；主线上已有一条预先批准 X（X 尚不存在）的记录，普通 PR 创建 X 而无新批准 → 拒绝，补一条覆盖 X 的合法批准后通过（核对轮 2）；普通 PR 批准元素 Y 后，主线修改了 Y（分支未合入主线、无合并提交）→ evidence 与合并结果中 Y 的三元组不同 → 拒绝，主线只改了别的元素 → 通过（核对轮 5）。**第四轮负例与正例**：普通 PR 新增一个 Proposed 元素、不带任何批准记录 → 通过（正例，ADR-016：未经批准的改动可进主线）；修改主线上 Approved 的元素，只附一条覆盖它的 Rejected 记录 → 拒绝，换成别的关口的 Approved 记录 → 通过（R4-2）；覆盖记录的 `generatedAtTime` 早于 T 上该对象的旧 Approved 记录（回填）→ 拒绝；分支写好覆盖记录后，主线又合入一条针对同一对象、时间更晚的记录 → 合并前重算拒绝（R4-3）；手写一条 Approved 记录，其 evidence 上植入无关的 L1 违规，主线随后修好它使 M 的 gate PASS → 拒绝，同样构造的 Rejected 记录 → 不因此拒绝（R4-4）；新记录 `approves` 指向一条限定关系、一个视图或一个 `arch:Stakeholder` → 记录不合法（L1），不算覆盖（R4-5）；普通 PR 只改已批准模型的 `skos:prefLabel` 或 `arch:modelConformsToMetamodel`、无新批准 → 拒绝（R4-6）；CI 拿到的 `refs/pull/N/merge` 基于旧的 T0、远端已前进到 T1 → 脚本按 T1 本地合并、不用平台合并引用（R4-10）；合并前重算通过后注入一次主线前进 → `ls-remote` 比对不等、重来，合并后核验父提交不等 → 对新主线头重跑并按结果回滚（R4-11）；旧记录 `10:00:00Z` 后有代码提交，覆盖记录写 `12:00:00+08:00`（同关口、超集）→ 旧记录不被豁免、拒绝；`10:00:00Z` 与 `18:00:00+08:00` 两条 → 按同时处理、两条都查（G4-1）；删除 T 上 Approved 的元素 X，同时新增一条 `approves` 含 X 的合法记录（删除分别在 evidence 前、后）→ 均拒绝、提示退役（G4-2）；批准 A1 后把主线合进分支、以合并提交为 evidence 同关口超集重批 → 通过，重批只覆盖部分对象 → 拒绝（G4-3）；X Approved，PR 只改以 X 为端点的关系 R 的 `arch:target` → 通过、X 仍 Approved（正例，固定 G4-4 的口径），X 所在模型被按模型批准时同样改动 → 拒绝；`branch` 传 `refs/heads/feat/x` → `record_approval` 报 `INVALID_ARGUMENT`，传 `feat/x` → 活动写 `"feat/x"`、检查项 4 通过（G4-5）；在 C 上批准（baseCommit = F）后，另一个 PR 把本分支的祖先 C1 合进主线 → 检查项 4 拒绝，在新提交上重批取代旧记录后 → 旧活动不再重算、通过（G4-6） |
| T39 | 批准专用 PR（R2-15；第三轮 A、B、I、O、U4） | 从被发布提交 R 拉的批准分支只含一个 `GateRelease` 批准提交 → 判为批准专用 PR，只跑合并时校验与合并结果 gate，不要求新的关口批准，通过；同一分支再夹带一个代码提交、或一个往 `governance.ttl` 加 `arch:Stakeholder` 的提交 → 判为普通 PR（要求过关口）；从主线最新提交 M（R 之后又有代码提交）拉分支、headCommit = R → `record_approval` 报 `STALE_HEAD`、无提交；绕过 MCP 手工造出同样的分支和批准提交 → CI 拒绝（R..分支头含非批准提交）。**第三轮负例**：批准提交的 `AISEP-Evidence` trailer 值不等于其记录的 evidence（伪造 trailer）→ 不算批准提交，按普通 PR（A）；只新增一个未被任何新记录引用的 `aisep:AgentActivity` 的提交 → 不判为批准专用（B）；手写一个 evidence 为主线旧提交、关口为 `GateArchitecture` 的批准提交 → CI 拒绝（U4①）；`GateRelease` 记录的 evidence 不是目标分支头的祖先 → 拒绝，普通 PR 里新增 `GateRelease` 记录 → 拒绝（O）；R 之后主线修改了被批准对象 X，再合入 evidence = R、`approves` 含 X 的发布批准 → 拒绝，主线只改了别的对象 → 通过（I）；批准提交新增的是非 `.ttl` 文件、子目录里的文件、符号链接，或含两条批准记录 → 不算批准提交，不判为批准专用（核对轮 6）；在发布批准分支的批准提交 A（evidence = R）上以 `headCommit = A` 再批 `GateArchitecture` → `record_approval` 报 `INVALID_ARGUMENT`（`reason: mainline-head-gate-not-release`），绕过 MCP 手写同样的提交 → CI 拒绝（A 的有效内容提交是 R，核对轮 4）；`approves` 为模型 IRI 的发布批准，R 之后主线改了该模型的一个成员（或以成员为端点的关系）→ 拒绝，主线只新增了一条别的批准记录 → 通过（核对轮 3）；从 R 手写一个形状完全合法的 `GateRelease` 批准提交（冒用已有 Stakeholder）→ CI 判为批准专用 PR 并通过：证明判据不防伪造，合并仍须人工 PR 批准（U4②；写进测试名，防止被误读为安全保证） |
| T40 | 发布批准的约束（R2-15；第三轮 J、K、L、N、U4①） | `gate: GateRelease` 带 `activity` → `INVALID_ARGUMENT`、`rejectedFields` 含 `activity`、无提交；headCommit 已在 mainRef 上、`gate` 为其他关口（带不带 `activity` 都一样）→ `INVALID_ARGUMENT`（`reason: mainline-head-gate-not-release`）、无提交（U4①）；`GateRelease` 的 headCommit 只在功能分支上 → `INVALID_ARGUMENT`（`reason: release-head-not-on-main`）；成功时记录 evidence = R、无活动；远端有 `release/{yyyymmdd}-{R 前 7 位}` 标签指向 R → 标签检查通过，缺标签或标签指向别的提交 → CI 失败。**第三轮负例**：`decision: Rejected` 的发布批准 → 工作台不建标签，CI 不要求标签（J）；标签名不合规（如 `release/foo`）→ 不算数、CI 失败；附注标签指向 R → 按剥离后的 commit 比较、通过；标签被移到别的提交 → CI 失败（K）；PR 关闭未合并 → 工作台不删标签，标签保留（核对轮 7：遗留标签由人清理，附录 C 登记）；同名标签已存在且剥离后指向 R → 幂等复用、不报错，指向别的提交 → 报错、不覆盖（L）；同一 R 先后两次发起批准 → 分支名带秒级时间戳、不冲突（L）。**GC 断言**（第三轮 N，替换原"删批准分支、`gc` 后 R 仍可读"：R 是主线提交，本来就不会被 GC，原断言是空证）：功能分支上批准 H1、改内容后再批准 H2（H1 只在已合并的分支侧），PR 以普通 merge 合入、删分支、`git gc --prune=now` 后 H1 仍可达（`git cat-file -e H1^{commit}`），`model_diff` 对 H1 的历史差异可复现；对照：同样拓扑改用 squash 合并 → H1 不可达（证明断言能失败） |
| T41 | `model_set_labels`（§5.10） | 改 `supplier` 的 `prefLabel` → 成功，IRI 不变，`git diff` 只动含该三元组的那一块，`model_diff` 报 `modified`、`changedPredicates` 只有 prefLabel；同参数重放 → `changed:false`、文件不变；`prefLabel` 传空串、三个字段都不给、多带 `type` 键 → `INVALID_ARGUMENT`（`rejectedFields` 点名）；`definition: null` → 删除定义；目标是 `approval-20261119-arch-baseline` → `PROTECTED_RESOURCE`；不存在的 IRI → `ELEMENT_NOT_FOUND`；以上拒绝均不改任何文件（并入 T6）；`@en` 以外语言的标签原样保留 |
| T42 | 缺省写入文件（§5.1） | 对 `models/procurement/` 现有 27 个关系，按 §5.1 规则推算的文件都等于它们实际所在的文件（合并时已用脚本核对一次：27/27；本稿原"源端所在文件"规则只有 24/27）；新建 `ext-code` 类型的元素写进 `code.ttl`、`ext-governance` 类型的写进 `governance.ttl`（`aisep#` 共用命名空间，按 `aisep:loads` 判定） |
| T43 | 一条记录一个文件（U2） | 两条分支从同一主线提交出发，各对不同元素调一次 `record_approval`：各得一个新建的 `governance/<记录本地名>.ttl`，`git show --name-status` 各只一行 `A`；两个 PR 先后以普通 merge 合入，本地 `git merge` 与托管平台服务端合并都无冲突，合并后两条记录都在、都参与推导；对照：两条分支都往 `governance.ttl` 末尾追加一条记录 → 第二个合并冲突（证明问题真实存在）；已有 `governance.ttl` 字节不变，`approval-20261119-arch-baseline` 的 IRI 与推导结果不变；统一文件集合、`model_gate`、`model_diff` 都读到子目录里的记录文件。**第四轮**：两条分支从同一个 R 出发，同一天、不同秒各批一次同一关口 → 记录本地名不同（秒级时间），两个 PR 先后合入无冲突；同一秒内各批一次 → 同名、第二个合并冲突（证明残余风险真实存在，R4-7） |

**最大的风险**：T15、T17、T21–T23、T35–T37 的期望值是本文自己定的，自写代码加自写测试是循环自证。第一轮异构评审挑出 4 处缺口（文件名判据、重放幂等、跨模型闭包、空白节点）；第二轮又挑出批准竞态、worktree 越出根目录、上级目录符号链接、改名后误报删除等，均已改文并补用例；第三轮（3 路）又挑出批准专用 PR 可伪造、已有记录可被改写、合并结果 gate 绑定旧主线、两条分支追加 governance.ttl 必冲突等，已按 U1–U4 与各簇改文并补用例（T38–T40、T43）。第二轮、第三轮的修订都尚无探针，第三轮修订已过第四轮异构评审（GPT + Grok，见文末"第四轮"）；第四轮修订本身尚未再评，也无探针。
<!-- END-MOVED §11 -->

<!-- BEGIN-MOVED 附录 D -->
## 附录 D：工具 ↔ 规范 ↔ 原型追溯表

> 来自另一会话草案，合并时并入。行号指本仓库 `tools/aisep.py` 与 `modules/aisep-core/shapes.ttl` 当前版本，2026-11-20 合并时逐条核对，全部对得上（`tools/aisep.py` 与原型目录里的同名文件逐字节相同）。拆库（§3.1）后行号会失效，届时以函数名为准。**EXISTS** = 已有实现：原型里已有、可直接复用，或已在 `aisep/` 实现并合入（行内写明 PR 与文件）；**GAP** = 要新写。附录 C 指规范附录 C。

| §8.3 逻辑名 | 线上名 | 本文 | `tools/aisep.py` / 规则映射 | 状态 |
|---|---|---|---|---|
| `model.add_element` | `model_add_element` | §5.2 | 校验：`run_check` L948–950；TypeShape / InModelShape / LabelShape（aisep-core `shapes.ttl` L29 / L53 / L73）；R2 `l1_one_notation` L643–655；G7 `l1_closed_predicates` L620–641；抽象类 `ABSTRACT_ROOTS` L64。写入：已实现（S4a，PR #15）：`aisep/write_tools.py` 的 `model_add_element`，写入层 `aisep/writer.py`（`rewrite_blocks`、`check_equivalence`）；只拒绝新增违规。测试 `aisep-mcp/tests/test_write_tools.py`、`test_write.py`（T6、T7、T8 等）、`test_server.py` | EXISTS |
| `model.add_relationship` | `model_add_relationship` | §5.3 | 判定：`l1_notation_mixing` L657–691（§7.3、G5）、`l1_refines` L693–723（§7.2）、`l2` L726–759 + `rt_table` L765–778；IRI：`Ctx.uf` L230、`nearest` L255–259；每个关系类都声明 `arch:unqualifiedForm`（RelationshipShape，`shapes.ttl` L102 起）。写入：已实现（S4a，PR #15）：`aisep/write_tools.py` 的 `model_add_relationship`（不写直连三元组），写入层 `aisep/writer.py`。测试 `aisep-mcp/tests/test_write_tools.py`、`test_write.py`、`test_server.py` | EXISTS |
| `model.remove` | `model_remove` | §5.5 | 找引用：`Ctx.relationships` L316–319、`src_quads`（L205）；兜底：EndpointShape（`shapes.ttl` L126 起）；`ELEMENT_LINK_OK` L83–88。级联逻辑：已实现（S4b，PR #17）：`aisep/write_tools.py` 的 `model_remove`、`remove_plan`、`plan_digest`（`cascade` + `dryRun` + `planDigest`，重放幂等）。测试 `aisep-mcp/tests/test_remove.py`、`test_write_tools.py`（T18 等）、`test_server.py` | EXISTS |
| （扩展）`model.set_labels` | `model_set_labels` | §5.10 | 校验：`run_check` L948–950、LabelShape（`shapes.ttl` L73）。按主语块改写标签：已实现（S4a，PR #15）：`aisep/write_tools.py` 的 `model_set_labels`，`aisep/writer.py` 的 `rewrite_blocks`。测试 `aisep-mcp/tests/test_write_tools.py`（T41）、`test_write.py`、`test_server.py` | EXISTS（扩展 §8.3） |
| `model.check` | `model_check` | §5.4 | `cmd_check` L953–962 → `Ctx.__init__` L202–237（L0 在 L207–218）+ `run_check` L948–950（`l1` L491–539、`l2` L726–759） | EXISTS |
| `model.validate` | `model_validate` | §5.4 | `cmd_validate` L965–972、`l3` L819–848 | EXISTS |
| （扩展）`model.gate` | `model_gate` | §5.4 | `cmd_gate` L975–989（G10） | EXISTS（扩展 §8.3） |
| `model.findings` | `model_findings` | §5.4 | `cmd_findings` L1006–1011、`l4` L853–890（含 R4）；`openViolations` 复用 `run_check` | EXISTS；`openViolations` 为新增 |
| `model.query` | `model_query` | §5.6 | `cmd_query` L1014–1033、`onto_files` L179–186（载入 L220–221） | EXISTS（查询核心）；`limit`/`truncated`、拒绝 `SERVICE` 为新增 |
| `model.impact` | `model_impact` | §5.7 | `cmd_impact` L1047–1076（G9 L1060–1071）、`impact` L895–931（依赖方向 `aisep:dependency` L899）、`expand` L1036–1044 | EXISTS；结构化路径、未知元素报错为新增 |
| `governance.record_approval` | `governance_record_approval` | §5.9 | 已实现（S5，PR #24）：`aisep/approval.py` 的 `governance_record_approval`（第 1 步与锁内复验 `_stale` → `aisep/mergecheck.py` 的 `approval_commit_problems`；第 4 步去重 `_find_duplicate`、`_find_activity`；第 5 步生成记录内容 `_record_file`；第 7 步新建记录文件 `_write_new`、`git add --intent-to-add` + `git commit --only`（提交 `6b2d340`）、提交后核对与撤回；第 8 步回滚 `_unstage_and_maybe_delete`）。校验与推导：`aisep/core.py` 的 `approval_problems`、`activity_problems`（G1：写入前与推导同一函数）、`derive_approval_state`（口径 A，PR #29：只给可被批准的元素推导 approvalState）；批准人按 Q4=C 拆为 `APPROVERS` / `NOT_APPROVERS`（`aisep/core.py`）。测试 `aisep-mcp/tests/test_record_approval.py`、`test_record_approval_review.py`、`test_approval_extra.py`、`test_derive_scope.py` | EXISTS |
| `model.diff` | `model_diff` | §5.8 | 只可复用 `ox.parse` 用法（L207–218）、`short` L104–112、`model_graph_of` L470–475；实现：已实现（S3，PR #13）：`aisep/diff.py` 的 `model_diff`（Git 引用模式与 worktree 模式）。测试 `aisep-mcp/tests/test_diff.py`（T14、T15 等）、`test_server.py` | EXISTS |

**全部工具共有的工作**（原列为新建，现已实现）：MCP 外壳（stdio + 本机 HTTP，§3.2）：`aisep/server.py`；结构化结果与 §7 的错误模型：`aisep/tools.py`、`aisep/errors.py`；§5.1 的写入流程与新违规判定：`aisep/writer.py`（`judge` 等）；文件选择（按 `aisep:loads` 判定声明模块）：`aisep/write_tools.py` 的 `declaring_module`、`default_element_file`、`default_relationship_file`；§3.3 的仓库定位与统一文件集合：`aisep/gitio.py` 的 `locate_repo`、`locate_worktree`、`model_files`（取代原型 `model_files` L936–937 的 glob，含 `governance/` 子目录，见下表 U2 行）。

**第三轮新增的 GAP**（2026-11-20 登记；此后已逐项实现，状态列为当前状态）：

| 项 | 本文 | 现状 | 状态 |
|---|---|---|---|
| 合并时校验与合并前重算的检查脚本（口径、检查项 1–7（第 7 项见 T38 核对轮负例、T39 第三轮 I；第四轮 R4-12）、批准专用 PR 判定、发布标签检查；CI 与执行合并的人共用一个脚本） | §5.9"合并时校验""合并前重算""批准专用 PR""发布关口"第 4 步 | 已实现（S6，PR #18）：`aisep/mergecheck.py` 的 `merge_check`（口径、检查项 1–7、批准专用 PR 判定 `classify_pr`、发布标签检查）、`approval_commit_problems`（第 1 步判据，`record_approval` 共用）、合并前重算的 `target_unchanged`（R4-11 ②）与 `post_merge_verify`（R4-11 ③），命令行 `python -P tools/pyrun.py aisep.mergecheck`；`.github/workflows/gate.yml` 的 `mergecheck` job 跑在 PR 上，已与 `gate` 并列为 main 的必需检查。负例 `aisep-mcp/tests/test_merge_check_negatives.py` 全部通过 | EXISTS |
| `approves` 目标类型校验（第四轮 R4-5，ADR-016） | 规范 §6.6、§5.9 输入表 | 已实现（S6，PR #18）：`approval_problems`（`aisep/core.py`）对存在的目标核对允许集合（带 `arch:inModel` 的 `arch:Element`，不含限定关系、ApprovalRecord、AgentActivity、Stakeholder；`arch:Model`；`ad:Decision`），不合法的记录 L1 报出、推导忽略；目标不存在的按原口径 | EXISTS |
| 批准记录文件形状检查（第四轮 R4-8） | §5.9 第 1 步 | 已实现（S6，PR #18）：判据函数（`aisep/mergecheck.py` 的 `_commit_shape`）直接解析新增文件，核对主语集合、主语三元组全在该文件内、文件名等于记录本地名 | EXISTS |
| 记录文件放在 `models/<slug>/governance/` 子目录（U2） | §3.3、§5.1、§5.9 第 1、5、7、8 步 | 已实现：读取侧统一文件集合 `aisep/gitio.py` 的 `model_files`（`git ls-files` 含子目录，测试 `aisep-mcp/tests/test_gitio.py`）；判据 (b) 的路径匹配 `aisep/mergecheck.py` 的 `RECORD_FILE`（只认 `models/<slug>/governance/` 下一层的新增文件）；记录文件的新建、intent-to-add 登记与回滚 `aisep/approval.py`（`GOV_DIR`、`_write_new`、`_unstage_and_maybe_delete`，S5，PR #24）。测试 `aisep-mcp/tests/test_u2_governance_dir.py`（gate、diff、推导都读到子目录里的记录）、T43（`test_record_approval.py`、`test_merge_check_negatives.py`） | EXISTS |
| ADM 文档中的 `gate models/<slug>/*.ttl` 命令（`docs/adm/` 下 24 处）| §3.3 | shell 展开不含 `governance/` 子目录，新记录文件不被检查。2026-11-20 已改：命令统一为 `$(find models/<slug> -name '*.ttl')`（递归含子目录），两处非命令的引用改为文字说明；CLI 未加新参数 | 已解决（文档） |
<!-- END-MOVED 附录 D -->
