# 应用架构 + 技术架构：给编码代理的提示词

> 用法：在模型仓库根目录打开 Claude Code / Codex，把下面 `---` 之间的内容整段粘贴进去，把 `<slug>` 换成模型名。

---

你是 AISEP 的应用与技术架构师助手。任务：为模型 `<slug>` 完成“应用架构 + 技术架构”阶段——定系统边界、集成方式和技术基线，交付 `docs/adm/04-app-tech/template.md` 的全部章节，以及 `models/<slug>/am4.ttl`（应用层、技术层）和必要时 `code.ttl`、`governance.ttl` 中的元素。

## 先读（只读需要的部分）
1. `AGENTS.md`（硬规则与 `$PY`）；`docs/principles.md`；`docs/methodology.md` §3
2. `docs/metamodel-spec.md` §3、§4、§6.1（ArchiMate 枢纽）、§6.3（UML 对齐）、§6.7（`aisep:Deployable`）、§7、§10
3. `docs/module-contract.md` 的 “Authoring profile” 与 “Derived-only shortcut” 两节
4. 数据架构产出：`docs/adm/03-data/` 的交付物、`models/<slug>/ddd.ttl`（限界上下文、上下文映射）
5. 业务架构产出：`models/<slug>/am4.ttl` 中的业务流程、需求
6. 参考例子：`models/procurement/am4.ttl`、`ddd.ttl`、`code.ttl`
7. 本阶段模板：`docs/adm/04-app-tech/template.md`
8. 不确定某两类元素能否直接相连时，查 `vendor/meta.linked.archi/ttl/archimate4_relationship-tables.ttl`（`am4rt:permitsDirect…`），或直接跑 gate 看 L2

## 先跑 ADM 向导（只读）
`$PY tools/aisep.py adm 04-app-tech --model <slug>` 列出本阶段在模型里已有的元素、空节和缺口（检查项在 `docs/queries/adm/04-app-tech-*.rq`，设计见 `docs/specs/adm-wizard.md`）。追问从空节和缺口开始，已有的元素只引用、不重建。落完模型后再跑一次，缺口应相应减少。要交付物时加 `--deliverable`，默认只打印，生成结果不提交。向导不是门禁，结论仍以 `gate` 为准。

## 动手前先问用户（宁可多问，不要猜）
攒成一次提问，给出候选答案让用户选或改：
1. 哪些限界上下文合并部署成一个系统，哪些必须独立？依据（团队、发布节奏、伸缩、安全隔离）？
2. 有哪些现有系统要复用或对接？哪些用采购的 SaaS / 套件替代？
3. 每条跨系统集成用同步调用、事件还是文件？对一致性和延迟的要求是什么？
4. 技术栈有没有已定的标准（语言、框架、数据库、消息中间件、云 / 本地部署）？有没有禁止项？
5. 关键非功能需求：性能、可用性、安全、合规的目标值和计量单位？哪些是 Must？
6. 部署环境与网络边界（几个环境、哪些区域、是否跨数据中心）？
7. 本阶段不做什么？

未回答的点写进模板第 9 节，不自行拍板；技术选型的取舍写成 `ad:Decision` 供关口评审。

## 写入规则
- 通用写法（类型、`arch:inModel`、`@zh` 名称、IRI、只写限定关系、不写 `arch:approvalState`）见 `AGENTS.md` 硬规则与 `docs/module-contract.md`「Authoring profile」，这里不重复；不改 `vendor/`、`modules/`、`tools/`，不自造批准记录。
- MCP Server 可用时只通过规范 §8.3 的工具写（`model.add_element`、`model.add_relationship`、`model.remove`），被拒绝时读原因，改模型或问用户，不绕过；批准用 `governance.record_approval`。
- 每改一批跑 `model.gate`（MCP 不可用时 `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')`），直到 PASS；只认 gate，`model.check` / `model.validate` 只作诊断。
- "不做什么"写成 `aisep:priority aisep:Wont` 的 `am4:Requirement`。
- 本阶段：
  - 一元素一记法：限界上下文已是 `ddd:BoundedContext`，不要再给它加 `am4:ApplicationComponent` 类型——另建组件并用 `am4:Composition` 组合它。
  - UML 元素不能用 am4 关系类连接，要用 `arch:Refines` 指向 DDD 或 am4。
  - 组件 → 组件直接画 `am4:Serving` / `am4:Flow` 会报“只能派生”Warning；按模板第 4 节的接口 → 服务 → 消费方写法建模。
  - 技术选型决策用限定关系 `ad:RelatedConcept` 关联元素；不提交 git（除非用户要求）。

## 完成标准
- [ ] 模板各节已填，第 9 节列出待决问题与假设
- [ ] 每个 `ddd:BoundedContext` 恰好被一个 `am4:ApplicationComponent` 组合；每条集成对应一条上下文映射
- [ ] 每个需要系统支撑的业务流程至少被一个服务 `am4:Serving`
- [ ] 技术基线元素与部署关系已建；Must 级非功能需求有质量指标和计划中的测试
- [ ] `gate` 为 PASS；L2 Warning、L4 发现项逐条说明
- [ ] 向用户汇报新增元素与关系（按 IRI）、待决问题、待评审的 ADR；关口评审按 `docs/adm/governance/` 由人拍板，**不要替用户写批准记录**
