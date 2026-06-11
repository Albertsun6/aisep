# 契约 04 · 计费边界(CLI 永不调模型)

1. **`python -m aiforge` 的任何子命令在任何代码路径下都不发起模型调用**——不 import 任何真实 LLM client(anthropic/openai 等 SDK 或其 HTTP 等价物)、不 subprocess 调 `claude`/`claude -p`/`cursor-agent`/`codex`。`gate-judge` = `StaticRiskScanner` 纯静态三态。
2. LLM 裁决只允许发生在:① 有头交互会话内;② judge skill 显式 shell-out cursor/codex(各厂商独立计费)。计费背景见 ADR-009(日期/额度类事实在 `vendor-facts.md`,不构成本契约依据)。
3. 核心理由(与计费无关也成立):CLI 被 pre-commit/CI 高频调用,内嵌模型调用会同时失去确定性、离线可用性与成本可控性。

## 钉死方式(M1;诚实边界:三层互补,均不单独完备)

- **静态 token 检查**(范围 = `harness.py`、`cli.py`、`__main__.py` 源码):不得出现 `claude -p`/`cursor-agent`/`codex`/`anthropic`/`openai` token(测试 fixture 与契约文本不在扫描范围);
- **行为测试**:无网络、清空相关 API key 环境变量下,5 个子命令全部正常完成并返回合法退出码(只证常见路径,承认不证明任何路径);
- **依赖审计**:aiforge 运行期保持零第三方依赖(stdlib only)——LLM SDK 进不了 import 闭包,这是结构性边界。
