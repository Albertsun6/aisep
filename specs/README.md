# 规格驱动开发（SDD）工作流

对齐 GitHub Spec Kit 的四阶段闭环，所有产物纳入版本管理、互相引用、可追溯（宪法 P1/P2）：

```
constitution.md      第 0 步：项目宪法（不可逾越的工程原则）
   ↓
spec.md   (specify)  做什么：需求 + 用户故事 + 验收标准(EARS 风格)
   ↓
plan.md   (plan)     怎么做：技术方案 + 模块边界 + 数据流
   ↓
tasks.md  (tasks)    拆成可执行任务，每个任务回链到验收标准
   ↓
implement            交由编排层（Analyst→Architect→Developer→Reviewer→Tester）执行
```

## 规则
- 无 `spec.md` 不得进入实现（门禁拒绝）。
- `plan.md` 必须引用 `spec.md` 的需求编号；`tasks.md` 每个任务必须引用验收标准编号（`AC*`）。
- 实现产出的代码/测试 artifact 通过 `refs` 回链到 task，形成端到端可追溯链。

## 与真实 Spec Kit 并用
本目录的模板可直接配合 `specify` CLI：

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init --ai claude .
# 然后在 agent 中: /speckit.constitution → /speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement
```

示例见 `examples/001-avatar-upload/`。
