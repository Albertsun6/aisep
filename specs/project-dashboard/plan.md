# project-dashboard · plan(architecture)

> refs: spec.md

## 设计
- **新模块 `src/aiforge/project_dashboard.py`**(与 eval 的 dashboard.py 分开,职责单一:项目总览):
  - `collect_state(repo_root) -> dict`:只读采集——
    - features: 遍历 `specs/*/`(排除 contracts/_workspace),读 spec.md 首个标题 + `status:` 行 + 哪些 `gates/*.json` receipt 存在
    - audit: 读 `.aiforge/audit/gates.jsonl`(缺失→空),取最近 N 行
    - contracts: 列 `specs/contracts/*.md`(取标题)
    - git: commit 数 + 最近若干 commit 标题(`git log`,失败→空)
    - counts: 测试数(静态扫 tests/ 的 `def test_` 计数,不跑测试)
  - `render_html(state) -> str`:纯字符串拼装 HTML;**所有动态内容过 `html.escape`**(契约/spec 安全要求)。架构图/管线图是内嵌静态 Mermaid(不含动态数据)。
  - `write_project_dashboard(repo_root, out) -> Path`:写 `docs/project-dashboard.html`。
- **CLI**:`cli.py` 加 `project-dashboard` 子命令,**lazy import**(守契约 04 import 边界),`--out` 默认 `docs/project-dashboard.html`。
- 复用现有视觉骨架(粘性目录 + Mermaid + pill,与 USER-GUIDE.html 一致风格,避免 AI slop)。

## 影响面 / 红线
- 新增 1 模块 + cli.py 一个子命令(lazy import);不动门禁/核心层;`.importlinter` 不变。
- 不是 gate 命令,但仍不调模型(纯读+生成);静态 token 检查范围只含 harness/cli/__main__,新模块自检不含模型 token。

## 不做
- 不做实时刷新/后端/watch;不做主题切换(YAGNI);不嵌 git 之外的外部数据。
