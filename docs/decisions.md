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

## ADR-030 · 2026-11-27 · 工具区与领域区分区

- **状态**：已采纳（Albert 2026-11-27 拍板「全部按推荐」，G3 第 1–4 条，经协调会话转达；修订稿为 G3 修订方案 2026-11-27）。修订 ADR-026 第 3 款、理由段、「与已有 ADR 的关系·ADR-019」条、后果「撤销」条，各自原文不改，以本条为准；ADR-026 第 1 款与「与已有 ADR 的关系·ADR-016」条不变。实现见 issue #169。按 ADR-019 第 5 款，规范、接口文档与 `AGENTS.md` 的条文在实现合入 `main` 前保持原口径，改写随实现 PR 一起做（见后果「文档同步」）。
- **背景**：
  - ADR-026 第 3 款把 ext-actions 的 `onto.ttl`、`catalog.ttl` 列进 `aisep:loads`。它们因此装进 `urn:aisep:onto:` 命名图，`model_query`、`gate`、写工具、影响分析都用 `use_default_graph_as_union=True` 或 `GRAPH ?g` 加 onto 前缀过滤，把这些文件当成领域元模型读（`aisep/core.py` 的 `Ctx.rows`、`onto_graph_filter`；`aisep/querybox.py`）。
  - 实测：领域 SPARQL 的结果里混进了 ext-actions 的两个文件（按 `main` 7d77392 直接数 `onto.ttl` + `catalog.ttl`：38 个 `skos:prefLabel` 三元组，分属 20 个主语；3 个 `owl:Class`）。动作词汇进了 `ctx.supers`、G7 的已声明谓词集和写工具的可实例化类表。模型文件里写的伪动作只有 EA 形状在 L3 碰巧拦住（探针：L1=0、L3=4）。
  - 只改默认图（`FROM`、`default_graph`）管不到 `GRAPH ?g`：它遍历的是数据集的命名图集合，与默认图怎么组成无关（SPARQL 1.1 Query §13.3）。core、写工具、mergecheck 里十余处（`main` 7d77392 上 core 10 处、写工具 3 处、mergecheck 1 处）的 `GRAPH ?g … FILTER(STRSTARTS(STR(?g),"urn:aisep:onto:"))` 判定，以及不经 SPARQL、按文件列表拼数据图的 L3，都不受默认图影响。
- **决策**：
  1. **新增模块清单属性 `aisep:toolingLoads "<相对路径>"`**，可出现多次，与 `aisep:loads` 并列。它声明的文件属于**工具区**：照常解析（解析失败照旧 `PARSE_FAILED`），由本模块的 `aisep:shapesFile` 在 L3 校验，但不进领域查询库，不参与领域判定。ext-actions 的 `onto.ttl`、`catalog.ttl` 从 `aisep:loads` 改列在这里。`aisep:moduleKind` 不变，ext-actions 仍是 Extension。哪些文件属于工具区由清单声明，不在代码里写死路径，也不按命名空间或内容推断。
  2. **工具区文件装进单独的 `ctx.tool_store`**，图名前缀 `urn:aisep:tool:`，不进 `ctx.store`。所有查询面默认只读领域区（默认拒绝），新增的查询面也一样。需要读工具区的只有三处，都显式处理：mergecheck 检查项 9、第 4 款的 L1 新规则、声明了 `toolingLoads` 的模块的 L3 那一轮。执行器与 `model_list_actions` 照旧直接读 `catalog.ttl`。各查询面读哪一区见下表。
  3. **L3 按区选数据图。** 领域各轮（am4+core、各非枢纽模块）的数据图不含工具文件；声明了 `toolingLoads` 的模块那一轮，数据图是领域区文件 + 本模块工具文件 + 模型。EA 形状照旧也扫模型文件，EA 形状（现为 EA1–EA11，ADR-026 补记新增 EA11）行为不变，现有负例照常通过。
  4. **新增 L1 规则：模型源图不得引用工具区术语。** 工具区文件里作主语、且领域区没有声明的 IRI，出现在 `urn:aisep:src:` 图的主语、谓词、`rdf:type` 宾语或 `aisep:approves` 宾语位置 → Violation。`aisep:approves` 宾语单列：工具文件移出 `ctx.store` 后，现有「`approves` 目标是元模型术语」判定在 onto 图里查不到动作，按「目标不是任何源图主语」直接跳过（`aisep/core.py` 现有注释：交给合并时核对），不点名会让 L1 对 `:rec aisep:approves aisep:ActionXxx` 从报错变成放行。普通宾语不一般化：G6 调用日志等持久化记录以后可能要引用动作 IRI，那是第 6 款的迁移触发条件，到时另定。写工具的可实例化类表只读领域区，`aisep:ActionType` 解析不到，按现有「未知类型」拒绝。写法与 mergecheck 检查项 9 对称：治理类型只能写在 `models/`，工具术语不能写进 `models/`。
  5. **`model_query` 不再暴露工具区，动作只经 `model_list_actions` 列出**（参照 Palantir Foundry：对象检索不返回 action type，动作走专门的 Action 接口）。`model_query` 的默认图恒为领域区并集，查询里的 `FROM` 不生效；`FROM NAMED` 只能在领域区的命名图里收窄 `GRAPH ?g` 遍历的范围，取不到工具区（依据：`querybox` 以 `use_default_graph_as_union=True` 调 pyoxigraph，0.5.13 实测 `FROM <g1>` 仍返回全部命名图的并集，`FROM NAMED <g1>` 只遍历 g1；工具区不在库里，点名也取不到）；这一点写进接口文档。
  6. **不迁命名空间。** 动作 IRI 留在 `aisep#`。按 `AGENTS.md` 硬规则 5、元模型规范 §3 与 ADR-026 后果「撤销」条，已铸 IRI 不删不改，「迁移」只能做成旧 IRI 退役加新铸一套，术语翻倍且撤不回；查询隔离靠图，不靠命名空间。迁移作为推迟项，任一出现即启动：① ext-actions 之外的模块、模型或持久化记录（含 G6 的调用日志）开始引用动作 IRI 之前；② 需要给 ext-actions 声明 `aisep:ownsNamespace`；③ 根命名空间统一替换时并入一起做。届时新铸 IRI，旧 IRI 加 `owl:deprecated true` 与 `dcterms:isReplacedBy`，写明并存期间执行器 `ACTION_IRI_RE`/OPS 与 EA1 的 pattern 接受哪一套，并报 Albert。
  7. **批准记录与 AI 活动属于领域区，本条不动。** 它们是 `arch:Element` 的子类，带 `arch:inModel`，存在 `models/<slug>/governance/`，作为源图加载（元模型规范 §6.6、§6.7）。
  8. **评审路径**：合并前独立 agent 评审；不做跨模型评审（ADR-021 第 2 款问过 Albert，2026-11-27 定不做）；新铸 IRI 只有 `aisep:toolingLoads` 一个，Albert 2026-11-27 已过目同意（ADR-026 第 5 款的做法）。
- **查询面 → 读哪一区**（位置以本条合入时的 `main` 为准）：

  | 查询面 | 位置 | 读哪一区 | 说明 |
  |---|---|---|---|
  | `model_query` | `tools.py` → `querybox.py` | 领域区 | 动作改由 `model_list_actions` 提供 |
  | `Ctx.rows`（supers、uf、label、types、L1、L2、L4、构建、relationships） | `core.py` | 领域区 | 动作类层次不再进 `ctx.supers` |
  | `shape_hits`（aisep-core 的 SPARQL 形状） | `core.py` | 领域区 | |
  | L1：Gates、R1 主语/方案/抽象类、G7 已声明谓词、属性定义域、`assertedShortcut` | `core.py` | 领域区 | G7 不再把 `aisep:steps`、`aisep:invokes` 等算作已声明谓词，模型文件用了就报未声明 |
  | L1：`approves` 目标是元模型术语 | `core.py` | 领域区 | 工具区术语在这里查不到类型，按「目标不是源图主语」跳过；改由第 4 款新规则的 `aisep:approves` 宾语位置报错（失败关闭） |
  | **L1 新规则：模型引用工具区术语** | 新增 | 工具区术语集 × 源图 | 第 4 款 |
  | L3 领域各轮 | `core.py` `_l3` | 领域区文件 + 模型 | |
  | L3 声明了 `toolingLoads` 的模块那一轮 | 同上 | 领域区文件 + 本模块工具文件 + 模型 | EA 形状（现为 EA1–EA11）不变 |
  | 影响分析 `aisep:dependency` | `core.py` | 领域区 | |
  | 写工具的类表、抽象类、类所在图 | `write_tools.py` | 领域区 | |
  | guard | `actions.py` | 领域区 | guard 判的是领域前提 |
  | ADM 向导、CLI query、出图 | `adm.py`、`tools/aisep.py`、`diagram*.py` | 领域区 | |
  | mergecheck 检查项 9 | `mergecheck.py` | 领域区 + 工具区 | 失败关闭：工具文件里声明治理类型照样拒绝 |
  | 执行器、`model_list_actions` | `actions.py` | 直接读 `catalog.ttl` | 不变 |

- **理由**：
  - 分区要落到「哪些图进查询库」这一层。参照 Apache Jena Fuseki 用多个数据集（`ja:RDFDataset`）把不同用途的数据分开，而不是放进一个库再靠查询过滤；与它的差别是不另开端点，只在进程内分两个库。工具区不进 `ctx.store`，现有几十处查询入口和 `querybox` 子进程协议一行不改，读到的自动只有领域区；新增查询也默认看不到工具区。
  - 归区由清单声明，参照 Gradle/Maven 的依赖作用域（`implementation` 与 `testImplementation`）：构件进不进主 classpath 由声明决定，不按路径或内容推断。
  - L3 按区选数据图，参照 W3C SHACL 的 shapes graph / data graph 分离：验证时显式指定数据图。EA 形状不收窄到只看工具区：那样 EA1、EA10 对模型文件的拦截会悄悄失效；领域形状不扫工具节点才是分区的目标，EA 扫领域数据无害，还多一层防线。
  - 两个方向都要防：领域查询看不到工具节点（第 2、3 款），模型写不进工具术语（第 4 款）。后者不依赖 EA 碰巧兜住。
  - 外部参考的更正：TDB 的 `unionDefaultGraph`、Stardog 的 `query.all.graphs` 都只是布尔开关，不能配置默认图由哪些命名图组成；Foundry 的 action type 与 object type 同属一个 Ontology 的 schema，它不支持「迁出命名空间」，这里只借鉴「动作走专门接口列出」。
- **替代方案（不采纳）**：
  - A. 只改默认图（`FROM` / `default_graph`）：管不到 `GRAPH ?g` 判定和 L3，只隔离了一半。
  - B. 同一个库里逐个查询传 `default_graph` / `named_graphs`：可行，但入口多、容易漏，默认放开；还要改 `querybox` 子进程协议。
  - C. 在 core 里写死 `modules/ext-actions/` 路径：违背模块契约的通用清单（ADR-026 理由段「不改 `core.py` 新模块即可加载」），以后新增的工具文件默认落进领域区。
  - D. 新增 `moduleKind`（如 `aisep:Tooling`）：牵动 Extension 语义的现有用法，粒度也不如文件级声明。
  - E. 把 `catalog.ttl` 移出 `aisep:loads` 且不另行声明：`gate` 失去对目录的 L3 校验，ADR-026 第 3 款的核心能力丢失。
  - F. 维持并集，只在文档里约束「领域查询按 `inModel` 限定」：只靠约定，写工具和 G7 的词表仍混入动作，留下隐患。
  - G. 迁到独立命名空间：违反硬规则 5，或只能退役加重铸，术语翻倍，对分区没有贡献（见第 6 款）。
- **与已有 ADR 的关系**：
  - ADR-026：第 3 款改为「`catalog.ttl`（连同 `onto.ttl`）列进 `aisep:toolingLoads`：`gate` 的 L3 用 `shapes.ttl` 校验它；要查有哪些动作用 `model_list_actions`，`model_query` 查不到」。理由段删掉「`model_query` 查不到」这项动机，「查询和工作台能按 RDF 读到动作及其中文标签」一句也作废（工作台要列动作走 `model_list_actions`），目录写坏 `gate` 失败的动机仍成立。「与已有 ADR 的关系·ADR-019」条的依据改为「`catalog.ttl` 在 `aisep:toolingLoads` 里，仍属 `modules/**`，按元模型改动做合并前评审」。后果「撤销」条里的「从 `aisep:loads` 移除 `catalog.ttl`」改为「从 `aisep:toolingLoads` 移除」。第 1 款（共用 `aisep#`）与「ADR-016」关系条不变。
  - ADR-016、硬规则 5：不迁命名空间，不改已铸 IRI，见第 6 款。
  - ADR-019、ADR-027 第 1 款：清单改动仍属 `modules/**`；`modules/ext-actions/**` 与 `aisep/**` 都在合并前评审范围内，实现 PR 走合并前评审与三步合并（ADR-024 第 2、5 款）。
  - ADR-019 第 2 款（治理加固冻结，含 `mergecheck`）：检查项 9 改为同时读工具区，改的是冻结范围内的合并判据。这不是新的加固：工具文件移出 `ctx.store` 后，检查项 9 若照旧只读 `ctx.store` 就看不到它们，本改动只为保住原有覆盖；它列在 G3 修订稿的查询面表与实施出口里，在 Albert 2026-11-27 G3 拍板（以修订稿为准）范围内。
  - ADR-019 第 5 款（规范 PR 只写已合入 `main` 的行为）：本条只落 ADR 文本，不改规范与接口文档，相应改写列进后果「文档同步」，由实现 PR 与代码一起做。
  - ADR-021 第 2 款：跨模型评审已问过 Albert，定为不做（第 8 款）。
  - ADR-027 理由段引用的 mergecheck 检查项 9（#105 评审、#115）、ADR-027 后果③：检查项 9 改为同时读工具区，归区不新开「把治理记录藏进模块」的口子。
- **后果**：
  - 正面：领域判定、写工具、guard、ADM、出图、CLI 统一只看领域区，现有调用点不用改，新增查询默认安全；`catalog.ttl` 里夹带的 TBox 不再影响领域判定，残余只剩 EA 规则在 `gate` 与执行器两侧是两份实现、没有差分测试（ADR-026 补记，#160 已收紧其余结构残余）；两个方向都有测试覆盖并做对照证伪。
  - 代价：新增 1 个清单 IRI 和 1 条 L1 规则；`model_query` 失去列动作的能力，推翻 ADR-026 理由段的一项动机（工作台等消费方有没有用 `model_query` 读动作，由实现 PR 核实：在工作台仓库与本仓库 `git grep -n "ActionType\|aisep:Action"`，有命中就改走 `model_list_actions`，结果写进实现 PR 描述）；读工具区的三处要显式处理。
  - 文档同步（按 ADR-019 第 5 款，实现合入 `main` 前保持原口径，由实现 PR 与代码一起改，列入 issue #169 的实现范围）：`docs/mcp-interface.md` §5.4 的 `PARSE_FAILED` 条（补 `aisep:toolingLoads` 的文件）、§5.6「图」（`model_query` 只读领域区，`FROM` 不生效、`FROM NAMED` 只在领域区内收窄）、§5.9 检查项 9（含工具区文件）、§5.13「动作是什么」（目录在工具区，列动作走 `model_list_actions`）、§5.14 第 5 步（guard 只看领域区）；`docs/metamodel-spec.md` §5（清单属性 `aisep:toolingLoads`）、§6.9（L1 新规则）、§8.3（`model.query` 行）、§10.2（`catalog.ttl` 归工具区），以及 §5 模块测试条里 `tests/valid/catalog-loads.ttl`「随清单加载」的一句；`docs/module-contract.md` 清单段注释与动作词汇条；`docs/actions.md`「动作目录」一节的 `model_query` 示例改为 `model_list_actions`；`modules/ext-actions/metamodel.ttl` 头部注释（现写 `catalog.ttl` 在 `aisep:loads`、`model_query can list the actions`）与 `modules/ext-actions/tests/valid/catalog-loads.ttl` 头部注释；`AGENTS.md` 有相关条文时一并改。ADR 原文不改。
  - 撤销：代码可以 revert；`aisep:toolingLoads` 铸出后按硬规则 5 只能退役，不能删。
  - 仍推迟的（各带触发条件）：动作词汇迁出 `aisep#`（第 6 款）；`model_query` 遇到 `FROM` 直接报错（现在只在文档里说明 `FROM` 不生效、`FROM NAMED` 只在领域区内收窄；触发：出现照 `FROM` 写查询而得出错误结论的实例，或 `model_query` 要开放按图选数据集）；给 SPARQL 公开稳定的工具区逻辑图 IRI（触发：消费方确实要用 SPARQL 读动作定义而 `model_list_actions` 不够用）。
  - **实施（入口 / 出口标准）**：
    1. 契约与清单。入口：本条合入。出口：在 `modules/aisep-core/onto.ttl` 里与 `aisep:loads` 并列铸 `aisep:toolingLoads`；ext-actions 清单完成迁移，`modules/ext-actions/metamodel.ttl` 与 `tests/valid/catalog-loads.ttl` 的头部注释改为工具区口径；`Module` 能解析新属性。这一步单独不保证测试全绿（`catalog.ttl` 要等第 2 步接上工具区那一轮才回到 L3），所以第 1–3 步放在同一个 PR，测试在第 2 步出口统一判。
    2. 装载与判定。入口：第 1 步完成。出口：`ctx.tool_store` 落地；`onto_files` 排除工具文件；L3 按区选数据文件；L1 新规则落地；检查项 9 读工具区；issue #169 列出的回归测试 1–6 全部通过，第 5 项（把工具文件放回 `ctx.store`、注掉 L1 新规则）确实让第 1–3 项各自变红；在 `main` 快照上 `gate` 结论与基线一致：与实现 PR 的 merge-base 上的 `gate` 输出逐项比较，结论同为 PASS，L0–L4 各层违规计数逐项相等（基线为 0）。
    3. 文档同步。入口：第 2 步完成。出口：后果「文档同步」列出的条文已在实现 PR 中改写；`git grep -n "也能查到有哪些动作\|model_query can list\|也可以用 \`model_query\`" -- docs AGENTS.md modules ':!docs/decisions.md'` 无命中（ADR 原文不改，排除 `decisions.md`）。
    第 1–3 步放在同一个 PR 里，走合并前独立评审。

## ADR-031 · 2026-11-27 · 服务端调用日志（P1 与规范 §8.3 的唯一例外），以及防篡改审计的触发条件

- **状态**：已采纳（Albert 2026-11-27 拍板「全部按推荐」，经协调会话转达；依据是他对 ext-actions 对照报告 G6 的答复「正规如何做」「不要留隐患」）。第 3、6 款、出口标准与推迟项按 Albert 2026-11-27 第三批拍板（第 14 条，「全部按推荐」）修订：新增只读 MCP 工具 `model_call_log`；日志行带版本号 `v: 1` 作为契约；记单个动作的 `definitionDigest`；结构性参数放在 `measured.request` 下。本条合入前直接改正文，不另立补记。本条是 ADR-024「可追溯、可审计、可复现三个质量目标的校验与留痕在 MVP 期间放宽」的**例外**：ADR-024 放宽的是「可以不做」，没有禁止新增，本条按 Albert 的指示在放宽期间先做 A 层。本条不改 `mergecheck`，也不改批准提交形状，不在 ADR-019 第 2 款的冻结范围内。修订下列条文的适用范围。ADR 条文原文不改，按本条理解：ADR-013；ADR-024 第 7 款「不放宽的：硬规则 1–5、7」中的硬规则 7（见「与已有 ADR 的关系·ADR-024」）；ADR-026 第 1 款「不建执行记录」、它理由段里的「不建 action log」、「与已有 ADR 的关系·ADR-013」条「不建执行记录，不写日志」。规范、接口文档与 `AGENTS.md` 的下列条文在实现合入 `main` 前保持原口径，合入时按「后果」的清单改写：元模型规范 §6.9「只建定义，不建执行记录」、§8.3 的 `model.apply_action` 行「不留执行记录」、§8.3 末段「MCP 不保存任何不在文件里的状态」与「不记录『执行过哪个动作』」；接口文档 P1、§3.2、§3.3、§3.4 第 4 点、§3.5、§5.13「不留执行记录，不写日志文件」；`docs/actions.md` 第 9 行与「动作目录」一节；`AGENTS.md` 硬规则 7（原文在实施 PR 改写前按本条理解）。按 ADR-019 第 5 款，这些文档的改写和实现代码放在同一个 PR。
- **决策**：
  1. **威胁模型。** 攻击者假设与 #120 的批准人签名方案相同：同一台 Mac、同一个 macOS 账号下的 AI 代理，能改自己 worktree 里的服务端代码、换解释器（`$AISEP_PY`）、直接改文件或用 `git update-ref`、绕过 MCP 直接编辑 `.ttl`，还持有所有者级的 `gh` 令牌。本条只保证一件事：**服务进程按仓库里经过评审的代码诚实运行时**，它经手的每一次被审计调用（成功与被拒）都留下一行记录。本条不证明调用方身份，不防代理删改日志，也不覆盖不经 MCP 的改动，**不防代理篡改**。
  2. **记录范围。** 挂在 `aisep/server.py` 的 `on_call_tool`，不只挂在 `call()` 上：参数校验（`validate_args`）在 `call()` 里面，挂在哪里都能记到；画像外工具名在进入 `call()` 之前就被 `on_call_tool` 自己以 JSON-RPC `INVALID_PARAMS`「Unknown tool」拒绝（`aisep/server.py` 的 `on_call_tool` 第一行判断），只有挂在 `on_call_tool` 才记得到。被审计的工具：五个 `model_*` 写工具、`model_apply_action`（`dryRun` 也记）、`governance_record_approval`；调用名属于这个集合、但当前画像里没有的，也记一条，结果写 `UNKNOWN_TOOL`（日志专用的结果值，不是接口错误码，不进 `aisep/errors.py`；只为排查诚实代理的误调用，不作安全留痕）。只读工具不记，既不在审计集合里、也不在画像里的未知工具名也不记。
  3. **字段。** 每行一个 JSON 对象，顶层三个键：`v`、`measured`、`declared`。`v` 是行格式版本，现为 `1`。行格式是对外契约（`model_call_log` 原样返回日志行，见第 6 款），字段的增删、改名或含义变化都升 `v`；读方遇到不认识的 `v` 跳过该行并计数，不报错。只记动作 id，不记动作 IRI（ADR-030 第 6 款①：持久化记录引用动作 IRI 是命名空间迁移的触发条件；迁移只能按该款新铸 IRI 并退役旧 IRI，已铸 IRI 不删不改，硬规则 5）。`measured`（服务端测得或收到）：UTC 时间、耗时；服务进程 pid 与启动参数（`--profile`、`--transport`、`--allow-root`、`--repo`）；工具名；`request`：参数规范化 JSON（键排序、无空白、UTF-8）的 sha256，加结构性参数——模型 slug、目标 IRI（`model_apply_action` 只取动作定义 `iriParams` 列出的参数值）、动作 id、`dryRun`、是否带了 `planDigest`（只记有无）、调用方传的 `repo` 原值（供排查 `PATH_OUTSIDE_ROOT`），以及服务端按动作 id 从目录解析出的 `owl:versionInfo` 与**该动作**的 `definitionDigest`（接口文档 §5.13 已定义的单个动作摘要，能与 `model_list_actions` 逐条对上；不记整份 `catalog.ttl` 的摘要）；标签、定义、gherkin 这类正文一律不记；画像外的调用不解读参数，结构性参数为空，只记 sha256；结果（`ok` 或错误码）；目标 worktree 路径、分支、HEAD（还没定位到仓库就被拒时为空）；每个被写文件改动前后的 sha256；`governance_record_approval` 另记它产生的提交号与 AgentActivity 的 IRI，只用来关联。`declared`（调用方对自己身份与会话的声明）：`clientInfo`（stdio 取 `initialize` 里的；HTTP 传输没有 `initialize`，取每次请求 `params._meta` 里的，依据是 MCP Python SDK 的 `CLIENT_INFO_META_KEY`；接口文档 §3.2 现在只写了 `_meta` 带协议版本和客户端能力，实施 PR 在 §3.2 补上 clientInfo），`record_approval` 的 `activity.agent`、`activity.sessionRef`。分组按字段语义划分，不按值从哪里来：结构性参数是服务端收到的请求值，照实记在 `measured.request` 下（对应 Kubernetes 审计的 `objectRef`、CloudTrail 的 `requestParameters`），只说明「服务端收到了什么」；`declared` 组的字段只出现在 `declared` 下，不进 `measured`。声明字段只用来关联，任何判定都不能用它。
  4. **存放与并发。** 文件为 `<git-common-dir>/aisep/calls.jsonl`（`git rev-parse --git-common-dir`，先例是接口文档 §3.5 把写锁放在 `.git` 内）。位置由启动参数决定，调用方传的 `repo` 不参与，所以还没定位到仓库就被拒的调用（`PATH_OUTSIDE_ROOT`）也有地方写。按顺序取：① 第一个 `--allow-root`，它本身在某个 Git 仓库里时取该仓库的 common dir；② 否则（没带 `--allow-root`，或它是外层的非仓库目录）取启动参数 `--repo` 的 common dir；③ 都取不到时不写日志，启动时与每次被审计调用时在 stderr 报警告（按第 5 款 fail-open）。不用 cwd 兜底，免得日志落到意料之外的仓库。追加前拿仓库级 `flock`（`<git-common-dir>/aisep/calls.lock`，与按 worktree 加的写锁分开，因为各 worktree 写同一个文件），再用 `O_APPEND` 一次写入一整行。不进工作区，不进模型图，不推远端，不做哈希链（没有外部锚点的链挡不住重算，反而让人误以为日志防篡改），不做轮转。
  5. **失败策略。** 日志写不进去时，工具返回结果不变，只在 stderr 报警告（fail-open）。A 层是排障记录，不能因为日志写不进去挡住建模；B 层改为 fail-closed。
  6. **与已有记录的关系。** 调用日志是唯一的文件外记录，不是 ADR-013 所说的「进行中状态」，不参与 gate、guard、approvalState 推导或任何合并判据。它也不是 ADR-026 所说的「执行记录」：不进模型；B 层那份签发的执行记录到时另行命名。它可经只读 MCP 工具 `model_call_log` 查询：只列在 `workbench` 画像（以及测试用的 `all`），不列在 `agent` 画像；不收 `repo` 参数，按第 4 款的取位规则由启动参数定位日志文件，读的就是写的那一份；只返回日志行原样解析的内容（只有哈希与标识符，不含模型正文），另附该行的字节偏移作行键，不聚合、不改写；annotations 为 `readOnlyHint: true`、`idempotentHint: true`、`openWorldHint: false`，结果随日志增长变化、不随 Git 内容变化；它自己是只读工具，调用不记日志行（第 2 款）。不列入 `agent` 画像，是免得代理把跨调用存在的日志当成跨会话的进行中状态来用（ADR-013）；画像不是安全边界（接口文档 §4），代理照样能直接读这个文件，这一点不防。它不能代替 AgentActivity、`AISEP-Session` trailer 或批准记录，那两者都不动；它不作身份证据；批准是否出自本人，计划由 #120 的签名方案负责（未落地，方案待 Albert 决定）。
  7. **B 层（防代理篡改的审计）推迟，触发条件。** 下列任一出现即启动：① 动作改为唯一写入途径；② guard 升为硬门槛；③ 代理改用另一个 macOS 用户（#120 的后续项）；④ ADR-024 恢复条件②（第二个批准人或使用者）或③（外部数据或受监管数据进入模型）；⑤ HTTP 服务不再只绑本机。届时与 `mergecheck` 文件级对账一起做：记录方放到代理的信任边界之外（服务以另一个 OS 用户运行，代理经带令牌的 HTTP 调用，令牌方案即 ADR-014 Q1 打包前要定的那个），身份字段绑定到令牌，记录 fail-closed，链头 checkpoint 用代理读不到的密钥签名（#120 落地后可复用它的签名与信任根；#120 未落地，方案待 Albert 决定），远端锚点用**受规则集保护的普通分支**（禁止删除、禁止非快进、限定推送者）或 CI 产物，不用自定义 ref。文件级对账另以「已决定禁止直接编辑」为前提（要先修订 ADR-026 第 1 款与接口文档「MCP 写工具不是唯一写入途径」一段，并补视图、布局类写工具）。
- **理由**：被拒的写调用和动作调用（guard 拒绝、删除两段式被拒、参数校验拒绝）现在事后查不到（对照报告 G6/R2），这是 Albert 点名的隐患。原提案「服务端写入所以不是自报，`refs/aisep/audit` 加哈希链，远端禁止强推」的前提核实后不成立：编码代理的 MCP 服务端是代理按 `.mcp.json` 自己拉起的 stdio 子进程（`tools/aisep-mcp`），跑的是代理 worktree 里的代码（`tools/pyrun.py`），系统用户与代理相同；哈希链没有密钥和外部锚点，代理能整条重算；`refs/aisep/*` 不记 reflog；GitHub 的规则集与分支保护只管分支和标签，管不了自定义 ref，克隆与 CI 默认也取不到它；「会话、代理」字段服务端拿不到可信来源。所以照实降级为 A 层，把防篡改写成有触发条件的 B 层：直接编辑还允许时，旁路照样能改模型，给可绕过的路径做防篡改日志没有落点。参照与差别：
  - Kubernetes 审计、AWS CloudTrail、OWASP Logging Cheat Sheet：被拒的请求也记，审计后端与状态存储分开，区分系统产生的字段与来自用户输入的字段。本条照做（成功与拒绝都记；日志不进模型图；`measured` / `declared` 分组）。差别：它们的记录方（apiserver、AWS）不在调用方控制之下，AISEP 的 stdio 服务端由调用方拉起，没有可信记录方，所以 A 层不宣称防篡改。
  - CloudTrail digest 签名、Certificate Transparency（RFC 6962）：防篡改靠记录方持有的密钥加外部保存的历史，不靠哈希链本身。B 层沿用这一做法。
  - CloudTrail `LookupEvents`、GitHub 组织审计日志 REST API：只读查询接口，按时间倒序，用不透明游标续页，服务端不存游标。`model_call_log` 照做（游标编码文件身份与字节偏移，符合接口文档 §3.5 的无状态要求）。差别：它们按账号权限开放查询，这里只列在工作台画像，因为代理读日志的风险是把它当进行中状态（ADR-013），不是越权。
  - Gerrit NoteDb：专用 ref 可信是因为服务器是唯一写入方、由服务端 ACL 把关。AISEP 本机写入与代理同权，所以不用自定义 ref；「唯一写入方」到 B 层靠「代理换用另一个 OS 用户」实现。
  - Palantir Foundry action log（作对照，不作依据）：只记成功的提交，且做成模型里可查询的对象。本条相反：被拒也记，不进模型图，因为 AISEP 的模型图同时是 gate、approvalState 推导与批准的对象，运行记录混进去会污染这些判定的输入。
- **未采纳的方案**：
  - A. 原提案 `refs/aisep/audit` + 哈希链 + 远端禁止强推：理由见上；多个 worktree 并发写这个 ref 还需要比较并交换。
  - B. 维持现状，只在 ADR-026 写触发条件：最省事，但留下被拒调用不留痕的隐患。
  - C. 写进提交 trailer：调用方自报，且只覆盖已提交的成功写入，被拒调用没地方写。
  - D. 像 Foundry 那样把执行记录做成模型对象：违背 ADR-013，也与 G3「领域区与工具区分开」的方向相反。
  - E. 现在就做 B 层：要另一个 OS 用户、令牌、签名与远端锚点；直接编辑还允许时防篡改没有落点。
- **与已有 ADR 的关系**：
  - ADR-013：原文不改。按本条理解，服务端调用日志是唯一的文件外记录，是本机运维记录，不是进行中状态，不参与任何判定；ADR-013 理由里引的「MCP 不保存文件外状态」同样按本条理解。
  - ADR-014：Q1（打包前定令牌）不变，B 层复用它。
  - ADR-019：第 2 款，本条不改冻结范围内的判据；第 5 款，规范与接口文档的改写随实现 PR 落地。
  - ADR-024：本条是 MVP 放宽期间的例外（见状态）；B 层的触发条件④直接引用它的恢复条件②③。第 7 款「硬规则 7 不放宽」原文不改，按本条理解（依据：Albert 2026-11-27 拍板「全部按推荐」所采纳的 G6 修订方案，其中列明改写硬规则 7 后半句）：调用日志是本机运维记录，不是模型或治理状态；硬规则 7 的其余约束不变——不存在任何「上报进行中状态」的写入（ADR-013），模型与治理状态只在 Git 里的文件中。
  - ADR-026：第 1 款「不建执行记录」、理由段「不建 action log」、「与已有 ADR 的关系·ADR-013」条「不写日志」原文不改，按本条理解：调用日志不是那里所说的执行记录；动作仍是推荐通道，直接编辑照旧允许（B 层触发前不变）。
- **后果**：
  - 新增一个跨调用存在的本机文件、一把仓库级锁和一个只读工具 `model_call_log`（工作台画像）；接口文档 §3.5「会话、游标、草稿、订阅、进行中标记不存在」仍然成立，调用日志不构成会话。
  - 能排查诚实代理的反复试探与被拒情况；防不住恶意代理。已知限制：服务端写完文件、还没写日志时进程崩溃，这条记录会丢；不经 MCP 的改动不留记录；代理可以改服务端代码让它不记，或直接删改日志。
  - 不新铸 IRI，不改 `modules/` 与 `models/`。
  - **实施（issue #170）**，一个 PR 内含写日志、读工具 `model_call_log`、测试与下列文档改写，`aisep/**` 改动走合并前独立评审，负例由不参与实现的评审人构造。入口：本条合入 `main`。出口（可证伪的测试，全部通过）：
    1. 每个被审计工具成功调用一次，日志恰好多一行，`outcome=ok`，改前、改后哈希与磁盘上的真实文件一致（`governance_record_approval` 只在测试夹具的临时仓库里用 `workbench` 画像（或 `all`）跑，不碰 `models/` 下的真实模型，不产生真实批准记录）；
    2. 下列拒绝各一条用例，各多一行且结果值正确（`UNKNOWN_TOOL` 是日志专用值，见决策第 2 款；其余按接口文档 §5.14 的错误码）：参数校验 `INVALID_ARGUMENT`、guard 拒绝 `PRECONDITION_FAILED`、删除两段式被拒（不带 `planDigest` 为 `PLAN_REQUIRED`，带旧的为 `PLAN_STALE`，各一条）、`PATH_OUTSIDE_ROOT`、agent 画像调用 `governance_record_approval`（`UNKNOWN_TOOL`）；
    3. 两个 worktree 里各起 4 个服务进程，每个进程同时追加 50 次被审计调用，最后恰好 400 行，每行都能解析；
    3a. 只带 `--repo`、不带 `--allow-root` 启动时，日志写到 `--repo` 的 common dir；两者都没有时不写日志、stderr 有警告，工具结果不变；
    3b. 同时带 `--allow-root`（在仓库 X 内）和 `--repo`（仓库 Y），调用方在参数里传另一个仓库 Z 时，日志写到 X 的 common dir，Y、Z 下都没有新行；
    4. 日志文件不出现在任何 worktree 的 `git status` 里，`model_query` 查全部图查不到日志内容；
    5. 只读工具、以及审计集合外的未知工具名都不产生日志行，T4 仍然全绿；
    6. 日志目录设为只读后，工具返回结果与原来逐字节相同，stderr 有警告；
    7. `declared` 组字段（`clientInfo`、`activity.agent`、`activity.sessionRef`）只出现在 `declared` 下，不进 `measured`；结构性参数只出现在 `measured.request` 下；
    8. 去掉挂钩后第 1、2 条测试失败（证明测试能抓到缺失）；
    9. 每行 `v` 为 `1`；`model_apply_action` 行的 `definitionDigest` 等于同一目录下 `model_list_actions` 里该动作的 `definitionDigest`，改动该动作定义后新行的值随之变化；
    10. `model_call_log`：`workbench` 与 `all` 画像的 `tools/list` 有它，`agent` 画像没有；输入模式里没有 `repo`；连续调 N 次被审计工具后，第一页条数为 min(N, limit)、按时间倒序、与磁盘上的日志行逐字段一致；拿到游标后再追加若干行，续页结果不变；日志被截短或换掉后旧游标返回 `INVALID_ARGUMENT`；手工插入一行非 JSON 和一行 `v: 99`，两行都不出现在结果里，分别计入跳过数；每个过滤条件各一条用例（至少一条组合过滤），去掉某个过滤条件的实现，对应用例失败；调用 `model_call_log` 本身不产生日志行；
    11. 哨兵检查：用一个哨兵标签调一次 `model_add_element`，`calls.jsonl` 与 `model_call_log` 的整份输出里都搜不到这个标签。
  - 实施 PR 同步改写的文档：元模型规范四处加例外并引用本条：§6.9「只建定义，不建执行记录」、§8.3 的 `model.apply_action` 行「不留执行记录」、§8.3 末段「MCP 不保存任何不在文件里的状态」、§8.3 末段「不记录『执行过哪个动作』」（改为：不在模型里记录执行过哪个动作，服务端调用日志按本条另记）；接口文档 P1 加例外（表头注明「P1 由 ADR-031 修订」），§3.2「协议没有会话」补一句「调用日志不构成会话」，§3.3 写明还没定位到仓库就被拒的调用写到哪里，§3.4 第 4 点补「调用日志不用于恢复」与「调用日志用仓库级锁，跨 worktree 串行追加」，§3.5 表加一行「调用日志：在 `.git` 内，跨调用存在，不进版本库，不参与判定」（T4 原文已是「所有只读工具的结果」，不用改），§5.13 中「不留执行记录，不写日志文件」改写，新增一节「调用日志」（字段、来源分组、行格式版本 `v`、挂钩点、失败策略、威胁模型）；§2 操作表加一行「调用日志」（工作台 ✔，编码代理 —）；§4 工具总表加 `model_call_log` 一行，画像表 `workbench` 加它、`agent` 的排除项加它，「规范外的工具」一句补上它；§5 新增 `model_call_log` 一节（入参、出参、游标、错误）；§8 `client.ts` 草图补对应方法；`docs/actions.md` 中「动作不产生审批项，也不留执行记录」与「动作目录」一节（配方一、三的一次调用版）里的「不建执行记录」改写对用户的说法；`AGENTS.md` 硬规则 7 只替换后半句：前半句「不存在任何『上报进行中状态』的写入（ADR-013）」保留，「所有状态都在 Git 里的文件中」改为「模型与治理状态都在 Git 里的文件中；服务端调用日志是本机运维记录，不是模型状态（ADR-031）」（走合并前评审）。
  - 回滚：去掉挂钩，文档恢复原口径。已写的 `calls.jsonl` 保留；删不删由 Albert 决定，它不进版本库，删掉后无法恢复。
  - 推迟项及触发条件：B 层与 `mergecheck` 文件级对账见决策第 7 款；日志轮转与保留期，在单个文件超过 64 MiB 或出现分享日志的需求时做（按大小轮转，分享前先界定能外发哪些字段，aisep 是公开仓库）；调用日志的聚合、统计、全文搜索与导出，在出现实际需求时做（`model_call_log` 只按条件列行）。

## ADR-032 · 2026-11-27 · 工作台视图的查看与编辑边界

- **状态**：已采纳（Albert 2026-11-27 拍板，第 22 条）。第三批拍板第 16 条定了 Q1、Q3、Q4，均按推荐；按第 17 条在草案阶段做过一轮跨模型评审（ADR-021 第 2 款，Albert 已同意），评审意见已处理。修订 ADR-028 第 4 款的适用范围与其后果末条，原文不改，以本条为准；ADR-016 R4-5、ADR-017 R3 不变。按 ADR-019 第 5 款，规范、接口文档与 `AGENTS.md` 的条文在对应阶段的实现合入 `main` 前保持原口径，改写随实现 PR 一起做（见后果「文档同步」）。依据的设计提案是协调会话的「工作台视图的查看与编辑：最终设计提案」（2026-11-27，综合 model-first、diagram-first、risk-first 三份提案与一份评审意见）。
- **背景**：
  - `models/` 下现在没有一张声明视图（`arch:Diagram`）；视图只能经 CLI `tools/aisep.py diagram` 出图，工作台看不到。
  - 视图写工具不在本版（接口文档 §1）。通用写工具按名拒绝 `arch:inView`（`aisep/write_tools.py` 的不接受谓词表；接口文档 §5.2、§5.12），拒绝理由是「视图成员关系归视图，视图写工具不在本版」。ADR-028 后果末条同样写明「视图成员关系仍没有写工具，不由本条放开」。
  - 写工具的 `file` 参数只接受 `models/<slug>/<名>.ttl`，不接受子目录（`aisep/write_tools.py` 的 `file` 校验；`aisep-mcp/tests/test_actions_invariants.py` 把 `models/workbench/sub/x.ttl` 列为动作必须拒绝的落点）。加载端不受限：`aisep/gitio.py` 的 `model_files` 已含 `models/` 下的子目录。
  - 出图只在模型成员里找视图：`aisep/diagram.py` 的 `select` 遇到不带本模型 `arch:inModel` 的视图直接报错。`mergecheck` 的 `_scope` 按 `arch:inModel` 把视图计入模型的比较范围，`aisep/diff.py` 把 `arch:inView` 归到宾语视图名下（接口文档 §5.8 第 6 步「成员谓词归宾语」）。视图不带 `arch:inModel` 时 gate 已经拒绝：`modules/aisep-core/shapes.ttl` 的 `MembershipShape` 报 L1 与 L3 Violation，结果 FAIL（PR #179 实跑探针；`aisep-mcp/tests/test_set_attributes.py` 的 `test_adr032_view_facts_today` 钉住 L1 这一条）。真正没有检查的是跨模型成员：视图属 A 模型、成员属 B 模型时实跑 gate PASS，只在成员类型不在视点里时出一条 L3 视点 Warning。
  - 视点符合性已部分检查：`modules/am4/metamodel.ttl` 已加载 `archimate4_viewpoints.ttl` 与 `core-shapes.ttl`，ArchiMate 视图的成员类型不在视点 `arch:includesConcept` 里时 L3 给 Warning（同一测试钉住）。`modules/c4/metamodel.ttl` 没有加载 `c4_viewpoints.ttl`，C4 视图没有这项检查；实跑中一张以 `c4vp:SystemContext` 为视点的视图收进 ArchiMate 元素也没有视点 Warning，反而因 C4 视点 IRI 不是图里的 `arch:Viewpoint`，被 `core-shapes.ttl` 报一条 L3 Warning「必须声明恰好一个视点」。
  - 现有写工具已能改视图的一部分：`model_set_attributes` 接受视图作主语（`test_view_as_target`），`arch:viewConformsToViewpoint` 不在不接受谓词表（`RESERVED`）里，现在就能改视点（`test_adr032_view_facts_today` 实跑）；`model_remove` 能删视图并摘除以它为宾语的 `arch:inView`（接口文档 §5.5）。现在没有入口的只有 `arch:inView` 的增删与新建视图；`model_add_element` 建不出规范 §3 形状的视图：`slug` 须匹配 `SLUG_RE`（`^[A-Za-z][A-Za-z0-9]*$`，不允许 `view-{slug}` 里的 `-`），`file` 经 `_check_file` 拒收子目录。
  - 规范 §4 视图条已写「布局坐标存放在 `views/<视图>.layout.json`，不进语义模型」，但没有任何实现，§13 把「图形布局」列在第一批范围之外；`aisep/diagram.py`、`aisep/diagram_c4.py` 文件头写「no coordinates are stored anywhere」。
- **决策**：
  1. **分三阶段放开，先读后写。**
     - **P1 只读**，不需要本条放开任何写入面：**P1a 能看**（列视图、出图、点选元素联动详情与「所在视图」、切换 ref：main、分支、批准记录的 headCommit）；**P1b 能比**（关口页把视图类改动单列一组，注明「视图不可单独批准，随所属模型一起看」，可跳到视图页看两个 ref 的成员差异）。只读工具的契约随实现 PR 写进接口文档（ADR-019 第 5 款），现由 PR #174 提出 `model_list_views`、`model_render_view`；按第 17 条不做跨模型评审。P1b 不改关口页「批准候选」对视图的排除：视图不能被预填进 `approves`（R4-5）。
     - **P2 视图语义写**（新建视图、增删成员），只进 `agent` 画像；改视点、删视图现已可经 `model_set_attributes`、`model_remove` 做（见背景），P2 不另开工具，只把它们纳入第 4 款的约束并补契约。
     - **P3 布局写**：唯一的工具 `view_set_layout`，进 `agent` 与 `workbench` 两个画像。
     - 接口文档 §1「视图与布局的写工具不在本版」改为分阶段放开：P2 实现合入时改为「视图语义写工具只在 `agent` 画像（见对应小节）；布局写工具不在本版」，P3 实现合入时删去该项。
  2. **工作台的写边界。** 工作台最终是「只读 + 2 个写操作」：`governance_record_approval` 与 `view_set_layout`。工作台**永远不写模型语义**：除 `governance_record_approval` 新增批准记录文件（`models/<slug>/governance/*.ttl`，`aisep/approval.py`）外不写任何 `.ttl`，不写元素、关系、视图及其成员；新建视图、增删成员、改视点、删视图只给编码代理。接口文档 §2「工作台：只读 + 1 个写操作」与 §8 `client.ts` 草图「工作台不写模型」随 P3 实现 PR 改写；P3 之前两处原文不变。
  3. **视图文件与成员落点（修订 ADR-028 第 4 款适用范围）。** 每张视图一个文件 `models/<slug>/views/<视图 slug>.ttl`，内含视图主语块（`a arch:Diagram`、恰好一个 `arch:viewConformsToViewpoint`、恰好一个 `arch:inModel`、标签），以及全部成员三元组 `<成员> arch:inView <视图>`。成员三元组的主语仍是元素或关系（规范 §4 不变），只是**物理上落在视图文件里**，每个成员一个主语块。视图实例 IRI 按规范 §3 的 `{model}view-{slug}` 照常铸，不新铸元模型术语。
     - ADR-028 第 4 款（落点由已有三元组决定；原来没有值时写进 `rdf:type` 所在文件）**不适用于 `arch:inView`**：新增的 `arch:inView` 写进宾语视图所在的视图文件；移除时在三元组所在的文件里摘除（兼容手写在别处的旧三元组）。落点是写工具的行为约定，gate 不检查文件落点，与 ADR-028 第 4 款同一口径；手写 ttl 也按此放。
     - ADR-028 后果末条「视图成员关系仍没有写工具」：自 P2 实现合入起由 P2 的视图写工具放开。`model_add_element`、`model_set_attributes` 仍按名拒绝 `arch:inView`，拒绝理由改为指向 P2 的成员工具。
     - 写工具的落点白名单只为 P2 的视图写工具多放开 `models/<slug>/views/<视图 slug>.ttl` 这一种形状；通用写工具与动作的 `file` 参数仍只接受 `models/<slug>/<名>.ttl`，`models/<slug>/governance/` 照旧拒写（`aisep/writer.py` 的 `check_paths`）。
  4. **视图必须带 `arch:inModel`，成员只限本模型。** 自 P2 实现合入起，所有能改视图的写入口（P2 的新工具，以及现有的 `model_set_attributes` 改视点）都拒绝（`WRITE_REJECTED`）三种情形：视图没有恰好一个 `arch:inModel`（gate 已报 Violation，入口拒绝只是提前给出同一结论）；成员与视图不属同一个模型（元素与关系都按其 `arch:inModel` 判）；成员的记法与视点的记法不符（C4 视点只配 C4 元素，ArchiMate 视点只配 ArchiMate 元素；改视点时按改后的视点核对现有成员）。P2 之前现有路径不受第二、三种情形约束，这是现状，P2 的出口③覆盖现有路径。类型不在视点 `arch:includesConcept` 里不拒绝，只给 Warning：ArchiMate 视图现已由 L3（`core-shapes.ttl`）给出，不另加；C4 没有这项检查，由 P2 加载 `c4_viewpoints.ttl`（或等效的视点定义）补上，同时消掉 C4 视图「必须声明恰好一个视点」的误报。规范 §10.1 把「视点不符」列在 L4，与现状的 L3 不一致，随 P2 文档同步按现状改写。理由见「理由」第 3 条。手写 ttl 的跨模型成员与记法不符 gate 不拒，P2 也不为它们加 gate 检查，由 P1b 关口页的视图分组让人看见；升为检查的触发条件见后果「推迟项」。
  5. **批准口径不变。** 视图仍不可批准，`approves` 仍拒绝视图（R4-5）；`arch:inView` 计入视图、不计入元素（ADR-017 R3）；视图属于已批准模型时，改它的成员算改该模型，要重批该模型（R4-5 下视图改动计入所属模型；`mergecheck` 报 `unapproved-change-to-approved`）。这是现状，本条不改；P2 入口的探针只用来确认现状。布局文件不在任何 RDF 图里，不进批准对象与 `mergecheck` 的比较范围（第 6 款）。
  6. **布局是表示层文件（P3）。** 路径 `models/<slug>/views/<视图 slug>.layout.json`，可选，缺省不存在（无布局即全自动布局）。格式 `aisep-layout/1`：`{"format","view","nodes":{"<元素 IRI>":{"x","y","w","h"}}}`，整数坐标，规范化写出（键排序、每节点一行、末尾换行，读进再写出逐字节相同）；不存颜色、z 序、隐藏标志。**唯一不变式：成员只取自 RDF，布局只能改位置，不能增删或隐藏成员**——布局里多出的 IRI 忽略并给 Warning，RDF 有而布局没有的成员照样画出（由自动布局放置），`w`、`h` 低于下限时钳到下限。布局不进任何图区（领域区、工具区都不进，ADR-030 之外的第三类文件），`model_query` 读不到，只由 gate 的布局校验与出图的专门解析器读。「出图是模型的纯函数」改述为「出图是（模型，可选布局文件）的纯函数」，仍然确定。gate 布局校验：JSON 不合法、`format` 不认识、`view` 与文件名不对应 → Violation；孤儿键、未规范化 → Warning（两条分支一删成员一改布局，合并后不应让 `main` 变红）。
  7. **`view_set_layout` 的写入约束（P3）。** 入参 `{view, branch, layout|null, ifMatch}`；`ifMatch` 必填，是布局文件当前内容的 sha256，新建传 `"absent"`，不一致返回 `CONFLICT`，磁盘一个字节不改（参照 HTTP `If-Match`，RFC 9110 §13.1.1）；`layout: null` 删除文件，回到自动布局。一律拒绝三种情形：① 写默认分支；② 目标 worktree 有未提交改动（含代理的）；③ 该分支 merge-base 之后已有批准提交（新增了 `models/<slug>/governance/*.ttl`），避免让已有批准在合并时失效。复用 `aisep/approval.py` 已有的 worktree 定位、仓库锁与提交和并发撤回路径（先 `git commit --only`，发现并发提交时再撤回），提交信息用固定模板；**干净检查不能直接复用** `approval.py` 的 `_dirty`：它只比对 `models/` 下的 `.ttl` 与 `models/` 下的暂存，看不见 `.layout.json`，也看不见 `models/` 以外的改动（`aisep-mcp/tests/test_record_approval.py` 的 `test_adr032_dirty_check_ignores_non_ttl` 钉住），照搬会让②对布局文件不生效，代理未提交的布局被覆盖并提交；②按整个 worktree 的 `git status --porcelain --untracked-files=all`（含暂存与未跟踪）判，非空即拒；服务端先做格式校验与规范化再写。工作台未保存的拖动只在客户端，服务端不持有草稿（ADR-013）。
  8. **审计与分区。** P2 的视图写工具（若复用现有写工具则已在集合内）与 `view_set_layout` 进 ADR-031 第 2 款的被审计集合，成功与被拒都记，随各自实现 PR 扩充；只读的 `model_list_views`、`model_render_view` 不记。视图定义、成员、视点属于领域区（ADR-030）；只读出图工具只读领域区，ADR-030 的「查询面 → 读哪一区」表随 P1 实现 PR 加一行；布局文件按第 6 款不进任何区。
  9. **待定项（P3 入口时由 Albert 定）。** ① 布局文件的评审分级：现行 ADR-019 第 1 款、ADR-024 第 1 款下 `models/` 下不是 `.ttl` 的文件一律合并前评审，即每次拖动保存都要合并前评审；推荐「通过 gate 布局校验即走合并后评审」，定了就修订这两款与 `AGENTS.md`。② 已存坐标如何与 ELK 结合：先查 ELK 官方文档确认「有坐标节点原样保留、只放置缺坐标节点」能用哪种机制实现（layered 的 interactive 策略只用已有坐标推断分层与顺序，最终坐标会重算），查不到可行机制就改为「有坐标节点原样使用、缺坐标节点按 ELK 结果放置并对重叠给 Warning」，据此写定 P3 出口③。
  10. **评审路径与新铸 IRI。** 本条在草案阶段做过一轮跨模型评审（第 17 条）；P1 只读工具不做（第 17 条）。P2、P3 的实现 PR 走合并前独立评审；其接口契约以本条为准，不另做跨模型评审，除非实现中出现与本条不符的新证据，届时先问 Albert（ADR-021 第 2 款）。本条新铸 IRI：0 个。
- **理由**：
  1. **先读后写**：P1 只增不改、可撤回，能让 Albert 尽快在工作台看到视图；写入面会扩大批准绕过面、引入并发与审计问题，放到 P2、P3 按入口条件逐个放开。
  2. **工作台不写 RDF**：语义写入的校验、事务、审计都已集中在编码代理的写工具上，工作台再开一条 RDF 写入路径就要复制这一整套；布局只改观感、不进语义模型，是唯一值得给工作台的写操作。参照 Archi：「从视图移除」与「从模型删除」分两档——移除成员走成员工具，删元素走已有 `model_remove`。
  3. **成员落在视图文件**：调视图不碰元素文件（尤其已批准元素所在的 `am4.ttl` 等），「PR 即锁」细到单张视图，并发改不同视图不在同一文件上冲突；语义不变（主语仍是元素），图差异与 `mergecheck` 按图判，不受文件落点影响。**`inModel` 强制**：不带时 gate 已报 Violation、出图报错，入口拒绝与之同口径。**成员限本模型**：跨模型成员现在 gate PASS，是真正没有检查的缺口；跨模型成员会让 `model_remove` 删 A 模型元素时被别的模型的视图挡住（接口文档 §5.5 跨模型引用一律拒绝），出图时又被 `diagram.py` 按本模型成员静默丢掉；也关闭了 ADR-017 后果所述「未批准模型的视图收进已批准元素、没有检查项能看到」在写工具上的路径。
  4. **布局与模型分开**：参照 Structurizr（布局与模型分开、没有坐标的节点走自动布局，差别是按 IRI 而不是按名称匹配，IRI 一经创建不改，避开「改名丢布局」）、Eclipse Sirius 的 `.aird`（语义模型不知道表示层，表示层单独存、单独 diff）、JSON Canvas（节点 `{id,x,y,w,h}`，纯文本、Git 友好）。差别：不存颜色、z 序、隐藏标志，因为它们都是「布局改变观感进而改变含义」的入口。
  5. **布局写入的三条拒绝**：参照 tldraw 把 document 与 session 分开（未保存的拖动只在客户端）；条件写参照 HTTP `If-Match`。「merge-base 之后已有批准提交即拒绝」是因为批准后再写入会让 ADR-019 第 3 款的批准提交豁免不再成立，已批准的分支要重评。
  6. **不做布局合并**：coArchi 的教训是不能靠 Git 逐行合并模型；语义部分照旧由 `mergecheck` 按图判，布局冲突只给「载入对方版本」「基于对方版本重新编辑」，不提供合并。
- **未采纳的方案**：
  - 前端图库（如 `@xyflow/react`）在前端重画 ArchiMate/C4：违反接口文档的前提 P10（工作台上游接触面固定；接口文档 §8 已以 P10 为由不引入 `@modelcontextprotocol/sdk`），要改前端依赖，且与 `diagram.py` 两套渲染迟早不一致。
  - 「每次拖动保存即提交」：批准后再拖一下就让批准在合并时失效。
  - 另建 `views/*` 草稿分支体系：草稿就是 Git 分支，改动就是 `model_diff` 与关口页，合并把关是 `mergecheck`，不另建机制（参照 IcePanel Drafts 的思路，不照搬其存储）。
  - 工作台也能改成员或视点：会让工作台成为第二条 RDF 写入路径；推迟，触发条件见后果。
  - 纯动态视图（Ardoq）与不绑定模型的形状（LeanIX）：评审要稳定的图，且破坏「视图是模型的投影」。
  - 签入锁（Sparx EA、BiZZdesign）：与 Git 作为真相源冲突。
  - 视图可批准或「视图随模型批准快照」：R4-5 已决不批视图；快照推迟，触发条件见后果。
- **与已有 ADR 的关系**：
  - ADR-003：三原语不变，视图仍是 `arch:View` 的实例。
  - ADR-009、ADR-013：工作台不保存状态；未保存的布局只在客户端，布局写入是一次落到 Git 的提交，不是「进行中状态」。
  - ADR-016 R4-5、ADR-017 R3：原文不改，口径见决策第 5 款。ADR-017 后果中「视图在未批准模型里时，没有检查项能看到已批准元素的视图从属变化」：P2 的写入口按第 4 款关闭这条路径，手写 ttl 仍可能出现，残余风险照旧登记规范附录 C。
  - ADR-019：第 1 款的评审分级见第 9 款待定项①；第 2 款冻结范围内的 `mergecheck` 判据本条不改；第 3 款批准提交豁免由第 7 款③保护；第 5 款决定了文档改写的时机。
  - ADR-021 第 2 款：本条草案阶段一轮跨模型评审，见第 10 款。
  - ADR-024 第 1 款：布局文件的分级见第 9 款待定项①；新增 IRI 的视图 `.ttl`（不在 `governance/` 下）照旧属于 MVP 放宽类，走合并后评审。
  - ADR-028：第 4 款适用范围与后果末条按第 3 款修订；第 1–3、5、6 款不变，`model_set_attributes` 继续拒绝 `arch:inView`。
  - ADR-030（PR #172，已合入）：视图属于领域区，布局不进任何区，见第 8 款。
  - ADR-031（PR #171，已合入）：被审计集合随 P2、P3 扩充，见第 8 款。
- **后果**：
  - **实施的入口与出口**（出口的期望值来自独立来源：评审人写的查询或探针，不用实现者自写测试自证）：
    - **P0（本条）**。入口：Albert 第 16、17 条拍板。出口：一轮跨模型评审的意见逐条处理并写进 PR；本条合入并改为「已采纳」。
    - **P1a 能看**。入口：procurement 先手写并合入 1 张 ArchiMate 4 声明视图、1 张 C4 声明视图（按第 3 款放在 `models/procurement/views/`，带 `arch:inModel`，其中一张故意含一个视点外类型），gate PASS；工作台专用检出装好 `tools/elk`。出口：① 出图结果里的成员 IRI 集合等于评审人按 `diagram.select` 同一口径写的独立 SPARQL 结果；② 取视图改动前后两个提交为 `ref`，成员分别等于各自提交上的独立查询结果；③ 出图后工作台其它 SVG 图标的计算样式不变，系统深色、应用浅色时图背景是浅色调色板值；④ 含 `<script>`、`on*`、`foreignObject`、`javascript:` 链接的 SVG 进不了页面的可执行上下文；⑤ `workbench` 画像只多出只读工具，前端 `package.json` 与锁文件没有改动；⑥ PATH 去掉 node 时出图工具返回明确错误码，`model_query` 照常；⑦ 在工作台里给 Albert 打开 procurement 的两张视图，点选节点后右栏 IRI 与图上标识一致。
    - **P1b 能比**。入口：P1a 出口。出口：① 一个只改 `arch:inView` 的分支在关口页视图分组里出现，跳转后新增 / 移除成员等于两个 ref 的独立查询求差；② 两张图并排时箭头标记各自解析正确（DOM 检查 + 截图）；③ 带视图类条目的差异上，批准候选不含任何视图 IRI（负例）。
    - **P2 视图语义写**。入口：P0、P1a 出口；跑完三个探针并记进 PR：① 已批准模型里只加一条 `arch:inView`，`mergecheck` 报 `unapproved-change-to-approved`（确认第 5 款现状）；② 已定为不能：`model_add_element` 的 `SLUG_RE` 不允许 `-`，铸不出 `view-{slug}`，`_check_file` 拒收子目录，所以新建视图要新增工具（或为它单独放开 `slug` 与落点），P2 入口不再探；③ 确认 `model_remove` 删视图连带摘除以它为宾语的 `arch:inView`（接口文档 §5.5 所述现状）。改视点沿用 `model_set_attributes`（现已接受视图主语，接口文档 §5.12 现写「元素或关系」，随 P2 补写），只补第 4 款的记法拒绝，不另立工具。出口：① `model_add_element`、`model_set_attributes` 写 `arch:inView` 仍被拒（负例）；② 一次成员增删后 `git diff --stat` 只涉及该视图文件，元素文件 sha256 不变；③ 第 4 款的三种情形被拒，含经 `model_set_attributes` 改视点造成记法不符；④ 删视图后没有残留以它为宾语的 `arch:inView`；⑤ 通用写工具与动作写 `models/<slug>/views/x.ttl` 仍被拒（`test_actions_invariants.py` 的子目录负例照常通过）；⑥ 被拒调用在调用日志里有对应行（ADR-031 实现已合入时）；⑦ `test_merge_check_inview.py` 照常通过。
    - **P3 布局写**。入口：P2 出口；第 9 款两项已定。出口：① 两个写入方用同一个 `ifMatch` 写，后到者得 `CONFLICT`、文件不变；② 第 7 款三种情形都被拒，其中②含两条负例：worktree 里有未提交（含未跟踪）的 `views/*.layout.json` 时被拒、只有 `models/` 以外的未提交改动时也被拒，两例磁盘与分支均不变；③ 布局缺某成员时该成员照样画出，`w` 设 0 不能隐藏节点；④ 布局读进再写出逐字节相同；⑤ 加布局文件后 `model_query` 查 `?s ?p ?o` 计数不变；⑥ 已批准模型只改布局时，`mergecheck` 的 `problems` 为空；⑦ 工作台画像只多出 `view_set_layout` 一个写工具。
  - **文档同步**（随实现 PR，ADR-019 第 5 款）：P1 改接口文档 §1 注明只读工具、§2 工作台读表、§4 工具总表与画像、§5 新增小节、§8 `client.ts`，以及 ADR-030 查询面表；P2 改接口文档 §1、§5.2 与 §5.12 中「视图写工具不在本版」的拒绝理由、§5.12 `iri` 照现状写明含视图主语并补改视点的记法约束、新增视图写工具小节，规范 §4 视图条补「成员落在视图文件、`arch:inModel` 必填、成员限本模型」、§10.1「视点不符」按现状改写（ArchiMate 由 L3 `core-shapes.ttl` 给 Warning，C4 由 P2 补上）、附录 C 更新 ADR-017 残余风险的说法；P3 改接口文档 §1、§2「只读 + 2 个写操作」、§5.5 第 5 点「布局」、§8 `client.ts`，规范 §4「布局」条补「可选覆盖层」与不变式、§13 把「图形布局」改为部分在范围内、附录 C 中「布局文件出现前，删除不处理布局」，`aisep/diagram.py`、`aisep/diagram_c4.py` 文件头的「no coordinates are stored anywhere」改述；第 9 款①定为放宽时同步 `AGENTS.md`。
  - **推迟项与触发条件**（任一出现即启动）：
    - 跨模型成员（全景视图）：现在拒绝；出现真实跨模型全景需求时另立 ADR。
    - 工作台写成员或视点：不做；动作成为唯一写入途径（ADR-031 B 层触发条件①），或出现第二个使用者。
    - 视图随模型批准的快照：不做，用 `ref` 回看 headCommit 时的视图；ADR、关口模板或批准记录开始引用某张视图作证据时。
    - 手写 ttl 的跨模型成员、记法不符升为 gate 或 `mergecheck` 检查（缺 `arch:inModel` 已是 Violation，不在此列）：不做，关口页可见；出现第二个批准人（ADR-024 恢复条件②），或发现一次未被注意的此类改动进了主线。
    - `model_diff` 加布局类计数：不做（要改负例清单里的 `aisep/diff.py`）；评审者反映关口页看不出布局改动时。
    - ELK 增量布局、连线折点持久化：不做；自动放置的新节点与已存布局重叠被报告两次以上，或某视图边数超过约 30 条且走线不稳定被反馈时。
    - 布局合并工具：不做，冲突二选一；同一布局文件冲突两次以上时。
    - 前端图库：不引入；P3 的 SVG 拖动不够用（框选、连线编辑）时，届时过依赖评审。
    - 「视点不符」升为 Violation：保持 Warning；真实模型出现误导性视图时。
    - BPMN、UML、DDD、ext-* 视图与 Catalog、Matrix、规则式视图的编辑：不在本条；有模型实际需要且对应视点已接入时另议（只读出图另由各自 PR 处理）。
  - **残余风险**：布局文件不在 RDF 图里，`mergecheck` 看不到它的变化，安全性只靠第 6 款的不变式与 gate 布局校验；不变式被实现破坏（例如出图按布局隐藏了成员）时，批准人看到的图与模型不符。P3 出口③是这条的守门测试。
