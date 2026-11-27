## ADR-010 · 2026-11-19

- **状态**：已采纳；修正 ADR-004 的"后果"一项
- **决策**：BPMN、UML 到 ArchiMate 4.0 的子类对齐由 AISEP 自行编写，作为独立的对齐模块（只放在 AISEP 自己的图里，不改上游词汇文件）；上游 SKOS 映射文件原样保留，仅作文档参考。
- **理由**：元模型调研（2026-11-19，带文件行号证据，已经复核）证实：上游 `bpmn_crossmappings.ttl` 只有 SKOS 近似映射（closeMatch/relatedMatch），不含任何 `rdfs:subClassOf`/`subPropertyOf`，对子类遍历的查询不可见；UML 没有任何到 ArchiMate 的映射文件。"泳道/参与者通过分配关系挂接"在上游也没有依据。
- **后果**：BPMN、UML 对齐工作量要单独排期：初版只把上游标为 closeMatch 的项升格为子类；多义概念（uml:Class、uml:Component、bpmn:Task/Lane）不做子类对齐，改用 `arch:refines` 显式连接；对齐模块默认不继承 ArchiMate 关系矩阵校验，避免误报。具体方案见《AISEP 第二步：元模型规范（草案）》§5、§6.2、§6.3、§10.2。
