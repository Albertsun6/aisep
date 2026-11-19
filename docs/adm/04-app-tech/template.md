# 应用架构 + 技术架构：阶段交付物模板

> 适用：裁剪后 ADM 的“应用架构 + 技术架构”阶段（`docs/methodology.md` §3）：系统边界、集成方式、技术基线。
> 用法：复制到 `models/<slug>/app-tech.md`，按各节提示填写；`<…>` 是占位符。
> 例子：采购模型 `models/procurement/am4.ttl`（应用组件、服务）、`ddd.ttl`（组件组合限界上下文）、`code.ttl`（可部署包实现组件）。

## 0. 元信息
- 模型：`https://aisep.example/model/<slug>/`
- 业务负责人（`am4:Stakeholder`）：<IRI>（关口批准人另建 `arch:Stakeholder`，放 `governance.ttl`）
- 上游输入：数据架构（`docs/adm/03-data/`，`models/<slug>/ddd.ttl`）、业务架构（`models/<slug>/am4.ttl` 中的流程与需求）
- 状态：由批准记录推导，**不在此手写**

## 1. 入口条件
- [ ] 数据架构已过“架构决策”关口（限界上下文与聚合已批准）
- [ ] `$PY tools/aisep.py gate models/<slug>/*.ttl` 为 PASS

## 2. 系统边界（应用组件）
<每个应用组件一行。原则：组件边界对齐限界上下文，一个上下文只落在一个组件里；一个组件可以组合多个上下文。>

| 应用组件（zh 名） | slug | 组合的限界上下文（`am4:Composition` → `ddd:BoundedContext`） | 新建 / 复用 / 采购 | 负责人 |
|---|---|---|---|---|

## 3. 应用服务与接口
| 服务（`am4:Service`） | 由谁提供（`am4:Function` 经 `am4:Realization`） | 服务谁（`am4:Serving` → 流程 / 组件） | 暴露接口（`am4:ApplicationInterface`） |
|---|---|---|---|

## 4. 集成方式
<组件之间每一条集成一行。语义上的上下游关系已在数据架构的上下文映射里定；这里补技术方式。>

| 提供方 | 消费方 | 对应的上下文映射 | 方式（同步 API / 事件 / 文件 / 共享库） | 接口 | 数据（`am4:DataObject` 或聚合） |
|---|---|---|---|---|---|

建模提示（以 `gate` L2 为准）：ArchiMate 4.0 关系表中 组件 → 组件 的 `am4:Serving` / `am4:Flow` 只允许作为派生关系，直接画会报 Warning。推荐写法：组件 `am4:Composition` → 接口，接口 `am4:Assignment` → 服务，服务 `am4:Serving` → 消费方组件（这三步表中都可直接画）。

## 5. 技术基线
<列出技术栈的标准选型，每项给出版本策略与理由；与架构原则冲突时写 ADR。>

| 类别 | 选型 | 元素类 | 理由 / ADR |
|---|---|---|---|
| 运行环境 / 中间件 / 数据库 | <…> | `am4:SystemSoftware` | <…> |
| 计算节点 / 设备 | <…> | `am4:Node` / `am4:Device` | <…> |
| 网络 | <…> | `am4:CommunicationNetwork` / `am4:Path` | <…> |
| 技术接口 | <…> | `am4:TechnologyInterface` | <…> |
| 部署单元 | <…> | `aisep:Deployable`（⊑ `am4:Artifact`，带 `aisep:packageUrl`） | <…> |

部署关系（表中可直接画）：`am4:Node` `am4:Composition` → `am4:SystemSoftware`；`am4:SystemSoftware` `am4:Assignment` → `am4:Artifact`；`am4:Artifact` `am4:Realization` → `am4:ApplicationComponent`。

## 6. 非功能需求与质量指标
| 需求（`am4:Requirement`，`aisep:priority`） | 适用对象 | 质量指标（`arch:hasQualityMeasure`，`aisep:target` + `aisep:unit`） | 验证方式（`aisep:TestCase`） |
|---|---|---|---|

## 7. 本阶段产出的模型元素

| 内容 | 类 | 记法 | 文件 |
|---|---|---|---|
| 应用层 | `am4:ApplicationComponent`、`am4:ApplicationInterface`、`am4:Service`、`am4:Function`、`am4:DataObject` | ArchiMate | `models/<slug>/am4.ttl` |
| 技术层 | `am4:Node`、`am4:Device`、`am4:SystemSoftware`、`am4:TechnologyInterface`、`am4:CommunicationNetwork`、`am4:Path`、`am4:Artifact` | ArchiMate | 同上 |
| 约束与原则 | `am4:Requirement`、`am4:Principle` | ArchiMate | 同上 |
| 关系 | `am4:Composition`、`am4:Aggregation`、`am4:Assignment`、`am4:Realization`、`am4:Serving`、`am4:Access`、`am4:Flow`、`am4:Triggering` | ArchiMate | 同上 |
| 部署单元 | `aisep:Deployable` | 代码扩展 | `models/<slug>/code.ttl` |
| 组件内部设计（可选，细到代码级时） | `uml:Component`、`uml:Interface`、`uml:Node` | UML | `models/<slug>/uml.ttl` |
| 技术选型决策 | `ad:Decision`（`ad:RelatedConcept` → 元素） | 治理 | `models/<slug>/governance.ttl` |
| 视图（可选） | `arch:Diagram`，视点如 `am4vp:ApplicationCooperationViewpoint`、`am4vp:TechnologyUsageViewpoint`、`am4vp:ImplementationAndDeploymentViewpoint` | — | `models/<slug>/am4.ttl` |

（`am4vp:` = `https://meta.linked.archi/archimate4/viewpoints#`）

## 8. 必须建立的追溯（只用规范 §7.1 的三类连接）
- 枢纽关系：应用组件 `am4:Composition` → 限界上下文（每个限界上下文恰好被一个组件组合）；服务 `am4:Serving` → 业务流程（每个需要系统支撑的流程至少一个）；组件或可部署包 `am4:Realization` → 需求（适用时）。
- `arch:Refines`：UML 元素只能 refines 到 DDD 或 am4（code → design / hub），同一更高记法最多一个主锚；不要把 `uml:Component` 加上 am4 类型。
- 追溯关系：Must 级非功能需求要有 `aisep:TestCase` 经 `aisep:Verification` 验证；代码就位后用 `aisep:CodeLocation` 经 `aisep:Implementation` 指向限界上下文或组件（`models/procurement/code.ttl`）。

## 9. 待决问题与假设
<列出尚未确认的点，以及“我假设了 X”。>

## 10. 出口条件（关口评审）
- [ ] 每个限界上下文落在恰好一个应用组件里；每条跨组件集成都能对应到一条上下文映射
- [ ] 技术基线每项有选型与理由；偏离架构原则的有 ADR
- [ ] `$PY tools/aisep.py gate models/<slug>/*.ttl` 为 PASS，L2 Warning 与 L4 发现项逐条处置
- [ ] 已按 `docs/adm/governance/` 完成“架构决策”关口评审并写入批准记录（`aisep:ApprovalRecord`，`aisep:gate aisep:GateArchitecture`，`aisep:evidence` 为评审时的 commit；经 MCP 时用 `governance.record_approval`）；不手写 `arch:approvalState`
