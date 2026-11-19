# AISEP 第二步：元模型规范（v0.4）

状态：§14 的 D1–D10 已于 2026-11-19 全部按建议拍板（ADR-011）；v0.3 = v0.2 + 三轮审计和第二次 GPT 评审之后补的 R1–R4、G1–G10，全部已在原型里实现并验证。v0.4 = v0.3 + “AI 进行中”的数据来源（ADR-013）：新增 `aisep:AgentActivity`（§6.7）、批准记录的 `aisep:activity`（§6.6）、MCP 的 `model.diff` 与 `governance.record_approval` 改动（§8.3）；AgentActivity 与两个 MCP 工具在 MCP 接口设计时一并定稿。依据：`spike-linked-archi/spike-result.md`（第一步结论）、《方法论总纲（草案1）》§6/§6a、《AISEP 架构原则》、`decisions.md`（ADR-003/004/007/008/009/010）。
基线：Linked.Archi core 0.6.0 + ArchiMate 4.0（vendored，按 SHA256 锁定）。命名空间先用占位符 `https://aisep.example/`，第三步建正式仓库前统一替换。
原型：`metamodel-prototype/`（179 项测试全部通过，详见 §15）。修订与辩论记录见附录 B，已知限制见附录 C。

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
| 关系 | `{model}rel-{源slug}-{直连谓词本地名}-{目标slug}`，重名时加 `-2` | `…/procurement/rel-supplier-assignedTo-quoteApproval` |
| 视图 | `{model}view-{slug}` | `…/procurement/view-quote` |
| 批准记录 | `{model}approval-{yyyymmdd}-{slug}` | `…/procurement/approval-20261119-arch-baseline` |

- slug 用可读英文 camelCase。**一经创建不改**：改名只改标签。IRI 由写入层生成（§8），不靠人记规则。
- 跨模型引用直接写对方的 IRI；被引用元素被删除时 L1 报错（原型已验证）。
- 修订历史交给 Git。

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
- `aisep:priority` ∈ {Must, Should, Could, Wont}（MoSCoW），挂在需求上。**只有 Must 级**的需求或验收标准没有 TestCase 时，才算追溯缺口（L4）。
- 概念名用 `skos:exactMatch` 对到 OSLC QM/RM；不导入 OSLC。

### 6.6 治理与批准（Extension，ADR-009）
- `aisep:ApprovalRecord` ⊑ `arch:Element`。这是作者写的唯一治理事实，字段：
  - `aisep:gate` ∈ {需求确认, 架构决策, 设计评审, 代码合并, 发布上线}，即架构原则五的五个关口（SKOS）；
  - `aisep:decision` ∈ {Approved, Rejected}；
  - `aisep:approvedBy` → 人（必须是 `arch:Stakeholder` 或 `prov:Agent` 的实例）；
  - `prov:generatedAtTime`；
  - `aisep:approves` → 一个或多个元素、模型或 ADR；
  - `aisep:evidence`（**必填**，恰好一个）：批准时那次校验报告对应的 git commit（40 位十六进制）或 `sha256:<64 位十六进制>`，证明"批准的是哪个版本"。经 MCP 写入时自动填写。
  - `aisep:activity`（可选，最多一个）→ 一条 `aisep:AgentActivity`（§6.7），表示这次批准针对的是哪次 AI 活动；必须是模型元素（IRI，带 `arch:inModel`），不能是空白节点。evidence 是 40 位 commit 时，必须等于该活动的 `aisep:headCommit`，否则 L1 报错。
- **`arch:approvalState` 由构建推导**：取最近一条**合法**批准记录的结论（不合法的记录不参与推导，构建时报 Warning）；没有记录则为 Proposed；元素本身被合并、替换（带 `dcterms:isReplacedBy`，且目标必须是某个模型里的元素，否则 L1 报错，也不触发）则为 Superseded。`aisep:Rejected`、`aisep:Superseded` 是 AISEP 补的取值，上游只有 Proposed/Approved。同一元素有两条时间相同（按时区归一化后）但结论不同的记录时，L1 报"批准有歧义"。手填 approvalState，包括通过子属性间接写入，都在 L1 报错。
- 工作台只展示批准记录、触发新增批准记录，不保存状态（ADR-009）。
- 架构决策采用 vendored 的 `arch-decision`（ADR：Decision/Option/Force），用 `ad:relatedConcept` 连接元素。它的 shapes 读的是直连三元组，所以 L3 必须跑在构建后的图上（§10）。
- 质量：`arch:hasQualityMeasure` + ISO 25010 个体；补 `aisep:value`、`aisep:unit`、`aisep:target`、`prov:generatedAtTime`。

### 6.7 代码与交付追溯（Extension）
- `aisep:CodeLocation`：`schema:codeRepository`（命名空间统一用 `https://schema.org/`）、`aisep:path`、可选 `aisep:symbol`、`aisep:swhid`。
- `aisep:Implementation`（限定关系，CodeLocation → 设计元素），直连谓词 `aisep:implements`。
- `aisep:Deployable` ⊑ `am4:Artifact`，带 `aisep:packageUrl`（purl）。Artifact → ApplicationComponent 的 Realization 可以直接画。
- `aisep:AgentActivity` ⊑ `arch:Element`、`prov:Activity`（ADR-013，**草案，与 MCP 接口设计一并定稿**）：一次**已完成**的 AI 活动，只在任务过关口时经 `governance.record_approval` 写入；进行中的状态不进模型仓库。字段：
  - `prov:wasAssociatedWith` → 执行的代理，恰好一个；判定与 `aisep:approvedBy` 相同（`arch:Stakeholder` 或 `prov:Agent` 的实例；`prov:Agent` 目前实际不可用，见附录 C）；
  - `prov:startedAtTime`、`prov:endedAtTime`，各恰好一个 xsd:dateTime，开始不晚于结束（按时区归一化，不带时区的按 UTC）；
  - `aisep:sessionRef`：外部编排器的会话标识，字符串，恰好一个；对元模型不透明，不绑定 AO；
  - `aisep:branch`：分支名，字符串，恰好一个；
  - `aisep:baseCommit`、`aisep:headCommit`：各恰好一个 40 位十六进制 commit。baseCommit 取分支与模型主分支的分叉点（merge-base），不是主分支最新提交。
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
- **未原型化**（`rm` 还没实现），在 MCP Server 里实现。

### 8.3 MCP Server 语义契约（ADR-008）
| 工具 | 语义 | 对应层 |
|---|---|---|
| `model.add_element` | 生成 IRI（§3），写入恰好一个类型、inModel、zh 名称 | 写入后自动跑 L1/L2 |
| `model.add_relationship` | 只写限定关系；先查记法混用规则和矩阵，不合法就拒绝写入并说明原因 | L1/L2 |
| `model.remove` | 按 §8.2 级联删除，或者拒绝 | L1 |
| `model.check` / `model.validate` | L0–L2 / L3 | §10 |
| `model.query` | 只读 SPARQL，跑在构建后的图上 | — |
| `model.impact` | §9 两种模式 | — |
| `model.findings` | L4 | — |
| `governance.record_approval` | 新增一条批准记录（不改状态字段）；可选传入活动信息（代理、sessionRef、分支、起止时间、baseCommit、headCommit），在同一次提交里写入 `aisep:AgentActivity` 并用 `aisep:activity` 关联，evidence 自动填为 headCommit | L1 |
| `model.diff` | 只读，输入两个 Git 引用 base、head（不给 base 时取 head 与模型主分支的 merge-base），返回新增、修改、删除的元素和关系清单（按 IRI；同一 IRI 的三元组有变化算修改；改关系类型按 §8.2 表现为删除加新增）。无状态，只读 Git 对象，可从任意 worktree 调用 | — |

所有写操作都是 Turtle 文件的修改，进 Git；MCP 不保存任何不在文件里的状态。接口的具体设计另写文档。

`model.diff` 同时服务两处：工作台"AI 进行中"区域（每个编排器会话按分支名算改动元素）和关口页的模型差异图，接口按这两个用途一起设计。v1 只比较已提交内容；前提是模型文件和会话改动的代码在同一个仓库、同一条分支上（见附录 C）。**不提供任何"上报进行中状态"的写工具**（ADR-013）。

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
C4、Backstage 接入、TOGAF 内容元模型、ArchiMate 派生规则引擎、图形布局、成本扩展、ADM 框架实例化（第三步）、CI/CD 实际接入、MCP 接口的具体设计（另写文档）。

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

**最终状态（2026-11-20）**：`tools/aisep.py test` 179/179 通过（v0.4 新增 31 项，见下表最后一行）；3 份验收脚本全部成立（规范主张 22/22、审计回归 19/19、GPT 评审回归 12/12）；采购例子跑 `gate` 结论为 PASS，0 违规；那条 1 Warning 是原例子里"组件 → 服务"的派生捷径，属于已知情况。v0.3 及以前的结果都由独立复核者在副本上重跑确认；v0.4 新增部分经过一轮异构评审（GPT 族，附录 B.3），尚未经独立复核。

| 轮次 | 做了什么 | 结果 |
|---|---|---|
| v0.1 原型 | 8 个模块 + 跨记法采购例子 | 84/84；对抗审计构造了 10 个攻击用例，2 个暴露漏洞（H、J） |
| v0.2 | D1–D10 落地 | 109/109；H、J 封住；新的 24 个攻击用例里 10 个失败 → R1–R4 |
| R1–R4 | 模型不能改元模型、一个元素只属于一个记法、批准记录推导、refines 指向废弃节点 | 128/128；10 个失败全部修好；新的 24 个攻击用例里 12 个失败 → G1–G6（另 2 个登记为已知限制） |
| G1–G6 | 批准合法性统一成一个定义、关口只能来自模块、evidence 格式、日期格式、核心关系的记法混用、禁止继承抽象根类 | 139/139；30 个回归用例中 28 个通过，另 2 个是已登记的已知限制 |
| G7–G10 | 第二次 GPT 评审：谓词闭世界、isReplacedBy 目标、impact 先过校验、统一入口 `gate` | 148/148；4 个反例和 2 个已知限制全部封住；合法夹具和例子中 0 误报 |
| v0.4 | `aisep:AgentActivity`（L1 核心检查 + L3 EG17–EG24）、批准记录的 `aisep:activity`（EG25）与 evidence=headCommit（EG26，纳入批准合法性定义）、§4 白名单补齐；异构评审后补：两个直连谓词的主语限制、activity 必须是模型元素、EG24 混合时区 | 179/179；新增 3 个合法夹具、28 个非法夹具；`prov:used` 等其他 PROV 谓词仍被拒绝；采购例子 `gate` 仍为 PASS、0 违规、Warning 不变 |

核心主张都已用可执行测试证实：写入层生成的直连三元组与限定关系一一对应；一条通用查询能从测试用例经 am4、DDD 走到代码和可部署包；校验范围（BPMN 内部连线不受 ArchiMate 矩阵约束，DDD 受约束）；depends/ripple 两种影响模式在手工核对的图上结果一致；批准状态推导（含时区、平局、非法记录）；闭世界规则（类型、谓词、元模型修改）。

**性能**（采购例子，7 个文件）：check 约 0.1 秒，`gate`（L0–L4）约 5 秒，全量测试约 2–3 分钟。

## 附 A：可直接粘贴到《总纲（草案1）》的更新

（总纲已按设计会话的指令改过 §7、§8、§6a、§9。下面只剩建议补充的一句。）

> §6a"待验证"一行可改为：跨记法追溯已在 metamodel-prototype 中验证：一条通用查询走通测试用例 → 需求 → am4 → DDD → 代码/可部署包，BPMN/UML 经 refines 挂接；148 项测试全部通过。见《第二步：元模型规范》§15。

## 附 B：修订与辩论记录

### B.1 v0.1 → v0.2

来源：GPT-5.3 Codex 设计评审（经 cursor-agent，只读）；原型审计（Claude，独立）；集成阶段发现的规范自相矛盾；ADR-008/009。

| 意见 | 来源 | 处置 | 依据 |
|---|---|---|---|
| D1 "选 Grouping 就无法用 Serving/Flow"不成立 | GPT | **接受** | 查表确认 Grouping 允许（派生）；另外发现 AC→AC 的 Serving 也只能派生 |
| D2 "只能派生"不是上游的约束 | GPT | **部分接受**：上游表确实标为派生（`permitsDirect=false`），但 shapes 接受 → 新增"派生捷径"规则，把决定权写明 | 查表 |
| D3 命令丢失载荷语义 | GPT | 接受，加可选 payload | — |
| D4 需要规定何时必须 refines | GPT | 接受（§6.2） | — |
| D5 并非所有连接都有直连谓词 | GPT | 接受（只对有 unqualifiedForm 的生成） | — |
| D6 导入器会断言超类 | GPT | 接受（允许冗余超类） | — |
| D7 Composition 方向错误 | GPT | **部分接受**：改为 Both，不是 Forward（部分的存在依赖整体，整体的结构也依赖部分） | 上游定义原文 |
| §7.2 同一性 ≠ 细化，缺主锚规则 | GPT | 接受：加层级、无环、主锚唯一、合并/拆分规则；但仍用 refines，不另造同一性关系，因为跨记法表示天然存在粗细之分 | — |
| §7.1 直接写 refines 三元组会被漏掉 | GPT | 已由构建归一化解决（§7.1） | 原型 |
| §10.2 扩展子类会逃过矩阵 | GPT | 接受（Extension 对齐常驻） | — |
| "泳道成员关系是 relatedMatch"无依据 | GPT | 接受，更正措辞 | — |
| 漏洞 H：BPMN 连线跨 am4 元素 | 审计 | 接受 → D8 | 已复现：0 违规 |
| 漏洞 J：同记法 refines 被放行 | 审计 | 接受 → D9 | — |
| "7 元素"与 §9 矛盾 | 集成 | 接受 → 两种模式 | 原型计算结果为 5 个 |
| BC implements Subdomain 既是"派生"又必须写入 | 审计 | 接受 → 派生捷径规则 | — |
| zh+en 两个 prefLabel 与上游 UML/BPMN shapes 冲突 | 集成 | 接受 → 英文名放 altLabel | — |
| 一个模型 = 一个文件 与例子不符 | 审计 | 接受 → 一个模型 = 一个目录 | — |
| arch-decision shapes 读直连三元组 | 集成 | 接受 → L3 跑在构建后的图上 | — |
| 取值集只在 L3、直连三元组只在 L1 | 审计 | 接受 → pre-commit 跑 L0–L3 | 实测 L3 约 5 秒 |
| 追溯缺口应只针对 Must 级 | 审计 | 接受 → 加 priority | — |
| Rejected/Superseded 上游不存在 | 原型 | 接受 → aisep: 取值 | 已查询确认 |
| schema: 命名空间 http/https 混用 | 审计 | 接受 → 统一用 https | — |

### B.2 v0.2 → v0.3（三轮原型审计 + 第二次 GPT 评审）

| 意见 | 来源 | 处置 |
|---|---|---|
| 模型文件可以声明双父类、子属性、模块注解，从而绕过多条规则 | 审计第二轮 | 接受 → R1：模型文件只允许单父类特化 |
| 跨记法的多类型 L1 放行而 L3 拦截 | 审计第二轮 | 接受 → R2：一个元素只属于一个记法 |
| 非法批准记录也参与推导；evidence 可省略；同一时刻平局时结论取决于 IRI 排序 | 审计第二轮 | 接受 → R3 |
| refines 指向已废弃节点不报 | 审计第二轮 | 接受 → R4（L4 Warning） |
| 推导、L1、L3 三处对批准记录合法性的判断不一致 | 审计第三轮 | 接受 → G1：统一成一个函数 |
| 模型可以给关口概念表添加成员 | 审计第三轮 | 接受 → G2 |
| evidence 填空白也能通过 | 审计第三轮 | 接受 → G3：commit 或 sha256 格式 |
| 格式错误的日期能通过 L1 | 审计第三轮 | 接受 → G4（并入 G1） |
| 核心的 Association/HasPart 可以跨记法 | 审计第三轮 | 接受 → G5 |
| 模型可以直接继承抽象根类 | 审计第三轮 | 接受 → G6 |
| 自定义谓词能跨记法直连（REFUTED） | GPT 第二次 | 接受 → G7：谓词闭世界 |
| isReplacedBy 指向字面量也会触发 Superseded | GPT 第二次 | 接受 → G8 |
| impact 在脏模型上照样给结论 | GPT 第二次 | 接受 → G9 |
| check 与 validate 分开跑，结论可能分裂 | GPT 第二次 | 接受 → G10：统一入口 `gate` |
| 加"导入兼容模式"，允许同义冗余超类 | GPT 第二次 | **不接受**：导入时转成 refines 即可；放宽会重新打开 R2 刚堵上的口子 |

修复循环在 G7–G10 之后按预设上限停止，不再开新一轮对抗挖掘。

### B.3 v0.3 → v0.4（"AI 进行中"的数据来源，ADR-013）

| 意见 | 来源 | 处置 |
|---|---|---|
| 运行态读编排器、改动元素由 Git 差异派生、已完成活动在关口处入库 | 设计会话答复（2026-11-20） | 接受 |
| 差异起点未定义：和主分支最新提交比，会把主分支新合入的改动误报为"删除" | 执行会话核对 | 接受 → baseCommit 取 merge-base |
| 分支差异只在模型与代码同仓同分支时有意义 | 执行会话核对 | 接受 → 写为前提（附录 C） |
| v1 只比较已提交内容，进行中会话这一栏多半为空 | 执行会话核对 | 接受为已知限制（附录 C） |
| 设计会话起的 `aisep:headCommit` 与批准记录的 `aisep:evidence` 重复记录同一版本 | 执行会话核对 | 部分接受：保留 headCommit（evidence 也可能是报告哈希），evidence 为 commit 时 L1 要求两者相等 |
| 新类和 PROV 谓词不在谓词白名单与元素直连白名单里，闭世界规则会直接拒绝 | 执行会话核对 | 接受 → §4 白名单补齐 |
| 两个直连谓词进了全局白名单，任何元素都能用它们直连 | GPT 评审 | 接受 → 主语限制（aisep-core `ActivityLinkSubjectShape`，L1/L3） |
| §6.7 写"prov:Agent 的实例"，实现还接受 arch:Stakeholder | GPT 评审 | 接受 → 改规范措辞，与 §6.6 approvedBy 统一 |
| PROV-O 未加载，闭世界下写不出 `a prov:Agent` | GPT 评审 | 部分接受：属实，但 approvedBy 自 v0.2 起就如此；登记为已知限制（附录 C），不在本轮加载 PROV-O |
| 空白节点活动绕过 `arch:inModel` 成员要求 | GPT 评审 | 接受 → activity 必须是带 inModel 的 IRI（L1；L3 EG25 加 sh:nodeKind sh:IRI） |
| EG24 遇到一个带时区、一个不带时区的时间时，L3 不报而 L1 报 | GPT 评审（存疑）→ 实测证实 | 接受 → EG24 把不带时区的按 UTC 处理；验收脚本加 L1/L3 一致性两例 |
| 缺上述绕过的反例 | GPT 评审 | 接受 → 新增 4 个非法夹具、1 个合法夹具 |

## 附 C：已知限制（第一批不处理）

- `model.diff` v1 只比较已提交内容：进行中的会话在提交前，"改动元素"一栏为空或滞后。
- 分支差异的前提是模型文件和会话改动的代码在同一仓库、同一分支；模型仓库独立时，编码会话的分支里没有模型差异。

- 同一节点在不同层级的锚点是否互相一致（UML 类的 am4 锚点是否等于它 DDD 锚点的 am4 锚点），不检查。
- Verification、Implementation 指向已被替换的节点时，不提示迁移；多步替换链（旧 → 中 → 新）只提示第一步。
- 模型里声明的类不能用 deprecated/isReplacedBy 退役（R1 只允许名称和定义）；合并、拆分模式只适用于实例。
- "通用域风味"推导规则（§6.1）、DomainEvent 过去时 Warning（§6.4）、`rm` 级联删除（§8.2）没有原型化，留给 MCP Server 实现。
- G7 的"元素间直连"白名单包含 BPMN 结构属性（flowElements、lanes 等）和 `arch:hasQualityMeasure`、`ddd:exposedAggregate`。这是为了让合法模型通过而做的判断，未经异构评审。
- PROV-O 本体没有加载，闭世界下模型里不能写 `a prov:Agent`；`aisep:approvedBy` 和 `prov:wasAssociatedWith` 规则里的 "或 prov:Agent" 目前用不上，代理只能用 `arch:Stakeholder`。
- `tools/aisep.py` 需要 Python 3.12 及以上。
