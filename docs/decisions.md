# AISEP 架构决策记录

每条记录含：编号、日期、决策、理由、后果。

## ADR-001 · 2026-11-19

- **决策**：采用裁剪后的 TOGAF ADM 作为方法论顶层框架。
- **理由**：目标是企业级可持续增长的系统，需要架构治理防止烟囱；完整 ADM 对超级个体过重。
- **后果**：保留愿景+业务架构、数据架构、应用+技术架构、需求管理中枢；预备阶段简化为架构原则文档；机会与迁移合并为路线图；治理与变更融入 SDLC 关口。

## ADR-002 · 2026-11-19

- **决策**：三层结构：基础设施层（模型仓库 + AI 接入）、方法论层（裁剪 ADM）、业务系统层。
- **理由**：方法论可调整而基础设施不动；平台一期范围收敛到基础设施层。
- **后果**：基础设施层不绑定任何方法论；工作台和业务系统都建在其上。

## ADR-003 · 2026-11-19

- **决策**：模型仓库底层统一为元素、关系、视图三原语，各记法作为上层方言。
- **理由**：跨记法追溯是平台灵魂；记法规则放上层，新增记法不改底层。
- **后果**：本质是一套文本 DSL，进 Git，图形界面只是渲染。

## ADR-004 · 2026-11-19

- **状态**：部分修正，见 ADR-010（"BPMN、UML 用上游现成对齐"不成立）
- **决策**：以 ArchiMate 4.0 为枢纽记法，其他记法通过子类对齐接入。
- **理由**：4.0 为 2026 年 4 月最新版，概念精简 30%，从零起步无包袱；子类对齐使一套查询穿透多记法。
- **后果**：BPMN、UML 用上游现成对齐；DDD 需自定义记法对齐到应用域；测试作为扩展属性而非独立记法。

## ADR-005 · 2026-11-19

- **决策**：确立五条架构原则：单一事实来源、模型即资产、全程可追溯、标准优先、自动执行人工把关。
- **理由**：见 principles.md。
- **后果**：所有架构决策、设计、代码和 AI 行为受其约束；决策记录本身也是资产，故建立本文件。

## ADR-006 · 2026-11-19

- **状态**：已采纳（2026-11-19，经 spike-workbench 验证后转正）
- **决策**：工作台以 Orchestrator.inc 为骨架，以私有镜像方式 fork；架构面板放在独立目录，以 fork 改前端的方式加入（不走插件，spike 证实插件机制不能加界面面板）。
- **理由**：Apache-2.0，近 30 天 900+ 次提交；关口审批、看板、多代理调度与需求直接对应；优先源头项目。spike 实测加一个面板改 16 个前端文件，约 20 分钟。详见 spike-workbench-result.md。
- **后果**：立即 fork，锁定 stable v0.15.3；AISEP 改动集中在独立目录，与上游接触面最小化；升级为显式动作，由 AI 辅助完成适配。GitHub 的 fork 只能公开，故采用私有镜像并保留 upstream remote。

## ADR-007 · 2026-11-19

- **决策**：采用 Linked.Archi core 0.6.0 + ArchiMate 4.0 作为基础设施层底座。
- **理由**：spike 通过（12 个负例、1200 条差分 0 分歧、AI 读写测试通过、跨模型评审反驳已修复）。详见 spike-linked-archi/spike-result.md。
- **后果**：必须自建闭世界规则、两层校验、写入层、影响分析口径；上游单人维护且全为草稿，按 SHA 锁定版本，升级为显式动作；跨记法追溯待单独验证。

## ADR-008 · 2026-11-19

- **决策**：一期交付物为 MCP Server，提供写入层、查表校验、SPARQL 查询、影响分析四项能力；工作台和编码代理均为其客户端。
- **理由**：单一事实来源；两次 spike 均指向它为接缝。
- **后果**：MCP Server 接口设计需同时满足两类客户端。
- **接口设计**：`docs/mcp-interface.md`（2026-11-20 定稿候选，由两个会话的稿件合并；Q1–Q6 已拍板，见其 §10；新增 `model.gate`、`model.set_labels` 两个对规范 §8.3 的扩展）。

## ADR-009 · 2026-11-19

- **决策**：批准记录作为模型仓库中的治理实体，不存放在工作台。
- **理由**：单一事实来源；更换工作台不丢历史。
- **后果**：元模型需定义批准记录实体及其与关口、元素的关系；工作台只展示和触发。

## ADR-010 · 2026-11-19

- **状态**：已采纳；修正 ADR-004 的"后果"一项
- **决策**：BPMN、UML 到 ArchiMate 4.0 的子类对齐由 AISEP 自行编写，作为独立的对齐模块（只放在 AISEP 自己的图里，不改上游词汇文件）；上游 SKOS 映射文件原样保留，仅作文档参考。
- **理由**：元模型调研（2026-11-19，带文件行号证据，已经复核）证实：上游 `bpmn_crossmappings.ttl` 只有 SKOS 近似映射（closeMatch/relatedMatch），不含任何 `rdfs:subClassOf`/`subPropertyOf`，对子类遍历的查询不可见；UML 没有任何到 ArchiMate 的映射文件。"泳道/参与者通过分配关系挂接"在上游也没有依据。
- **后果**：BPMN、UML 对齐工作量要单独排期：初版只把上游标为 closeMatch 的项升格为子类；多义概念（uml:Class、uml:Component、bpmn:Task/Lane）不做子类对齐，改用 `arch:refines` 显式连接；对齐模块默认不继承 ArchiMate 关系矩阵校验，避免误报。具体方案见《AISEP 第二步：元模型规范（草案）》§5、§6.2、§6.3、§10.2。

## ADR-011 · 2026-11-19

- **状态**：已采纳
- **决策**：元模型规范 v0.2 的 D1–D10 全部按建议采纳：DDD 的 BoundedContext ⊑ ApplicationComponent、Subdomain ⊑ Capability、Command ⊑ Event（可带载荷）；BPMN 的 Task/Lane 不升格，需要追溯的节点 refines 到 am4；作者只写限定关系；元素只允许一个最具体类型；影响分析分 depends（默认）和 ripple 两种模式；跨记法只允许枢纽关系、refines、追溯关系三类连接；refines 按 code→design→hub 层级、每种记法最多一个主锚；approvalState 由批准记录推导，不手填。
- **理由**：metamodel-prototype 已验证（84 项测试全部通过，14 条验收主张全部成立）；GPT 设计评审与原型对抗审计提出的反驳都已吸收进规范，见《AISEP 第二步：元模型规范（草案）》附录 B。
- **后果**：原型需要实现 v0.2 的改动（记法混用规则、refines 层级、批准记录、两种影响模式、派生捷径 Warning）；MCP Server 按规范 §8.3 的语义契约设计。

## ADR-012 · 2026-11-20

- **状态**：已采纳
- **决策**：元模型规范 v0.3 在 D1–D10（ADR-011）之上新增 14 条规则：
  - R1：模型文件不能修改元模型（只允许单父类特化，父类必须是具体类）。
  - R2：一个元素只属于一个记法。
  - R3：approvalState 只由合法批准记录推导；evidence 必填；同一时刻有冲突结论时报歧义。
  - R4：refines 指向已废弃节点时提示迁移。
  - G1：批准记录合法性只有一个定义，L1、L3 和推导共用。
  - G2：关口只能来自模块定义。
  - G3：evidence 必须是 git commit 或 sha256。
  - G4：日期格式严格校验。
  - G5：核心的 Association/HasPart/DependsOn 也受记法混用规则约束（DependsOn 由 core 0.7.0 新增，PR #103 补入；原文只列前两者）。
  - G6：禁止继承抽象根类。
  - G7：模型文件里的谓词也是闭世界。
  - G8：isReplacedBy 的目标必须是模型元素。
  - G9：模型有违规时 impact 拒绝输出。
  - G10：提交和 CI 只认统一入口 `gate`（原子执行 L0–L4）。
- **理由**：三轮原型对抗审计和第二次 GPT 跨模型评审发现的漏洞，每一条都能绕过 D1–D10 已经定下的规则（单一事实来源、一个元素一个类型、跨记法只允许三类连接、批准由记录推导）。修补后，metamodel-prototype 的 148 项测试全部通过，独立复核确认，合法模型和例子 0 误报。详见《AISEP 第二步：元模型规范（草案）》附录 B.2。
- **后果**：模型作者（包括 AI）的写法受到更严格的约束，MCP Server 的写入工具需要在写入前执行这些规则；G7 的"元素间直连"白名单（BPMN 结构属性等）是判断性的，未经异构评审，扩展新记法时要复核；已知限制见规范附录 C。

## ADR-013 · 2026-11-20

- **状态**：已采纳（设计会话 2026-11-20 答复；元模型与 MCP 部分已由 ADR-014 定稿；2026-11-20 设计会话拍板时修订"后果"中的 diff 限制（见下））
- **决策**：工作台"AI 进行中"区域的运行态读编排器（AO 会话）；改动元素不存储，由 Git 分支差异（`model.diff`，起点为 merge-base）实时算出；只在任务过关口时，经 `governance.record_approval` 往模型仓库写一条已完成的 `aisep:AgentActivity` 并与批准记录关联。区域每一行是一个编排器会话，显示代理、任务、状态和改动元素数量，共享键是分支名。
- **理由**：进行中是运行态，不是资产，不进 Git；被改动的元素已经是分支上 Turtle 文件的差异，再存一份违反单一事实来源；历史和关联在关口处低频落盘，符合 ADR-008、ADR-009 和规范 §8.3"MCP 不保存文件外状态"。
- **后果**：元模型 v0.4 新增 `aisep:AgentActivity`（§6.7）和 `aisep:activity`（§6.6），MCP 新增只读 `model.diff`、修改 `governance.record_approval`（§8.3），不新增任何上报进行中状态的写工具；工作台读 AO 的代码收在 `aisep/data/` 下的一个适配器里，依赖的接口登记进 `workbench/UPSTREAM.md`；已知限制：要求模型与代码同仓同分支（规范附录 C）。（2026-11-20 修订：原"v1 只比较已提交内容"撤销。MCP 写工具只改工作区不提交，只比已提交内容会让"AI 进行中"在批准前一直为空；`model.diff` 改为也能比较会话分支检出的工作区，按分支名定位、不接受路径，"AI 进行中"缺省用这一模式；关口页差异图和批准仍只认已提交的 commit。）

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

## ADR-015 · 2026-11-20

- **状态**：已采纳（设计会话 2026-11-20 拍板第三轮评审转来的 U1–U4，均按推荐；ADR-014 不改，本条在其上收紧）
- **决策**：第三轮评审（GPT 异构 + Claude Git 语义 lens + Claude 对抗绕过 lens，32 条归并为 18 簇）后，`docs/mcp-interface.md` §5.9 与规范 §6.6、§8.3、附录 C 按其 §9 改文同步。拍板结果：
  - U1 改动已批准元素须重批：CI 拦截，不改元模型。普通 PR 中被修改、在目标分支头上 approvalState=Approved 的元素，同一 PR 里必须有一条新增且通过逐条核对的合法批准记录覆盖它，否则拒绝合并；删除这类元素一律拒绝（只能退役，沿用 Q6④）。
  - U2 批准记录分文件：`governance.record_approval` 每条记录新建一个 `models/<slug>/governance/<记录本地名>.ttl`（活动块（如有）+ 记录块），只提交这一个新路径；批准提交判据改为只在一个模型的 `governance/` 目录下新增文件，不修改、不删除任何已有文件；已有 `governance.ttl` 的记录与人员不搬迁（IRI 不变），它仍是 Stakeholder 等治理类元素的缺省写入文件。
  - U3 合并前重算：不开"要求分支最新"、不用合并队列（个人账号的 private 仓库不可用）；执行合并的人（目前是 AI 按「批准 #N」代合并）在 `gh pr merge` 之前，用同一个检查脚本对当前目标分支头重跑合并时校验与合并结果 `gate`，不过不合。
  - U4 批准专用 PR 收紧：① 主线提交（按有效内容提交判定，接口文档 §5.9 第 1 步；第四轮 R4-13 补注）上的批准只允许发布关口，其他关口返回 `INVALID_ARGUMENT`（`mainline-head-gate-not-release`）；② 批准专用 PR 只免"再过 AISEP 关口"，仍须人工 PR 批准（AGENTS.md「批准 #N」）；信任模型维持（真正的约束是代码评审和分支保护），不引入签名。
  - 同轮按处置矩阵收紧的合并时校验：批准提交的 trailer 值须等于所新增记录的 evidence；目标分支上已有的批准记录与 AI 活动不得修改或删除；查本 PR 新增的全部合法记录（只豁免同一 PR 内被同关口、approves 为超集、时间更晚的新记录取代的）；新记录 evidence 须是 40 位 commit、生成时间不得晚于检查时的当前时间 5 分钟以上（不与可伪造的提交时间比）；新增活动的 baseCommit、branch 须与重算值一致；ref 口径与完整克隆写死；发布批准的对象在 evidence 到目标分支头之间不得被改动；只有 Approved 的发布批准打 release 标签，按剥离到 commit 的值检查；标签不再被视为防 GC 手段。
- **理由**：两条分支各往 `governance.ttl` 末尾追加记录必冲突，托管平台的服务端合并大概率不遵守 `merge=union`；CI 通过后主线前进不会自动重跑必需检查，合并队列在个人 private 仓库不可用；批准专用 PR 的判据只验证提交形状，可被手写伪造；修改已批准元素后旧批准仍让它显示为 Approved。详见 `docs/mcp-interface.md` §10.1 末四行与文末"第三轮（2026-11-20，R2-13/R2-15 拍板后）"。
- **后果**：合并时校验与合并前重算要新写一个检查脚本（接口文档附录 D 的 GAP），未实现前这些规则只在文档里；验收新增 T43，T38–T40 补负例；残余风险登记规范附录 C：绕过脚本直接点网页合并时合并结果 gate 可能只对旧主线有效。（第四轮 R4-14 更新现状）本仓库 `main` 已于 2026-11-20 配置分支保护（必需检查 `gate`、不要求最新、禁 force push 与删除、管理员受约束）并只允许普通合并，`release/*` 标签由规则集 `release-tags-immutable` 禁删禁移（无绕过者）；这些规则被停用或放宽时，Q5 的可达性保证与标签不可变随之失效，为残余风险。

## ADR-016 · 2026-11-20

- **状态**：已采纳（用户 2026-11-20 拍板第四轮评审转来的 5 题；ADR-014、ADR-015 不改，本条在其上补充）
- **决策**：第四轮评审（只评第三轮修订本身：GPT `gpt-5.6-sol-high` 14 条 + Grok `grok-4.7-high` 红队 7 条，每条经文档对照与可执行探针两路独立核实）后，`docs/mcp-interface.md` §5.9 与规范 §6.6、附录 C 同步修订。拍板结果：
  - R4-1 普通 PR 不要求带批准记录：未经批准的模型改动可以进主线，在主线上推导为 Proposed，由"待批准关口"列出（维持 Q2=A）。已知限制：主线提交只能批 `GateRelease`（ADR-015 U4①），主线上的 Proposed 元素要过其他关口，须从主线拉分支、先有一个非批准提交（可以是空提交）再批；登记规范附录 C。
  - R4-2 U1 的覆盖记录须为 `decision = Approved`，关口不限（approvalState 不分关口）。另按 R4-3，覆盖记录须是该对象在合并结果中生效的那条。
  - R4-5 `aisep:approves` 的允许集合：带 `arch:inModel` 的元素（不含 `aisep:ApprovalRecord`、`aisep:AgentActivity`、`arch:Stakeholder`）、`arch:Model` 实例、ADR；限定关系和视图不可被批准，改动只计入所属模型、不计入端点元素（与 G4-4 一致）；目标存在但类型不合法的记录不合法，目标不存在的按原口径处理。
  - G4-4 元素级批准不覆盖以它为端点的限定关系：只改关系端点不触发对端点元素的重批；要约束连接，按模型批准。理由：否则每加一条代码追溯（`aisep:Implementation`）都会触发对设计元素的重批。登记规范附录 C。
  - R4-7 记录与活动的缺省 IRI 改用秒级 UTC 时间（`{yyyymmddHHMMSS}`），不加随机量；同一秒内跨分支并发批准同一提交同一关口仍会撞名，登记为残余风险。
- **理由**：核实确认，普通 PR 不带记录能过全部检查项，与治理模板"没有批准记录的变更不进主分支"矛盾；用户选择维持 Q2=A 的"主线可有 Proposed"，改模板而不加检查项。Rejected 记录不是"重批"；推导会给任意目标产生 approvalState，规范文字与代码不一致；同一天对同一提交同一关口的两次批准会生成同名文件。
- **后果**：合并时校验脚本的范围随之增加（evidence 上重跑 gate、生效记录核对、文件形状、本地生成合并结果、合并后核验父提交），`approval_problems` 要加目标类型检查（接口文档附录 D 的 GAP）；T23、T38、T43 补第四轮负例；"主线 Proposed 补批要先有一个非批准提交"是已知限制，日后若成为实际阻碍，再议 U4① 的范围。

## ADR-017 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板第四轮复评转来的 4 题，均按推荐；ADR-014、ADR-015、ADR-016 不改，本条在其上补充）
- **决策**：第四轮复评（主评 GPT `gpt-5.6-sol-high`、红队 Grok `grok-4.7-high`，blocker 0、major 2、minor 5）后，拍板结果：
  - R2 合并前后三步写进 `AGENTS.md`「分支与合并」第 2 条：① 合并前用 `python -m aisep.mergecheck --pr-head H --head-ref <分支> --target main` 对当前目标分支头重算；② 用 `--target-unchanged T` 复核目标分支没动；③ 用 `gh pr merge --merge --match-head-commit H` 合并，合并后跑 `--post-merge`，不通过就开 revert PR。合并提交说明记下 T、H 和结果。先只写进文档，不另做封装命令。
  - R3（选 A）`arch:inView` 计入视图、不计入元素，与接口文档 §5.8 一致：只改已批准元素的视图从属不算修改该元素，不触发重批。接口文档 §5.9「对象的比较范围」补注，规范附录 C 登记，`aisep-mcp/tests/` 加正例固定口径。
  - R4（选 B）没有批准记录的 `arch:Model` 与 ADR 不推导为 Proposed，只在有记录后才有 approvalState，不进「待批准关口」。规范 §6.6 的括号改为「元素部分与允许集合一致；模型、ADR 只在有记录时有状态」。
  - R7（维持现状）第四轮负例 `test_merge_check_negatives.py` 仍不进 CI（Albert 2026-11-20 的取舍不变）；「涉及 mergecheck 的 PR 合并前须在本地跑它」从 `gate.yml` 的注释搬进 `AGENTS.md` 合并条款。
- **理由**：分支保护不要求分支最新，目标分支前进后必需检查不重跑，重算、复核、合并后核验由工具实现了却没进合并流程（R2）；视图不可被批准，把视图从属算进元素会让调整视图触发对元素的重批（R3）；把模型、ADR 计入缺省 Proposed 需要改推导和关口查询，收益小，规范括号只需与实现对齐（R4）；负例单跑约 21 分钟，按路径触发的必需 job 成本高于收益，但本地必跑的要求要放到执行合并的人会读的地方（R7）。详见第四轮复评报告。
- **后果**：R2、R7 仍只靠执行合并的人照做，没有机制强制，登记规范附录 C；R3 的口径下，视图在未批准模型里时，没有检查项能看到已批准元素的视图从属变化，登记附录 C。同轮不需拍板的修订一并落地：规范 §6.7 活动复用键改为 `(sessionRef, headCommit, branch)`（R5）；规范附录 C、接口文档与 `gate.yml` 注释里「脚本未实现」「必需检查只有 gate」的过时说法改为现状（必需检查 `gate`、`mergecheck`、`pytest`，脚本已实现）（R6）。R1（批准提交判据放行空白节点主语）改代码，另行处理。

## ADR-018 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板，经协调会话转达）
- **决策**：删除 `vendor/` 中未被使用、且未声明许可的文件，不算规范 §11 所说的"升级上游"，不需要批准记录，走普通 PR。判断是否声明了许可，要同时看文件自身（`cc:license`、`dcterms:license` 等）和上游 catalog 按数据集的声明（`ttl/catalog.ttl` 中 `dcat:Dataset` 的 `dcterms:license`）。本次按此只删除 `vendor/meta.linked.archi/llms.txt`，来源与理由见该目录的 `REMOVED.txt`。
- **理由**：仓库已公开并采用 Apache-2.0，没有许可声明的第三方文件会带来许可风险。`llms.txt` 不来自 `ttl/` 那次抓取，自身没有许可声明，catalog 里也没有它的条目，AISEP 也没有任何地方引用它。PR #31 的 NOTICE 只看了文件自身的 `cc:license`，把另外 14 个文件也算作无许可：其中 `catalog.ttl` 用 `dcterms:license` 声明了 CC BY 4.0；其余 13 个由 `catalog.ttl` 按数据集逐一声明为 CC BY 4.0。这 14 个都保留。
- **后果**：被删文件记入 `REMOVED.txt`；`FETCHED_AT`、`fetch.log`、`urls.txt`、`SHA256SUMS` 不变。`NOTICE` 把那 13 个文件改列为"许可由 catalog.ttl 按数据集声明为 CC BY 4.0"。以后核对 vendor 许可，两处声明都要看。

## ADR-019 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板「采用流程调整」及第一条链路的载体与范围，经规划会话转达；自合入 `main` 起生效，合入之前所有 PR 仍按当时的 `AGENTS.md` 走合并前独立评审）
- **决策**：进入第一条端到端链路阶段，合并与评审流程按下面七条调整。
  1. **评审按路径分级，默认合并前评审，只按白名单放行。** PR 改到的每一个路径（新增、修改、删除，改名的两端都算）都落在下面的白名单内、且都是模式 100644 的普通文件（按 `git diff --raw` 判断：新增看新侧，删除看旧侧，修改与改名两侧都看；120000 符号链接、160000 gitlink、100755 都不算）时，才可以合并后评审；否则一律合并前独立评审（评审人没参与该 PR 的实现、也没写它的测试）。白名单只有三类：① `docs/` 下的 `.md` 文件，但不含：`docs/principles.md`、`docs/decisions.md`、`docs/metamodel-spec.md`、`docs/mcp-interface.md`、`docs/methodology.md`、`docs/module-contract.md`；`docs/adm/governance/**`（关口评审的模板与提示词）；任意层级的 `docs/adm/**/prompt.md` 与 `docs/adm/**/template.md`（各阶段 AI 的提示词与模板，含护栏）；任意层级名为 `CLAUDE.md`、`CLAUDE.local.md`、`AGENTS.md` 的文件，以及路径中含 `.claude/` 的文件（代理会把它们当项目指令自动加载）。这些排除项的文件名与目录名都按不区分大小写比较（APFS 等文件系统上 `claude.md` 与 `CLAUDE.md` 是同一个文件）；② `docs/queries/` 下的 `.rq` 文件；③ `models/` 下的 `.ttl` 文件，且 PR 不新增任何 IRI（IRI 一经创建不改）。仓库根目录的任何文件、新增的顶层文件或目录、`aisep/**`、`aisep-mcp/**`、`tests/**`、`tools/**`、`modules/**`、`vendor/**`、`.github/**`、`.githooks/**` 等都不在白名单内，一律合并前评审。合并前评审的结论写成 PR 评论并注明评审的提交 SHA。合并后评审：PR 在全部必需检查通过（以分支保护设置为准）后即可合并；合并后由协调会话立即派出同样独立的评审人，并跟踪到结论贴出为止；结论写成 PR 评论并注明评审的提交 SHA，发现阻塞问题就开修复 PR 或 revert PR。协调会话合并前用 PR 的文件清单（`git diff --raw`，含改名与文件模式）和模型差异判定走哪一级，拿不准按合并前评审。两级都照走 `AGENTS.md` 的合并前重算、复核目标分支、合并后核验三步。
  2. **治理加固冻结在现状。** 范围：`docs/mcp-interface.md` §5.9 的规则、合并时校验（`mergecheck`）、批准提交形状、并发边角情形、发布标签，不再开新的评审轮，也不开加固 PR。例外：AI 能绕过门禁或代人批准的漏洞照修。MCP 入口参数校验（写工具与只读工具对调用方传入参数的校验）不在冻结范围内，照常做；但不能借它修改冻结范围内的判据（如批准提交形状、合并时校验），除非属于上面的漏洞例外。冻结期间发现的其他治理问题记进 GitHub issue，不当场修。出现下面任一情形就恢复加固：① 出现第二个批准人或使用者；② 有外部数据或受监管数据进入模型；③ HTTP 服务不再只绑本机。ADR-014 至 ADR-018 已有的规则继续有效，只是不再加固。
  3. **批准提交豁免重评。** PR 在头提交 H0 上评审通过后，新的头 H 同时满足下面四条时不再重评：① H 只有一个父提交，且 `git rev-parse H^` 等于 H0；② `git diff --raw H0 H` 恰好一行，状态为新增（`A`）、模式 100644，路径形如 `models/<slug>/governance/<名>.ttl`；③ 核对前先 `git fetch origin`，下面的 `$PY -c` 命令在最新 `origin/main` 的干净检出里执行，不在 PR 分支的检出里执行（`-c` 会把当前目录放进 `sys.path`，PR 带来的同名模块会顶替依赖）；H 是一个合法批准提交，且批的正是 H0：`$PY -c "from aisep import mergecheck as m; print(m.approval_commit_problems('.', 'H0', 'H'))"` 输出 `[]`（它核对 §5.9 第 1 步判据：新文件里恰好一条 `aisep:ApprovalRecord`、至多一个它引用的活动、没有别的主语、没有空白节点、trailer 等于记录的 `aisep:evidence`），`git log -1 --format='%(trailers:key=AISEP-Evidence,valueonly)' H` 等于 H0，且这条记录被 `mergecheck` 选中（`_Analysis.selected`，即合法、未被同一 PR 里更新的记录取代；`mergecheck` 命令行不输出这一项，由协调会话的豁免核对脚本核对）；④ 合并前重算的 `mergecheck` 输出 `problems` 为空。①②③由协调会话机械核对（命令如上，H0、H 填 40 位 SHA，可由协调脚本执行），④由 `mergecheck` 判定。任何一条不满足（包括分支被强推、H0 不再是 H 的父提交、新增的不是批准记录），就对新的头重评。
  4. **修订 ADR-017 R7。** 第四轮负例 `test_merge_check_negatives.py` 可以作为非必需 job 进 CI；在它升为必需检查之前，「涉及 mergecheck 的 PR 合并前须在本地跑它并全绿」仍然有效，CI 上这个 job 的结果不拦合并，也不代替本地跑。这一条在 CI 加没加这个 job 时都成立。把它升为必需检查、以及 CI 上通过能否代替本地跑，由 Albert 另定。
  5. **规范 PR 只写已合入 `main` 的行为。** 规范文档（`docs/mcp-interface.md`、`docs/metamodel-spec.md` 等）不描述尚未合入 `main` 的实现；接口契约的变更与实现它的代码放在同一个 PR 里。
  6. **ADR-015 中「批准 #N」的说法以现行 `AGENTS.md` 为准。** U3 的「目前是 AI 按「批准 #N」代合并」与 U4② 的「仍须人工 PR 批准（AGENTS.md「批准 #N」）」，现指 `AGENTS.md`「分支与合并」第 2 条的自动合并：必需检查通过、按本条第 1 款评审通过后，由协调会话合并。批准专用 PR 在 `models/**` 下新增批准记录的 IRI，按第 1 款走合并前评审。
  7. **第一条端到端链路的载体与范围。** 载体是工作台的「批准进度展示」，四个阶段为待批准 → 已批准待推送 → 已推送待合并 → 已合入，全部从 Git 推导，不存进行中状态（ADR-013）。本期范围：第一条链路（AI 经 MCP 写模型 → 固定查询从代码查回业务能力 → Albert 在工作台批准 → 进度走到「已合入」）、批准进度展示、从待批准关口进入关口页的入口、一键启动脚本。链路用新建的模型目录，不动 `models/procurement`。批准只能由 Albert 本人在工作台做出。
- **理由**：三天内合并了 35 个以上 PR，其中约三成实现代码、近半测试用于批准与合并校验，经过四轮跨模型评审，而 `models/` 只有建仓时的一次提交，没有任何真实需求走通链路。对抗式评审没有自然终点，每轮发现都变成新的规则、测试和文档。另一方面，本机 MCP 仍有攻击面，约束 AI 的门禁不能放松，所以默认仍合并前评审，能让 AI 绕过门禁或代人批准的漏洞仍照修。MVP 方案草案按列举写核心清单，列举总有遗漏：评审实测，在仓库根目录放一个与依赖同名的 `.py` 文件，就能让 `python -m aisep.mergecheck` 输出 `problems=[]` 并以 0 退出（`-m` 把当前目录放进 `sys.path` 首位，CI 与工具都在仓库根目录运行）；测试夹具、`conftest.py`、`pytest.ini` 等削弱后也等于绕过门禁。所以改为默认合并前评审、只按白名单放行，白名单只放不会被执行、也不会被代理当作指令加载的说明文档、查询和模型数据。新增 IRI 的模型 PR 合并后就无法撤回 IRI，故不放进合并后评审。批准提交只能由 Albert 在工作台做出，其形状由 `mergecheck` 逐项核对，评审人重看它没有新增信息；但 `mergecheck` 不知道评审过的头，也只对被选中的新批准记录核对提交形状，所以「只多这一个提交」和「它确实是批准提交」都须由协调会话机械核对：评审实测，H0 之后只新增一个 `governance/*.ttl`、内容却是一个新的 `arch:Stakeholder` 时，`mergecheck` 仍输出 `problems=[]`。负例已提速（PR #26 开 xdist 后单跑约 431 s），适合放进 CI 观察，但升为必需检查之前不能削弱 ADR-017 的本地保障。规范写进未合入的实现细节最先过时。
- **后果**：`AGENTS.md`「分支与合并」第 2 条同步改为分级评审，列出白名单、批准提交豁免的核对条件和两种合并说明文案；负例条款的文件清单补上 `aisep/writer.py`（`approval.py` 依赖它）。旧 ADR 原文不改：ADR-017 R7「仍不进 CI」由本条第 4 款修订；ADR-017 后果中「R2、R7 仍只靠执行合并的人照做，没有机制强制」在负例升为必需检查之前仍然成立；ADR-015 U3、U4② 按第 6 款理解。`docs/mcp-interface.md` 第 748 行「仍须人工 PR 批准（AGENTS.md「批准 #N」）」同样按第 6 款理解，正文的更正留给改该文件的 PR。日后若把 `docs/mcp-interface.md` 的评审记录、实现镜像等章节（§3.1、§9–§11、附录与文末「附」）移入 `docs/history/`，ADR-014 至 ADR-017 对这些章节的引用以迁移 PR 留在原位的指引为准。负例 job 升为必需检查、CI 上通过能否代替本地跑，留给 Albert 定。跨模型评审的使用范围不在本条内。

## ADR-020 · 2026-11-21

- **状态**：已采纳（补登记：下列决定均已由 Albert 拍板并在执行，此前没有写进本文件；本条只登记，不新增决定）
- **决策**：
  1. **自动合并（Albert 2026-11-20 定）。** PR 不再逐个等 Albert 批准：CI 的全部必需检查通过、独立评审通过，即可合并，具体条款见 `AGENTS.md`「分支与合并」第 2 条（提交 9f1b9fe 写入，评审分级按 ADR-019 第 1 款）。Albert 在会话里明确说「先别合 #N」时不合。这一条只管代码与文档 PR 的合并，模型里的批准记录仍只能由 Albert 本人做出。
  2. **只由协调会话合并（2026-11-20，与上一款同时定）。** 协调会话是唯一执行合并的会话；开 PR 的会话只开 PR、回报，不自己合并。
  3. **测试由独立方先写。** 测试由不做该实现的一方先写，实现方不改别人写的断言；评审人也不能是写该 PR 测试的一方。
  4. **aisep 公开并采用 Apache-2.0。** 本仓库为公开仓库，许可证为 Apache-2.0（LICENSE 与 NOTICE 由提交 f76f335 于 2026-11-21 加入）；`vendor/` 下的第三方文件保留各自的许可（ADR-018）。
  5. **workbench 公开（Albert 2026-11-21 定）。** `Albertsun6/aisep-workbench` 改为公开仓库，PR 走「CI 通过 + 独立评审」的合并流程。这一款修订 ADR-006 后果中「采用私有镜像」的说法；ADR-006 其余内容（以 Orchestrator.inc 为骨架、AISEP 改动集中在独立目录、锁定上游版本、升级为显式动作）不变。
  6. **根命名空间继续用占位符，之后统一迁移。** IRI 根命名空间继续使用 `https://aisep.example/`，到统一迁移时一次替换；在那之前不自行更改（`AGENTS.md` 硬规则第 5 条）。
- **理由**：这些决定已在 `AGENTS.md`、协调会话交接和规划文件里执行，但 `docs/decisions.md` 里没有对应条目，与 ADR-005「决策记录本身也是资产」不符；其中 workbench 公开与 ADR-006 的原文矛盾，Apache-2.0 只在 ADR-018 的理由里顺带提到。workbench 公开的原因是项目本来就要开源，且私有仓库的 Actions 因计费跑不起来。
- **后果**：ADR-006 原文不改，「私有镜像」一句以本条第 5 款为准。负例不进 CI、必需检查为 `gate`、`mergecheck`、`pytest`，已由 ADR-017 登记，负例一项由 ADR-019 第 4 款修订，不在本条重复。

## ADR-021 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 对 PR #42 回报里四个待定问题的答复，第 1 款经他再次确认；ADR-019、ADR-020 原文不改，本条在其上补充）
- **决策**：
  1. **批准专用 PR 免独立评审，改由机械核对。** 批准专用 PR（ADR-014 R2-15：从被批准的提交 E 拉出、只含一个批准提交 C 的短命分支）同时满足下面四条时，合并前、合并后都不需要独立评审，必需检查通过即由协调会话合并：① C 只有一个父提交，等于 E，且 E 是 `origin/main` 上的提交（`git merge-base --is-ancestor E origin/main`）；② `git diff --raw E C` 恰好一行，是模式 100644 的 `models/<slug>/governance/<名>.ttl` 新增（`A`）；③ 按 ADR-019 第 3 款③核对（H0 取 E，H 取 C）：`approval_commit_problems(E, C)` 为空、trailer 等于 E、记录被 `mergecheck` 选中；④ 合并前重算的 `mergecheck` 输出 `problems` 为空。①②③由协调会话机械核对（可由协调脚本执行），④由 `mergecheck` 判定。任何一条不满足，就按 ADR-019 第 1 款走合并前评审。这一款是 ADR-019 第 1 款（`models/**` 下新增 IRI 走合并前评审）的例外，也修订 ADR-019 第 6 款末句「批准专用 PR……按第 1 款走合并前评审」；ADR-020 第 1 款「必需检查通过、独立评审通过即可合并」对批准专用 PR 按本款执行，不要求独立评审。因为①要求 E 已在 `main` 上，而主线提交上的批准只允许发布关口（ADR-015 U4①），本款实际只适用于发布关口的批准专用 PR；分支上新做的批准仍随所在 PR 合并，适用 ADR-019 第 3 款的批准提交豁免。
  2. **跨模型评审的使用范围（Albert 授权由 AI 定）。** 只用于不可逆或合入后难撤回的设计：IRI 方案与根命名空间迁移、元模型（`modules/**`）的语义变更、MCP 对外接口契约、批准与合并判据。每个设计限一轮，有新证据（新的实测失败或新需求）才追加一轮；评审意见要有实跑测试或探针支撑才据以改规则或代码。每次发起前先问 Albert。普通 PR 的评审仍用 ADR-019 第 1 款的独立评审，不另做跨模型评审。
  3. **批准提交豁免确认为已拍板。** ADR-019 第 3 款（批准提交豁免重评）经 Albert 2026-11-21 确认。
  4. **aisep 公开的拍板日期。** ADR-020 第 4 款「aisep 公开并采用 Apache-2.0」由 Albert 2026-11-21 定，是在私有仓库的 GitHub Actions 需要付费时决定公开的。
- **理由**：批准专用 PR 的内容只有 Albert 在工作台做出的一条批准记录。它的形状、合法性和是否生效，`mergecheck` 与 ADR-019 第 3 款的机械核对已逐项覆盖；批准是否真由 Albert 本人做出，评审人同样无法验证（ADR-015 U4② 的信任模型），重看不增加可靠性，只增加等待。所以在保留全部机械核对的前提下去掉人工评审，这是 Albert「可靠前提下尽量精简」的要求。跨模型评审：前四轮的经验是多轮、多模型评审误报上升而收益递减，没有自然终点；但不可逆的设计一旦合入就无法撤回，值得多花一轮。
- **后果**：`AGENTS.md`「分支与合并」第 2 条补上批准专用 PR 的核对条件和第三种合并说明文案，「工作方式」补一句跨模型评审的范围。`docs/mcp-interface.md`「批准专用 PR」一段原写「仍须人工 PR 批准（AGENTS.md「批准 #N」）」，同步改为按本条第 1 款执行。残余风险不变：有写权限的人或代理仍能手写一个形状合法的批准提交，挡住它的是「AI 不得新增批准记录」的硬规则与分支保护，不是评审。

## ADR-022 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板，经规划会话转达；修订 ADR-017 R7 与 ADR-019 第 4 款，两者原文不改）
- **决策**：
  1. **负例改认 CI 结果。** 改到负例清单里文件的 PR（清单不变，见 `AGENTS.md`「分支与合并」第 2 条），合并条件由「合并前在本地跑第四轮负例并全绿」改为「本次合并的 PR 头 H 上，CI 的 `negatives` job 结论为 `success`」。协调会话合并前用 `gh api "repos/Albertsun6/aisep/commits/H/check-runs?check_name=negatives&filter=latest" -q '[.check_runs[]|select(.app.slug=="github-actions")|.conclusion]'` 核对：输出必须恰好是 `["success"]`（只取 GitHub Actions 的最新一次运行，恰好一条），并把结论记进合并说明；H 上没有这次运行、还没跑完、多于一条，或结论不是 `success`（含 `cancelled`），就不合并。PR 同时改了 `.github/workflows/**` 时，它的 CI 跑的是 PR 自己的工作流定义，结论不可信，改为在本地跑负例并全绿。CI 不可用时也可以退回本地跑，这只是退路；两种情形都在合并说明里写明用了本地跑。
  2. **`negatives` 不升为所有 PR 的必需检查。** 它在 runner 上实测 304 到 691 秒，其余分片 150 到 290 秒，升为必需会让所有 PR（含纯文档）多等几分钟。以后升不升，仍由 Albert 定。
- **理由**：Albert 原话「如果替代后简化了，就替代」。替代后省掉协调会话每次合并前约 4 分钟的串行本地运行，也不再和本机其他任务抢 CPU；CI 的 `negatives` 与评审并行，不在关键路径上。只对改到负例清单的 PR 核对它，其余 PR 不受影响。
- **后果**：残余风险：PR 事件的 CI 跑在触发时的合并结果上，合并时 `main` 可能已前进，H 上的 `success` 不覆盖新的 `main`。兜底是 push 到 `main` 之后 `negatives` 还会再跑一次：协调会话合并这类 PR 后，在合并后核验里等新的 `main` 头 M 上的 `negatives` 跑完，用同一命令（H 换成 M）取结论写进 PR 评论，不是 `success` 就开 revert PR 并报告 Albert。ADR-017 后果中「R7 仍只靠执行合并的人照做，没有机制强制」仍然成立（核对由协调会话执行，不是分支保护）。`AGENTS.md` 负例条款同步改；协调脚本 `merge_pr.sh` 的 `NEG=1` 一步要改为核对 H 上 `negatives` 的结论（仓库外，由协调会话改）。本地 `tools/aisep.py test` 仍包含负例，开发时自测照旧。

## ADR-023 · 2026-11-22

- **状态**：已采纳（Albert 2026-11-22 拍板，经规划会话转达；补记 PR #78，属 ADR-019 第 2 款冻结范围内的合并判据变更）
- **决策**：
  1. **治理记录必须是带 `arch:inModel` 的 IRI。** 批准记录（`aisep:ApprovalRecord` 及其子类）与 AI 活动记录（`aisep:AgentActivity` 及其子类）是空白节点或没有 `arch:inModel` 的，L1 判违规（元模型规范 §6.6、§6.7）。这样的批准记录被 approvalState 推导忽略；这样的活动不进推导，但引用它的批准记录被判为不合法，因而同样被忽略。L1 只检查有没有 `arch:inModel`，不核对它的值，值不对的情形由 L3 和 mergecheck 兜住。
  2. **合并判据对空白节点另设一道不依赖 gate 的检查。** PR 头 H 与合并结果 M 的模型源文件里，被引用的这类空白节点报 `governance-blank-node`（`docs/mcp-interface.md` §5.9 检查项 8）；无人引用、被共享或成环、图差异算不出的空白节点报 `check-error`（§5.8）。两种都拒绝合并。对空白节点，两层各自成立，关掉任一层另一层仍能拦住；没有 `arch:inModel` 的 IRI 记录只靠第 1 层。
- **理由**：2026-11-22 的取证（三路实测加独立证伪）发现，被具名主语引用的空白节点批准记录能通过 gate 与 mergecheck，推导却认它：未经批准的内容会被推导为已批准，已批准的元素也会失去保护。规范 §3 本就要求模型成员是 IRI，这里把它明确到治理记录，并在合并判据里机械强制。治理加固虽然冻结，但「AI 能绕过门禁或代人批准的漏洞照修」。不做跨模型评审：两位评审人合计构造了 9 类绕过，并验证了对空白节点两层各自独立。
- **后果**：未覆盖：批准记录是否出自 Albert 本人（另由签名方案处理，见 2026-11-22 的调研）；ext-governance 的 L3 没有镜像这条规则；第 2 层的谓词清单是硬编码的，不覆盖空白节点作类；评审遗留的 5 条 minor 另开 PR 处理。

## ADR-024 · 2026-11-25

- **状态**：已采纳（Albert 2026-11-25 在协调会话拍板「按清单改」；临时放宽；自合入 `main` 起生效）。修订下列条款的适用范围，各自原文不改：ADR-019 第 1 款（评审分级及其末句「两级都照走三步」）；ADR-017 的三步合并与 R2 末句「合并提交说明记下 T、H 和结果」；ADR-015 U3 与 `docs/mcp-interface.md` §5.9「合并前重算」中「执行合并的人对每个 PR 重算」的说法；元模型规范 §11；`docs/adm/**/template.md` 出口条件里的关口评审项。
- **决策**：可追溯、可审计、可复现三个质量目标的**校验与留痕**在 MVP 期间放宽，先让模型能建、能查、能出图（含 C4 与 ArchiMate 4 双模型）。数据采集和安全约束不动。
  1. **评审分级只放宽模型数据。** 新增 IRI 的 `models/` 下的 `.ttl`（不含 `models/<slug>/governance/**` 与 `models/<slug>/governance.ttl`）由合并前评审改为合并后评审。`vendor/**` 与 `modules/**` **暂不放宽**：本条的独立评审实跑证明，在任一模块文件里声明 `aisep:ApprovalRecord` 的子类，用它做类型的记录会被 approvalState 推导认可（推导读全部模块与 vendor 的并集图），却不进 `mergecheck` 的记录检查（它只看模型文件里的类链），gate 与 mergecheck 都通过；合并前评审是目前唯一的拦截点。等 `mergecheck` 的记录识别改用与 `check_bnodes` 相同的类闭包并补上负例后，由 Albert 决定是否把这两个目录的 `.ttl` 放进合并后评审。
  2. **三步合并缩小范围。** 合并前重算、复核目标分支、合并后核验只对改到 `models/**`、`modules/**`、`vendor/**` 或负例清单的 PR 执行；其余 PR 必需检查通过、评审条件满足后直接合并（仍用 `--merge --match-head-commit H`）。拿不准就执行三步。
  3. **合并说明不再记 T、H 与各步结果。** `negatives` 结论照旧记。
  4. **上游升级不要求批准记录。** 元模型规范 §11 的「人工批准（一条批准记录）」暂停，差异报告写进 PR 即可；`vendor/` 只读、`MANIFEST.json` 与 SHA256 清单照旧。
  5. **本地不跑全量测试。** 改 `modules/` 或 `vendor/` 后本地只跑 `tools/aisep.py test --no-pytest`，`aisep-mcp/tests` 与负例交给 CI；改到 `modules/**` 的 PR 合并前由协调会话按 ADR-022 的命令核对 H 上 `negatives` 为 `["success"]`。
  6. **ADM 阶段关口评审暂停。** 各阶段模板出口条件里的关口评审项在此期间不要求。
  7. **不放宽的**：硬规则 1–5、7；批准记录只能由 Albert 本人做出；CI 必需检查；涉及 mergecheck 的 PR 核对 `negatives`（ADR-022）；用合并提交；PR 即锁；跨模型评审先问 Albert。
- **理由**：Albert 原话「把可追溯，可审计，可复现这三个质量目标先搁置，后期再做，先做 mvp，不然太慢了」。放宽的都是事后可以补做的校验与留痕（批准记录、三步合并的留痕、本地约 48 分钟的全量测试、阶段关口）；IRI、限定关系、vendor 哈希、批准只能由本人做出这些事后补不回来或属于安全约束的不动。根目录文件、`aisep/**`、`aisep-mcp/**`、`tests/**`、`tools/**` 不放宽，因为 ADR-019 的评审实测过在这些位置放文件可以让 `mergecheck` 空跑通过；`modules/**` 与 `vendor/**` 不放宽的原因见第 1 款。分支保护不要求分支与 `main` 同步（`strict:false`），CI 的结论是对开 PR 时的 `main` 算的，所以会改变 gate 结论的 `modules/**`、`vendor/**` 仍走三步。
- **后果**：评审方面实际省下的只有「新增 IRI 的模型 PR」；`modules/**`、`vendor/**` 的 PR 仍要等合并前评审，直到第 1 款的漏洞修掉。不改模型、模块、vendor 与负例清单的 PR 不再有合并前重算，靠 CI 的 `mergecheck` 必需检查兜底。第 1 款的漏洞在 `main` 上现已存在（不是本条引入），按 ADR-019 第 2 款的漏洞例外另开修复 PR。**恢复条件**（任一出现即逐条恢复，由 Albert 定）：① MVP 走通第一条含 C4 的端到端链路；② 出现第二个批准人或使用者；③ 有外部数据或受监管数据进入模型；④ 合并后评审在同一类路径上连续两次查出阻塞问题。
  - 补记（Albert 2026-11-26 定）：`models/<slug>/governance/**` 与 `models/<slug>/governance.ttl` 的改动只要不新增 IRI，就不在第 1 款的排除范围内，走合并后评审，删除或修改已有批准记录也在其中。这类改动会直接改变 approvalState 的推导结果，由必需检查 `mergecheck` 兜底：目标分支上已有的批准记录或 AI 活动被删除、被修改时，check 1 拒绝合并（`governance-record-removed` / `governance-record-modified`），与 gate 结论无关，负例覆盖记录写在 `governance/` 单独文件里与写在 `governance.ttl` 里两种情形；改动 `arch:Stakeholder` 等其他治理元素（例如改掉或删除批准人）也能让已有记录失效、改变推导结果，这类改动 check 1 不管，原先只靠 check 5（合并结果上的 gate）拦截（PR #132 独立评审实测）；Albert 2026-11-26 同意加一道不依赖 gate 的防线（ADR-019 第 2 款治理加固冻结的例外，由 Albert 批准）：T 上已有记录引用的批准人在 M 上被删除，或推导判定它能否当批准人的结论（按类型及其子类链）改变时，`mergecheck` 拒绝合并（`governance-approver-removed` / `governance-approver-retyped`，`docs/mcp-interface.md` §5.9 检查项 10），负例覆盖改成 `aisep:AIAgent`、去掉类型、删除干系人、在模块里加类型、给其类加父类 `aisep:AIAgent` 五种。
  - 补记（Albert 2026-11-27 定，issue #124 第④项）：第 1 款的两个排除项 `models/<slug>/governance/**` 与 `models/<slug>/governance.ttl` 中的 `governance` 按不区分大小写比较（如 `models/<slug>/Governance/` 下的文件、`models/<slug>/GOVERNANCE.ttl` 同样排除，留在合并前评审），与 ADR-019 第 1 款白名单①的文档排除项、ADR-027 第 1 款的三个排除目录同一口径，也与写入层拒写 `models/<slug>/governance/` 时按不区分大小写比较（`aisep/writer.py` 的 `check_paths`）一致。这是收紧，只让更多路径留在合并前评审；`AGENTS.md`「分支与合并」第 2 条按此表述。

## ADR-025 · 2026-11-26

- **状态**：已采纳（双模型是规范给定的前提；第 2–4 款的关联方式、数据库映射、层级与上游版本由 Albert 2026-11-25 在关口 A 拍板，见 [`docs/specs/c4-archimate4-verification.md`](specs/c4-archimate4-verification.md) §9.3；本条补记，已由 PR #103、#106、#111 落地；底座版本更新 ADR-007 的 core 0.6.0，ADR-007 原文不改）
- **决策**：C4 与 ArchiMate 4 走**双模型**，同一知识图谱、显式关联，C4 不做成 ArchiMate 的视图（规范 [`docs/specs/c4-archimate4-dual-model.md`](specs/c4-archimate4-dual-model.md)）。
  1. **C4 是独立记法模块** `modules/c4`（Language，`aisep:inheritsHubRules false`）：词汇只用上游 `c4/onto` 与 `c4/structurizr`，不写 `align.ttl`，不声明任何 C4 ⊑ am4 公理。这是 ADR-004「其他记法通过子类对齐接入」的例外（元模型规范 §0、§6.8）。
  2. **跨模型关联用 `arch:refines`**，方向 C4 → am4，C4 的层级是 **design**（`aisep:LevelDesign`，元模型规范 §7.2）；不用上游 DD-11 的 `skos:exactMatch` 加 reconciliation 图，因为它不在 D8 允许的三类连接里，要求的记录形式（RDF 1.2 三元组项）又被 L0 禁止，还会和已在用的 refines 形成两套身份机制。
  3. **一个数据库对应多个逻辑数据对象时**，先在 am4 侧聚合，数据库再 refines 聚合后的那个 DataObject，以守住 §7.2 的主锚唯一。
  4. **上游整体升到线上版**（core 0.7.0，PR #103），带来 `arch:DependsOn`，它同样受记法混用规则约束（G5，见 ADR-012）。
- **理由**：规范要求两套模型放在同一知识图谱里，各管一类事实，通过显式关联连接。`arch:refines` 是上游 core 自己的跨模型追溯谓词，也是 AISEP 对 BPMN、DDD、UML 已在用的机制，已有 L1 的方向与主锚规则，不需要新的身份机制（核实报告 §9.3）。
- **后果**：AISEP 自有的 C4 规则 R1–R8 写在 `modules/c4/shapes.ttl`；与规范原文的偏离（R1 反向按「至多一个」、R4 由构建保证、R6/R7 以上游关系表为准经 Role 执行等）记在 [`docs/specs/c4-archimate4-step4.md`](specs/c4-archimate4-step4.md) §4，规范原文不改。已知局限：组件归属不检查；独立治理的数据库无法同时 refines 组件和 DataObject（第 3 款的副作用）。

## ADR-026 · 2026-11-26

- **状态**：已采纳（Albert 2026-11-26 拍板，经协调会话转达；改选 2026-11-25 动作机制决定 2「动作目录写成 JSON、不进元模型」）
- **决策**：
  1. **动作定义建进元模型，只建定义、不建执行记录。** 新扩展模块 `modules/ext-actions/`（Extension，与 ext-code、ext-verification、ext-governance 一样共用 `https://aisep.example/ont/aisep#`，不声明 `aisep:ownsNamespace`；模块 IRI `https://aisep.example/module/ext-actions`）。参照 Palantir Foundry 的 Action type 建 `aisep:ActionType`（参数、有序步骤、提示级前置检查）、`aisep:ActionStep`、`aisep:BasicAction`（封闭集合，五个个体对应五个写工具）。不建执行记录（Foundry 的 Action log），保持 ADR-013；不跟 Foundry「默认只能经动作编辑」，动作仍是推荐通道，直接编辑照旧允许。
  2. **复用现成词汇，不另造。** 参数用 SHACL 的 `sh:parameter` / `sh:Parameter`（参数名 = `sh:path` 的本地名）；前置检查用 `sh:SPARQLAskValidator`（`sh:ask` 为 true 即通过，`sh:message` 是修法提示，参数以 `$名` 预绑定）；标识用 `dcterms:identifier`，版本用 `owl:versionInfo`（历史靠 Git），名称与说明用 `skos:prefLabel`、`skos:definition`。步骤用 `rdf:List` 排序（`aisep:steps`）。参数键放在 `https://aisep.example/ont/ext-actions#`（规范 §3 现有的「AISEP 模块本体 `{base}ont/{module}#`」形状，Albert 2026-11-26 选 A），不声明为属性。
  3. **目录改读 RDF。** 执行器 `aisep/actions.py` 与两个固定工具 `model_list_actions`、`model_apply_action` 保留，目录从 `modules/ext-actions/catalog.ttl` 读；删除 `aisep/action_catalog.json`。`catalog.ttl` 列进模块清单的 `aisep:loads`：`gate` 的 L3 用 `shapes.ttl`（EA1–EA10）校验它，`model_query` 能查到有哪些动作。执行器每次调用重读目录，自己再判一遍同样的结构（X1），另判 SHACL Core 说不了的规则（X2–X10，含「两步作用于同一目标判无效」）；单条定义有错只让该条无效，两个工具不因此返回 `INTERNAL`。
  4. **不采纳 Foundry 的 Function rule。** 动作只组合现成写工具的计划函数：受保护类型、IRI 生成、文件落点三道防线不重写；也避开 Foundry 自己承认的问题（没有动作编辑权限的人可以通过改函数来改变动作行为）。
  5. **不做跨模型评审，只做独立评审。** 本次改动属于 ADR-021 第 2 款所说的「元模型语义、IRI 方案」，依该款问过 Albert，他选不做跨模型评审（2026-11-26）。新铸 IRI 合并前报 Albert 过目。
- **理由**：动作机制同类产品调研报告第 3.4 节第 2 条指出 JSON 目录的弱点：动作定义游离在元模型之外，`gate` 校验不到、`model_query` 查不到，也不符合原则四「自定义的标准本身也是仓库里的元素」。建成元模型里的定义后，目录写坏会让 `gate` 失败，从而进不了主线；查询和工作台能按 RDF 读到动作及其中文标签。与 Foundry 的对照：保留 Action type（参数、规则、提交条件）的形状；规则限定为五个基本动作，并禁止两步作用于同一目标以换取重放幂等（Foundry 允许后一条规则覆盖前一条）；提交条件降为提示级前置检查（Foundry 的条件是硬门槛，因为在 OSv2 里动作是用户编辑的唯一入口，这里不是；Foundry 的数据源管道另有一条不经动作的写入路径）；不建 action log、side effects、Function rule。副本实跑：不改 `aisep/core.py`，新模块就能被发现、加载，并参与 L3 和 `gate`；模型上 `gate` 的结论、计数与耗时不变。
- **与已有 ADR 的关系**：
  - ADR-013：不建执行记录，不写日志，不产生审批项，所有状态仍在 Git 文件里；动作定义是模块文件，不是「进行中状态」。
  - ADR-016：动作个体与基本动作个体都在共享的 `aisep#` 里，用 `Action` / `Basic` 前缀区分，不另开模块命名空间；参数键放在 `ont/ext-actions#`，符合规范 §3 现有表行，不新增表行。
  - ADR-019：`modules/**`、`aisep/**` 都是合并前评审；`catalog.ttl` 新增或修改动作同样走合并前评审，并按元模型改动来评审（`catalog.ttl` 在 `aisep:loads` 里，作为元模型加载；执行器只校验 `aisep:ActionType` 闭包内的三元组，不限制其中出现其他 TBox 三元组）。新增动作会铸 IRI，不属于白名单。
  - ADR-021：第 2 款（跨模型评审先问 Albert）见决策第 5 条。
  - ADR-024（MVP 期间放宽评审分级）：第 1 款明确 `modules/**` 暂不放宽，本条不受其影响；按第 2 款，改到 `catalog.ttl`（属 `modules/**`）的 PR 仍走三步合并；按第 5 款，合并前由协调会话核对 H 上 `negatives` 为 `["success"]`。
  - 动作机制调研报告阶段 D：报告把阶段 D（建进元模型）的入口标准定为「至少 3 个动作在真实链路上被调用过」等；这次 Albert 改选决定 2，直接跳过了这些入口标准。
- **后果**：
  - 两个工具的入参与返回基本不变：动作仍用短 id 调用；列表与执行结果多了动作 IRI（`iri`、`actionIri`）和动作版本；`operations` 改为五个写工具名（新增 `model_set_attributes`）；guard 语义从 `expect` 改为 SHACL 原义「true = 通过」，`bind` 改为 `$参数名` 隐式预绑定。
  - `catalog.ttl` 写成非法 Turtle 时，与任何模块文件写坏时相同：动作工具报 `PARSE_FAILED`，`gate` 失败（命令行以解析错误退出，退出码 1）。
  - X6（两步作用于同一目标）只由执行器判，`gate` 不知道它；靠 CI 的 pytest「仓库目录每条定义都有效」挡在合并前。由调用时取值造成的重叠（两个不同参数填成同一个 IRI、`slug` 恰好等于被删的 IRI）判不出。重放判定按合并后的文件逐字节比较：各步改动相互抵消（例如两个参数填成同一 IRI、先后改它的名称）时重放返回 `changed: false`、不重写文件；涉及新增元素或删除步骤的重叠，重放可能被拒。接口文档 §5.14 写明了这条重放边界。
  - 只判最终候选图：中间步骤只查能否解析（L0），不判 L1/L2，所以动作能写出「依次调写工具写不出」的组合（例如一个元素要求的必有关系必须和元素同时出现）。这不算放宽 L0–L2：最终图用的是同一套规则。
  - 撤销：报告阶段 D 的「反向出口：撤回只是一次代码 revert」在铸了 IRI 之后不再成立。将来撤销动作机制时，代码可以 revert，已铸的 IRI 按硬规则 5 不删不改，按 `owl:deprecated true` 退役（模块清单从 `aisep:loads` 移除 `catalog.ttl` 前先标退役）。
  - 新铸 IRI 39 个（模块与本体 2、类 3、属性 10、基本动作 5、动作 2、参数键 9、shape 节点 8；设计稿写的「40」是加法错误），新开命名空间 `ont/ext-actions#`（参数键）、`shapes/ext-actions#`。Albert 2026-11-26 已过目并同意。
  - 已知限制：模块测试的负例是模型文件，L1 的 G7 会拒绝空白节点上的 `sh:`、`dcterms:`、`rdf:first` 谓词且没有 focus，因此 EA8、EA9 的负例把参数和 guard 写成 IRI 节点，EA5–EA7 的负例不用 `( … )` 表。后果：`ea8-parameter-two-types`、`ea8-parameter-unsupported-key`、`ea9-guard-without-message`、`ea9-guard-not-a-validator`、`ea5-member-not-a-step` 这几个负例实际命中的是 `sh:nodeKind sh:BlankNode` 那一条或第一条 EA5 形状，去掉文件名所说的缺陷后仍然命中，**只证伪 nodeKind**，证伪不了它们声称的缺陷。ParameterShape、GuardShape、EA5 成员形状本身有效（独立评审直接改 `catalog.ttl` 后 `gate` 都 FAIL），但目前只有 EA6 有 pytest 覆盖（`test_gate_checks_the_catalogue_with_the_module_shapes`）；补「改副本 `catalog.ttl` 跑 `gate`、断言 EA5/EA8/EA9 被点名」的用例留作后续。这几条规则在执行器一侧另由 pytest 覆盖。（2026-11-26 更新：这组用例已由 PR #133 补上，即 `test_gate_names_the_shape_of_each_catalogue_defect`，在真实目录副本的空白节点上分别写入上述缺陷；同一测试另有五例把节点原样改写成 IRI 节点，分别单独证伪 EA5（列表、成员）、EA7、EA8、EA9 的 `sh:nodeKind sh:BlankNode`，issue #140。）
- **补记（2026-11-27，issue #160）**：
  - **合并规则（Albert 2026-11-27 定，经协调会话转达）**：`modules/ext-actions/**` 的改动照旧合并前评审，经独立评审人（agent）评审通过即可合并，不需要 Albert 批准；合并后由协调会话告知 Albert（PR 号与改动要点），必要时请他看。这一条明文接受「动作定义的修改由 agent 评审把关」，不加 CODEOWNERS 或分支保护上的人工批准；新铸 IRI 合并前报 Albert 过目（本 ADR 决策第 5 条）不变。
  - **执行与列出读同一份受信目录**：`model_apply_action` 不再读调用参数 `repo` 所指工作区里的 `catalog.ttl`，改为与 `model_list_actions` 一样只读服务器所服务工作区（`--repo`）里的那份；`repo` 只决定写哪个工作区的模型。此前在未合并分支的 worktree 里改目录，带 `repo` 指向它就能立即执行，绕过「动作定义经 PR 修改」。已知边界：所服务检出本身有未提交的目录改动时仍会生效（决策第 3 条「每次调用重读、改动立即生效」）；触发条件：所服务的检出不再是只跟随 `main` 的检出（例如有人在里面改 `catalog.ttl`），届时改为从 `main` 的提交读目录。
  - **结构残余收紧**：`ActionTypeShape` 加 `sh:closed true`（报 EA1），动作上只能写 `rdf:type` 与目录写法表里的谓词，`aisep:ActionX rdfs:subClassOf arch:Element` 这类 TBox 三元组 `gate` 会拒；新增 EA11：动作个体的 `rdf:type` 只能是 `aisep:ActionType`，不另带领域类型。执行器 X1 同步判 EA11（封闭性原本就判，记为 EA1）。上文「执行器只校验 `aisep:ActionType` 闭包内的三元组，不限制其中出现其他 TBox 三元组」改为：目录文件里闭包以外的三元组由 CI 的 pytest（`test_catalogue_has_no_triples_outside_action_closures`）拒绝，执行器仍只读闭包内的三元组。`aisep:ActionType` 加进写工具的受保护类型（`write_tools.PROTECTED_TYPES`），写工具不能在 `models/` 下新建或修改动作个体。未铸新 IRI（EA11 与封闭约束写在 `ActionTypeShape` 的空白节点上）。形状与目录改了，ext-actions 升 0.3.0（0.2.0 已由 ADR-029 的 `aisep:ActionBinding` 占用）。
  - **目录引用失效检测**：新增 pytest，断言目录里每个 `aisep:constant`、`aisep:attributePredicate` 引用的 IRI 在当前元模型（全部模块清单 `aisep:loads` 的文件，不含 `catalog.ttl`）里有声明、没有 `owl:deprecated true`；不放进 `gate`。
  - **「补用例留作后续」的补记**：上文已知限制里 EA5/EA8/EA9 的用例已由 PR #133 补上；EA2、EA3、EA4、EA7、EA10（三条形状各一例）、EA11 与 EA1 的封闭约束现在也在 `test_gate_names_the_shape_of_each_catalogue_defect` 里各有「改真实目录副本、跑 `gate`、断言点名」的用例，并逐条做过停用对应约束后变红的对照。EA 规则在 `gate` 与执行器两侧仍是两份实现，没有差分测试。

## ADR-027 · 2026-11-26

- **状态**：已采纳（Albert 2026-11-26 拍板：「先补上那一层防线，再放宽」，范围在会话里逐项选定）；兑现 ADR-024 第 1 款「漏洞修掉后由 Albert 决定是否把 `modules/**`、`vendor/**` 放进合并后评审」，ADR-024 原文不改。
- **决策**：
  1. **`modules/` 下的 `.ttl` 改为合并后评审**，但不含 `modules/aisep-core/**`（批准记录、活动、关口的类与属性，以及它们的 SPARQL 形状）、`modules/ext-governance/**`（批准记录与活动的 SHACL 形状 EG*、质量度量）、`modules/ext-actions/**`（AI 可执行的写动作目录，ADR-026 要求按元模型改动评审）；这三个排除目录按不区分大小写比较。判断口径与 ADR-024 第 1 款相同：PR 改到的每一个路径都属于这一类、ADR-024 放宽类或 ADR-019 白名单，且都是模式 100644 的普通文件。
  2. **`vendor/**` 暂不放宽。** 上游升级同时改 `MANIFEST.json`、`SHA256SUMS` 等非 `.ttl` 文件，只放宽 `.ttl` 没有实际效果；升级少、影响面大，照旧合并前评审。
  3. **不变的**：改到 `modules/**` 的 PR 照旧走三步合并，合并前核对 H 上 `negatives` 为 `["success"]`（ADR-024 第 2、5 款）；ADR-024 第 7 款列出的不放宽项照旧。
- **理由**：ADR-024 不放宽 `modules/**` 的原因是 #105（模块声明的 `aisep:ApprovalRecord` 子类做类型的记录被推导认可、却绕过 `mergecheck`），合并前评审是唯一拦截点。现在两层防线都不依赖评审：#110 让 `mergecheck` 按 T 与 M 上下文的子类闭包识别记录与活动，与推导同口径；#115 把类型写在模块或 vendor 文件里的记录与活动一律拒绝（`docs/mcp-interface.md` §5.9 检查项 9），两者都有负例，且做过去掉修复的对照证伪。三个排除的模块直接定义批准记录与活动、判定记录是否合法、决定 AI 能写什么，留在合并前评审。
- **后果**：其余模块（am4、bpmn、c4、ddd、uml、ext-code、ext-verification，以及新增的模块目录）的元模型改动必需检查通过即可合并，合并后派独立评审人。残余风险，靠合并后评审事后发现：① 这些模块仍能写入影响治理判定的三元组，例如往 `aisep:Gates` 方案里加关口（`approval_problems` 从全部本体图取关口）；② am4 是枢纽模块，它的形状与 aisep-core 的形状在 L3 同图校验，能用 `sh:deactivated` 停用 aisep-core 的 L3 形状，L1 的 `approval_problems` 与 ext-governance 的 L3 校验不受影响（#118 评审实跑）；③ 新增模块能经清单加载 `vendor/`、`modules/`、`models/` 下的任意文件，但改不了 vendor，把治理记录当本体加载会被 `mergecheck` 检查项 9 拒绝。恢复条件同 ADR-024。

## ADR-028 · 2026-11-27

- **状态**：已采纳（补记。`model_set_attributes` 由 PR #102 加入，Albert 2026-11-25 放行动作机制阶段 A 时随之加入；下面的接口取舍是动作机制调研报告的推荐，Albert 2026-11-27 已认可；2026-11-27 Albert 同意把这些取舍补记成本条，issue #124 第⑤项）。接口契约以 `docs/mcp-interface.md` §5.12 为准，本条只记取舍与理由。
- **决策**：
  1. **新增独立写工具，不扩展 `model_set_labels`。** 改已存在元素或关系的非标签属性（如 `aisep:priority`、`aisep:gherkin`、`aisep:path`）走 `model_set_attributes`；名称、英文名、定义仍只走 `model_set_labels`，那里有语言与长度约束。没采纳的两个方案：给 `model_set_labels` 加 `attributes` 参数（改了已评审工具的契约，工具名也名不副实）；不加工具、继续「删了重加」（已批准元素的非标签属性没有修改路径，`docs/methodology.md`「改已批准元素」）。
  2. **`set` 按谓词整体替换，`unset` 删除该谓词的全部值。** 写入后主语在该谓词上的值恰好是 `set` 给出的那几项；没出现的谓词不变。参照 JSON Merge Patch（RFC 7396）对成员值、包括数组的整体替换，以及 SPARQL 1.1 Update 的 `DELETE/INSERT … WHERE`：一次调用就是一个「删该谓词旧值、插新值」的替换。没采纳逐值的「追加一个 / 移除一个」（JSON Patch 式）：整体替换的请求本身就是结果，同参数重放天然幂等（`changed: false`、文件不变），与其他写工具的重放语义一致。
  3. **谓词合法性不另写白名单。** 只按名拒绝写入层自有或另有入口的谓词（`rdf:type`、`arch:inModel`、`arch:source`、`arch:target`、三个标签谓词、`arch:inView`），其余由候选图上的 L1 规则判定，与 `model_add_element` 的 `attributes` 同一口径（闭世界 G7、手写 `arch:approvalState` 都表现为 `WRITE_REJECTED`）。元模型加谓词时不用同步改工具。
  4. **不接受 `file`，落点由已有三元组决定。** 新值写进被替换的三元组所在的文件；跨多个文件时写进按仓库相对路径排在最前的那个（PR #157）；原来没有值时写进 `rdf:type` 所在的文件。写入方不选文件，避免同一主语的三元组被随意打散。
  5. **对已批准元素不拦，把关在合并。** 与 `model_set_labels` 相同：`gate` 照常 PASS，`mergecheck` 按图差异报 `unapproved-change-to-approved`；不改任何合并判据，不进 ADR-019 第 2 款的冻结范围。
  6. **不做跨模型评审，走合并前独立评审。** 它是已评审过的 `model_set_labels` 模式的平移，不涉及批准与合并判据（调研报告的 Q3 推荐，PR #102 按此执行）。
- **理由**：这是「改属性」唯一缺的写入口（`docs/methodology.md` 第三条链路实跑时没有它，只能删了重加），也是动作目录首批动作需要的基本动作（ADR-026 的五个 `aisep:BasicAction` 之一）。照现成工具的模式平移，校验、事务、主语块改写都复用 `model_set_labels` 的路径，不新增写入机制。
- **后果**：
  - 多值谓词的调用方必须一次给全集：只给一个值，就只剩一个。`docs/actions.md` 写明了这一点。
  - **丢失更新**：整体替换是「读后写」，调用方先读到旧值集合再拼出全集，两次调用之间别的会话给同一谓词加的值会被覆盖。写入层的写锁与写前哈希核对只管单次调用之内，管不到调用方的读和写之间。业界的做法是乐观并发控制（HTTP 的 `If-Match`/ETag，RFC 9110 §13.1.1）：调用时附上期望的旧值或其摘要，不一致就拒绝。现在不做：目前的用例（`docs/actions.md` 的配方与动作目录）改的是 `aisep:priority`、`aisep:path` 这类单值属性，还没有两个会话并发维护同一多值谓词的场景。**触发条件**：出现两个会话并发写同一模型目录，或需要经它维护多值的成员属性（如 BPMN 的 `bpmn:flowElements`）时，加一个可选的期望旧值参数（不一致报 `CONFLICT`），或补逐值增删的入参，二者择一另立 ADR。
  - 改类型、所属模型、关系端点、视图成员关系仍没有写工具（`docs/mcp-interface.md` §1），不由本条放开。

## ADR-029 · 2026-11-27

- **状态**：已采纳（Albert 2026-11-27 定：模块属性必须声明定义域；vendor 定义域暂不强制）。承接 issue #67 与 PR #153。
- **决策**：
  1. **模块属性必须声明定义域。** `modules/**` 声明的每个 `owl:ObjectProperty`、`owl:DatatypeProperty`、`rdf:Property` 至少有一条写在模块文件里的 `rdfs:domain`，取值是 IRI 或 `owl:unionOf` 的 IRI 列表；`owl:AnnotationProperty` 是元模型注解，不在此列。这是模块合约，由 pytest `aisep-mcp/tests/test_module_property_domains.py` 检查（CI 必需检查 `pytest`）。L1 定义域检查（PR #153）对 `owl:unionOf` 定义域按「主语是其中任一类」判定。
  2. **`vendor/` 上游本体声明的 `rdfs:domain` 暂不强制。** L1 只读模块文件里的定义域；上游属性被借用到别的类型上，`gate` 照旧不拦。
- **理由**：PR #153 只强制已声明的定义域，没声明定义域的模块属性仍可借用到任意元素上，等于留了一个口子；补齐定义域并把「必须声明」做成常驻检查，口子才算堵上。vendor 暂不强制，是因为上游的写法与 RDFS 语义不完全一致：`ad:appliedInOption` 声明了三个 `rdfs:domain`（ReferenceArchitecture、Pattern、Tactic），按 RDFS 是交集，上游大概率想要并集；ArchiMate 4 的关系谓词用的是不蕴含的 `arch:domainIncludes`。强制之前要先定口径，又不能改上游文件（硬规则 6）。实测当前仓库模型没有违反 vendor 定义域的写法。
- **后果**：
  - 本次补齐的定义域：DDD 关系类的直连谓词取关系类定义写明的源端（`ddd:upstreamOf`、`supplierOf`、`partnerOf`、`sharesKernelWith`、`owns`、`implements` → `ddd:BoundedContext`；`ddd:contains`、`hasRoot` → `ddd:Aggregate`；`ddd:triggers` → `owl:unionOf(ddd:DomainService ddd:Policy)`），DDD 升 0.2.1；ext-actions 新增类 `aisep:ActionBinding` 作参数绑定节点的定义域（`aisep:argument`、`constant`、`fromParameter`、`fromStep`、`modelOf`、`attributePredicate`），并作 `aisep:binding` 的值域，`catalog.ttl` 里的绑定节点仍不写类型，已有动作的定义摘要不变，ext-actions 升 0.2.0。声明这个类会让它在 L1 成为合法类型，所以 EA10 的绑定形状同时以 `aisep:ActionBinding` 为目标：类型写成它的节点必须是 `aisep:binding` 的宾语，否则 L3 报 EA10（负例 `ea10-action-binding-type-on-model-element.ttl`）；未铸新 IRI。
  - 直连谓词的定义域只在源文件里读到，而源文件里写直连三元组本身就是 L1 违规；限定关系的 `arch:source` 目前不按直连谓词的定义域核对（ext-code 的 EC5、ext-verification 的 EV2 已有同类核对，DDD 没有）。
  - 重新考虑 vendor 定义域的触发条件：模型里出现借用上游属性造成的实际问题，或升级上游（规范 §11）时上游改了定义域的写法。
