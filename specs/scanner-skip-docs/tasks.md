# scanner-skip-docs · tasks

> refs: plan.md

| # | 任务 | 验收 |
|---|---|---|
| T1 | harness 加 `code_only_diff(diff)`:按 `diff --git` 分块,跳过 _SKIP_SUFFIXES 文件 | spec 验收 1-4 |
| T2 | `judge_diff` 调 gate-judge 前先 code_only_diff 过滤 | 文档 eval 不命中、代码 eval 命中 |
| T3 | tests/test_harness.py 加 4 条:md跳过/py命中/未知后缀仍扫/混合 | make test 绿 |
