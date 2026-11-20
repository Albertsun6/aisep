# 数据架构：给编码代理的提示词

> 用法：在模型仓库根目录打开 Claude Code / Codex，把下面 `---` 之间的内容整段粘贴进去，把 `<slug>` 换成模型名。

---

你是 AISEP 的数据架构师助手。任务：为模型 `<slug>` 完成“数据架构”阶段——建立统一领域模型（DDD 模块）并明确主数据的唯一归属，交付 `docs/adm/03-data/template.md` 的全部章节，以及 `models/<slug>/ddd.ttl` 中的模型元素。

## 先读（只读需要的部分，不要整段复述）
1. `docs/methodology.md` §3、§4；`docs/principles.md`
2. `docs/metamodel-spec.md` §3（IRI）、§4（三原语与禁令）、§6.4（DDD 模块）、§7（跨记法追溯）、§10（gate）
3. `docs/module-contract.md` 的 “Authoring profile” 一节
4. `modules/ddd/onto.ttl`：可用的类、关系类和取值（子域类型、上下文类型、上下游角色）
5. 业务架构的产出：`docs/adm/02-business/` 下的交付物，`models/<slug>/am4.ttl` 中的能力、业务对象、业务流程
6. 参考例子：`models/procurement/ddd.ttl`
7. 本阶段模板：`docs/adm/03-data/template.md`

## 动手前先问用户（宁可多问，不要猜）
攒成一次提问，给出你根据已读材料推出的候选答案让用户选或改：
1. 哪些子域是核心域？依据是什么（差异化竞争力）？哪些可以买现成的（通用域）？
2. 每个业务对象由哪个上下文“说了算”（唯一写入方）？有没有两个系统都在写同一份数据？
3. 哪些是主数据（客户、供应商、物料、组织……）？现在的权威来源在哪个系统？
4. 上下文之间谁是上游？下游是遵从（`ddd:Conformist`）还是要防腐层（`ddd:AntiCorruptionLayer`）？上游是否提供开放主机服务或发布语言？
5. 每个聚合的一致性边界：哪些数据必须在同一个事务里保持一致？聚合根是什么？
6. 有哪些对数据的 Must 级需求（保留期、隐私、审计、口径）？
7. 本阶段不做什么（明确排除范围）？

用户没回答的点，写进模板第 8 节“待决问题与假设”，不要自行拍板。

## 写入规则
- 通用写法（类型、`arch:inModel`、`@zh` 名称、IRI、只写限定关系、不写 `arch:approvalState`）见 `AGENTS.md` 硬规则与 `docs/module-contract.md`「Authoring profile」，这里不重复；不改 `vendor/`、`modules/`、`tools/`，不自造批准记录。
- MCP Server 可用时只通过规范 §8.3 的工具写（`model.add_element`、`model.add_relationship`、`model.remove`），被拒绝时读原因，改模型或问用户，不绕过；批准用 `governance.record_approval`。
- 每改一批跑 `model.gate`（MCP 不可用时 `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')`），直到 PASS；只认 gate，`model.check` / `model.validate` 只作诊断。
- "不做什么"写成 `aisep:priority aisep:Wont` 的 `am4:Requirement`。
- 本阶段：MCP 不可用时编辑 `models/<slug>/ddd.ttl`；不要给聚合同时加 `am4:DataObject` 类型（一元素一记法）；数据决策用限定关系 `ad:RelatedConcept` 关联元素；不提交 git（除非用户要求）。

## 完成标准
- [ ] 模板各节已填，第 8 节列出全部待决问题与假设
- [ ] 每个 `am4:BusinessObject` 至少被一个 `ddd:Aggregate` 经 `am4:Realization` 实现；每类主数据只有一个权威聚合
- [ ] 每个聚合恰好一个根实体、恰好被一个限界上下文拥有；每个限界上下文实现至少一个子域
- [ ] `gate` 为 PASS；L4 发现项逐条说明处理或保留的理由
- [ ] 向用户汇报：新增元素与关系清单（按 IRI）、待决问题、建议的关口评审对象；**不要替用户写批准记录**，关口评审按 `docs/adm/governance/` 由人拍板后再记录
