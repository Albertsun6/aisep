# 契约 04 · 计费边界(CLI 永不调模型)

1. **`python -m aiforge` 的任何子命令在任何代码路径下都不发起模型调用**——不 import 任何真实 LLM client、不 subprocess 调 `claude`/`claude -p`/`cursor-agent`/`codex`。`gate-judge` = `StaticRiskScanner` 纯静态三态。
2. LLM 裁决只允许发生在:① 有头交互会话内(订阅计费);② judge skill 显式 shell-out cursor/codex(各厂商独立计费)。
3. 理由:2026-06-15 起无头/Agent SDK 走单独额度按 API 价计费;CLI 被 pre-commit/CI 高频调用,一旦内嵌模型调用,成本与确定性同时失守。

## 钉死方式(M1 落地)

- 静态断言测试:`src/aiforge/harness.py` 与 CLI 入口源码中 grep 不得出现 `claude -p` / `cursor-agent` / `codex` / 真实 LLM client import(白名单:注释与本契约引用);
- 行为断言:在无网络、无任何 API key 的环境变量下,5 个子命令全部正常完成并返回合法退出码。
