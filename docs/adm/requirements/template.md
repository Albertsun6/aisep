# 需求管理：阶段交付物模板

> 需求管理是贯穿所有 ADM 阶段的中枢（总纲 §3、§4）。本模板每次针对一个需求范围填写一份，复制到 `models/<slug>/requirements-<范围 slug>.md`。
> **模型是唯一事实来源**（原则一）：本文档只写叙述、访谈结论和元素 IRI 清单；需求、验收标准的正式文本以模型为准，不在文档里另存一份。
> 填写说明用 `<…>` 标出，填完删除。范例：`models/procurement/am4.ttl`（`:reqTwoLevelApproval`）、`models/procurement/verification.ttl`、`models/procurement/bpmn.ttl`。

## 0. 基本信息

- 模型：`https://aisep.example/model/<slug>/`
- 需求范围：<一句话：这次讨论的是哪块业务>
- 业务负责人（`am4:Stakeholder`）：<IRI>
- 关联阶段：<架构愿景 / 业务架构 / 数据架构 / 应用架构 / 技术架构 / 路线图 中的哪些>

## 1. 访谈记录（AI 追问的结论）

<按"问 → 答 → 结论"记录。每条结论要么落成下面某个模型元素，要么写明"不进模型"的理由。>

- 使用者：<谁在用、以什么角色>
- 边界条件：<数量、金额、时间等临界值；越界时怎样>
- 异常情况：<失败、超时、撤回、并发、数据缺失时怎样>
- 不做什么：<明确排除的范围，逐条列出>
- 尚未回答的问题：<列出；有未回答问题不能进入关口评审>

## 2. 业务语言复述 + 业务流程

- 复述：<AI 用业务语言写一段，用户确认"就是这个意思"后才继续>
- 流程：<BPMN 流程的 IRI；图由模型渲染，不贴截图>
- 用户确认：<日期 + 确认人>

## 3. 本阶段产出的模型元素

| 内容 | 类 | 记法 | 文件 |
|---|---|---|---|
| 干系人 | `am4:Stakeholder` | am4 | `models/<slug>/am4.ttl` |
| 驱动因素 | `am4:Driver` | am4 | 同上 |
| 目标 / 成果 | `am4:Goal` / `am4:Outcome` | am4 | 同上 |
| 需求（含"不做什么"） | `am4:Requirement`，带 `aisep:priority` | am4 | 同上 |
| 验收标准 | `aisep:AcceptanceCriterion`，带 `aisep:priority`，可选 `aisep:gherkin` | am4（Extension 类，⊑ `am4:Requirement`） | `models/<slug>/verification.ttl` |
| 使用者 | `am4:BusinessActor` / `am4:Role` | am4 | `models/<slug>/am4.ttl` |
| 业务流程（枢纽） | `am4:Process` | am4 | 同上 |
| 业务流程（细化） | `bpmn:Process` 及其 `bpmn:UserTask`、`bpmn:ExclusiveGateway`、`bpmn:StartEvent`、`bpmn:EndEvent`、`bpmn:SequenceFlow` | bpmn | `models/<slug>/bpmn.ttl` |

规则提要（细则见 `docs/metamodel-spec.md` §4、§6.5）：
- 每个元素恰好一个类型、一个 `arch:inModel`、一个 `skos:prefLabel …@zh`。
- 优先级取 `aisep:Must` / `aisep:Should` / `aisep:Could` / `aisep:Wont`；"不做什么"写成 `aisep:Wont` 级的 `am4:Requirement`。
- 只有 Must 级的需求或验收标准才要求有测试用例（L4 追溯缺口）。
- `arch:approvalState` 不手填，由关口批准记录推导。

## 4. 必需的追溯（只用规范 §7.1 的三类连接）

| 连接 | 种类 | 方向 |
|---|---|---|
| 干系人 — 驱动因素 | 枢纽关系 `am4:Association` | Stakeholder → Driver |
| 驱动因素 — 目标 | 枢纽关系 `am4:Influence` | Driver → Goal |
| 成果 — 目标；需求 — 成果 | 枢纽关系 `am4:Realization` | Outcome → Goal；Requirement → Outcome |
| 需求 — 验收标准 | 枢纽关系 `am4:Aggregation` | Requirement → AcceptanceCriterion |
| 业务流程 — 需求 | 枢纽关系 `am4:Realization` | Process → Requirement |
| 使用者 — 流程 | 枢纽关系 `am4:Assignment` | Role → Process（BusinessActor → Role） |
| BPMN 流程 — am4 流程 | `arch:Refines`（design → hub） | `bpmn:Process` → `am4:Process` |
| 测试用例 — 验收标准 | 追溯关系 `aisep:Verification`（测试阶段补） | `aisep:TestCase` → `aisep:AcceptanceCriterion` |

- 后续阶段中由枢纽规则判定的元素（am4、DDD）通过 `am4:Realization` 连到需求，BPMN / UML 节点经 `arch:Refines` 连到这些元素；代码通过 `aisep:Implementation` 连到设计元素，不直接连需求。
- BPMN 任务、泳道不做 am4 子类对齐（D4）；被测试验证或被代码实现的 BPMN 节点必须经 `arch:Refines` 到达 am4 / DDD 节点，否则 L4 报追溯缺口；`bpmn:Lane` 可 refines 对应的 `am4:Role`。
- 关系是否合法由 L2 矩阵判定，以 `gate` 结论为准。

## 5. 入口条件

- 有明确的需求范围和业务负责人。
- 上游已批准的原则、目标（如有）可在模型中查到。

## 6. 出口条件

- 第 1 节"尚未回答的问题"为空；第 2 节已有用户确认。
- 每条 Must 需求至少聚合一条验收标准，验收标准可直接写成测试（Given/When/Then）。
- `$PY tools/aisep.py gate models/<slug>/*.ttl` 结果为 PASS。此时 Must 级的"追溯缺口"Warning 允许存在（测试用例尚未编写），在本文档第 7 节列出；到"代码合并"关口前必须清零。
- 通过**需求确认**关口评审（`docs/adm/governance/template.md`），产出一条 `aisep:gate aisep:GateRequirements` 的批准记录。

## 7. 关口评审输入

- gate 摘要行：<粘贴 SUMMARY 行>
- 遗留 Warning 及处理计划：<逐条>
- 本次批准范围（`aisep:approves` 目标）：<需求 IRI 列表>
