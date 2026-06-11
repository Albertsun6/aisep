#!/bin/sh
# 重建 main 的 branch protection —— 唯一强制层(契约 01),**不随代码 clone**。
# clone/push 到新 GitHub repo 后跑一次,否则新部署只有 CI 在跑、但"红了不让合"不生效(安全降级)。
#
# 用法: scripts/setup-github-protection.sh <owner/repo>
#   例: scripts/setup-github-protection.sh Albertsun6/AISEP6-6
# 前置: gh auth login;CODEOWNERS 里的 @owner 已改成你的账号
set -e
REPO="${1:?用法: $0 <owner/repo>}"
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<JSON
{
  "required_status_checks": { "strict": true, "contexts": ["gates"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "require_code_owner_reviews": true, "required_approving_review_count": 1 },
  "restrictions": null
}
JSON
echo "✓ branch protection 已设: required check 'gates' / code-owner 审批 / enforce_admins=false"
echo "⚠ enforce_admins=false 是单人开发的裁决(ADR-014);多操作者时改 true,否则强制层对 admin 不生效"
echo "⚠ .github/CODEOWNERS 里的 owner 记得改成你的 GitHub 账号,否则 code-owner 审批无人可批"
