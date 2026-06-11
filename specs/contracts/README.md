# specs/contracts/ — 冻结契约(STEP 0 v2 §2.1)

> **冻结的含义**:这 10 条是后续 driver / CI / skills 在其上构建的接口——改了就全链断裂或数据不可比。
> **变更流程**:契约改动必须走 PR + 人审 + 对被改契约重跑一次异构(cursor-agent)评审;紧急情况走 [09-data-safety.md](09-data-safety.md) 的 break-glass 流程。
> **不在此列的一切**(提示词文案、skill 内部步骤、模型精调矩阵等)显式留给迭代,见 v2 方案 §2.2 推迟清单。

| # | 契约 | 一句话 |
|---|---|---|
| 01 | [authority-layers](01-authority-layers.md) | 唯一强制层 = GitHub CI + branch protection;会话内一切不算强制 |
| 02 | [migration-baseline](02-migration-baseline.md) | 基线 tag + 受保护路径 + 契约变更流程 |
| 03 | [gate-exit-codes](03-gate-exit-codes.md) | 0/1/2/3 退出码;fail-closed 用会失败的测试钉死 |
| 04 | [billing-boundary](04-billing-boundary.md) | `python -m aiforge` 任何子命令永不调模型 |
| 05 | [hetero-fail-closed](05-hetero-fail-closed.md) | 缺真异构 → 转人审;评审者模型身份留痕 |
| 06 | [gate-receipt](06-gate-receipt.md) | 每个 gate 落 receipt;gate-commit 校验 receipt 链 |
| 07 | [ack-human](07-ack-human.md) | 本地 ack 仅审计;权威放行 = 人类账号 PR approval |
| 08 | [specs-layout-dual-host](08-specs-layout-dual-host.md) | specs/<id>/ 目录契约 + agent 双宿主规范 |
| 09 | [data-safety](09-data-safety.md) | schema_version / hash 规范化 / redaction / CI 最小权限 / break-glass |
| 10 | [model-config](10-model-config.md) | model/effort 显式配置;被拒参数 fail-closed;记实际模型 |

留痕:本包整体经 cursor-agent 异构评审后生效(评审记录见各文件尾注或 ADR)。
