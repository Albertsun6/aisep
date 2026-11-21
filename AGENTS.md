# AISEP 仓库：给编码代理的规则

本仓库是 AISEP 的模型仓库 + 元模型 + 工具。规范以 `docs/` 为准：原则 `docs/principles.md`，方法论 `docs/methodology.md`，元模型 `docs/metamodel-spec.md`，决策 `docs/decisions.md`，MCP 接口 `docs/mcp-interface.md`。`docs/history/` 下是历史材料（spike 结果、交接、草稿、取证），不是规范。

## 环境
- Python ≥ 3.12，依赖见 `requirements.txt`。解释器用主 checkout 的 `.venv`（已 gitignore，所有 worktree 共用，不要在 worktree 里另建）：`PY=~/Desktop/AISEP/aisep/.venv/bin/python`。新机器上建：`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt`。
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
2. **自动合并（Albert 2026-11-20 定；评审分级见 ADR-019）**：PR 不再逐个等 Albert 批准，满足下面全部条件就合并：
   - CI 的全部必需检查通过（当前为 `gate`、`mergecheck`、`pytest`；以分支保护设置为准）；
   - **按路径分级评审**。独立评审人是一个没参与该 PR 实现、也没写它测试的 agent。
     - **核心路径，合并前评审**：PR 改到 `aisep/**`、`tools/**`、`modules/**`、`.github/workflows/**`、`.githooks/**`、`vendor/**`、`requirements.txt`、`pytest.ini`、`aisep-mcp/tests/test_merge_check*.py`、`AGENTS.md`、`docs/principles.md`、`docs/decisions.md`、`docs/metamodel-spec.md`、`docs/mcp-interface.md` 中任一项，或在 `models/**` 下新增 IRI（IRI 一经创建不改），就要先由独立评审人评审 PR 头提交，没有阻塞问题才合并。评审之后又加了提交，就要对新的头重新评审；**例外**：新的头与评审过的头之间只多一个合法批准提交时不再重评，由下面第 1 步的 `mergecheck` 核对它的形状（ADR-019 第 3 款）。
     - **其余路径，合并后评审**：必需检查通过即可合并；合并后由独立评审人评审，结论写成 PR 评论并注明评审的提交 SHA，发现阻塞问题就开修复 PR 或 revert PR。
     - 协调会话用 PR 的文件清单和模型差异对照上面的清单判定走哪一级，拿不准按合并前评审；
   - 只由**协调会话**执行合并。开 PR 的会话只开 PR、回报，不自己合并；
   - 涉及 mergecheck 的 PR（改到 `aisep/mergecheck.py`、`aisep/diff.py`、`aisep/approval.py`、`aisep/gitio.py`、`aisep/tools.py`、`aisep/writer.py`，或 `aisep/core.py` 的批准核对与 approvalState 推导）合并前，须在本地跑第四轮负例 `$PY -m pytest -q -n auto aisep-mcp/tests/test_merge_check_negatives.py` 并全绿。CI 的必需检查不跑这个文件；CI 若另有跑它的非必需 job，其结果不拦合并，也不代替本地跑。在它升为必需检查之前，本地跑是唯一有约束力的保障（ADR-017、ADR-019 第 4 款）；
   - 合并按下面三步执行（接口文档 §5.9「合并前重算」、第四轮 R4-11、ADR-017）。H 是评审过的 PR 头（`gh pr view N --json headRefOid,headRefName`），`<分支>` 是 PR 源分支名：
     1. **合并前重算**：`git fetch origin` 后跑 `$PY -m aisep.mergecheck --pr-head H --head-ref <分支> --target main`。`--target main` 取远端跟踪分支 `origin/main`，所以必须先 fetch。输出里的 `T` 就是重算用的目标分支头。退出码不是 0（`problems` 非空）就不合。
     2. **复核目标分支没动**：`$PY -m aisep.mergecheck --target main --target-unchanged T`。它用 `ls-remote` 比对远端，输出 `targetUnchanged: false`（退出码 1）时，说明 main 已经前进，回到第 1 步重算。
     3. **合并与合并后核验**：`gh pr merge N --merge --match-head-commit H`。合并后 `git fetch origin`，取新的 main 头 M，跑 `$PY -m aisep.mergecheck --post-merge M --t-used T --pr-head H --head-ref <分支>`。不通过（退出码 1）就立即开 revert PR，并报告 Albert。
   - 合并提交说明按评审级别写：合并前评审的写「自动合并：必需检查通过、独立评审通过（评审要点）」，用了批准提交豁免的在评审要点里注明评审过的头和「之后只多一个批准提交」；合并后评审的写「自动合并：必需检查通过，合并后评审（ADR-019）」。两种都记下 T、H 以及第 1、2 步的结果（如「合并前重算：T=…，H=…，problems=[]；targetUnchanged=true」）。第 3 步的核验结果在合并后才有，写进 PR 评论；合并后评审的结论也写进 PR 评论。
   Albert 在会话里明确说「先别合 #N」时，就不合。这一条只管代码与文档 PR 的合并；**模型里的批准记录（`ApprovalRecord`）仍只能由 Albert 本人做出**，AI 不得以他的名义新增批准记录。
3. **用合并提交**：`gh pr merge --merge`，不用 squash / rebase，保留分支上的提交可达（关口回看历史批准依赖 commit 可达，见 `docs/mcp-interface.md`）。
4. **PR 即锁**：开工前看开着的 PR；某文件已在别的 PR 里被改，就不碰它，去那个 PR 留言或等合并。

## 工作方式
- 改元模型（`modules/`）后跑全量测试：`$PY tools/aisep.py test`（含第四轮负例，耗时长，以 `tools/aisep.py` 中 `run_pytest` 的注释为准，应全绿）。
- 改模型（`models/`）后跑 `gate`。
- 各 ADM 阶段的模板与提示词在 `docs/adm/<阶段>/`，阶段出口统一走 `docs/adm/governance/` 的关口评审。
- 已拍板的决策（`docs/decisions.md`）不再重新讨论；发现冲突先报告，不自行改动。
