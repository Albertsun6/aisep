# AISEP 第二步：元模型规范（v0.4）

状态：§14 的 D1–D10 已于 2026-11-19 全部按建议拍板（ADR-011）；v0.3 = v0.2 + 三轮审计和第二次 GPT 评审之后补的 R1–R4、G1–G10，全部已在原型里实现并验证。v0.4 = v0.3 + “AI 进行中”的数据来源（ADR-013）：新增 `aisep:AgentActivity`（§6.7）、批准记录的 `aisep:activity`（§6.6）、MCP 的 `model.diff` 与 `governance.record_approval` 改动（§8.3）；AgentActivity 与 `model.diff`、`governance.record_approval` 已在《MCP Server 接口设计》中定稿（ADR-014）。依据：`spike-linked-archi/spike-result.md`（第一步结论）、《方法论总纲（草案1）》§6/§6a、《AISEP 架构原则》、`decisions.md`（ADR-003/004/007/008/009/010）。
基线：Linked.Archi core 0.6.0 + ArchiMate 4.0（vendored，按 SHA256 锁定）。命名空间先用占位符 `https://aisep.example/`，第三步建正式仓库前统一替换。
原型：`metamodel-prototype/`（179 项测试全部通过，详见 [`docs/history/metamodel-spec-prototype-and-revisions.md`](history/metamodel-spec-prototype-and-revisions.md) 的「§15」）。修订与辩论记录见同一文件的「附 B」，已知限制见本文附 C。

## 0. 一页摘要

- **底座照搬 Linked.Archi core**：元素 `arch:Element`、关系 `arch:QualifiedRelationship`、视图 `arch:View`、容器 `arch:Model`、记法清单 `arch:Metamodel`。AISEP 不发明新的原语。
- **枢纽记法 ArchiMate 4.0**。其他记法用 `rdfs:subClassOf`/`subPropertyOf` 挂到 4.0 上，这层对齐**由 AISEP 自己写**（ADR-010）。
- **AISEP 自己补的部分**：闭世界规则、写入层（只写限定关系）、记法混用规则、`refines` 层级规则、按模块划定校验范围、影响分析口径（作为数据）、批准记录（ADR-009）、验证扩展、代码追溯扩展、IRI 与版本策略。
- **对外形态**：以上能力都通过 MCP Server 暴露（ADR-008）；本规范定义它的语义契约（§8.3）。
- **第一批模块**：ArchiMate 4.0（枢纽）、BPMN、UML（子集）、DDD（新建，基于 Context Mapper CML）；扩展：治理与批准、架构决策（ADR）、质量、验证、代码追溯。

## 1. 架构原则如何落到元模型

| 原则 | 元模型里的硬规则 |
|---|---|
| 一 单一事实来源 | 一个事物在一种记法里只有一个节点；不同记法里的表示用 `arch:refines` 按层级连接（§7.2）。关系只存限定关系资源（§8）。`approvalState` 由批准记录推导，不手填（§6.6）。 |
| 二 模型即资产 | 模型是 Git 里的 Turtle 文件；所有能力都可以从命令行或 MCP 调用，可以进 CI（§10）。 |
| 三 全程可追溯 | 跨记法连接只有固定几种（§7.1）；影响分析口径定义成数据（§9）。 |
| 四 标准优先 | 优先复用 ArchiMate 4.0、BPMN 2.0、UML 2.5、CML、OSLC、SPDX、PROV-O；AISEP 自己定义的部分本身也是带版本的模块（§5）。 |
| 五 自动执行，人工把关 | 校验分层，自动运行（§10）；五个关口的批准是模型里的实体（§6.6）。 |

## 2. 存储与引擎

- **一个模型 = 一个目录 = 一个命名图**：`models/<model-slug>/*.ttl`，目录里可以按记法拆成多个文件；图 IRI = 模型 IRI；每个成员都写 `arch:inModel`。
- **目录**（第三步落地）：`vendor/`（上游，只读）、`modules/<模块>/`（AISEP 的本体、shapes、对齐、测试）、`models/`、`build/`（生成物，不提交）。
- **引擎分工**：pyoxigraph 负责存储、查询、读 RDF 1.2、L1/L2 检查；pyshacl 只跑 SHACL Core 和能通过它语法检查的 SPARQL 约束（不能含 `MINUS`，不能含 `SERVICE` 字样）。
- **作者写的 Turtle 里禁止出现 `rdf:reifies` 和 `<<( )>>`**。

## 3. 标识（IRI）策略

| 对象 | 格式 | 例子 |
|---|---|---|
| AISEP 模块本体 | `{base}ont/{module}#` | `https://aisep.example/ont/ddd#BoundedContext` |
| 模型 | `{base}model/{model-slug}/` | `https://aisep.example/model/procurement/` |
| 元素 | `{model}{slug}` | `…/procurement/quoteApproval` |
| 关系 | `{model}rel-{源slug}-{直连谓词本地名}-{目标slug}`，重名时加 `-2`。直连谓词本地名取关系类最近的 `arch:unqualifiedForm`；类没有声明时取类本地名，首字母小写。 | `…/procurement/rel-supplier-assignedTo-quoteApproval` |
| 视图 | `{model}view-{slug}` | `…/procurement/view-quote` |
| 批准记录 | `{model}approval-{yyyymmddHHMMSS}-{slug}`（UTC；2026-11-20 前的存量记录按 `{yyyymmdd}` 命名，不改） | `…/procurement/approval-20261119-arch-baseline` |
| AI 活动 | `{model}activity-{yyyymmddHHMMSS}-{headCommit 前 7 位}`（UTC），重名时加 `-2` | `…/procurement/activity-20261120093015-9c41e07` |

- slug 用可读英文 camelCase。**一经创建不改**：改名只改标签。改标签经 `model.set_labels` 写入（§8.3）。IRI 由写入层生成（§8），不靠人记规则。
- 跨模型引用直接写对方的 IRI；被引用元素被删除时 L1 报错（原型已验证）。
- 修订历史交给 Git。
- 现有手写 IRI 不按本表重命名（slug 一经创建不改）；本表只约束写入层新生成的 IRI。

## 4. 三原语骨架（AISEP 最小必填）

**元素**
- `rdf:type`：**恰好一个最具体的类**，必须是已加载模块里声明过的类，或者其子类链能回到已声明的类。允许额外断言它的超类（导入器常这样做，语义上是冗余的）；**不允许出现两个互不为超类的类型**。
- `arch:inModel`：恰好 1 个。只对 `{base}model/` 下的 IRI 强制，避免误伤本体里的个体。
- 名称：`skos:prefLabel` **恰好一个 `@zh`**；英文名放 `skos:altLabel "…"@en`。上游 BPMN/UML 的 shapes 要求 prefLabel 最多一个，用这个办法两边都满足。junction、gateway、关系资源可以没有名称（`aisep:labelOptional`）。
- 可选：`skos:definition`、`arch:conceptOwner`、`arch:architectureState`。`arch:approvalState` **不手填**（§6.6）；`aisep:notation` 由类型推出，也不手填。

**关系**
- 一个限定关系资源（`am4:Serving` 等），带 `arch:source`、`arch:target`、`arch:inModel`，各恰好 1 个。
- 直连三元组由构建生成，**作者不写**（§8）。端点必须是某个模型里的元素，或者是关系（上游允许关系指向关系）。
- 必须遵守记法混用规则（§7.3）。

**视图**
- `arch:Diagram`/`arch:Catalog`/`arch:Matrix`，恰好一个 `arch:viewConformsToViewpoint`；成员用 `arch:inView` 指向视图。
- 布局坐标存放在 `views/<视图>.layout.json`，不进语义模型；不使用 core-vis（CC-BY-SA）。

**禁用**：`arch:partOfModel`、`arch:exposedInView`、`arch:contains`（L1 报错）。

**一个元素只属于一个记法**：它的所有类型（化简到最具体的那个之后）必须属于同一个记法模块；冗余的超类也只能来自本记法。跨记法的"混合类型"一律改用 `arch:refines`（L1 报错）。

**模型文件不能修改元模型**：模型文件里唯一允许出现的 schema 级三元组，是"单父类特化"，即 `:X rdfs:subClassOf <一个已声明的元素类>`，父类恰好一个，可以附带名称和定义。下面这些都在 L1 报错：声明属性或子属性、一个类有多个父类、以模块或上游术语为主语的三元组、在模型里写 `aisep:assertedShortcut`/`aisep:dependency`/`arch:unqualifiedForm`。这些注解只有写在模块文件里才生效。父类必须是 Language 或 Extension 模块里的**具体类**，不能是 `arch:Element`、`arch:QualifiedRelationship` 这类抽象根类。模型文件也不能往模块的概念表里添加成员（例如自造一个关口）。（原型审计发现：如果不加这条，模型文件可以绕过单一类型、禁手填 approvalState、派生捷径 Warning 等规则。）

**谓词也是闭世界**：模型文件里用到的每个谓词，必须是已加载模块或上游本体声明过的属性，或者在一个小白名单里（`rdf:type`、SKOS 名称与定义、`dcterms:isReplacedBy`、`owl:deprecated`、`prov:generatedAtTime`、`prov:startedAtTime`、`prov:endedAtTime`、`prov:wasAssociatedWith` 等）。两个模型元素之间的连接，必须是限定关系资源；能直接写成谓词的只有几种追溯属性（`aisep:approves`、`ad:relatedConcept`、`aisep:activity`、`prov:wasAssociatedWith` 等）；其中 `aisep:activity` 只能用在批准记录上、`prov:wasAssociatedWith` 只能用在 `aisep:AgentActivity` 上（L1 报错）。（GPT 评审发现：如果不加这条，一个自定义谓词就能绕过全部关系规则。）

## 5. 模块体系

- 每个模块是一个 `arch:Metamodel` 清单，带这些属性：
  - `aisep:moduleKind` ∈ {Language, Extension, Alignment, Framework}。
  - `aisep:loads`：按加载顺序列出依赖的文件。
  - `aisep:shapesFile`。
  - `aisep:alignmentFile`：只包含子类/子属性公理。
  - `aisep:impactFile`：影响分析口径的覆盖，必须在清单里声明才会生效。
  - `aisep:inheritsHubRules`：只对 Language 模块有意义，见 §10.2。
  - `aisep:notationLevel` ∈ {code, design, hub}，见 §7.2。
  - `aisep:ownsNamespace`。
  - `owl:versionInfo`（semver）。
- 对齐公理**只放在 AISEP 自己的图里**，不往第三方词汇文件里写。上游的 SKOS 映射文件原样保留，只当文档用。
- 每个模块都带 `tests/valid` 和 `tests/invalid`。原型的 8 个模块共 83 个用例，每条规则至少各有一个正例和一个负例。

## 6. 第一批模块

### 6.1 ArchiMate 4.0（枢纽，Language，level=hub）
- 原样使用 vendored 的 onto、shapes、relationship-tables、viewpoints。补丁：`am4:Grouping`、`am4:Location` ⊑ `am4:CommonDomainElement`（OWL 和分类表不一致，以分类表为准）。
- **"通用域风味"规则**（business/application/technology）：沿分派链推出，只用于查询和视图，不进校验。**未原型化。**
- 上游 `archimate4_principle-shapes` 里有 6 条约束 pyshacl 不接受，先不用。

### 6.2 BPMN（Language，`inheritsHubRules=false`，level=design）
- 采用完整的 `bpmn:`（`https://meta.linked.archi/bpmn/onto#`），不用 bpmn-lite。
- 对齐只升格上游标为 closeMatch 的项：Process/SubProcess ⊑ am4:Process；Event ⊑ am4:Event；SequenceFlow ⊑ am4:Triggering；MessageFlow ⊑ am4:Flow；DataObject ⊑ am4:BusinessObject；Collaboration ⊑ am4:Collaboration。
- **[D4]** Task、Lane 不升格（上游只标为 relatedMatch）。泳道和参与者与 am4 角色之间的对应，上游没有任何映射（v0.1 的说法有误）。BPMN 节点进入枢纽的唯一方式是 `arch:refines`（§7）。一个 BPMN 节点只要**被测试验证或被代码实现**，就必须经 refines 链连到继承枢纽规则的节点（am4 或 DDD）；否则 L4 报"追溯缺口"。（UML 节点同理。）
- 原型证实：任务 → 网关 → 任务的连线在本规则下通过；把同一份对齐放进 am4 校验则会误报。

### 6.3 UML（Language，子集，`inheritsHubRules=false`，level=code）
- 第一批：Class、Property、Operation、Association、Generalization、Interface、Component、Package、Activity、Action、StateMachine/State。
- 只对齐语义明确的：Interface ⊑ am4:ApplicationInterface；Activity ⊑ am4:Process；Generalization ⊑ am4:Specialization；Node/Device/Artifact/ExecutionEnvironment ⊑ 对应的技术层类。
- 多义的 `uml:Class`、`uml:Component` 不做子类对齐，只能通过 `arch:refines` 指向 DDD 或 am4 节点。

### 6.4 DDD（Language，新建，`inheritsHubRules=true`，level=design）
来源是 Context Mapper CML（Apache-2.0），概念用 `skos:exactMatch` 对到 CML 名和 jMolecules 注解；不复制 ddd-crew 的文字。

| DDD 概念 | ⊑ ArchiMate 4.0 | 备注 |
|---|---|---|
| Domain、ContextMap | Grouping | |
| Subdomain | Capability **[D2]** | `ddd:subdomainType` ∈ {Core, Supporting, Generic} |
| BoundedContext | ApplicationComponent **[D1]** | `ddd:contextType` ∈ {Feature, Application, System} |
| Team | BusinessActor | |
| Aggregate / Entity / ValueObject / ReadModel | DataObject | |
| DomainEvent | Event | |
| Command | Event **[D3]** | 可选 `ddd:payload` → DataObject，承载命令数据 |
| DomainService | Function | |
| ApplicationService | Service | |
| Policy | Process | |

| DDD 关系 | ⊑ am4 关系 | ArchiMate 4.0 关系表 |
|---|---|---|
| UpstreamDownstream（含 CustomerSupplier） | Serving | AC→AC：**只允许作为派生关系**（`permitsDirect=false`） |
| Partnership、SharedKernel | Association | |
| owns（BC → Aggregate） | Assignment | 可以直接画 |
| contains（Aggregate → Entity/VO） | Composition | 可以直接画 |
| implements（BC → Subdomain） | Realization | AC→Capability：只允许作为派生关系 |
| triggers（DomainService/Policy → Event） | Triggering | |

- **"派生捷径"规则**：ArchiMate 表里标为"只能派生"的关系，AISEP 默认在 L2 报 Warning。模块可以给自己的关系类声明 `aisep:assertedShortcut true`，表示"作为建模约定接受直接画"；这样不再报 Warning，影响分析也照常计入。DDD 的 UpstreamDownstream 和 implements 都这样声明。原因是派生引擎不在第一批范围内，上下游、实现子域这类关系又必须能直接写。
- DDD 自带的 shapes：CustomerSupplier 不允许 CF/OHS 角色；Partnership/SharedKernel 不带角色；每个 Aggregate 恰好 1 个根 Entity、恰好被 1 个 BC 拥有；暴露的 Aggregate 必须属于上游 BC。DomainEvent 名称用过去时的 Warning **未原型化**。

### 6.5 验证扩展（Extension）
- `aisep:TestCase` ⊑ `arch:Element`，**不挂到任何 am4 类下**。
- `aisep:Verification`（限定关系，TestCase → 任意元素），直连谓词 `aisep:verifies`。
- `aisep:AcceptanceCriterion` ⊑ `am4:Requirement`：通过 `am4:Aggregation` 从属于父需求（表里可以直接画），可选 `aisep:gherkin`。
- `aisep:TestResult`：`aisep:resultOf` → TestCase；`aisep:verdict` ∈ {Passed, Failed, Blocked, Skipped, Error}；`prov:generatedAtTime`。
  - 可选的运行出处（模块 v0.3.0）：`aisep:testedCommit`（被测提交，40 位小写十六进制字符串，写法同 `aisep:headCommit`）、`aisep:ciRun`（产出该结果的 CI 运行或作业的网址，如 GitHub Actions 的 run 或 job 网址，IRI）、`schema:codeRepository`（代码仓库网址，IRI），各至多一个（EV11–EV13）。`aisep:testedCommit`、`aisep:ciRun` 只能写在 TestResult 上（EV14）；提交锚点挂在每次运行的结果上，不改已批准的代码位置。
- `aisep:priority` ∈ {Must, Should, Could, Wont}（MoSCoW），挂在需求上。**只有 Must 级**的需求或验收标准没有 TestCase 时，才算追溯缺口（L4）。
- 概念名用 `skos:exactMatch` 对到 OSLC QM/RM；不导入 OSLC。

### 6.6 治理与批准（Extension，ADR-009）
- `aisep:ApprovalRecord` ⊑ `arch:Element`。这是作者写的唯一治理事实。记录本身必须是模型元素（IRI，`arch:inModel` 指向一个 `arch:Model`），不能是空白节点，也不能是不属于任何模型的资源，否则 L1 报错，不参与推导；合并时另拒绝模型源文件里任何空白节点形式的批准记录或 AI 活动。字段：
  - `aisep:gate` ∈ {需求确认, 架构决策, 设计评审, 代码合并, 发布上线}，即架构原则五的五个关口（SKOS）；
  - `aisep:decision` ∈ {Approved, Rejected}；
  - `aisep:approvedBy` → 人（必须是 `arch:Stakeholder` 的实例，且不能是 `aisep:AIAgent`；AI 不能批准，原则五）；
  - `prov:generatedAtTime`；
  - `aisep:approves` → 一个或多个元素、模型或 ADR。允许集合：带 `arch:inModel` 的元素（不含 `aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Stakeholder`）、`arch:Model` 实例、ADR（`ad:Decision`）；限定关系和视图不可被批准，它们的改动只计入所属模型、不计入端点元素。目标存在但类型不在集合内的记录不合法（L1 报错，不参与推导；ADR-016）；目标不存在的按原口径处理（不因此报 L1）；
  - `aisep:evidence`（**必填**，恰好一个）：批准时那次校验报告对应的 git commit（40 位十六进制）或 `sha256:<64 位十六进制>`，证明"批准的是哪个版本"。经 MCP 写入时自动填写：取调用方给出的 headCommit（人评审的那个提交；有活动时等于该活动的 `aisep:headCommit`），写入层核对它与分支头之间只有批准提交：其间不得有合并提交，每个提交都恰好带一个值等于所新增记录 evidence 的 `AISEP-Evidence` trailer、恰好新增一个 `models/<slug>/governance/` 下的 `.ttl` 普通文件（不进子目录，不修改、不删除已有文件）、且源图只新增一条批准记录（可另带一条被它引用的 AI 活动；无修改、无删除）；该核对在提交前持锁复做一次，提交后父提交不是被核对的分支头时撤回。写入前在该提交上运行 `gate`，结论为 Approved 而 gate 未通过时拒绝写入。

    批准提交判据：一个提交只有一个父提交，恰好带一个 `AISEP-Evidence` trailer 且其值等于该提交新增记录的 evidence，相对父提交恰好新增一个文件（路径为 `models/<slug>/governance/<文件名>.ttl`，不在子目录，文件模式 100644），不修改、不删除已有文件，且相对父提交源图只新增一条批准记录，另可带至多一条被它引用的 AI 活动（无修改、无删除）；新文件里只能有这条记录及其活动，文件名等于记录 IRI 的本地名。批准记录的 evidence（有活动时即活动的 headCommit）到所在分支头之间只允许出现满足该判据的提交；evidence 等于分支头是其特例。写入时由写入层核对；合并进受保护分支前由 CI 用同一判据再核对一次（范围 `evidence..分支头`，不含合并提交本身），查本次合并新增的全部合法记录（同一合并请求内被同关口、`approves` 为其超集、时间（按时区归一化）更晚的新记录取代的除外）。合并时另要求：新记录的 evidence 必须是 40 位 commit，结论为 Approved 的新记录在 evidence 上运行 `gate` 须通过，生成时间不得晚于检查时的当前时间 5 分钟以上（不与可伪造的提交时间比）；被批准对象必须在 evidence 中存在，且其内容（模型按它自身、全部成员及以成员为端点的关系，ADR 按它及其直接引用的组成节点）在 evidence 与合并结果中必须相同；目标分支上已有的批准记录和 AI 活动不得修改或删除；修改目标分支上已批准的元素，或新增目标分支上已显示为批准但尚不存在的元素，须在同一合并请求里有新的、结论为 Approved 的合法批准记录覆盖（关口不限），且它须是该对象在合并结果中生效的那条记录；删除目标分支上已批准的元素一律拒绝（被批准过的元素只能退役，Q6④）；新增 AI 活动的 baseCommit、branch 须与按目标分支重算的值一致；合并请求头与合并结果的模型源文件里不得有空白节点形式的批准记录或 AI 活动；在合并结果上运行 `gate`。任一不通过即拒绝合并，须在新的提交上重新过关口。CI 通过后目标分支可能前进，执行合并的人在合并前用同一检查对当前目标分支头重算，不过不合。只含批准提交、至少新增一条批准记录、且新增的 AI 活动都被新记录引用的合并请求不要求再过关口，上述核对、`gate` 与人工合并批准照常；夹带其他提交的按普通合并请求处理。

    已在主分支上的提交只能批准发布关口，其他关口拒绝；判断时从被批准的提交沿第一父提交回溯、跳过批准提交，取得到的第一个提交（有效内容提交）。这类批准不直接提交到主分支：从被批准的那个提交拉短命分支，只提交这一条批准记录，经合并请求合入后删分支；这类记录只能经只含批准提交的合并请求合入，夹带其他提交的合并请求中出现即拒绝。这类批准不带 AI 活动；evidence 是被发布的主分支提交，必须是目标分支头的祖先，被批准对象在 evidence 到目标分支当前头之间不得被修改或删除（内容已变须重新选被发布的提交）。只有结论为 Approved 时被发布的提交才打 `release/{yyyymmdd}-{前 7 位}` 标签（或版本号标签 `release/v…`），Rejected 不打；标签是对外的发布指针，被发布提交的可达性由主线保证。

  - `aisep:activity`（可选，最多一个）→ 一条 `aisep:AgentActivity`（§6.7），表示这次批准针对的是哪次 AI 活动；必须是模型元素（IRI，带 `arch:inModel`），不能是空白节点。evidence 是 40 位 commit 时，必须等于该活动的 `aisep:headCommit`，否则 L1 报错。
  - 文件：每条批准记录单独一个文件 `models/<slug>/governance/<记录本地名>.ttl`（同次写入的 AI 活动在同一文件）；批准只新增文件，不改已有文件。早先写在 `governance.ttl` 里的记录与人员不搬迁，`governance.ttl` 仍放 `arch:Stakeholder` 等治理类元素。
- **`arch:approvalState` 由构建推导**，只推导给可被批准的元素（元素部分与 `aisep:approves` 的允许集合一致；模型、ADR 只在有记录时有状态。第四轮 R4-5、ADR-016、ADR-017）：带 `arch:inModel` 的 `arch:Element`，不含限定关系、`aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Stakeholder`，这几类没有 approvalState。取值：取（按时区归一化，不带时区的按 UTC）最近一条**合法**批准记录的结论（不合法的记录不参与推导，构建时报 Warning）；没有记录则为 Proposed；元素本身被合并、替换（带 `dcterms:isReplacedBy`，且目标必须是某个模型里的元素，否则 L1 报错，也不触发）则为 Superseded。`aisep:Rejected`、`aisep:Superseded` 是 AISEP 补的取值，上游只有 Proposed/Approved。同一元素有两条时间相同（按时区归一化后）但结论不同的记录时，L1 报"批准有歧义"。手填 approvalState，包括通过子属性间接写入，都在 L1 报错。
- 工作台只展示批准记录、触发新增批准记录，不保存状态（ADR-009）。
- 架构决策采用 vendored 的 `arch-decision`（ADR：Decision/Option/Force），用 `ad:relatedConcept` 连接元素。它的 shapes 读的是直连三元组，所以 L3 必须跑在构建后的图上（§10）。
- 质量：`arch:hasQualityMeasure` + ISO 25010 个体；补 `aisep:value`、`aisep:unit`、`aisep:target`、`prov:generatedAtTime`。

### 6.7 代码与交付追溯（Extension）
- `aisep:CodeLocation`：`schema:codeRepository`（命名空间统一用 `https://schema.org/`）、`aisep:path`、可选 `aisep:symbol`、`aisep:swhid`。
- `aisep:Implementation`（限定关系，CodeLocation → 设计元素），直连谓词 `aisep:implements`。
- `aisep:Deployable` ⊑ `am4:Artifact`，带 `aisep:packageUrl`（purl）。Artifact → ApplicationComponent 的 Realization 可以直接画。
- `aisep:AIAgent` ⊑ `arch:Element`、`prov:SoftwareAgent`（aisep-core 另声明 `prov:SoftwareAgent ⊑ prov:Agent`；不加载 PROV-O 本体）：执行任务的 AI 代理，按元素通则写名称和 `arch:inModel`。
- `aisep:AgentActivity` ⊑ `arch:Element`、`prov:Activity`（ADR-013、ADR-014）：一次**已完成**的 AI 活动。只在任务过关口时由 `governance.record_approval` 写入，与批准记录在同一次提交里；进行中的状态不进模型仓库。一个（sessionRef, headCommit, branch）只有一条，同一 head 过多个关口时复用；IRI 见 §3。字段：
  - `skos:prefLabel` 恰好一个 `@zh`（缺省"AI 活动：{分支}"，建议写任务标题），`arch:inModel` 恰好一个；活动必须是 IRI、`arch:inModel` 指向一个 `arch:Model`，不能是空白节点（否则 L1 报错）；
  - `prov:wasAssociatedWith` → 执行的代理，恰好一个，必须是 `arch:Stakeholder` 或 `aisep:AIAgent` 的实例；
  - `prov:startedAtTime`、`prov:endedAtTime`，各恰好一个 xsd:dateTime，开始不晚于结束（按时区归一化，不带时区的按 UTC）；
  - `aisep:sessionRef`：外部编排器的会话标识，非空字符串，恰好一个；对元模型不透明，不绑定 AO；
  - `aisep:branch`：分支短名（不含 `refs/heads/`），非空字符串，恰好一个；
  - `aisep:baseCommit`、`aisep:headCommit`：各恰好一个 40 位十六进制 commit，**只由写入层填写**：headCommit 是被批准的那个 commit（写入层核对它与分支头之间只有批准提交），baseCommit 是它与模型主分支的 merge-base。L1 只校验格式。
  - **不存"作用于哪些元素"**：由 `model.diff(baseCommit, headCommit)` 实时算出（§8.3）。
- 提交、构建、部署的溯源只定义词汇（PROV-O），不做接入。

## 7. 跨记法追溯

### 7.1 跨记法连接只有三类
1. **枢纽关系**：am4 关系类（以及继承枢纽规则的 DDD 关系），两端都必须是枢纽可判定的元素。
2. **`arch:refines`**：同一事物在更细的记法里的表示（§7.2）。
3. **追溯关系**：`aisep:Verification`、`aisep:Implementation`、`aisep:approves`、`ad:relatedConcept`。

通用遍历：`?r a/rdfs:subClassOf* arch:QualifiedRelationship ; arch:source ?s ; arch:target ?t`，类型判断走 `rdf:type/rdfs:subClassOf*`。这条查询在构建后的图上运行（直连三元组已经归一化），所以不存在"漏掉作者手写的直连边"的问题。原型用一条完全不含记法专有谓词的查询，从 TestCase 出发走通了 21 条边、18 个节点：经过 am4、DDD 到达代码和可部署包；BPMN 和 UML 节点作为 refines 的叶子挂在路径旁边（它们是细化分支，不在主链上）。

### 7.2 `arch:refines` 的层级规则（同一性治理）
- **方向**：从细到粗，按 `aisep:notationLevel`：code（UML）→ design（DDD、BPMN）→ hub（am4）。refines 必须指向**更高层级**的记法（可以跨级，例如 UML 直接指向 am4）；同级或同一记法内**禁止**使用（同记法内的细化用它自己的 Specialization/Composition）。refines 指向已废弃或已被替换的节点时，L4 报 Warning，提示把追溯链迁移到替换它的节点。同一节点在不同层级的锚点之间是否互相一致（例如 UML 类的 am4 锚点是否等于它 DDD 锚点的 am4 锚点），第一批不检查。
- **无环**：由层级方向保证。
- **主锚唯一**：一个节点对每种更高级别的记法**最多 refines 一个节点**。被 refines 的那个节点就是它在该层级的主锚。
- **合并与拆分**：两个节点要合并时，保留一个，另一个标 `owl:deprecated true` 并加 `dcterms:isReplacedBy`，追溯链迁移到保留的节点上；拆分时，原节点也标 deprecated。不使用 `owl:sameAs`，不使用多类型。

### 7.3 记法混用规则（修复原型审计的漏洞 H）
- 记法 N 的关系类（例如 `bpmn:SequenceFlow`），两端都必须是记法 N 的节点。
- 核心的通用关系 `arch:Association`、`arch:HasPart`（以及模型里对它们的特化）也一样：只能连接同一记法的节点。
- 不同记法之间只能通过 §7.1 的三类连接。
- am4 关系类的两端由 am4 矩阵判定；端点类型若属于 `inheritsHubRules=false` 的模块（例如 BPMN 任务），在矩阵里视为未知类型，直接报错，并提示改用 refines。

## 8. 写入层

### 8.1 只写限定关系
- 作者（人或 AI）只写限定关系资源。构建时，对上游或 AISEP 声明了 `arch:unqualifiedForm` 的关系类生成直连三元组；没有声明的，保持只有限定形式。
- L1 规则：源文件里出现直连三元组即报错，并给出改写建议（原型对 am4、DDD、BPMN 三种记法都已验证）。

### 8.2 删除与变更
- 删除元素：一并删除以它为端点的关系、指向它的 `inView`、它作为 refines 目标的关系；或者拒绝删除并列出引用。
- 改关系类型 = 删掉旧资源、新建一个，IRI 跟着变。
- 删除由 `model.remove` 执行（接口文档 §5.5）。删除集从目标开始，反复加入以删除集成员为 `arch:source` 或 `arch:target`、且与目标同属一个模型的限定关系，直到不变；删除集成员在本模型文件里作为主语的三元组全部删除。判据在模型源文件上算，不用构建后的图。外部引用中，`arch:inView` 与 BPMN 成员属性（flowElements、flowNodeRefs、lanes、laneSets）摘除；其他谓词（含批准、替换、追溯、`bpmn:default`）与跨模型引用（含别的模型里以目标为端点的关系）一律拒绝并列出，提示改用 `owl:deprecated` + `dcterms:isReplacedBy` 退役。批准记录、AI 活动、模型本身不能删除。默认不级联（有牵连即拒绝并返回计划），`cascade` 显式开启；支持 dryRun。删除后不得引入新的 L0–L2 违规，否则整体不写。按主语块编辑文本，编辑后必须与预期的图等价，否则不写。

### 8.3 MCP Server 语义契约（ADR-008）
| 工具 | 语义 | 对应层 |
|---|---|---|
| `model.add_element` | 生成 IRI（§3），写入恰好一个类型、inModel、zh 名称 | 写入前在候选图上跑 L0–L2，只拒绝新增的违规；结果逐条标明违规是写前已有还是本次新增 |
| `model.add_relationship` | 只写限定关系；先查记法混用规则和矩阵，不合法就拒绝写入并说明原因 | L1/L2 |
| `model.remove` | 按 §8.2 级联删除，或者拒绝 | L1 |
| `model.set_labels` | 只改名称（`skos:prefLabel` @zh）、英文名（`skos:altLabel` @en）、定义（`skos:definition` @zh），IRI、类型、关系不变；§3"改名只改标签"的写入口。批准记录、AI 活动不能改 | 写入前在候选图上跑 L0–L2，只拒绝新增的违规 |
| `model.check` / `model.validate` | L0–L2 / L3 | §10 |
| `model.gate` | 只读，原子执行 L0–L4，一份合并结论；提交、CI 与关口页只认它（G10） | L0–L4 |
| `model.query` | 只读 SPARQL，跑在构建后的图上 | — |
| `model.impact` | §9 两种模式 | — |
| `model.findings` | L4；另返回 openViolations：同一份内容上 L0–L2 的全部违规（结构化发现项），供查看写入时被放过的遗留违规。openViolations 不新增层级，不计入 gate 结论 | L4（openViolations 复用 L0–L2） |
| `governance.record_approval` | 新增一条批准记录（不改状态字段）。顶层必填 branch、headCommit（有无活动都必填）；可选 expectedBaseCommit，只用于核对、不写入（不等于被拒收的 baseCommit）。写入层核对 headCommit 与分支头之间只有批准提交（无合并提交；每个提交恰好带一个值等于记录 evidence 的 `AISEP-Evidence` trailer、恰好新增一个 governance 目录下的 `.ttl` 普通文件、源图只新增一条批准记录（可另带一条它引用的 AI 活动）），提交前持锁复核。branch 不能是主分支；headCommit 已在主分支上（按有效内容提交判定，§6.6）时只接受发布关口、不接受活动信息；发布关口的 headCommit 必须在主分支上。可选活动信息只含代理、sessionRef、起止时间和标签：写入层算出 baseCommit，在同一次提交里写入 `aisep:AgentActivity`（分支、headCommit 取顶层值）并用 `aisep:activity` 关联；evidence 取调用方给出的 headCommit，generatedAtTime、baseCommit 由写入层填，不接受调用方传入 evidence、generatedAtTime、baseCommit。Approved 要求 evidence 处 gate 通过。每条记录新建一个 `governance/<记录本地名>.ttl`，只提交这一个路径，不跳过 pre-commit | L0–L2 + gate |
| `model.diff` | 只读。base 是 Git 引用（不给时取 head 侧 commit 与模型主分支的 merge-base）；head 有两种：Git 引用，或某分支检出的工作区（按分支名经 `git worktree list` 定位，只接受分支名，不接受路径）。工作区内容 = 该工作区模型目录下已跟踪 Turtle 文件的当前内容 + 未跟踪且未被忽略的新 Turtle 文件 − 已在工作区删除的文件。返回新增、修改、删除的元素和关系清单（按 IRI；同一 IRI 的三元组有变化算修改；改关系类型按 §8.2 表现为删除加新增）。比较的是两边模型源文件的并集图（构建前）；三元组在文件间移动、排版和注释变化不算修改。多个 merge-base 时报错，要求显式给 base。结果按 kind（element / relationship / view / governance / schema / other）分组计数；detail 取 summary / items / triples；标明 head 的种类、对应 commit 和工作区是否有未提交改动。工作区里某个文件解析失败时，结果标为不完整并列出失败文件，其余照常比较，失败文件里的主语不判为删除。无状态，不写任何东西，可从任意 worktree 调用 | L0 |

所有写操作都是 Turtle 文件的修改，进 Git；MCP 不保存任何不在文件里的状态。接口的具体设计见《MCP Server 接口设计》（`docs/mcp-interface.md`）。线上工具名把点换成下划线（`model.diff` → `model_diff`）。写工具只改工作区、不提交；`governance.record_approval` 例外，自己做一次只含 governance 文件的提交。

`model.diff` 同时服务两处：工作台"AI 进行中"区域（每个编排器会话按分支名算改动元素）和关口页的模型差异图，接口按这两个用途一起设计。"AI 进行中"缺省比较会话分支的工作区（含未提交改动），关口页差异图和批准只认已提交的 commit；前提是模型文件和会话改动的代码在同一个仓库、同一条分支上（见附录 C）。**不提供任何"上报进行中状态"的写工具**（ADR-013）。

## 9. 影响分析口径（作为数据）

每种关系类声明 `aisep:dependency` ∈ {Forward（目标依赖源）、Backward（源依赖目标）、Both、None}；子类继承父类，模块覆盖必须写在清单的 `aisep:impactFile` 里。

| 关系 | 依赖方向 | 读法 |
|---|---|---|
| Serving | Forward | 被服务者依赖服务者 |
| Realization | Both | 被实现者依赖实现者，实现者也必须符合被实现者 |
| Access | Backward | 行为依赖它访问的数据 |
| Assignment | Both | 执行者和行为相互依赖 |
| Composition | **Both** | 部分的存在依赖整体，整体的结构依赖部分（v0.1 写成 Backward，有误） |
| Aggregation | Backward | 整体依赖部分；部分可以独立存在 |
| Triggering、Flow、Influence | Forward | 下游依赖上游 |
| Specialization | Backward | 特化依赖泛化 |
| Association | None | 只在第 1 跳列出，标为"相关" |
| `arch:refines` | Backward | 细化方依赖被细化方 |
| `aisep:verifies`、`aisep:implements` | Backward | 测试、代码依赖设计 |

**两种模式**：
- **`depends`（默认）**：沿上表的依赖方向找，默认深度 3。回答"谁会被改坏"。
- **`ripple`**：除 Association 外一律双向，默认深度 3。回答"谁可能要一起改"，范围更大。

**模型有 L1/L2 违规时，impact 拒绝输出**（脏数据会污染影响结论），除非显式加 `--allow-invalid`，此时会在结果顶部打印警告。

spike 里 AI 试验用的 7 元素标准答案，其实是无向的 3 跳邻域，所以对应 `ripple` 模式。在原 spike 模型上，`depends` 模式得到 5 个元素（原型已验证）。v0.1 把"7 个元素"写成 `depends` 的回归用例，和表本身矛盾，已更正。

## 10. 校验分层

### 10.1 分层
| 层 | 做什么 | 引擎 | 何时跑 |
|---|---|---|---|
| L0 | 能解析 | pyoxigraph | 每次写入 |
| L1 | 闭世界：类型、必填项、禁用词汇、禁写直连三元组、禁手填 approvalState、悬空引用、记法混用、refines 层级 | pyoxigraph SPARQL | 每次写入 |
| L2 | 枢纽关系表查表 + 派生捷径 Warning | pyoxigraph + Python | 每次写入 |
| L3 | 完整 SHACL（含各记法自己的 shapes、闭合取值集） | pyshacl，跑在**构建后的图**上 | pre-commit 和 CI |
| L4 | 发现项：追溯缺口（Must 级）、孤立元素、视点不符 | pyoxigraph | CI、关口评审 |

- 原型实测（采购例子，6 个文件）：L0–L2 用时 0.06–0.14 秒，L3 用时 4.7–5.6 秒，所以 **pre-commit 跑 L0–L3**。原型审计发现，有些错误只有一层能抓到（取值集只在 L3，直连三元组只在 L1），只跑其中一层就会漏。
- L2 只查枢纽矩阵。BPMN、UML、DDD 自己的规则都在 L3，不另建快速表。
- **统一入口 `gate`**：原子执行 L0–L4，给出一份合并结论；**pre-commit 和 CI 只认 `gate`**。check、validate 只用于开发时的快速反馈。（GPT 评审指出：分开跑会出现"validate 绿、check 红"的结论分裂。）
- **批准记录的合法性只有一个定义**，L1、L3 和 approvalState 推导共用同一个函数，避免三处判断标准不一致（原型第三轮审计发现过这种不一致）。

### 10.2 对齐公理和校验范围
- **L3 跑 am4 shapes 时**，数据图里放入：枢纽和核心模块、`inheritsHubRules=true` 的 Language 模块、**所有 Extension 模块**（例如 `Deployable ⊑ Artifact` 必须常驻，否则 Deployable 会逃过矩阵）的对齐公理。不放入 `inheritsHubRules=false` 的 Language 对齐。
- 其他每个模块的 shapes，在"源文件 + 构建出的直连三元组 + 本模块依赖"上单独运行。
- 查询和影响分析加载全部对齐公理。

## 11. 版本与 vendoring
- `vendor/MANIFEST.json`：每个上游文件记录 URL、抓取时间、SHA256、许可证、`owl:versionInfo`。
- 升级上游是一次显式变更：抓取 → 生成差异报告 → 全部模块测试回归 → 人工批准（一条批准记录，关口为"架构决策"）。
- `arch:modelConformsToMetamodel` 指向 AISEP 模块 IRI；AISEP 模块按 semver 发版。

## 12. 许可证立场
- AISEP 自己的本体和 shapes 用 CC-BY-4.0，`NOTICE` 里署名 Linked.Archi。
- 允许引入：CC-BY-4.0（Linked.Archi 的大部分文件，含 arch-decision）、Apache-2.0（CML、jMolecules、OSLC 的概念名）。
- 不引入：core-vis、edgy（CC-BY-SA）、ddd-crew 的文字（CC-BY-SA）。SPDX、OSLC 只用 `skos:exactMatch` 引用。

## 13. 不在第一批范围
C4、Backstage 接入、TOGAF 内容元模型、ArchiMate 派生规则引擎、图形布局、成本扩展、ADM 框架实例化（第三步）、CI/CD 实际接入。

## 14. 决策（2026-11-19 已拍板，全部按建议采纳，见 ADR-011）

| # | 决策 | 建议 | 主要备选 | 依据与影响 |
|---|---|---|---|---|
| D1 | BoundedContext ⊑ ? | ApplicationComponent | Grouping | 两者在矩阵里都只能派生出 Serving/Flow（v0.1 的论据有误，已更正）。按语义选：BC "封装行为和数据"，更贴近组件；选 Grouping 则 BC 只是边界，不能被分派行为 |
| D2 | Subdomain ⊑ ? | Capability，并把 implements 声明为派生捷径 | Grouping | 能力地图、热力图可以直接复用 |
| D3 | Command ⊑ ? | Event + 可选 payload DataObject | DataObject | DataObject 不能触发行为 |
| D4 | BPMN Task/Lane 是否升格 | 不升格；要追溯的节点必须 refines 到 am4 | 升格 | 升格的话 ArchiMate 里流程数量会膨胀 |
| D5 | 作者只写限定关系 | 是 | 两种都写 | 单一事实来源；原型已验证 |
| D6 | 多类型元素 | 只允许一个最具体类型，可附带它的超类 | 完全禁止 / 完全允许 | 兼顾导入器习惯和校验的可预测性 |
| D7 | 影响口径 | §9 表 + 两种模式 | 只用一种模式 | 决定所有影响分析的答案 |
| D8 | 跨记法连接只允许三类（§7.1/§7.3） | 是 | 允许各记法关系随意跨接 | 不这样定，就会出现审计 H 那样两套规则都管不到的漏洞 |
| D9 | refines 的层级方向与主锚唯一（§7.2） | code → design → hub | 不设层级 | 防环、防一个节点挂多个主锚、防同记法内滥用 |
| D10 | approvalState 由批准记录推导（§6.6） | 是 | 允许手填 | ADR-009 + 单一事实来源 |

## 15. 原型验证结果（`metamodel-prototype/`）

已移至 [`docs/history/metamodel-spec-prototype-and-revisions.md`](history/metamodel-spec-prototype-and-revisions.md) 的「§15」，原文未改。

## 附 A：可直接粘贴到《总纲（草案1）》的更新

已移至 [`docs/history/metamodel-spec-prototype-and-revisions.md`](history/metamodel-spec-prototype-and-revisions.md) 的「附 A」，原文未改。

## 附 B：修订与辩论记录

已移至 [`docs/history/metamodel-spec-prototype-and-revisions.md`](history/metamodel-spec-prototype-and-revisions.md) 的「附 B（含 B.1–B.3）」，原文未改。

## 附 C：已知限制（第一批不处理）

- `model.diff` 的 worktree 模式读的是会话分支检出的工作区：会话的工作区已被清理（只剩分支）时退回只比较已提交内容；工作区里写到一半的文件会让结果标为不完整（失败文件里的主语不计）。index（暂存区）与磁盘不同时以磁盘为准。
- 分支差异的前提是模型文件和会话改动的代码在同一仓库、同一分支；模型仓库独立时，编码会话的分支里没有模型差异。

- 同一节点在不同层级的锚点是否互相一致（UML 类的 am4 锚点是否等于它 DDD 锚点的 am4 锚点），不检查。
- Verification、Implementation 指向已被替换的节点时，不提示迁移；多步替换链（旧 → 中 → 新）只提示第一步。
- 模型里声明的类不能用 deprecated/isReplacedBy 退役（R1 只允许名称和定义）；合并、拆分模式只适用于实例。
- "通用域风味"推导规则（§6.1）、DomainEvent 过去时 Warning（§6.4）、`rm` 级联删除（§8.2）没有原型化，留给 MCP Server 实现。
- G7 的"元素间直连"白名单包含 BPMN 结构属性（flowElements、lanes 等）和 `arch:hasQualityMeasure`、`ddd:exposedAggregate`。这是为了让合法模型通过而做的判断，未经异构评审。
- PROV-O 不整体加载；aisep-core 只声明 `aisep:AIAgent`，另在其对齐文件里加 `prov:SoftwareAgent ⊑ prov:Agent` 一条（ADR-010），其余 PROV-O 术语不可用，G7 白名单不变。
- 历史批准的差异图和 gate 重跑依赖 headCommit 仍可达。模型仓库禁用 squash 合并和 rebase 合并，批准提交只经普通 merge 进受保护分支（ADR-014）；落实要同时做到：托管平台关闭 squash、rebase 两种 PR 合并方式，受保护分支禁止 force push、限制直接 push，PR 合并保留原提交（cherry-pick、rebase 都会生成新的 commit id）。这些是仓库托管平台的设置，元模型和 MCP 不检查；合并时校验已要求新记录的 evidence 是合并请求头的祖先（发布批准还须是目标分支头的祖先）。绕过它合入、或分支未合并就删除时，旧 commit 可能被 GC，历史批准无法重跑；管理员绕过分支保护、force push 后重开合并请求，同样可能让已合入记录的 evidence 不再可达。本仓库已于 2026-11-20 配置：只允许普通合并（关闭 squash、rebase），`main` 受保护（必需检查 `gate`、`mergecheck`、`pytest`，不要求分支最新、禁止 force push 与删除、管理员同样受约束）；未要求平台上的 PR 评审批准（个人仓库没有第二人评审）。合并条件见 AGENTS.md「分支与合并」第 2 条：必需检查通过，且由没参与实现的 agent 独立评审通过。
- 合并时校验（evidence 到分支头之间只有批准提交、已有记录不可改、已批准元素改动须重批、合并结果 gate 等）、批准专用合并请求的判定、发布标签检查由 CI 的 `mergecheck` 执行（脚本 `aisep/mergecheck.py`），本仓库已把它设为受保护分支的必需检查；元模型和 MCP 不检查 CI 是否配上。不开"要求分支最新"、不用合并队列（个人账号的 private 仓库用不了合并队列），目标分支前进后必需检查不会自动重跑，所以合并前由执行合并的人用同一检查对当前目标分支头重算；绕过它直接在网页上点合并时，合并结果 gate 可能只对旧主线有效，这是残余风险。重算与合并之间也没有原子绑定：平台合并只能锁合并请求头、锁不了目标分支头，重算通过后目标分支仍可能前进；由合并串行、合并前再比对目标分支头、合并后核验父提交并在不过时回滚来压缩，余下为残余风险。重算、复核、合并后核验三步已写进 AGENTS.md 的合并条款（ADR-017），但只靠执行合并的人照做，没有机制强制；第四轮负例（`test_merge_check_negatives.py`）不在 CI 里，涉及 mergecheck 的合并请求是否在本地跑过，同样只靠执行合并的人核对。
- 普通合并请求不要求带批准记录，未经批准的模型改动可以进主分支（推导为 Proposed，ADR-016）。主线提交只能批准发布关口，所以主线上的 Proposed 元素要过其他关口，须从主分支拉分支、先有一个非批准提交（可以是空提交）再批；这是已拍板规则组合（ADR-015 U4①、ADR-016）的已知限制。
- 元素级批准不覆盖以它为端点的限定关系：合并请求只改一条关系的端点（如换掉 target）时，被连接的已批准元素不须重批，合并后仍显示 Approved。要约束连接，须按模型批准（模型的比较范围含以成员为端点的关系）。这是有意的口径（第四轮 G4-4，用户拍板），否则每加一条代码追溯都会触发对设计元素的重批。
- 视图从属不计入元素：`arch:inView` 三元组计入视图、不计入元素（与接口文档 §5.8 一致），所以合并请求只改已批准元素的 `arch:inView`（把它放进或移出某张视图）时，该元素不须重批。视图不可被批准（R4-5）：视图属于某个已批准模型时，模型的比较范围能看到这个改动；视图在其他模型里时，没有检查项能看到。这是有意的口径（第四轮复评 R3，Albert 2026-11-21 拍板，ADR-017）。
- 进入受保护分支的批准记录 evidence 只能是 40 位 commit：`sha256:<64 位十六进制>` 形式 L1 合法，但合并时校验判断不了它与分支的祖先关系，一律拒绝；它只适用于不经合并进受保护分支的场合。
- `release/*` 标签由托管平台的 tag ruleset 禁止删除与移动（本仓库 2026-11-20 已配置规则集 `release-tags-immutable`：规则 deletion、update、non_fast_forward，无绕过者，管理员同样受约束；探针实测创建可以、强推移动与删除均被 GH013 拒绝）。规则集被停用或修改时，标签可被移动、删除，发布标签检查又只在合并时看一次，此时为残余风险。
- 发布批准的合并请求关闭未合并时，已推送的 `release/*` 标签不自动删除，由人清理；清理前它指向一个未合入主线的发布批准。因规则集禁止删除，清理须由仓库管理员临时停用规则集、删标签、再启用；规则集不设绕过者，是为了不让与人共用账号凭据的 AI 也能绕过。
- 写入层对工作区文件的"写前哈希核对"不是真正的比较并交换：不遵守写锁的外部编辑器或 Git 命令在核对与替换之间（毫秒级）写入的内容会被覆盖。
- `model.remove` 只检查本仓库：独立模型仓库里指向被删元素的引用看不到，删除后会在那边悬空。
- `governance.record_approval` 在"新建记录文件"与"提交完成"之间被杀，会留下未提交的记录文件；下次调用以 DIRTY_WORKTREE 报出，需人工清理。多文件写入同样不是崩溃原子的，由 gate 兜底。
- `model.remove` 对 BPMN 成员属性以外的引用一律拒绝，放开需要逐条进规范。布局文件出现前，删除不处理布局。
- `tools/aisep.py` 需要 Python 3.12 及以上。
