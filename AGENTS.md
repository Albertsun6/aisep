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

## 工作方式
- 改元模型（`modules/`）后跑全量测试：`$PY tools/aisep.py test`（约 2.5 分钟，应全绿）。
- 改模型（`models/`）后跑 `gate`。
- 各 ADM 阶段的模板与提示词在 `docs/adm/<阶段>/`，阶段出口统一走 `docs/adm/governance/` 的关口评审。
- 已拍板的决策（`docs/decisions.md`）不再重新讨论；发现冲突先报告，不自行改动。
