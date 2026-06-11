# gate-audit-log · plan(architecture)

> refs: spec.md

## 设计
- **落点 = `harness.write_receipt`**:所有 gate 的 receipt 都经它落盘——在此一处末尾追加审计行,DRY 覆盖全部 gate(② Simplicity:不在每个 gate 函数重复)。
- `_append_audit(receipt, repo_root)`:从 receipt dict 取**子集字段**(created_at/gate/feature_id/decision/exit_code/git_head/run_id),JSON Lines 追加到 `.aiforge/audit/gates.jsonl`。
- **fail-open**(supervisor 拍板):`try/except OSError → stderr 警告`,不抛、不改 gate 的 decision/退出码。
- 不动 receipt 写入逻辑、不动任何 gate 的判定;审计行字段集 ⊆ receipt 字段(无文件内容/secret)。
- 路径 `.aiforge/audit/gates.jsonl` 已被 `.gitignore` 忽略(`!.gitkeep` 保留目录),不入库。

## 影响面 / 红线
- 仅 `src/aiforge/harness.py` 加一个私有函数 + write_receipt 末尾一行调用;`.importlinter` 分层不变(harness 已在该层)。
- 现有 gate 测试不受影响(审计是附加旁路,receipt/decision/退出码不变)。

## 不做
- 不做 HMAC/哈希链/外部 sink(强制版,契约 06);不做日志轮转/清理(YAGNI)。
