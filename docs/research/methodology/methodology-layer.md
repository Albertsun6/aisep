> **来源**:老库 AISEP/.aisep/docs/methodology-layer.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。概念参考(阶段↔方法论映射);其 SKILL.md gating 是另一套体系,非照搬。

# AISEP 方法论层设计

## 概述

方法论层是 AISEP 的**认知协议**——告诉 AI "怎么思考"，而不只是"做什么"和"产出什么"。

```
┌─────────────────────────────────────────────┐
│  阶段定义（Stage）     = WHAT to do          │
│  输出 Schema           = WHAT to produce     │
│  方法论（Methodology） = HOW to think        │  ← 新增
│  Quality Gate          = HOW to verify       │
└─────────────────────────────────────────────┘
```

---

## 目录结构

```
.agents/skills/methodologies/
├── domain/                     ← 领域分析类（3 个）
│   ├── ddd/SKILL.md
│   ├── business-blueprint/SKILL.md
│   └── event-storming/SKILL.md
├── requirements/               ← 需求工程类（4 个）
│   ├── user-story-mapping/SKILL.md
│   ├── invest/SKILL.md
│   ├── moscow/SKILL.md
│   └── given-when-then/SKILL.md
├── architecture/               ← 架构设计类（2 个）
│   ├── c4-model/SKILL.md
│   └── adr/SKILL.md
├── design/                     ← 详细设计类（2 个）
│   ├── solid/SKILL.md
│   └── design-patterns/SKILL.md
├── implementation/             ← 实现类（2 个）
│   ├── clean-code/SKILL.md
│   └── tdd/SKILL.md
├── testing/                    ← 测试类（2 个）
│   ├── test-pyramid/SKILL.md
│   └── bdd/SKILL.md
└── deployment/                 ← 部署类（1 个）
    └── twelve-factor/SKILL.md
```

> 共 16 个方法论 Skill（11 required + 5 optional）。

---

## 方法论文件格式（SKILL.md + Frontmatter Gating）

> [!IMPORTANT]
> 方法论已统一采用 **SKILL.md** 格式（对齐 Antigravity Skills 机制），借鉴 OpenClaw 的 frontmatter gating 条件加载。

### SKILL.md 格式

每个方法论目录包含一个 `SKILL.md` 入口文件，使用 YAML frontmatter 声明元数据和加载条件：

```markdown
<!-- .agents/skills/methodologies/domain/ddd/SKILL.md -->
---
name: ddd
description: "Domain-Driven Design — 领域驱动设计"
category: domain
applicable_stages: [s1, s3, s4]

# 🆕 Gating 条件（借鉴 OpenClaw requires 机制）
# 只有满足条件时才加载到 AI 上下文，避免 token 浪费
requires:
  stage: [s1, s3, s4]        # 仅在这些阶段激活
  # tech_stack: "*"           # 不限技术栈（通用方法论）
  # bins: []                  # 无外部工具依赖

# Gating 选项
always: false                 # true = 跳过条件检查，始终加载
---

## 核心指令（AI 执行时的思考协议）

1. 与用户共同建立 Ubiquitous Language（统一语言）
2. 识别核心域、支撑域、通用域
3. 划分 Bounded Context（限界上下文）
4. 在每个 Context 内识别 Aggregate Root, Entity, Value Object
5. 定义 Context Map — 各 Context 间的关系（ACL, Open Host, Shared Kernel 等）
6. 将 Bounded Context 映射到模块边界

## Gate 审查检查清单

- [ ] 是否识别并文档化了 Ubiquitous Language？
- [ ] 是否划分了 Bounded Context，边界是否清晰？
- [ ] 是否有 Context Map？
- [ ] 每个 Aggregate Root 的不变量是否定义？
- [ ] 模块边界是否与 Context 边界对齐？

## 产出增强

该方法论要求额外输出：

| 阶段 | 字段 | 类型 | 说明 |
|------|------|------|------|
| S1 | `ubiquitous_language` | glossary | 统一语言词汇表 |
| S1 | `context_map` | diagram_spec | 限界上下文映射关系 |

## 参考文献

- Eric Evans — Domain-Driven Design (2003)
- Vaughn Vernon — Implementing DDD (2013)
```

### 框架知识的 Gating 示例

框架知识库的 `SKILL.md` 由 `tech_stack` 字段控制按需加载：

```markdown
<!-- .agents/skills/frameworks/odoo17/SKILL.md -->
---
name: odoo17
description: "Odoo 17 框架知识库"
applicable_stages: [s3, s4, s5, s6, s7]

requires:
  stage: [s3, s4, s5, s6, s7]
  tech_stack: "odoo17"            # 仅在项目 tech_stack 匹配时加载
  bins: ["python3"]               # 需要 Python 3 环境

always: false
---

（框架知识内容...）
```

### Gating 条件速查

| 条件 | 类型 | 说明 |
|------|------|------|
| `stage` | `string[]` | 仅在匹配的 pipeline 阶段加载 |
| `tech_stack` | `string` | 仅在项目 tech_stack 匹配时加载（`"*"` = 不限） |
| `bins` | `string[]` | 要求 PATH 上存在的外部工具 |
| `env` | `string[]` | 要求存在的环境变量（如 API Key） |
| `always` | `bool` | `true` = 跳过所有条件，始终加载 |

### 业务蓝图（基于 SAP ASAP 方法论）

```yaml
# .agents/skills/methodologies/domain/business-blueprint.yaml
methodology:
  id: business-blueprint
  name: "业务蓝图"
  origin: "SAP ASAP Methodology — Business Blueprint Phase + TOGAF ADM"
  category: domain
  applicable_stages: [s1]

  # 核心：不预置具体内容，约束 AI 必须覆盖的维度（meta-template）
  instructions: |
    根据用户描述的行业和业务范围，动态生成该行业的业务蓝图。
    蓝图必须覆盖以下维度（按需展开，不强制全部）：
    
    1. 核心业务流程（End-to-End Processes）
       - 每个流程用 "动词-名词" 格式命名
       - 标注流程间的触发关系和数据流
    2. 主数据（Master Data）
       - 列出所有需要管理的主数据实体
    3. 组织架构（Organizational Structure）
       - 公司、部门、岗位、权限层级
    4. 报表与分析（Reporting）
       - 关键报表和分析维度
    5. 外部集成（Integration Points）
       - 与外部系统的接口需求
    6. 合规与审计（Compliance）
       - 行业特定的合规要求
    7. 业务能力映射（Business Capability Map）— 来自 TOGAF BA
       - 按"能力"而非"功能"组织，以能力树形式呈现
       - 每个能力节点标注：成熟度、优先级、对应的业务流程
       - 用于发现功能视角下容易遗漏的能力项
    8. 现状-目标-差距分析（Baseline/Target/Gap）— 来自 TOGAF ADM
       - 仅当存在现有系统时激活
       - Baseline：现有系统的能力覆盖（如 Excel、旧 ERP、手工流程）
       - Target：目标系统的能力覆盖
       - Gap：需要新建的能力（开发范围）
       - Overlap：现有系统已满足的能力（可对接或迁移）

  checklist:
    - "是否覆盖了至少 3 个端到端业务流程？"
    - "每个流程是否有明确的起点和终点？"
    - "流程链是否连续，没有断裂？"
    - "是否识别了所有主数据实体？"
    - "是否生成了业务能力映射（能力树）？"
    - "如果有现有系统：是否完成了 Baseline/Target/Gap 分析？"

  references:
    - "SAP ASAP Methodology — Business Blueprint Phase"
    - "TOGAF ADM — Business Architecture Phase"
    - "TOGAF ADM — Gap Analysis Technique"
```

---

## 阶段↔方法论映射表

### S1-S2 三层需求控制模型

```
Layer 1: 领域驱动发现（S1）
  DDD + Business Blueprint → 系统化梳理业务流程，不遗漏

Layer 2: 结构化需求编写（S2）
  User Story + INVEST + Given/When/Then → 每个需求可测试可验收

Layer 3: 完整性验证（S2 Gate）
  CRUD Matrix + Process Coverage → 确保无遗漏无断裂
```

### 完整映射表

| 阶段 | Required | Optional | Gate 验证 | 理由 |
|------|----------|----------|----------|------|
| **S0** 项目初始化 | — | — | — | 初始化无需方法论 |
| **S1** 领域分析 | `ddd` + `business-blueprint` | `event-storming` | — | DDD 结构化建模；蓝图驱动 AI 主动提问，不遗漏业务流程 |
| **S2** 需求规格 | `user-story-mapping` + `invest` | `moscow`, `given-when-then` | `crud-matrix` + `process-coverage` | INVEST 保证 Story 质量；GWT 格式化验收标准；Gate 矩阵检查完整性 |
| **S3** 架构设计 | `c4-model` | `adr` | — | C4 提供多层级视图；ADR 记录关键决策 |
| **S4** Slice 设计 | `solid` | `design-patterns` | — | SOLID 保证模块质量 |
| **S5** 代码实现 | `clean-code` | `tdd` | — | Clean Code 保证可读性 |
| **S6** 测试验证 | `test-pyramid` | `bdd` | — | 测试金字塔定分层策略 |
| **S7** 部署配置 | `twelve-factor` | — | — | 12-Factor 云原生标准 |

---

## config.yaml 中的引用方式

```yaml
stages:
  - id: s1
    name: "业务领域分析"
    workflow: ".agents/workflows/s1-domain.md"
    gate: manual
    methodologies:
      required: [ddd, business-blueprint]
      optional: [event-storming]
  - id: s2
    name: "需求规格 + Slice 规划"
    workflow: ".agents/workflows/s2-requirements.md"
    gate: manual
    methodologies:
      required: [user-story-mapping, invest]
      optional: [moscow, given-when-then]
    gate_validators: [crud-matrix, process-coverage]
```

项目级可覆盖：

```yaml
# projects/{id}/project.yaml
methodology_overrides:
  s1:
    required: [event-storming]   # 该项目 S1 改用 Event Storming 主导
    optional: [ddd]
```

---

## Workflow 中的使用机制

每个阶段 workflow（如 `s1-domain.md`）在执行时：

1. 读取该阶段绑定的 `methodologies.required` 列表
2. 加载对应的 `.yaml` 文件
3. 将 `instructions` 注入 AI 的执行提示
4. 执行完成后，用 `checklist` 生成 gate 审查项
5. 将 `artifact_additions` 合并到该阶段的输出 schema

```
Stage Workflow 执行流程：
┌──────────────┐
│ 1. 读取阶段配置 │
│ 2. 加载方法论   │──→ instructions 注入提示
│ 3. 执行分析     │
│ 4. 生成制品     │──→ artifact_additions 合并
│ 5. Gate 检查    │──→ checklist 生成审查项
└──────────────┘
```
