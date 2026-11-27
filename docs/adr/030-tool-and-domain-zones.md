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
