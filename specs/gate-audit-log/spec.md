# gate-audit-log — 门禁运行追加到本地 append-only 审计流水

status: active
目标:每次 gate(gate-spec/gate-trace/gate-judge/gate-commit)运行时,除了写/覆盖 receipt,再**追加**一行到 `.aiforge/audit/gates.jsonl`——补 receipt"同 gate 重跑覆盖"丢失的"何时跑过哪些 gate、结果如何"的时间线。

## 背景与范围
- 现状:receipt(`specs/<id>/gates/<gate>.json`)同 gate 重跑会覆盖,只留最后一次;没有"跑过哪些 gate"的连续时间线。
- 范围内:在 harness 写 receipt 的同一处,顺带向 `.aiforge/audit/gates.jsonl` 追加一行(JSON Lines);不动 receipt 本身。
- **不做**:不做防篡改(HMAC 链 / 外部 sink 是强制版事项,契约 06 已推迟);不入库(本地流水,`.gitignore` 已忽略 `.aiforge/audit/*.jsonl`)。

## 验收标准(Gherkin)
- Given 跑一次 `gate-spec`(对合法 spec)
  When 命令结束
  Then `.aiforge/audit/gates.jsonl` 末尾追加一行 JSON,含 `gate`、`feature_id`、`decision`、`exit_code`、`git_head`、`run_id`、`created_at`。
- Given 连续跑两个 gate
  When 都结束
  Then 审计文件有**两行**(append 不覆盖;第一行原样保留)。
- Given `.aiforge/audit/` 目录不存在
  When 跑任一 gate
  Then 目录被自动创建,审计行正常写入,gate 不报错。
- Given 审计写入失败(如目录不可写)
  When 跑 gate
  Then **gate 本身的 decision/退出码不受影响**(审计是旁路观测,fail-open),仅向 stderr 打印一行警告。

## 非功能清单(P6)
- 安全(**诚实定位**):这是**本地 append-only 流水,不是防篡改保证**——本地文件可被删/改;真防篡改 = HMAC 哈希链 + 外部不可写 sink,属强制版(契约 06 推迟)。审计行**不含 secret**(只记 gate 元数据,与 receipt 同字段集,无文件内容)。
- 错误处理:审计写失败 **fail-open**(旁路,不阻断门禁)——取舍理由:审计是观测增强,不该让"写日志失败"把通过的门禁变成不通过;但失败必须 stderr 可见,不静默。**(此取舍请 supervisor 确认)**
- 可观测:本功能即可观测性增强;jsonl 可被 `tail -f` / `jq` 直接消费。
- 限流/审计:N/A。
