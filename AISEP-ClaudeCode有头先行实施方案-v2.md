# AISEP × Claude Code — 有头先行实施方案 v2(STEP 0 修订版)

| | |
|---|---|
| **日期** | 2026-06-11 |
| **状态** | 提案;待执行(**取代 2026-06-10 v1**:`AISEP-ClaudeCode有头先行实施方案.md`) |
| **前置** | `AISEP-ClaudeCode架构决策文档.md`(ADR-001~010)+ v1 + 本次异构验证(§9 留痕) |
| **修订方法** | 10-agent grounding(ADR 消化/repo 实测盘点/能力调研)→ 三视角独立建议(极简/强制/能力)→ 合成草案 → **cursor-agent 真异构评审(5 接受/18 挑战)+ 2 路对抗证伪(均驳倒草案最强论断)** → 裁决落本稿 |
| **一句话** | 功能版组件(agents/skills/hooks/CLAUDE.md/复用核)全部落地、**人当 supervisor** 不变;v2 新增三项裁决:① **就地实施,不新开 repo**;② 动工前**只冻结契约(10 条)不冻细节**;③ Fable 5 的正确兑现方式主要是"**少建设**" + **receipt 留痕**,三条底线(进程外强制/异构 fail-closed/退出码语义)不因新模型而变。 |

---

## 0. 相对 v1 的关键变化(速览)

| # | v1 | v2 | 依据 |
|---|---|---|---|
| 1 | 未显式讨论实施载体 | **显式裁决:就地实施现 repo**;"新开 repo / clone 整库"被对抗证伪以可执行探针驳倒 | §1、§9 |
| 2 | 直接进 M1~M4 | 动工前先落 **契约冻结清单 10 条**(`specs/contracts/`),其余显式推迟 | §2 |
| 3 | M1 `gate-judge` 接 `AgentAsJudge` | M1 CLI **永不调模型**(纯静态三态);LLM 裁决只在有头会话(订阅)或 cursor/codex shell-out(独立计费)发生 | §4-M1 |
| 4 | 无 receipt 概念 | 新增 **gate receipt 链** —— 对抗 Fable 5 长程自主"静默跳阶段"的唯一机器证据 | §4-M1 |
| 5 | M3 含 PreToolUse 正则 hook | **砍掉**(用户已实测定性:纯 hook 防护=剧场);保留 `permissions.deny` 并追加 3 条,诚实标注"会话层摩擦,非强制" | §4-M3 |
| 6 | pre-commit 装 `.git/hooks/` | 改 **repo 内 `.githooks/` + `core.hooksPath`**(否则他人 clone 后钩子静默缺席) | §4-M4 |
| 7 | driver 4 个触发条件 | **四级升级阶梯** + 触发条件改写;"≥3 特性并行"**降级为软信号**(不删除) | §5-ADR-003 |
| 8 | 成本测量"得出一个实数" | **双口径台账 schema**(实际应答模型 + effort 档 + 计费制度标签 + 订阅/假想 API 双口径) | §4-M4 |
| 9 | 退出码 0/1/2 | 增 **3 = 基础设施错误**(core import 失败也必须非 0,fail-closed 用会失败的测试钉死) | §2-契约3 |
| 10 | M2 一次性交付 7 agents + 5 skills | **按需物化**:首批只建 3 个资产跑最小闭环;7/5 是上限不是验收指标;但**双宿主规范先冻结** | §4-M2 |

---

## 1. 裁决一:就地实施,不新开 repo

### 1.1 结论与依据

**结论:在现 repo(AISEP6-6)就地清理后实施;不 clone、不 git init 新仓。** 需要"新项目门面"时,把清理后的 repo 直接 push 到新建 GitHub 远端 + branch protection——这就是"新项目",且全程只有一个本地工作副本。

对抗证伪(本机可执行探针)驳倒"新开 repo"的事实依据:

- **clone 的每条收益都是现 repo 已具备的性质**:保历史、`make test` 33 绿、`make arch` 2 契约 kept、STEP 0 全部路径逐字有效——不迁移即满足;
- **"改 `.gitignore` 牵连历史"是伪前提**:实测 `git ls-files` 中零个 tracked `.claude/` 文件,去掉忽略行就是一行编辑,不碰历史;
- **新 repo 三类真实成本**:① 本 repo **无 origin 远端**,"旧 repo 冻结"只能靠 README 声明(按 §2 契约 1 的权威分层属最弱建议层),挡不住多窗作业误写进旧 repo;② `~/.claude/projects/` 的项目记忆与 session 按**绝对路径**键控,换路径全部孤儿化(含本决策链上下文);③ `.cursor/` 配置、被 gitignore 的调研文件夹(约 7.6MB,方法论源)等非 git 资产不随 clone 走;
- 按 Simplicity 自检:clone 不增加任何就地得不到的能力,只新增"两个活 repo"漂移风险。

**唯一真该新开 repo 的场景**(记录备查):将来把 harness 抽成给*其他*企业项目用的模板/发行物。那是 STEP 0 之后的"抽取发布",不是现在的"迁移"。届时对四个抽取方案的否决理由依然成立:subtree(给冻结源付 git 仪式税)、submodule(无 origin 远端,URL 只能本机绝对路径,CI 必断)、跨 repo 路径依赖(harness 脱离 `.importlinter` 契约)、直拷 git init(丢 C1~C6 硬化审计链)。

### 1.2 D0 前置三件套(不做完不许动 M1)

1. **commit 工作区 3 个修改**:`src/aiforge/governance/review.py`、`src/aiforge/orchestration/__init__.py`(PEP 562 修复,是 `review_after_session` 的运行期依赖)、`src/aiforge/runtime/base.py`;
2. `chore/health-improvements` **合回 main**;
3. 打 tag **`archive/pre-harness`**(就地基线,代替"旧 repo 冻结"语义)。

### 1.3 首批 commit(顺序固定)

| # | 动作 | 说明 |
|---|---|---|
| ① | `.gitignore` 去掉 `.claude/` 整体忽略 | 改为只忽略 `.claude/settings.local.json`;M2/M3 交付物(agents/skills/settings.json)必须入库 |
| ② | **0 号地雷双层排雷** | 项目级**和用户级** settings 双查 `bypassPermissions`——权限规则跨层**叠加合并**而非覆盖,只查项目级是假排雷 |
| ③ | `judge.py:81` 翻转为默认不可信 | 显式 `trust_llm=True` 才信 LLM 自报,带回归测试 |
| ④ | **ADR-013**:记录"就地清理 + tag 基线" | 含基线 commit hash、验收命令(`make test` + `make arch`)、杂物归档去向 |
| ⑤ | 根目录 14 个未追踪杂物归档 | 一条 `mv` 移到 `../AISEP6-6-archive/`(untracked 文件无需 git mv);调研文件夹已被 gitignore,原地不动 |

休眠目录(dashboard/、openhands seam 等)**保留不删**——删除才是 churn;ADR 记一句"休眠"即可。

---

## 2. 裁决二:冻结契约,不冻细节

**反对"细节全定完再实施"的三个硬理由**:① 决策对象在移动(Agent SDK 0.x、编排类特性 GA/preview 措辞冲突),冻完即过期;② 计费节点倒计时(6/15 无头分池,见 §5-ADR-009),瀑布式定细节烧掉低成本基准测量窗口;③ M2/M4 的验收本身就是反馈回路("玩具需求走闭环""跑出成本实数"),这些细节只有跑起来才定得对。

**冻结判定标准**(经异构评审扩充):跨进程/跨人依赖、持久化格式、安全边界、审计证据、权限模型、不可逆迁移、成本口径——**改了会让数据不可比或追责断链的,冻结;跑两轮就能廉价改的,推迟。**

### 2.1 冻结清单(契约级,D1~D2 落字到 `specs/contracts/`,整包过一次 cursor-agent 异构评审后生效)

1. **权威层级声明(单独 ADR-014)**:唯一强制层 = GitHub CI + branch protection + CODEOWNERS;pre-commit = 快速反馈(可 `--no-verify` 旁路,明文承认);hooks/`permissions.deny` = 会话内护栏;CLAUDE.md = 建议层;**会话内的一切编排(含 Workflow/Agent 工具/长程会话)永远不是强制**——任何 ADR 不得以会话内构件作为权威/强制层论据。
2. **迁移机制与前置**(即 §1.2/§1.3,作为契约固化)。
3. **gate 退出码契约**:`0=approved / 1=rejected / 2=needs_human / 3=基础设施错误`(core import 失败、配置缺失也必须非 0);fail-closed 语义用**会失败的可执行测试**钉死,落 `specs/contracts/`。
4. **计费边界**:M1 CLI 永不调模型(纯确定性检查,代码内禁止出现 `claude -p`);LLM 裁决只发生在有头会话(订阅)或 cursor/codex shell-out(独立计费)。
5. **异构 fail-closed**:judge 缺真异构(cursor/codex)→ exit 2 转人审,绝不静默退回 Claude-审-Claude,**Fable 5 不豁免**(同模型盲区是系统性的,用户 3 次实测被 cursor 抓洞);评审产物**记录评审者模型身份**入 `specs/<id>/`;若评审工具不自报模型身份,留痕注明"身份未自报+请求参数"。
6. **gate receipt 回执**:每个 gate 写 `specs/<id>/gates/<gate>.json`,字段至少含:gate 名、输入 artifact 路径+hash、exit code、git HEAD、时间戳、(涉及人审时)执行者;`gate-commit` 校验上游 receipt 齐全且 hash 一致,缺失/过期即 exit 1。receipt 由 CLI 真实命令产生,模型贴回会话的只是引用——防编造。
7. **`--ack-human` 双层语义**:本地 ack = 仅审计(isatty 检查 + 记录执行者),只解锁本地 pre-commit;权威放行 = GitHub **人类账号** PR approval;CI 永远重跑 gate,不消费本地 ack。
8. **`specs/<id>/` 目录契约 + agent 双宿主规范**:spec.md 过 gate-spec 后冻结(改动需人审);agents 设计为同时可被交互会话与编排工具复用——file-in/file-out、每角色 JSON 输出 schema、**定序逻辑不进 prompt**。规范冻结,提示词文案不冻。
9. **数据与安全契约**(异构评审补充,写原则不写复杂实现):receipt/台账含 `schema_version` 字段 + 迁移策略;hash 规范化规则(对哪些字节计算、换行/编码处理);secret/PII redaction 原则(台账与 receipt 不得含 secret);CI token 最小权限;CODEOWNERS 责任边界;break-glass 紧急放行流程(怎么绕、谁批、如何留痕)。
10. **模型配置原则**(按异构评审从"冻结厂商默认值"弱化为"冻结原则"):所有 model/effort **显式配置**;被 API 拒绝的参数 fail-closed(不静默降级);成本/评审记录**实际应答模型**;具体厂商行为(如 Fable 5 仅 adaptive thinking、显式 disable 返回 400)写进 ADR **附验证命令与日期**,不当契约。

### 2.2 推迟清单(显式留给迭代,禁止顺手做)

- **Agent SDK driver 全部**(触发条件命中或 SDK 1.0 时重评,见 §5-ADR-003);
- 会话内 Workflow 编排范围(观察项,不承重,不进验收);
- 7 agents / 5 skills 的**提示词文案**——随试运行按需物化,首批只建 `analyst` + `sdlc-requirements` + `sdlc-gate`;
- per-agent model/effort 精调矩阵(等 M4 实数,顺序不能反);
- OTel collector(最低配 `/cost` 落账够用,ADR-007 保留为升级路标);
- plugin 打包(>1 repo 消费再说);看板迁移(调研文件夹 console.py 资产,开工前不裁决);
- managed-settings / MDM / HMAC sink(强制版事项,ADR-008 原样保留);
- 6/15 后无头 credit 细节官方核验(**预算承诺前必须**,但不挡 M1~M3)。

---

## 3. 总体形态(v2)

```
人(supervisor:定序、审批、resume)
 └─ Claude Code 交互会话(引擎,Fable 5)
     ├─ CLAUDE.md ← @import constitution.md(宪法,建议层;增"长程自主约束"段)
     ├─ .claude/agents/*.md     角色子代理(按需物化,上限 7;双宿主规范)
     ├─ .claude/skills/         阶段 skills(按需物化,上限 5)
     ├─ .claude/settings.json   permissions.deny + 显式 model/effort(会话内护栏,非强制)
     └─ Bash → python -m aiforge ...(薄 CLI,零模型调用,产 receipt)
进程外(真强制,AI/人都绕不过):
 ├─ .githooks/pre-commit(core.hooksPath)→ make gate-commit   [快速反馈,可旁路,明文承认]
 └─ GitHub CI + branch protection + CODEOWNERS → make gate-feature + receipt 链校验   [唯一强制层]
状态存储:specs/<id>/{spec.md(冻结), plan.md, tasks.md, gates/*.json(receipt 链)}
```

---

## 4. 交付物清单(v2 修订)

### M1 · 薄 CLI(唯一要写的代码;**零模型调用**)

| 子命令 | 输入 | 复用 | 输出/退出码 |
|---|---|---|---|
| `aiforge gate-spec <file>` | spec.md 路径 | `SpecGate`(P1) | 0/1/3 + receipt |
| `aiforge gate-trace <dir>` | specs/<id>/ + git 代码引用 | `TraceabilityGate`(P2)语义 | 0/1/3 + receipt |
| `aiforge gate-judge [--staged]` | `git diff` 文本 | **仅 `StaticRiskScanner` 静态三态**(不接 AgentAsJudge) | 0 / 1 / 2(needs_human,打印人审清单)/ 3 + receipt |
| `aiforge review-3f [--staged]` | `git diff --numstat` | `review_after_session`(P7) | 打印必读清单 |
| `aiforge gate-commit` | 聚合:lint + gate-judge + review-3f + **上游 receipt 链校验** | `PreCommitGate` 语义(fails-closed) | 0/1/2/3 |

- 诚实边界:`needs_human` 路径上,`--ack-human` 按契约 7 双层语义执行;
- 验收:`tests/test_harness.py` 覆盖每个子命令 + **每条 fail-closed 断言用会失败的测试钉死**;`make test`、`make arch` 全绿;
- 预计 250~400 行 + 测试(v1 的 200~300 行 + receipt 增量;工作量为估计值,非实测)。

### M2 · CLAUDE.md + 角色子代理 + 阶段 skills(按需物化)

- **首批(最小闭环)**:`analyst.md` + `sdlc-requirements` + `sdlc-gate`,对一个玩具需求走通 requirements → gate-spec;
- 其余角色(architect/developer/reviewer/tester/verifier/judge)与 skills(architecture/decompose/integrate)**随试运行按需建**;v1 的职责/工具白名单表原样有效,作为物化时的规格;
- **双宿主规范先冻结**(契约 8):否则编排复用时 7 个文件全返工;
- CLAUDE.md 增"**长程自主约束**"段:任何特性按 requirements→gate→architecture→gate→decompose→实现→integrate 走;每阶段产物落 `specs/<id>/`;阶段切换前必须跑对应 `aiforge gate-*`(receipt 由真实命令产生)并把结果贴回会话;**并逐条标注对应的机器强制点**(哪条由 CI 兜底、哪条只是建议);
- `judge.md` 异构评审语义不变:Bash 调 cursor-agent/codex;缺真异构 → 明示"异构缺席,转人审"。

### M3 · 权限白名单(会话内护栏,宽松版)

- `permissions.deny`(v1 基础上追加 3 条):`Bash(git push --force*)`、`Bash(rm -rf /*)`、`Read/Write(.env*)`、`Write(constitution.md)` + **`Bash(git commit --no-verify*)`、`Bash(git config core.hooksPath*)`、`Bash(* --ack-human*)`**(会话内不许自我放行);
- **砍掉 v1 的 PreToolUse 正则 hook**(实测定性:剧场);Stop hook 提示跑 `review-3f` 保留(提示,不拦);
- settings.json **显式锁 model + effort**(契约 10 原则);
- 诚实标注:以上全部是"会话层摩擦",防呆不防恶;真强制在 M4。功能版不设防"AI 改 settings 本身"(对齐 ADR-002)。

### M4 · 进程外强制层 + 成本测量

1. **pre-commit**:repo 内 `.githooks/pre-commit` + `git config core.hooksPath .githooks`(setup 脚本一行),跑 `gate-commit`;明文承认可 `--no-verify` 旁路——它是反馈层,不是强制层;
2. **CI(唯一强制层)**:`.github/workflows/gates.yml` 跑 `make test` + `make arch` + `gate-spec`(PR 涉及的 specs)+ `gate-judge`(PR diff)+ **receipt 链校验**;branch protection + CODEOWNERS(保护 `.github/`、`specs/contracts/`、constitution.md);
3. **验收 = 三个攻击探针 PR 全被拦**:① 无 spec 的代码提交 → CI 红;② 同一 PR 把 gates.yml 改空 → CODEOWNERS/branch protection 拦;③ 改已冻结的 spec.md → 拦;
4. **成本测量(双口径台账)**:每条记录含【实际应答模型 + effort 档 + 计费制度标签 + 订阅/假想 API 双口径】(契约 9 schema);按模型分桶;**计费节点(6/15)前后各测一轮**,口径标签保证可比;最低配 = 每次管线跑完记 `/cost` 到 `eval/cost-log.md`,OTel 推迟。

---

## 5. Fable 5 / 新能力对既有 ADR 的连带修订

| ADR | 修订 |
|---|---|
| **ADR-003**(编排主干) | 升级阶梯改**四级**:人肉定序 → repo 脚本/CI → 会话内 Workflow 编排 → Agent SDK driver(进程外)。触发条件改写:**硬触发** = 需要进程外强制 / 无人值守(定时、失败重试与幂等、队列)/ 跨会话权威状态 / 多操作者纪律 / secret 隔离 / 成本预算熔断 / 可重放执行,任一命中或 **Agent SDK 1.0 发布**即重评;**软信号** = decompose 经常拆出 ≥3 特性并行(调度复杂度预警,不单独触发)。**driver 是有条件推迟,不是取消**:会话内编排是"被约束方自己执行的约束"(定义落在模型可写路径),崩溃恢复是对转录的 best-effort 再解读而非幂等重放,无人值守按定义在会话外——范畴差异,功能补不上。推迟的经济前提(有头≈零边际成本)在计费节点后**须复核**。 |
| **ADR-009**(成本) | 补 Fable 5 价签:**API $10/$50 每 MTok = Opus 4.8($5/$25)的 2 倍**(官方参考,2026-05 口径)→ 无头额度燃烧翻倍 → 有头先行的经济理由加码。6/15 无头/Agent SDK 计费分池为既有结论;**第三方流传的其他日期/额度细节($20/$100/$200、订阅窗口变化)未经官方核验,不入硬阈值**,预算承诺前必须官方二次确认。新增控本手段备查:effort 档(low~max)、task budgets(beta)、Batch 五折、cache 读 ~0.1x。 |
| **ADR-010**(模型策略) | 阶梯改 **Fable 5 > Opus 4.8(半价)> Haiku**;同模型内**先调 effort 再降模型**。但 judge/architect 等角色用哪一档**靠 M4 任务集实测定**,不按"越强越好"线性排——更强模型也可能更会合理化错误。API 硬注意(附验证日期 2026-06):Fable 5 仅 adaptive thinking,显式 `disabled` 返回 400——任何配置不得发送关闭 thinking 的参数;API surface 同 Opus 4.7/4.8,`.claude/agents/*.md` 的 model 字段写法不变。 |
| **ADR-011**(本方案) | 有头先行 + **就地实施**;状态存储 = `specs/<id>/` 文件契约 + **receipt 链**;driver 按 ADR-003 v2 阶梯升级。 |
| **ADR-012**(占位) | **随推迟保留,不得随"取消"废除**:driver 不依赖 `-p` 自动发现(防 `--bare` 默认翻转),所有加载项显式传 + 钉死 CLI/SDK 版本。会话内编排骑在自动更新的客户端上、无法钉版本——这正是 ADR-012 防的事,也是它不能当权威层的理由之一。 |
| **ADR-013**(新) | 就地清理 + tag 基线记录(§1.3-④)。 |
| **ADR-014**(新) | 权威层级声明(契约 1 升格为 ADR)。 |

**不因 Fable 5 而变的底线**:① 会话内的一切不算强制(编排工具的 token budget 是成本护栏,不是权限护栏);② 异构评审 fail-closed——模型越强,"Claude 审 Claude 就够了"的滑坡诱惑越大,而同模型盲区是系统性的;③ fails-closed 退出码语义;④ 0 号地雷禁令。

**Fable 5 的正确兑现方式主要是"少建设"**:长程自主 + 1M 上下文 → 支持**暂缓**复杂 driver(推不出"需求消失")、不拆 query;文件型记忆变强 → `specs/` 文件协议使用成本下降(但协议本身仍需 schema/原子写入/冲突处理,不是免费红利);新增的唯一硬义务 = receipt 链 + 台账记实际模型。

---

## 6. 实施顺序与验收

| 阶段 | 内容 | 验收 |
|---|---|---|
| **D0~D1** | §1.2 前置三件套 → §1.3 首批 commit ①~⑤ | `make test`(33 绿)+ `make arch`(2 契约)双绿;`git tag` 可见 `archive/pre-harness` |
| **D1~D2** | 冻结清单 10 条落字 `specs/contracts/` + ADR-011/012/013/014 | **整包过一次 cursor-agent 异构评审**(留痕含评审者身份注记) |
| **第 1 周** | M1 薄 CLI(5 子命令 + receipt + 退出码 0/1/2/3)+ tests;**push 新建 GitHub 远端 + branch protection** | 5 子命令独立可跑;fail-closed 断言测试全绿;远端 protection 生效 |
| **第 1~2 周** | M2 最小闭环(3 资产,玩具需求走 requirements→gate-spec);M3 deny 清单 + settings 锁 model/effort | 闭环走通;实测 deny 各条真被拦 |
| **6/15 前后** | 自举试运行第一轮(人工定序跑完整管线);M4 最低配台账记 Fable 5 基准 | 七阶段产物齐 + receipt 链完整 + 成本入账(制度标签=节点前) |
| **节点后** | 同口径复测一轮;M4 CI + 三攻击探针验收 | 三探针 PR 全被拦;两轮台账可比 |
| **收尾** | 凭两轮数据重裁 ADR-003(四级阶梯走到哪级)与 ADR-010(角色路由) | 裁决写回 ADR,留痕 |

---

## 7. 风险与边界(诚实清单)

- **门禁覆盖缺口**(v1 保留):有头模式拦不住"整个阶段被跳过"的过程纪律,只能在 commit/PR 边界兜底;v2 的 receipt 链把"跳了"变成**可机检的证据缺失**,但仍不能阻止人/模型不跑——此为接受的残余风险(ADR-003 软信号的监测对象)。
- **judge 离线即转人审**(v1 保留):验证期每特性至少一次人审,这是 fail-closed 的代价,不是 bug。
- **pre-commit 可旁路**(v2 明文化):`--no-verify`、改 hooksPath 在本地都可行;M3 deny 只挡会话内,真强制只有 CI。
- **未经核验的事实,不作为依据**:6/15 后无头 credit 细节(额度/滚存/合池)系第三方解读;调研中出现的"分类器静默回落"说法可疑且不可观测,**不进任何设计**;编排类特性 GA/preview 官方措辞冲突,接入前查文档现状页。
- **工作量数字均为估计**("250~400 行""receipt 增量极小"),非实测。
- **成本数据偏差**(v1 保留):有头会话含人的来回,token 高于纯无头管线;估算 driver 成本按上界使用。
- **`.claude/` 资产与 AGENTS.md 双轨**(v1 保留):@import 单一事实源,新约定只写 AGENTS.md/constitution.md。

---

## 8. 对 v1 的处置

v1(`AISEP-ClaudeCode有头先行实施方案.md`)保留为历史记录,文件头标注"已被 v2 取代";其 §0 决策依据、M1 子命令表、M2 角色/skills 规格表、§4 连带修订条目在 v2 中分别被继承或修订,未被 v2 显式推翻的内容(如计费依据①②、产物落盘约定)继续有效。

---

## 9. 验证留痕(本修订的异构对抗记录)

| 项 | 结果 |
|---|---|
| **cursor-agent 异构评审** | 已实际执行(`cursor-agent -p --mode ask`,未指定 --model 即其默认模型;其自述未获联网核验权限,故对事实类只能判"证据不足"而非核查;**输出未自报具体模型身份**——按契约 5 注记)。verdict:方向成立但需修订后动工;5 点接受 / 18 点挑战,高严重度挑战已全部吸收(§1 措辞收敛、§2 判定标准扩充与契约 9/10、§5 ADR-003 软信号与四级阶梯、未核验事实降级) |
| **对抗证伪 ①** | "会话内编排已覆盖 driver 缺口,可取消 driver" → **驳倒**;弱化版(有条件推迟 + 阶梯 + ADR-012 保留 + 计费节点复核)采纳入 §5 |
| **对抗证伪 ②** | "新开 repo(clone 整库 + 旧 repo 冻结)优于就地" → **驳倒**(本机可执行探针);就地版采纳入 §1,clone 方案的前置/首批 commit 等正确成分原样移植 |
| **材料** | 草案 `/tmp/wf_draft.md`;评审与证伪 `/tmp/wf_verify.json`;workflow 全量输出 task `wfxjy6dq4`(2026-06-10/11 会话) |
| **未尽事项** | 本 v2 文档本身的冻结清单落字稿(D1~D2 产物)仍须按计划再过一次 cursor-agent 整包评审——本表记录的是方案级评审,不替代契约级评审 |
