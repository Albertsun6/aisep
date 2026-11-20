# 数据架构：阶段交付物模板

> 适用：裁剪后 ADM 的“数据架构”阶段（`docs/methodology.md` §3）。本阶段是防烟囱的关键：**同一份业务数据只有一个归属上下文**。
> 用法：复制到 `models/<slug>/data.md`，按各节提示填写；`<…>` 是占位符，填完删掉提示。
> 例子：采购模型 `models/procurement/ddd.ttl`（子域、上下文、聚合、根实体及到 am4 的连接）。

## 0. 元信息
- 模型：`https://aisep.example/model/<slug>/`
- 业务负责人（`am4:Stakeholder`）：<IRI>（关口批准人另建 `arch:Stakeholder`，放 `governance.ttl`）
- 上游输入：业务架构阶段的交付物与模型（`docs/adm/02-business/`；`models/<slug>/am4.ttl` 中的能力、业务对象、业务流程）
- 状态：由批准记录推导，**不在此手写**

## 1. 入口条件
- [ ] 业务架构已过“架构决策”关口（存在对其元素的 `aisep:decision aisep:DecisionApproved` 批准记录）
- [ ] 业务对象（`am4:BusinessObject`）与业务能力（`am4:Capability`）清单已在 `am4.ttl`
- [ ] `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')` 为 PASS

## 2. 子域划分
<列出子域，每个说明类型与理由。核心域要说清“为什么是差异化竞争力”。>

| 子域（zh 名） | slug | `ddd:subdomainType` | 对应业务能力（am4） | 理由 |
|---|---|---|---|---|
| <…> | <…> | `ddd:Core` / `ddd:Supporting` / `ddd:Generic` | <capability slug> | <…> |

## 3. 限界上下文与上下文映射
<每个上下文一行；`ddd:contextType` 取 `ddd:Feature` / `ddd:Application` / `ddd:System`。>

| 上下文 | slug | 类型 | 实现的子域（`ddd:SubdomainImplementation`） | 负责团队（`ddd:Team`，可选） |
|---|---|---|---|---|

上下文之间的关系（上游 → 下游）：

| 上游 | 下游 | 关系类 | 上游角色 | 下游角色 | 暴露的聚合（`ddd:exposedAggregate`） |
|---|---|---|---|---|---|
| <…> | <…> | `ddd:UpstreamDownstream` / `ddd:CustomerSupplier` / `ddd:Partnership` / `ddd:SharedKernel` | `ddd:OpenHost` / `ddd:PublishedLanguage` | `ddd:AntiCorruptionLayer` / `ddd:Conformist` | <aggregate slug> |

约束（DDD shapes 会在 L3 检查）：CustomerSupplier 不带 CF/OHS 角色；Partnership、SharedKernel 不带角色；暴露的聚合必须属于上游上下文。

## 4. 统一领域模型
<按上下文列聚合。每个聚合：恰好 1 个根实体（`ddd:RootContainment`），恰好被 1 个上下文拥有（`ddd:Ownership`）。>

| 聚合 | 所属上下文 | 根实体 | 其他实体 / 值对象（`ddd:Containment`） | 实现的业务对象（am4:Realization → `am4:BusinessObject`） |
|---|---|---|---|---|

领域事件、命令与服务（按需）：`ddd:DomainEvent`、`ddd:Command`（可选 `ddd:payload` → 数据对象）、`ddd:DomainService`、`ddd:ApplicationService`、`ddd:Policy`、`ddd:ReadModel`；触发关系用 `ddd:EventTriggering`。

## 5. 主数据
<主数据没有专门的类，靠“唯一归属”表达：每类主数据 = 一个 `am4:BusinessObject` + 恰好一个拥有它的聚合（system of record）。其他上下文只能经上下文映射消费，不得另建同义聚合。>

| 主数据 | 业务对象 slug | 权威聚合 / 所属上下文 | 消费方上下文（经哪条映射） | 数据质量指标（可选，`arch:hasQualityMeasure`） |
|---|---|---|---|---|

## 6. 本阶段产出的模型元素

| 内容 | 类（已在模块中声明） | 记法 | 文件 |
|---|---|---|---|
| 领域、子域、上下文映射 | `ddd:Domain`、`ddd:Subdomain`、`ddd:ContextMap` | DDD | `models/<slug>/ddd.ttl` |
| 限界上下文、团队 | `ddd:BoundedContext`、`ddd:Team` | DDD | 同上 |
| 聚合与内部结构 | `ddd:Aggregate`、`ddd:Entity`、`ddd:ValueObject`、`ddd:ReadModel` | DDD | 同上 |
| 行为 | `ddd:DomainEvent`、`ddd:Command`、`ddd:DomainService`、`ddd:ApplicationService`、`ddd:Policy` | DDD | 同上 |
| DDD 关系 | `ddd:Ownership`、`ddd:RootContainment`、`ddd:Containment`、`ddd:SubdomainImplementation`、`ddd:UpstreamDownstream`、`ddd:CustomerSupplier`、`ddd:Partnership`、`ddd:SharedKernel`、`ddd:EventTriggering` | DDD | 同上 |
| 不属于任何上下文的纯技术数据（少见） | `am4:DataObject` | ArchiMate | `models/<slug>/am4.ttl` |
| 数据决策 | `ad:Decision`（用限定关系 `ad:RelatedConcept` 关联元素） | 治理 | `models/<slug>/governance.ttl` |

## 7. 必须建立的追溯（只用规范 §7.1 的三类连接）
- 枢纽关系（DDD 继承枢纽规则，可直接与 am4 元素相连）：
  - 业务流程 `am4:Realization` → 子域（采购例子 `rel-quoteApproval-realizes-procurementSubdomain`）
  - 聚合 `am4:Realization` → 业务对象（每个业务对象至少一个聚合实现它）
  - 应用组件 `am4:Composition` → 限界上下文（若 04 阶段已有 `am4:ApplicationComponent`）
- `arch:Refines`：只在出现 UML 类时用（UML → DDD，code → design），本阶段通常不写。
- 追溯关系：数据相关的 Must 级需求应有 `aisep:TestCase` 经 `aisep:Verification` 验证（可在后续阶段补，L4 会报缺口）。
- 禁止：同一个东西既写成 `ddd:Aggregate` 又写成 `am4:DataObject`（一元素一记法，L1 报错）。

## 8. 待决问题与假设
<列出尚未确认的点，以及“我假设了 X”。>

## 9. 出口条件（关口评审）
- [ ] 每个 `am4:BusinessObject` 至少被一个聚合实现；每类主数据只有一个权威聚合
- [ ] `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')` 为 PASS，L4 发现项已逐条处置
- [ ] 已按 `docs/adm/governance/` 完成“架构决策”关口评审，并写入批准记录：`aisep:ApprovalRecord`，`aisep:gate aisep:GateArchitecture`，`aisep:approves` 指向本阶段元素，`aisep:evidence` 为评审时的 commit；经 MCP 时用 `governance.record_approval`
- [ ] 不手写 `arch:approvalState`（由构建推导）
