# AISEP 仓库：给编码代理的规则

本仓库是 AISEP 的模型仓库 + 元模型 + 工具。规范以 `docs/` 为准：原则 `docs/principles.md`，方法论 `docs/methodology.md`，元模型 `docs/metamodel-spec.md`，决策 `docs/decisions.md`，MCP 接口 `docs/mcp-interface.md`。

## 环境
- Python ≥ 3.12，依赖见 `requirements.txt`。本机共用解释器：`PY=~/Desktop/AISEP/spike-linked-archi/.venv/bin/python`，不要另建 venv。
- 启用提交钩子：`git config core.hooksPath .githooks`

## 硬规则（违反即返工）
1. **提交和 CI 只认 `gate`**：`$PY tools/aisep.py gate` 为 PASS 才算完成。`check` / `validate` 只做开发时快速反馈。
2. **只写限定关系**：关系一律写成限定关系资源，不写直连三元组（规范 §8.1）。
3. **一元素一记法一类型**；跨记法只允许规范 §7.1 的三类连接；`arch:refines` 只能 code → design → hub（§7.2）。
4. **不手写 `approvalState`**：它由批准记录推导。批准只能新增批准记录（`governance.record_approval` / ext-governance 模块）。
5. **IRI 按规范 §3 生成，一经创建不改**；改名只改标签。根命名空间暂为占位符 `https://aisep.example/`，统一替换前不要自行改。
6. **`vendor/` 只读**；升级上游按规范 §11 走一次显式变更。
7. 不存在任何"上报进行中状态"的写入（ADR-013）；所有状态都在 Git 里的文件中。

## 分支与合并（一律走 PR）
1. **不直接推 `main`**：改动在 `claude/<主题>` 分支上做（用 worktree：`.claude/worktrees/<主题>`），推送后开 PR 到 `main`。
2. **合并要 Albert 批准**：Albert 在会话里明确批准某个 PR（如「批准 #N」）后，由 AI 代为合并，合并提交写明原话。批准按 PR 逐个算；CI 的 `gate` 没过、或批准后又加了提交，都不合并，需重新批准。没有批准不得合并。
3. **用合并提交**：`gh pr merge --merge`，不用 squash / rebase，保留分支上的提交可达（关口回看历史批准依赖 commit 可达，见 `docs/mcp-interface.md`）。
4. **PR 即锁**：开工前看开着的 PR；某文件已在别的 PR 里被改，就不碰它，去那个 PR 留言或等合并。

## 工作方式
- 改元模型（`modules/`）后跑全量测试：`$PY tools/aisep.py test`（约 2.5 分钟，应全绿）。
- 改模型（`models/`）后跑 `gate`。
- 各 ADM 阶段的模板与提示词在 `docs/adm/<阶段>/`，阶段出口统一走 `docs/adm/governance/` 的关口评审。
- 已拍板的决策（`docs/decisions.md`）不再重新讨论；发现冲突先报告，不自行改动。
