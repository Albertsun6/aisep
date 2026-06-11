# 契约 06 · gate receipt 回执链

每次 gate 运行由 **CLI 真实命令**写出 receipt;模型贴回会话的只是引用。这是对抗长程自主"静默跳阶段"的机器证据:跳了 = receipt 缺失 = `gate-commit`/CI 拒绝。

## 路径与 schema(v1)

路径:`specs/<feature-id>/gates/<gate-name>.json`。同 gate 重跑**覆盖**,每次运行带唯一 `run_id`;**权威消费在 CI(已提交状态)**——本地覆盖/amend 不构成审计漏洞(本地本就是反馈层);append-only 审计日志显式推迟(强制版 HMAC sink 事项)。

```json
{
  "schema_version": 1,
  "run_id": "<uuid4>",
  "gate": "gate-spec | gate-trace | gate-judge | gate-commit",
  "feature_id": "<id 或 _workspace>",
  "inputs": [{"path": "specs/<id>/spec.md", "sha256": "<hex>"}],
  "exit_code": 0,
  "decision": "approved | rejected | needs_human | infra_error",
  "git_head": "<commit sha>",
  "git_dirty": true,
  "created_at": "<ISO-8601 带偏移>",
  "tool": "aiforge gate-spec",
  "aiforge_version": "<版本>",
  "argv": ["gate-spec", "specs/<id>/spec.md"],
  "ack": null,
  "reviewer": null
}
```

- `ack`(契约 07,人审审计):`{"user", "uid", "hostname", "tty", "at"}` —— 审计信号,非身份认证;
- `reviewer`(契约 05,异构评审):`{"tool", "params", "reported_model", "observed_source"}`;
- `inputs[].path`:相对 repo root 的 POSIX 路径;`sha256` 对**原始字节**计算(契约 09);
- `git_head` + `git_dirty`:生成时刻的 HEAD 与工作区是否干净;
- 消费方**忽略未知字段**;`schema_version` 高于自己认识 → 退出码 3 并打印诊断(契约 09)。

## 链校验规则(`gate-commit` 与 CI 同语义)

1. **feature 声明制**(契约 02):staged 含 `src/`、`tests/` 改动 → 必须有 feature 声明(`--feature`/`AIFORGE_FEATURE`),无声明 → 1;
2. 声明的 id 与 staged 中出现的 `specs/<id>/`:上游 receipt 必须**齐全**(按阶段顺序,最低要求 gate-spec)且**未过期**(inputs hash 与当前文件一致)、decision=approved(2 走契约 07 通道);缺失/过期/伪造(hash 不符)→ 1;
3. receipt 文件不可解析/版本不识别 → 3,stderr 给出可读诊断(哪个文件、建议重跑哪个 gate)。**3 与 1 同样阻断**,差别仅在诊断含义(内容问题 vs 基础设施问题)。

## 钉死方式(M1)

- 篡改测试:改动 spec.md 后不重跑 gate-spec,断言 `gate-commit` = 1;
- 伪造测试:手写 decision=approved 但 hash 不符的 receipt,断言 = 1;
- 坏 receipt 测试:写入非法 JSON / schema_version=99,断言 = 3 且 stderr 有诊断。
