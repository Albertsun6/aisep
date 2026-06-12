# feat-req-5step — 架构方案

> refs: spec.md

## 设计原则

复用 harness.py 既有机制,零新依赖(纯标准库):receipt 走 `build_receipt`/`write_receipt`(harness.py:153/184),symlink 防护走 `_read_no_symlink`(harness.py:143),CLI 装配走 `_infra_guard` + `_emit` 模式(cli.py:149/165),trace 语法复用 `_REFS_RE`(harness.py:40)。

## 1. 产物格式(机器可检判据)

### intent.md(gate-intent 的输入)
- **track 行**:正文任意位置一行 `track: <值>`(regex `^track:\s*(\S+)`,MULTILINE);值 ∈ {fast, standard, epic},非法 → 1,缺失 → 1(诊断列允许集合)。
- **必填节**:markdown 二级标题 `## <名>`,名集合(忽略大小写/首尾空白):`problem`、`users`、`成功指标`(别名 `success-metrics`)、`non-goals`、`appetite`。节非空 = 标题与下一个 `## `(或 EOF)之间存在非空白行。任一缺失/空 → 1(诊断点名)。
- **解析失败判据(→3)**:文件不存在 → InfraError(spec 验收 4);文件存在但**一个 `## ` 标题都解析不到** → InfraError(结构损坏到无法定位必填节)。部分缺节 → 1(不是 3)。
- source 出处行:建议层,不机器强制(spec 范围表 R0)。

### discovery.md(gate-scope 的输入)
- **两节**:`## in` 与 `## out`(忽略大小写)。任一节标题缺失 / 文件不存在 → InfraError(spec 验收 8)。
- **项**:节内的 bullet 行(`- `/`* `)或表格数据行(`|` 开头,排除表头与 `|---|` 分隔行)。
- **in 项追溯**:每个 in 项行内须含 `refs:` 且引用含 `intent` 字样(覆盖 `> refs: intent.md` 与 `refs: intent#<条目>` 两种写法);任一未追溯 → 1(点名该项)。
- **out 非空**:out 节 ≥1 项,否则 → 1。
- in 节存在但 0 项 → 1(范围未圈定)。
- intent.md 不存在 → 1(诊断"先过 gate-intent";链断语义同 gate-trace → 1,非 3)。

### spec.md 升级判据(并入 `_spec_decision`,gate-spec 与 --check 同享)
- **清零检查(总是跑)**:正文含字面 `[NEEDS CLARIFICATION` → 1。**判据细化**:先剥离 fenced 代码块(```)与行内代码段(反引号)再搜索——真正的残留标记是裸文本,代码格式内的是"讨论该标记"(否则本 spec 自身与任何引用该机制的文档都会被误拒)。
- **trace 链(仅 `spec_path.parent/intent.md` 存在时)**:`_REFS_RE` 提取的 refs 合并串须匹配 `(scope|intent)(\.md|#)`;不匹配 → 1(诊断引导 `> refs: scope.md` 写法)。

## 2. harness.py 改动

| 函数 | 性质 | 说明 |
|---|---|---|
| `_intent_decision(intent_path) -> (decision, msgs)` | 新增 | 纯结构校验,无 receipt;依 §1 判据 |
| `gate_intent(intent_path, repo_root, feature_id, argv)` | 新增 | 镜像 `gate_spec`(harness.py:282):symlink→infra;approved 才填 inputs(path+sha256);无论过/拒写 receipt(gate=`gate-intent`) |
| `_scope_decision(discovery_path, feature_dir)` | 新增 | 依 §1 判据(含 intent 存在性) |
| `gate_scope(discovery_path, repo_root, feature_id, argv)` | 新增 | 同上,gate=`gate-scope`,inputs=discovery.md |
| `_spec_decision`(harness.py:270) | 升级 | 追加清零检查 + 条件 trace 链;gate_spec/gate_spec_check 自动同享 |
| `check_receipt_chain`(harness.py:528) | 升级 | 末尾追加:intent 内容源 = git index 优先、磁盘兜底(同 spec.md 的 TOCTOU 思路);存在 → 校验 `gates/gate-intent.json`(元数据/approved/hash 一致),缺/不符 → 返回点名 gate-intent 的问题串;不存在 intent → 跳过(向后兼容,spec 验收 15) |

退出码语义不变:0/1 由 decision 表达,3 只经 InfraError;新 gate 不产生 needs_human(spec 契约对齐节)。

## 3. cli.py 改动

- 新增 `_cmd_gate_intent` / `_cmd_gate_scope`(均 `@_infra_guard`):
  - 参数:可选位置参数 `path`(intent.md / discovery.md 路径)与 `--feature <id>` 二选一;只给 --feature 时路径推导为 `specs/<id>/{intent,discovery}.md`;只给 path 时 feature_id 用 `derive_feature_id`(对 path.parent/spec.md 同目录推导,cli.py:179 同型)。
  - 输出走 `_emit("gate-intent", ...)`。
- `main()` 注册两个子命令(help 一句话 + 上述参数)。
- gate-spec 子命令不改(升级在 harness 层)。

## 4. 测试(tests/test_req_5step.py,unittest)

镜像 tests/test_harness.py 的临时 repo fixture 模式(tempfile + git init + 最小 specs 树)。用例 1:1 对应 spec 验收 1-16:A 组 gate-intent 过/缺节/track 非法/infra;B 组 gate-scope 过/缺 refs/out 空/infra;C 组清零检查与 trace 链(含修复后通过);D 组三档 track 行为;E 组 receipt 链扩展 + 两条向后兼容。receipt 断言:gate/feature_id/exit_code/decision/inputs hash/schema_version。

## 5. 建议层产物

- `.claude/skills/sdlc-requirements/SKILL.md` 重写为 R1-R5 编排:输入不限形态(先萃取)、track 三档分流(fast=R1+R5;standard=全步;epic=R2 后拆子 feature 分形回流)、每步产物/人审点/对应 gate 命令、页数预算(intent≤1 页、scope≤1 页、discovery 表格化——建议层,无机器强制)。
- `docs/flows/stage-requirements.bpmn`:to-be 流程图入库(项目级,AGENTS.md 约定;不动 sdlc-pipeline.bpmn 六 stage id,无测试钉死面)。

## 6. 风险与回滚

- 新检查全部渐进启用(无 intent.md 的存量 feature 行为不变),CI 不变红(spec 验收 15/16 直接测试);回滚 = revert 单 PR。
- gate-commit 链扩展只在 `check_receipt_chain` 内部加分支,不改其调用方签名。
