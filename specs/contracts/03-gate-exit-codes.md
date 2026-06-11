# 契约 03 · gate 退出码(0/1/2/3)

`python -m aiforge gate-*` 与 `gate-commit` 在**受控路径**下只产生四个退出码:

| 码 | 语义 | 含义 |
|---|---|---|
| 0 | `approved` | 通过,可推进 |
| 1 | `rejected` | 拒绝(含 receipt 链缺失/过期、追溯断裂、src 改动无 feature 声明) |
| 2 | `needs_human` | 转人审;打印人审清单;消费方不得视作通过 |
| 3 | `infra_error` | 基础设施错误:包 import 失败、配置缺失、receipt 不可解析、未预期异常——**绝不能落到 0** |

**外部异常退出码**(SIGINT 130 / SIGKILL 137 / timeout 124 / OOM 等)不在受控路径内——**消费方(pre-commit/CI)遇到 0/1/2/3 之外的任何值一律按 infra_error 处理,不放行**。

## fail-closed 规则

1. 受控路径内任何未预期异常 → 3,并向 stderr 打印可读诊断(出错环节 + 建议动作),不允许裸 traceback 后含混退出;
2. `aiforge` 包 import 失败由**极薄 `__main__.py`** 兜住 → 3(该入口顶层除 stdlib 外零 import,业务模块在 try 内延迟加载);
3. 消费方语义:对 1/2/3(及一切非 0)一律不放行;2 的放行只走契约 07 的人审通道。

## 钉死方式(M1,tests/test_harness.py)

- 统一 result mapper(decision → exit code)单点实现 + 单点测试;
- 每个语义(0/1/2/3)至少一条端到端断言(按各命令自然产生的语义覆盖,不强迫每命令伪造全部四态);
- 一条"破坏性"测试:人为制造坏 receipt/坏配置,断言退出码 = 3 且 stderr 含诊断(改回 fails-open 即红)。
