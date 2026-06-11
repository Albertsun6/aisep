# 契约 08 · specs/ 目录契约 + agent 双宿主规范

## specs/<feature-id>/ 目录契约

```
specs/<feature-id>/
├── spec.md      # P3 产物;头部可带 `status: active|abandoned`;过 gate-spec 后冻结(改动走契约 02 变更流程)
├── plan.md      # PA 产物(+ ADR 引用);须声明上游 refs(`> refs: spec.md`)
├── tasks.md     # decompose 产物(标注可并行组);须声明上游 refs(`> refs: plan.md`)
├── outputs/     # 角色 agent 的结构化 JSON 落盘处
│   └── <role>.json   # 内含 schema_version
└── gates/       # receipt 链(契约 06)
    └── <gate-name>.json
```

- `<feature-id>`:小写 kebab-case,稳定不改名;**废弃** = spec.md 头部标 `status: abandoned`(tombstone,目录保留);拆分/合并记 ADR;更复杂的生命周期显式推迟。
- 这是有头模式的**权威状态存储**,将来 driver 原样继承——**权威**管线状态不得存到此约定之外(CI artifacts/PR 评论/日志/缓存等辅助状态不在此限;会话记忆不算权威状态)。

## agent 双宿主规范(角色 agent 同时可被交互会话与编排工具复用)

物化任何 `.claude/agents/<role>.md`(当前宿主;其他宿主按各自配置位)时必须满足:

1. **file-in / file-out**:输入 = 文件路径(spec/plan/diff),输出 = 写入 specs/<id>/ 的文件 + 结构化 JSON 落盘到 `specs/<id>/outputs/<role>.json`(自报产物路径与结论,内含 `schema_version`);
2. **每角色一个 JSON 输出 schema**(随该角色物化时定义,版本演进按契约 09),消费方按 schema 解析,不靠自然语言抠结论;
3. **定序逻辑不进 prompt**:角色文案只描述单阶段职责;"下一步走哪"由人/skill/将来 driver 决定——prompt 里出现"然后进入下一阶段"即违约;
4. **工具白名单**(内联,自洽;来源 v1 方案 §M2 经评审采纳):

| 角色 | 允许 | 禁止 |
|---|---|---|
| analyst | Read/Grep | Write 代码、Bash |
| architect | Read/Grep/Glob | 改码 |
| developer | Read/Write/Edit/Bash | (受会话护栏约束) |
| reviewer | Read/Grep | Write |
| tester | Read/Write(限 tests/)/Bash(只跑测试) | 改 src/ |
| verifier | Bash/Read | — |
| judge | Read/Bash(只跑 `aiforge gate-judge` 与异构 shell-out) | 自审自过 |

**规范冻结,文案不冻**:提示词措辞随试运行迭代,但违反 1~4 的文案不得合入。机器检查(lint/测试扫 `.claude/agents/*.md` 的 frontmatter 与禁语)随 M2 落地。
