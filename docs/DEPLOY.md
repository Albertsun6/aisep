# 部署 / 迁移说明 — 哪些在 repo,哪些要重建

> 一句话:**harness 的所有"内容"都在这个 repo 里**(代码/契约/agents/skills/钩子/CI 定义全入库);
> 部署到新机器或新 GitHub repo 时,只需**重建几个外部状态**——其中只有 GitHub 强制层不重建会**静默降级安全**,务必跑。

## A. repo 自洽(clone 就有,零丢失)

| 资产 | 位置 |
|---|---|
| 核心引擎 + 门禁 CLI | `src/aiforge/`(**零运行期依赖**,纯标准库) |
| 角色 agent / 阶段 skill / 会话护栏 | `.claude/agents/`、`.claude/skills/sdlc-*`、`.claude/settings.json` |
| 本地钩子 / CI 强制层定义 | `.githooks/pre-commit`、`.github/workflows/gates.yml`、`.github/CODEOWNERS` |
| 契约 / 宪法 / 决策文档 | `specs/contracts/`、`constitution.md`、`docs/` |

`make test` / 门禁 / 整套流程,clone 下来直接能跑,**不依赖 `~/.claude` 的任何东西**。

## B. 新克隆/新机器要重建(有命令,不重建只是缺便利或 lint)

```sh
make bootstrap          # = make install-dev (装 ruff/import-linter) + make hooks (激活 .githooks)
make test && make arch  # 验证就绪
```

- 不跑 `make hooks`:只是没本地 pre-commit 反馈,CI 仍兜底(反馈层,契约 01)。
- 不跑 `make install-dev`:门禁的 lint 步骤会 fail-closed 报 infra(退出码 3),提示装。

## C. 新 GitHub repo 要重建强制层(**唯一不做会安全降级的**)

branch protection 是 **repo settings,不在代码里、不随 clone**。不重建 → 新部署默认**只有 CI 在跑,但"红了不让合""要 code-owner 审批"这些强制是关的** = 以为有强制层、其实没有。

```sh
# 1) 把 .github/CODEOWNERS 里的 @Albertsun6 改成你的 GitHub 账号
# 2) 推到你的 remote 后,一键重建强制层:
scripts/setup-github-protection.sh <你的owner>/<repo>
```

该脚本设:required status check = `gates`(strict)、require code-owner review、`enforce_admins=false`。
⚠️ `enforce_admins=false` 是单人开发的裁决(ADR-014);**多操作者时改 true**,否则强制层对 repo admin 不生效。
⚠️ **单人仓 2026-06-13 修订(契约 01)**:强制 review/code-owner 项已撤销,机器强制仅剩 required check `gates`;脚本保留完整保护配置以便多人化时一键恢复——单人部署跑完脚本后可按脚本头注释删除 review 项复刻该裁决。

## D. 个人/机器级(不进 repo,也不影响项目运行)

| 东西 | 说明 |
|---|---|
| `~/.claude/projects/.../memory/` | AI 协作记忆——影响 Claude 会话连续性,**不影响项目运行/门禁** |
| 用户级 `~/.claude/settings.json` | 个人配置;本项目**不依赖**(项目级 `.claude/settings.json` 已覆盖) |
| `gh` auth | 机器级凭证,新机器 `gh auth login` |
| cursor-agent / codex(异构评审) | 机器级,新机器没有就**降级转人审**(契约 05 fail-closed),不阻断 |

## 一句话检查清单(部署到新 GitHub repo)

```sh
git clone <你的repo> && cd <repo>
make bootstrap                                   # B: 本地就绪
# 编辑 .github/CODEOWNERS 的 owner
git push origin main
scripts/setup-github-protection.sh <owner>/<repo>  # C: 强制层(关键!)
make test && make arch                           # 验证
```
