# AISEP 实施规范：C4 与 ArchiMate 4 双模型

Nov 25, 2026 · @GalaxyTelecom

实施 AI 按本文在 AISEP 模型库中落地 C4 与 ArchiMate 4 的双模型方案：两套模型放在同一个知识图谱里，各管一类事实，通过显式关联连接。凡标注“须核实”的地方，先查上游原文再动手，不得猜测。

## 1. 任务目标与范围

在 AISEP 基础设施层的模型库中，建立 C4 与 ArchiMate 4 并存的建模能力，并能为每个系统生成 C4 视图和 arc42 文档骨架。

- **范围内**：导入上游本体与校验规则、定义 AISEP 跨模型关联规则、编写 AISEP 自有校验规则、实现 C4 视图与 arc42 骨架的生成、用一个示例系统跑通全流程。
- **范围外**：工作台前端渲染、BPMN 与 UML 的对齐、DDD 记法、代码级（C4 第 4 级）建模。
- **必须遵守的 AISEP 原则**：单一事实来源；模型是一等资产，放进 Git、有版本、要评审；全程可追溯；标准先行，没有标准不动手；自动执行，关键节点由人确认，AI 主动汇报做了什么、为什么。

## 2. 上游依赖与许可证

全部依赖来自 Linked.Archi（源码仓库 linked-archi-meta），许可证均为 CC-BY-4.0，必须署名。

| 资产 | 命名空间 | 版本 | 用途 |
| --- | --- | --- | --- |
| Core 本体 | `https://meta.linked.archi/core#` | 0.6.0（已批准） | 所有语言的共同基础 `arch:` |
| ArchiMate 4.0 本体 | `https://meta.linked.archi/archimate4/onto#` | 4.0（发布页标注 draft，须核实是否有更新） | 元素与 11 种关系 |
| ArchiMate 4.0 校验与推导 | `archimate4/shapes#`、`element-shapes#`、`principle-shapes#`、`derivation#` | 跟随本体 | 关系合法性、元素完整性、推导规则 |
| C4 元模型清单 | `https://meta.linked.archi/c4/metamodel#` | 0.1.0 | 汇总下面几项 |
| C4 本体与校验 | `c4/onto#`、`c4/shapes#`、`c4/viewpoints#` | 0.1.0 | C4 元素、关系、视图定义 |
| C4 文档模板 | `c4/deliverable-templates#` | 0.1.0 | System Overview、Component Design 两个模板 |
| Core 校验 | `core-shapes` | 跟随 core | 视图一致性检查 |

**硬性规定**

- 上游文件原样放进仓库的独立目录（例如 `vendor/linked-archi/`），锁定版本，附 LICENSE 与署名说明，不得修改。
- AISEP 的扩展一律放在自己的命名空间，通过导入和子类对齐挂到上游，不改上游文件。
- **不得引入** core-vis 和 edgy 系列，它们是 CC-BY-SA。
- C4 本体只有 0.1.0，后续可能改名或调整，升级时必须走人工关口。

## 3. 建模路线：双模型并存

ArchiMate 记录系统对企业意味着什么，C4 记录系统在技术上长什么样；同一事实只在一边记录，两边靠显式关联连接，这样才符合单一事实来源。这是 Linked.Archi 官方推荐的做法。

| 要表达的事 | 记在哪边 | 用什么元素 |
| --- | --- | --- |
| 系统在企业版图中存在 | 两边都有，必须关联 | ArchiMate Application Component ↔ C4 Software System |
| 系统向业务提供什么服务 | ArchiMate | Service、Application Interface |
| 系统内部做什么（行为） | ArchiMate | Function、Process |
| 系统拥有或处理什么数据（逻辑） | ArchiMate | Data Object |
| 数据存在哪里（物理） | C4 | Database 类容器 |
| 系统产生或消费什么事件 | ArchiMate | Event；C4 只在连线文字上注明 |
| 业务能力、需求、目标的追溯 | ArchiMate | Capability、Requirement、Goal 等 |
| 可独立运行或部署的单元 | C4 | Container |
| 容器内部的主要模块 | C4 | Component |
| 技术栈、通信协议 | C4 | 容器与关系上的 technology 属性 |
| 部署到哪些基础设施 | C4 部署视图为主 | 须核实 C4 本体的部署类；企业级基础设施清单才用 ArchiMate 技术域 |

**两条硬规则**

- 不要把每个 C4 容器都建成 ArchiMate 的 Application Component。只有当某个容器有独立的生命周期、团队、对外服务和治理时，才在 ArchiMate 侧也建一个组件并关联。
- ArchiMate 侧保持技术中立：服务、接口上不写 REST、gRPC 这类协议，协议只记在 C4 侧。

## 4. C4 侧建模规则

只用 `c4:` 本体里已有的类和属性；下表“已确认”的名称见于 Linked.Archi 官方示例，其余须打开 `c4/onto` 核对后再用。

| 概念 | 类或属性 | 状态 |
| --- | --- | --- |
| 软件系统 | `c4:SoftwareSystem` | 已确认 |
| 容器 | `c4:Container` | 已确认 |
| 数据库容器 | `c4:Database`（是 `c4:Container` 的子类） | 已确认 |
| 系统包含容器 | `c4:hasContainer` | 已确认 |
| 使用关系（直接谓词） | `c4:uses` | 已确认 |
| 使用关系（限定资源） | `c4:Using`，经 `c4:qualifiedUsing` 指向，用 `arch:source`、`arch:target` 标端点 | 已确认 |
| 技术栈、协议 | `c4:technology` | 已确认 |
| 人、组件、容器包含组件、外部系统标记 | 本体中对应的类与属性 | 须核实 |
| 部署节点、基础设施节点、容器实例 | 本体中对应的类与属性 | 须核实 |

**写法规定**

1. 每个元素必须有带语言标签的 `skos:prefLabel`，例如 `"订单 API"@zh`。
2. 每条关系同时写直接谓词和限定资源两种形式，这是 Linked.Archi 的三重声明模式；协议、说明、生命周期等元数据只挂在限定资源上。
3. 关系的说明文字（C4 连线上那句话）放在限定资源上，具体属性名须核实。
4. 不发明 `c4:` 命名空间下不存在的属性；确实缺的，在 AISEP 命名空间里定义并在第 10 节登记。

## 5. ArchiMate 4 侧建模规则

每个系统按“组件执行功能、功能实现服务、服务服务于使用方”的链条建模，不能只建一个组件就结束，否则无法向业务追溯。以下类名均已在 Linked.Archi 4.0 本体中核对。

| 要表达的事 | 写法 |
| --- | --- |
| 组件执行某项功能或流程 | `am4:ApplicationComponent` `am4:assignedTo` `am4:Function` 或 `am4:Process` |
| 功能对外提供服务 | `am4:Function` `am4:realizes` `am4:Service` |
| 服务支撑业务角色或流程 | `am4:Service` `am4:serves` `am4:Role` 或 `am4:Process` |
| 服务通过接口暴露 | `am4:ApplicationInterface`，与组件、服务的关系按关系合法性表 |
| 行为读写数据 | `am4:accesses`，限定资源用 `am4:ReadAccess`、`am4:WriteAccess`、`am4:ReadWriteAccess` 子类；不用已废弃的 `am4:accessType` |
| 某系统是某数据的权威来源 | `am4:ApplicationComponent` `am4:assignedTo` `am4:DataObject`（4.0 新增） |
| 严格包含（部分随整体存在） | `am4:composedOf`，限定资源 `am4:Composition` |
| 一般组合 | `am4:aggregates`，限定资源 `am4:Aggregation` |
| 事件触发流程 | `am4:Event` `am4:triggers` `am4:Process` |
| 向能力和需求追溯 | 服务或功能 `am4:realizes` `am4:Capability`、`am4:Requirement` |

**写法规定**

1. 行为一律用通用的 Process、Function、Service、Event；由谁执行靠 Assignment 表达，不靠元素类型。
2. 同样采用三重声明模式：直接谓词加限定资源。
3. 关系是否合法以上游 relationship-shapes 为准，不自己判断。
4. 不使用 4.0 已删除的元素：Interaction、Contract、Constraint、Gap、Representation、Implementation Event。约束用 Requirement 的特化表示。

## 6. 跨模型关联

两边模型必须用显式的关联三元组连接；Linked.Archi 示例里靠同名标签关联的做法只能用于查询辅助，不能作为唯一手段，因为改名或重名都会断链。

| C4 元素 | ArchiMate 元素 | 是否必须 | 含义 |
| --- | --- | --- | --- |
| `c4:SoftwareSystem`（本方系统） | `am4:ApplicationComponent` | 必须，一对一 | 同一个系统的两种描述 |
| `c4:SoftwareSystem`（外部系统） | `am4:ApplicationComponent` | 已在 ArchiMate 侧建模的才连 | 同上 |
| `c4:Container` | `am4:ApplicationComponent` | 仅当该容器被独立治理时 | 见第 3 节硬规则 |
| `c4:Database` | `am4:DataObject`（可多个） | 必须 | 物理存储与逻辑数据的对应 |
| C4 中的人 | `am4:BusinessActor` 或 `am4:Role` | 建议 | 同一类使用者 |
| 经消息队列的使用关系 | `am4:Event` | 可选 | 连线上注明的事件对应的事件元素 |

**关联谓词的确定方式（须核实，涉及人工关口）**

1. 先读 Linked.Archi 的跨语言映射编写指南（Authoring Cross-Language Mappings），若上游已规定关联谓词，直接使用。
2. 上游没有合适谓词时，在 AISEP 命名空间定义一个，例如“对应于”关系，并提交人工确认后再用。
3. 不使用 `owl:sameAs`：它会把两个不同类型的个体合并，推理后会产生错误的类型。
4. 关联写在哪个文件、由哪一侧维护，与谓词一起提交确认。

## 7. 校验规则

校验分两级：第一级不通过就拒绝写入，第二级只报警告；能复用上游的一律复用，AISEP 只补上游没有的。

**直接复用的上游规则（第一级）**

- ArchiMate 4.0 元素校验：命名、组合与聚合不成环、一个部分只属于一个整体等。
- ArchiMate 4.0 关系合法性：按规范附录 B 的关系表生成。
- C4 校验规则：`c4/shapes`。
- 视图一致性：`core-shapes`。

**AISEP 自有规则**

| 规则 | 级别 |
| --- | --- |
| 每个本方 `c4:SoftwareSystem` 恰好关联一个 `am4:ApplicationComponent`，反之亦然 | 第一级 |
| 每个 `c4:Container` 恰好属于一个 `c4:SoftwareSystem`（若 `c4/shapes` 已覆盖则不重复写） | 第一级 |
| 每个 `c4:Database` 至少关联一个 `am4:DataObject` | 第一级 |
| 每条关系同时有直接谓词和限定资源，两者端点一致 | 第一级 |
| 跨容器的 `c4:Using` 必须有 `c4:technology` | 第一级 |
| 每个 `am4:ApplicationComponent` 至少执行一个 Function 或 Process | 第二级 |
| 每个 `am4:Service` 至少被一个行为实现，并能追溯到 Capability 或 Requirement | 第二级 |
| 每个 `am4:DataObject` 至多一个权威来源（Assignment） | 第二级 |

规则一律用 SHACL 写，放在 AISEP 命名空间的独立文件中，每条带中文说明信息。

## 8. 视图生成与 arc42 落位

C4 视图从 C4 模型生成，ArchiMate 视图从 ArchiMate 模型生成，arc42 文档按章节从两边取数；图不手画、不单独存。生成方式优先复用上游的视图定义、文档模板和文档生成规范（Deliverable Generator Spec），须核实其可用程度后再决定是否自写。

| arc42 章节 | 内容来源 |
| --- | --- |
| 1 引言与目标、10 质量需求 | ArchiMate 的 Goal、Requirement |
| 2 约束 | ArchiMate 的 Requirement 特化（约束类） |
| 3 上下文与范围 | C4 系统上下文视图，加 ArchiMate 中该系统服务的角色与流程 |
| 4 解决方案策略 | 人工撰写，AI 起草 |
| 5 构建块视图 | C4 容器视图（第 1 级）、组件视图（第 2 级） |
| 6 运行时视图 | C4 动态视图，或 ArchiMate 的 Process 与 Triggering 链 |
| 7 部署视图 | C4 部署视图 |
| 8 横切概念 | AISEP 架构原则文档 |
| 9 架构决策 | 模型库中的审批记录（ADR） |
| 11 风险与技术债 | 人工撰写，AI 起草 |
| 12 术语表 | Business Object、Data Object 的定义 |

系统全景视图不属于单个系统，放在 TOGAF 应用架构的产出物里。

## 9. 实施步骤、人工关口与验收标准

在独立分支上按顺序做，每步单独提交；遇到人工关口就停下，汇报后等确认，不得跳过。

1. **核实**：逐项核实第 10 节的事项，写成核实报告，注明每项的上游出处。
2. **人工关口 A**：确认核实结果，以及关联谓词和关联的存放位置（见第 6 节）。
3. **引入上游**：按第 2 节放入 vendor 目录、锁定版本、附署名；用上游自带的示例数据跑一遍校验，确认环境可用。
4. **编写 AISEP 规则**：按第 7 节写 SHACL，每条规则至少配一个应通过和一个应失败的测试样例，并接入 CI。
5. **示例系统**：用 AISEP 平台自身做示例，在两边建模并建立关联，跑通全部第一级校验。
6. **生成产出物**：生成该系统的 C4 视图和 arc42 文档骨架。
7. **人工关口 B**：提交汇报，说明做了什么、为什么、有哪些偏离本文之处，确认后再合并。

**验收标准**

- [ ] 上游文件未被修改，版本已锁定，署名齐全，未引入 CC-BY-SA 资产。
- [ ] 第 7 节每条 AISEP 规则都有通过和失败两类测试，CI 全绿。
- [ ] 示例系统通过全部第一级校验，第二级警告已列出并说明原因。
- [ ] arc42 骨架中第 1、2、3、5、7、9、12 节已从模型自动填入内容。
- [ ] 所有“须核实”项都有结论和出处，没有凭猜测实现的部分。

## 10. 动手前必须核实的事项

1. Linked.Archi ArchiMate 4.0 本体发布页标注为 draft，是否已有正式版或更新；core 0.6.0 与它是否兼容。
2. `c4/onto` 中人、组件、外部系统标记、部署节点、基础设施节点、容器实例的确切类名和属性名，以及容器包含组件的谓词。
3. C4 关系说明文字放在哪个属性上。
4. Linked.Archi 跨语言映射指南规定的关联谓词与映射文件格式，是否已有现成的 C4 与 ArchiMate 4 映射文件。
5. `c4/shapes` 是否已经包含“容器只属于一个系统”等检查，避免和 AISEP 规则重复。
6. 上游视图定义、文档模板和文档生成规范能否直接用于生成 C4 视图和 arc42 骨架，还是只覆盖上游自己的模板。
7. 上游 Structurizr 本体（`c4/structurizr#`）的用途，是否可用来从 Structurizr DSL 导入或导出。

本文中所有 ArchiMate 4 元素与关系名称已按 Linked.Archi 4.0 本体核对：4.0 正式版保留了 Composition 和 Node、Device、System Software 等技术域元素。

## 11. 来源

- [Linked.Archi ArchiMate 4.0 本体](https://meta.linked.archi/archimate4/onto/)
- [Linked.Archi ArchiMate 4.0 建模指南](https://meta.linked.archi/docs/guide/archimate/archimate-4.0-modeling-guide/)
- [Linked.Archi C4 元模型清单](https://meta.linked.archi/c4/metamodel/)
- [Linked.Archi：ArchiMate 应用层与 C4 容器](https://meta.linked.archi/docs/practice/archimate-application-layer-vs-c4-containers/)
- [ArchiMate 4 正式版分析（引用 Open Group C260）](https://4m4.it/longforms/archimate_4_and_the_cartography_of_complexity/)
