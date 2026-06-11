# 契约 03 · gate 退出码(0/1/2/3)

`python -m aiforge gate-*` 与 `gate-commit` 的退出码语义,**所有消费方(pre-commit / CI / skills / 将来 driver)只认这四个值**:

| 码 | 语义 | 含义 |
|---|---|---|
| 0 | `approved` | 通过,可推进 |
| 1 | `rejected` | 拒绝(含 receipt 链缺失/过期、追溯断裂) |
| 2 | `needs_human` | 转人审;打印人审清单;消费方不得视作通过 |
| 3 | `infra_error` | 基础设施错误:core import 失败、配置缺失、未预期异常——**绝不能落到 0** |

## fail-closed 规则

1. 任何未预期异常 → 3,不允许裸 traceback 后退出码 0/1 含混。
2. `aiforge` 包自身 import 失败也必须非 0(由入口最外层兜住 → 3)。
3. 消费方语义:pre-commit/CI 对 1/2/3 一律不放行(2 的放行走契约 07 的人审通道)。

## 钉死方式(M1 落地,tests/test_harness.py)

- 每个子命令对四种结果各有一条断言;
- 一条"破坏性"测试:人为制造 import 错误/坏配置,断言退出码 = 3(改回 fails-open 即红)。
