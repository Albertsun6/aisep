## ADR-025 · 2026-11-26

- **状态**：已采纳（双模型是规范给定的前提；第 2–4 款的关联方式、数据库映射、层级与上游版本由 Albert 2026-11-25 在关口 A 拍板，见 [`docs/specs/c4-archimate4-verification.md`](../specs/c4-archimate4-verification.md) §9.3；本条补记，已由 PR #103、#106、#111 落地；底座版本更新 ADR-007 的 core 0.6.0，ADR-007 原文不改）
- **决策**：C4 与 ArchiMate 4 走**双模型**，同一知识图谱、显式关联，C4 不做成 ArchiMate 的视图（规范 [`docs/specs/c4-archimate4-dual-model.md`](../specs/c4-archimate4-dual-model.md)）。
  1. **C4 是独立记法模块** `modules/c4`（Language，`aisep:inheritsHubRules false`）：词汇只用上游 `c4/onto` 与 `c4/structurizr`，不写 `align.ttl`，不声明任何 C4 ⊑ am4 公理。这是 ADR-004「其他记法通过子类对齐接入」的例外（元模型规范 §0、§6.8）。
  2. **跨模型关联用 `arch:refines`**，方向 C4 → am4，C4 的层级是 **design**（`aisep:LevelDesign`，元模型规范 §7.2）；不用上游 DD-11 的 `skos:exactMatch` 加 reconciliation 图，因为它不在 D8 允许的三类连接里，要求的记录形式（RDF 1.2 三元组项）又被 L0 禁止，还会和已在用的 refines 形成两套身份机制。
  3. **一个数据库对应多个逻辑数据对象时**，先在 am4 侧聚合，数据库再 refines 聚合后的那个 DataObject，以守住 §7.2 的主锚唯一。
  4. **上游整体升到线上版**（core 0.7.0，PR #103），带来 `arch:DependsOn`，它同样受记法混用规则约束（G5，见 ADR-012）。
- **理由**：规范要求两套模型放在同一知识图谱里，各管一类事实，通过显式关联连接。`arch:refines` 是上游 core 自己的跨模型追溯谓词，也是 AISEP 对 BPMN、DDD、UML 已在用的机制，已有 L1 的方向与主锚规则，不需要新的身份机制（核实报告 §9.3）。
- **后果**：AISEP 自有的 C4 规则 R1–R8 写在 `modules/c4/shapes.ttl`；与规范原文的偏离（R1 反向按「至多一个」、R4 由构建保证、R6/R7 以上游关系表为准经 Role 执行等）记在 [`docs/specs/c4-archimate4-step4.md`](../specs/c4-archimate4-step4.md) §4，规范原文不改。已知局限：组件归属不检查；独立治理的数据库无法同时 refines 组件和 DataObject（第 3 款的副作用）。
