# 契约 10 · 模型配置原则

> 冻结的是**原则**,不是厂商默认值——供应商行为(默认 effort、参数兼容性)是版本相关事实,进 ADR 附验证命令与日期,不当契约。

1. **显式配置**:会话默认 model/effort 在 `.claude/settings.json` 显式声明;每个 `.claude/agents/*.md` 的 `model` 字段显式填写,不依赖"继承当时默认"。
2. **被拒参数 fail-closed**:任何配置参数被 API 拒绝(如向仅支持 adaptive thinking 的模型发送关闭 thinking 的参数 → 400)时,调用方**报错退出**,不静默降级/不静默改参重试。
3. **记录实际模型**:成本台账与异构评审留痕记录**实际应答模型**(可观测来源:API 响应的 model 字段 / `/cost` 输出 / 工具自报);不可观测时记"请求模型 + 来源不可观测",不编造。
4. **厂商行为登记处**:当前已验证条目(验证日期 2026-06-11,来源:官方 API 参考)——
   - Fable 5(`claude-fable-5`):仅 adaptive thinking,显式 `thinking:{type:"disabled"}` 返回 400(应整体省略该参数);API 价 $10/$50 每 MTok;API surface 同 Opus 4.7/4.8。
   - 复验方式:见官方 models/migration 文档或 `client.models.retrieve("claude-fable-5")`。
   - 此清单过期不影响契约 1~3 的效力。
