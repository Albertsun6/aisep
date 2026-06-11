# project-dashboard — 项目状态可视化总览(单页 HTML,读真实状态生成)

status: active
目标:`aiforge project-dashboard` 读 `specs/` + `.aiforge/audit/gates.jsonl` + git + 契约,生成一份**人性化的单页 HTML**,让人不用读代码和对话就看懂整个项目:它是什么、架构、管线、已建特性、门禁运行时间线、契约、上手入口。

## 背景与范围
- 痛点:项目状态散在代码、specs、审计流水、git 历史、对话里,人看着累。
- 范围内:一个**只读报告生成**命令,读真实状态 → 生成单文件 HTML(零构建,双击可开);可重复生成,始终反映当前状态。
- **不做**:不写/不改 specs/审计/代码(纯生成 HTML 到 docs/);不调模型(契约 04);不做后端/实时刷新(静态单页)。

## 验收标准(Gherkin)
- Given 在 repo 根跑 `python -m aiforge project-dashboard`
  When 命令结束
  Then 生成 `docs/project-dashboard.html`,单文件、双击可开,含这些区:概览(关键数字)/架构/管线/特性/门禁时间线/契约/上手入口。
- Given `specs/` 下有 N 个特性目录(排除 `contracts/` 与 `_workspace`)
  When 生成
  Then 特性区列出 N 张卡片,每张含 feature id、status、spec 标题、已存在的 gate receipt(过了哪些 gate)。
- Given `.aiforge/audit/gates.jsonl` 有审计行
  When 生成
  Then 门禁时间线区按时间倒序展示门禁运行(gate / decision / 时间);无审计文件则该区显示"暂无数据",命令不崩。
- Given 命令重跑
  When 项目状态变了(新增特性/新跑门禁)
  Then 重新生成的 HTML 反映最新状态(幂等)。
- Given spec 标题/feature id/审计内容含 HTML 特殊字符(如 `<`、`&`)
  When 嵌入页面
  Then **全部 HTML 转义**(防注入/XSS),页面不被破坏。

## 非功能清单(P6)
- 安全(**核心**):① 只读生成,**不调模型**(契约 04)、不改任何 specs/审计/代码;② 所有从文件读入、嵌进 HTML 的动态内容**必须 HTML 转义**(`html.escape`)——spec 标题、feature id、审计字段都来自文件,不转义 = XSS/注入面;③ 不嵌 secret(审计行本就无 secret,字段集是 allowlist)。
- 错误处理:任一数据源缺失/损坏 → 该区优雅降级显示"暂无数据",命令不崩、退出码 0。
- 可观测:本功能即可观测增强;输出路径打印到 stdout。
- 性能/限流:纯本地文件读 + 字符串生成,无外部调用、无网络。
