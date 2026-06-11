# gate-audit-log · tasks(decompose)

> refs: plan.md

| # | 任务 | 验收 | 并行 |
|---|---|---|---|
| T1 | `_append_audit(receipt, repo_root)`:fail-open append receipt 子集到 .aiforge/audit/gates.jsonl | spec 验收 1/3/4 | A |
| T2 | `write_receipt` 末尾调 `_append_audit` | 任一 gate 跑完审计文件多一行 | A(同文件依赖 T1) |
| T3 | tests/test_harness.py +4:追加一行/多次不覆盖/目录自动建/写失败 fail-open | make test 绿 | A |

blast radius:1 src 文件 + 1 测试文件,< P5 上限,无需再拆。
