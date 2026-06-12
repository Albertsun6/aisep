# 老库 AISEP 系列方法论资产整合索引(2026-06-12)

> 本项目(AISEP)由 5 个早期 AISEP 系列仓演进而来。2026-06-12 收编合并:那 5 个旧仓的**代码/Odoo 业务/运行时引擎**(约 80%)因与本项目"纯标准库 + 规格驱动 + 机器强制 gate"的纪律冲突而**未整合**(全历史镜像备份在 `~/Desktop/aisep-legacy-backup-2026-06-12/`,旧仓已删);此处沉淀的是与该纪律**正交**、当前项目确实空白的**方法论/治理/踩坑知识**。每份文档顶部带 provenance banner,诚实标注来源与现行适用性(契约 01)。

## 来源仓与处置

| 旧仓 | 性质 | 整合 | 备份 |
|---|---|---|---|
| AISEP(37MB) | 概念祖先(MetaP 自进化/S0-S8/本体论) | 8 份方法论+知识+2 调研报告 | 镜像 |
| AISEP416(1.6MB) | DDD 架构文档 + LangGraph 运行代码 | 自治矩阵 / ADR 模板 / ADR 生命周期 / 需求方法论 | 镜像 |
| vessel-aisep(645KB) | TS 栈祖先 | 全局记忆本体论 / 12 篇实战复盘 / 方法论 DAG / 架构阶段规范 | 镜像 |
| new_AISEP(28MB) | Odoo ERP 生成器 | AI 上下文工程标准 | 镜像 |
| AISEPHarness(664KB) | 早期分叉(Antigravity/真 LLM) | **0(整仓无增益)** | 镜像 |

## 整合内容地图

### docs/research/methodology/ —— 上下文工程 + 方法论(10 份)
- **context-loading-protocol.md** ⭐ L0/L1/L2 三层上下文预算 + 8 大机制(当前最大空白)
- **memory-architecture.md** 短/中/长期记忆引擎(配套上一篇)
- **ai-context-standard.md** token 冷热分级(HOT/WARM/COLD)
- **self-evolution.md** 四层自进化路线图(标注:**未实现设想**)
- **deliberation-guards.md** 辩论反模式守护(虚假共识/无源标注/立场锁定)→ 补强原则⑤
- **vertical-slice-evaluation.md** 切片粒度判据(300-800 行=一次可演示)→ decompose 参考
- **methodology-layer.md** 阶段↔方法论映射(DDD/INVEST/C4/test-pyramid)
- **global-memory-ontology.md** 跨项目记忆本体论(~/.aisep 四区)
- **vessel-methodology-v0.1.md** / **vessel-architecture-stage-spec.md** 10 阶段 DAG + 架构阶段 7 问锚点

### docs/research/governance/ —— 治理(2 份)
- **agent-autonomy-matrix.md** ⭐ 把 P4/P5 落成 L0-L6 风险×阶段自治矩阵 + 6 条 never-cross 硬规则
- **adr-lifecycle.md** ADR 生命周期(Accepted 后冻结,与本项目 spec 冻结同构)

### docs/research/domain-knowledge/ —— 领域专属参考(2 份)
- **odoo17-pitfalls.md** 29 条 Odoo 实战踩坑(仅未来做 Odoo 特性时取用)
- **requirements-engineering-methodology.md** 需求工程方法论(粒度/变更管理)

### docs/research/legacy-reports/ —— 调研报告原档(2 份)
- **ontology-architecture/** Palantir Foundry 本体论三要素
- **ai-reverse-engineering/** AI 逆向工程行业三路线(未来 onboard 能力底料)

### docs/research/retrospectives/ —— 实战复盘踩坑(14 份)
- vessel 12 篇 pilot(prompt-only fix / mock-era timeout 等真实坑)
- auction-worked-example(receipt 链 + 量化学习曲线具象化)

### docs/research/governance/ADR-template.md —— 补当前缺的 ADR 骨架(未放 specs/templates 因门禁把 specs/<dir> 当特性)

### docs/decisions/proposals/PROPOSAL-constitution-P10-P12.md —— 宪法追加提案(待裁决,未写入)

## 为什么旧代码没整合(诚实说明)
旧仓的引擎(.metap)、流水线(S0-S8)、产物 schema、Odoo 业务代码、LangGraph agents、TS packages —— 这些是"在 prompt 里写运行时逻辑"或"绑特定框架/领域"的实现,与本项目刻意用**机器强制 gate CLI 替换掉的旧架构**正相反;倒进来会违反 P1(无 spec 的代码被门禁拒)与契约 08。它们的**价值已被上面的方法论文档提炼**;原始实现完整保存在备份镜像里,需要时可查。
