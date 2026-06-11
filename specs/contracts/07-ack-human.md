# 契约 07 · `--ack-human` 双层语义

`needs_human`(退出码 2)的放行分两层,**不可混淆**:

| 层 | 动作 | 效力 |
|---|---|---|
| 本地 ack | `aiforge gate-commit --ack-human` | **仅本地审计记录**:要求 stdin isatty + 记录 `{user, uid, hostname, tty, at}` 到 receipt 的 `ack` 字段;只解锁**本地 pre-commit** |
| 权威放行 | GitHub **人类账号**对 PR 的 approval(branch protection 要求,契约 01) | 唯一作数的放行 |

## 硬规则

1. **CI 永远重跑 gate,不消费本地 ack**——ack receipt 对 CI 无放行效力。CI 模式识别:workflow 显式传 `--ci` 为准,env `CI` 仅辅助;**两者语义只收紧(忽略 ack),不放宽任何检查**——本地伪造 CI 标记得不到任何好处。
2. **isatty 与 user 信息是审计信号/反自动化摩擦,不是身份认证**——伪 TTY、污染的 `$USER` 都可能存在;真正的人类身份证明只来自 GitHub 人类账号 approval。
3. 非 tty 环境下 `--ack-human` → 退出码 3(语义:"审计环境不可满足",属基础设施类;不用 1 以免与"门禁拒绝内容"混淆),不留环境变量绕过通道。
4. 会话内 `permissions.deny` 含 `Bash(* --ack-human*)`(M3)——**护栏性质,不是本契约的安全依据**;安全依据是第 1 条(CI 不消费 ack)。

## 钉死方式(M1)

- 非 tty 调用 `--ack-human` → 断言退出码 3;
- ack 后 receipt `ack` 字段含 user/uid/hostname/tty/at;
- `--ci` 模式下即便存在 ack(mock tty)→ 仍按原始 decision 退出(断言 2)。
