# gate-audit-log 异构评审辩论记录(2026-06-11)

- **评审者**:cursor-agent(`-p --mode ask`),自报 **GPT-5.5**。原始输出见会话留痕。
- **verdict**:有条件通过(补 1 High + 1 Medium 后落)→ 全部采纳。
- **时机**:提交后对抗验证(183e175 已进 main+CI 绿),据评审补一个 fix commit。

| 严重度 | 意见 | 裁决 | 落改 |
|---|---|---|---|
| High | 审计写入缺 symlink 防护(write_receipt 有,_append_audit 没有)→ 污染仓库可写到 repo 外 | **接受** | `_append_audit` 加契约 09 风格 symlink 防护(`.aiforge`/`audit`/`gates.jsonl` 任一是 symlink 则拒绝跟随、fail-open 警告);新增 `test_audit_symlink_path_refused`(断言不写到 repo 外) |
| Medium | `open("a")+write` 多进程一行不交错保证不够硬 | **接受** | 改 `os.open(O_APPEND\|O_CREAT\|O_WRONLY)` + 单次 `os.write(bytes)`;文档标 "best-effort 不交错"(不上 fcntl 锁,YAGNI) |
| Medium | fail-open 仅成立于"旁路观测"定位,否则掩盖审计缺失 | **接受** | spec/注释加"**非放行依据**;未来若当强审计须另加 `--strict-audit`/CI fail-closed" |
| Low | 字段 allowlist 对(无 secret),建议加防回归测试 | **接受** | `test_audit_no_sensitive_fields`:断言审计行只含 7 字段 allowlist,绝不含 argv/ack/reviewer/inputs/tool/version |
| Low | "append-only" 易误解为存储不可改 | **接受** | 改 "**writer** append-only / 本地追加流水";继续明确"可删改、非防篡改" |
| Low | 落点 write_receipt 合理;约束新 gate 走 write_receipt | **接受(注释)** | 注释说明审计经 write_receipt 统一落点;`gate-spec --check` 不写 receipt 故不审计(合理) |

验证:落改后 96 测试绿(+2)/ruff 0/arch kept;改冻结 spec 已重跑 gate-spec。
