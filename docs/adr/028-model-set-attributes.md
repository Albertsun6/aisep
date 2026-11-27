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
