# 阶段 01 · 架构愿景 —— 交付物模板

> 用法：复制本文件到 `models/<slug>/vision.md`，按占位符填写。正文只写结论和理由；
> 所有可被追溯的事实（干系人、驱动力、目标……）必须同时落成模型元素，本文档只引用它们的 IRI，不另存一份（原则一）。
> 对应总纲 §3"架构愿景"、§4 需求阶段方法；规范见 `docs/metamodel-spec.md`。

## 本阶段产出的模型元素

记法：**ArchiMate 4.0（am4，枢纽）**，文件 `models/<slug>/am4.ttl`；模型 IRI `https://aisep.example/model/<slug>/`。

| 概念 | 类（已在 vendor 本体核实） | 说明 |
|---|---|---|
| 干系人 | `am4:Stakeholder` | 关注本系统的人/团队/组织 |
| 驱动力 | `am4:Driver` | 促使变化的内外部因素 |
| 评估 | `am4:Assessment` | 对驱动力的分析结论（问题/机会） |
| 目标 | `am4:Goal` | 高层意图 |
| 成果 | `am4:Outcome` | 可度量的最终结果 |
| 本项目特有原则 | `am4:Principle` | 只放 `docs/principles.md` 之外新增的原则 |
| 需求 | `am4:Requirement` | 可带 `aisep:priority`（`aisep:Must` 等）；ArchiMate 4.0 无独立 Constraint 类，约束也用 Requirement |
| 范围（可选） | `am4:Grouping` | 把"范围内"元素归组；不需要就不建 |

元素关系只用 am4 限定关系资源，例如 `am4:Association`（干系人—驱动力）、`am4:Influence`（评估→目标）、
`am4:Realization`（成果→目标、需求→成果）、`am4:Aggregation`。**合法性以 L2 枢纽矩阵为准**：gate 拒绝就改模型或提问，不绕过。

可选视图：`arch:Diagram`，`arch:viewConformsToViewpoint` 取 `am4vp:StakeholderViewpoint`、`am4vp:GoalRealizationViewpoint`
或 `am4vp:MotivationViewpoint`；成员用 `arch:inView`。

写法规则（每个元素恰好一个类型、恰好一个 `@zh` 的 `skos:prefLabel`、`arch:inModel`；只写限定关系；不手填
`arch:approvalState`）见 `docs/module-contract.md`「Authoring profile」。

## 1. 背景与问题陈述
<!-- 用业务语言写 3–5 句：现在怎么做、痛在哪里、为什么是现在。每个痛点对应一个 am4:Driver / am4:Assessment。 -->

## 2. 干系人
| 干系人（IRI） | 关注点 | 影响力/参与方式 |
|---|---|---|
| `:<slug>` | <!-- 关注什么 --> | <!-- 决策/使用/受影响 --> |

<!-- 关口批准人（aisep:approvedBy 的对象）按 models/procurement/governance.ttl 的写法另建 arch:Stakeholder，放 governance.ttl。 -->

## 3. 驱动力与评估
| 驱动力（IRI） | 评估（IRI） | 证据/数据来源 |
|---|---|---|

## 4. 目标与成果
| 目标（IRI） | 成果（IRI） | 度量方式与目标值 |
|---|---|---|

<!-- 成果必须可度量；说不出怎么量的，写进第 8 节"待决问题"。 -->

## 5. 范围
- 范围内：<!-- 业务领域、组织单元、流程边界 -->
- **范围外（不做什么）**：<!-- 必填，至少一条；每条落成 `aisep:priority aisep:Wont` 的 am4:Requirement -->
- 假设与约束：<!-- 每条约束落成 am4:Requirement -->

## 6. 架构原则引用
- 适用 `docs/principles.md` 原则一至五（按编号引用，不复制原文）。
- 本项目新增原则：<!-- 列 am4:Principle 的 IRI 与一句理由；没有就写"无" -->

## 7. 高层需求
| 需求（IRI） | 一句话陈述 | 优先级（Must/Should/Could/Wont） | 来源目标/成果 |
|---|---|---|---|

<!-- Must 级需求到需求管理/测试阶段必须有 aisep:AcceptanceCriterion + aisep:TestCase，否则 L4 报追溯缺口。
     参考例子：models/procurement/am4.ttl 的 :reqTwoLevelApproval，models/procurement/verification.ttl。 -->

## 8. 待决问题与风险
<!-- AI 追问中用户没有答案的点；每条写负责人和期限。 -->

## 追溯要求（向后续阶段）
只使用规范 §7.1 的三类连接：
1. **枢纽关系**：业务架构阶段的 `am4:Capability` / `am4:ValueStream` / `am4:Process` 通过 am4 关系（如 `am4:Realization`）连到本阶段的需求，需求再实现成果、目标；能力不直接连目标、成果（只能派生，L2 报 Warning）。
2. **`arch:Refines`**：本阶段元素全部在枢纽层，不作为 refines 的源；下游 BPMN/DDD/UML 节点 refines 到 am4 节点。
3. **追溯关系**：`aisep:Verification`（测试→需求/验收标准）、`aisep:approves`（批准记录→元素）、`ad:RelatedConcept`（ADR→元素，限定关系资源；直连的 `ad:relatedConcept` 由 build 生成，不手写）。

## 入口条件
- 已有项目 slug 和模型目录 `models/<slug>/`（含 `arch:Model` 声明，参考 `models/procurement/am4.ttl` 开头）。
- 已指定发起人和至少一名关口批准人。

## 出口条件
- 第 2–7 节填完，每张表的 IRI 都在 `models/<slug>/am4.ttl` 中存在。
- 每个目标至少有一个成果或需求关联；范围外至少一条；第 8 节无阻断项。
- `tools/aisep.py gate models/<slug>/*.ttl` 结果为 PASS（只认 gate）。
- **关口评审**：按 `docs/adm/governance` 的流程评审，产出一条 `aisep:ApprovalRecord`（`aisep:gate aisep:GateRequirements`，见 governance 模板第 0 节的阶段—关口对照），`aisep:approves` 指向本阶段的目标与需求，`aisep:evidence` 为评审时的 commit。批准记录写在 `models/<slug>/governance.ttl`，参考 `models/procurement/governance.ttl`。
