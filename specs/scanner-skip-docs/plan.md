# scanner-skip-docs · plan

> refs: spec.md

## 设计
- 落点:`src/aiforge/harness.py`——在喂给 StaticRiskScanner 前,按 diff 的 `diff --git a/<path>` 分块,跳过明确文档/数据后缀的块。
- 不改 `quality/judge.py` 的 StaticRiskScanner(它仍是"给什么扫什么");分流逻辑放调用方 harness,保持核纯净(ADR-004:核不感知 CC/文件类型)。
- fail-closed:`_SKIP_SUFFIXES` 白名单(明确无害的文档/数据),只跳这些;路径解析不出 → 当代码扫。
- 影响面:仅 `judge_diff` 的输入预处理;receipt/退出码语义不变。

## 不做
- 不动 gates.yml(它调 gate-judge,行为透明继承);不动 gate-commit 其它步骤。
