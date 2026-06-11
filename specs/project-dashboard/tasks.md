# project-dashboard · tasks(decompose)

> refs: plan.md

| # | 任务 | 验收 | 并行 |
|---|---|---|---|
| T1 | `collect_state`:只读采集 features/audit/contracts/git/counts,缺失优雅降级 | spec 验收 2/3,降级不崩 | A |
| T2 | `render_html`:单页 HTML,所有动态内容 html.escape;内嵌架构/管线 Mermaid | spec 验收 1/5(转义) | A(依赖 T1 的 state 形状) |
| T3 | `write_project_dashboard` + cli `project-dashboard` 子命令(lazy import) | `python -m aiforge project-dashboard` 出 HTML | A |
| T4 | tests/test_project_dashboard.py:生成成功/特性计数/审计降级/HTML 转义防注入/幂等 | make test 绿 | A |

blast radius:1 新模块 + cli 一处 + 1 测试文件,< P5 上限。
