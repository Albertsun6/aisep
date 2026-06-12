# AISEP × Claude Code Harness(STEP 0,有头模式)

@constitution.md
@AGENTS.md

## SDLC 纪律(任何特性必须走管线)

requirements → `gate-spec` → architecture → `gate-trace` → decompose → 实现循环(developer/reviewer/tester)→ `gate-judge`/`gate-commit` → integrate。

- 每阶段产物落 `specs/<feature-id>/`(spec.md / plan.md / tasks.md / outputs/ / gates/),目录契约见 `specs/contracts/08`;
- 阶段切换前必须跑对应 `PYTHONPATH=src python3 -m aiforge gate-*` 并把结果贴回会话;退出码 0=过 / 1=拒 / 2=转人审 / 3=infra(`specs/contracts/03`);
- `src/`、`tests/` 改动提交必须声明 feature(`gate-commit --feature <id>` 或 `AIFORGE_FEATURE=<id>`)——无 spec 的代码改动会被 gate-commit 与 CI 拒绝。

## 长程自主约束(跳阶段 = receipt 缺失 = 被拒)

| 约束 | 机器强制点 |
|---|---|
| 每阶段先落盘产物、跑 gate,再继续 | receipt 链(契约 06):缺/过期 = exit 1;本地是反馈,CI 是权威 |
| receipt 必须由真实命令产生,贴回会话的只是引用 | hash 校验:伪造/过期 = exit 1 |
| spec 过 gate-spec 后冻结 | 改动不重跑 gate = exit 1;CI `gate-spec --check` 复验(契约 06;CODEOWNERS 强制已撤销,契约 01 修订 2026-06-13) |
| judge 缺真异构 → 转人审,不许作者模型自审自过 | CLI 无模型调用通道(契约 04);CI 重跑 gate |
| 本地 `--ack-human` 仅审计 | CI 不消费 ack(契约 07) |
| 本文件其余内容 | **建议层,无机器强制**(契约 01——诚实标注) |

## 角色与技能

- 角色子代理:`.claude/agents/`,按需物化(上限 7);必须满足双宿主规范——file-in/file-out、JSON 落 `specs/<id>/outputs/<role>.json`、**定序逻辑不进 prompt**(契约 08);
- 阶段技能:`.claude/skills/sdlc-*`;每个 gate 怎么跑、结果怎么读,见 `sdlc-gate`。
