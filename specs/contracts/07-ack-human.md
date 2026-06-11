# 契约 07 · `--ack-human` 双层语义

`needs_human`(退出码 2)的放行分两层,**不可混淆**:

| 层 | 动作 | 效力 |
|---|---|---|
| 本地 ack | `aiforge gate-commit --ack-human` | **仅审计**:要求 stdin isatty(防脚本/模型自动 ack)、记录执行者(`$USER`)到 receipt 的 `actor`;只解锁**本地 pre-commit** |
| 权威放行 | GitHub **人类账号**对 PR 的 approval(branch protection 要求) | 唯一作数的放行 |

## 硬规则

1. **CI 永远重跑 gate,不消费本地 ack**——本地 ack 的 receipt 对 CI 无放行效力;
2. 非 tty 环境下 `--ack-human` 直接失败(退出码 3),不留"环境变量绕过"通道;
3. 会话内禁止自我放行:`permissions.deny` 含 `Bash(* --ack-human*)`(M3;护栏性质,真强制仍在 CI)。

## 钉死方式(M1)

- 非 tty 调用 `--ack-human` → 断言退出码 3;
- ack 后 receipt `actor.type == "human-ack"` 且记录了 user;
- gate-commit 在"有本地 ack receipt 但 CI 模式(env 标记)"下仍按原始 decision 处理。
