# 契约 08 · specs/ 目录契约 + agent 双宿主规范

## specs/<feature-id>/ 目录契约

```
specs/<feature-id>/
├── spec.md      # P3 产物;过 gate-spec 后冻结(改动走契约 02 变更流程)
├── plan.md      # PA 产物(+ ADR 引用)
├── tasks.md     # decompose 产物(标注可并行组)
└── gates/       # receipt 链(契约 06)
    └── <gate-name>.json
```

- `<feature-id>`:小写 kebab-case,稳定不改名;
- 这就是有头模式的**状态存储**,将来 driver 原样继承——任何工具不得把管线状态存到此约定之外(会话记忆/外部数据库均不算权威状态)。

## agent 双宿主规范(角色 agent 同时可被交互会话与编排工具复用)

物化任何 `.claude/agents/<role>.md` 时必须满足:

1. **file-in / file-out**:输入 = 文件路径(spec/plan/diff),输出 = 写入 specs/<id>/ 的文件 + 一段结构化 JSON(自报产物路径与结论);
2. **每角色一个 JSON 输出 schema**(随该角色物化时定义,带 `schema_version`),消费方按 schema 解析,不靠自然语言抠结论;
3. **定序逻辑不进 prompt**:角色文案只描述单阶段职责;"下一步走哪"由人/skill/将来 driver 决定——prompt 里出现"然后进入下一阶段"即违约;
4. 工具白名单按 v1 方案 §M2 表执行(analyst 禁 Write 代码、tester 只写 tests/ 等)。

**规范冻结,文案不冻**:提示词措辞随试运行迭代,但违反 1~4 的文案不得合入。
