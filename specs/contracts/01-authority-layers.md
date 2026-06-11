# 契约 01 · 权威层级(=ADR-014)

| 层 | 机制 | 性质 | 谁能绕过 |
|---|---|---|---|
| **强制层(唯一)** | GitHub CI(gates.yml)+ branch protection + CODEOWNERS(按下方配置清单开启) | 对 AI 和人同等生效 | 仅 repo admin 经 break-glass(契约 09)显式改保护规则 |
| 反馈层 | 本地 pre-commit(`.githooks/` + `core.hooksPath`) | 快速反馈,**明文承认可旁路**(`--no-verify`、改 hooksPath) | 任何人/任何会话 |
| 会话护栏 | `settings.json` `permissions.deny` / 权限模式 | 会话内摩擦,防呆不防恶 | 改 settings、换无防护会话 |
| 建议层 | CLAUDE.md / constitution.md / skills 文案 | 模型可无视 | 模型自身 |

## 强制层机器可验证配置清单(M4 建远端时逐项核对)

branch protection(main)必须开启,缺一项即"强制层未生效":

1. `Require status checks to pass` + required check 名 = **`gates`**(gates.yml 的 job 名,钉死不改);
2. `Require a pull request before merging` + `Require review from Code Owners`(CODEOWNERS 只有开了这一项才强制);
3. `Do not allow bypassing the above settings`(含 administrators)——admin 绕过必须走 break-glass 流程,不能是默认能力;
4. `Require branches to be up to date before merging`。

## 硬规则

1. **会话内的一切编排——Workflow、Agent 工具、长程会话、本地 git hooks / 会话 hooks——永远不是强制**。任何 ADR/文档不得以会话内构件作为权威或强制层的论据。理由:会话内约束是"被约束方自己执行的约束",定义落在模型可写路径。(注:GitHub 侧 webhook/App check 属远端强制链,不在此限。)
2. "已强制"三个字只允许指向按上述清单配置生效后的强制层。远端 + 配置清单生效之前,本 repo 不存在任何强制,只有反馈与建议。
3. 受 CODEOWNERS 保护的路径:`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`。

## 钉死方式

- M4 验收 = 配置清单逐项核对 + 三个攻击探针 PR 全被拦(无 feature 声明的 src 提交 → required check `gates` 红;同 PR 改空 gates.yml → Code Owners 审查拦;改已冻结 spec → `gates` 的 receipt 校验红 + Code Owners 拦);
- 本契约文字本身受 CODEOWNERS 保护。
