## ADR-027 · 2026-11-26

- **状态**：已采纳（Albert 2026-11-26 拍板：「先补上那一层防线，再放宽」，范围在会话里逐项选定）；兑现 ADR-024 第 1 款「漏洞修掉后由 Albert 决定是否把 `modules/**`、`vendor/**` 放进合并后评审」，ADR-024 原文不改。
- **决策**：
  1. **`modules/` 下的 `.ttl` 改为合并后评审**，但不含 `modules/aisep-core/**`（批准记录、活动、关口的类与属性，以及它们的 SPARQL 形状）、`modules/ext-governance/**`（批准记录与活动的 SHACL 形状 EG*、质量度量）、`modules/ext-actions/**`（AI 可执行的写动作目录，ADR-026 要求按元模型改动评审）；这三个排除目录按不区分大小写比较。判断口径与 ADR-024 第 1 款相同：PR 改到的每一个路径都属于这一类、ADR-024 放宽类或 ADR-019 白名单，且都是模式 100644 的普通文件。
  2. **`vendor/**` 暂不放宽。** 上游升级同时改 `MANIFEST.json`、`SHA256SUMS` 等非 `.ttl` 文件，只放宽 `.ttl` 没有实际效果；升级少、影响面大，照旧合并前评审。
  3. **不变的**：改到 `modules/**` 的 PR 照旧走三步合并，合并前核对 H 上 `negatives` 为 `["success"]`（ADR-024 第 2、5 款）；ADR-024 第 7 款列出的不放宽项照旧。
- **理由**：ADR-024 不放宽 `modules/**` 的原因是 #105（模块声明的 `aisep:ApprovalRecord` 子类做类型的记录被推导认可、却绕过 `mergecheck`），合并前评审是唯一拦截点。现在两层防线都不依赖评审：#110 让 `mergecheck` 按 T 与 M 上下文的子类闭包识别记录与活动，与推导同口径；#115 把类型写在模块或 vendor 文件里的记录与活动一律拒绝（`docs/mcp-interface.md` §5.9 检查项 9），两者都有负例，且做过去掉修复的对照证伪。三个排除的模块直接定义批准记录与活动、判定记录是否合法、决定 AI 能写什么，留在合并前评审。
- **后果**：其余模块（am4、bpmn、c4、ddd、uml、ext-code、ext-verification，以及新增的模块目录）的元模型改动必需检查通过即可合并，合并后派独立评审人。残余风险，靠合并后评审事后发现：① 这些模块仍能写入影响治理判定的三元组，例如往 `aisep:Gates` 方案里加关口（`approval_problems` 从全部本体图取关口）；② am4 是枢纽模块，它的形状与 aisep-core 的形状在 L3 同图校验，能用 `sh:deactivated` 停用 aisep-core 的 L3 形状，L1 的 `approval_problems` 与 ext-governance 的 L3 校验不受影响（#118 评审实跑）；③ 新增模块能经清单加载 `vendor/`、`modules/`、`models/` 下的任意文件，但改不了 vendor，把治理记录当本体加载会被 `mergecheck` 检查项 9 拒绝。恢复条件同 ADR-024。
