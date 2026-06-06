# Tasks: 用户头像上传

- 关联 Plan: F001

| 任务ID | 标题 | 类型 | 回链 AC | HITL | 验证方式 |
|---|---|---|---|---|---|
| F001-T1 | 实现 FileValidator（大小/类型/魔数） | feature | AC2 | 否 | 单测覆盖边界 |
| F001-T2 | 实现 BlobStore 抽象 + 本地实现 | feature | AC1 | 否 | 集成测试 |
| F001-T3 | 实现 AvatarController（鉴权+编排） | auth | AC1,AC3 | 是 | 集成 + 人审 |
| F001-T4 | 接入限流与审计 | feature | 非功能 | 否 | 集成测试 |
| F001-T5 | 可观测埋点（计数/耗时） | feature | 非功能 | 否 | 指标出现 |
