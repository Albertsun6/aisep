#!/bin/sh
# SessionStart hook:用 Claude Code 打开本项目时自动就绪。
# 只做**本地、无副作用风险**的自动化:激活本地门禁钩子 + 检测 lint 依赖。
# 就绪后静默(不刷屏);不碰 GitHub 强制层(那需要权限,且会话内自动设=权限放大,见 deploy-setup skill)。
# 始终 exit 0:就绪检测绝不阻断会话。
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$ROOT" 2>/dev/null || exit 0

msgs=""
# 1) 激活本地门禁钩子(反馈层,契约 01)——core.hooksPath 是 per-repo git config,设一次即可
if [ "$(git config --get core.hooksPath 2>/dev/null)" != ".githooks" ]; then
  git config core.hooksPath .githooks 2>/dev/null && \
    msgs="${msgs}  ✓ 已激活本地门禁钩子(.githooks);提交将自动跑 gate-commit\n"
fi
# 2) 检测 lint 依赖(不自动装——装包侵入性高,提示即可)
if ! python3 -m ruff --version >/dev/null 2>&1; then
  msgs="${msgs}  ⚠ 缺 lint 依赖,跑 \`make install-dev\`(否则 gate-commit 的 lint 步骤报 infra=3)\n"
fi

# 就绪则静默;有事才提示(%b 解释 \n 换行)
[ -n "$msgs" ] && { printf "[harness 自检]\n"; printf "%b" "$msgs"; }
exit 0
