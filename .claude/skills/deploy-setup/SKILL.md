---
name: deploy-setup
description: 把这套 AISEP harness 部署/迁移到新机器或新 GitHub repo——一步步带过 make bootstrap、CODEOWNERS 改名、推送、重建 GitHub 强制层、验证。当用户说"部署/迁移这个 harness"、"clone 后怎么就绪"、"在新 repo 重建强制层"、"setup 这个项目"时使用。
---

# deploy-setup — 部署/迁移 harness 到新环境

完整说明见 [docs/DEPLOY.md](../../../docs/DEPLOY.md)。本 skill 把那份清单变成可执行流程。
**诚实边界**:能自动的只有本地就绪 + 引导;**GitHub 强制层(branch protection)不替用户自动设**——它需要 repo admin 权限,会话内自动设=权限放大,违反"强制层人来配"(契约 01)。本 skill 把命令准备好,由人执行/确认。

## 前提确认(先问清楚)
1. 部署到**新机器**(同一个 GitHub repo),还是**新 GitHub repo**(fork/换组织)?后者多两步(改 owner + 重建强制层)。
2. 目标 `owner/repo` 是什么?
3. 这台机器有没有 `gh auth`(推送 + 设强制层要)、`ruff`(lint 依赖)。

## 步骤

### 1. 本地就绪
```bash
make bootstrap          # 装 lint 依赖 + 激活 .githooks
make test && make arch  # 验证:测试绿 + 架构契约 kept
```
- `make test` 失败 → 报告失败,不继续。
- 缺 ruff → `make bootstrap` 已含 install-dev;若 pip 失败,提示用户手动装。

### 2.(仅新 GitHub repo)改 CODEOWNERS owner
`.github/CODEOWNERS` 里的 `@Albertsun6` 改成目标账号——否则 code-owner 审批无人可批。用 Edit 改,确认后让用户审。

### 3.(仅新 GitHub repo)推送 + 重建强制层
```bash
git remote add origin https://github.com/<owner>/<repo>.git   # 若还没有
git push -u origin main
sh scripts/setup-github-protection.sh <owner>/<repo>          # ← 关键:强制层不随 clone
```
- **这一步不替用户跑也行,但必须明确提醒**:不跑它,新 repo 只有 CI 在跑、"红了不让合"不生效(安全静默降级)。
- 跑完确认输出里 `required check 'gates'` / `code-owner review` 已设。
- 提醒:`enforce_admins=false` 是单人开发裁决(ADR-014);多操作者改 true。

### 4. 验证强制层真生效(可选,推荐)
```bash
gh api repos/<owner>/<repo>/branches/main/protection \
  --jq '{check: .required_status_checks.contexts, codeowners: .required_pull_request_reviews.require_code_owner_reviews}'
```
确认能读到 `["gates"]` + `codeowners: true`。

## 收尾报告
告诉用户:① 本地就绪状态(测试/arch);② 强制层是否已设(或还需用户跑哪条);③ 个人级(记忆/cursor-agent)不影响运行,但异构评审需要 cursor-agent/codex,缺了会降级转人审(契约 05)。
