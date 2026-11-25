# C4 与 ArchiMate 4 双模型：第 10 节核实报告（人工关口 A）

- 对应规范：[c4-archimate4-dual-model.md](c4-archimate4-dual-model.md) 第 9 节第 1 步、第 10 节
- 核实日期：2026-11-25
- 核实方式：直接读上游原文。Turtle 用 `Accept: text/turtle` 从 meta.linked.archi 取线上当前版本，并与仓库快照 `vendor/meta.linked.archi/`（抓取于 2026-11-19T13:47Z）逐文件比对 SHA-256；网页指南读 meta.linked.archi/docs 原页。
- 源码仓库 linked-archi-meta：`github.com/linked-archi/linked-archi-meta` 仍返回 404，GitLab 同名仓库需登录（与 [docs/history/spike-linked-archi-result.md](../history/spike-linked-archi-result.md) 结论一致）。**未找到**可公开访问的源码仓库，以下出处一律引用 meta.linked.archi 的发布物。

## 0. 先看结论

| # | 事项 | 结论（一句话） |
| --- | --- | --- |
| 1 | ArchiMate 4 本体状态与 core 兼容性 | 仍标 `draft`，无正式版；但线上本体 2026-11-22 已改且依赖 core 0.7.0。我们的 11-19 快照（am4 + core 0.6.0）自洽可用 |
| 2 | C4 人、组件、外部、部署等类名 | 人、组件、外部在 `c4:`；**部署类不在 `c4:`**，在 `structurizr:`（`https://meta.linked.archi/c4/structurizr#`）；**没有容器实例类** |
| 3 | 关系说明文字放哪个属性 | 本体未定义专门属性；上游转换器把关系说明写成关系资源上的 `skos:prefLabel` |
| 4 | 跨语言映射谓词与映射文件 | 类型级用 SKOS 映射文件；实例级（同一系统的两种描述）上游 DD-11 规定 `skos:exactMatch`。**没有** C4↔ArchiMate 4 映射文件 |
| 5 | `c4/shapes` 是否已有“容器只属于一个系统” | **没有**，AISEP 需要自己写 |
| 6 | 视图定义、文档模板、生成器能否直接用 | C4 视点 7 个可复用；C4 模板只有 2 个，部署那节查询用了不存在的谓词，且只取 `@en` 标签；没有 arc42 模板；生成器 la-generate **未找到下载** |
| 7 | `c4/structurizr#` 的用途 | 是部署词汇扩展，不是导入导出工具。导入由上游转换器 structurizr2linkedarchi 完成（读 workspace JSON），**未找到** RDF→DSL 导出 |

另有 10 处规范与上游不一致，见第 8 节（S10 于 2026-11-26 补入）；第 6 节的建议方案见第 9 节。

## 1. ArchiMate 4.0 本体是否有正式版，core 0.6.0 是否兼容

**结论**：没有正式版。线上本体仍是 `bibo:status "draft"`、`owl:versionInfo "4.0"`、`owl:versionIRI <…/archimate4/onto/4.0#>`；`dcterms:source` 指向 Open Group 的 `archimate4-doc`，没有出现 C260 或“正式版”字样。

但上游在**不改版本号**的情况下改了内容：

- 线上 am4 本体 `dcterms:modified "2026-11-22"`，与快照（2026-10-10）不同。新增 `am4:serves rdfs:subPropertyOf arch:dependencyOf`（changeNote 引 DD-44），另把十几处 `arch:domainIncludes arch:Element` 收窄成 am4 自己的四个抽象类。
- `arch:dependencyOf` 是 **core 0.7.0**（`dcterms:modified "2026-11-22"`，`owl:priorVersion <…/core/0.6.0#>`）才新增的。线上 core 已是 0.7.0，`owl:versionIRI` 仍是不带版本的 `<…/core#>`，am4 的 `owl:imports` 也是不带版本的 `<…/core#>`。
- 兼容性实测（脚本列出每个文件用到、但 core 里没有定义的 `arch:` 术语）：
  - 快照 am4 + 快照 core 0.6.0：缺失为空，**兼容**。
  - 线上 am4 + core 0.6.0：缺 `arch:dependencyOf`，**不兼容**（悬空 IRI，不会报语法错，但 DD-44 的依赖查询会断）。
  - 线上 am4 + 线上 core 0.7.0：缺失为空。
  - c4/onto、c4/shapes、c4/structurizr（快照与线上）、am4/shapes、c4/deliverable-templates 配 core 0.6.0：缺失均为空，**兼容**。
- 11-19 快照与线上一致（SHA 相同）的有：core-shapes 0.4.0、archimate4 shapes/metamodel/viewpoints/deliverable-templates、c4 metamodel/viewpoints/deliverable-templates/tax、core-viewpoints。已经变化的有：core、archimate4/onto、c4/onto、c4/shapes、c4/structurizr、c4/structurizr-shapes、core-deliverable-templates。

**含义**：锁版本只能按文件哈希锁，不能靠 `owl:versionInfo`。如果第 3 步继续用 11-19 快照，am4 与 core 0.6.0 保持一致；要升到线上版本，就必须连 core 一起升到 0.7.0，这要过人工关口。

出处：
- <https://meta.linked.archi/archimate4/onto>（Turtle 头部 `bibo:status`、`dcterms:modified`、`skos:changeNote`）
- <https://meta.linked.archi/core>（`owl:versionInfo "0.7.0"`、`skos:historyNote` 0.7.0 条）
- <https://meta.linked.archi/docs/guide/design-decisions/#dd-44-languages-align-their-dependencies-with-the-cores-inferences-stay-out-of-models>

## 2. C4 的人、组件、外部、部署、基础设施、容器实例，以及容器包含组件

**结论**（版本为 `c4/onto` 0.3.0，快照与线上在这些术语上一致）：

| 概念 | 确切名称 | 所在命名空间 |
| --- | --- | --- |
| 人 | `c4:Person` | `c4/onto#` |
| 外部人 | `c4:ExternalPerson`（`c4:Person` 的子类） | `c4/onto#` |
| 组件 | `c4:Component` | `c4/onto#` |
| 外部系统标记 | `c4:ExternalSoftwareSystem`（`c4:SoftwareSystem` 的子类），**是子类，不是布尔属性** | `c4/onto#` |
| 容器包含组件 | 直接谓词 `c4:hasComponent`；限定资源 `c4:ComponentContainment`，经 `c4:qualifiedComponentContainment` 指向 | `c4/onto#` |
| 系统包含容器 | `c4:hasContainer`；`c4:ContainerContainment`，经 `c4:qualifiedContainerContainment` 指向 | `c4/onto#` |
| 其他容器子类 | `c4:Database`、`c4:MobileApp`、`c4:ClientSideWebApp` | `c4/onto#` |
| 部署节点 | `structurizr:DeploymentNode` | `c4/structurizr#` |
| 基础设施节点 | `structurizr:InfrastructureNode` | `c4/structurizr#` |
| 容器实例 | **没有类**。上游把它建模成关系：`structurizr:deployedOn`（容器 → 部署节点），限定资源 `structurizr:Deployment`，经 `structurizr:qualifiedDeployment` 指向 | `c4/structurizr#` |
| 部署属性 | `structurizr:environment`（xsd:string）、`structurizr:instances`（xsd:integer），定义域都是 `DeploymentNode` | `c4/structurizr#` |
| 部署节点嵌套 | 扩展没有定义父子属性；上游转换器用 core 的 `arch:hasPart` | — |

`c4/onto` 的 `skos:historyNote` 原话：0.3.0 把部署节点、基础设施节点和部署关系从 C4 本体移到了 structurizr 扩展。`c4/tax` 里的注释也说明 `c4:DeploymentNode`、`c4:InfrastructureNode` “resolve to nothing”。

出处：
- <https://meta.linked.archi/c4/onto>（类与属性定义，`skos:historyNote`）
- <https://meta.linked.archi/c4/structurizr>（`DeploymentNode`、`InfrastructureNode`、`deployedOn`、`Deployment`、`environment`、`instances`）
- <https://meta.linked.archi/c4/tax>（第 41–43 行注释）
- <https://converters-c2cddb.gitlab.io/converters/structurizr/#relationships>（“A container instance is a relationship, not an element. The extension publishes no ContainerInstance class”）

## 3. C4 关系的说明文字放在哪个属性上

**结论**：`c4/onto` 和 core 都**没有**为关系说明文字单独定义属性。core 对 `arch:QualifiedRelationship` 的定义是：关系资源“承载全部元数据：标签、来源、生命周期等”。上游 Structurizr 转换器的映射表把关系的 `description` 写成关系资源上的 `skos:prefLabel`，原文是“a relationship's description is its label”；元素的 `description` 则写成 `skos:definition`。

因此规范第 4 节第 3 条可以落实为：C4 连线上那句话写在 `c4:Using` 资源上的 `skos:prefLabel`（带语言标签）。这是转换器约定，本体本身没有规定。

出处：
- <https://meta.linked.archi/core>（`arch:QualifiedRelationship` 的 `skos:definition`）
- <https://converters-c2cddb.gitlab.io/converters/structurizr/#attributes>（映射表“description on a relationship”一行）

## 4. 跨语言映射指南规定的关联谓词与文件格式；是否已有 C4↔ArchiMate 4 映射文件

**结论**：上游把映射分为两层，用的机制不同。

| 层级 | 关联什么 | 谓词 | 放在哪里 | 依据 |
| --- | --- | --- | --- | --- |
| 类型级 | 两个**类**，例如 `c4:SoftwareSystem` ↔ `am4:ApplicationComponent` | `skos:closeMatch` / `relatedMatch` / `broadMatch` / `narrowMatch`，只有范围真正重合时才用 `exactMatch`；禁止 `owl:equivalentClass`、`rdfs:subClassOf`、`owl:sameAs` | 每个语言一份 `{lang}-crossmappings.ttl`，命名空间 `https://meta.linked.archi/{lang}/crossmappings#`，前缀 `{lang}xm`；在元模型清单上用 `arch:crossLanguageMappings` 登记；`owl:imports` 只写自己的本体；不设默认前缀；本语言术语一律作主语 | 编写指南 |
| 实例级 | 两个**节点**，指同一个真实系统 | 默认 `skos:exactMatch`；只有通过“可替换性测试”（推理机任何时候把一个 IRI 换成另一个都安全）才用 `owl:sameAs` | 独立的 reconciliation 图 `{base}graph/reconciliation`，每条链接附一条 RDF 1.2 记录（`rdf:reifies <<( … )>>`、`prov:wasAttributedTo`、`prov:generatedAtTime`、`skos:scopeNote`）；由人编写并评审，转换器从不生成 | DD-11、DD-27 |

规范第 6 节说的关联属于**实例级**。上游给出的默认谓词是 `skos:exactMatch`，DD-11 的示例正好是“Backstage `bs:Component` 与 `am4:ApplicationComponent` 指同一系统”。

现成映射文件：**未找到** C4 与 ArchiMate 4（或 ArchiMate 3）的映射文件。`c4/metamodel` 没有 `arch:crossLanguageMappings`；`https://meta.linked.archi/c4/crossmappings` 和 `…/archimate4/crossmappings` 都返回 404；快照里 6 份 crossmappings（backstage、bpmn、leanix、time-framework、togaf、uaf）没有一份提到 `c4:`。

另外两点相关：

- 线上 `c4/onto` 新增了 `c4:uses` 的 scopeNote：“Between a C4 element and an element of another language, use the core's relationship types.” 也就是说，C4 元素与其他语言元素之间不能用 `c4:uses`，要用 core 的关系类型。
- core 0.6.0 自带三个用于跨语言的关系类型：`arch:Association`（`associatedWith`，对称）、`arch:HasPart`、`arch:Refines`（`refines`）；0.7.0 又新增了第四个 `arch:DependsOn`（DD-40）。其中 `arch:refines` 的定义写明是“traceability property intended to use within a single model or across models”。

出处：
- <https://meta.linked.archi/docs/guide/authoring-crossmappings/>
- <https://meta.linked.archi/docs/guide/design-decisions/#dd-11-identity-mechanism-correspondence-vs-merge>
- <https://meta.linked.archi/docs/guide/design-decisions/#dd-27-three-provenance-layers-distinguished-by-graph-and-by-activity>（reconciliation 层）
- <https://meta.linked.archi/docs/guide/design-decisions/#dd-40-the-core-has-four-relationship-types-for-elements-no-language-relates>
- <https://meta.linked.archi/docs/tools/>（“Merging without flattening”一节，重申 reconciliation 图里放评审过的 `skos:exactMatch`）
- <https://meta.linked.archi/c4/metamodel>、<https://meta.linked.archi/c4/onto>（`c4:uses` 的 scopeNote）、<https://meta.linked.archi/core>（`arch:crossLanguageMappings`、`arch:refines`）

## 5. `c4/shapes` 是否已有“容器只属于一个系统”等检查

**结论**：**没有**。线上 `c4/shapes`（0.2.0，内容与快照不同，但版本号没变）有以下几类：

- `UsingShape`：36 组合法的源/目标类型组合；
- `ContainerContainmentShape`：源必须是 `SoftwareSystem`，目标必须是 `Container`；
- `ComponentContainmentShape`：源必须是 `Container`，目标必须是 `Component`；
- 四个 `*UnqualifiedShape`：限制直接谓词的目标类型，例如 `Person` 和 `Container` 上 `c4:hasContainer` 的 `sh:maxCount 0`；
- `C4ElementLabelShape`：每个元素至少一个带语言标签的 `skos:prefLabel`。

全文没有 `sh:inversePath`，也没有对“被几个系统包含”计数。所以规范第 7 节“每个 `c4:Container` 恰好属于一个 `c4:SoftwareSystem`”需要 AISEP 自己写，不会和上游重复。组件属于几个容器，上游同样没有检查。

上游已经覆盖的部分（AISEP 不要重复写）：包含关系的端点类型、`c4:uses` 的端点类型、`prefLabel` 必填且必须带语言标签。`structurizr-shapes` 另外检查 `Deployment` 必须从 `Container` 指向 `DeploymentNode`。

出处：
- <https://meta.linked.archi/c4/shapes>
- <https://meta.linked.archi/c4/structurizr-shapes>

## 6. 视图定义、文档模板、文档生成规范能否直接用于生成 C4 视图和 arc42 骨架

**结论**：只能部分复用，不能直接生成 arc42。

- **视点**（`c4/viewpoints` 0.1.0）：有 `SystemContext`、`ContainerDiagram`、`ComponentDiagram`、`CodeDiagram`、`C4Deployment`、`SystemLandscape`、`DynamicDiagram` 七个，可直接作为 arc42 第 3、5、6、7 节的视点引用。
- **文档模板**（`c4/deliverable-templates` 0.1.0）：只有两个，`SystemOverviewDocument`（系统上下文、容器、部署拓扑）和 `ComponentDesignDocument`（容器上下文、组件结构、动态行为），都用 `arch:sectionQuery` 内联 SPARQL。存在两个上游缺陷：
  1. 部署拓扑那节查询用的是 `c4:deploys` 和 `c4:environment`，两者在 `c4/onto` 0.3.0 里**都不存在**（已移到 `structurizr:deployedOn`，方向相反；以及 `structurizr:environment`），所以这一节永远查不出结果；
  2. 所有查询都写死了 `FILTER(lang(?label) = "en")`，而规范第 4 节要求用 `@zh` 标签，这样一来所有节都会是空的。
- **arc42**：快照里 245 个文件没有一个提到 arc42，站点地图里也没有 arc42 页面。**未找到** arc42 模板。
- **生成器**：文档生成规范描述的是 `la-generate`（Java 25，读模板、跑问题和查询，再用 Handlebars 渲染成 Markdown 或 HTML），原文说“the reference implementation is la-generate, in the Linked.Archi toolbox”。但工具页列出的可下载工具只有转换器、APM 技能和 WebMCP，**未找到** la-generate 的下载。规范本身写明“图不渲染”，图示列在 Future Extensions。

**含义**：第 6 步需要 AISEP 自己写 arc42 生成器（或模板 + 查询）。可以参照上游模板的数据结构（`arch:DeliverableTemplate` / `arch:TemplateSection` / `arch:sectionViewpoint`），并引用上游视点 IRI；但上游 C4 模板不能原样用。

出处：
- <https://meta.linked.archi/c4/viewpoints>
- <https://meta.linked.archi/c4/deliverable-templates>（`SOD-S3` 的查询）
- <https://meta.linked.archi/docs/guide/deliverable-generator-spec/>
- <https://meta.linked.archi/docs/guide/deliverable-templates/>
- <https://meta.linked.archi/docs/tools/>

## 7. `c4/structurizr#` 的用途，能否用于 Structurizr DSL 导入导出

**结论**：`c4/structurizr#`（0.1.0，draft）是**部署建模词汇扩展**，内容见第 2 项。它本身不提供导入导出。原文描述是：“Structurizr-specific extensions … Adds deployment modeling concepts … that are part of the Structurizr tooling but not part of the abstract C4 model.”

- **导入**：上游有转换器 `structurizr2linkedarchi.jar`（Java 25+）。它读的是 Structurizr **workspace JSON**，不是 DSL；DSL 需要先用 `structurizr-cli export -workspace workspace.dsl -format json` 转成 JSON。输出对齐 `c4:` 和 `structurizr:`，分成 semantic、model、views、provenance 四个命名图。默认不把 `location External` 映射成 `c4:ExternalSoftwareSystem`（`softwareSystem` 一律映射为 `c4:SoftwareSystem`，可以用 `--type-mapping` 覆盖）。
- **导出**（RDF → DSL 或 JSON）：**未找到**。
- 转换器的许可证：转换器文档站上**未找到**许可证声明。引入前需要单独确认；这件事超出第 10 节范围，列为后续事项。

出处：
- <https://meta.linked.archi/c4/structurizr>
- <https://meta.linked.archi/docs/tools/converters/>
- <https://converters-c2cddb.gitlab.io/converters/structurizr/>（`#mapping-reference`、`#how-to-get-a-workspace-json`）

## 8. 规范与上游不一致之处（以上游为准，未改动规范原文）

| # | 规范位置 | 规范写法 | 上游实际 |
| --- | --- | --- | --- |
| S1 | §2 表“C4 本体与校验” | `c4/onto`、`c4/shapes`、`c4/viewpoints` 都是 0.1.0 | `c4/onto` 是 **0.3.0**，`c4/shapes` 是 **0.2.0**；`viewpoints`、`metamodel`、`deliverable-templates`、`structurizr` 是 0.1.0 |
| S2 | §2 依赖表、§4 表最后一行、§3“部署到哪些基础设施” | 部署类“须核实 C4 本体的部署类”，暗含部署类在 `c4:` 下 | 部署类在 `c4/structurizr#`（`structurizr:` 前缀），依赖表漏了 `c4/structurizr` 和 `c4/structurizr-shapes`；也没有容器实例类（见第 2 项） |
| S3 | §2 “core 0.6.0（已批准）”配“ArchiMate 4.0 本体” | 两者并列，默认可以搭配 | 线上 am4 本体（2026-11-22）已依赖 core 0.7.0。只有 11-19 快照的 am4 能配 core 0.6.0（见第 1 项） |
| S4 | §2 “锁定版本” | 隐含按版本号锁定 | 上游多次改内容不改版本号（am4 `4.0`、c4/onto `0.3.0`、c4/shapes `0.2.0`），只能按文件哈希锁 |
| S5 | §6 “关联谓词的确定方式”第 1 步 | “若上游已规定关联谓词，直接使用” | 上游**已经规定**：实例级默认 `skos:exactMatch`，放在 reconciliation 图，每条带 RDF 1.2 记录（DD-11/27）。但这与 AISEP 已批准的规则冲突（`docs/metamodel-spec.md` §7.1 D8 只允许三类跨记法连接；§L0 禁止 RDF 1.2 三元组项），所以不能“直接使用”，需要 Albert 定。见第 9 节 |
| S6 | §6 表“`c4:Database` ↔ `am4:DataObject`（可多个）” | 一个数据库可以关联多个数据对象 | 这不是同一事物，不满足 `skos:exactMatch` 的可替换性；如果改用 `arch:refines`，又会碰上 AISEP §7.2 的“每个节点对每个更高层级记法最多 refines 一个节点”。见第 9 节 |
| S7 | §8 “优先复用上游的视图定义、文档模板和文档生成规范” | 隐含上游模板可以直接用 | 上游 C4 部署节用了不存在的谓词，所有查询只取 `@en` 标签；没有 arc42 模板；la-generate 未公开下载（见第 6 项） |
| S8 | §4 写法规定第 2 条“三重声明模式” | 直接谓词 + 限定资源 | core 的 `arch:QualifiedRelationship` 定义列了四种表示（直接三元组、限定谓词、限定资源、`rdf:reifies` 桥）；AISEP 禁止第四种（RDF 1.2），所以实际仍是前三种，这条不受影响，只是名称有出入 |
| S9 | §6 开头“Linked.Archi 示例里靠同名标签关联的做法只能用于查询辅助” | — | 与上游一致：practice 页确实只靠 `skos:prefLabel` 同名关联，而 DD-11 要求显式链接。不算冲突，在此记录出处：<https://meta.linked.archi/docs/practice/archimate-application-layer-vs-c4-containers/#the-connection-same-name-queryable-together> |
| S10 | §5 表“组件执行某项功能或流程”：`am4:ApplicationComponent` `am4:assignedTo` `am4:Function` 或 `am4:Process` | 组件直接分派到行为 | 上游 `archimate4_relationship-tables`（<https://meta.linked.archi/archimate4/relationship-tables>）中，组件只对 `am4:Role` 和 `am4:DataObject` 有 `am4rt:permitsDirectAssignment`；组件 → Function/Process 只在 `am4rt:permitsAssignment` 里，也就是只能派生，直接写会被 L2 报 derived-only。以上游为准：写成“组件 → Role → Function/Process”，C4 模块的 R6、R7 同时接受直接分派和经一个 Role 的分派（PR #106，`docs/specs/c4-archimate4-step4.md` §4 偏离 6）。此项在 2026-11-26 补入，规范原文未改 |

已顺带核对、与规范一致的项：§5、§10 末段列出的 am4 类和谓词在线上本体里都存在（`ApplicationComponent`、`Function`、`Process`、`Service`、`Role`、`ApplicationInterface`、`DataObject`、`Event`、`Capability`、`Requirement`、`BusinessActor`、`ReadAccess`/`WriteAccess`/`ReadWriteAccess`、`Composition`、`Aggregation`、`Node`、`Device`、`SystemSoftware`，以及 `assignedTo`、`realizes`、`serves`、`accesses`、`composedOf`、`aggregates`、`triggers`）；`am4:accessType` 标为 `owl:deprecated`；`Interaction`、`Contract`、`Constraint`、`Gap`、`Representation`、`ImplementationEvent` 在本体里都不存在。上游 practice 页关于基础设施的分工（“ArchiMate owns the enterprise infrastructure model … C4 deployment diagrams … detail the specific container-to-node mapping”）也与规范 §3 一致。

## 9. 第 6 节建议方案：关联谓词与存放位置（待关口 A 确认）

### 9.1 约束

1. 上游实例级默认是 `skos:exactMatch` 加 reconciliation 图（DD-11/27）。
2. AISEP 已批准的 [docs/metamodel-spec.md](../metamodel-spec.md)：
   - §7.1（决策 D8）：跨记法连接只有三类，即 am4 枢纽关系、`arch:refines`、追溯关系；
   - §7.2：`arch:refines` 由低层级指向高层级（code → design → hub），每个节点对每个更高层级的记法最多 refines 一个节点，不用 `owl:sameAs`；
   - §7.3：`arch:Association`、`arch:HasPart` 不能跨记法；
   - L0：模型里禁止 RDF 1.2 三元组项 `<<( )>>`（[aisep/core.py](../../aisep/core.py) 有 L0 检查）。
3. 线上 `c4/onto` 的 scopeNote：C4 元素与其他语言元素之间，要用 core 的关系类型。

上游的 `skos:exactMatch` 不在 AISEP 允许的三类连接里，它要求的记录形式又被 L0 禁止；而 `arch:refines` 是上游 core 自己的跨模型追溯谓词，也正是 AISEP 对 BPMN、DDD、UML 已经在用的机制。DD-11 自己也强调，两种身份机制不能悄悄混用。

### 9.2 建议

**谓词**：不定义 AISEP 新谓词，用上游 core 的 `arch:refines`，按 AISEP 三元组写法写（直接谓词 `arch:refines`，加 `arch:qualifiedRefines` 指向 `arch:Refines` 资源，资源上写 `arch:source`、`arch:target`、`arch:inModel`）。方向由 C4 指向 am4。为此，新的 c4 记法模块定为 `aisep:notationLevel aisep:LevelDesign`（与 DDD、BPMN 同级）。

| 规范 §6 的行 | 建议写法 | 说明 |
| --- | --- | --- |
| 本方 `c4:SoftwareSystem` ↔ `am4:ApplicationComponent`，一对一 | `c4 系统 arch:refines am4 组件` | “主锚唯一”已保证至多一个；“恰好一个”和“反之亦然”由 AISEP 规则检查（§7） |
| 外部 `c4:SoftwareSystem`（含 `c4:ExternalSoftwareSystem`）↔ `am4:ApplicationComponent` | 同上，只连在 am4 侧已经建模的 | — |
| 独立治理的 `c4:Container` ↔ `am4:ApplicationComponent` | `c4 容器 arch:refines am4 组件` | 与它所属的系统各自 refines 各自的组件，互不冲突 |
| C4 人 ↔ `am4:BusinessActor` 或 `am4:Role` | `c4 人 arch:refines am4 角色或参与者` | 只能选一个主锚 |
| `c4:Database` ↔ `am4:DataObject`（可多个） | **需要 Albert 选**，见 9.3 | 与 §7.2 主锚唯一冲突 |
| 经消息队列的使用关系 ↔ `am4:Event` | 第一批**不建关联**，事件名写在 `c4:Using` 的 `skos:prefLabel` 里 | 与上游 practice Pattern 3 一致；规范把这一行列为“可选” |

**存放位置**：沿用 AISEP 现有做法（例如 [models/workbench/bpmn.ttl](../../models/workbench/bpmn.ttl) 里的 `rel-…-refines-…`），由较细的一侧维护：关联写在 `models/<slug>/c4.ttl` 里，与 C4 元素同一个文件，由 C4 侧的作者维护，随该文件一起评审。不另建 reconciliation 图或文件。am4 侧文件不因 C4 的增删而改动。

**放弃的方案及理由**：
- `skos:exactMatch` 加 reconciliation 图：上游的推荐做法，但违反 AISEP D8 和 L0，而且会和已在用的 `arch:refines` 形成两套身份机制。如果 Albert 希望与上游对齐，需要先修订 metamodel-spec（规范类文档，合并前要评审），属于更大的改动。
- AISEP 自定义“对应于”谓词：上游 core 已有合适的谓词，再加一个会违反“标准先行”，同样要改 D8。
- `owl:sameAs`：规范和上游都排除了。

### 9.3 请 Albert 拍板的问题

1. **身份谓词**：采用 `arch:refines`（推荐，贴合 AISEP D8）还是上游 DD-11 的 `skos:exactMatch`（需要先修订 metamodel-spec）？
   - **已决（Albert，2026-11-25）**：采用 `arch:refines`。
2. **数据库对多个数据对象**，可选做法：
   - (a) 一个 `c4:Database` 只 refines 一个 `am4:DataObject`；多个逻辑数据对象先在 am4 侧用 `am4:aggregates` 归到一个汇总数据对象下（推荐，不改 AISEP 规则）；
   - (b) 放宽 §7.2 的主锚唯一规则，对 Database → DataObject 开例外（要改 metamodel-spec）；
   - (c) 在 §7.1 第三类里加一个 AISEP 追溯谓词，例如 `aisep:stores`（要改 metamodel-spec）。
   - **已决（Albert，2026-11-25）**：选 (a)，先在 am4 侧聚合，再让数据库 refines 汇总数据对象。
3. **c4 模块层级**定为 design（推荐）还是另设一级？
   - **已决（Albert，2026-11-25）**：design。
4. **第 3 步引入哪一版上游**：
   - (a) 继续用 11-19 快照（推荐，与已批准的 core 0.6.0 一致；c4 文件用快照版，包括较宽的 `c4:uses` 定义域）；
   - (b) 整体升级到线上版（core 0.7.0、am4 11-22 版、c4 线上版），这意味着改变已批准的底座。
   - **已决（Albert，2026-11-25）**：选 (b)，整体升级到线上版。第 3 步因此要连同 am4 模块已加载的 core、archimate4 文件一起升级：按 AGENTS.md 硬规则 6 和元模型规范 §11 走一次显式变更，重新抓取并重算 SHA256SUMS，跑全量测试；改动涉及 `vendor/**`、`modules/**`，需要合并前评审。

## 10. 后续事项（不在本次范围）

- 规范 §2 的示例目录是 `vendor/linked-archi/`，仓库已有的是 `vendor/meta.linked.archi/`（含 SHA256SUMS、MANIFEST.json），第 3 步建议沿用现有目录。
- 引入 structurizr2linkedarchi 转换器之前，先确认它的许可证。
- 上游 C4 模板的两个缺陷（`c4:deploys`，以及只取 `@en`）可以考虑向 Linked.Archi 报告。这是对外动作，需要先征得 Albert 同意。
