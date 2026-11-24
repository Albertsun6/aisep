# 需求：关口页批准或驳回发布，批准的发布打 release 标签

> 按 `docs/adm/requirements/template.md` 填写。模型是唯一事实来源：需求与验收标准的正文以 `am4.ttl`、`verification.ttl` 为准，这里只记叙述、访谈结论和 IRI。
> 前缀 `:` = `https://aisep.example/model/workbench/`。

## 0. 基本信息

- 模型：`https://aisep.example/model/workbench/`
- 需求范围：对 aisep main 最新提交做发布批准或驳回，以及批准后打 release 标签
- 业务负责人：`:projectLead`（项目负责人，Albert）。它是 `arch:Stakeholder`，连不到驱动因素，原因同 `requirements-approver-scope.md` 第 8 节（aisep #83）。
- 关联阶段：需求管理；业务架构（流程细化在后续设计 PR）

## 1. 访谈记录（2026-11-25）

- 使用者：在工作台关口页做批准的人，目前只有项目负责人；批准人规则同其他关口（只列被批模型的人类干系人）。→ `:approverRole`（复用）
- 目的：发布关口的规则已写进接口规范 §5.9 和合并校验，但从没走过一次：仓库里没有发布批准记录，也没有 release 标签；工作台关口页不提供发布关口。→ `:drvReleaseNeverExercised`、`:goalIdentifiableRelease`、`:outReleaseTagged`
- 主流程：会话从 main 最新提交 R 拉出发布批准分支 → 首页关口区列出它 → 关口页只提供发布关口，批准对象是整个被批模型 → Albert 批准或驳回 → 结论是批准时，会话打 `release/{yyyymmdd}-{R 前 7 位}` 标签 → 会话推送分支与标签、开批准专用 PR，按 AGENTS.md 三步合并。→ `:gateApprovalFlow`（复用已有流程）
- 分工：工作台前端只调 MCP，不做 git 写操作。拉分支、打标签、推送、开 PR 由会话做；这一点和规范 §5.9 第 5 步「由工作台做」不同，在设计 PR 的 ADR 里记录。
- 边界条件：只能发布 main 最新提交；标签只用日期加短提交号；同名标签已指向 R 时复用。
- 异常情况：分支准备好后 main 又前进了 → 不能批，提示重新准备分支；gate 不通过 → 只能驳回；同名标签指向别的提交 → 停下由人处理，不移动标签。
- 发布前提：元素是「待批准」（Proposed）也允许发布，照现行规则，服务端不要求先过前面的关口。
- 不做什么：版本号标签；批准 PR 关闭未合并时自动删标签；发布后自动部署；给 workbench 仓库打标签；发布关口页显示自上次发布以来的改动。五条都写成 Won't 需求。
- 尚未回答的问题：无。

## 2. 业务语言复述 + 业务流程

- 复述：Albert 在工作台关口页，对 aisep main 的最新提交做「发布」批准或驳回。会话先从该提交拉好发布批准分支 `approval/release-{短号}-{时间}`；关口页认出这类分支后只提供「发布」关口，批准人仍只列被批模型的人类干系人，gate 不通过只能驳回。只有记录是「批准」时，会话才打 `release/{日期}-{短号}` 标签，再推送、开批准专用 PR，三步合并；驳回只合记录，不打标签。
- 流程：BPMN 细化在后续设计 PR。
- 用户确认：2026-11-25，Albert。

## 3. 本阶段产出的模型元素

| 内容 | IRI | 优先级 |
|---|---|---|
| 驱动因素 | `:drvReleaseNeverExercised` | |
| 目标 | `:goalIdentifiableRelease` | |
| 成果 | `:outReleaseTagged` | |
| 需求 | `:reqApproveRelease`、`:reqTagOnlyApprovedRelease` | Must |
| 需求 | `:reqRejectRelease` | Should |
| 需求（不做） | `:reqReleaseVersionTag`、`:reqAutoDeleteReleaseTag`、`:reqDeployOnRelease`、`:reqTagWorkbenchRepo`、`:reqReleaseChangeSummary` | Won't |
| 验收标准 | `:acReleaseBranchListed`、`:acReleaseOnlyReleaseGate`、`:acReleaseStaleBlocks`、`:acReleaseGateFailRejectOnly`、`:acReleaseApproveRecorded`、`:acTagOnApprovedRelease`、`:acNoTagOnRejectedRelease`、`:acReleaseTagReused`、`:acReleaseTagConflictStops` | Must |
| 验收标准 | `:acRejectReleaseRecorded` | Should |

全部经 aisep 写工具（`model_add_element`、`model_add_relationship`）写入。

## 4. 必需的追溯

- 驱动因素 Influence 目标；成果 Realization 目标；三条需求 Realization 成果。
- `:gateApprovalFlow` Realization 三条需求；`:approverRole` Assignment `:gateApprovalFlow` 已有。
- 需求 Aggregation 各自的验收标准。
- 缺：干系人 Association 驱动因素，原因同上（aisep #83）。

## 6. 出口条件

- 第 1 节没有未回答的问题，第 2 节已有用户确认。
- 每条 Must 需求都聚合了验收标准，验收标准都是一条 Given/When/Then。
- 全仓库 gate 结果为 PASS（见第 7 节）。
- 需求确认关口：照前段链路的做法，是否批准由 Albert 在合入前决定。

## 7. 关口评审输入

- gate 摘要行（全仓库）：`SUMMARY gate files=17 violations=0 warnings=12 infos=8 ... result=PASS`。
- 遗留 Warning 共 12 条：
  - 11 条是 Must 追溯缺口：两条 Must 需求和它们的 9 条验收标准还没有测试用例。工作台代码合入后补成 `aisep:TestCase` 并连 `aisep:Verification`，代码合并关口前清零。
  - 1 条是采购模型原有的 Warning，与本需求无关。
- Info：5 条新的 Won't 需求是孤立元素，按设计不连（另 3 条是前段链路的 Won't）。
- 批准范围（若过需求确认关口）：第 3 节的全部元素。限定关系不能被批准（规范 §6.6）。
