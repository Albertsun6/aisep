# AISEP 方法论总纲（草案）

## 1. 目标与定位

AISEP 是以 AI 辅助贯穿全过程软件研发（SDLC）的工程体系。目标是企业级、可持续增长、可长期维护的大型系统，而不是一个个烟囱式的小工具。需求是一切的源头：需求必须来自业务需求，业务需求理解不清，后面全错。

## 2. 三层结构

- 基础设施层：统一模型仓库 + AI 接入。只负责存元素、关系、视图，并让 AI 能读写，不绑定任何方法论。
- 方法论层：裁剪后的 TOGAF ADM，定义要建哪些模型、用什么记法、阶段之间如何衔接。
- 业务系统层：具体业务系统在该体系内被设计和实现。

方法论调整时基础设施不动；平台一期范围收敛在基础设施层。

## 3. 裁剪后的 TOGAF ADM

保留并做扎实的核心阶段：

- 架构愿景 + 业务架构：业务能力地图、价值流。
- 数据架构：统一领域模型、主数据，这是防烟囱的关键。
- 应用架构 + 技术架构：系统边界、集成方式、技术基线。
- 需求管理：作为中枢贯穿所有阶段。

简化或合并：

- 预备阶段简化为一份架构原则文档。
- 机会与解决方案 + 迁移规划合并为路线图阶段。
- 实施治理 + 变更管理融入 SDLC 的评审关口和版本管理。

## 4. 需求阶段方法

超级个体模式的最大风险是“自己骗自己”：需求在脑子里清楚但没写出来。因此让 AI 当追问者而不是记录员：

1. AI 采访式追问，挖出边界条件、异常情况、使用者、不做什么。
2. AI 用业务语言复述并画业务流程，确认“就是这个意思”。
3. 落成带验收标准的需求文档，验收标准直接供测试阶段使用。

## 5. 平台定位与差异点

参考对象：Visual Paradigm（统一仓库，ArchiMate / BPMN / UML 互相关联，内置 TOGAF ADM Guide-Through 向导）。

自建平台的差异点：

- AI 深度接入：AI 直接读写模型、由模型生成代码和测试、反向从代码校验模型。
- 端到端贯通：从企业架构一直管到代码仓库、测试、DevOps、CI/CD、部署发布，全部在一条追溯链上。

分期策略：一期只做统一模型仓库 + AI 接口；代码仓库、CI/CD 先用 GitHub 和现成工具，平台只做关联与追溯，追溯链跑通后再逐步往下吞。

## 6. 基础设施层：元模型

底层只有三个原语：

- 元素：唯一标识、类型、名称、描述、属性包、所属记法。
- 关系：来源、目标、关系类型、方向性。
- 视图：包含哪些元素和关系，加布局信息；布局只是展示，不进语义。

外加记法定义：每种记法（ArchiMate、BPMN、UML、DDD、测试模型）声明自己的元素类型、关系类型和合法组合。记法规则放在上层做校验，不写死在存储里，新增记法不改底层。

跨记法追溯是平台的灵魂：BPMN 的活动 → ArchiMate 的业务能力 → DDD 的聚合 → UML 的类 → 测试用例。本质上这是一套自定义 DSL：底层通用原语 + 各记法的“方言”。DSL 应为文本格式（可进 Git、AI 易读写），图形界面只是文本的渲染。

## 7. 开源参考与选型建议

候选：

- Linked.Archi：RDF/OWL 本体 + SHACL 校验 + SKOS 分类。核心本体即元素、关系、视图三原语，各记法规则导入核心规则再叠加约束。已覆盖 ArchiMate 3.2/4.0、BPMN、UML、C4、Backstage、TOGAF 10。附带可执行 SPARQL 问题集，可作为 AI 查询接口。配套查询工具只依赖 Python 3.11 + PyYAML（可选 pyoxigraph、pyshacl），无需三元组库或 JVM，可离线。
- Modelio：开源桌面建模工具（Java/Eclipse），支持 UML2、BPMN2、ArchiMate、TOGAF。核心 GPLv3，关键 API Apache 2.0。元模型完整但封在工具内，适合参考设计思路。
- Archi：开源 ArchiMate 工具，模型交换格式公开，可参考存储方式。
- 其他：Eclipse EMF/Ecore 与 OMG MOF（通用元建模），Structurizr DSL 与 LikeC4（文本架构 DSL），Backstage（服务目录，对应后期 DevOps 部分）。

建议：底层数据模型采用 Linked.Archi 的本体结构，RDF 存储 + SHACL 校验；Modelio、Visual Paradigm 作为工作流与界面参考；自研精力集中在 AI 接入和 DevOps 延伸。

风险与现状：Linked.Archi 核心本体 2019 年发布，最近更新 2026 年 11 月，仍在活跃维护；但基本为单人维护（Kalin Maldzhanski），多数资源标为草稿，社区关注度很低（GitHub 旧仓库 0 星）。代码托管已从 GitLab 迁走，gitlab.com/linked-archi/linked-archi-meta 已无法访问；现行仓库在 github.com/linked-archi 组织下，含 meta-core、meta-archimate、meta-basic、meta-togaf、meta-index、tools、linked-archi-apm 等。现行本体为 CC-BY-4.0（需署名）；core-vis 和 edgy 系列为 CC-BY-SA，不得引入；GitHub 旧仓库为 Apache-2.0；本体源码仓库不公开，只能获取发布成品。应对：把本体文件复制进自己的仓库锁定版本，不依赖在线地址；若许可证不允许，则照其结构自定义一套。

同类项目（均只覆盖 ArchiMate 单一记法，可作对照和备选）：jwvveen/archimate-rdf（ArchiMate 4.0 本体 + SHACL，"ArchiMate in RDF" 工作组讨论稿，有 BPMN 姊妹项目，可能形成事实标准，需持续关注）；AlbertoDMendoza/archimate\_ontology（OWL + SHACL，面向工具无关仓库和 AI 辅助架构）；floresbakker/OntoArchimate（RDF 词汇表族，可解析、校验、生成 ArchiMate 文档）。整个"架构知识图谱"方向目前小众但在升温，没有主流大项目。

## 8. 待办

- [x] 在 github.com/linked-archi 确认 meta-core 的 LICENSE
- [x] 执行《AISEP 第一步：Linked.Archi 可行性验证清单》（已单独成文），产出 spike-result.md（结果见 spike-result.md）
- [x] 已决定：直接采用 Linked.Archi 本体
- [x] 细化元模型四部分：元素骨架、关系骨架、视图、记法定义（记法定义最有技术含量）（见 `docs/metamodel-spec.md` §4–§6，模块在 `modules/`）
- [x] 在 AISEP 文件夹搭建仓库骨架：目录结构、CLAUDE.md / AGENTS.md 规则文件、各阶段文档模板与提示词（各阶段模板与提示词在 `docs/adm/<阶段>/`）
- [x] 写架构原则文档（`docs/principles.md`）
- [ ] 按裁剪后的 ADM 启动架构愿景与业务架构：模板与提示词已备（`docs/adm/01-vision/`、`docs/adm/02-business/`），还没有真实系统走过这两个阶段；§10 的第一条链路有意跳过愿景阶段
- [ ] 走通第一条端到端链路，按 §10 的出口标准逐条给出证据

## 6a. 跨记法对齐设计（已决策）

枢纽记法：ArchiMate 4.0（The Open Group 2026 年 4 月发布，十年来首次大版本，概念精简约 30%，从零起步直接采用）。

对齐机制：采用 Linked.Archi 的子类对齐方式，而不是另建映射表。其他记法的元素和关系直接声明为 ArchiMate 对应概念的子类，例如 BPMN 网关是 ArchiMate 连接点的子类、BPMN 顺序流是触发关系的子类。这样一套 SPARQL 查询即可穿透多种记法。

各记法的落位：

- BPMN：流程映射到 ArchiMate 流程，泳道/参与者通过分配关系挂接。Linked.Archi 已有现成对齐。
- UML：活动映射到 ArchiMate 功能，类/组件落在应用域。Linked.Archi 已有现成对齐。
- DDD：Linked.Archi 没有现成记法，需自定义一个小记法（限界上下文、聚合、实体、值对象、领域事件、领域服务），对齐到 ArchiMate 应用域和数据概念。
- 测试：测试用例、覆盖状态作为"扩展"（横切属性）挂到任意元素上，而不是独立建模语言。

模块三分法（沿用 Linked.Archi）：建模语言贡献可实例化的元素与关系类型；扩展贡献可挂在任何元素上的横切属性（决策、质量属性、成本、治理状态、测试覆盖）；框架层（TOGAF ADM 等）定义过程与交付物。

~~待设计：DDD 记法的元素类型、关系类型及其到 ArchiMate 4.0 的对齐公理。~~ 已完成：见 `docs/metamodel-spec.md` §6.4，模块在 `modules/ddd/`。
~~待验证：跨记法追溯（BPMN→ArchiMate→DDD→UML→测试）本次 spike 未覆盖，需单独验证。~~ 已在元模型原型上验证：一条通用查询从测试用例经 ArchiMate、DDD 走到代码，BPMN、UML 节点作为 refines 分支挂在路径旁（`docs/metamodel-spec.md` §7.1、§15）。真实模型上的验证见 §10。

## 9. 执行路线与分工

四步走，每步有明确产出：

1. 验证可行性（半天到两天）：拉取 Linked.Archi，跑通"手写模型 → SHACL 校验 → SPARQL 查询 → Claude Code 读写"最小闭环。产出 spike-result.md。
2. 定元模型规范：基于验证结果写元模型设计文档，明确三原语骨架、第一批支持的记法及其追溯关系。
3. 搭 AISEP 仓库骨架与架构原则文档，然后按裁剪后的 ADM 进入架构愿景和业务架构。
4. 第一条端到端链路：用一条真实小需求把"AI 经 MCP 写模型 → 从代码查回业务能力 → 人在工作台批准 → 合入主干"走通一遍。入口、出口标准与步骤见 §10。

分工原则：探讨、决策、方法论文档在对话中完成；拉代码、装环境、跑校验、改文件等执行类工作交给 Claude Code，在 AISEP 目录下以本文档和验证清单为任务输入。关键节点（许可证判断、选型通过与否）由本人拍板。设计会话不直接产出文件，所有文件的新建和修改均由执行会话完成，设计会话以交接话术形式提出。

## 10. 第四步：第一条端到端链路

目的：证明三处集成都有真实调用，而不只是测试通过——AI 经 MCP 写模型、固定查询从代码位置查回业务能力、工作台批准写回模型仓库。

### 10.1 载体与裁剪

- **载体**：工作台自身的一条小需求（自举），Albert 2026-11-21 定为"批准进度展示"。代码在 `aisep-workbench` 仓库，模型与批准在本仓库。
- **新建模型目录**，不动 `models/procurement/` 示例。根命名空间继续用占位符 `https://aisep.example/`，以后统一迁移。（PR #43 建的 `models/workbench/` 已合入 `main`。）
- **只建追溯必需的元素**：需求 + 验收标准 → 流程 → 能力（子域）→ 限界上下文 → 代码位置 + 实现关系 → 测试用例 + 验证关系。
- **已知裁剪**：架构愿景、路线图阶段本次不走；不建 BPMN、UML 节点，所以整条链不需要 `arch:refines`。以后若加 BPMN 或 UML 节点并被代码或测试指向，必须 refines 到枢纽元素（`docs/metamodel-spec.md` §7.2）。

推荐的元素与关系（类型都已在 `main` 的模块里）：

| 元素 | 类型 | 关系（源 → 目标） | §7.1 类别 |
|---|---|---|---|
| 需求 | `am4:Requirement`，带 `aisep:priority` | — | — |
| 验收标准 | `aisep:AcceptanceCriterion`，带 `aisep:gherkin` | `am4:Aggregation` 需求 → 验收标准 | 枢纽关系 |
| 流程 | `am4:Process` | `am4:Realization` 流程 → 需求 | 枢纽关系 |
| 能力 | `ddd:Subdomain`（是 `am4:Capability` 的子类） | `am4:Realization` 流程 → 子域 | 枢纽关系 |
| 限界上下文 | `ddd:BoundedContext` | `ddd:SubdomainImplementation` 限界上下文 → 子域 | 枢纽关系 |
| 代码位置 | `aisep:CodeLocation` | `aisep:Implementation` 代码位置 → 限界上下文 | 追溯关系 |
| 测试用例 | `aisep:TestCase` | `aisep:Verification` 测试用例 → 验收标准 | 追溯关系 |

每个元素都带中文 `skos:prefLabel`，否则工作台里看不到名字。写入层只拒绝新增的 L0–L2 违规；语义上不该有的连接（例如代码位置直接实现需求）写入层不拦，要靠评审把关。

### 10.2 入口标准

- 编码代理里已启用项目的 `aisep` MCP 服务器，`tools/list` 返回 agent 画像的 11 个工具（启用方法见 `README.md`）。
- 从最新 `origin/main` 开 `claude/<主题>` 分支的 worktree，在 worktree 里起服务；不从落后的主检出起服务。
- 新模型目录已手写：一个 `arch:Model` 声明和一个人类 `arch:Stakeholder`（带 `arch:inModel` 和中文 `prefLabel`，照 `models/procurement/governance.ttl` 写）。MCP 写工具建不了模型本身：目录不存在时报 `MODEL_NOT_FOUND`；目录在但没有 `arch:Model` 声明时，写入能成功，`gate` 报 L3 违规（`arch:inModel` 须指向 `arch:Model`）。
- 载体需求已定。

### 10.3 实现与测试两段怎么落进模型

**实现**：

- 代码位置是 `aisep:CodeLocation`：恰好一个 `schema:codeRepository`（仓库 URL，写成 IRI）、恰好一个 `aisep:path`（字符串）；`aisep:symbol`、`aisep:swhid` 可选，后者可以把位置锚定到具体提交（`modules/ext-code/shapes.ttl` EC1–EC4）。
- 用 `aisep:Implementation` 从代码位置连到它实现的设计元素（本链路是限界上下文）。目标必须是模型元素（EC6）。
- 代码文件不必已经存在，可以先登记计划中的路径，代码写好后路径即生效。
- 代码与模型分属两个仓库，追溯只靠代码位置里的仓库地址和路径，两边的 PR 之间没有机制关联。

**测试**：

- 测试用例是 `aisep:TestCase`，用 `aisep:Verification` 连到它验证的验收标准。两步要连着写：只有测试用例、没有验证关系时 `gate` 报 EV1 违规。
- Must 级需求没有测试时，`gate` 给 L4 Warning（不阻断）。
- **测试结果：第二条链路起，回写真实 CI 的结果。** 测试结果是 `aisep:TestResult`（`aisep:resultOf` 指向测试用例，`aisep:verdict` 取 `aisep:VerdictScheme` 的一个值，`prov:generatedAtTime` 为 `xsd:dateTime`）。只写真实跑过的结果：代码 PR 合入后，取代码仓库主干上那次合并的 CI 运行，按日志里每条测试的结果行逐条写，经 MCP 写工具新增，走普通模型 PR，不需要批准，合入后推导为 Proposed。代码没写、测试没真实跑过之前不写结果，免得模型里出现虚构证据。第一条链路没有写结果；第二条链路的 4 个结果见 `models/workbench/verification.ttl` 的 `tr*1e77676`。
- **测试用例怎么对上测试代码**：元模型里测试用例没有指向测试文件或测试名的属性，只能在 `skos:definition` 里写明测试文件和测试标题，测试代码照抄标题。测试用例批准后，标题就不能再改，否则要重新批准。
- **测试结果的运行出处（验证扩展 v0.3.0 起）。** 测试结果用三个可选属性记下这次运行：`aisep:testedCommit`（被测提交，40 位小写十六进制）、`aisep:ciRun`（CI 运行网址，IRI）、`schema:codeRepository`（代码仓库网址，IRI），各至多一个（`modules/ext-verification/shapes.ttl` EV11–EV13）。前两个只能写在测试结果上（EV14），不能借用到代码位置、测试用例等元素上。固定查询可以直接取到提交号，不再从 `skos:note` 的字面量里解析。（此前没有这些属性，运行与提交只能写进 `skos:note` 的固定格式 `ciJob=… ; commit=… ; repo=…`。）
- **元模型限制：代码位置批准后补不了提交锚点。** `aisep:swhid` 的定义域只有 `aisep:CodeLocation`。代码位置在写代码之前就登记并批准了，之后补 `swhid` 就是改已批准元素，所以批准过的代码位置补不上提交锚点。提交信息改由测试结果承载（`aisep:testedCommit`，见上一条）：从代码位置经固定查询走到测试结果，就能拿到被测的提交；没有测试结果的代码位置仍然没有提交锚点。
- 从代码位置查到测试结果的固定查询是 `docs/queries/code-to-tests.rq`：代码位置 → 设计元素 → 能力 → 需求 → 验收标准 → 测试用例 → 测试结果。代码只连到限界上下文、需求只连到流程，两者在能力处汇合，所以会列出同一能力下所有需求的测试。

### 10.4 固定追溯查询

把"代码位置 → 设计元素 → 业务能力"的查询存成固定查询文件，经 `model_query` 真实调用。查询按限定关系资源遍历，类型判断走 `rdf:type/rdfs:subClassOf*`：

```sparql
SELECT ?code ?repo ?path ?design ?designLabel ?cap ?capLabel WHERE {
  ?i a/rdfs:subClassOf* aisep:Implementation ; arch:source ?code ; arch:target ?design .
  ?code schema:codeRepository ?repo ; aisep:path ?path ; arch:inModel <模型 IRI> .
  ?design skos:prefLabel ?designLabel .
  ?r a/rdfs:subClassOf* am4:Realization ; arch:source ?design ; arch:target ?cap .
  ?cap a/rdfs:subClassOf* am4:Capability ; skos:prefLabel ?capLabel } ORDER BY ?code
```

这条查询已存为 `docs/queries/code-to-capability.rq`。`model_query` 在无网络的子进程里执行，查询里的 `SERVICE` 子句发不出请求，写了会被拒（`QUERY_NOT_READONLY`）；`am4:Service`、`?service` 这类前缀名和变量照常可用（规则见 `docs/mcp-interface.md` 的 `model_query` 一节）。

### 10.5 固定顺序：写模型并提交 → 评审修完 → 批准 → 推送 → 合并

1. **写模型并提交**：代理在 worktree 里经 MCP 调 `model_add_element`、`model_add_relationship`（先 `dryRun` 再真实写入）。写工具只改工作区、不提交；代理跑 `gate` 为 PASS 后，按明确路径暂存并提交，推送，开 PR。
2. **评审修完**：独立评审这次模型改动，修完，CI 绿。返工都在这一步做完。
3. **批准**：Albert 在工作台关口页点批准。批准工具 `governance_record_approval` 只在 workbench 画像里，编码代理看不到也不能代批。它在分支检出的工作区新建一个批准记录文件并提交一次，`evidence` 是被批准的头提交。只批元素，不把 `arch:Model` 本身列进 `approves`，否则以后每次往这个模型加东西都要重批。被批准的内容提交不能已经在 `main` 上，否则只能批 `GateRelease`，所以批准必须在合并之前。
4. **推送**：推送批准提交，PR 头前进到批准提交。新头只比评审过的头多一个合法批准提交（批的正是评审过的头、这条记录被 `mergecheck` 选中、合并前重算 `problems` 为空）时，按 ADR-019 第 3 款「批准提交豁免重评」不再重评，否则对新头重新评审；核对条款以 `AGENTS.md`「分支与合并」第 2 条为准。
5. **合并**：按 `AGENTS.md`「分支与合并」的三步（合并前重算、复核目标分支没动、合并与合并后核验）执行。

**批准之后分支不能再动。** `mergecheck` 要求从 `evidence` 到分支头之间只有批准提交，批准的内容在 `evidence` 和合并结果之间也不能变：

| 批准之后的动作 | `mergecheck` 的结论 |
|---|---|
| 再加任何内容提交 | `not-approval-commit`（若仍拿旧的头提交去批，批准工具报 `STALE_HEAD`） |
| 把 `main` 合进分支 | `merge-commit-in-range` |
| rebase、squash，或 amend 被批准的提交（改写 `evidence` 及之前的历史） | `evidence-not-ancestor` |
| 被批准的元素在合并结果里变了 | `approved-content-drifted` |

所以"评审修完"必须在"批准"之前。批准之后若必须返工，只能在新的头上重批：同一关口、`approves` 覆盖旧记录、时间更晚，旧记录就不再参与检查。批准之前合 `main` 或 rebase 都没问题。

### 10.6 出口标准

每条都能跑命令或看页面证伪：

1. `git log -- models/<新模型>` 里有经 MCP 写入产生的提交，回报附工具调用记录。
2. 固定查询从一个真实代码位置返回对应的业务能力。
3. `models/<新模型>/governance/` 下有一条由工作台触发的批准记录，`evidence` 是真实提交。
4. 合并后，工作台"架构全景"里这些元素显示为已批准。
5. 整个过程由 Albert 在真实窗口里操作过一遍，不是只有测试通过。

本期还要让批准之后的进度可见：待批准 → 已批准待推送 → 已推送待合并 → 已合入，全部从 Git 推导，不存进行中状态（ADR-013）。（工作台的进度展示与一键启动脚本已合入：aisep-workbench PR #8、#9。）

### 10.7 后续能力放在哪一期

- **一期**：统一模型仓库 + MCP Server（ADR-008），工作台与编码代理都是它的客户端。代码仓库、CI/CD 先用 GitHub 和现成工具，平台只做关联与追溯（§5）。
- **本期**（Albert 2026-11-21 定）：第一条链路、批准进度展示、待批准关口到关口页的入口、一键启动脚本。
- **由模型生成代码**：未定。第一条链路里代码由人或代理照常写，模型只登记代码位置。
- **测试结果回写模型**：第二条链路起，回写真实 CI 的测试结果（§10.3）。测试结果指不到 CI 运行或提交的限制已解决：验证扩展 v0.3.0 给测试结果加了 `aisep:testedCommit`、`aisep:ciRun`（Albert 2026-11-21 定）。代码位置批准后补不上 `swhid` 的限制保留，提交信息由测试结果承载。
- **DevOps 延伸**（CI/CD、部署发布进追溯链）：未定。元模型已有 `aisep:Deployable`（`aisep:packageUrl`），但不在本期链路里。
