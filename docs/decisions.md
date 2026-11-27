# AISEP 架构决策记录（索引）

每个 ADR 一个文件，放在 [`docs/adr/`](adr/)，文件名 `NNN-<slug>.md`；每条记录含编号、日期、决策、理由、后果，带日期的补记写在各自文件末尾。目录、命名、编号分配与抢号处理见 [ADR-034](adr/034-one-file-per-adr.md)。

新增 ADR：取 `origin/main` 上 `docs/adr/` 已有最大编号加 1，在同一个 PR 里新增文件并在下表**末尾**加一行。两个并行 PR 取到同一编号时，这张表的末行会合并冲突：后合并的 PR 改号（重命名文件、改文件首行与本行）。本表与 `docs/adr/` 的一一对应、编号唯一由 `aisep-mcp/tests/test_adr_index.py` 检查。

| 编号 | 日期 | 标题 | 状态 |
|---|---|---|---|
| [ADR-001](adr/001-tailored-togaf-adm.md) | 2026-11-19 | 采用裁剪后的 TOGAF ADM 作为方法论顶层框架 | 未注明 |
| [ADR-002](adr/002-three-layer-structure.md) | 2026-11-19 | 三层结构：基础设施层、方法论层、业务系统层 | 未注明 |
| [ADR-003](adr/003-three-primitives.md) | 2026-11-19 | 模型仓库底层统一为元素、关系、视图三原语 | 未注明 |
| [ADR-004](adr/004-archimate4-hub-notation.md) | 2026-11-19 | 以 ArchiMate 4.0 为枢纽记法 | 部分修正，见 ADR-010 |
| [ADR-005](adr/005-five-architecture-principles.md) | 2026-11-19 | 五条架构原则 | 未注明 |
| [ADR-006](adr/006-workbench-fork-orchestrator.md) | 2026-11-19 | 工作台以 Orchestrator.inc 为骨架 fork | 已采纳 |
| [ADR-007](adr/007-linked-archi-foundation.md) | 2026-11-19 | Linked.Archi core + ArchiMate 4.0 作为底座 | 未注明 |
| [ADR-008](adr/008-mcp-server-first.md) | 2026-11-19 | 一期交付物为 MCP Server | 未注明 |
| [ADR-009](adr/009-approval-records-in-repo.md) | 2026-11-19 | 批准记录是模型仓库中的治理实体 | 未注明 |
| [ADR-010](adr/010-own-bpmn-uml-alignment.md) | 2026-11-19 | BPMN、UML 子类对齐由 AISEP 自行编写 | 已采纳 |
| [ADR-011](adr/011-metamodel-v02-decisions.md) | 2026-11-19 | 元模型规范 v0.2 的 D1–D10 按建议采纳 | 已采纳 |
| [ADR-012](adr/012-metamodel-v03-rules.md) | 2026-11-20 | 元模型规范 v0.3 新增 14 条规则 | 已采纳 |
| [ADR-013](adr/013-ai-in-progress-from-git.md) | 2026-11-20 | 「AI 进行中」读编排器，改动由 Git 分支差异算出 | 已采纳 |
| [ADR-014](adr/014-mcp-interface-final.md) | 2026-11-20 | MCP Server 接口定稿 | 已采纳 |
| [ADR-015](adr/015-mcp-interface-round3.md) | 2026-11-20 | 第三轮评审后的接口与规范同步 | 已采纳 |
| [ADR-016](adr/016-mcp-interface-round4.md) | 2026-11-20 | 第四轮评审后的接口与规范同步 | 已采纳 |
| [ADR-017](adr/017-mcp-interface-round4-recheck.md) | 2026-11-21 | 第四轮复评拍板 | 已采纳 |
| [ADR-018](adr/018-vendor-unlicensed-removal.md) | 2026-11-21 | 删除 vendor 中未使用且未声明许可的文件 | 已采纳 |
| [ADR-019](adr/019-merge-and-review-process.md) | 2026-11-21 | 第一条端到端链路阶段的合并与评审流程 | 已采纳 |
| [ADR-020](adr/020-backfill-executed-decisions.md) | 2026-11-21 | 补登记已在执行的决定 | 已采纳 |
| [ADR-021](adr/021-approval-only-pr-and-review.md) | 2026-11-21 | 批准专用 PR 机械核对等四项补充 | 已采纳 |
| [ADR-022](adr/022-negatives-from-ci.md) | 2026-11-21 | 负例改认 CI 结果 | 已采纳 |
| [ADR-023](adr/023-governance-records-must-be-iris.md) | 2026-11-22 | 治理记录必须是带 arch:inModel 的 IRI | 已采纳 |
| [ADR-024](adr/024-mvp-relax-checks.md) | 2026-11-25 | MVP 期间放宽校验与留痕 | 已采纳 |
| [ADR-025](adr/025-c4-archimate4-dual-model.md) | 2026-11-26 | C4 与 ArchiMate 4 双模型 | 已采纳 |
| [ADR-026](adr/026-actions-in-metamodel.md) | 2026-11-26 | 动作定义建进元模型 | 已采纳 |
| [ADR-027](adr/027-modules-ttl-post-merge-review.md) | 2026-11-26 | modules 下的 .ttl 改为合并后评审 | 已采纳 |
| [ADR-028](adr/028-model-set-attributes.md) | 2026-11-27 | model_set_attributes 接口取舍（补记） | 已采纳 |
| [ADR-029](adr/029-module-property-domains.md) | 2026-11-27 | 模块属性必须声明定义域 | 已采纳 |
| [ADR-030](adr/030-tool-and-domain-zones.md) | 2026-11-27 | 工具区与领域区分区 | 已采纳 |
| [ADR-031](adr/031-server-call-log.md) | 2026-11-27 | 服务端调用日志与防篡改审计的触发条件 | 已采纳 |
| [ADR-032](adr/032-workbench-view-edit-boundary.md) | 2026-11-27 | 工作台视图的查看与编辑边界 | 已采纳 |
| [ADR-033](adr/033-auto-merge-and-cadence.md) | 2026-11-27 | 自动合并与合并节奏 | 已采纳 |
| [ADR-034](adr/034-one-file-per-adr.md) | 2026-11-27 | 一个 ADR 一个文件 | 已采纳 |
