## ADR-011 · 2026-11-19

- **状态**：已采纳
- **决策**：元模型规范 v0.2 的 D1–D10 全部按建议采纳：DDD 的 BoundedContext ⊑ ApplicationComponent、Subdomain ⊑ Capability、Command ⊑ Event（可带载荷）；BPMN 的 Task/Lane 不升格，需要追溯的节点 refines 到 am4；作者只写限定关系；元素只允许一个最具体类型；影响分析分 depends（默认）和 ripple 两种模式；跨记法只允许枢纽关系、refines、追溯关系三类连接；refines 按 code→design→hub 层级、每种记法最多一个主锚；approvalState 由批准记录推导，不手填。
- **理由**：metamodel-prototype 已验证（84 项测试全部通过，14 条验收主张全部成立）；GPT 设计评审与原型对抗审计提出的反驳都已吸收进规范，见《AISEP 第二步：元模型规范（草案）》附录 B。
- **后果**：原型需要实现 v0.2 的改动（记法混用规则、refines 层级、批准记录、两种影响模式、派生捷径 Warning）；MCP Server 按规范 §8.3 的语义契约设计。
