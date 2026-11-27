## ADR-014 · 2026-11-20

- **状态**：已采纳（设计会话 2026-11-20 拍板 Q1–Q6，及第二轮评审转来的 R2-13、R2-15）
- **决策**：MCP Server 接口按 `docs/mcp-interface.md` 定稿，元模型规范 §0、§3、§6.6、§6.7、§8.2、§8.3、§13、附录 C 按其 §9 改文同步。拍板结果：
  - Q1=B：工作台走本机 Streamable HTTP，只绑 `127.0.0.1`，CORS 精确白名单；开发期不加令牌为接受的风险，打包前必须定令牌方案。
  - Q2=A：批准提交缺省写会话分支；"待批准关口"读主分支，另查分支上"已批准、待合并"的标记。
  - Q3=A：headCommit 落后于分支头时，两者之间只允许批准提交（带 `AISEP-Evidence` trailer、只改一个模型的 governance 文件、源图只新增批准记录或 AI 活动）。
  - Q4=C：新增最小桩 `aisep:AIAgent`（⊑ `prov:SoftwareAgent`，aisep-core 对齐文件声明 `prov:SoftwareAgent ⊑ prov:Agent`，不加载 PROV-O）；`aisep:approvedBy` 只收 `arch:Stakeholder` 且排除 AI。
  - Q5=A：模型仓库禁用 squash 合并，**同时禁用 rebase 合并**，批准提交只经普通 merge 进受保护分支。
  - Q6=A：整体接受接口对规范字面的 8 项偏离（写工具只改工作区不提交、Approved 要求 gate 通过、删除时摘除 BPMN 成员属性、批准记录/AI 活动/模型不能删除、`record_approval` 不收 evidence/baseCommit/generatedAt 且 headCommit 必填、新增 IRI 规则、写前只拒新增违规、新增 `model.gate`），附两个条件：条件一 `model.diff` 可比较会话分支工作区的未提交改动（撤销 ADR-013 的"只比较已提交内容"）；条件二遗留违规经 `model.findings` 的 openViolations 查到，并在工作台可见。
  - 另由用户在另一会话拍板：新增 `model.set_labels`，作为"改名只改标签"的写入口。
  - R2-13：批准记录的 evidence 到分支头之间只允许批准提交，记录时（写入层）与合并时（CI，范围 `evidence..分支头`）用同一判据，合并时另在合并结果上跑 `gate`。
  - R2-15：主线上已有提交（如发布关口）的批准走短命批准分支 + PR，不给分支保护开例外；从被批准的那个提交拉分支，只含一个批准提交，PR 合入后删分支；不带 AI 活动（带了返回 `INVALID_ARGUMENT`）；只含批准提交的 PR 只做 R2-13 的核对与 `gate`，不再过关口，夹带其他改动按普通 PR，由 CI 判定；发布提交打 `release/{yyyymmdd}-{前 7 位}` 或版本号标签。
- **理由**：见 `docs/mcp-interface.md` §10.1 与文末"设计会话拍板记录""合并记录"。
- **后果**：规范 v0.4 中标为草案的 AgentActivity 与两个 MCP 工具转为定稿；实现按接口文档附录 D 的 GAP 项推进，验收看其 §11 的 T1–T42；squash/rebase 禁用、CI 必需检查属托管平台设置，元模型和 MCP 不检查（规范附录 C）。
