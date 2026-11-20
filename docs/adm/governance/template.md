# 治理：关口评审模板

> 实施治理和变更管理不设单独阶段，融入 SDLC 的五个评审关口和 Git 版本管理（总纲 §3，原则五）。
> 每个 ADM 阶段的出口都是一次关口评审；评审的唯一产物是一条**批准记录**（`aisep:ApprovalRecord`，ADR-009），存放在模型仓库里。
> 填写说明用 `<…>` 标出，填完删除。范例：`models/procurement/governance.ttl`（`:approval-20261119-arch-baseline`）。

## 0. 基本信息

- 模型：`https://aisep.example/model/<slug>/`
- 关口（`aisep:gate`，五选一）：
  - `aisep:GateRequirements`（需求确认）
  - `aisep:GateArchitecture`（架构决策）
  - `aisep:GateDesign`（设计评审）
  - `aisep:GateMerge`（代码合并）
  - `aisep:GateRelease`（发布上线）
- 评审对象（`aisep:approves` 的目标）：<元素、模型或 ADR 的 IRI 列表>
- 待批准的版本：<分支名 + headCommit（40 位十六进制）>
- 批准人（`aisep:approvedBy`）：<人的 IRI，必须是 `arch:Stakeholder` 的实例，且不能是 `aisep:AIAgent`；AI 不能批准>

阶段—关口对照：

| 阶段 | 关口 |
|---|---|
| 01 架构愿景、需求管理 | `aisep:GateRequirements` |
| 02 业务架构、03 数据架构、04 应用 + 技术架构、05 路线图 | `aisep:GateArchitecture` |
| 设计 | `aisep:GateDesign` |
| 代码 | `aisep:GateMerge` |
| 发布 | `aisep:GateRelease` |

## 1. 自动检查结果（必须全部附上，不靠口述）

- `gate`：`$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')` 的 SUMMARY 行：<粘贴>。result 必须为 PASS。
- 模型差异：`model.diff`（base = 与主分支的分叉点，head = 待批准版本）列出的新增 / 修改 / 删除：<粘贴或附链接>。MCP 不可用时用 `git diff <base>..<head> -- models/<slug>/` 代替。
- 影响分析：对每个被修改或删除的元素跑 `$PY tools/aisep.py impact <IRI> --mode depends`，列出受影响元素：<粘贴>。
- L4 遗留 Warning：<逐条列出，并写处理计划>

## 2. 通用检查清单

- [ ] gate 为 PASS，且检查的正是待批准的 headCommit。
- [ ] 模型差异与本次任务范围一致，没有夹带无关改动。
- [ ] 每个新增元素都能追溯到需求（原则三）；跨记法连接只用规范 §7.1 的三类：枢纽关系、`arch:Refines`、追溯关系（`aisep:Verification`、`aisep:Implementation`、`aisep:approves`、`ad:RelatedConcept`）。
- [ ] 没有新建与已有元素同义的元素（原则一）；需要合并的已标 `owl:deprecated` 并加 `dcterms:isReplacedBy`。
- [ ] 影响分析列出的下游元素已逐个确认：要么一并修改，要么说明不受影响。
- [ ] AI 已汇报它做了什么、为什么（原则五）。

## 3. 各关口专项检查

| 关口 | 专项检查 |
|---|---|
| 需求确认 | 按 `docs/adm/requirements/template.md` 第 6 节；访谈无未答问题；每条 Must 需求有 `aisep:AcceptanceCriterion`；Must 级追溯缺口允许存在但已列出 |
| 架构决策 | 每个重要取舍有一条 `ad:Decision`，用 `ad:RelatedConcept` 连到受影响元素；与 `docs/principles.md` 无冲突 |
| 设计评审 | 被测试验证或被代码实现的 BPMN / UML 节点都有 `arch:Refines` 链到达枢纽规则判定的节点（am4 或 DDD），同一更高记法最多一个主锚；DDD 元素经 am4 关系（如 `am4:Realization`）追溯到需求 |
| 代码合并 | 改动的代码有 `aisep:CodeLocation` + `aisep:Implementation` 指向设计元素；Must 级追溯缺口为零（每条 Must 验收标准都有 `aisep:TestCase` + `aisep:Verification`） |
| 发布上线 | 每个 Must 验收标准的测试用例最近一条 `aisep:TestResult` 的 `aisep:verdict` 为 `aisep:VerdictPassed`；发布包有 `aisep:Deployable`（带 `aisep:packageUrl`） |

## 4. 结论与批准记录

- 结论（`aisep:decision`）：`aisep:DecisionApproved` / `aisep:DecisionRejected`
- 否决理由或附加条件：<写清楚；否决时列出需要返工的项>
- 每条批准记录新建一个文件 `models/<slug>/governance/<记录本地名>.ttl`（记录本地名即 IRI 去掉 `{model}` 前缀的部分；`governance.ttl` 里的是存量记录，不再往里追加），字段（规范 §6.6）：

| 字段 | 取值 |
|---|---|
| IRI | `{model}approval-{yyyymmddHHMMSS}-{slug}`（UTC，规范 §3） |
| 类型 | `aisep:ApprovalRecord`，带 `arch:inModel` 和一个 `@zh` 名称 |
| `aisep:gate` | 第 0 节选定的关口 |
| `aisep:decision` | 上面的结论 |
| `aisep:approvedBy` | 批准人 IRI |
| `aisep:approves` | 评审对象 IRI（一个或多个） |
| `aisep:evidence` | 待批准版本的 40 位 commit，恰好一个。`sha256:<64 位十六进制>` 形式 L1 合法，但合并时校验一律拒绝，只用于不经合并进主分支的场合（规范附录 C） |
| `prov:generatedAtTime` | 批准时间（xsd:dateTime，带时区） |
| `aisep:activity` | 可选：本次针对的 `aisep:AgentActivity`（代理、sessionRef、分支、起止时间、baseCommit、headCommit）；evidence 为 commit 时必须等于其 headCommit |

- 优先通过 `governance.record_approval` 写入（自动填 evidence，可同时写入 `aisep:AgentActivity`）；MCP 不可用时按上表手写，再跑一次 gate；要提交时按 `prompt.md` 第四步的手工提交配方，否则过不了合并时校验。
- **不写 `arch:approvalState`**：构建时由最近一条合法批准记录推导（无记录 = Proposed，被替换 = Superseded）。改结论只能新增一条记录，不修改旧记录。

## 5. 变更管理

- 所有变更走 Git 分支、经 PR 人工批准合入。未经关口批准的模型改动可以进主分支，在主分支上推导为 Proposed，由"待批准关口"列出（ADR-016）。
- 已批准的元素被修改后，旧批准不自动作废：CI 要求同一 PR 内有一条新的、结论为 Approved 的合法批准记录覆盖它（关口不限，且须是该对象在合并结果中生效、即时间最晚的那条），否则拒绝合并；评审时对照 `model.diff` 看清改了什么。删除已批准元素一律拒绝，只能退役（ADR-015 U1）。
- 合并或拆分元素：保留一个，其余标 `owl:deprecated true` + `dcterms:isReplacedBy`，追溯链迁移到保留的元素（规范 §7.2）。
- 不存在"进行中"状态的记录（ADR-013）；进行中的工作只体现为分支上的文件差异。
