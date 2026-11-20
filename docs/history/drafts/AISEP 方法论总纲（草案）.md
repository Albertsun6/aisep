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

风险与现状：Linked.Archi 核心本体 2019 年发布，最近更新 2026 年 11 月，仍在活跃维护；但基本为单人维护（Kalin Maldzhanski），多数资源标为草稿，社区关注度很低（GitHub 旧仓库 0 星）。代码托管已从 GitLab 迁走，gitlab.com/linked-archi/linked-archi-meta 已无法访问；现行仓库在 github.com/linked-archi 组织下，含 meta-core、meta-archimate、meta-basic、meta-togaf、meta-index、tools、linked-archi-apm 等。已确认 meta-archimate 为 Apache-2.0，meta-core 许可证待亲自确认。应对：把本体文件复制进自己的仓库锁定版本，不依赖在线地址；若许可证不允许，则照其结构自定义一套。

同类项目（均只覆盖 ArchiMate 单一记法，可作对照和备选）：jwvveen/archimate-rdf（ArchiMate 4.0 本体 + SHACL，"ArchiMate in RDF" 工作组讨论稿，有 BPMN 姊妹项目，可能形成事实标准，需持续关注）；AlbertoDMendoza/archimate\_ontology（OWL + SHACL，面向工具无关仓库和 AI 辅助架构）；floresbakker/OntoArchimate（RDF 词汇表族，可解析、校验、生成 ArchiMate 文档）。整个"架构知识图谱"方向目前小众但在升温，没有主流大项目。

## 8. 待办

- [ ] 在 github.com/linked-archi 确认 meta-core 的 LICENSE
- [ ] 执行《AISEP 第一步：Linked.Archi 可行性验证清单》（已单独成文），产出 spike-result.md
- [ ] 根据验证结果决定：直接采用 Linked.Archi 本体，或参考其结构自建
- [ ] 细化元模型四部分：元素骨架、关系骨架、视图、记法定义（记法定义最有技术含量）
- [ ] 在 AISEP 文件夹搭建仓库骨架：目录结构、CLAUDE.md / AGENTS.md 规则文件、各阶段文档模板与提示词
- [ ] 写架构原则文档，按裁剪后的 ADM 启动架构愿景与业务架构

## 9. 执行路线与分工

三步走，每步有明确产出：

1. 验证可行性（半天到两天）：拉取 Linked.Archi，跑通"手写模型 → SHACL 校验 → SPARQL 查询 → Claude Code 读写"最小闭环。产出 spike-result.md。
2. 定元模型规范：基于验证结果写元模型设计文档，明确三原语骨架、第一批支持的记法及其追溯关系。
3. 搭 AISEP 仓库骨架与架构原则文档，然后按裁剪后的 ADM 进入架构愿景和业务架构。

分工原则：探讨、决策、方法论文档在对话中完成；拉代码、装环境、跑校验、改文件等执行类工作交给 Claude Code，在 AISEP 目录下以本文档和验证清单为任务输入。关键节点（许可证判断、选型通过与否）由本人拍板。
