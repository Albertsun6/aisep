> **来源**:老库 AISEP/.aisep/docs/vertical-slice-evaluation.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。decompose 阶段切片粒度参考;Odoo 示例仅作示例。

# 垂直切片策略评估 — Odoo 兼容性与粒度分析

## 1. 与 Odoo 设计思想的兼容性评估

### 结论：✅ 完全兼容，且更符合 Odoo 官方推荐

| 评估维度 | 兼容性 | 说明 |
|----------|--------|------|
| **模块化架构** | ✅ 完全 | Odoo 官方推荐"按业务领域拆分模块"，垂直切片天然对齐 |
| **ORM 加载机制** | ✅ 无影响 | ORM 按需加载，不因 model 数量增加而变慢 |
| **增量更新** | ✅ 原生支持 | `odoo-bin -u module_name` 就是增量更新，每个 Slice 追加后 update 即可 |
| **继承机制** | ✅ 互补 | Slice 间可通过 `_inherit` 扩展前序 Slice 的 model |
| **View 系统** | ✅ 无冲突 | Views 存入DB，多个 XML 文件定义的 view 互不干扰 |
| **Security** | ✅ 追加式 | `ir.model.access.csv` 每行独立，Slice 追加行即可 |

### 为什么说更符合 Odoo 设计思想

Odoo 自身的**标准模块就是按垂直切片组织的**：

```
base 模块 = Slice 0（核心：用户、公司、合作伙伴）
    ↓
hr 模块 = Slice 1（员工 CRUD）
    ↓
hr_contract 模块 = Slice 2（合同管理，依赖 hr）
    ↓
hr_payroll 模块 = Slice 3（薪资，依赖 hr + hr_contract）
```

每个标准模块就是一个**可独立安装、可独立演示**的垂直功能切片。我们的策略只是在自定义模块内复制了这个模式。

---

## 2. 性能影响评估

### 结论：✅ 无负面影响

| 性能维度 | 影响 | 原因 |
|----------|------|------|
| **启动时间** | 无影响 | Model 注册在启动时发生，3 个 model vs 30 个 model 差异 < 100ms |
| **运行时查询** | 无影响 | ORM 按需加载，未使用的 model 不占资源 |
| **数据库结构** | 无影响 | 良好的规范化（多个小表）比大宽表性能更好 |
| **内存占用** | 无影响 | Model 类定义常驻内存占用极小（KB 级） |
| **模块更新** | 微影响 | 每次 `-u` 更新扫描module所有文件，但耗时 < 1s |

### 唯一需要注意的点

**跨 Slice model 的关联查询**：如果 Slice 3 的 model 需要 JOIN Slice 1 的 model，确保关联字段有索引。但这是所有数据库设计的通用原则，和切片策略无关。

```python
# 建议：对频繁查询的关联字段加索引
production_order_id = fields.Many2one(
    'manufacturing.production.order',
    index=True  # ← 确保有索引
)
```

---

## 3. Slice 粒度分析

### 三种粒度对比

| 粒度 | 定义 | 一个 Slice 的代码量 | AI 上下文 | 审查负担 | 可演示性 |
|------|------|-------------------|----------|---------|---------|
| **L1 实体级** | 1 个 model + 对应 views | ~100-200 行 | 太小，上下文浪费 | 审太多次 | 单个 CRUD 无业务意义 |
| **L2 功能级** ⭐ | 1 个业务能力 = 1-3 models + views + tests | ~300-800 行 | 刚好 | 适中 | 一个完整业务场景可演示 |
| **L3 模块级** | 整个模块所有功能 | ~2000-5000 行 | 可能超出 | 审一次但量大 | 完整但太晚才能看到 |

### 推荐：L2 功能级 ⭐

**一个 Slice = 一个可独立演示的业务场景**，包含该场景所需的全部 model + view + security + test。

### 粒度判断标准

```
一个 Slice 应满足以下所有条件：
✓ 安装后用户能完成一个有意义的业务操作
✓ 包含 1~3 个新 model（不超过 3 个）
✓ 总代码量在 300~800 行之间
✓ AI 能在一次交互中高质量完成
✓ 用户能在 5-10 分钟内审查完毕
```

### 制造业 ERP 示例切片规划

| Slice | 名称 | 包含内容 | 行数估算 | 依赖 |
|-------|------|---------|---------|------|
| S1 | BOM 管理 | `bom` + `bom_line` models, form/tree views, CRUD tests | ~400 行 | 无 |
| S2 | 生产工单 | `production_order` + `order_line`, 看板视图, 状态流转 | ~500 行 | S1 |
| S3 | 工单报工 | `work_report`, 工时记录, 完工确认 | ~300 行 | S2 |
| S4 | 质量检验 | `quality_check` + `check_point`, 检验工作流 | ~400 行 | S2 |
| S5 | 仓储入库 | `stock_receipt`, 与标准 `stock` 模块集成 | ~350 行 | S2, S4 |
| S6 | 生产报表 | report models, QWeb 模板, 统计视图 | ~300 行 | S1-S5 |

**总计 6 个 Slice，每个 Slice 交付后用户立刻能操作对应功能。**

### 切片依赖图

```
S1 BOM管理
├── S2 生产工单
│   ├── S3 工单报工
│   ├── S4 质量检验
│   │   └── S5 仓储入库
│   └── S5 仓储入库
└── S6 生产报表（汇总）
```

---

## 4. 综合建议

### 采纳垂直切片 + L2 功能级粒度

```yaml
# 在 S2 需求阶段的输出中增加 Slice Planning
slice_plan:
  strategy: vertical          # vertical | horizontal
  granularity: feature        # entity | feature | module
  
  slices:
    - id: "slice-1"
      name: "BOM 管理"
      scope: "创建、编辑、查看多级物料清单"
      models: [bom, bom_line]
      views: [form, tree, search]
      estimated_lines: 400
      depends_on: []
      acceptance: "用户能创建 BOM，添加子件，查看物料清单列表"
```

### Pipeline 流程更新

```
S0 → S1 → S2（+ Slice Planning）
  ↓
  S3: 整体架构（一次，看全貌） → Gate
  ↓
  For each Slice（按依赖拓扑序）:
    S4: Slice 详细设计 → Gate
    S5: Slice 代码生成（追加到模块）→ Gate
    S6: Slice 测试 + 安装验证 → Gate（可演示！）
  ↓
  S7: 最终部署配置 → Gate
```
