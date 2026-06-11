# 契约 01 · 权威层级(=ADR-014)

| 层 | 机制 | 性质 | 谁能绕过 |
|---|---|---|---|
| **强制层(唯一)** | GitHub CI(gates.yml)+ branch protection + CODEOWNERS | 不可绕过(对 AI 和人同等生效) | 仅 repo admin 显式改保护规则(走 break-glass,见契约 09) |
| 反馈层 | 本地 pre-commit(`.githooks/` + `core.hooksPath`) | 快速反馈,**明文承认可旁路**(`--no-verify`、改 hooksPath) | 任何人/任何会话 |
| 会话护栏 | `settings.json` `permissions.deny` / 权限模式 | 会话内摩擦,防呆不防恶 | 改 settings、换无防护会话 |
| 建议层 | CLAUDE.md / constitution.md / skills 文案 | 模型可无视 | 模型自身 |

## 硬规则

1. **会话内的一切编排——Workflow、Agent 工具、长程会话、hooks——永远不是强制**。任何 ADR/文档不得以会话内构件作为权威或强制层的论据。理由:会话内约束是"被约束方自己执行的约束",定义落在模型可写路径。
2. "已强制"三个字只允许指向强制层。GitHub 远端 + branch protection 生效之前,本 repo 不存在任何强制,只有反馈与建议。
3. 受 CODEOWNERS 保护的路径(随 M4 生效):`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`。

## 钉死方式

- M4 验收 = 三个攻击探针 PR 全被拦(无 spec 提交 / 同 PR 改空 gates.yml / 改已冻结 spec)。
- 本契约文字本身受 CODEOWNERS 保护。
