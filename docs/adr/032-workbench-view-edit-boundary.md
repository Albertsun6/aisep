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
