> **来源**:老库 AISEP(2026-03)/.aisep/docs/context-loading-protocol.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。文中 AISEP.md/project.yaml 等为老库目录名,概念(L0/L1/L2 上下文预算)可迁移。

# AISEP 上下文加载协议

> 第 10 份设计文档 — 横切面（cross-cutting concern），控制每次 AI 交互时的上下文预算。

## 设计哲学

**Context Engineering ≠ Prompt Engineering。** Prompt Engineering 关注"怎么措辞"，Context Engineering 关注"给 AI 看什么"。

AISEP 管理的是一个**随项目增长而膨胀**的结构化知识库——如果不显式控制加载策略，到 S6 第 4 个 Slice 时上下文会不可管理。

### 核心原则（来自行业最佳实践）

| 原则 | 来源 | AISEP 映射 |
|------|------|----------|
| **Just-in-Time Retrieval** | Anthropic | 不预加载所有制品，需要时再取 |
| **Compaction** | Anthropic / Claude Code | 前阶段制品自动摘要化 |
| **Progressive Disclosure** | 渐进披露 KI | L1 索引→L2 模块→L3 细节 |
| **Agentic Memory** | Anthropic | 跨阶段的结构化笔记（gate-log 摘要） |
| **Stage-Scoped Loading** | 12-Factor Agent | Workflow 声明上下文清单 |
| **Context Editing** | Claude Sonnet | 超阈值时自动清理旧工具调用 |

---

## 三层加载模型

```
┌──────────────────────────────────────────────────────┐
│  L0: 常驻层 — 每次交互都加载                          │
│  Token 预算：< 2K tokens（~6KB）                     │
│                                                      │
│  • AISEP.md（导航 + 当前项目指针）                      │
│  • constitution.md（全局铁律）                         │
│  • glossary.yaml（术语表，保证术语一致性）               │
│  • project.yaml 的 pipeline_state 字段（仅状态）       │
├──────────────────────────────────────────────────────┤
│  L1: 阶段层 — 由当前 stage + Workflow 声明决定         │
│  Token 预算：< 5K tokens（~15KB）                    │
│                                                      │
│  • 当前阶段 Workflow（s{n}-xxx.md）                    │
│  • 当前阶段绑定的 Skills（经 Gating 过滤后）            │
│  • 当前阶段的输入制品（上一阶段的输出）                  │
│  • 当前 Slice/Change 的 design.yaml                   │
│  • 适用的 conventions                                 │
├──────────────────────────────────────────────────────┤
│  L2: 按需层 — AI 主动请求或 Workflow 声明时加载         │
│  Token 预算：单次请求 < 3K tokens（~10KB）             │
│                                                      │
│  • 历史制品（已完成阶段的摘要版或完整版）                │
│  • gate-log（滑动窗口 or 摘要）                        │
│  • 其他 Slice/Change 的 design.yaml                   │
│  • Skills 的 references/ 补充文档                     │
│  • framework 的 api-reference.md                      │
└──────────────────────────────────────────────────────┘

总预算目标：常态 < 10K tokens，峰值 < 15K tokens
```

---

## 机制一：Workflow 上下文声明

每个阶段 Workflow 在 frontmatter 中显式声明需要什么上下文。**Pipeline 运行器**根据声明精确加载。

```yaml
# .agents/workflows/s4-design.md frontmatter
---
name: s4-slice-design
context:
  # 始终加载（追加到 L0 常驻层之上）
  always:
    - "artifacts/global/architecture.yaml"
    - "artifacts/global/slice-plan.yaml"

  # 当前 Slice 上下文
  current_slice:
    - "slices/{current-slice}/design.yaml"

  # 只加载摘要版（自动触发摘要生成）
  load_summary:
    - "artifacts/global/domain-model.yaml"
    - "artifacts/global/functional.yaml"

  # 显式排除（防止意外加载）
  exclude:
    - "history/**"
    - "slices/{other-slices}/**"
    - "changes/**"
---
```

**解析规则**：
- `always` → 完整内容加入 L1
- `current_slice` → `{current-slice}` 由 pipeline 运行器替换为当前 Slice ID
- `load_summary` → 检查是否存在 `.summary.yaml`，无则自动生成
- `exclude` → glob 匹配，即使 AI 请求也拒绝加载

---

## 机制二：制品自动摘要化（Compaction）

### 触发时机

Gate 通过时，系统自动为当前阶段的输出制品生成摘要版：

```
Gate passed (S1)
  ↓
domain-model.yaml（8KB 完整版）
  ↓ 自动生成
domain-model.summary.yaml（< 1KB 摘要版）
```

### 摘要规则

| 制品类型 | 摘要保留 | 摘要省略 |
|----------|---------|---------|
| `domain-model.yaml` | Context 数量、Aggregate 列表、关键决策 | 字段详情、Value Objects、业务规则细节 |
| `functional.yaml` | Story 数量、每模块覆盖度、MoSCoW 分布 | 具体验收标准、详细描述 |
| `architecture.yaml` | 模块依赖图、数据模型概要、安全模型类型 | 字段定义、完整 View 设计 |
| `slice-plan.yaml` | Slice 列表 + 状态 + 依赖关系 | 详细 scope 描述 |

### 摘要文件格式

```yaml
# artifacts/global/domain-model.summary.yaml（自动生成，不可手工编辑）
_meta:
  source: "artifacts/global/domain-model.yaml"
  generated_at: "2026-03-15T10:30:00"
  full_size_kb: 8.2
  summary_size_kb: 0.8

summary:
  bounded_contexts: 3
  aggregates: ["BOM", "ProductionOrder", "QualityCheck", "StockReceipt", ...]
  total_entities: 15
  total_value_objects: 8
  key_decisions:
    - "BOM 和 ProductionOrder 属于不同 Bounded Context"
    - "质检流程跨 Production 和 Quality Context"
    - "仓储使用标准 stock 模块继承扩展"
  cross_context_relationships:
    - "Production → Quality: ACL 模式"
    - "Production → Stock: Open Host Service"
```

---

## 机制三：gate-log 滑动窗口

```yaml
# .aisep/config.yaml
context:
  gate_log:
    recent_entries: 5              # 完整展示最近 5 条
    older_entries: summary_only    # 更早的只展示统计摘要
    max_loaded_entries: 10         # 最多加载 10 条
```

加载行为：

```
gate_log 有 23 条记录时，AI 看到的是：

统计摘要：共 23 次 Gate（18 通过 / 3 修正 / 2 拒绝）
高频修正类别：framework_pitfall (5次), methodology_gap (2次)

最近 5 条完整记录：
  #23: S5/slice-3 — passed
  #22: S5/slice-3 — revised (onchange → write override)
  #21: S4/slice-3 — passed
  #20: S6/slice-2 — passed
  #19: S5/slice-2 — revised (missing index on M2O)
```

---

## 机制四：渐进披露与懒加载

### Skills 的三层渐进披露

```
Boot 时加载（L1 Metadata）:
  "ddd: Domain-Driven Design — 领域分析方法论"           ← ~30 tokens
  "odoo17: Odoo 17 框架知识库"                          ← ~20 tokens

Gating 通过后加载（L2 Core Body）:
  ddd/SKILL.md 完整内容                                 ← ~500 tokens

AI 显式请求时加载（L3 References）:
  ddd/references/bounded-context-patterns.md            ← 按需
  odoo17/api-reference.md                               ← 按需
```

### 制品的渐进披露

```
Boot 时加载（L0 常驻层）:
  project.yaml 的 pipeline_state                        ← ~50 tokens

阶段进入时加载（L1 阶段层）:
  上一阶段输出的 summary 版                              ← ~300 tokens

AI 需要细节时加载（L2 按需层）:
  上一阶段输出的完整版                                    ← ~2000 tokens
```

---

## 机制五：capabilities.md 动态生成

`capabilities.md` 不是静态文件——由 Pipeline 运行器在每次交互前根据当前状态动态生成：

```yaml
# capabilities.md 生成逻辑
inputs:
  - current_stage               # 决定可用命令
  - loaded_skills               # 经 Gating 过滤后的 Skills 列表
  - active_project              # 当前项目的基本信息
  - context_budget_remaining    # 剩余 token 预算

output:
  - available_commands           # 当前阶段可用的命令
  - loaded_skills_summary        # 已加载 Skills 的名称 + 一行描述
  - context_usage                # "已用 8.2K / 15K tokens"
```

---

## 机制六：会话上下文审计与交接（Context Audit & Handoff）

### 审计闭环

```
会话进行中         /tidy 触发时            新会话开始
─────────         ──────────            ──────────
AI 读取/搜索文件   → 回顾 tool calls       → 读取 _next_session.yaml
                  → 生成 _context_audit    → 展示推荐文件列表
                  → 评估话题偏移           → 用户确认后加载
                  → 生成 _next_session     → 开始工作
                         │
                         ↓
              evolution/ 长期积累
              → S8 复盘时统计分析
              → 优化 Workflow context 声明
```

### 产出文件

| 文件 | 位置 | 生命周期 |
|------|------|----------|
| `_context_audit.yaml` | `projects/{id}/` | 追加式，保留最近 10 条 |
| `_next_session.yaml` | `projects/{id}/` | 覆盖式，新对话消费后保留作为历史参考 |

### 进化路径

```
次数    行为模式                        对应上下文控制等级
────    ──────                          ──────────────
1-2     推荐式（AI 推荐 + 用户确认）      Level 2
3+      自主式（基于审计历史自动加载）      伪 Level 3
S8      进化审计（统计分析 + 人确认后调整） 系统进化
```

---

## 上下文预算一览

| 阶段 | L0 常驻 | L1 阶段 | 预计总量 | 备注 |
|------|---------|---------|---------|------|
| S0 | ~2K | ~1K | **~3K** | 最轻，只需 project 初始化 |
| S1 | ~2K | ~3K | **~5K** | 加载 DDD + Blueprint Skills |
| S2 | ~2K | ~4K | **~6K** | 加载 S1 摘要 + Story/INVEST Skills |
| S3 | ~2K | ~5K | **~7K** | 加载 S1+S2 摘要 + 框架知识 |
| S4 (Slice N) | ~2K | ~5K | **~7K** | 加载架构 + 当前 Slice 定义 |
| S5 (Slice N) | ~2K | ~5K | **~7K** | 加载 S4 设计 + 代码模板 |
| S6 (Slice N) | ~2K | ~4K | **~6K** | 加载代码 + 测试模板 |
| S7 | ~2K | ~4K | **~6K** | 加载部署配置模板 |

**关键观察**：由于 Compaction + Stage-Scoped Loading，**上下文预算不会随项目增大而线性增长**——只有 L2 按需层的"可选加载量"会增加，但单次交互的 token 消耗保持在 **7-10K tokens** 范围内。

---

## 机制七：项目上下文围栏（Context Fence）

### 设计原理

多项目场景下，AI 可能意外加载非活跃项目的制品（例如搜索时匹配到归档项目的文件）。Context Fence 通过**显式排除规则**（Negative Prompting）解决这一问题——告诉 AI "不要看什么"比"要看什么"更可靠。

### 声明位置

`AISEP.md` 中的 `context_fence` 区块（L0 常驻层）：

```yaml
context_fence:
  active: "proj-042"
  excluded_dirs:
    - "projects/proj-001/**"     # 已归档
    - "projects/proj-002/**"     # 暂停中
  cross_project_allowed:
    - ".aisep/knowledge/**"      # 认知知识库始终可访问
    - ".metap/evolution/**"      # 进化数据始终可访问
    - ".aisep/docs/**"           # 系统文档始终可访问
```

### 解析规则

| 规则 | 行为 |
|------|------|
| `excluded_dirs` 匹配 | **硬排除**——即使 AI 主动请求也拒绝加载 |
| `cross_project_allowed` 匹配 | **白名单例外**——即使在 excluded 范围也可加载 |
| 未匹配任何规则 | 正常加载（遵循三层预算） |

### 自动维护触发点

| 触发事件 | 行为 |
|----------|------|
| `/project switch <id>` | 旧项目加入 `excluded_dirs`，新项目移出 |
| `/project archive <id>` | 永久加入 `excluded_dirs`，添加注释标注 `# 已归档` |
| 手动编辑 | 允许，用于暂停/恢复项目 |

### 与三层模型的关系

```
L0 常驻层加载 AISEP.md
  ↓ 解析 context_fence
  ↓ 过滤 excluded_dirs
L1 阶段层只在 active 项目范围内加载
L2 按需层同样受 fence 约束（cross_project_allowed 除外）
```

---

## 机制八：阶段与 Slice 过渡归档（Stage/Slice Transition Archival）

### 设计原理

随着项目推进，上下文的"热区"不断前移——S1 产出的领域模型在 S5 时很少被直接查阅，但偶尔需要回溯。归档机制确保**已完成的上下文被压缩但可回溯**，而非简单丢弃或全量保留。

这是 Compaction（机制二）的**编排层**——Compaction 定义"怎么压缩"，归档协议定义"什么时候触发、在谁身上触发、触发后做什么"。

### 两种过渡场景

#### 场景一：大阶段过渡（Stage Transition）

| 过渡 | 触发条件 | 归档动作 |
|------|----------|---------|
| S0→S1 | S0 Gate 通过 | `project.yaml` 摘要化（保留 pipeline_state） |
| S1→S2 | S1 Gate 通过 | `domain-model.yaml` → `.summary.yaml` |
| S2→S3 | S2 Gate 通过 | `functional.yaml` → `.summary.yaml` |
| S3→S4 | S3 Gate 通过 | `architecture.yaml` → `.summary.yaml`，**加载框架 Skill** |
| S4-S6→S7 | 所有 Slice 完成 | 所有 Slice 的 `.summary.yaml` 已存在 |
| S7→S8 | S7 Gate 通过 | `deployment.yaml` → `.summary.yaml` |

**归档动作标准清单**（每次 Gate 通过时执行，对应 pipeline.md 步骤 5）：

```
Gate 通过 → 步骤 5a: 状态更新
         → 步骤 5b: Compaction（生成 .summary.yaml）     ← 归档核心
         → 步骤 5c: Gate 日志写入
         → 步骤 5d: 推进到下一阶段
         → 步骤 5e: _map.yaml 更新                        ← 归档索引同步
```

#### 场景二：Slice 过渡（Slice Transition）

发生在 S4-S6 循环中，一个 Slice 完成后切换到下一个：

```
Slice N 完成（S6 Gate 通过）
  │
  ├─ 1. Compaction: 生成 slices/slice-N/ 下所有制品的 .summary.yaml
  │     • design.yaml → design.summary.yaml
  │     • code/ → 保留（代码不摘要化，但不加载到 L1）
  │     • tests/ → 保留（同上）
  │
  ├─ 2. 上下文卸载: 从 L1 阶段层中移除 Slice N 的完整制品
  │
  ├─ 3. _map.yaml 同步: 更新 slices.items[N].status = completed
  │
  ├─ 4. 上下文加载: 将 Slice N+1 的完整制品加载到 L1
  │     • 新 Slice 的 design.yaml（如已有前次 S4 产出）
  │     • 历史 Slice 仅通过 .summary.yaml 可访问（L2 按需）
  │
  └─ 5. 进度展示: 更新 Slice 进度条
```

### 归档后的访问策略

| 制品状态 | L1 可见性 | L2 可见性 | 完整版访问 |
|----------|----------|----------|-----------|
| 当前 Slice 制品 | ✅ 完整加载 | — | — |
| 已完成 Slice 制品 | ❌ | ✅ 摘要版 | AI 显式请求时 |
| 已完成阶段制品 | ❌ | ✅ 摘要版 | AI 显式请求时 |
| `_map.yaml` | ✅ 始终可用 | — | — |
| `gate-log.yaml` | ✅ 最近 5 条 | ✅ 更早的摘要 | — |

### 与其他机制的协作

```
机制二 Compaction     → 定义 HOW（怎么压缩）
机制八 过渡归档       → 定义 WHEN/WHAT（什么时候、压缩谁）
机制三 gate-log 窗口  → 定义 HOW MUCH（保留多少历史）
机制七 context_fence  → 定义 WHERE NOT（排除哪些项目）
步骤 5e _map.yaml    → 维护归档后的全局索引
```

---

## 与现有机制的关系

```
渐进披露（已有 KI）        → 本协议的理论基础
Skills Gating              → L1 阶段层的过滤器
三层 Skills 优先级          → 决定加载哪些 Skills
Workflow frontmatter        → 上下文声明的载体
制品摘要化                  → Compaction 的实现
gate-log 滑动窗口           → 历史记录的控制
capabilities.md 动态生成    → 上下文感知的自我描述
会话审计与交接              → 🆕 使用数据驱动的进化式上下文优化
项目上下文围栏              → 🆕 多项目场景的硬排除机制（AISEP.md context_fence）
阶段/Slice 过渡归档         → 🆕 Compaction 的编排层（WHEN/WHAT 触发）
```

---

## config.yaml 配置项

```yaml
# .aisep/config.yaml
context:
  # 全局预算
  budget:
    l0_max_tokens: 2000          # 常驻层上限
    l1_max_tokens: 5000          # 阶段层上限
    l2_per_request_tokens: 3000  # 按需层单次上限
    total_soft_limit: 10000      # 软上限（警告）
    total_hard_limit: 15000      # 硬上限（拒绝加载超出部分）

  # 制品摘要
  compaction:
    auto_generate: true          # Gate 通过时自动生成摘要
    summary_max_lines: 30        # 摘要最大行数

  # gate-log 控制
  gate_log:
    recent_entries: 5
    older_entries: summary_only
    max_loaded_entries: 10

  # 懒加载
  lazy_loading:
    skills_metadata_only: true   # Boot 时只加载 Skill 名称 + 描述
    artifacts_summary_first: true # 默认加载摘要版
```
