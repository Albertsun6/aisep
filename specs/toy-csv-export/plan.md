# toy-csv-export · plan(PA)

> refs: spec.md

## 设计决策

- **落点 = cli 表现层**(`src/aiforge/cli.py` 的 `_cmd_demo`):导出是展示关切,不进核心层;`orchestration/state.py` 与门禁零改动(③ Surgical)。
- **数据源** = `state.artifacts`(已有结构:kind/produced_by/refs/created_at),无新抽象。
- **错误处理**(spec 验收 2):父目录不存在 → stderr 可读错误 + return 1,不静默吞错;不自动建目录(避免把 typo 路径变成真目录)。
- **无 `--csv` 时零行为变化**(spec 验收 3):导出代码包在 `if args.csv:` 内,demo 原路径不动。
- 分层红线自查:cli 已依赖 orchestration.state,无新增反向边,`.importlinter` 两契约不受影响。

## 不做

- 不做 xlsx;不导出 artifact 内容;不加配置项(② Simplicity)。
