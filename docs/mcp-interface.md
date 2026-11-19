# AISEP 一期 MCP Server 接口设计（草案）

> 细化 ADR-008 与《元模型规范》v0.4 §8.3。本文只做设计，不含实现。
> 依据：`docs/metamodel-spec.md`（§3、§7、§8、§9、§10、附录 C）、`docs/decisions.md`（ADR-008、009、011、012、013）、`tools/aisep.py`（原型，下文行号均指该文件当前版本）。
> 状态：草案，待用户确认第 6 节的开放问题后定稿；定稿时 ADR-013 中"MCP 部分为草案"一并关闭。

## 1. 范围与原则

- **一期交付物**：一个 MCP Server，提供写入层、查表校验、SPARQL 查询、影响分析（ADR-008），外加 `model.diff`（ADR-013）。工作台与编码代理是它的**两类客户端**，调用同一套工具，没有专供某一方的工具。
- **无状态**：所有写操作只是对 `models/<slug>/*.ttl` 的文本修改，修改结果进 Git（由客户端提交，见 §6 Q3）。Server 不保存任何不在文件里的状态；每次调用都重新读取文件、重建上下文（原型 `Ctx`，L201–237）。允许的进程内缓存只有模块与上游本体（`rt_table` L765–778、`sparql_constraints` L784–794、`rdflib_graph` L802–816），它们在运行期不变；模块文件变更后需重启 Server。
- **不报告"进行中"**：不提供任何上报进行中状态的写工具（ADR-013）。工作台"AI 进行中"区域的运行态读编排器，改动元素数由 `model.diff` 实时算出。
- **传输**：v1 只用 stdio。客户端在某个 worktree 里启动 Server 进程，Server 的仓库根即该 worktree（与原型 `ROOT` 的取法一致，L26）。一个 worktree 一个 Server 进程。
- **工具命名**：语义名沿用 §8.3 的带点名称（`model.add_element`）。线上名把点换成下划线（`model_add_element`），以兼容只接受 `[A-Za-z0-9_-]` 的客户端。
- **实现方式**：Server 以库的方式直接调用 `tools/aisep.py` 里的函数，不再写第二套校验。原型里命令函数直接 `print`，需要改成返回结构化结果、由 CLI 负责打印（`report` L940–945 及各 `cmd_*`）。这一重构不改变任何规则，`aisep.py test` 必须仍为全绿。

## 2. 通用约定

### 2.1 IRI 生成（规范 §3）
| 对象 | 由谁给 | 规则 |
|---|---|---|
| 元素 | 客户端给 `slug` | `{base}model/{model}/{slug}`；slug 匹配 `^[A-Za-z][A-Za-z0-9]*$`（可读英文 camelCase，UML 类可大写开头，如 `QuotationEntity`）。已存在则拒绝（`IRI_EXISTS`），不自动改名 |
| 关系 | Server 生成 | `{model}rel-{源slug}-{直连谓词本地名}-{目标slug}`，重名依次加 `-2`、`-3`。直连谓词取 `Ctx.uf` 里最近的 `arch:unqualifiedForm`（L230、`nearest` L255–259）；每个关系类都必须声明它（aisep-core `shapes.ttl` RelationshipShape，L102 起），所以总能生成 |
| 批准记录 | 客户端给 `slug` | `{model}approval-{yyyymmdd}-{slug}`，日期取 Server 写入时的 UTC 日期 |
| AI 活动 | 客户端给 `slug` | `{model}activity-{yyyymmdd}-{slug}`。**规范 §3 尚未定义这一行，本文补充**，定稿后回填规范（§6 Q4） |

- `{base}` 仍为占位符 `https://aisep.example/`（原型 `MODEL_BASE` L45）。
- 输入中的 IRI 可写完整 IRI、`<slug>:<local>` 短形式或前缀名，统一用原型的 `expand`（L1036–1044）展开；输出一律给完整 IRI，另附 `short`（`short` L104–112）。
- IRI 一经创建不改；改名只改标签（§3）。§8.3 没有改标签的工具，见 §6 Q1。

### 2.2 写入哪个文件
模型目录里按记法拆文件只是为了方便阅读，语义不依赖文件。Server 用以下确定性规则选文件（与 `models/procurement/` 现有布局一致）：

- **元素**：按声明其类型的模块选文件。Language 模块 → `<模块名>.ttl`（`am4.ttl`、`bpmn.ttl`、`uml.ttl`、`ddd.ttl`）；Extension 模块 `ext-<x>` → `<x>.ttl`（`verification.ttl`、`code.ttl`、`governance.ttl`）；aisep-core 或上游 core 的类（如 `arch:Stakeholder`）→ `governance.ttl`。声明模块的判定：Language 类用 `owner`（L189–196）与 `Ctx.module_of`（L266–272）；`aisep#` 由 aisep-core 声明 `ownsNamespace`，但被多个 Extension 共享，`owner()` 会把它们都归到 aisep-core，所以按"哪个模块的 `aisep:loads` 文件里声明了这个类"来判定（本体按文件分图载入，L220–221）。**GAP**：需写一个小函数。
- **关系**：两端在同一文件，就写该文件；否则写**非 `am4.ttl` 的那一端**所在文件；两端都不在 `am4.ttl` 时写源端所在文件。（核对：`rel-quoteApproval-realizes-procurementSubdomain` 在 `ddd.ttl`，`arch:Refines` 在 `uml.ttl`/`bpmn.ttl`，`aisep:Implementation` 在 `code.ttl`。）
- 目标文件不存在时由 Server 新建，并写入标准前缀头。新建模型目录（`arch:Model` 本身）不在 §8.3 范围内，v1 手工建。

### 2.3 写入—校验原子性
每个写工具都按同一流程执行：

1. 校验输入（JSON schema、IRI 是否存在、类型是否已声明等，各工具的"前置检查"列）。
2. 在全部模型文件上跑一次 L0–L2，记下**基线违规集合**。
3. 在内存里保存目标文件的原始字节，然后做文本修改（追加或删除主语块，见 §6 Q2）。
4. 在全部模型文件（`model_files([])`，L936–937）上重建 `Ctx` 并执行 `run_check`（L948–950），得到 L0–L2 问题。
5. 如果出现**基线里没有的 Violation**，就把所有被改文件恢复为原始字节，返回 `VALIDATION_FAILED` 并列出新增违规。否则返回成功，附带新增 Warning 和基线违规数。

- 只比较新增部分，是为了让一个已经有违规的模型仍能通过写操作（包括 `remove`）被修好（§6 Q5）。
- 写操作**不跑 L3/L4**（L3 约 5 秒，规范 §10.1）。提交前由 pre-commit 跑 `gate`，提交与 CI 只认 `gate`（G10）。
- 加载范围始终是全部模型：跨模型引用的悬空检查依赖它（aisep-core `shapes.ttl` EndpointShape，L126 起）。原型实测 L0–L2 用时 0.06–0.14 秒，一次写操作建两次上下文的开销可以接受。

### 2.4 并发
- 一条分支同一时间只有一个写入者。Git 就是锁：不同会话在不同 worktree 和分支上工作，Server 不做任何加锁。
- 同一 worktree 里的多个写请求由 stdio 天然串行化。
- 合并冲突在 Git 层解决，解决后由 `gate` 把关。

### 2.5 错误模型
失败时返回 MCP 工具结果 `isError: true`，`structuredContent = {"error": {"code", "message", "problems"?: [...], "references"?: [...]}}`。`problems` 的每一项是 `{severity, layer, text}`，直接来自 `Ctx.problems`（L204、`add` L239–240）。

| code | 含义 |
|---|---|
| `INVALID_INPUT` | 不符合输入 schema、slug 格式错误、枚举值越界 |
| `UNKNOWN_MODEL` | `models/<model>/` 不存在 |
| `UNKNOWN_TYPE` | 类型不是已加载模块声明的具体类，或者是只能经专用工具写入的类（`aisep:ApprovalRecord`、`aisep:AgentActivity`） |
| `NOT_FOUND` | 引用的 IRI 不是任何模型的成员 |
| `IRI_EXISTS` | 元素、批准记录或活动的 IRI 已存在 |
| `VALIDATION_FAILED` | 写入后出现新的 L0–L2 Violation，已回滚 |
| `REFERENCED` | `remove` 被拒绝，`references` 列出引用方 |
| `MODEL_INVALID` | `impact` 因模型有 L0–L2 违规而拒绝（G9） |
| `QUERY_ERROR` | SPARQL 语法错误，或者是更新语句 |
| `GIT_ERROR` | Git 引用不存在、无法求 merge-base 等 |
| `PARSE_ERROR_AT_REF` | `diff` 时某个引用下的 Turtle 无法解析 |

成功时返回 `structuredContent`，其形状见各工具。校验类工具"有违规"不算错误：结论放在 `result` 字段里，`isError` 只表示调用本身失败。

## 3. 写工具

### 3.1 `model.add_element`
- **语义**：按 §3 生成 IRI，写入恰好一个类型、`arch:inModel`、一个 `@zh` 名称。
- **输入**：`{model: string, type: string, slug: string, labelZh: string, labelEn?: string, definition?: string}`
- **输出**：`{iri, short, file, warnings: [problem], baselineViolations: int}`
- **前置检查**：`type` 是已加载模块的类，且不是抽象类（`arch:isAbstractClass`，以及 `ABSTRACT_ROOTS` L64）；不是 `aisep:ApprovalRecord`、`aisep:AgentActivity`；slug 未被占用。
- **校验层**：写后 L0–L2（§2.3）。会用到的规则有 TypeShape（aisep-core `shapes.ttl` L29）、InModelShape（L53）、LabelShape（L73）、R2 `l1_one_notation`（L643–655）、G7 `l1_closed_predicates`（L620–641）。
- **映射**：写入部分是 **GAP**（原型没有写入命令）。要新建的是 IRI 生成、文件选择（§2.2）和追加主语块；校验直接复用 `run_check`。

### 3.2 `model.add_relationship`
- **语义**：只写限定关系资源（`arch:source`、`arch:target`、`arch:inModel`），作者从不写直连三元组（§8.1）。
- **输入**：`{model: string, type: string, source: iri, target: iri, labelZh?: string}`
- **输出**：`{iri, short, file, directPredicate, warnings, baselineViolations}`
- **前置检查**（写之前先判定，不合法就直接拒绝并说明原因，不必等回滚）：`type` 是 `arch:QualifiedRelationship` 的子类；两端都是模型成员；记法混用规则 §7.3（`l1_notation_mixing` L657–691，含 G5）；refines 层级规则 §7.2（`l1_refines` L693–723）；枢纽矩阵（`Ctx.l2` L726–759、`rt_table` L765–778）。实现上，前置检查就是在"假如写入后"的内存图上跑这几个函数，Violation 映射为 `VALIDATION_FAILED`，派生捷径的 L2 Warning 照常返回。
- **校验层**：L1/L2，然后按 §2.3 写后再跑一遍 L0–L2 兜底。
- **映射**：规则部分 **EXISTS**（同上各函数）；写入部分是 **GAP**（IRI 生成用 `Ctx.uf`/`nearest`、文件选择、追加主语块）。

### 3.3 `model.remove`
- **语义**：按 §8.2 删除。改关系类型 = `remove` 旧关系 + `add_relationship` 新关系，IRI 随之改变。
- **输入**：`{iri: string, mode?: "refuse" | "cascade"}`，默认 `refuse`。
- **输出**：`{removed: [iri], files: [path], warnings, baselineViolations}`。`mode=refuse` 而存在引用时返回 `REFERENCED`，附 `references: [{iri, predicate, file}]`。
- **级联范围**（`cascade`）：以被删对象为 `arch:source`/`arch:target` 的关系，递归处理（关系可以指向关系），这也包括它作为 refines 目标的情况；指向它的 `arch:inView`。
- **一律拒绝**的情况（哪种 mode 都不删）：
  - 被删对象是 `aisep:ApprovalRecord` 或 `aisep:AgentActivity`。批准历史只追加不修改，改结论要写一条时间更晚的记录（§6.6、R3）。
  - 被 `aisep:approves`、`ad:relatedConcept`、`dcterms:isReplacedBy`、其他 `ELEMENT_LINK_OK` 属性（L83–88）引用，或者被其他模型引用。这些引用的删除需要人判断，不能自动级联。
- **校验层**：L1（悬空引用由 EndpointShape 抓），按 §2.3 跑 L0–L2，涉及的多个文件一起回滚。
- **映射**：**GAP**（§8.2、附录 C 都写明"未原型化"）。找引用可复用 `Ctx.relationships`（L316–319）和 `src_quads`（L205），删除后由 EndpointShape（aisep-core `shapes.ttl` L126 起）兜底验证没有残留悬空引用。

### 3.4 `governance.record_approval`
- **语义**：追加一条批准记录，不碰任何状态字段（approvalState 由构建推导，D10）。可选同时写一条已完成的 `aisep:AgentActivity`，用 `aisep:activity` 关联，两者写在同一次文件修改里，由客户端在同一次提交里提交；gate（EG25）保证记录不会先于活动单独提交（ADR-013）。
- **输入**：
  ```json
  {"model": "string", "slug": "string",
   "gate": "GateRequirements|GateArchitecture|GateDesign|GateMerge|GateRelease",
   "decision": "Approved|Rejected", "approvedBy": ["iri"], "approves": ["iri"],
   "labelZh": "string", "evidence?": "40-hex | sha256:<64-hex>",
   "activity?": {"slug": "string", "agent": "iri", "sessionRef": "string", "branch": "string",
                 "startedAt": "xsd:dateTime", "endedAt": "xsd:dateTime",
                 "headCommit?": "40-hex", "baseCommit?": "40-hex"}}
  ```
- **由 Server 填写的值**：`prov:generatedAtTime` = 写入时的 UTC 时间。`activity.headCommit` 默认取 `branch` 的最新提交；`activity.baseCommit` 默认取 `git merge-base <主分支> <headCommit>`，客户端传入的值必须与之相等，否则返回 `INVALID_INPUT`。`evidence` 有活动时等于 `headCommit`（EG26）；无活动且未传入时，取 `git rev-parse HEAD`。
- **输出**：`{recordIri, activityIri?, file, evidence, derivedStates: {iri: state}}`。`derivedStates` 是写入后各被批准对象推导出的 approvalState（`derive_approval_state` L337–380），客户端不需要再查一次。
- **前置检查**：`approves`、`approvedBy`、`activity.agent` 都是模型成员，且 `approvedBy`、`agent` 是 `arch:Stakeholder`（`AGENTS` L56；`prov:Agent` 不作为模型类加载，§6 Q4）；各 commit 在仓库里存在。
- **校验层**：L1。批准记录的合法性只有一个定义（G1）：`approval_problems`（L396–433，含 ApprovalRecordShape aisep-core `shapes.ttl` L150 起、EG11/EG13/EG15、EG25/EG26）和 `activity_problems`（L435–468，含 AgentActivityShape L237 起、EG17–EG24），再加 R3c 歧义检查（`l1` L510–514）。按 §2.3 写后跑 L0–L2，不合法则回滚。
- **映射**：校验与推导 **EXISTS**；写入、默认值填充、Git 取值是 **GAP**。

### 3.5 `model.set_labels`（对 §8.3 的扩展，2026-11-20 用户拍板）
- **语义**：规范 §3"改名只改标签、IRI 不变"的唯一写入口。只改 `skos:prefLabel`、`skos:altLabel`、`skos:definition`，不动类型、IRI 和关系。
- **输入**：`{iri: string, labelZh?: string, labelEn?: string, altLabels?: [string], definition?: string}`；未给出的字段保持不变。
- **输出**：`{iri, file, warnings, baselineViolations}`
- **前置检查**：`iri` 是模型成员，且不是 `aisep:ApprovalRecord`、`aisep:AgentActivity`（批准历史只追加）。
- **校验层**：写后 L0–L2（§2.3），LabelShape（aisep-core `shapes.ttl` L73）兜底"恰好一个 `@zh` 名称"。
- **映射**：校验 **EXISTS**（`run_check` L948–950）；按主语块改写标签是 **GAP**。

## 4. 只读工具

### 4.1 `model.check` / `model.validate` / `model.gate`
| 工具 | 输入 | 跑哪些层 | 映射（EXISTS） |
|---|---|---|---|
| `model.check` | `{}` | L0–L2；L0 失败时只报 L0 | `cmd_check` L953–962 → `Ctx` L201–237（L0 在 L207–218）+ `run_check` L948–950（`l1` L491–539、`l2` L726–759） |
| `model.validate` | `{}` | L0 + L3（pyshacl，跑在构建后的图上，范围按 §10.2） | `cmd_validate` L965–972 → `l3` L819–848 |
| `model.gate` | `{}` | L0、build、L1–L4，一次原子执行 | `cmd_gate` L975–989 |

- 统一输出：`{result: "PASS"|"FAIL", violations, warnings, infos, byLayer: {L0, build, L1, L2, L3, L4}, problems: [problem], seconds}`。`result` 只在 `gate` 上有权威性，`check`、`validate` 只是开发时的快速反馈（§10.1）。
- **`model.gate` 是对 §8.3 的扩展**：§8.3 的工具表里没有它，但规范 §10.1 和 G10 规定提交与 CI 只认 `gate`，两类客户端需要在提交前、关口页上拿到同一结论，所以作为工具暴露。它和 pre-commit、CI 调用的是同一个函数，不存在第二个判定。
- 加载范围始终是全部模型，与 CI 一致；不提供按文件子集校验的参数，避免出现"子集绿、全量红"。

### 4.2 `model.query`
- **输入**：`{sparql: string, limit?: int}`，`limit` 默认 1000。
- **输出**：SELECT 返回 `{kind: "select", variables, rows: [{var: {value, short, termType}}], truncated}`；ASK 返回 `{kind: "ask", value: bool}`；CONSTRUCT/DESCRIBE 返回 `{kind: "graph", triples: [[s, p, o]], truncated}`。
- **只读**：执行走 pyoxigraph `Store.query`，它只接受查询，更新语句会解析失败，返回 `QUERY_ERROR`。查询的图包含源文件、构建生成的三元组（直连三元组、`aisep:notation`、`arch:approvalState`）以及全部本体和对齐（`onto_files(..., "all")` L179–186，载入在 L220–221、L237）。
- **校验层**：只做 L0。模型有违规时也照常查询，L0 问题放在 `warnings` 里返回。
- **映射**：**EXISTS**，`cmd_query` L1014–1033。

### 4.3 `model.impact`
- **输入**：`{element: string, mode?: "depends"|"ripple", depth?: int, allowInvalid?: bool}`，默认 `depends`、3、`false`。
- **输出**：`{start, mode, depth, invalidModel: bool, rows: [{iri, short, label, types, depth, path, related: bool}]}`
- **校验层**：先跑 L0–L2。有 Violation 且 `allowInvalid=false` 时返回 `MODEL_INVALID` 并附违规清单（G9）；`allowInvalid=true` 时照常计算，但置 `invalidModel=true`。
- **映射**：**EXISTS**，`cmd_impact` L1047–1076（拒绝逻辑在 L1060–1071）、`impact` L895–931（已经返回 rows，只需把打印改成结构化输出）、`expand` L1036–1044。依赖方向来自模块文件里的 `aisep:dependency`（L899）。

### 4.4 `model.findings`
- **输入**：`{}`。**输出**：`{warnings, infos, findings: [problem]}`。永不失败。
- **校验层**：L4（Must 级需求的追溯缺口、非枢纽节点缺少到枢纽的 refines、refines 指向已废弃节点即 R4、孤立元素）。
- **映射**：**EXISTS**，`cmd_findings` L1006–1011 → `l4` L853–890。

### 4.5 `model.diff`
- **语义**：只读、无状态，只读取 Git 对象，可以从任意 worktree 调用（各 worktree 共享对象库）。v1 只比较已提交内容（附录 C）。
- **输入**：`{model: string, head: string, base?: string, mainBranch?: string}`。`head`、`base` 是任意 Git 引用（分支名、commit）。不给 `base` 时取 `git merge-base <mainBranch> <head>`；`mainBranch` 默认 `main`。
- **输出**：
  ```json
  {"base": "40-hex", "head": "40-hex", "mergeBase": true,
   "counts": {"elements": {"added": 0, "modified": 0, "removed": 0},
              "relationships": {"added": 0, "modified": 0, "removed": 0}},
   "elements": [{"iri", "short", "change": "added|modified|removed", "types", "label", "file"}],
   "relationships": [{"iri", "short", "change", "type", "source", "target", "file"}]}
  ```
- **算法**：
  1. 分别在 `base` 和 `head` 上用 `git ls-tree -r` 列出 `models/<model>/*.ttl`，用 `git show <ref>:<path>` 读取内容，用 `ox.parse` 解析（与 L0 同一解析器，L207–218）。
  2. 按主语 IRI 把三元组分组。只看 `{base}model/<model>/` 下的主语；作者文件不使用空白节点（现有例子里没有），遇到时归入引用它的 IRI 主语。
  3. 只在一侧出现的 IRI 记为新增或删除；两侧都有但三元组集合不同的记为修改。
  4. 有 `arch:source` 的主语算关系，其余算元素。改关系类型会表现为一删一增（§8.2）。
  5. 只比较作者写的三元组，构建派生的三元组（如 approvalState）不参与。批准记录、AI 活动作为元素出现在差异里。
- **两种用途**（ADR-013）：
  - 工作台"AI 进行中"区域：每个编排器会话以分支名为键，调用 `{model, head: <分支名>}`，读取 `counts`。
  - 关口页的模型差异图：调用 `{model, head, base}`，读取完整清单。base、head 通常就是批准记录关联活动的 `baseCommit`、`headCommit`。
- **前提**：模型文件与会话改动的代码在同一仓库、同一分支（附录 C）。
- **映射**：**GAP**。可复用 `ox.parse` 的用法（L207–218）、`short`（L104–112）和 `model_graph_of`（L470–475）。需要新写 Git 读取、主语分组和分类。

## 5. 工具 ↔ 规范 ↔ 原型追溯表

| §8.3 行 | 本文 | aisep.py / 规则映射 | 状态 |
|---|---|---|---|
| `model.add_element` | §3.1 | 校验：`run_check` L948–950；TypeShape/InModelShape/LabelShape（aisep-core shapes L29/L53/L73）；R2 L643–655；G7 L620–641。写入：无 | GAP（校验复用 EXISTS） |
| `model.add_relationship` | §3.2 | 前置判定：`l1_notation_mixing` L657–691（§7.3、G5）、`l1_refines` L693–723（§7.2）、`l2` L726–759 + `rt_table` L765–778；IRI：`Ctx.uf` L230、`nearest` L255–259。写入：无 | GAP（规则 EXISTS） |
| `model.remove` | §3.3 | 找引用：`relationships` L316–319、`src_quads`；兜底：EndpointShape（aisep-core shapes L126 起）。级联逻辑：无（§8.2"未原型化"） | GAP |
| （扩展）`model.set_labels` | §3.5 | 校验：`run_check` L948–950、LabelShape（aisep-core shapes L73）。改写：无 | GAP（校验 EXISTS，扩展 §8.3） |
| `model.check` | §4.1 | `cmd_check` L953–962、`run_check` L948–950、`l1` L491–539、`l2` L726–759 | EXISTS |
| `model.validate` | §4.1 | `cmd_validate` L965–972、`l3` L819–848 | EXISTS |
| （扩展）`model.gate` | §4.1 | `cmd_gate` L975–989（G10） | EXISTS（扩展 §8.3） |
| `model.query` | §4.2 | `cmd_query` L1014–1033、`onto_files` L179–186 | EXISTS（查询核心）；`limit`/`truncated` 为新增 |
| `model.impact` | §4.3 | `cmd_impact` L1047–1076（G9 L1060–1071）、`impact` L895–931 | EXISTS |
| `model.findings` | §4.4 | `cmd_findings` L1006–1011、`l4` L853–890（含 R4） | EXISTS |
| `governance.record_approval` | §3.4 | `approval_problems` L396–433（G1、EG11/13/15/16/25/26）、`activity_problems` L435–468（EG17–24）、R3c `l1` L510–514、`derive_approval_state` L337–380。写入、默认值、Git 取值：无 | GAP（校验与推导 EXISTS） |
| `model.diff` | §4.5 | 仅可复用 `ox.parse` 用法 L207–218、`short` L104–112 | GAP |

**全部工具共有的新建工作**：MCP stdio 外壳；把命令函数改为返回结构化结果（`report` L940–945 等）；§2.2 文件选择；§2.3 写入—校验—回滚；§2.5 错误码。

## 6. 决定与待决问题

已决（2026-11-20 用户拍板，均按建议）：
1. **改名工具**：新增 `model.set_labels`（§3.5），作为对 §8.3 的扩展。
2. **Turtle 写回格式**：按主语块追加和删除，保留注释与顺序；文件不符合"一个主语一个块"时拒绝写入。
3. **谁来提交**：Server 只改工作区文件，不执行 `git commit`；由客户端提交，并由 pre-commit `gate` 把关。
4. （见下，待决）
5. **已有违规时的写入**：只拒绝新增的 Violation（§2.3），已有违规的模型可以逐步修好；提交时仍由 `gate` 最终把关。

待决：
4. **AI 代理的身份与活动 IRI**：规范 v0.4 附录 C 已登记 `prov:Agent` 目前不可用，代理只能是 `arch:Stakeholder`。建议每个编码代理在 `governance.ttl` 建一个 Stakeholder（例如 `:agentClaudeCode`），活动 IRI 采用 `{model}activity-{yyyymmdd}-{slug}` 并回填规范 §3 的 IRI 表。是否同意？
