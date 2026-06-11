# toy-csv-export · tasks(decompose)

> refs: plan.md

| # | 任务 | 验收 | 并行组 |
|---|---|---|---|
| T1 | `_cmd_demo` 增 `--csv <path>`:导出 kind/produced_by/refs/created_at,UTF-8 带表头;父目录缺失 → stderr+exit 1 | spec 验收 1/2/3 对应断言 | A |
| T2 | `tests/test_demo_csv.py`:happy path / 父目录缺失 / 不传 --csv 不产文件 | `make test` 绿 | A(同文件依赖 T1,串行) |

blast radius:2 文件(cli.py + 新测试文件),< P5 上限,无需再拆。
