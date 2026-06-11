# 契约 06 · gate receipt 回执链

每次 gate 运行由 **CLI 真实命令**写出 receipt;模型贴回会话的只是引用。这是对抗长程自主"静默跳阶段"的机器证据:跳了 = receipt 缺失 = `gate-commit`/CI 拒绝。

## 路径与 schema(v1)

路径:`specs/<feature-id>/gates/<gate-name>.json`(同 gate 重跑覆盖,git 历史即演化记录)

```json
{
  "schema_version": 1,
  "gate": "gate-spec | gate-trace | gate-judge | gate-commit",
  "feature_id": "<id>",
  "inputs": [{"path": "specs/<id>/spec.md", "sha256": "<hex>"}],
  "exit_code": 0,
  "decision": "approved | rejected | needs_human | infra_error",
  "git_head": "<commit sha>",
  "created_at": "<ISO-8601, 本地时区带偏移>",
  "tool": "aiforge gate-spec",
  "actor": null
}
```

- `actor`:默认 `null`(机器);人审放行时为 `{"type": "human-ack", "user": "<执行者>", "isatty": true}`(契约 07);异构评审时记评审者信息(契约 05)。
- `sha256`:对输入文件**原始字节**计算,不做换行/编码规范化(契约 09)。
- `git_head`:receipt 生成时刻的 HEAD;消费方据此判断"过期"(输入文件在 receipt 之后又改过 = hash 不匹配 = 过期)。

## 链校验规则(`gate-commit` 与 CI 同语义)

1. 待提交变更涉及 `specs/<id>/` 或其代码时,该 id 的上游 receipt 必须**齐全**(按阶段顺序)且**未过期**(inputs hash 与当前文件一致);
2. 缺失/过期/decision 非 approved(2 的情况走契约 07)→ 退出码 1;
3. receipt 文件本身解析失败 → 退出码 3。

## 钉死方式(M1)

- 篡改测试:改动 spec.md 后不重跑 gate-spec,断言 `gate-commit` = 1;
- 伪造测试:手写一个 decision=approved 但 hash 不匹配的 receipt,断言 = 1。
