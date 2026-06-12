# PROPOSAL — 棕地项目的 Gap 分析挂载(R1 后、R2 前)

- 状态:**已裁决方向、暂缓实施**(用户 2026-06-13:绿地优先,本提案记录待加项)
- 来源:用户 Gap 分析思考(2026-06-13 会话)+ TOGAF ADM Gap Analysis Technique + BABOK(Transition Requirements)+ 老库 docs/research/methodology/methodology-layer.md("仅当存在现有系统时激活")
- 关联:specs/feat-req-5step(R1-R5 管线,已实现)、docs/flows/stage-requirements.bpmn(to-be 图)

## 裁决要点(冻结本提案语义,实施时不重辩)

1. **不是每个 feature 都做**:Gap 分析仅在「有现状、要变到目标」时激活。决策表:

   | 条件 | 做不做 |
   |---|---|
   | 纯新建、无遗留(绿地) | 不做——R1 intent 的 problem/成功指标/non-goals 已够 |
   | 有旧系统要替换/对接 | 必做 |
   | 现有代码库小改动(fast track) | 不做 |
   | 现有产品中大型变更 | 轻量版(3~5 项关键能力对比) |
   | 有数据迁移/双轨上线 | 必做,且 Transition 需求单独写 |

2. **阶段位置:R1 intent 人审之后、R2 圈范围之前**(或作 R2 第一节)。太早没 Baseline,太晚(进 architecture)返工。复杂遗留域:Gap 是 Event Storming 的前置输入。

3. **产物形态:不加新文件、不加新 gate**——棕地 feature 在 `discovery.md` 顶部加 `## Baseline/Target/Gap` 一节,一页表格:

   | 能力 | Baseline(现状) | Target(目标) | 判定 | 备注 |
   |---|---|---|---|---|
   | …… | …… | …… | Gap/Overlap/Out/Defer | …… |

   判定四类的去向:**Gap** → R2 in 表候选;**Overlap** → 对接/复用(开发量小);**Out** → R2 out 表(与 intent non-goals 对齐);**Defer** → R4 后续 release。

4. **人审红线:Baseline 必须人确认**——现状只有业务方/运维清楚,这是 AI 最容易胡编的格子(与 R1-R5 的"范围决策人主导"同根)。

5. **与 Transition Requirements 分工**:Gap 答"能力差什么"(R1 后 R2 前);Transition 答"怎么切过去"(迁移/培训/双轨,R3 提问覆盖、R5 写进 spec 或独立 migration 计划)。

## 后期实施清单(届时立 feature 走管线)

- [ ] **intent.md 加可选 `baseline:` 行**(绿地写 `baseline: none`):让绿地/棕地判定本身显式留痕——这也是机器条件触发的开关
- [ ] **gate-scope 条件升级**:`baseline:` 非 none(棕地)时,要求 discovery.md 含 `## Baseline/Target/Gap` 节且每个 Gap 行有判定列;渐进启用(无 baseline 行的存量/绿地 feature 不受影响——模式同 feat-req-5step 的 intent.md 条件触发)
- [ ] **sdlc-requirements skill** 增补 Gap 步骤文案(AI 起草表,人确认 Baseline)
- [ ] **to-be BPMN**:R1→R2 之间插入 Gap 任务 + "棕地?"网关(docs/flows/stage-requirements.bpmn)
- [ ] **Transition 类需求**的 spec 模板段(迁移脚本/双轨/回滚条件)

## 评审备注(主 agent,2026-06-13)

- 方向无异议;一个补充提醒:**"绿地"常有隐性 baseline**(现行手工流程/Excel 就是现状)——`baseline:` 显式行的价值正在于把这个判断从默认变成必答。
- track 映射:fast→不做;standard 绿地→不做;standard 棕地→轻量;epic→必做+Transition 单列。
- 机器校验挂 gate-scope 而非新设 gate-gap:零新增产物与 gate,符合 ② Simplicity First 与"防 markdown 审阅税"。
