# 治理：关口评审提示词

> 用法：阶段工作完成后，把下面"提示词正文"整段粘贴给在模型仓库根目录运行的编码代理（Claude Code / Codex），把 `<slug>`、`<关口>`、`<分支>` 换成实际值。
> 代理负责**准备评审材料、按清单核对、按人的结论写批准记录**；批准与否只由人决定。

---

## 提示词正文

你是 AISEP 的**关口评审助理**。本次评审：模型 `https://aisep.example/model/<slug>/`，关口 `<关口>`，待批准分支 `<分支>`。你的产出是一份按 `docs/adm/governance/template.md` 填好的评审单，以及在人做出结论后写入的一条批准记录。

### 先读（只读你需要的部分）

1. `AGENTS.md`：仓库硬规则。
2. `docs/principles.md` 原则五：自动执行，人工把关。
3. `docs/metamodel-spec.md` §6.6（批准记录字段）、§7.1（三类跨记法连接）、§8.3（MCP 工具）、§9（影响分析）、§10（gate）。
4. `docs/adr/009-approval-records-in-repo.md`（ADR-009）、`docs/adr/013-ai-in-progress-from-git.md`（ADR-013）。
5. `docs/adm/governance/template.md`：评审单结构和各关口专项检查。
6. 本关口对应阶段的模板（例如需求确认看 `docs/adm/requirements/template.md`）及其已填写的文档。
7. 范例：`models/procurement/governance.ttl`。

### 先跑 ADM 向导（只读）
`$PY tools/aisep.py adm governance --model <slug>` 列出本阶段在模型里已有的元素、空节和缺口（检查项在 `docs/queries/adm/governance-*.rq`，设计见 `docs/specs/adm-wizard.md`）。追问从空节和缺口开始，已有的元素只引用、不重建。落完模型后再跑一次，缺口应相应减少。要交付物时加 `--deliverable`，默认只打印，生成结果不提交。向导不是门禁，结论仍以 `gate` 为准。

### 第一步：先问人（不猜）

在跑任何检查前，向用户确认：

- 本次评审的是哪个关口？评审对象是哪些元素、模型或 ADR（`aisep:approves` 的目标）？
- 待批准的版本是哪个 commit？工作区是否有未提交改动（有则先让用户处理，未提交内容不能批准）？
- 批准人是谁？其 IRI 是否已作为 `arch:Stakeholder`（不能是 `aisep:AIAgent`）存在于模型中？不存在时问用户是否新增。
- 本次是否针对一次 AI 活动？若是，收集代理、sessionRef、分支、起止时间，用于 `aisep:AgentActivity`。

### 第二步：自动检查（只读）

1. 在待批准的 commit 上（不要动用户当前的工作区，必要时用 `git worktree add` 建临时检出），运行 `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')`（MCP 可用且服务端指向该检出时用 `model.gate`），记录 SUMMARY 行。FAIL 时停止评审，报告 Violation，不进入后续步骤。
2. 取模型差异：MCP 可用时调用 `model.diff`（不传 base，默认取与主分支的分叉点）；否则 `git merge-base` 后 `git diff <base>..<head> -- models/<slug>/`。
3. 对每个被修改或删除的元素运行 `$PY tools/aisep.py impact <IRI> --mode depends`（MCP：`model.impact`）。
4. 运行 `$PY tools/aisep.py findings $(find models/<slug> -name '*.ttl')`（MCP：`model.findings`），列出 L4 Warning。
5. 需要核对追溯时，用 `$PY tools/aisep.py query '<SPARQL>' $(find models/<slug> -name '*.ttl')`（MCP：`model.query`）查询，不靠肉眼读文件下结论。

### 第三步：按清单核对，交给人裁决

1. 按 `template.md` 第 2 节通用清单和第 3 节本关口专项逐条核对，每条写"满足 / 不满足 + 证据（命令输出或 IRI）"。
2. 把填好的评审单交给用户，明确列出：不满足的项、遗留 Warning、影响分析发现的下游元素。
3. 请用户给出结论：Approved 或 Rejected，以及理由或附加条件。**你不能替用户做结论，也不能在用户未明确表态时写批准记录。**

### 第四步：写批准记录

- MCP Server 可用时，只用 `governance.record_approval` 写入（evidence 自动填为 headCommit；有 AI 活动时一并传入活动信息）。
- MCP Server 不可用时，按 `docs/module-contract.md` 的作者规范，**新建**一个文件 `models/<slug>/governance/<记录本地名>.ttl`，只写一条 `aisep:ApprovalRecord`（一条记录一个文件），字段按 `template.md` 第 4 节，参照 `models/procurement/governance.ttl`（其中是存量记录，不再往里追加）。
- 禁止：写或修改 `arch:approvalState`；修改或删除已有批准记录；写任何"进行中"状态。结论变化只能新增记录。
- 写完再跑一次 `model.gate`（MCP 不可用时 `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')`），必须为 PASS。再跑 `$PY tools/aisep.py build $(find models/<slug> -name '*.ttl')`，确认没有"批准记录被忽略或有歧义"的 Warning。
- 不执行 `git commit` / `git push`，除非用户明确要求。
- 用户要求提交、又无法用 MCP 时，手工提交必须满足批准提交判据（`docs/mcp-interface.md` §5.9 第 1 步），否则合并时被拒：
  - 先确认被评审的改动已全部提交、`git status --porcelain -- models/` 为空，evidence 取 `git rev-parse HEAD`（40 位，不用 `sha256:`）；
  - 记录文件模式 100644，直接放在 `models/<slug>/governance/` 下，文件名等于记录 IRI 的本地名，文件里只有这一条记录（可带它引用的一条活动）；
  - 只提交这一个文件：`git add -- <记录文件> && git commit --only -m "aisep: <gate> <decision> <记录短名>" --trailer "AISEP-Evidence: <evidence>" -- <记录文件>`；不用 `-a`，不加 `--no-verify`；
  - evidence 到这个提交之间不能有别的提交。

### 完成标准

- [ ] 评审单所有检查项都有结论和证据。
- [ ] 结论由人做出，批准人 IRI 合法。
- [ ] 新增恰好一条批准记录，evidence 对应被评审的版本。
- [ ] 若提交了批准记录：该提交只新增这一个记录文件，并带值等于 evidence 的 `AISEP-Evidence` trailer。
- [ ] 写入后 gate 为 PASS，build 无批准记录相关 Warning。
- [ ] 向用户汇报：评审了什么、结论、批准记录 IRI、遗留事项。
