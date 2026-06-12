---
name: sdlc-requirements
description: AISEP 管线 requirements 阶段:R1-R5 五步渐进细化——从任意形态的原始输入(一句话/会议纪要/BRD)到冻结 spec,AI 当放大器、人当范围决策者。当用户给出新特性需求、说"走管线/起 spec/需求工程"时使用。
---

# sdlc-requirements — R1-R5 渐进细化 → 冻结 spec

**输入**:任意形态的原始输入(一句话/业务会议纪要/BRD 草稿/聊天记录)+ feature-id(无则与用户商定,小写 kebab-case)。
**输出**(track=standard 全量):`specs/<id>/intent.md`、`discovery.md`、`clarifications.md`、`scope.md`、`spec.md` + 对应 receipt(gate-intent / gate-scope / gate-spec)。

> 设计依据:《需求工程化细化全流程》调研(57 源,异构终审收敛;spec: specs/feat-req-5step)。核心判据:范围决策与价值判断是 LLM 实证最弱、臆想后果最重的环节(LLM 访谈仅能引出 <50% 隐性需求),必须人主导;AI 在萃取/生成候选/系统提问/算分环节当放大器。

## R1 意图简报(人主写,AI 萃取+提问,不代填业务判断)

1. 原始输入若是会议纪要/长材料:先萃取要点/分歧/未决问题,贴给用户;
2. 引导用户写/改定 `specs/<id>/intent.md`(≤1 页,页数为建议层):
   - `track: fast|standard|epic` 行(人定 appetite:fast=微变更如"调整页面位置";standard=单特性;epic=史诗级如"做个 ERP");
   - 必填节 `## problem` / `## users` / `## 成功指标` / `## non-goals` / `## appetite`(机器校验);
   - `source:` 行记原始材料出处(建议层);
3. 用户逐字确认后跑:`PYTHONPATH=src python3 -m aiforge gate-intent --feature <id>`(0/1/3,语义见 sdlc-gate)。

**track=fast** → 跳到 R5(短路径留痕:intent 里的 `track: fast` 即审计痕)。

## R2 发现与范围地图(AI 生成,人执刀)

> 棕地项目(有遗留系统要替换/对接/迁移):R1 后先做轻量 Gap 分析,表格放 discovery.md 顶部 `## Baseline/Target/Gap` 节,**Baseline 必须人确认**(AI 最易胡编现状);绿地不做。详见 docs/decisions/proposals/PROPOSAL-gap-analysis-brownfield.md(机器校验待加,当前建议层)。

1. 基于 intent 生成 `specs/<id>/discovery.md`:`## in` 与 `## out` 两节(bullet 或表格),候选功能挂假设;
2. **人圈范围**:用户勾选/删改,确认 in/out 两张表——每个 in 项行内须含 `refs: intent...`(挂回意图),out 表不许空(没有显式排除 = 没做范围决策);
3. 跑 `PYTHONPATH=src python3 -m aiforge gate-scope --feature <id>`。

**track=epic** 且范围 > 单 feature → 按 release 切片拆 N 个子 feature(人定序),原 intent 升格为 program vision,每个子 feature 以自己的 feature-id **回流本 skill**(子 intent `refs` 父 vision);本 skill 对当前 id 到此停止。

## R3 覆盖式澄清(AI 提问,人作答)

按维度矩阵(角色与权限/数据生命周期/业务规则/边界与异常/NFR/集成点)生成问题清单,落 `specs/<id>/clarifications.md`(append-only Q&A);逐题问用户,答案回填;红卡清零或显式 defer。spec 残留裸 `[NEEDS CLARIFICATION` 标记会被 gate-spec 拒(代码格式内的提及不算)。

## R4 优先级与首版切片(AI 算分,人改定)

对 in 表预填 MoSCoW(Must ≤60% effort 红线)或 RICE 分,**用户改定**;walking skeleton 切首版,落 `specs/<id>/scope.md`(≤1 页,建议层)。无独立 gate(人决策环节)。

## R5 spec 起草与冻结(analyst 在 R1-R4 约束下起草)

1. 调用 **analyst** 子代理(`.claude/agents/analyst.md`)产出 spec 草稿与结构化结论;它列出阻断性歧义时,先向用户澄清,再重调;spec 每条需求带可测验收(Gherkin/EARS)且含 `> refs: scope.md`(fast track 用 `> refs: intent.md`)trace 行;
2. 跑门禁(skill 持有 Bash,analyst 没有):
   ```bash
   PYTHONPATH=src python3 -m aiforge gate-spec specs/<id>/spec.md
   ```
3. **exit 1 → 迭代**:按输出的"缺什么"修 spec,重跑;**不得带病推进**(P1:无冻结 spec 不许进下一阶段);exit 3 → 修基础设施问题后重跑;
4. exit 0 → 把 gate 输出与 receipt 路径贴回会话;spec 自此**冻结**(改动走 specs/contracts/02 变更流程);
5. 停止。下一阶段(architecture)由用户/调用方决定——本 skill 不自动推进(契约 08:定序不进 prompt)。

## 纪律

- 每个 gate 结果原样贴回会话,不复述软化;receipt 不许手写(hash 校验会拒);
- R1 的业务判断、R2 的圈范围、R4 的优先级:**只能问用户,不许代答**;
- 产物页数预算(intent/scope ≤1 页、discovery 表格化)是建议层,超了提醒用户拆分。

## 验收自检
- [ ] intent.md 必填节齐 + track 合法,gate-intent receipt 落盘
- [ ] (standard/epic)discovery.md in/out 两表,gate-scope receipt 落盘
- [ ] spec.md 含 Gherkin/EARS 验收 + P6 非功能清单、无裸 NEEDS CLARIFICATION 残留、带 trace 行,gate-spec exit 0
- [ ] analyst.json 落在 specs/<id>/outputs/
