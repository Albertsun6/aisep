---
name: sdlc-requirements
description: AISEP 管线 requirements 阶段:把原始需求转成 specs/<feature-id>/spec.md 并过 gate-spec。当用户给出新特性需求、说"走管线/起 spec/需求工程"时使用。
---

# sdlc-requirements — 需求 → 冻结 spec

**输入**:原始需求 + feature-id(无则与用户商定,小写 kebab-case)。
**输出**:`specs/<id>/spec.md`(过 gate)+ `specs/<id>/outputs/analyst.json` + `specs/<id>/gates/gate-spec.json`(receipt)。

## 步骤

1. 调用 **analyst** 子代理(`.claude/agents/analyst.md`)产出 spec 草稿与结构化结论;它列出阻断性歧义时,先向用户澄清,再重调;
2. 跑门禁(skill 持有 Bash,analyst 没有):
   ```bash
   PYTHONPATH=src python3 -m aiforge gate-spec specs/<id>/spec.md
   ```
3. **exit 1 → 迭代**:按输出的"缺什么"修 spec,重跑;**不得带病推进**(P1:无冻结 spec 不许进下一阶段);exit 3 → 修基础设施问题后重跑;
4. exit 0 → 把 gate 输出与 receipt 路径贴回会话;spec 自此**冻结**(改动走 specs/contracts/02 变更流程);
5. 停止。下一阶段(architecture)由用户/调用方决定——本 skill 不自动推进(契约 08:定序不进 prompt)。

## 验收自检
- [ ] spec.md 含 Gherkin/EARS 验收结构 + P6 非功能清单
- [ ] gate-spec exit 0,receipt 落在 specs/<id>/gates/
- [ ] analyst.json 落在 specs/<id>/outputs/
