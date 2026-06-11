# 厂商事实登记处(非规范附录)

> **本文件不是契约**。这里登记实现所依赖的供应商行为/价格/日期类事实——每条必须带**验证日期、来源、复验方式**;过期或失效不影响契约 01~10 的效力(契约只写原则)。

| 事实 | 验证日期 | 来源 | 复验方式 | 置信 |
|---|---|---|---|---|
| Fable 5(`claude-fable-5`)仅 adaptive thinking;显式 `thinking:{type:"disabled"}` 返回 400(应整体省略参数) | 2026-06-11 | 官方 API 参考(claude-api skill,缓存 2026-05-26) | `client.models.retrieve("claude-fable-5")` / 官方 migration 文档 | 高 |
| Fable 5 API 价 $10/$50 每 MTok;Opus 4.8 $5/$25 | 2026-06-11 | 同上 | 官方 pricing 页 | 高 |
| Fable 5 API surface 同 Opus 4.7/4.8(sampling params 移除等) | 2026-06-11 | 同上 | 官方 migration 文档 | 高 |
| 2026-06-15 起 `claude -p`/Agent SDK 走单独月度额度(API 价,不滚存),交互模式仍走订阅 | 2026-06-10 | 官方 headless 文档提示框 + 计费支持页(见 ADR-009 链接) | 复查该两页 | 中高 |
| 第三方流传的 credit 细节(额度拆分/滚存/订阅窗口日期) | — | 第三方解读 | **未核验,预算承诺前必须官方确认** | 低 |
| `--bare` 将成为 `claude -p` 默认 | 2026-06-10 | 官方 headless 文档(见 ADR 文档 §1.1) | 复查 headless 文档 | 中高 |
| cursor-agent CLI 非交互为 `-p --mode ask`;不自报可观测模型字段(身份靠自报文本) | 2026-06-11 | 本机实测 | `cursor-agent --help` + 一次试调 | 高(本机) |
