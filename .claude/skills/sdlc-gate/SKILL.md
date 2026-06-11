---
name: sdlc-gate
description: AISEP 门禁使用说明书:当前阶段该跑哪个 gate、命令怎么写、退出码怎么读、卡住怎么办。其他 sdlc-* skill 引用本文;用户问"怎么跑门禁/gate 是什么意思"时使用。
---

# sdlc-gate — 门禁怎么跑

## 阶段 → 命令对照

| 阶段完成时 | 命令 | 过 = 0 |
|---|---|---|
| requirements | `PYTHONPATH=src python3 -m aiforge gate-spec specs/<id>/spec.md` | spec 有验收结构 |
| architecture/decompose | `PYTHONPATH=src python3 -m aiforge gate-trace specs/<id>` | 文档链 refs 解析(plan→spec,tasks→plan) |
| 实现中(任意时点) | `PYTHONPATH=src python3 -m aiforge gate-judge --staged` | 静态风险扫描无命中 |
| 提交前(聚合) | `PYTHONPATH=src python3 -m aiforge gate-commit --feature <id>` | 声明制+receipt 链+lint+judge 全过 |
| session 收尾 | `PYTHONPATH=src python3 -m aiforge review-3f --staged` | (信息性,打印三文件 review 必读清单) |

## 退出码(specs/contracts/03)

- **0 approved** — 推进;**1 rejected** — 按输出修内容后重跑,不许绕;
- **2 needs_human** — 转人审。本地放行:人(且只有人)在 tty 里跑 `gate-commit --ack-human`(仅审计);**权威放行 = GitHub 人类账号 PR approval,CI 永远重跑 gate**;
- **3 infra_error** — 基础设施问题(看 stderr 诊断:装依赖/修 receipt/重跑 gate),修好再来。

## 纪律

- 结果(命令+退出码+关键输出)**原样贴回会话**,不复述软化;
- receipt 由命令真实产生(specs/<id>/gates/),**不许手写/补写** receipt——hash 不符会被 gate-commit/CI 当伪造拒掉;
- **异构评审缺席时**(cursor-agent/codex 均不可用):明示"异构缺席,转人审",绝不用作者模型自评顶替(specs/contracts/05)。
