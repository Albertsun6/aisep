# 模型动作目录

本文件告诉编码代理：要改模型时调用哪个写工具、几个工具怎么组合。参数、返回和错误码的完整定义只在《MCP Server 接口设计》（`docs/mcp-interface.md`）里，本文件只引用，不重述；两处不一致时以接口文档为准。

三点前提：

- **动作是推荐通道，不是唯一通道。** 人和代理仍然可以直接编辑 `.ttl`（接口文档 §1）。不管改动从哪来，提交和 CI 都只认 `gate`，合并时由 `mergecheck` 核对批准。
- **写工具只改工作区**，不 `git add`、不提交。写之前在候选图上跑 L0–L2，只拒绝本次新增的违规，被拒绝时磁盘一个字节不改（接口文档 §5.1）。
- **动作不产生审批项，也不在模型里留执行记录。** 每次写调用与动作调用（成功和被拒）只由服务端在本机记一行调用日志，供排查用，不进模型、不可经 MCP 查询（接口文档 §3.6，ADR-031）。批准只在关口做，只能由批准人本人做出；改了哪些元素由分支差异实时算（`model_diff`），不另存一份。

## 1. 基本动作

五个写工具就是五个基本动作，都在 agent 画像的 `tools/list` 里。

| 动作 | 工具 | 什么时候用 | 要点 | 接口文档 |
|---|---|---|---|---|
| 新增元素 | `model_add_element` | 模型里还没有这个元素 | IRI 由 `model` 和 `slug` 生成（不给 `slug` 时由 `altLabel` 转 camelCase）。非标签属性在新增时经 `attributes` 一起写。同参数重放无变化；同一 IRI 已存在且内容不同报 `IRI_EXISTS`，这时改用下面两个「改」的动作 | §5.2 |
| 新增关系 | `model_add_relationship` | 把两个已存在的元素连起来 | 只写限定关系资源，不写直连三元组。两端必须已存在，否则 `ELEMENT_NOT_FOUND`。同类型同端点重放返回已有的那一条 | §5.3 |
| 改名称、英文名、定义 | `model_set_labels` | 改 `skos:prefLabel`（中文名）、`skos:altLabel`（英文名）、`skos:definition`（定义） | IRI 不变。`altLabel`、`definition` 传 `null` 表示删除 | §5.10 |
| 改其他属性 | `model_set_attributes` | 改已存在元素或关系的其他属性，如 `aisep:priority`、`aisep:gherkin`、`aisep:path` | `set` 按谓词整体替换，`unset` 删除该谓词的全部值。类型、所属模型、关系端点不能改；三个标签谓词不收（走上一行） | §5.12 |
| 删除 | `model_remove` | 删除元素、关系或视图 | 唯一需要「先看计划再执行」的动作，见配方三。被批准记录等引用的元素删不掉（`REFERENCED`），只能退役 | §5.5 |

五个动作共同的行为：

- `dryRun` 为 `true` 时只算不写，返回与实际写入相同的结果。
- 同参数重放是安全的：返回里的 `changed` 为 `false`，文件不变。调用超时后可以直接重试。
- 批准记录、AI 活动和模型本身（`arch:Model`）不能经这些工具新增、修改或删除，返回 `PROTECTED_RESOURCE`。
- 写完用 `model_check` 快速自查（不带 `model` 参数：只查单个模型时，指向别的模型的引用会被报成违规）；提交前以 `model_gate` 的结论为准。

**没有对应动作的改法**（当前只能直接编辑 `.ttl`，或按下面的办法绕开）：

- 改元素类型：不支持。
- 改关系类型或端点：删掉旧关系（`model_remove`），再新建一条（`model_add_relationship`），IRI 跟着变。
- 新建模型目录和 `arch:Model` 声明：手写。
- 新建视图、布局：没有写工具。视图成员关系 `arch:inView` 也不能经 `model_set_attributes` 改（`INVALID_ARGUMENT`），要手写。

## 2. 属性值怎么写

`model_add_element` 的 `attributes` 与 `model_set_attributes` 的 `set` 用同一种写法：一个数组，每项是 `{predicate, value}`。

| 值的种类 | `value` 的写法 | 例子 |
|---|---|---|
| IRI（枚举值、指向别的资源） | `{"iri": …}`，完整 IRI 或前缀名 | `{"iri": "aisep:Must"}` |
| 普通字符串 | `{"value": …}` | `{"value": "Given …\nWhen …\nThen …"}` |
| 带语言标签的字符串 | `{"value": …, "lang": …}` | `{"value": "备注", "lang": "zh"}` |
| 带数据类型的字面量 | `{"value": …, "datatype": …}` | `{"value": "true", "datatype": "xsd:boolean"}` |

`predicate` 写完整 IRI 或前缀名（`aisep:priority`）。谓词合不合法不看白名单，由候选图上的 L1 闭世界规则判定：模型文件里出现的谓词必须在已加载的模块或本体里声明过，否则 `WRITE_REJECTED`，错误里带违规原文。

## 3. 配方

配方是几个基本动作的固定顺序。每一步都是一次独立的工具调用，各自校验、各自落盘；中途某一步被拒绝时，前面已经成功的步骤留在工作区里，按配方里写的办法处理。

### 配方一：登记验收标准并挂到需求

用途：给一个已存在的需求补一条验收标准。

第 1 步，新增验收标准，Gherkin 文本经 `attributes` 一起写：

```json
{"tool": "model_add_element",
 "arguments": {"model": "workbench", "type": "aisep:AcceptanceCriterion",
               "slug": "acProgressStagesShown",
               "prefLabel": "批准进度的四个阶段都能显示",
               "altLabel": "All four approval progress stages are shown",
               "attributes": [{"predicate": "aisep:gherkin",
                               "value": {"value": "Given 一个带待批准关口的分支\nWhen 批准记录被提交\nThen 工作台显示已批准待推送"}}]}}
```

显式给 `slug`，IRI 就是 `workbench:acProgressStagesShown`；不给时由 `altLabel` 转 camelCase，英文名长 IRI 就长。返回里的 `iri` 是新元素的 IRI，下一步要用。

第 2 步，用聚合关系把它挂到需求上，源端是需求，目标端是验收标准：

```json
{"tool": "model_add_relationship",
 "arguments": {"type": "am4:Aggregation",
               "source": "workbench:reqApprovalProgress",
               "target": "<第 1 步返回的 iri>"}}
```

`source`、`target` 写完整 IRI 或前缀名（`workbench:acProgressStagesShown`）都可以。

- 顺序不能反：验收标准还不存在时先建关系，返回 `ELEMENT_NOT_FOUND`，文件不变。
- 第 2 步被拒绝时，第 1 步的验收标准已经在工作区里。改正参数后重试第 2 步；不想要了就按配方三删掉它。
- 只做了第 1 步、没有挂到需求的验收标准不违反 L0–L2，写入层不拦，要靠自查和评审发现。

### 配方二：改已存在元素的属性

用途：改一个已存在元素或关系的属性值，例如调需求的优先级、改验收标准的 Gherkin 文本、改代码位置的路径。

```json
{"tool": "model_set_attributes",
 "arguments": {"iri": "workbench:reqApprovalProgress",
               "set": [{"predicate": "aisep:priority", "value": {"iri": "aisep:Should"}}]}}
```

- **`set` 是按谓词整体替换。** 调用之后，该元素在这个谓词上的值恰好是这次 `set` 里给出的那些。一个谓词要保留多个值时，把每个值各写成一项、`predicate` 相同，一次给全；只给一个就只剩一个。
- 不确定现在有哪些值时，先带 `dryRun` 为 `true` 调一次，返回里的 `before` 列出当前值，`after` 列出写入后的值。
- 删除一个属性用 `unset`，给谓词的数组：`"unset": ["aisep:priority"]`。同一个谓词不能同时出现在 `set` 和 `unset` 里。
- `rdf:type`、`arch:inModel`、`arch:source`、`arch:target` 不能经它改；`skos:prefLabel`、`skos:altLabel`、`skos:definition` 请用 `model_set_labels`。这七个谓词出现在 `set` 或 `unset` 里返回 `INVALID_ARGUMENT`。
- `arch:approvalState` 不能手写，它由批准记录推导；写它返回 `WRITE_REJECTED`。
- 不要用「先删除、再用同一 IRI 重新新增」来改属性：那样要连带重建关系，被批准过的元素还删不掉。

**改的是已批准元素时**：写工具不拦，`gate` 照常 PASS；把关在合并，`mergecheck` 报 `unapproved-change-to-approved`，要求同一个 PR 里有一条覆盖该元素的新批准记录，由批准人本人做出（`docs/methodology.md` §10.8）。动手前先对被改元素跑 `model_impact`（`mode` 取 `depends` 和 `ripple` 各一次），把结果写进 PR 描述。

### 配方三：删除元素

用途：删掉一个元素（连同以它为端点的关系）。删除是唯一的破坏性动作，固定走「看影响 → 取计划 → 按计划执行」三步。示例删的是配方一刚建的那条验收标准，它还没被批准过；已批准的元素删不掉，见本节末尾。

第 1 步，看影响面，两种模式各跑一次：

```json
{"tool": "model_impact", "arguments": {"focus": "workbench:acProgressStagesShown", "mode": "depends"}}
```

```json
{"tool": "model_impact", "arguments": {"focus": "workbench:acProgressStagesShown", "mode": "ripple"}}
```

第 2 步，取删除计划，不落盘：

```json
{"tool": "model_remove",
 "arguments": {"iri": "workbench:acProgressStagesShown", "cascade": true, "dryRun": true}}
```

返回里的 `plan` 列出会删除的资源（`delete`）、会摘除的成员关系（`detach`），`planDigest` 是这份计划的哈希。确认 `delete` 里只有目标本身和以它为端点的关系，没有不该删的东西；第 1 步的影响面用来判断删掉之后哪些元素要跟着复查，它列的是邻居，不会和计划逐项对上。

第 3 步，带着计划哈希执行：

```json
{"tool": "model_remove",
 "arguments": {"iri": "workbench:acProgressStagesShown", "cascade": true,
               "planDigest": "<第 2 步返回的 planDigest>"}}
```

- 第 2 步之后相关文件被改过，第 3 步返回 `PLAN_STALE`，文件不变：回到第 2 步取新计划。
- 第 3 步成功后响应丢了，带同一个 `planDigest` 重放是安全的，返回里的 `changed` 为 `false`。
- 不带 `cascade` 而删除会牵连别的资源，返回 `CASCADE_REQUIRED`，错误详情里带同一份计划和 `planDigest`。
- 返回 `REFERENCED` 说明元素被批准记录、追溯或别的模型引用，不能删除（被批准过的元素都属于这一类）。第 2 步带 `dryRun` 时就会返回它，不用等到第 3 步。这时改为**退役**：用配方二给它写上 `owl:deprecated` 和 `dcterms:isReplacedBy`，元素保留、标为已被取代。

```json
{"tool": "model_set_attributes",
 "arguments": {"iri": "workbench:reqApprovalProgress",
               "set": [{"predicate": "owl:deprecated", "value": {"value": "true", "datatype": "xsd:boolean"}},
                       {"predicate": "dcterms:isReplacedBy", "value": {"iri": "<替换它的元素的 IRI>"}}]}}
```

退役改的是已批准元素，合并时同样需要新的批准记录（见配方二末段）。

### 动作目录：配方一、三的一次调用版

配方一、三另有一份写成元模型定义的版本：扩展模块 `modules/ext-actions/` 的 `catalog.ttl` 里的 `aisep:ActionType` 个体（参照 Palantir Foundry 的 Action type：参数、有序步骤、提示级前置检查；不在模型里建执行记录，服务端调用日志见接口文档 §3.6）。两个固定工具读它：`model_list_actions` 列出目录里的动作和每个动作的参数说明，`model_apply_action` 按动作 id 执行一个动作。动作定义的写法、校验规则（`gate` 的 EA1–EA10 与执行器的 X1–X10）见接口文档 §5.13，执行见 §5.14。要查有哪些动作，也可以用 `model_query`：`SELECT ?a ?id WHERE { ?a a aisep:ActionType ; dcterms:identifier ?id }`。

动作目录也是**推荐通道**：上面的配方照旧可以逐个调写工具来做，两种做法写出的文件逐字节相同；`gate` 和合并核对不知道、也不关心改动是不是经动作做的。区别只有两点：

- 一个动作的几步在**一次写入**里完成，全有或全无：任何一步被拒绝，工作区一个字节都不改，不会留下配方一第 2 步失败时那种「只做了一半」的状态。
- 动作可以带**前置检查**（只读查询），不满足时返回 `PRECONDITION_FAILED` 和中文修法提示，不写。前置检查只是提示，不是合法性规则：逐个调写工具或直接编辑时不受它约束，`gate` 也不检查它。

目录里现在有两个动作：

- `register-acceptance-criterion`（登记验收标准并挂到需求）对应配方一：新增一条 `aisep:AcceptanceCriterion`，再用 `am4:Aggregation`（源端是需求，目标端是验收标准）挂上去。所属模型取需求所在的模型。需求必须写完整 IRI，不接受前缀名。两条前置检查：被挂的对象本身不能是一条验收标准；被挂的需求不能已退役（`owl:deprecated true`）。

```json
{"tool": "model_apply_action",
 "arguments": {"action": "register-acceptance-criterion",
               "params": {"requirement": "https://aisep.example/model/workbench/reqApprovalProgress",
                          "slug": "acProgressStagesShown",
                          "prefLabel": "批准进度的四个阶段都能显示",
                          "altLabel": "All four approval progress stages are shown",
                          "gherkin": "Given 一个带待批准关口的分支\nWhen 批准记录被提交\nThen 工作台显示已批准待推送"}}}
```

- `remove-element`（删除元素）对应配方三的第 2、3 步：固定按级联规划，必须先带 `dryRun` 为 `true` 调一次，取返回里的 `planDigest`，再带它执行；不带 `planDigest` 直接执行返回 `PLAN_REQUIRED`，错误详情里带计划和影响摘要。影响摘要只是提示，不受 `planDigest` 保护；配方三第 1 步的两种影响面仍建议自己跑。被引用的元素同样返回 `REFERENCED`，改为按配方三末尾退役。

```json
{"tool": "model_apply_action",
 "arguments": {"action": "remove-element",
               "params": {"iri": "https://aisep.example/model/workbench/acProgressStagesShown"},
               "dryRun": true}}
```

同参数重放同样安全：两个动作重放都返回 `changed` 为 `false`，文件不变（删除要带同一个 `planDigest`）。

## 4. 升级信号

现在的做法是「基本动作在代码里、组合写成本文件的配方或 `modules/ext-actions/catalog.ttl` 里的动作定义」。下表列的是说明这个做法开始吃力的可观测信号，留作日后判断动作机制要不要再升一档时的证据。本表只列信号：不规定信号出现之后做什么，也不限制信号出现之前做什么。表里的阈值是暂定值；遇到信号时怎么记账（是否开 GitHub issue、由谁登记）待 Albert 确认。

| # | 信号 | 怎么观测 |
|---|---|---|
| S1 | 出现一个真实改动：按任何顺序逐步调用基本动作都会被 L0–L2 拒绝，而整体是合法的 | 一个可复现的最小用例 |
| S2 | 同一条配方因为代理漏步或顺序错而返工，累计 3 次 | PR 评审评论里按配方名计数 |
| S3 | 出现第一条依赖「改之前」与「改之后」两个状态的业务规则（例如优先级只能调高不能调低） | 规则的一句话陈述。只看某一时刻模型状态的规则不算，它们应当写成校验规则，对直接编辑也生效 |
| S4 | 新增一种组合需要改 Python，而提出者不写代码 | 提出者与实现者不是同一方的需求条目 |
| S5 | 工作台要对选中的元素列出「可以做哪些动作」并按动作渲染表单 | 工作台的需求条目 |
| S6 | 治理加固恢复的任一情形出现：第二个批准人或使用者；外部或受监管数据进入模型；HTTP 服务不再只绑本机 | `docs/decisions.md` ADR-019 第 2 款的判据 |
