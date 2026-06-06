# Tasks: <功能名>

- 关联 Plan: <FEATURE-ID>

> 每个任务必须可独立执行、可验证，并回链到验收标准（AC*）。高风险类型（migration/security/auth/...）标注 [HITL]。

| 任务ID | 标题 | 类型 | 回链 AC | HITL | 验证方式 |
|---|---|---|---|---|---|
| T1 | <标题> | feature | AC1 | 否 | 单测通过 |
| T2 | <标题> | migration | AC2 | 是 | 迁移演练 + 回滚验证 |
