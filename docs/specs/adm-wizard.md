# AISEP 的 ADM 向导：与 VP 的对照与设计（待确认）

> 状态：2026-11-26 协调会话确认「按建议实现」（第 5 节四个问题都按建议：不提交生成的交付物、形态 B、顺带改各阶段 `prompt.md`、预备阶段不设检查项且差距只在路线图做），已实现。实现与初稿的差别见第 7 节。
> 背景：Albert 2026-11-26 看过 Visual Paradigm（下称 VP）调研后决定自己做 ADM 向导。VP 的 TOGAF 向导只在 Enterprise 版提供，AI 功能要联网并要求项目托管在 VP Online，`.vpp` 是不公开的二进制格式，进不了 Git，所以 VP 只当方法论参考。本文只借鉴结构，不搬原文。

## 1. 参考了什么

| 参考对象 | 借鉴点 | 我们的差别 |
|---|---|---|
| VP 传统向导（教程页，2018，只演示了预备阶段） | 阶段 → 活动 → 步骤三层导航；每个交付物一条泳道，泳道走完就生成一份交付物，并自动归档到 Architecture Repository；每步有说明和样例 | 进度不靠手点「Complete Step」，每次从模型现算；生成的交付物不另存一个仓库，Git 提交就是归档 |
| VP AI 向导（2026-01 发布说明，覆盖预备到 F） | 一句话描述问题，AI 生成 ArchiMate 图、基线与目标模型、差距分析、WBS、过渡架构、迁移时间线；前一步的产出带到后一步 | AI 不一次性生成模型，先当追问者（`docs/methodology.md` §4）；模型由代理经 MCP 写工具逐条写入，gate 把关；不做日历时间线 |
| Linked.Archi 交付物模板（`vendor/meta.linked.archi/ttl/togaf_deliverable-templates.ttl`、`archimate4_deliverable-templates.ttl`，CC-BY-4.0） | 交付物模板 → 有序的节 → 每节一条 SPARQL，查询结果填进该节 | 每节除了「已有什么」的清单查询，再加「缺什么」的缺口查询；查询按 AISEP 自己的类和限定关系写 |
| TOGAF 10 标准（VP 没覆盖的 G、H、需求管理） | G 的合规评审、H 的变更请求与影响评估、需求管理的需求库与影响评估 | 落到已有的批准记录、PR、`model_diff`、`model_impact`，不另建文档 |

## 2. 对照表

「VP」列只写 VP 教程或发布说明里点名的活动和交付物；VP 没覆盖的阶段注明「VP 未覆盖，按 TOGAF 补」。采纳的意思是向导会检查或生成它。

| AISEP 阶段（模板） | VP / TOGAF 的活动或交付物 | 采纳与否 | 理由 |
|---|---|---|---|
| **预备**（`docs/principles.md`，总纲 §3 简化为一份原则文档） | VP：组织影响范围图 + 影响描述表；EA 成熟度评估雷达图与成熟度差距；治理结构图；（AI 版）高层项目计划 | 原则：采纳（已有）；其余不采纳 | 单人超级个体模式，没有多组织影响和组织成熟度问题；治理结构已由 `AGENTS.md`、批准记录和关口定义；计划不写日历工期。向导不为预备阶段设检查项，原则只查 `am4:Principle` 是否只放新增原则（愿景阶段一并查） |
| **01 架构愿景**（`docs/adm/01-vision/`） | VP（AI 版）：方案概念图、业务与 IT 能力雷达图、更新成熟度评估。TOGAF：干系人地图、业务目标与驱动力、范围、架构原则、架构工作说明书 | 干系人、驱动力、评估、目标、成果、范围外、高层需求：采纳；方案概念图：留给出图；能力雷达图、工作说明书：不采纳 | 前一组已是模板第 2–7 节，向导逐节查。方案概念图是视图，归「从模型自动出图」会话。能力现状评价放在业务架构第 1 节的「现状评价」列。没有甲乙方，不需要工作说明书，范围写在第 5 节 |
| **需求管理**（`docs/adm/requirements/`） | VP 未覆盖，按 TOGAF 补：需求库、需求影响评估、架构需求规格说明（ARS） | 需求 + 优先级 + 验收标准 + 追溯：采纳；需求影响评估：采纳，复用 `model_impact`；独立的需求库和 ARS 文档：不采纳 | 模型就是需求库（原则一）；ARS 的内容由向导从模型生成，不另存 |
| **02 业务架构**（`docs/adm/02-business/`） | VP（AI 版）：基线与目标业务架构模型、业务域差距图。TOGAF：组织 / 参与者目录、业务服务 / 功能目录、能力地图、价值流、流程图 | 能力地图、价值流、参与者与角色、流程（am4 + BPMN）、业务服务与业务对象：采纳；每阶段各建基线和目标两套模型、阶段内差距：不采纳 | 前一组是模板第 1–5 节。AISEP 只建目标态，差距统一在路线图阶段做（ArchiMate 4.0 没有 Gap 元素，差距只记在路线图表里）；各阶段各做一次差距会重复 |
| **03 数据架构**（`docs/adm/03-data/`） | VP（AI 版）：基线与目标数据模型、差距图。TOGAF：数据实体 / 组件目录、逻辑数据图、数据生命周期、数据迁移 | 逻辑数据（用 DDD 的子域、上下文、聚合表达）与主数据唯一归属：采纳；物理库表设计、数据生命周期图：不采纳；基线与目标两套：不采纳 | 防烟囱靠「每类数据一个权威聚合」，模板第 5 节；物理设计落到代码层；理由同上 |
| **04 应用 + 技术架构**（`docs/adm/04-app-tech/`，对应 TOGAF C 应用部分与 D） | VP（AI 版）：基线与目标应用、技术模型，技术差距识别。TOGAF：应用组合目录、接口目录、应用通信图、技术组合目录、平台分解图 | 组件对齐上下文、服务与接口、集成、技术基线、非功能需求：采纳；基线与目标两套：不采纳 | 前一组是模板第 2–6 节；理由同上 |
| **05 路线图**（`docs/adm/05-roadmap/`，TOGAF E + F 合并） | VP（AI 版）：工作包 WBS、过渡架构、架构状态、迁移时间线；F 细化路线图。VP 教程列出的产物还有合并差距表、方案与依赖矩阵、实施因素评估矩阵、PERT 图、RACI 表 | 差距表、平台期（即过渡架构）、工作包（即 WBS）、交付物：采纳；迁移时间线、PERT、实施因素评估矩阵、RACI：不采纳 | 前一组是模板第 2–5 节。排期到工作包为止，更细的进 issue；不写日历工期；单人模式不需要 RACI |
| **治理：G 实施治理**（`docs/adm/governance/`） | VP 未覆盖，按 TOGAF 补：架构合规评审、架构合同、实施治理模型 | 合规检查：采纳，用 gate、`mergecheck`、`code-to-tests.rq`；关口评审：MVP 期间暂停（ADR-024 第 6 款），向导只列出、不判定；架构合同：不采纳 | 合规的唯一结论是 gate；PR 加批准记录已经起到合同的作用 |
| **治理：H 变更管理**（`docs/adm/governance/` 第 5 节） | VP 未覆盖，按 TOGAF 补：变更请求、变更影响评估、变更分类（简化、增量、重新架构） | 影响评估：采纳，复用 `model_impact` 与 `model_diff`；变更请求单与变更分类：不采纳 | PR 就是变更请求；改已批准元素须重批，由 `mergecheck` 把关（`docs/methodology.md` §10.8） |
| **向导机制**（跨阶段） | VP：泳道 = 交付物；手点 Complete Step 推进、完成的活动打勾；交付物自动归档到 Architecture Repository；Instruction / View Sample；Perform Action 打开编辑器 | 泳道 = 交付物：采纳；手点进度：不采纳；归档：改为 Git；说明与样例：采纳（已有 `prompt.md` 与 procurement 样例）；Perform Action：改为 MCP 写工具 | ADR-013 不存进行中状态，进度每次从模型算；Git 提交本身就是可复现的归档 |

## 3. 设计

### 3.1 形态：缺口查询 + 一个 `tools/` 命令，不加 MCP 工具

三个候选：

| 形态 | 优点 | 缺点 |
|---|---|---|
| A. 新的 MCP 只读工具 `model_adm_status` | 工作台和代理都能直接调 | 改 MCP 接口契约（`docs/mcp-interface.md`），属于 ADR-021 第 2 款要先问是否跨模型评审的一类；改 `aisep/server.py`、`aisep/tools.py`，后者在负例清单里，要核对 `negatives` |
| B. `tools/aisep.py adm` 命令 + 存成 `.rq` 的查询 | 命令行与 CI 都能跑；查询是数据，可读、可评审；代理经 MCP 时也能把同一条 `.rq` 交给 `model_query` | 代理要用 Bash 调命令才能拿到整份报告 |
| C. 只改 `prompt.md`，让代理自己写查询 | 零代码 | 每次查法不同，结果不可复现，成功标准没法证伪 |

**建议 B。** 以后要接工作台，再在 B 之上加 MCP 工具，查询文件原样复用。

组成：

1. **检查项**：`docs/queries/adm/<阶段>-<序号>-<名>.rq`，一条查询一个检查项。文件头用注释声明元数据，向导按它分组排序（借鉴 Linked.Archi 的「节 + 查询」）：

   ```sparql
   # adm-phase: 02-business
   # section: 1. 业务能力地图
   # kind: gap            （inventory = 已有清单；gap = 缺口，每行一个缺口）
   # title: 能力没有经 am4:Realization 连到需求
   # source: 02-business/template.md 出口条件第 2 条
   PREFIX …
   SELECT ?element ?label WHERE {
     VALUES ?model { <https://aisep.example/model/workbench/> }
     …
   }
   ```

   模型范围写在 `VALUES ?model { … }` 这一行，向导运行时替换成 `--model` 指定的模型；直接交给 `model_query` 时手改这一行即可，和现有 `code-to-capability.rq` 的用法一致。
2. **运行器**：新模块 `aisep/adm.py`（不碰 `aisep/core.py`、`aisep/tools.py`），`tools/aisep.py` 只加一个 `adm` 子命令分派。复用 `core.Ctx` 构建图，查询与 `query` 子命令走同一条路径。
3. **提示词**：各阶段 `prompt.md` 的「先读」加一步「先跑 `tools/aisep.py adm <阶段> --model <slug>`，按缺口清单追问」。这一步改到 `docs/adm/**/prompt.md`，属合并前评审。

命令：

```
$PY tools/aisep.py adm                          # 列出阶段和检查项数
$PY tools/aisep.py adm 02-business --model workbench            # 已有 / 缺口报告
$PY tools/aisep.py adm 02-business --model workbench --deliverable   # 生成交付物 Markdown
```

### 3.2 「已有什么、缺什么」怎么查

- **已有**：每节一条 `inventory` 查询，列出该节涉及的元素（IRI、中文名、类型），类型判断一律 `a/rdfs:subClassOf*`，所以 `ddd:Subdomain` 会算作能力。
- **缺什么**有两种：
  - **整节为空**：`inventory` 返回 0 行，报「本节还没有元素」。
  - **元素级缺口**：`gap` 查询每行一个缺口，来源是模板出口条件和追溯要求，逐条在文件头 `source:` 注明出处。
- **复用 L4**：Must 级追溯缺口、孤立元素已由 gate 的 L4 报出，向导不重写这些查询，而是在报告末尾附上本模型的 L4 发现项，避免两套口径；gate 结论仍以 `tools/aisep.py gate` 为准（报告里注明）。
- **第一批检查项**（实现时按模板逐条落，括号里是出处）：

| 阶段 | inventory（节） | gap |
|---|---|---|
| 01 愿景 | 干系人、驱动力与评估、目标与成果、原则、高层需求 | 目标没有成果或需求实现它（出口第 2 条）；没有任何 Wont 需求（第 5 节「范围外至少一条」）；驱动力没有影响任何目标 |
| 需求管理 | 需求（按优先级）、验收标准 | Must 需求没有聚合验收标准（出口第 2 条）；需求没有 `aisep:priority`；需求没有流程实现它（追溯表） |
| 02 业务 | 能力、价值流、参与者与角色、am4 流程、业务服务与对象 | 能力没有经 Realization 连到需求（出口第 2 条）；am4 流程没有执行角色；am4 流程没有 BPMN 细化（出口第 2 条）；参与者没有承担角色 |
| 03 数据 | 子域、限界上下文、聚合、主数据 | 业务对象没有聚合实现（出口第 1 条）；限界上下文没有实现子域 |
| 04 应用技术 | 应用组件、服务与接口、技术基线 | 限界上下文没有落在恰好一个组件里（出口第 1 条） |
| 05 路线图 | 平台期、工作包、交付物 | 组件或节点没有被交付物实现、不属于任何平台期（出口第 1 条）；Must 需求没有被工作包或交付物实现（追溯第 2 条）；孤立工作包（出口第 2 条） |
| 治理 G/H | 批准记录、架构决策、测试结果 | Must 验收标准最近一条测试结果不是 Passed（发布关口专项）；关口评审一行固定显示「MVP 暂停（ADR-024 第 6 款）」，不判定 |

### 3.3 交付物生成到哪里、什么格式

- 格式：Markdown，节标题沿用该阶段 `template.md` 的节；每节放 inventory 结果表（IRI + 中文名 + 类型）和本节缺口；需人写的叙述节（背景、待决问题）留 `<!-- 人工填写 -->` 占位；文件头写明模型、生成所依据的提交（`git rev-parse HEAD`，工作区有未提交改动时注明）和生成命令。
- 位置：**默认打印到标准输出，不写文件。** 进度和缺口每次从模型现算，不落任何「完成到第几步」的状态（ADR-013）。要留档时，任何提交上重跑同一命令都能得到当时的交付物，Git 即归档。
- 需要落文件时用 `--out <路径>`，向导只写这一个文件、不提交。是否把生成的交付物提交进 `models/<slug>/`，见第 5 节待定问题 1。

### 3.4 与关口评审、gate 的关系

- 向导只读，退出码与缺口多少无关（有缺口也返回 0，只有用法错误或模型无法解析才非 0），不进 gate、不进 CI 必需检查，不改变 gate 结论。
- MVP 期间关口评审暂停（ADR-024 第 6 款），向导不把「已有批准记录」当作进入下一阶段的前提，入口条件里的批准一项只显示、不判定。恢复关口后，可以把向导报告作为 `docs/adm/governance/template.md` 第 1 节「自动检查结果」的附件。
- 向导不写批准记录，也不提示代理去写。

## 4. 入口与出口标准（可证伪断言）

入口：

- I1：本设计经协调会话确认（含第 5 节的取舍）。
- I2：开工时 `gh pr list` 里没有别的 PR 改 `tools/aisep.py`、`aisep/adm.py`、`docs/queries/adm/**`、`docs/adm/**/prompt.md`。

出口（每条都能跑命令证伪）：

- E1：`tools/aisep.py adm 02-business --model workbench` 在「能力」节列出 `ddd:Subdomain` 的那一个子域，在「am4 流程」节列出 `gateApprovalFlow`，在「参与者与角色」节列出那一个角色；「价值流」节报「本节还没有元素」。
- E2：同一命令在 workbench 上报出的缺口包含「能力没有经 Realization 连到需求」（该子域只被流程实现，没有实现需求）；在临时副本里给子域补一条 `am4:Realization` 到某个需求后重跑，这条缺口消失，其他缺口不变（缺口总数恰好减 1）。
- E3：在临时副本里补一个 `am4:ValueStream`，重跑后「价值流」节列出它，不再报空节。
- E4：对同一提交连续跑两次，输出逐字节相同；跑完 `git status --porcelain` 为空（不加 `--out` 时不写任何文件）。
- E5：`tools/aisep.py adm 05-roadmap --model workbench` 三个节都报空节，退出码 0。
- E6：对 workbench 与 procurement 的每个阶段跑一遍，都不报错；每个 `gap` 查询文件头都有 `source:`。
- E7：`gate` 与 CI 必需检查（`gate`、`mergecheck`、`pytest`）在 PR 头通过。
- E1–E5 写成 `aisep-mcp/tests/test_adm_wizard.py`；为免自写代码自写测试循环自证，独立评审人另按本节断言在命令行实跑复核。

## 5. 待定问题（请协调会话确认）

1. **生成的交付物要不要提交？** 建议：不提交，默认只打印（理由见 3.3）。若要提交，位置可选 `models/<slug>/adm/<阶段>.md`；但 `models/` 下不是 `.ttl` 的文件属合并前评审，每次归档都要独立评审。
2. **形态是否同意 B**（`tools/` 命令 + `.rq`，暂不加 MCP 工具）？
3. **本 PR 是否顺带改各阶段 `prompt.md`**（加「先跑向导」一步）？建议：顺带改，否则代理不会用；改动只加一步，不动其他内容。
4. 预备阶段不设检查项、各阶段不做基线与目标两套模型、差距只在路线图做：是否同意？

## 6. 实现后的改动清单与评审级别（预估）

| 路径 | 评审级别 |
|---|---|
| `docs/specs/adm-wizard.md`（本文） | 白名单 |
| `docs/queries/adm/*.rq` | 白名单 |
| `aisep/adm.py`（新增）、`tools/aisep.py`（加子命令） | 合并前评审 |
| `aisep-mcp/tests/test_adm_wizard.py` | 合并前评审 |
| `docs/adm/*/prompt.md`（若第 5 节问题 3 同意） | 合并前评审 |

整份 PR 走合并前评审；不改 `models/**`、`modules/**`、`vendor/**` 和负例清单，所以不需要三步合并，也不需要核对 `negatives`。

## 7. 实现与初稿的差别

- 03 数据去掉「聚合的根实体或所属上下文不是恰好一个」：DDD 模块的 SHACL（`modules/ddd/shapes.ttl`）已在 L3 检查，违反时 gate 直接失败，向导不重复。
- 04 应用技术去掉「技术基线为空」这条缺口查询：清单查询返回 0 行时已报「本节还没有元素」。
- 报告末尾只附本模型的 L4 发现项，不附 gate 摘要行：gate 要跑 L3（SHACL），慢且结论应以 `gate` 命令本身为准。
- 类型判断：`ddd:BoundedContext` ⊑ `am4:ApplicationComponent`、`bpmn:Process` ⊑ `am4:Process`、`aisep:AcceptanceCriterion` ⊑ `am4:Requirement`。清单里需要「只算 am4 记法」的地方（am4 流程、应用组件、需求）按断言类型的命名空间过滤；能力不过滤，`ddd:Subdomain` 算能力。
- 交付物中人写的叙述节（背景、待决问题、差距分析等）名单放在 `aisep/adm.py` 的 `MANUAL`，节名取自各阶段 `template.md`。
