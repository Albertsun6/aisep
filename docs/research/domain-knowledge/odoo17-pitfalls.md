> **来源**:老库 AISEP/.agents/skills/frameworks/odoo17/pitfalls.md。本文为方法论/知识沉淀,非当前 harness 现行强制规范(契约 01:诚实标注建议层)。**领域专属参考(Odoo)**,非当前 harness 通用规范;仅未来真做 Odoo 特性时按需取用。

# Odoo 17 已知陷阱

> ⚠️ **S5 代码生成时必须逐条检查。** 每个陷阱标注了严重程度和自检方法。

---

## P1: 致命级（导致安装失败或数据损坏）

### P1-01: `__manifest__.py` 加载顺序错误
- **问题**：`data` 列表中 View XML 放在 Security 之前
- **后果**：安装时报 `Access Error`，因为 View 引用了尚未定义的 Group
- **规则**：**安全文件永远排在 data 列表最前面**
- **自检**：检查 `data` 列表第一个文件是否为 `security/ir.model.access.csv`

### P1-02: 计算字段 `depends` 遗漏
- **问题**：`@api.depends` 未列出所有影响计算结果的字段
- **后果**：字段修改后不触发重算 → 数据不一致
- **规则**：依赖链必须完整，包括关系字段的跨表依赖（如 `'line_ids.price'`）
- **自检**：每个 `compute` 方法，追踪其内部访问的所有字段，确认都在 `depends` 中

### P1-03: `depends` 中引用不存在的字段
- **问题**：`@api.depends('typo_field')` 引用了拼写错误的字段名
- **后果**：模块安装时不报错，但运行时触发 `KeyError` 或 `AttributeError`
- **规则**：`depends` 中的每个字段必须在 Model 中存在
- **自检**：交叉检查 `depends` 列表和 Model 字段定义

### P1-04: 循环 `depends` 依赖
- **问题**：字段 A depends B，字段 B depends A
- **后果**：无限递归或不确定的计算顺序
- **规则**：绘制 depends 依赖图，确认无环
- **自检**：检查所有 compute 字段的 depends 链是否有环

### P1-05: Odoo 17 `stock.move` 字段重命名
- **问题**：Odoo 17 将 `stock.move.quantity_done` 合并为 `quantity`
- **后果**：引用 `quantity_done` 的 compute depends 在模块更新时报 `ValueError`
- **规则**：`stock.move` 上使用 `quantity` 而非 `quantity_done`；`product_uom_qty` 仍为需求量
- **自检**：搜索代码中所有 `quantity_done` 引用，确认已替换为 `quantity`
- **发现时间**：Slice 5 开发中（2026-03-13）

---

## P2: 严重级（功能异常但不导致崩溃）

### P2-01: `onchange` 放业务逻辑
- **问题**：在 `@api.onchange` 中做数据修改或业务计算
- **后果**：前端操作正常，但通过 API / XML-RPC 创建时逻辑丢失
- **规则**：`onchange` 仅用于 UI 提示/警告，业务逻辑用 `compute` + `store`
- **自检**：检查所有 `onchange` 方法，确认仅做 UI 交互

### P2-02: `create()` / `write()` 覆盖未调 `super()`
- **问题**：覆盖 CRUD 方法时忘记 `super()`
- **后果**：核心逻辑丢失（audit log、消息通知、级联计算等）
- **规则**：**必须** `result = super().create(vals)` / `super().write(vals)`
- **自检**：检查所有 `create` / `write` / `unlink` override 是否有 `super()` 调用

### P2-03: Many2one 字段缺 `ondelete`
- **问题**：Many2one 字段未指定 `ondelete`
- **后果**：父记录删除时行为不确定（可能报错或产生孤儿记录）
- **规则**：每个 Many2one 必须明确 `ondelete`：
  - `'cascade'` — 父删则子删
  - `'set null'` — 父删则字段置空
  - `'restrict'` — 有子记录时禁止删父
- **自检**：检查所有 `Many2one` 字段是否有 `ondelete` 参数

### P2-04: `_rec_name` 缺失
- **问题**：Model 没有 `name` 字段，也没设 `_rec_name`
- **后果**：列表和 Many2one 下拉显示 `模型名(ID)` 而非可读名称
- **规则**：要么定义 `name` 字段，要么设置 `_rec_name`
- **自检**：检查所有 Model 是否有 `name` 字段或 `_rec_name` 属性

### P2-05: TransactionCase 中 SQL 约束破坏 savepoint
- **问题**：在 `TransactionCase` 测试中触发 SQL 约束后，savepoint 被破坏
- **后果**：同一测试方法内后续 ORM 操作均报 `InternalError: current transaction is aborted`
- **规则**：期望 SQL 约束的测试用 `with self.assertRaises(IntegrityError)` 包裹，或拆分为独立测试方法
- **自检**：检查测试中是否有故意触发 SQL 约束的 case，确认是否正确捕获异常
- **发现时间**：Auction 项目 Slice-1（2026-03-16）

### P2-06: One2many 缓存刷新：create 后 compute 不更新
- **问题**：在同一事务中 create One2many 子记录后，父记录的 compute 字段值未刷新
- **后果**：测试中断言失败（count 为旧值），或前端显示不一致
- **规则**：create 子记录后调用 `parent.invalidate_recordset()` 强制刷新 ORM 缓存
- **自检**：检查测试中是否在 create 后立即读取关联的 compute 字段
- **发现时间**：Auction 项目 Slice-2（2026-03-16）

### P2-07: 自定义安全组对 admin 不自动可见
- **问题**：自定义 `groups` 的菜单项 admin 用户看不到
- **后果**：安装模块后管理员看不到菜单，误以为安装失败
- **规则**：自定义组需通过 `implied_ids` 链到 `base.group_user`，确保 admin（属于 base.group_user）自动获取该组权限
- **自检**：检查自定义 group 的 `implied_ids` 是否包含 `base.group_user`
- **发现时间**：Auction 项目 S7 部署验证（2026-03-16）

---

## P3: 中等级（影响维护性或特定场景）

### P3-01: 初始数据缺 `noupdate="1"`
- **问题**：初始数据 XML 未设 `noupdate`
- **后果**：模块更新时覆盖用户修改过的数据（如改过的sequence、分类等）
- **规则**：`<data noupdate="1">` 用于用户可能修改的初始化记录
- **自检**：检查 `data/*.xml` 中的 `<data>` 标签

### P3-02: XML ID 冲突
- **问题**：两个模块使用了相同的 XML ID
- **后果**：后安装的模块覆盖先安装的记录
- **规则**：所有 XML ID 必须以 `{module_name}.` 为前缀（`__manifest__` 中会自动加）
- **自检**：搜索所有 XML 文件中的 `id=` 属性，确认无重复

### P3-03: `sudo()` 安全风险
- **问题**：在业务逻辑中使用 `sudo()` 绕过安全检查
- **后果**：普通用户可能间接操作到超权限数据
- **规则**：`sudo()` 仅用于**系统级操作**（如生成序列号），业务逻辑禁止使用
- **自检**：搜索所有 `.sudo()` 调用，确认每个都有充分理由

### P3-04: 多公司数据隔离遗漏
- **问题**：业务 Model 忘记加 `company_id` 字段和 Record Rule
- **后果**：多公司环境下数据互相可见
- **规则**：涉及业务数据的 Model 必须有 `company_id = fields.Many2one('res.company')`
- **自检**：检查所有业务 Model 是否有 `company_id` 字段

### P3-05: 循环模块引用
- **问题**：Model A 引用 B（`Many2one`），B 引用 A
- **后果**：Python import 链循环导致 `ImportError`
- **规则**：使用字符串引用 `comodel_name='module.model'` 而非直接 Python import
- **自检**：检查 Model 间的引用关系图

---

## P4: 轻微级（代码质量和可维护性）

### P4-01: 缺少 `_description`
- **问题**：Model 没有 `_description` 属性
- **后果**：管理界面和日志中显示技术名（`mrp.bom`）而非可读名
- **规则**：每个 Model 必须有 `_description = '可读名称'`

### P4-02: 字段 `string` 使用英文
- **问题**：面向中国用户的项目，字段 `string` 用英文
- **后果**：UI 显示英文标签
- **规则**：`string` 使用中文（国际化通过 `.po` 翻译处理）

### P4-03: View 中暴露技术字段
- **问题**：在 Form/Tree 中显示 `id`、`create_uid` 等技术字段
- **后果**：用户困惑
- **规则**：技术字段在 View 中设为 `invisible="1"` 或不显示

---

## AISEP 自检清单（S5 Gate 前执行）

```
[ ] P1-01: __manifest__.py data 列表顺序正确?（security 在前）
[ ] P1-02: 所有 compute 字段的 depends 完整?
[ ] P1-03: depends 中的字段名拼写正确?
[ ] P1-04: compute depends 链无环?
[ ] P2-01: onchange 中无业务逻辑?
[ ] P2-02: 所有 CRUD override 都调了 super()?
[ ] P2-03: 所有 Many2one 有 ondelete?
[ ] P2-04: 所有 Model 有 name 字段或 _rec_name?
[ ] P2-05: 测试中 SQL 约束用 assertRaises 包裹?
[ ] P2-06: create 子记录后需要 invalidate_recordset()?
[ ] P2-07: 自定义 group 的 implied_ids 包含 base.group_user?
[ ] P3-01: 初始数据有 noupdate="1"?
[ ] P3-02: XML ID 无冲突?
[ ] P3-03: sudo() 仅用于系统级操作?
[ ] P3-04: 业务 Model 有 company_id?
```
