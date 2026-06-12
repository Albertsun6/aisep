> **来源**:老库 AISEP/.aisep/docs/self-evolution.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。**L1-L4 自进化 + 规则生命周期是未实现设想**;.metap/triggers.yaml 等实现假设不适用当前 harness。'摩擦与影响面成正比'与契约 05/07 同源。

# AISEP 自进化机制设计

## 设计哲学

AISEP 不是静态工具——它应该**越用越好**。每个项目的 Gate 修正、每次人工反馈都是提升系统质量的原材料。

**参考项目：**
- **OpenClaw** — 自生成代码更新自己
- **小米 MiClaw** — 运行中自动创建新能力模块
- **DeepMind AlphaEvolve** — 提出代码改进 → 测试 → 保留更优方案
- **Mem0** — 分层记忆（语义/情景/用户级）

**AISEP 的关键区别：人在回路（Human-in-the-Loop）。** 系统管理的是工程流程和质量标准，错误的自改会影响所有后续项目，因此进化必须经人审批。

---

## 四层进化架构

```
┌─────────────────────────────────────────────┐
│ L4: 能力自生成（MiClaw 模式）               │
│ 遇到新框架/领域 → AI 自动生成 skill         │
├─────────────────────────────────────────────┤
│ L3: 规则优化（AlphaEvolve 模式）            │
│ 追踪规则有效率 → 生成改进建议 → 人确认       │
├─────────────────────────────────────────────┤
│ L2: 知识沉淀（Mem0 模式）                   │
│ Gate 修正 → 回流到 skills 知识库             │
├─────────────────────────────────────────────┤
│ L1: 经验记忆（Episodic Memory）             │
│ 每次 Gate 的修正记录 → 项目级存储            │
└─────────────────────────────────────────────┘

自动化程度：  L1 全自动  |  L2 半自动  |  L3 人触发  |  L4 人触发
```

---

## 进化植入点分布（v2 · exp-006）

进化不应只在项目结尾（S8）发生。以下是三层植入点在 pipeline 中的分布：

```
Pipeline 阶段:    S0   S1   S2   S3🔸  S4   S5   S6🔸  S7   S8★  /tidy★
                                  │                  │        │     │
                                  │                  │        │     │
Auto 层（无感）:   ←─── Gate 修正模式检测（同类 ≥2 次自动提醒）────→
Nudge 层（轻感）:                 └ 架构经验追问      └ 首Slice质量回顾
Prompt 层（显性）:                                          └ 完整6步复盘  └ interaction-rules更新
```

### 植入点详情

| 层级 | 植入点 | 所在文件 | 触发方式 |
|------|--------|---------|---------|
| **Auto** | Gate 修正模式检测 | `pipeline.md` Step 5.修正流程 | 同类 revision ≥ 2 次自动提醒 |
| **Nudge** | S3 架构经验追问 | `s3-architecture.md` Gate 通过后 #6 | AI 追问一句，可跳过 |
| **Nudge** | S6 首 Slice 质量回顾 | `s6-testing.md` Gate 通过后 #5 | 仅 slice_index == 1 时追问 |
| **Prompt** | S8 复盘 | `s8-retrospective.md` | 完整 6 步流程 |
| **Prompt** | /tidy 收尾 | `tidy.md` Step 9 | interaction-rules 更新 |

### 设计原则

1. **不增加用户负担**：Auto 层完全无感，Nudge 层可跳过
2. **有意义的交付物后反思**：只在 S3（架构决策）和 S6 首 Slice（首次代码质量信号）后植入
3. **频率递增、深度递增**：Auto → Nudge → Prompt，越往后越深入
4. **记录到 observations.yaml**：所有 Nudge 反馈统一记录，供 L2 知识沉淀分析



## L1: 经验记忆（自动）

每个 Gate 通过/修正/拒绝时自动记录，无需人工干预。

```yaml
# projects/{id}/history/gate-log.yaml（自动生成）
gates:
  - stage: s5
    slice: slice-2
    timestamp: "2026-03-15T10:30:00"
    result: revised             # passed | revised | rejected
    corrections:
      - type: code
        file: "models/production_order.py"
        original: "onchange 处理逻辑"
        revised: "write override 处理逻辑"
        user_comment: "onchange 在代码调用时不触发"
        category: framework_pitfall    # 分类标签，供 L2 分析

  - stage: s2
    slice: null
    timestamp: "2026-03-14T09:00:00"
    result: rejected
    reason: "缺少异常流程的 Story"
    category: methodology_gap
```

---

## L2: 知识沉淀协议（半自动）

系统检测**重复修正模式**或**高价值知识条目**时，自动生成沉淀建议。

### 两条沉淀路径

```
路径 A: 修正模式沉淀（被动式）                路径 B: 知识条目晋升（主动式）
──────────────────────                       ──────────────────────
多项目 gate-log 中发现相同 correction         S8 复盘产出 knowledge entry
  ↓ triggers.yaml 触发                        ↓ S8 步骤 4 评估
自动生成 Skill 补丁建议                       评估 readiness 等级
  ↓ 人确认                                     ↓ 达到 L2-ready
写入 skills/ 文件                             生成 Skill 文件到 ~/.aisep/skills/
  ↓ evolution-history 记录                     ↓ 人确认 + evolution-history 记录
```

### 触发条件

```yaml
# .metap/evolution/triggers.yaml
triggers:
  # 路径 A: 修正模式
  - condition: "同一类 correction 出现 >= 2 次（跨项目）"
    action: generate_knowledge_pr
  - condition: "同一 checklist item 连续 5 次 pass"
    action: suggest_strengthen_rule
  - condition: "某 methodology 的 gate_rejection_rate > 30%"
    action: suggest_methodology_revision

  # 路径 B: 知识晋升
  - condition: "knowledge entry 的 readiness 达到 L2-ready"
    action: suggest_skill_promotion
```

### 知识条目 Readiness 评估（路径 B）

S8 复盘时对每个 knowledge entry 评估三个维度：

| 维度 | 权重 | L0-项目级 | L1-跨项目 | L2-全局技能 |
|------|------|----------|----------|-----------|
| **跨项目验证** | 40% | 1 个项目使用 | 2+ 项目验证 | 3+ 项目验证且无负面反馈 |
| **复用频率** | 30% | 单次使用 | 在 S8 评估中被引用 2+ 次 | 成为常规实践 |
| **稳定性** | 30% | 初始提出 | 无修正经历 | 经过 trial 无需调整 |

**Readiness 等级判定**：
- **L0-project**: 初始状态（单项目产出，未经跨项目验证）
- **L1-cross-project**: 2+ 项目验证，可记录在 `knowledge/index.yaml` 的 `by_project` 中
- **L2-ready**: 三维度均达到 L2 标准，**可提议晋升为全局 Skill**

```yaml
# knowledge entry 中追加 readiness 字段（S8 复盘时更新）
# .aisep/knowledge/entries/learn-006.yaml
readiness:
  level: "L1-cross-project"    # L0-project | L1-cross-project | L2-ready
  evaluated_at: "2026-03-13"
  projects_validated: ["proj-001"]
  reuse_count: 1
  stability: "untested"        # untested | stable | needs-revision
  promotion_blocked_by: "仅 1 个项目验证，需 3+ 项目"
```

### 晋升操作步骤（达到 L2-ready 后）

```
1. AI 生成晋升建议：
   ┌──────────────────────────────────────────────┐
   │ 🎓 知识晋升建议                               │
   │                                               │
   │ 条目: learn-006 "TransientModel 向导模式"      │
   │ Readiness: L2-ready                           │
   │ 验证项目: proj-001, proj-003, proj-005         │
   │                                               │
   │ 目标:                                          │
   │   ~/.aisep/skills/frameworks/odoo17/           │
   │     patterns/transient-model.md                │
   │                                               │
   │ 内容预览:                                      │
   │   [从 learn-006 提取，扩展为 Skill 格式]        │
   │                                               │
   │ 确认晋升？ [Y/N]                               │
   └──────────────────────────────────────────────┘

2. 用户确认 → 创建 Skill 文件到 ~/.aisep/skills/（全局层）
3. 更新 knowledge entry: readiness.level = "promoted"
4. 更新 knowledge index: 在 by_tag 中标注 "→ promoted to skill"
5. 记录到 .metap/evolution/evolution-history.yaml:
   - layer: L2
     change: "Promoted learn-006 to skill: frameworks/odoo17/patterns/transient-model.md"
     evidence: ["proj-001", "proj-003", "proj-005"]
     approved_by: user
```

### 沉淀目标目录

```
~/.aisep/skills/                    ← 全局级（L2 沉淀目标）
├── methodologies/                  ← 方法论沉淀
│   └── patterns/                   ← 从实战中提炼的模式
└── frameworks/                     ← 框架知识沉淀
    └── odoo17/
        └── patterns/               ← 从项目中沉淀的模式
            ├── transient-model.md   ← 从 learn-006 晋升
            └── standard-inherit.md  ← 从 learn-XXX 晋升
```

---

## L3: 规则优化（`/evolve` 命令触发）

用户主动触发，AI 对所有规则进行全面评估。

```
/evolve

AI 分析所有项目的 gate-log + rule-metrics：

┌──────────────────────────────────────────────────┐
│ 改进报告                                          │
├──────────────────────────────────────────────────┤
│ 1. [建议强化] business-blueprint checklist        │
│    "异常流程覆盖" — 2 个项目因遗漏返工             │
│    修改：增加 checklist 项                         │
│                                                   │
│ 2. [建议细化] naming convention                   │
│    字段命名修正率 35%                              │
│    修改：从 snake_case 细化为 {entity}_{attr}     │
│                                                   │
│ 3. [建议降级] S6 test-pyramid checklist item #3   │
│    从未触发任何修正，可能是冗余检查                  │
│    修改：标记为 optional                           │
└──────────────────────────────────────────────────┘

是否应用这些改进？[逐条确认]
```

### 有效率追踪

```yaml
# .metap/evolution/rule-metrics.yaml
rules:
  - id: "methodology/business-blueprint/checklist/3"
    rule: "流程链是否连续，没有断裂？"
    applied_count: 8
    triggered_revision: 3        # 因为这条检查导致了返工
    effectiveness: 0.375         # 有效率 = 触发修正/使用次数
    trend: stable

  - id: "convention/naming/field_name"
    rule: "snake_case，业务语义清晰"
    applied_count: 45
    gate_corrections: 16         # Gate 时被用户改了 16 次
    correction_rate: 0.35        # 太高了 → 规则不够具体
    trend: increasing            # 越来越糟 → 急需优化
```

---

## L4: 能力自生成（新 Skill 创建）

遇到系统中不存在的框架或方法论时，AI 自动研究并生成。

```
触发：用户选择了一个未知框架
  ↓
AI 搜索框架官方文档 + 社区最佳实践
  ↓
自动生成 skill 目录：
  .agents/skills/frameworks/{name}/
  ├── SKILL.md
  ├── manifest.yaml
  ├── best-practices.md
  ├── pitfalls.md
  └── templates/
  ↓
用户审阅 → 确认 → 永久保存
```

---

## 规则生命周期

规则不应只增不减。每条规则都有生命周期：

```
draft -> trial -> active -> deprecated -> archived
 提出     试行     正式       弱化        归档
```

### 各阶段定义

| 状态 | 含义 | 进入条件 | 退出条件 |
|------|------|----------|----------|
| **draft** | AI 生成的建议，待人确认 | L2/L3 自动生成 | 用户确认 -> trial |
| **trial** | 试行中，观察效果 | 用户确认 draft | 经过 >= 3 个 Gate 且无负面反馈 -> active |
| **active** | 正式生效 | trial 验证通过 | 触发弱化条件 -> deprecated |
| **deprecated** | 仍存在但标记为待清理 | 连续 6 个月未触发，或环境变化使其失效 | 用户确认归档 -> archived |
| **archived** | 保留历史记录，不再参与评估 | 用户确认 | 终态 |

### Schema 示例

```yaml
# rule-metrics.yaml 中的每条规则
rules:
  - id: "convention/naming/field_name"
    status: active              # draft | trial | active | deprecated | archived
    created: "2026-03-12"
    status_changed: "2026-03-15"
    last_triggered: "2026-04-01"
    trial_gates_passed: 5       # trial 阶段经过的 Gate 数
    deprecation_reason: null     # deprecated 时填写原因
    applied_count: 45
    gate_corrections: 16
    correction_rate: 0.35
```

### 自动提醒

```yaml
# triggers.yaml 中追加
triggers:
  - condition: "active 规则连续 6 个月未触发"
    action: suggest_deprecation
  - condition: "trial 规则经过 >= 3 个 Gate 且无负面反馈"
    action: suggest_promotion_to_active
  - condition: "deprecated 规则超过 3 个月无人处理"
    action: remind_archive_decision
```

---

## 目录结构

```
.metap/evolution/                ← 进化引擎数据│├── interaction-rules.yaml      ← 交互进化规则（从 .aisep/ 迁入）
├── triggers.yaml               ← L2 触发条件配置
├── rule-metrics.yaml           ← L3 规则有效率追踪
├── corrections-log.yaml        ← 跨项目修正汇总（由 L1 gate-log 聚合）
├── evolution-history.yaml      ← 每次进化的记录（审计追踪）
│   entries:
│     - timestamp: "2026-04-01"
│       layer: L2
│       change: "Added P5 to odoo17/pitfalls.md"
│       evidence: [3 projects]
│       approved_by: user
└── pending-suggestions.yaml    ← 待审批的改进建议
```

---

## 安全原则：分层审批

不同层级的变更，审批门槛不同：

| 层级 | 变更对象 | AI 能做 | 审批方式 |
|------|---------|---------|----------|
| **参数层** | 触发阈值、有效率计算参数 | 建议 + 自动写入 | 用户说"好" -> 自动生效 |
| **策略层** | checklist 项、convention、skill 文件 | 建议 | 用户逐条确认 -> 自动写入 |
| **铁律层** | constitution.md 的条目 | 建议 | 用户**手动编辑文件**（不可自动写入） |

**设计原理：摩擦即特性（Friction is a Feature）。** 越重要的变更，人工参与度越高。铁律层要求手动编辑，是为了迫使充分思考，防止轻率批准。

### 不变的底线

```
✅ 可自动做：记录 Gate 结果、统计规则有效率、跨项目聚合修正
✅ 可以建议：对任何层级生成改进方案（包括铁律层）
❌ 不可自动做：修改 skill 文件、删除规则、改变阶段流程
❌ 不可自动做：修改 constitution.md（即使用户口头同意）
❌ 硬门禁：所有系统规则变更必须经人确认，铁律层必须人工编辑
```
