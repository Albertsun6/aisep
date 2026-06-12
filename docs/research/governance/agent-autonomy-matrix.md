> **来源**:老库 AISEP416(2026-04)/policies/agent-governance.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。把宪法 P4/P5 落成 L0-L6 风险×阶段自治矩阵;Odoo 专属硬规则(H-2/H-3/S3)需泛化后才适用。

# Agent Governance Policy

> **文档类型**：正式治理政策（Formal Policy）
>
> **适用范围**：所有 AISEP Agent 的自主权边界、操作限制、审批流程
>
> **生效时间**：即日起（M1-M3 起步期）
>
> **变更流程**：本文档变更需要 CEO / 架构师审批，并创建对应 ADR 记录决策理由
>
> 版本：v1.0 · 2026-04-16

---

## 一、永不越界原则（6 条硬规则）

> 以下规则**不随阶段演进放开**，在任何时期、任何 Agent、任何情况下均不例外。
> 违反任一条视为严重安全事故，需立即上报并触发 Kill Switch。

| # | 规则 | 说明 |
|---|------|------|
| H-1 | **生产数据库永远不直接操作** | Agent 持有的技术账号对生产 DB 只有只读权限。写操作必须经过人工确认后由运维手动执行。 |
| H-2 | **会计期间关闭/重开永不触碰** | `account.period` 相关操作（关闭、重开、对账）完全禁止 Agent 发起，无论权限是否具备。 |
| H-3 | **权限与安全规则必须架构师审核** | `ir.rule`、`res.groups`、`ir.model.access` 的任何写操作需架构师线下审核后手动执行。 |
| H-4 | **生产环境部署永远人工扳闸** | Agent 可生成部署脚本、制作 PR、运行 staging 测试，但 prod 部署的最终触发必须由人工在 CI 界面确认。 |
| H-5 | **数据库 Schema 破坏性变更必须双签** | 删字段、重命名字段、变更字段类型等破坏性 migration，需架构师 + 一名高级开发双签 review 后方可合并。 |
| H-6 | **Agent 不能修改自己的约束** | Agent 不能修改本文档、不能修改 CI 中的 Fitness Function、不能修改自身的 system prompt 或权限策略。 |

---

## 二、操作风险等级定义

| 等级 | 名称 | 典型操作 | 可逆性 |
|------|------|----------|--------|
| L0 | 只读 | 查询代码、分析影响、生成报告、查询 traceability.db | 完全可逆 |
| L1 | 建议 | 提出 PR 草案、生成设计文档、建议重构方案 | 完全可逆 |
| L2 | 文档 | 写测试、更新文档、修复 lint、更新 ADR 草稿 | 易回滚 |
| L3 | 代码 | 修改业务代码、新增 Odoo 模块、提交 PR | Git 可回滚 |
| L4 | 架构 | 修改核心架构制品、跨模块重构、变更 ADR 结论 | 影响大，需评估 |
| L5 | 数据 | 数据迁移脚本、schema 变更（非破坏性）| 难回滚 |
| L6 | 生产 | 部署到 prod、修改生产权限、操作生产数据 | 灾难性 |

---

## 三、领域敏感度等级定义

| 等级 | 名称 | 模块示例 | 特殊限制 |
|------|------|----------|----------|
| S3 | 核心 | `account`、`hr_payroll`、`stock_valuation`、`account_move` | 永远适用 H-1 ~ H-6，且操作风险等级自动上移一级 |
| S2 | 重要 | `sale`、`purchase`、`stock`、`mrp`、`crm` | 起步期和闭环期，L3 及以上需人审 |
| S1 | 一般 | `website`、`helpdesk`、`forum`、`project` | 按阶段矩阵执行 |
| S0 | 辅助 | `mail` 基础扩展、`contacts` 扩展、`res.partner` 非核心字段 | 按阶段矩阵执行 |

---

## 四、渐进式自主权矩阵

> 矩阵定义 Agent **默认行为**。特定 Agent 的具体权限以各 Agent 定义文件为准，但不得超出矩阵上限。

### M1–M3：地基期

```
              L0只读  L1建议  L2文档  L3代码  L4架构  L5数据  L6生产
默认策略     │  自主  │  自主  │  人审  │  人审  │  禁止  │  禁止  │  禁止  │
```

- 目标：建立知识底座，让 Agent 从只读和分析任务开始积累信任
- 所有 L2+ 操作需架构师审批，无例外

### M4–M6：闭环期

```
              L0只读  L1建议  L2文档  L3代码  L4架构  L5数据  L6生产
默认策略     │  自主  │  自主  │  自主  │  通知  │  人审  │  人审  │  禁止  │
```

- 目标：需求 → 代码 → 测试闭环，L3 代码操作走 `feature/ai-*` 分支 + 人工通知
- L3 "通知"含义：Agent 自动创建 PR 并发通知，无需等待审批即可合并（但人工可随时回退）
- 前提：CI Fitness Functions 必须通过

### M7–M9：深化期

```
              L0只读  L1建议  L2文档  L3代码  L4架构  L5数据  L6生产
默认策略     │  自主  │  自主  │  自主  │  自主  │  通知  │  人审  │  禁止  │
```

- 目标：Agent 可独立完成模块级代码变更，架构变更升级为通知制
- L4 "通知"含义：Agent 更新架构制品后发通知，架构师可在 SLA 内（48h）驳回

### M10+：成熟期

```
              L0只读  L1建议  L2文档  L3代码  L4架构  L5数据  L6生产
默认策略     │  自主  │  自主  │  自主  │  自主  │  通知  │  人审  │  人审  │
```

- 目标：70% 工程工作 AI 主导，人工聚焦高价值判断
- L6 生产操作从"禁止"升级为"人审"，但 H-1 ~ H-6 永远有效

---

## 五、配套执行机制

### 5.1 Policy as Code（[M4-M6] 实现）

所有矩阵规则将以代码形式实现在 CI 流水线中：

```python
# tools/check-agent-policy.py（示意）
def check_operation(agent_id, operation_level, domain_sensitivity, current_phase):
    if is_hard_rule_violation(operation_level, domain_sensitivity):
        raise HardRuleViolation(f"Operation blocked by hard rule")
    
    allowed = AUTONOMY_MATRIX[current_phase][operation_level]
    if allowed == "FORBIDDEN":
        raise PolicyViolation(f"Operation not allowed in {current_phase}")
    elif allowed == "NOTIFY":
        send_notification(agent_id, operation_level)
    elif allowed == "HUMAN_REVIEW":
        request_approval(agent_id, operation_level)
```

### 5.2 全量审计日志

- 所有 Agent 操作通过 Langfuse 记录 Trace ID
- Trace 包含：Agent 身份、操作级别、领域敏感度、人审状态、最终结果
- 日志保留 365 天，不可篡改

### 5.3 Kill Switch

- 架构师可通过设置环境变量 `AISEP_AGENT_KILL_SWITCH=true` 立即停止所有 Agent 的 L3+ 操作
- Kill Switch 触发后，所有进行中的 L3+ 任务回滚到最近的 Git commit
- Kill Switch 状态变更需记录在 ADR 或 Incident Report 中

### 5.4 定期红队演练（[M7+] 开始）

每季度对 Agent 体系进行一次红队测试：
- 尝试绕过 H-1 ~ H-6 硬规则
- 验证 Kill Switch 有效性
- 测试异常输入对 Agent 决策的影响
- 结果记录在 `docs/red-team/` 目录

---

## 六、变更记录

| 版本 | 日期 | 变更内容 | 批准人 |
|------|------|----------|--------|
| v1.0 | 2026-04-16 | 初始版本，从原始规划对话提炼 | CEO / 架构师 |
