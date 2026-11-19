# Spike 结论：Linked.Archi 能否做 AISEP 基础设施层底座

日期：2026-11-19 · 环境：macOS arm64（Apple Silicon，不是清单里写的 Intel）、Python 3.12.13（uv 建的 venv；系统自带 3.9.6 太旧）、pyoxigraph 0.5.13、pyshacl 0.40.2、rdflib 7.6.0

## 结论：有条件通过 ✅（照计划采用其本体；校验与 AI 接口的一部分自己写）

> **关于 ArchiMate 4.0**：本次 spike 主体用的是 3.2。验证过程中，`AISEP 方法论总纲（草案1）` §6a 决定改用 **4.0 作为枢纽记法**，所以补做了 4.0 的验证（见 §2b）：同一套工具链只要设 `LA_NOTATION=4` 就能跑，所有结论在 4.0 上同样成立。

| 判断标准（清单 §7） | 结果 | 证据 |
|---|---|---|
| 许可证允许商用 | ✅ 通过（需署名） | 代码仓库全部 Apache-2.0；我们用到的本体全部 CC-BY-4.0 |
| 校验能拦住非法关系，报错可读 | ✅ 通过（有前提） | `scripts/negative_tests.py` 12/12 CONFIRMED；必须关掉 RDFS 推理、补 AISEP 自己的闭世界规则 |
| SPARQL 在百元素规模秒级返回 | ✅ 远超标准 | 3000 个元素时查询 14–70 ms |
| Claude Code 不需要太多提示就能正确增改模型 | ✅ 通过 | 5 个独立智能体、2 轮共 7 个任务：0 个用错类型、0 次越界改文件；建模每次第一遍就通过校验；第二轮全部自己写了 SPARQL |
| 工具链能在本机装起来跑起来 | ✅ | 纯 pip 安装，无 JVM、无三元组库 |

**一句话**：本体本身质量很高（ArchiMate 3.2 关系矩阵完整、报错文案可读、还附带一张机读的关系表），可以直接当元模型底座；但它是"开放世界"的，单靠上游 shapes 校验会漏掉 AI 最容易犯的错（拼错类型、悬空引用），而且 pyshacl 跑全量关系矩阵太慢。这两块要由 AISEP 自己补，补起来都很小（已在 spike 里做出原型）。

## 1. 许可证（清单 §0）

- 清单里的 `gitlab.com/linked-archi/linked-archi-meta` 现在跳转到登录页（403）；`github.com/linked-archi/linked-archi-meta` 也不存在。**本体源码仓库目前不公开**，只能拿到发布出来的成品。
- GitHub `linked-archi` 组织下 11 个仓库**全部 Apache-2.0**（含 meta-core，总纲 §8 的待办可以勾掉）。但 meta-core 等是 2019 年的旧版本体；现行本体只在 https://meta.linked.archi 发布。
- meta.linked.archi 的 `catalog.jsonld` 给每份产物标了许可证：245 份里 233 份 CC-BY-4.0，**12 份 CC-BY-SA**（`core-vis` 和整个 `edgy` 系列，外加 2019 年的 `archimate3/onto/3.0`）。
- 我们实际用到的文件（core、core-shapes、archimate3 onto/shapes/viewpoints/relationship-tables）**全是 CC-BY-4.0** → 可以商用、可以修改，只需署名。**不要引入 core-vis 和 edgy**，否则 SA 条款会传染到派生的本体文件。
- 已全部镜像到 `vendor/meta.linked.archi/ttl/`（245 个文件，带 `SHA256SUMS`、抓取时间 `FETCHED_AT`），离线可用，版本已锁定。

## 2. 跑通的闭环

```
model/sample-model.ttl ─┬─ la.py validate  (pyshacl：上游 shapes + AISEP 闭世界规则)  ~1 s
                        ├─ la.py check     (Python 查上游关系表；结论与 SHACL 一致)   ~10 ms
                        └─ la.py query     (pyoxigraph SPARQL)                         ~ms
```
- 示例模型：供应商（BusinessRole）—Assignment→ 报价审批（BusinessProcess）—Access→ 报价单（BusinessObject），1 个视图。每条关系写两遍：限定关系资源（供 SHACL 校验）+ 直连三元组（方便 SPARQL 遍历）——这和上游示例的写法一致。
- 三个查询（`queries/`）：元素清单、报价单影响分析（1 跳 / 2 跳）、视图内容，结果都正确。
- 上游 `linked-archi-apm` 的 `la-kg` 工具**不用改代码**就能直接查我们的模型（清点、影响分析模板都能跑）；在数据集缺少它需要的本体时，它会明确拒绝回答，而不是返回一个空结果。

## 2b. ArchiMate 4.0 复验

- 4.0 的文件（onto / shapes / viewpoints / relationship-tables）同样是 **CC-BY-4.0**，同样标 `draft`。
- `model-am4/sample-model.ttl`：同一个采购模型改用 4.0 类型（`am:Role`、`am:Process`、`am:BusinessObject`，视点 `ProcessCooperationViewpoint`）。check、validate、影响查询结果全部和 3.2 一致。
- 负例：非法的 BusinessObject → Process 分派，check 和 SHACL 两层都拦得住（SHACL 文案会直接列出合法的源类型）；在 4.0 模型里误用 3.2 的类型 `am:BusinessRole`，闭世界规则会报 "not a class declared"。**这一条正是"从 3.2 资料迁移过来"最容易犯的错，只有 AISEP 规则能抓到。**
- 差分测试（4.0 的 41 种元素类型 × 11 种关系，约 15% 的源元素带多个类型）：3 个种子共 1200 条，0 处分歧。
- 性能：1000 个元素时 validate 约 24 秒（4.0 的矩阵 shapes 比 3.2 小一半，3.2 是 33–74 秒），check 仍是毫秒级。
- 用法：命令前加 `LA_NOTATION=4`，默认仍是 3.2。

## 3. 踩到的坑（都已绕过，并有可执行测试兜底）

1. **RDFS 推理会掩盖悬空引用**：`arch:inView` 的值域是 `arch:View`，开推理后，一个不存在的视图会被"推断"成 View，于是校验通过。→ `validate` 默认 `inference=none`（子类判断照样生效，因为本体已经合并进数据图）。代价（异构评审指出）：子属性不再被蕴含，比如 `arch:partOfModel ⊑ arch:inModel`。所以 AISEP 规则需要显式同时覆盖这两个属性（已改）。
2. **上游是开放世界**：拼错的类型（`am:BusinesActor`）落在没有关系的孤立元素上时，上游 shapes 一声不吭。→ 新增 `shapes/aisep-closed-world.ttl`：类型必须是本体里声明过的类，或者是模型里声明的、其子类链能回到已声明类的子类（如 `:CloudServer rdfs:subClassOf am:Device`）；关系两端必须是某个模型里的元素。
3. **上游 core-shapes 有两条约束不合 SHACL 1.0 规范**（SPARQL 里用了 MINUS），pyshacl 会因此**整次拒绝运行**。→ 上游注释自己说明这里 MINUS 与 `FILTER NOT EXISTS` 等价，所以运行时改写后保留（每次打印 NOTE），"视图里放了视点不允许的元素"的 Warning 因此能正常报出。
3b. **pyshacl 的 `ont_graph` 只注入类层级，不注入个体**（如视点），导致"视图未声明合法视点"的误报 Warning。→ 改为把本体完整并进数据图。
4. **RDF 1.2 语法**：上游的示例和关系表用了 `rdf:reifies <<( … )>>`，rdflib/pyshacl 解析不了（245 个文件里有 9 个），pyoxigraph 可以。→ 模型约定不用 `rdf:reifies`；关系表只交给 pyoxigraph 读。
5. **pyshacl 慢**：ArchiMate 关系矩阵 shapes 有 8 万条三元组、2.4 万个 `sh:class`。1000 个元素时全量校验 74 秒，3000 个元素约 2 分钟（core shapes 只要 1.4 秒）。→ `la.py check` 改为直接查上游发布的 `relationship-tables`（同一张矩阵的查表形式）：3000 个元素 32 ms。**差分测试** `scripts/diff_test.py`：4 个随机种子共 1400 条随机关系（覆盖 9 种关系 × 39 种元素类型），SHACL 与 check **0 处分歧**（1155 条非法 / 245 条合法）。按评审意见扩大覆盖后（加入 Association、Specialization，以及 15% 的源元素带两个类型）又跑了 3 个种子共 1200 条：仍是 0 处分歧，且每一行 Violation 都被解析到（脚本里有断言，解析不到就判失败）。没覆盖到的：Junction、指向关系的关系、Grouping。
6. 限定关系和直连三元组不同步时，SHACL 抓不到（上游把这一项放在 SPARQL 问题集里）→ 已加进 `check`，两个方向都查。

## 4. AI 读写测试（清单 §6）

方法：用 workflow 起独立的 Claude 智能体，每个在一份隔离的 spike 副本里工作。只告诉它"先读 CLAUDE.md"，任务原样照搬清单。每个智能体后面跟一个默认持怀疑态度的复核者：复核者自己重跑 check/validate、diff 全部文件、用 SPARQL 算出标准答案，再打分。

**第一轮（3 个智能体）**：清单原题 1–3，外加一道更难的建模题（"供应商提交报价单触发审批；采购系统的报价管理服务支撑审批；审批要满足'单笔超过 10 万需二级审批'"）。

| | a | b | c |
|---|---|---|---|
| 采购经理建模（BusinessRole + Assignment，两遍写法） | ✅ | ✅ | ✅ |
| 第 4 题建模通过 check + validate | ✅ 第一遍就过 | ✅ 第一遍就过 | ✅ 第一遍就过 |
| 用错的类型 / 越界改文件 | 0 / 否 | 0 / 否 | 0 / 否 |
| 复核评级 | 有小问题的通过 | 有小问题的通过 | 通过 |

- 自己跑了校验，还有一个智能体主动造了个负例，验证校验器确实会拦。
- 语义上的小问题（全部合法，只是不够地道）：用 BusinessProcess 而不是 BusinessEvent 表示"提交"；"组件 realizes 服务"是派生出来的捷径；原有的"供应商 → 报价审批"分派和新业务语义冲突（智能体发现了，但按"只改必须改的"没删）。
- 中文解释有 1–2 处轻微的过度解读（把泛化的 Access 说成"读写"；把 Triggering 说成"完成后触发"）。
- **这一轮的设计缺陷**：因为预置了 `queries/02` 影响分析查询，三个智能体都直接用了它，没有自己写 SPARQL。

**第二轮（2 个智能体，删掉预置的影响查询，模型换成第一轮 a 的结果）**：报价单的影响面；采购系统下线影响哪些流程和角色；处理一条视点 Warning。
- 两个都**自己写了 SPARQL**（`( ^am:accesses | ^am:assignedTo | am:triggers … )+` 这类属性路径、`am:realizes/am:serves/am:triggers*` 链）。
- 采购系统下线：2/2 和标准答案完全一致。报价单影响面：一个 7/7 全对；另一个 6/7，漏掉了 3 跳外的采购系统，但它自己点出"按我的追溯路径追不到采购系统"。
- Warning：两个都把需求移出视图（保留元素和关系），改动只有两行，并说明了另一种做法（新建一张需求实现视点的视图）。
- 复核评级：一个通过，一个有小问题的通过。

**AI 用起来的摩擦（已修 / 待第二步处理）**：本体文件内部用默认前缀，grep `am:X` 搜不到（已写进 CLAUDE.md）；`query` 没预置 `amvp:` 前缀（已修）；视点误报 Warning（已修，见 §3 第 3b 条）；"影响分析沿哪些关系、往哪个方向追"没有约定，导致答案不一致 → **第二步需要把影响分析规则定义成元模型的一部分**（上游 la-kg 的 `impact-of-change` 模板也只是一种口径）。

## 4b. 异构评审（清单外，按规则对关键结论做跨模型挑战）

- 通道：Codex CLI **未登录**，不可用（登录需要交互操作，我没有代登）；改用 cursor-agent → **GPT-5.3 Codex High**，只读、不加 `--force`。挑战 5 条核心主张；评审原文见 `reviews-gpt-5.3-codex.txt`。
- 结果：C4（MINUS 改写等价）、C5（许可证）**CONFIRMED**；C1、C2、C3 **REFUTED**，每条都给了具体反例。我把这些反例逐条写成可执行探针跑过，**全部属实**：

| 反驳 | 反例 | 处置 | 现状 |
|---|---|---|---|
| C1 "关推理严格更好"过强 | 只用 `arch:partOfModel` 的元素拼错类型 → 漏报 | 闭世界规则同时覆盖 inModel/partOfModel | 负例 ✅ |
| C2 check 与 SHACL 等价 | 源元素同时是 Artifact + ApplicationComponent → SHACL 报错，check 放行 | check 改为"源元素每个类型都必须允许"（与 SHACL 语义一致） | 负例 ✅ + 差分 1200 条 ✅ |
| C3 闭世界无误报 | 模型里声明的子类 `:CloudServer` 被误判为未知类型 | 允许子类链回到已声明类 | 负例 ✅ |
| 补充 | DirectedAssociation 不在同步映射里；只查了单向同步；差分覆盖窄；正则可能漏解析 | 全部修正 / 补断言 | ✅ |

- 辩论记录：4 条补充意见全部接受；对 C1 只接受"严格更好"这个措辞过强，`inference=none` 的选择本身保留——悬空引用被掩盖的风险更大，子属性问题由规则显式覆盖。

## 5. 对元模型设计（第二步）的启示

1. **直接采用 Linked.Archi 的三原语**：`arch:Element` / `arch:QualifiedRelationship`（`arch:source`/`arch:target`）/ `arch:View`（元素用 `arch:inView` 指向视图，**不是**视图列出成员）。记法 = 独立的 onto + shapes + relationship-tables，叠加在 core 之上——和总纲 §6"记法规则放上层"完全一致。
2. **关系存两遍**是上游的约定，代价是两份可能不同步 → AISEP 需要一个"只写限定关系、自动派生直连三元组"的写入层（或至少保留 `check` 的同步检查）。这一层也是 AI 写模型的唯一入口的天然位置。
3. **校验分两层**：快速层（查表，毫秒级，每次保存都跑）+ 全量 SHACL（CI / 评审关口跑）。"合法性"本质上是数据（关系表），不是代码。
4. **AISEP 闭世界规则是必需品**，不是可选项：开放世界本体 + AI 写入 = 拼写错误静默通过。
5. 版本漂移很快：core 本体在 apm fixture 里是 0.5.0（11-08），发布站点上已经是 0.6.0；而且全部标着 `bibo:status "draft"`。→ 必须按 SHA 锁定，升级要当成显式动作。
6. **影响分析口径要进元模型**：沿哪些关系、往哪个方向、追几跳，现在由每个 AI 自己定，同一个问题得出 6 个或 7 个元素两种答案。应该像关系表一样，把"依赖语义"定义成数据（例如 serving/realization 反向传播、access 双向传播），所有人和 AI 共用一份。
7. 跨记法追溯（BPMN→ArchiMate→DDD→UML→测试）这次没有验证；上游有 `crossmappings`（bpmn、backstage），第二步需要专门验证。

## 6. 下一步建议

- 勾掉总纲 §8 第 1 条（meta-core 是 Apache-2.0；但现行本体是 CC-BY-4.0，注意 SA 例外）
- 第二步写元模型规范时，以 `vendor/` 里锁定的 core 0.6.0 + **archimate4 4.0** 为基线（按草案1 §6a）；3.2 只保留用来对照
- 正式仓库里沿用：`vendor/` 锁定 + `la.py check/validate` + 闭世界 shapes + 本次的负例 / 差分测试

## 附：怎么复现
```bash
cd ~/Desktop/AISEP/spike-linked-archi
.venv/bin/python scripts/la.py check && .venv/bin/python scripts/la.py validate
.venv/bin/python scripts/negative_tests.py          # 12 个负例
.venv/bin/python scripts/diff_test.py 400 2          # SHACL vs check 差分
.venv/bin/python scripts/scale_test.py 100 1000      # 性能
LA_NOTATION=4 .venv/bin/python scripts/la.py check   # 以上命令前加 LA_NOTATION=4 即切到 ArchiMate 4.0（model-am4/）
```

目录说明：`upstream/` 是拉下来的 11 个 GitHub 仓库（只作参考）；`vendor/` 是锁定的本体；`reviews-gpt-5.3-codex.txt` 是异构评审原文。spike 目录整体可以删，不进正式仓库。
