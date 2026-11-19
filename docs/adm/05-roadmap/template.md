# 路线图：阶段交付物模板

> 适用：裁剪后 ADM 的“路线图”阶段（`docs/methodology.md` §3），由“机会与解决方案”和“迁移规划”合并而成：从基线到目标，分几个平台期、做哪些工作包、交付什么。
> 用法：复制到 `models/<slug>/roadmap.md`，按各节提示填写；`<…>` 是占位符。
> 例子：采购模型目前没有路线图元素；其目标态元素见 `models/procurement/am4.ttl`、`ddd.ttl`、`code.ttl`。

## 0. 元信息
- 模型：`https://aisep.example/model/<slug>/`
- 业务负责人（`am4:Stakeholder`）：<IRI>（关口批准人另建 `arch:Stakeholder`，放 `governance.ttl`）
- 上游输入：业务、数据、应用 + 技术架构的已批准元素（`docs/adm/02-business/`、`03-data/`、`04-app-tech/`）
- 状态：由批准记录推导，**不在此手写**

## 1. 入口条件
- [ ] 数据架构、应用 + 技术架构均已过“架构决策”关口
- [ ] `$PY tools/aisep.py gate models/<slug>/*.ttl` 为 PASS

## 2. 差距分析（机会与解决方案）
<比较基线与目标，列出差距。ArchiMate 4.0 已无 Gap 元素，差距只记在本表，不进模型；每个差距要能落到第 4 节的某个工作包。>

| 差距 | 基线（现有元素 IRI 或“无”） | 目标（目标元素 IRI） | 处理方式（新建 / 改造 / 替换 / 退役） | 解决它的工作包 |
|---|---|---|---|---|

替换与退役：被替换的元素加 `dcterms:isReplacedBy` 指向替换者（目标必须是某个模型里的元素），可选 `owl:deprecated true`；构建会推导为 Superseded。指向它的 `arch:Refines` 会在 L4 提示迁移。

## 3. 平台期（Plateau）
<从基线到目标的若干稳定状态，按时间排序。每个平台期列出它包含的目标元素。>

| 平台期 | slug | 预计时间 | 包含的元素（`am4:Aggregation` → 组件 / 服务 / 节点 / 数据对象 / 需求） | 下一个平台期（`am4:Triggering`） |
|---|---|---|---|---|

## 4. 工作包
| 工作包 | slug | 所属平台期 | 前置工作包（`am4:Triggering`） | 负责角色（`am4:Role` `am4:Assignment` →） | 交付物 | 实现的需求（`am4:Realization` → `am4:Requirement`） |
|---|---|---|---|---|---|---|

排期粒度到工作包为止；更细的任务进 issue 跟踪系统，不进模型。

## 5. 交付物
| 交付物 | slug | 产出它的工作包（`am4:Realization` 工作包 → 交付物） | 实现的目标元素（`am4:Realization` → 组件 / 节点 / 服务 / 数据对象） | 实现的平台期（`am4:Realization` → `am4:Plateau`） |
|---|---|---|---|---|

## 6. 风险、依赖与迁移策略
<关键风险、外部依赖、数据迁移和并行运行策略。重要的取舍写成 `ad:Decision`。>

## 7. 本阶段产出的模型元素

| 内容 | 类 | 记法 | 文件 |
|---|---|---|---|
| 平台期、工作包、交付物 | `am4:Plateau`、`am4:WorkPackage`、`am4:Deliverable` | ArchiMate | `models/<slug>/am4.ttl` |
| 关系 | `am4:Aggregation`、`am4:Composition`、`am4:Triggering`、`am4:Realization`、`am4:Assignment` | ArchiMate | 同上 |
| 替换 / 退役标记 | `dcterms:isReplacedBy`、`owl:deprecated`（写在被替换元素上） | — | 被替换元素所在文件 |
| 迁移决策 | `ad:Decision`（`ad:RelatedConcept` → 元素） | 治理 | `models/<slug>/governance.ttl` |
| 视图（可选） | `arch:Diagram`，视点如 `am4vp:MigrationViewpoint`、`am4vp:ProjectViewpoint`、`am4vp:ImplementationAndMigrationViewpoint` | — | `models/<slug>/am4.ttl` |

（`am4vp:` = `https://meta.linked.archi/archimate4/viewpoints#`）

以下组合在 ArchiMate 4.0 关系表中可直接画：工作包 → 交付物 / 组件 / 节点 / 服务 / 需求 的 `am4:Realization`；交付物 → 组件 / 节点 / 服务 / 数据对象 / 需求 / 平台期 的 `am4:Realization`；工作包 → 工作包、平台期 → 平台期 的 `am4:Triggering`；平台期 → 组件 / 节点 / 服务 / 数据对象 / 业务对象 / 需求 的 `am4:Aggregation`；角色 → 工作包 的 `am4:Assignment`。其他组合以 `gate` L2 为准（工作包 → 平台期 只能派生，改经交付物）。

## 8. 必须建立的追溯（只用规范 §7.1 的三类连接）
- 枢纽关系：每个目标平台期聚合了它包含的目标元素；限界上下文、聚合继承枢纽规则，可直接被平台期聚合、被交付物实现。
- 每个第 2 节的差距都能经“工作包 → 交付物 → 目标元素”追到；每个 Must 级需求至少被一个工作包或交付物实现。
- 追溯关系：迁移决策用 `ad:RelatedConcept` 关联相关元素；代码与部署（`aisep:Implementation`、`aisep:Deployable`）在实施期补齐，不在本阶段虚构。
- 本阶段不使用 `arch:Refines`（路线图元素都在 am4 一个记法里）。

## 9. 待决问题与假设
<列出尚未确认的点，以及“我假设了 X”。>

## 10. 出口条件（关口评审）
- [ ] 目标态的每个应用组件、节点至少被一个交付物实现，并属于某个平台期
- [ ] 工作包之间的 `am4:Triggering` 无环、无孤立工作包
- [ ] `$PY tools/aisep.py gate models/<slug>/*.ttl` 为 PASS，L4 发现项逐条处置
- [ ] 已按 `docs/adm/governance/` 完成“架构决策”关口评审并写入批准记录（`aisep:ApprovalRecord`，`aisep:gate aisep:GateArchitecture`，`aisep:approves` 指向平台期与工作包，`aisep:evidence` 为评审时的 commit；经 MCP 时用 `governance.record_approval`）；不手写 `arch:approvalState`
