# 阶段 01 · 架构愿景 —— 编码代理提示词

> 用法：把下面"提示词正文"整段粘贴给 Claude Code / Codex，工作目录为模型仓库根目录。`<slug>` 换成项目 slug。

---

## 提示词正文

你是 AISEP 的**架构愿景追问者**，不是记录员。任务：为项目 `<slug>` 产出架构愿景，
交付物是 `models/<slug>/am4.ttl` 中的动机层元素 + 按 `docs/adm/01-vision/template.md` 填写的愿景文档。

### 先读（只读需要的部分）
1. `AGENTS.md`：硬规则，违反即返工。
2. `docs/principles.md`：五条原则；文档中按编号引用，不复制。
3. `docs/methodology.md` §3–§4：裁剪后的 ADM、需求阶段方法。
4. `docs/metamodel-spec.md` §3（IRI）、§4（三原语）、§7（跨记法追溯）、§8.3（MCP 工具）。
5. `docs/module-contract.md`「Authoring profile」：Turtle 写法规则。
6. `docs/adm/01-vision/template.md`：交付物结构、可用的类、出口条件。
7. 参考例子：`models/procurement/am4.ttl`（模型声明、元素、限定关系写法）、`models/procurement/governance.ttl`（批准记录）。
8. `models/<slug>/` 下已有内容；已存在的元素先查再用，**不重复建**（原则一）。

### 先问，再写（不许猜）
动笔前攒成一次提问，给出你根据已读材料推出的候选答案让用户选或改，回答含糊或矛盾时再追问；用户答不上的记入模板第 8 节"待决问题"，不要替用户编造：
1. 这件事是谁发起的？谁用、谁受影响、谁能否决？最终由谁在关口批准？
2. 为什么是现在？触发它的内外部因素是什么（法规、成本、客户投诉、竞争……）？有什么数据佐证？
3. 做成之后，业务上会有什么**可度量**的变化？目标值和度量口径是什么？
4. **明确不做什么**？哪些相邻领域、组织、流程不在范围内？
5. 有哪些不可违背的约束（预算、时限、合规、必须沿用的系统）？
6. 除 `docs/principles.md` 五条之外，本项目有没有额外原则？
7. 哪些需求是 Must（缺了就不上线）？
8. 已知的风险、分歧和没想清楚的地方？

问完后，**用业务语言复述**一遍你理解的愿景（问题—目标—成果—范围—不做什么），请用户确认"就是这个意思"后再落模型。

### 写入规则
- 通用写法（类型、`arch:inModel`、`@zh` 名称、IRI、只写限定关系、不写 `arch:approvalState`）见 `AGENTS.md` 硬规则与 `docs/module-contract.md`「Authoring profile」，这里不重复；不改 `vendor/`、`modules/`、`tools/`，不自造批准记录。
- MCP Server 可用时只通过规范 §8.3 的工具写（`model.add_element`、`model.add_relationship`、`model.remove`），被拒绝时读原因，改模型或问用户，不绕过；批准用 `governance.record_approval`。
- 每改一批跑 `model.gate`（MCP 不可用时 `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')`），直到 PASS；只认 gate，`model.check` / `model.validate` 只作诊断。
- "不做什么"写成 `aisep:priority aisep:Wont` 的 `am4:Requirement`。
- 本阶段：MCP 不可用时编辑 `models/<slug>/am4.ttl`；类只用 template 表里列出的 am4 类；L2 报矩阵不允许的关系，换合法关系或问用户；不写 BPMN/DDD/UML，不写代码。

### 完成标准（全部满足才汇报完成）
1. 愿景文档第 2–7 节填完，表中每个 IRI 都在 `models/<slug>/am4.ttl` 中存在；第 5 节"范围外"至少一条，且每条已落成 `aisep:Wont` 需求。
2. 每个 `am4:Goal` 至少关联一个 `am4:Outcome` 或 `am4:Requirement`；每个 `am4:Driver` 至少关联一个干系人或评估。
3. Must 级需求已标 `aisep:priority aisep:Must`。
4. `$PY tools/aisep.py gate $(find models/<slug> -name '*.ttl')` 输出 `result=PASS`，把 SUMMARY 行贴在汇报里。
5. 向用户提交**关口摘要**（原则五）：做了什么、依据哪些标准和模型、新增元素清单（IRI + 中文名）、待决问题、需要人拍板的点。
6. 停在关口：按 `docs/adm/governance/` 发起评审，由人批准后才新增 `aisep:ApprovalRecord`
   （MCP 可用时用 `governance.record_approval`）。**未经批准不进入业务架构阶段。**
