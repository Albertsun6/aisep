# 需求：关口页批准人只能选被批模型的干系人

> 按 `docs/adm/requirements/template.md` 填写。模型是唯一事实来源：需求与验收标准的正文以 `am4.ttl`、`verification.ttl` 为准，这里只记叙述、访谈结论和 IRI。
> 前缀 `:` = `https://aisep.example/model/workbench/`。

## 0. 基本信息

- 模型：`https://aisep.example/model/workbench/`
- 需求范围：工作台关口页上批准人的可选范围
- 业务负责人：`:projectLead`（项目负责人，Albert）。它是 `arch:Stakeholder`，不是模板要求的 `am4:Stakeholder`，见第 8 节。
- 关联阶段：需求管理；业务架构（流程细化在 aisep #82）

## 1. 访谈记录（2026-11-24）

- 使用者：在工作台关口页做批准的人，目前只有项目负责人；AI 代理不能当批准人。→ `:approverRole`
- 目的：aisep #68 的批准人误选成采购模型的首席架构师，只看工作台模型时这条批准不算数（aisep #73）。→ `:drvCrossModelApprover`、`:goalApproverInModel`、`:outApproverInModel`
- 主流程：打开关口页 → 选被批模型 → 只列该模型的人类干系人 → 选关口、勾元素 → 批准或驳回。→ `:gateApprovalFlow`（复用已有流程）
- 边界条件：被批模型恰好一个人类干系人时自动选上（Should），包括从别的模型切换过来；两个及以上时不预选。
- 异常情况：没有人类干系人时提示没有可选的批准人，不能批；干系人列表读不到时不显示下拉，不能批；切换被批模型后，之前为别的模型选的批准人不再生效。三条都照现状。
- 不做什么：服务端强制批准人属于被批模型（留给 aisep #73）；补批 #68 那条跨模型记录；按关口分配批准人。三条都写成 Won't 需求。
- 尚未回答的问题：无。

## 2. 业务语言复述 + 业务流程

- 复述：在工作台关口页批准时，批准人只能从被批模型自己的人类干系人里选，别的模型的干系人和 AI 代理都不出现。只有一个干系人时自动选上；有多个时不预选；一个都没有或列表读不到时不能批；切换模型后不沿用之前的选择，按新模型处理。
- 流程：BPMN 细化见 aisep #82（`:bpmnApproverSelection`，经 `arch:Refines` 指向 `:gateApprovalFlow`）。
- 用户确认：2026-11-24，Albert。

## 3. 本阶段产出的模型元素

| 内容 | IRI | 优先级 |
|---|---|---|
| 驱动因素 | `:drvCrossModelApprover` | |
| 目标 | `:goalApproverInModel` | |
| 成果 | `:outApproverInModel` | |
| 角色 | `:approverRole` | |
| 需求 | `:reqApproverFromModel` | Must |
| 需求 | `:reqSingleApproverPreselect` | Should |
| 需求（不做） | `:reqServerEnforcesApproverModel`、`:reqBackfillCrossModelApproval`、`:reqApproverPerGate` | Won't |
| 验收标准 | `:acOnlyModelStakeholders`、`:acNoApproversBlocks`、`:acApproversUnreadable`、`:acSwitchModelClears` | Must |
| 验收标准 | `:acSingleApproverPreselected`、`:acSingleApproverAfterSwitch`、`:acMultipleNotPreselected` | Should |

全部经 aisep 写工具（`model_add_element`、`model_add_relationship`、`model_set_labels`、`model_remove`）写入。

## 4. 必需的追溯

- 驱动因素 Influence 目标；成果 Realization 目标；两条需求 Realization 成果。
- `:gateApprovalFlow` Realization 两条需求；`:approverRole` Assignment `:gateApprovalFlow`。
- 需求 Aggregation 各自的验收标准。
- 缺：干系人 Association 驱动因素，写不进去，见第 8 节。
- 未建：BusinessActor → Role 的 Assignment（模板里是可选项）。

## 6. 出口条件

- 第 1 节没有未回答的问题，第 2 节已有用户确认。
- 每条 Must 需求都聚合了验收标准，验收标准都是一条 Given/When/Then。
- 全仓库 gate 结果为 PASS（见第 7 节）。只对 `models/workbench` 跑 gate 是 FAIL，2 条违规都来自 #68 的跨模型批准记录（EG13），本需求之前就有。由于不补批（`:reqBackfillCrossModelApproval`）、批准记录又不能改，这一项在 aisep #73 有结论前一直达不到。
- 需求确认关口：没有批准。Albert 2026-11-24 决定这次不批，直接合入，元素保持「待批准」（Proposed）。

## 7. 关口评审输入

- gate 摘要行（全仓库）：`SUMMARY gate files=16 violations=0 warnings=6 infos=3 ... result=PASS`。
- 遗留 Warning 共 6 条：
  - 5 条是 Must 追溯缺口：`:reqApproverFromModel` 与它的 4 条验收标准还没有测试用例。工作台代码合入后补成 `aisep:TestCase` 并连 `aisep:Verification`，代码合并关口前清零。
  - 1 条是采购模型原有的 Warning，与本需求无关。
- Info：3 条 Won't 需求是孤立元素，按设计不连。
- 批准范围（若以后过需求确认关口）：第 3 节的全部元素。限定关系不能被批准（规范 §6.6）。

## 8. 发现：干系人到驱动因素的连接写不进去

模板第 4 节要求 Stakeholder Association Driver。工作台的批准人 `:projectLead` 是 `arch:Stakeholder`，不是 `am4:Stakeholder`，写工具按 ArchiMate 4.0 关系表拒绝（L2，`am4rt:permitsAssociation`）。为这条连接再建一个 `am4:Stakeholder`，同一个人就有两份，违反原则一，所以这次不连。跟踪在 aisep #83。
