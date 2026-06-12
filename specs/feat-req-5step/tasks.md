# feat-req-5step — 任务拆解

> refs: plan.md

## 组 1(核心门禁,串行——同文件 harness.py)

- [ ] T1 `_intent_decision` + `gate_intent`(plan §1 intent 判据 + §2;满足 spec 验收 1-4)
- [ ] T2 `_scope_decision` + `gate_scope`(plan §1 discovery 判据;满足 spec 验收 5-8)
- [ ] T3 `_spec_decision` 升级:清零检查(总是)+ trace 链(intent 存在时)(满足 spec 验收 9-10、16)
- [ ] T4 `check_receipt_chain` 扩展 gate-intent 链校验(满足 spec 验收 14-15)

## 组 2(CLI,依赖组 1)

- [ ] T5 `_cmd_gate_intent`/`_cmd_gate_scope` + main() 注册(plan §3;支持 --feature 与路径两种调用)

## 组 3(测试,依赖组 1-2;与组 4 可并行)

- [ ] T6 tests/test_req_5step.py:A 组(验收 1-4)、B 组(验收 5-8)、C 组(验收 9-10)、D 组三档 track(验收 11-13)、E 组链扩展与向后兼容(验收 14-16);全绿 + 存量测试不回归(make test)

## 组 4(建议层产物,独立可并行)

- [ ] T7 重写 .claude/skills/sdlc-requirements/SKILL.md 为 R1-R5 编排(plan §5)
- [ ] T8 docs/flows/stage-requirements.bpmn 入库(to-be 图)

## 组 5(收尾,依赖全部)

- [ ] T9 make lint + make test + gate-judge --staged + gate-commit --feature feat-req-5step;按需修复后提交
