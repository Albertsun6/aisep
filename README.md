# AISEP

AI 驱动的软件工程平台：统一模型仓库（ArchiMate 4.0 枢纽 + BPMN / UML / DDD）+ AI 接入。一期交付物是 MCP Server（ADR-008），本仓库目前包含元模型、校验工具原型、示例模型和各 ADM 阶段的模板。

| 目录 | 内容 |
|---|---|
| `docs/` | 原则、方法论、元模型规范、决策记录（ADR）、MCP 接口设计、ADM 阶段模板 `docs/adm/`、历史证据 `docs/history/` |
| `vendor/` | 上游 Linked.Archi 本体（只读） |
| `modules/` | AISEP 模块：本体、shapes、对齐、测试 |
| `models/` | 模型（一个目录一个模型），`procurement/` 为示例 |
| `tools/aisep.py` | CLI：`gate` / `check` / `validate` / `findings` / `query` / `impact` / `build` / `test` |

环境、常用命令与代理规则见 `AGENTS.md`。

## MCP 上手路径（编码代理）

AISEP 的能力都经 MCP Server 暴露（ADR-008，接口契约见 `docs/mcp-interface.md`）。编码代理在本仓库的 worktree 里用它读写模型。

**1. 准备解释器**：服务器用主检出的 `.venv`（所有 worktree 共用），建法见 `AGENTS.md`「环境」。也可以用环境变量 `AISEP_PY` 指定别的解释器。

**2. 启用项目的 `aisep` 服务器**：仓库根的 `.mcp.json` 已声明它（stdio，命令 `sh tools/aisep-mcp`）。项目级服务器要本人批准一次：在 Claude Code 里打开本仓库时按提示批准，或在 Claude Code 设置（如 `~/.claude/settings.json`）里写 `"enabledMcpjsonServers": ["aisep"]`。确认已连上：

```bash
claude mcp list
```

输出里应有 `aisep: sh tools/aisep-mcp - ✔ Connected`。

**3. stdio 启动命令**（`.mcp.json` 调的就是它，也可以自己起来调试）：

```bash
sh tools/aisep-mcp
```

它在当前 worktree 里起服务（worktree 须在主检出目录之下，因为 `--allow-root` 固定为主检出，否则报 `PATH_OUTSIDE_ROOT`），等价于 `python -m aisep.server --transport stdio --profile agent --allow-root <主检出> --repo <当前 worktree>`，每行收发一条 JSON-RPC 消息（先 `initialize`，再 `notifications/initialized`，然后 `tools/list` / `tools/call`）。

**4. 工具清单与画像**（以 `aisep/server.py` 的 `TOOLS` 为准）：

| 画像 | 谁用 | 工具 |
|---|---|---|
| `agent`（`tools/aisep-mcp` 固定用它） | 编码代理 | 16 个：只读的 `model_check`、`model_validate`、`model_findings`、`model_gate`、`model_query`、`model_impact`、`model_diff`、`model_list_actions`、`model_list_views`、`model_render_view`；写入的 `model_add_element`、`model_add_relationship`、`model_set_labels`、`model_set_attributes`、`model_remove`、`model_apply_action`（怎么选、怎么组合见 `docs/actions.md`） |
| `workbench` | 工作台（经 HTTP） | 9 个：`model_findings`、`model_gate`、`model_query`、`model_impact`、`model_diff`、`model_branches`、`model_list_views`、`model_render_view`、`governance_record_approval` |
| `all` | 调试 | 以上 18 个 |

- 批准工具 `governance_record_approval` **不在 agent 画像里**，编码代理看不到它。批准记录只能由 Albert 本人做出（`AGENTS.md`「分支与合并」），经工作台关口页触发（`docs/mcp-interface.md`）。
- `model_list_views`、`model_render_view` 只读看视图：前者列出声明视图与视点投影，后者把一项画成 SVG（与 `tools/aisep.py diagram` 同一出图器，需要 elkjs，见 `docs/mcp-interface.md` §5.15、§5.16）。
- `model_check`、`model_validate` 只做快速诊断；提交和 CI 只认 `gate`，读 `model_gate` 的结论看返回里的 `structuredContent.result`。
- 写工具只改工作区、不提交。写完跑 `gate`，再按明确路径暂存、提交。
- 工作台用的 HTTP 方式：`python -m aisep.server --transport http --profile workbench --allow-root <目录> --allow-origin <工作台页面来源>`，只绑本机回环地址，带 `Origin` 且不在白名单的请求返回 403，不带 `Origin` 的本机请求放行。

**5. 新建模型**：写工具建不了模型本身。新模型目录 `models/<slug>/` 要先手写一个 `arch:Model` 声明（IRI 为 `https://aisep.example/model/<slug>/`，带中文 `skos:prefLabel`），之后才能经 MCP 往里写元素。目录不存在时写工具报 `MODEL_NOT_FOUND`；目录在但没有声明时写入能成功，`gate` 报 L3 违规。

**6. `model` 参数只传裸 slug**，例如 `"model": "procurement"`，不带斜杠或路径（也可以传完整的模型 IRI）。

第一条端到端链路怎么用这些工具，见 `docs/methodology.md` §10。
