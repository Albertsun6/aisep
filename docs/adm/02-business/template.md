# 阶段 02 · 业务架构 —— 交付物模板

> 用法：复制本文件到 `models/<slug>/business.md`，按占位符填写。文档只引用模型元素的 IRI，
> 不另存事实（原则一）。对应总纲 §3"业务架构：业务能力地图、价值流"；规范见 `docs/metamodel-spec.md`。

## 本阶段产出的模型元素

**ArchiMate 4.0（枢纽）**，文件 `models/<slug>/am4.ttl`：

| 概念 | 类（已在 vendor 本体核实） | 说明 |
|---|---|---|
| 业务能力 | `am4:Capability` | 能力地图节点；层级用 `am4:Composition` |
| 价值流 / 阶段 | `am4:ValueStream` | 阶段也是 ValueStream，阶段间用 `am4:Triggering` / `am4:Flow` |
| 业务参与者 | `am4:BusinessActor` | 具体的人、部门、外部组织 |
| 角色 | `am4:Role` | 承担行为的职责；参与者到角色用 `am4:Assignment` |
| 业务流程 | `am4:Process` | 枢纽层流程（ArchiMate 4.0 不再区分 BusinessProcess） |
| 业务服务 | `am4:Service` | 对外提供的业务行为 |
| 业务对象 | `am4:BusinessObject` | 流程访问的业务信息，`am4:Access` |
| 协作（可选） | `am4:Collaboration` | 多个角色/参与者的临时组合 |

**BPMN**（`inheritsHubRules=false`，level=design），文件 `models/<slug>/bpmn.ttl`：

| 概念 | 类 |
|---|---|
| 流程 | `bpmn:Process`（`bpmn:flowElements` 列出成员） |
| 泳道 | `bpmn:LaneSet`、`bpmn:Lane`（`bpmn:laneSets`、`bpmn:lanes`、`bpmn:flowNodeRefs`） |
| 跨组织协作（可选） | `bpmn:Collaboration`、`bpmn:Participant`、`bpmn:MessageFlow` |
| 事件 | `bpmn:StartEvent`、`bpmn:EndEvent` |
| 任务 | `bpmn:UserTask`、`bpmn:ServiceTask`、`bpmn:ManualTask`（或 `bpmn:Task`） |
| 网关 | `bpmn:ExclusiveGateway`、`bpmn:ParallelGateway` |
| 顺序流 | `bpmn:SequenceFlow`（限定关系，两端都必须是 BPMN 节点） |

"业务域风味"由分派链推导，只用于查询和视图，不进校验（规范 §6.1）。
可选视图：`arch:Diagram` + `arch:viewConformsToViewpoint` 取 `am4vp:CapabilityMapViewpoint`、`am4vp:ValueStreamViewpoint`、
`am4vp:OrganizationViewpoint` 或 `am4vp:StrategyViewpoint`。
写法规则见 `docs/module-contract.md`「Authoring profile」。完整例子：`models/procurement/am4.ttl`（角色、流程、
业务对象、Assignment/Access/Triggering）与 `models/procurement/bpmn.ttl`（BPMN 流程及其 refines）。

## 1. 业务能力地图
| 能力（IRI） | 上级能力 | 实现的愿景需求（IRI） | 现状评价（强/弱/缺失） |
|---|---|---|---|

<!-- 能力只回答"做什么"，不回答"怎么做/谁做"；名称用名词短语，2–3 层为宜。 -->

## 2. 价值流
| 价值流（IRI） | 阶段（IRI，按顺序） | 触发者 / 价值接收者 | 各阶段使用的能力 |
|---|---|---|---|

## 3. 组织：参与者与角色
| 参与者（IRI） | 承担的角色（IRI） | 内部/外部 |
|---|---|---|

## 4. 业务流程
| am4 流程（IRI） | 实现的能力 | 执行角色 | 访问的业务对象 | BPMN 细化（IRI） |
|---|---|---|---|---|

<!-- 每个关键流程画一张 BPMN：至少包含开始/结束事件、任务、网关的异常分支。
     异常与边界情况（超时、驳回、金额阈值……）必须出现在 BPMN 上，而不是只写在文字里。 -->

## 5. 业务服务与业务对象
<!-- 列出对外服务、流程读写的业务对象；业务对象是数据架构阶段的输入。 -->

## 6. 待决问题与风险

## 追溯要求
只使用规范 §7.1 的三类连接：
1. **枢纽关系（am4）**：
   - 向上连愿景：能力、流程经 `am4:Realization` 连到 `am4:Requirement`（参考 `:rel-quoteApproval-realizes-reqTwoLevelApproval`），需求再实现成果、目标；不要直接画 能力 → 目标 / 成果（ArchiMate 4.0 表中只能派生，L2 报 Warning）。
   - 阶段内：能力层级 `am4:Composition`；流程实现能力 `am4:Realization`；角色执行流程 `am4:Assignment`；流程访问对象 `am4:Access`。
   - 关系是否合法以 L2 枢纽矩阵为准；BPMN 节点不能出现在 am4 关系的任一端（L1/L2 报错）。
2. **`arch:Refines`（设计→枢纽）**：每个 `bpmn:Process` 恰好 refines 一个 `am4:Process`（参考 `:rel-bpmnQuoteApproval-refines-quoteApproval`）；
   需要时 `bpmn:Lane` refines 对应的 `am4:Role`。一个节点对 am4 最多 refines 一个目标；BPMN 内部不用 refines。
3. **追溯关系**：被测试验证或被代码实现的 BPMN 节点，必须经 refines 链到达枢纽节点，否则 L4 报追溯缺口。

向下游：数据架构阶段的 DDD 元素通过 am4 关系承接 `am4:BusinessObject` 与 `am4:Capability`（参考 `models/procurement/ddd.ttl`）。

## 入口条件
- 阶段 01 架构愿景已通过关口，`models/<slug>/governance.ttl` 中有对应的 `aisep:ApprovalRecord`，`aisep:decision aisep:DecisionApproved`。

## 出口条件
- 第 1–5 节填完，表中 IRI 都在 `am4.ttl` / `bpmn.ttl` 中存在。
- 每个能力至少经 `am4:Realization` 连到一个愿景需求；每个关键 `am4:Process` 有执行角色，并有 BPMN 细化。
- `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')` 为 PASS（只认 gate）。
- **关口评审**：按 `docs/adm/governance/` 的流程评审，产出一条 `aisep:ApprovalRecord`（`aisep:gate aisep:GateArchitecture`，见 governance 模板第 0 节的阶段—关口对照），
  `aisep:approves` 指向能力地图与关键流程，`aisep:evidence` 为评审时的 commit，写在 `models/<slug>/governance.ttl`。
