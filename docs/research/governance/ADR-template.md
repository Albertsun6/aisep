> **来源**:老库 AISEP416/architecture/adr/ADR-template.md。本文为可复用 ADR 骨架(当前 specs/templates/ 暂无 ADR 模板,放此供取用);架构决策可用此骨架记录。注:未直接放 specs/templates/ 是因门禁会把 specs/<dir> 当特性校验(templates 豁免是 harness 待改项)。

# ADR-XXXX: [Title]

---

| Field      | Value |
|------------|-------|
| **Date**   | YYYY-MM-DD |
| **Status** | Proposed \| Accepted \| Rejected \| Deprecated \| Superseded by [ADR-XXXX] |
<!-- Status 枚举值必须与 tools/fitness_functions.py::ADR_STATUS_ENUM 一致（FF-3 校验；policies/adr-lifecycle.md §1 定义生命周期） -->
| **Deciders** | [Names / roles] |
| **Tags**   | [e.g. architecture, ai-agent, odoo, infrastructure] |

---

## Context

<!--
Describe the situation, problem, or opportunity that led to this decision.
Include relevant constraints, forces at play, and why a decision is needed now.
Be factual and concise — this section should be understandable without prior context.
-->

## Decision

<!--
State the decision clearly in one or two sentences.
Then explain the rationale — why this option over others.
-->

## Alternatives Considered

<!--
List each alternative that was seriously considered.
For each, briefly explain what it is and why it was not chosen.
-->

### Option A: [Name]

**Description**: ...

**Reason not chosen**: ...

### Option B: [Name]

**Description**: ...

**Reason not chosen**: ...

### Option C: [Name] *(chosen)*

**Description**: ...

**Reason chosen**: ...

---

## Consequences

### Positive

- ...

### Negative

- ...

### Neutral

- ...

---

## References

- 外部链接：使用完整 URL（示例：`https://example.com/path`）
- 相关 ADR：填写编号后链接到对应文件（示例：`ADR-0001-adopt-ai-native-sdlc.md`）
