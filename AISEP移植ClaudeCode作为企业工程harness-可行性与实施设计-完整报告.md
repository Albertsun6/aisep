# aiforge 工程纪律 harness 落在 Claude Code 之上：可行性与实施设计报告

## 1. 结论先行 (Executive Verdict)

**可行，但不是"在 CC 里写几个 hook 就完事"——可行的是一个明确的混合形态:把 Claude Code 的模型驱动 loop 当 per-phase 执行引擎,外面套一层薄的进程外权威层(Agent SDK 外层 supervisor + git pre-commit/CI + 进程外 HMAC 审计/审批 sink + cursor/codex 异构 shell-out)。** 单凭 CC 自带扩展点(CLAUDE.md / hook / settings deny / subagent / skill / MCP),在一个**同时持有 Edit + Bash 的模型驱动 agent** 面前,只有"粗粒度最小权限(bare deny 整工具移除)"和"OS 级 Bash sandbox"两类是真正 fail-closed 的;凡是依赖"读取 agent 可写文件里的状态/证据""按命令字符串模式匹配 Bash""靠 CLAUDE.md 约束顺序""用 CC subagent 当评审 panel"的,在对抗探针下**全部 fail-open = 原则⑤ 定义的 theater**。这一点不是推断——用户自己的生产 hook(`~/.claude/hooks/git-guardrails.sh`)被 8 条间接 Bash 旁路实测全部 ALLOW、500 文件写风暴绕过 P5、harness 状态计数器被一次 model 写从 9 重置为 0,均已 CONFIRMED。**所以"最快"的纯 (a) 路线,在依赖"正则匹配 Bash / agent 可写状态 / CLAUDE.md 约束顺序 / CC subagent 自评"的那些面上是 fail-open,直接违反用户硬规则。** 但需精确(异构复审 §9 修正):受管锁定的纯 CC 子集(OS sandbox + bare-deny 整工具移除 + 受管 OTel 外送 + server 端 CI)在**写面 / 粗权限 / 事件级审计 / 原子 blast-radius** 上**是 fail-closed 的**;真正纯 CC 覆盖不了、必须外部脚手架的是**确定性 supervisor / 异构验证 / actor-bound 审批 / 完整内容级审计**——这四项才是仍需 thin-outer-supervisor 混合的真理由(见 §4)。

关键前提还必须如实标注:用户**当前真实部署**就是最坏配置——`settings.json` 里 `defaultMode=bypassPermissions`、`allow=['Bash(*)']`、`deny=[]` 空、无 MDM Managed Settings。也就是说今天这台机器上,连"粗粒度 deny"这层绿灯都没点亮。下表的"绿/黄"是**在正确锁定配置下能达到**的状态,不是开箱即得。

### 九大宪法原则红绿灯(正确锁定配置下可达上限)

| 原则 | 状态 | 一句话判定 |
|---|---|---|
| **P1** spec 先于 code | 🟡 黄 | PreToolUse hook 能拦 Edit/Write,但 Bash heredoc/`python -c`/改后缀可绕;且 `_spec_has_acceptance` 可被 `"given when then "+"x"*30` 语义糊弄。需外层 supervisor 决定相位推进 + 内容血缘校验。 |
| **P2** 可追溯 spec→…→test | 🟡 黄 | TraceabilityGate 只查"某 KIND 的上游 artifact 存在",不查血缘;refs 在 CC 下由 **model 自己填**,可给孤儿代码挂 `refs=['spec']` 自证。需 refs 由外层 loop 从真实相位产物写入。 |
| **P3** 质量门禁不可绕过 | 🟡 黄 | 门禁**检查逻辑**可移植,但"非可绕过"靠的是输入由可信 supervisor 产出。CC 下门禁要读 `tests_ok` 只能从 agent 可写的 workspace 文件读 → `echo '{"tests_ok":true}' > state.json` 自证绿;commit 边界又被 `$(git commit)` 子进程旁路。真 fail-closed 必须放进程外 SDK loop + 服务器端 git pre-commit/CI。 |
| **P4-perm** 最小权限 + HMAC 票据 | 🟡 黄 | 粗粒度(bare `deny:['Bash']` 整工具移除)是 🟢;但**按 actor 绑定 + HMAC 单次票据**做不到——CC 权限是 session 级非 role 级,且这正是 aiforge 自己 #1 gap:同进程 agent 读到 secret 就伪造票据,CC 下若 secret/SDK hook 代码在 workspace 更糟。需进程外 ApprovalAuthority。 |
| **P4-halt** 安全停机 | 🟡 黄 | hook 只能"拒下一个工具调用"→ model 换姿势重试 = 拒绝循环,**不是停机**。CC 文档明说 "Blocking Stop does NOT kill the agent mid-thought"、"no hard time-out to kill a rogue session"。真停机只能靠 SDK 外层 tear down query()/杀进程。 |
| **P5** 爆炸半径限制 | 🟡 黄 | 单条 `for i in $(seq 1 500)` Bash 写风暴对 per-Edit hook **完全不可见**(实测 500 文件落盘,counter 仍 0);Edit 路径非原子(1–10 已落盘才拦第 11)。真原子限制只能在 server 端 git pre-commit `--numstat` 看全量 diff + 一次性丢弃 worktree。 |
| **P6** 非功能需求一等公民 | 🟡 黄 | StaticRiskScanner 正则可移植成 PreToolUse deny(命中即拦,与 aiforge 同强度,本就 best-effort);"+20% 完整性"任一系统都证不出,CC 不改善也不恶化。 |
| **P7** 三文件审查 / 认知债 | 🟡 黄 | review_after_session 本就是**咨询性 checklist**(aiforge 自标 fail_closed:false);CC 用 Stop/PostToolUse hook 产出 checklist 是**功能全等**。真阻断靠 P4/P3 的 HITL,且 additionalContext 可能被 compaction 丢掉。 |
| **P8** 防篡改审计 | 🟡/🔴 黄红分层 | **(异构复审 §9 修正:原判"死红"是 overclaim)** ① **事件/决策级 → 黄**:CC **原生 OpenTelemetry** 经受管 env 强制开启,把 tool decision/permission/api 事件送到 model 写不到的外部 OTLP collector,是**原生、抗篡改**的外部证据层(不必先自研 sink);② **完整内容级+防篡改 → 仍红**:OTel 非 HMAC append-only ledger、默认不含完整 tool args/文件 diff、对 Bash 内 500 文件改同样盲、无尾截断 anchor;CC 本地 JSONL(PostToolUse 写)model 可删改、`--no-session-persistence` 可关 = 红。要 HMAC 链+外部 anchor+文件级 diff 仍须外部 sink(skeleton `test_unkeyed_full_rechain_forgery_passes` / `..._truncation_needs_external_anchor` 已证)。 |
| **P9** 可插拔 / 厂商中立 | 🔴 红 (但**故意的**) | 用户决策"用 CC 当引擎"= 在 engine 层主动放弃厂商中立(CC 工具/subagent/hook/skill/permission/MCP 是 Claude 专有,loop 只驱动 Claude)。这是**有意接受的 ADR 成本**,不是缺陷。可移植方法论内核(spec/gate 逻辑/审计 schema)保持 CC-free 即可部分保留。 |

> 红绿灯里**没有一个 P 是开箱绿**:CC 唯二真 fail-closed 的原语(bare-deny 整工具移除、OS Bash sandbox)只支撑"粗粒度最小权限"和"写约束",其余全部要外部脚手架才能从黄/红抬到可接受。这正是本报告 §5 的主线。

---

## 2. 框架反转的意义:为什么"avoid A"的旧结论被改写,以及它在哪儿仍然咬人

旧报告的三义裁决(A=整体替换引擎=避免 / B=借架构约定 / C=挂适配器)有一条**单一决策轴**:你的部署是否必须自托管/离线/多模型。当时把 A 判"避免",理由是 A 会同时摧毁离线、确定性 index 路由、厂商中立三条立身 DNA。

**用户的"给 Claude Code 加 harness"框架把决策轴主动钉在"Anthropic 云可接受"那一格**——而旧报告**自己在该格下的裁决就不是"避免"**。所以反转不是推翻旧逻辑,是**选定了旧逻辑早已给出条件结论的那个分支**。具体到三条 DNA:

- **离线/无 key 运行**(旧 A 反对理由之一):**被中和**。这是 constraint-conditional 论点,前提是"保留离线作立身 DNA"。用户以"最快、完全借助 CC 优势"主动接受 CC 当引擎 = 主动放弃离线。**不是被驳倒,是被决策放弃**。诚实边界:若仍要服务受监管/气隙客户,这条对那条产品线 100% 成立——SDK loop 根本跑不起来,那条线必须保留自研引擎。
- **厂商中立 / P9**:**对 engine 层成立,但已被有意接受**。"给 Claude Code 加 harness"语义上就是要 CC 专有的工具/subagent/hook/skill/permission/MCP,engine 层多模型中立确实没了。登记成 ADR 锁定成本即可。
- **确定性 index 路由 + 不可绕过 BLOCKED**(旧 A 称"最硬的冲突"):**没消失,被重新归置成新项目的核心工程问题**。CC 的 loop 下一步由模型每 turn 决定,而 graph.py:51-57 是纯 index 算术、graph.py:86-88 让 BLOCKED 不可被 approve 绕过(本次已逐行复核确认)。反转后这不再是"别用"的理由,而是**定义了 harness 的设计约束**:必须在 CC 的非确定 loop 之上、于确定的检查点重新施加门禁纪律——这只能由 Agent SDK 外层 supervisor 提供,CLAUDE.md 给不出(它"以 user message 投递,无严格遵从保证")。

**旧 caution 仍然咬人的三处**,反转一处都没消除:

1. **确定性 + 不可绕过 BLOCKED**:CC loop 天生与之相反,只能靠进程外 SDK loop 重建(§4 路线 b)。
2. **异构验证**(原则⑤ 硬要求):CC subagent **全是 Claude**(CC 文档明文),"subagent 评 subagent"= 共享训练盲区的循环自证,**不是**异构。真异构只能 shell out cursor-agent(GPT-5.5)/codex,与 skeleton `backends.py` 现有做法一致。
3. **纯 stdlib / 零依赖宪法 + 自包含确定性 resume**:harness 适配层(hooks/skills/MCP server/SDK 编排)天然依赖 CC,"core 纯 stdlib"边界要重画为"不依赖 CC 的可移植方法论内核";CC session=JSONL transcript 不能当权威状态,harness 必须自带蒸馏 PipelineState 当 SSOT(这正是 P8/P3 的落点)。

> 一句话:反转把旧报告里"避免 A 的六条论据"中两条(离线、engine 层中立)**有意放弃**,其余四条(确定性、供应链分层、自包含状态、审计/权限旁路)**全部升级为新项目必须正面解决的 crux 工程问题**——尤其第六条(base.py:65 apply() 那个唯一强制漏斗在 CC 下被 N 个 Read/Write/Edit/Bash 旁路)字面上就是用户的 crux 问题本身。

---

## 3. 目标架构:aiforge 层/不变量 → 具体 CC 机制映射

标注 **HARD**(可 fail-closed 强制) / **ADV**(咨询性,模型可绕) / **EXT**(必须借进程外脚手架才 HARD)。

| aiforge 层 / 不变量 | CC 机制 | 强度 | 说明 |
|---|---|---|---|
| 治理宪法叙事 | `CLAUDE.md` + `AGENTS.md` | **ADV** | "以 user message 投递,无严格遵从保证";只做叙事,绝不当门禁。 |
| P1 spec 先于 code | PreToolUse hook(Edit/Write 上跑移植的 `SpecGate._spec_has_acceptance`)→ deny | **HARD**(Edit/Write 面) / **EXT**(全面) | 仅对识别得到的文件工具 fail-closed;Bash heredoc/改后缀/语义糊弄漏。 |
| P2 可追溯 | PreToolUse hook(commit 类)跑 `TraceabilityGate`;refs 由**外层 loop**从真实相位产物写入 | **EXT** | CC 内 refs 由 model 填 = 自证;血缘校验必须在外层。 |
| P3 质量门禁链 | 门禁链移植成 **MCP 'gate' 工具 / 外层 Python**;权威 backstop = **server 端 git pre-commit + protected branch + required CI** | **EXT** | CC 内 hook 是 early-warning;`tests_ok` 等证据来源必须在 model 写不到的地方。 |
| P4-perm 粗粒度最小权限 | settings `deny:['Bash']`(bare → 整工具从上下文移除) + 默认只读模式 | **HARD** | CC 唯一真 fail-closed 的权限原语;bare-deny > 模式 deny(后者只当咨询)。 |
| P4-perm HMAC actor 票据 | 进程外 **ApprovalAuthority**(独立 MCP server / SDK 外层持 secret),敏感能力仅暴露为服务器端校验的 MCP 工具;每 role 一个独立 `query()` 带各自 `allowed_tools` | **EXT** | secret 永不落 agent 文件系统;每 role 独立 query() 才有 per-actor 隔离。 |
| P4-halt 安全停机 | SDK 外层 supervisor 检测 halt 信号 → **tear down query()/杀进程** | **EXT** | hook 的 continue:false **不杀** agent,只拒下一工具;真停机在外层。 |
| P5 爆炸半径 | (1) Bash sandbox `allowWrite` 限 worktree + `allowUnsandboxedCommands=false`;(2) **server 端 git pre-commit `--numstat` 看全量 diff**;(3) 一次性 worktree 当穷人回滚 | **EXT** | per-Edit hook 非原子且对 Bash 写风暴盲;原子检查只能在 commit 边界看全量。 |
| P6 非功能 | PreToolUse hook 跑 `StaticRiskScanner` 正则 → 命中 deny;Code-Review 插件 | **HARD**(匹配模式)/ **ADV**(完整性) | 与 aiforge 同强度;Code-Review 插件本身是异步咨询。 |
| P7 三文件审查 | Stop/PostToolUse hook 产 checklist(systemMessage/additionalContext) | **ADV**(=原意) | aiforge 本就咨询性,功能全等;阻断靠 P4/P3 HITL。 |
| P8 防篡改审计 | **第一层(原生·零自研)= 受管 OTel** 强制导出事件到外部 collector;**第二层(自研)=** PostToolUse hook → POST 到进程外 append-only sink,服务器端 HMAC 链 + 外部 anchor(head+count),链密钥在 agent 文件系统外 | **HARD**(事件级·受管 OTel)/ **EXT**(内容级+防篡改) | 受管 OTel 给事件级抗篡改证据;完整内容/diff/HMAC ledger 仍须自研外部 sink。 |
| P9 可插拔 | N/A——engine 层有意锁定 Claude;portable 内核保持 CC-free 隔离进 optional extra | **ADV** | 登记为 ADR 接受成本。 |
| X-judge Agent-as-Judge + 异构 | shell out `cursor-agent`(GPT-5.5)/`codex` 为独立订阅 CLI(复用 skeleton `backends.py`),经 MCP/Bash-工具接入,缺 vendor → `[independent gate not executable]` → HITL | **EXT** | CC subagent 全是 Claude = 循环自证;必须改 judge.py:81 默认不可信。 |
| X-isolation 沙箱隔离 | CC Bash OS sandbox(Seatbelt/bubblewrap)+ `failIfUnavailable=true` + `allowUnsandboxedCommands=false` + 自探针 hook | **HARD**(Bash 面) / **EXT**(全面) | 真内核边界,但只覆盖 Bash 工具;读面默认 allow-all,需 denyRead 收 + `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`。 |
| X-verifier 真验证+变异 | custom 工具在 sandbox 跑测试 + 移植变异检查;`tests_ok` 只由该工具写入外层 SSOT;CompletenessGate 当 PreToolUse deny | **EXT** | 验证结果 provenance 必须出 model 写程;否则即"自己写自己的绿"。 |
| X-supervisor 确定性路由 | **Agent SDK 外层 Python**:纯 index 推进 + 每相位一次 query() + 相位间跑门禁 + BLOCKED 不可 approve | **EXT** | CLAUDE.md/skill 给不出确定性;这是 crux,只能外层。 |

> **补充·异构复审 §9 新增的 CC 管理面能力**(原报告轻描淡写):① **受管 OTel** 当一等审计层(见 P8 修正);② **`disallowedTools`** 与受管 permission rules 是强约束(强于"模式 deny",别与 SDK `allowedTools` 的误区混淆);③ **SDK `defer` / permissionDecision** 可把工具请求挂起交外部 authority/UI,比 deny-loop 更适合做 HITL/审批;④ **`strictPluginOnlyCustomization` / 受管 MCP·plugin 源**进一步压"skills/hooks/MCP 被项目改写"的风险面(不止 `allowManagedHooksOnly`)。这些把若干"黄/红"在**正确受管配置下**抬高,但都不改变"确定性/异构/审批/完整审计仍需外部"的结论。

---

## 4. 编排两条路线

### 路线 (a) — 模型驱动 loop + CLAUDE.md/skills/hooks(字面"最快")
**怎么做**:单个 CC session;CLAUDE.md 载方法论叙事;skill 打包每个 SDLC 相位(spec/architecture/decompose);一组 PreToolUse/PostToolUse/Stop hook(经 Managed Settings + protected `.claude/` 锁不可变)强制能反应式强制的门禁;server 端 git pre-commit + protected-branch CI 当外部 backstop。
**给了什么**:真·最快;充分吃 CC 原生 loop/工具/规划/checkpoint/session resume,几乎不写编排代码。
**放弃了什么(且直接撞用户原则⑤)**:相位**顺序是咨询性**(模型自选下一步);**无确定性 index 路由、无不可绕过 BLOCKED**;安全停机只能 deny-and-loop **不能真停**;per-actor HMAC 审批和防篡改审计需要它本身不提供的进程外件;爆炸半径非原子且 Bash 可绕。**净结果**:fail-closed 不变量只在"反应式 hook 或外部 git/CI 能抓到"处存活,凡需确定性/原子性/进程外身份/跨厂商验证的全降级为咨询 = theater。

### 路线 (b) — Agent SDK 确定性外层 supervisor 调 CC per phase(复刻 graph.py)
**怎么做**:Python SDK driver 持有权威蒸馏 PipelineState(**不是** CC transcript),纯 index 算术推进相位,每相位调一次 `query()/resume()`(各自 `allowed_tools` = per-actor 最小权限),**相位间在外层进程**跑移植的 QualityGateChain,HMAC ApprovalAuthority secret 在 agent 触不到处,每事件发到进程外 HMAC 链审计 sink,安全停机时杀 query(),异构验证 shell out cursor/codex。
**给了什么**:**唯一**能把全部 crux 不变量 fail-closed 复刻的形态——确定性不可绕过顺序、BLOCKED 不可 approve、进程外审批身份、防篡改审计、真跨模型验证、进程级真停机。**唯一满足原则⑤硬不变量的路线**。
**放弃了什么**:明显更多工程(重建 supervisor / 状态 SSOT / 门禁接线 / 审计 sink / 审批 server);per-phase 门控部分牺牲 CC 自由奔跑;CC session append-only 且副作用跨 resume 持久,外层只能"拒绝推进",**不能真回滚**一个相位。

### 推荐:**HYBRID(thin-outer-supervisor),偏向用户目标但对原则⑤诚实**
不要把 (a)/(b) 当互斥。**用 CC 模型驱动 loop 当 per-phase 执行引擎**(这里"最快+充分借 CC"是真的、对的),外面套一层**薄** SDK supervisor,只接管 CC 内做不到 fail-closed 的非协商项:

1. 相位内 = 完整 (a) 自由:CLAUDE.md + skills + 反应式 hook 驱动一个正常 CC session。
2. 外层 SDK loop 只强制**五个硬 gap**:确定性相位推进 + 不可绕过 BLOCKED(X-supervisor);进程外 HMAC 审批(P4-perm);HMAC 链外部审计 sink(P8);爆炸半径靠 server 端 git pre-commit/CI 看全量 diff 原子化(P5);异构验证 shell out cursor/codex(X-judge)。
3. 用 Managed Settings + sandbox(`failIfUnavailable`, `allowUnsandboxedCommands=false`)锁住相位内 hook,使其不可被本相位 session 解除。
4. 先修地雷 judge.py:81(默认不可信),portable 方法论内核保持 CC-free 隔进 optional extra(保住残余 P9)。

> 这比纯 (a) 略多,但**远少于重建引擎**——是让用户保住"最快+借 CC"而 harness **不塌成 fail-open theater** 的最小代价。纯 (a) 只在一种情况下可接受:部署**明确**把宪法在 P5/P8/P4-perm/异构验证上降级为咨询——而这直接违反用户既定硬规则,故不推荐。

---

## 5. 真实 gap 与必须的外部脚手架(逐条引对抗实测)

| Gap | 能否关闭 | 怎么关(具体机制) | 对抗证据(为什么 CC 内不行) |
|---|---|---|---|
| **P5 爆炸半径** | 能(EXT) | (1) 所有写限进 CC Bash sandbox,`allowWrite`=worktree + `allowUnsandboxedCommands=false` + `failIfUnavailable=true`,bare-deny 任何非沙箱写路径;(2) **server 端 git pre-commit / CI** 用 `git diff --numstat` 看**全量** staged diff,files>10 或 (added+removed)>400 拒 commit——唯一能一次看全集且能正确数删除行;(3) 跑在一次性 worktree,超限改整体丢弃=穷人原子回滚。 | 实测:`for i in $(seq 1 500); do echo x > out_$i; done` 写 500 文件落盘而 hook(tool=Bash)退 0、counter 仍 0;Edit 路径 1–10 已落盘才拦第 11(非原子,无回滚);`python -c` 截断 5000 行文件的 4990 行删除对只数新内容的 hook 不可见。 |
| **P8 防篡改审计** | 能(EXT) | PostToolUse hook(经 MDM Managed Settings + `allowManagedHooksOnly` 锁不可变)把每事件 POST 到 agent 无写凭据的进程外 **MCP audit server / 远程 OTel collector**,服务器端 **HMAC 链**(端口 skeleton `ArtifactStore(secret=...)`,密钥在 agent 文件系统外)+ 维护**外部 anchor(head+count)**防尾截断;protected 分支签名 commit 当 git 不可变 backstop 应对 crash 漏记。 | 实测:CC 内 JSONL 非 protected path,Edit/Bash 可删改;`CLAUDE_CODE_SKIP_PROMPT_HISTORY`/`--no-session-persistence` 可在任何 hook 触发前关掉;PostToolUse crash 漏记;Bash 命令字符串粒度对 500 文件改盲。skeleton `test_unkeyed_full_rechain_forgery_passes` 证无密钥链可整链重算伪造;`test_jsonl_truncation_needs_external_anchor` 证尾截断需外部 anchor。**CC 内是死 gap,不出进程即 theater。** |
| **异构跨模型验证(X-judge)** | 能(EXT) | 全部异构验证移出 CC 进程,进 SDK 外层 / 独立 MCP 'verify' server(持 vendor CLI/keys);`backends.py` + `run-cursor-agent.sh` 搬离任何 agent 可写路径(**不是** `.claude/skills/`——CC 留它可写)、managed settings 钉死 `CLAUDE_CLI`/`PATH`、子进程前 scrub env。**(异构复审 §9 收紧)真信任边界 = runner + keys 在 model 完全不可写/不可影响(env/PATH/binary/输出解析器)的外部进程或服务里执行**;脱离这个外部边界,单靠 model-id challenge / 签名 token 的 "attestation" 仍会被能改 runner/env 的 model 演成新剧场。在外部边界**之内**再做 attestation 才有意义:断言 ≥2 个已验证 distinct vendor;缺真 vendor → `[independent gate not executable]` → HITL,绝不静默替成 Claude。 | 实测三连塌:`CLAUDE_CLI=/bin/echo` 后 `ClaudeCLI.available()` 仍 True;PATH 放假 `cursor-agent` 后 `available()` 仍 True 且无 fail-closed marker;`run-cursor-agent.sh` 在 CC **可写的** `.claude/skills/` 下,agent 可把 `--model gpt-5.5-medium` 改成 Claude。叠加 judge.py:81(本次复核确认 `trust_llm=(not isinstance(self.llm,MockLLM))`)→ 任何真 LLM 翻 trust ON;CC subagent 全 Claude = 循环自证。`backends.py` grep `attest/identity/fingerprint/distinct` 全无。 |
| **安全停机(P4-halt)** | 部分(EXT) | SDK 外层 supervisor 检测 halt 信号(外层状态 / custom-tool `safe_halt` 返回)→ **tear down query()/杀进程**(复刻 graph.py invoke() 在 _STOP_STATES 上 return);**不**靠 continue:false;失败计数器/HALTED/BLOCKED flag 在外层进程状态、绝不在 agent 可写 workspace。 | CC 文档:"Blocking Stop does NOT kill the agent mid-thought""no hard time-out to kill a rogue session";hook 拒工具 N → model 换工具重试 = 拒绝循环非停机;计数器若在 workspace,model 一次 Edit 重置为 0。"不伪造完成/不吞错"是**文本语义属性**,任何 hook 都不强制——靠独立 verifier+变异检查(其 `tests_ok` model 写不到)+ 异构验证,这是另一套机制,不是 halt。 |
| **不可绕过有序门禁(P1/P2/P3, X-supervisor)** | 能(EXT) | (A) SDK 外层 supervisor 纯 index 推进 + BLOCKED 不可 approve;(B) 权威 PipelineState/registry 在外层进程,**绝不**在 agent 可写文件;门禁链在外层 Python 相位间跑读该状态;(C) `tests_ok`/coverage/sast_ok 只由 model 触不到的 verifier(外层或真 CI)写,CC 内 gate hook 只经 MCP 工具**读**;(D) refs 由外层 loop 从真实相位产物填(补 aiforge 自己缺的 dangling-ref 负测);(E) **server 端 git pre-commit + protected branch + required CI** 重 diff 全量 + 重跑门禁,无视文件怎么写;(F) MDM Managed Settings 锁 hook。 | 实测:`echo '{"tests_ok":true,"coverage":0.95}' > .harness/state.json`(workspace 应用数据,**非** `.claude/*` protected)即让 commit gate 读自己伪造的绿;commit 边界被 `$(git commit)`/heredoc/`python -c subprocess` 子进程旁路;refs 由 model 填可给孤儿代码挂 `refs=['spec']`,TraceabilityGate 只查 KIND 存在不查血缘(aiforge 自承无 dangling-ref 负测)。 |

---

## 6. 必须先修的地雷(旧报告 + 本次新发现)

**旧报告三地雷(本次均已实测复核 CONFIRMED):**
1. **judge.py:81 身份信任后门**——`self.trust_llm = (not isinstance(self.llm, MockLLM))`(本报告逐行复核,逻辑原样仍在)。挂任何非-Mock 真 LLM(如 ClaudeAgentLLM)→ trust_llm=True → judge 仅凭模型裁决自动放行,正是它声称修掉的 bug。**修:每 client 显式 `trusted=True`,默认不可信,且 trusted 必须绑定到已 attest 的非-Claude vendor。**
2. **openhands.py:54/59 半成品适配器缝**——两处 `NotImplementedError`("接通 OpenHands API 后实现")。**修:C/适配器验收门 = 有 key 时真发一次调用拿到响应,绝不止步 NotImplementedError。**
3. **memory.py:24 单厂商耦合种子**——`compact_trigger_tokens: int = 50_000  # 与 Anthropic compact 最小阈值一致`,是全 src 唯一把调参钉死到单厂商公布数字处。**修:移成 GovernanceConfig 字段,去掉"Anthropic 阈值"钉死。**(全 src `anthropic|claude|bedrock|vertex|litellm` 当前恰 3 命中:memory.py×2 + llm.py docstring,中立基线未漂移——修此条防漂。)

**本次对抗新发现(必须当 fail-open 风险登记并修):**
4. **用户当前真实部署 = 最坏配置**:`defaultMode=bypassPermissions` + `allow=['Bash(*)']` + `deny=[]` 空 + 无 MDM。**这是 0 号地雷**——任何红绿灯里的"绿/黄"在这台机器上都未点亮。**修:先部署 Managed Settings(`allowManagedHooksOnly` + `allowManagedPermissionRulesOnly` + `disableBypassPermissionsMode`),否则下面所有强制都是空中楼阁。**
5. **harness 状态文件在 agent 可写 workspace**:实测一次 model 写把 blast-radius counter 从 9 重置为 0;`tests_ok` 可被 `echo > state.json` 伪造。**修:状态/证据 SSOT 出 workspace 进外层进程或 MCP server;CC 内只经只读 MCP 工具读取——绝不读 model 可 Edit/Bash 触及的 .json。**
6. **`run-cursor-agent.sh` 在 CC 可写的 `.claude/skills/`**:CC 故意把 skills 目录留可写(skill authoring),agent 可改 `--model` 或换成 echo。**修:异构 runner 搬离 `.claude/skills/`,sandbox denyWrite + managed settings 钉死 `CLAUDE_CLI`/`PATH`。**
7. **`git-guardrails.sh` 正则剧场**:8 条间接 Bash 旁路全 ALLOW(var-indirect / alias / pipe-to-bash / `bash -c` / `$(echo git)` / `python subprocess` / `/usr/bin/git` / `git push origin +main` refspec force)。**修:任何模式/正则 Bash matcher 一律当咨询,永不当 fail-closed 控制;真控制靠 bare-deny 整工具移除 + OS sandbox + server 端门禁。**

---

## 7. 分期实施计划(MVP 优先,每期带可执行验证点)

> 贯穿原则:每期成功标准都是**可执行验证**(原则④);并把对抗探针(§5/§6 的旁路用例)作为回归测试,防 harness 静默退回 fail-open(原则⑤)。现有 33 条 aiforge pytest + skeleton 268 条作为 fitness check,全程保持绿。

### Phase 0 — 锁定地基(没有它,后面全是 theater)
- 部署 **MDM Managed Settings**:`allowManagedHooksOnly`、`allowManagedPermissionRulesOnly`、`disableBypassPermissionsMode`;关掉当前 `bypassPermissions`/`Bash(*)`。
- sandbox:`enabled` + `failIfUnavailable=true` + `allowUnsandboxedCommands=false` + `filesystem.allowWrite` 限 worktree + `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`。
- **验证点**:跑 §6 的 8 条 Bash 旁路 + 500 文件写风暴,**全部被 OS sandbox 拒**(不再靠正则);`claude --dangerously-skip-permissions` 被 managed settings 拒启。修 judge.py:81 默认不可信,`PYTHONPATH=src python3 -m unittest discover -s tests` 仍 33 绿。

### Phase 1 — 外部审计证据层(与 Phase 0 合并为同一去风险原型;异构复审 §9 修正了顺序与起步件)
- **先开原生 `受管 OTel`(零自研)**:受管 env 强制 `CLAUDE_CODE_ENABLE_TELEMETRY` + OTLP exporter,事件(tool decision/permission/api)直送 model 写不到的外部 collector/SIEM——**最便宜的事件级抗篡改证据层**,先有它再决定哪些高保证场景值得自研 HMAC sink。
- **再按需加自研 sink(内容级/防篡改)**:独立 MCP audit server,HMAC 链 + 外部 anchor(head+count),链密钥在 agent 文件系统外;PostToolUse hook(managed-locked)POST 每事件 + 文件 diff。
- **CLAUDE.md** 此期只写叙事:宪法 P1-P9 摘要——明确标注它是咨询性、不是门禁。
- **验证点**:受管 OTel 下,model 删本地 JSONL / `--no-session-persistence` 启动后,**外部 collector 仍如实收到事件**(证事件级抗篡改);自研 sink 则 port skeleton 的 `test_unkeyed_full_rechain_forgery_passes` / `test_jsonl_truncation_needs_external_anchor`——HMAC 版**拒**整链重算伪造、**测出**尾截断。

### Phase 2 — 第一批 fail-closed hook + server 端门禁 backstop
- 写并 managed-lock:**PreToolUse**(Edit/Write 跑移植 SpecGate → 无 frozen spec 即 deny,强制 **P1**;跑 StaticRiskScanner 正则命中 deny,强制 **P6** 匹配面);**Stop/PostToolUse** 产 P7 checklist。
- **server 端 git pre-commit + protected branch + required CI**:`git diff --numstat` 看全量 diff,files>10 或 (added+removed)>400 拒(原子 **P5**);重跑 SpecGate/TraceabilityGate/QualityGateChain(**P3 真 backstop**)。worktree 一次性化。
- **subagent/skill**:每 SDLC 相位一个 skill(spec/architecture/decompose);role subagent 仅作上下文隔离,**不**当评审 panel(它们全是 Claude)。
- **验证点**:无 spec 写 code 被 PreToolUse 拒;500 文件写风暴**在 pre-commit 被拒**(即使 sandbox 漏也兜住);`echo '{"tests_ok":true}'` 伪造状态后 commit 仍被 CI 重跑门禁拒(因证据来自外层 verifier 非 workspace)。33 pytest 绿。

### Phase 3 — Agent SDK 薄外层 supervisor(补 X-supervisor / P4-halt / P3 权威化)
- Python SDK driver:持权威 PipelineState SSOT(非 transcript),纯 index 推进,每相位一次 `query()`(各自 `allowed_tools`=per-actor 最小权限),相位间外层跑门禁链,BLOCKED 不可 approve(复刻 graph.py:86-88),halt 信号 → 杀 query()。
- `tests_ok`/coverage/sast 只由外层 verifier(sandbox 跑测试 + 变异检查)或真 CI 写入 SSOT;CC 内 gate 只经 MCP 工具读。
- **验证点**:高风险相位触发 NEEDS_HUMAN→approve→DONE;BLOCKED resume 不变(无 override);halt 后进程真被 tear down(非 deny-loop);refs 由外层从真实相位产物填,补 **dangling-ref 负测**(aiforge 现缺)。

### Phase 4 — 进程外 ApprovalAuthority + 异构验证桥(补 P4-perm / X-judge)
- 独立 MCP server(或 SDK 外层)持 HMAC secret,签 actor-bound + nonce + TTL + 单次票据;敏感能力仅暴露为服务器端校验 MCP 工具。
- 异构桥:`backends.py` 搬离 `.claude/skills/`,shell out cursor-agent(GPT-5.5)/codex,加 **vendor attestation**(model-id challenge / 签名 token),断言 ≥2 distinct 已验证 vendor,缺 → `[independent gate not executable]` → HITL;加 **backends 距离/distinctness 负测**(现完全没有)。
- **验证点**:伪造票据/重放/跨 actor 泄漏被拒(port test_governance);`CLAUDE_CLI=/bin/echo` 与 PATH 假 cursor-agent **被 attestation 拒**并 fail-closed 转 HITL;两 backend 解析到同 vendor/binary 时负测 fail-closed。

> **fitness check 贯穿**:每期结束 `PYTHONPATH=src python3 -m unittest discover -s tests` + skeleton 套件全绿,并新增该期对抗探针为永久回归——绿测是**异构/进程外**证出来的,不是自证。

---

## 8. 取舍与诚实边界

**相比当前 aiforge 失去的:**
- **确定性 supervisor 路由**:graph.py 纯 index 推进在 CC 内不存在,只能靠外层 SDK loop 重建——且 CC session append-only、副作用跨 resume 持久,外层只能"拒绝推进"**不能真回滚**一个相位(比 aiforge 的 checkpoint 弱)。
- **真·跨模型独立性**:CC subagent 全 Claude,异构必须出进程 shell out cursor/codex;独立 best-of-N 需 ≥3 vendor(1 oracle 作者 + ≥2 独立候选),codex 仍是硬依赖。
- **离线 / 零依赖 / 厂商中立(P9 engine 层)**:被用户决策有意放弃;受监管/气隙产品线**必须保留自研引擎**,CC 上跑不起来。
- **base.py:65 那个唯一强制漏斗**:CC 下 N 个 Read/Write/Edit/Bash 各自落 transcript,permission/blast-radius/audit 的单点强制被打散——必须靠外层重新汇聚。

**获得的:**
- CC 成熟的工具/模型驱动 loop/规划/checkpoint/session/MCP/skill 生态——**最快路径**,几乎不写引擎代码。
- 真 OS 级 Bash sandbox(Seatbelt/bubblewrap)+ bare-deny 整工具移除:这两个原语**比 aiforge 自己的 LocalSandbox 更接近生产硬化**(虽窄)。
- portable 方法论内核(spec/gate 逻辑/审计 schema/状态模型)若保持 CC-free,**方法论仍可再平台化**,即便 engine 锁 Claude。

---

### 最该先 prototype 的一件事(去风险整盘赌注)

**先做"Phase 0 受管配置地基 + 外部审计证据层"这一个合并原型**(异构复审 §9 修正了原"先自研 HMAC sink"的提法):① 部署 MDM Managed Settings(禁 bypass / 禁或强 sandbox Bash / managed-only hooks)——**没有它,审计 sink 的覆盖面本身不可信**(model 能绕 hook、关 persistence、Bash 乱写);② 同一原型里开**原生受管 OTel**,把每个工具调用/权限决策送到外部 collector;③ 立即跑对抗探针:model 删/改本地 JSONL、`--no-session-persistence` 启动、(自研 sink 才需的)整链重算伪造 + 尾截断——验证**外部 collector 仍如实收到事件**。

理由:P8 是整套 harness 的"地基真实性证明",但它的前提是 Phase 0 锁住"model 关不掉/绕不过记录通道"。先用**零自研的受管 OTel** 把"每个 model 动作都被一个关不掉、改不了、漏不掉的外部层如实记下"证出来(证明而非声称),其余门禁才有可被独立审计的立足点;HMAC 链 + 文件级 diff 留给确有高保证需求时再自研。反过来,若连受管 OTel + Phase 0 这步都证不出 fail-closed,说明赌注该收缩到路线 (b) 全量外层或对受监管线保留自研引擎,而不是继续往纯 (a) 投钱。

---

## 9. 异构复审修正(cursor-agent / GPT-5.5,2026-06-09)

> 本报告由全 Claude 多-agent workflow 产出(已含对抗实测真 hook)。按原则⑤再上一次**真跨模型**终审:cursor-agent(GPT-5.5)独立复审结论。下表 steelman → 裁决 → 落改。GPT-5.5 抓到一个全 Claude workflow 系统性漏看的真盲区(**原生受管 OTel**),并收紧若干 overclaim;**无一条被全盘反驳**。

| # | GPT-5.5 意见 | 裁决 | 落改 |
|---|---|---|---|
| 1 | P8 判"CC 内死红"是 overclaim——漏了原生**受管 OTel**(强制 env → 外部 collector,model 写不到)能抬到黄 | **部分接受** | P8 改"黄红分层":事件级黄(受管 OTel,原生抗篡改)/ 完整内容级+防篡改仍红(需外部 HMAC sink)。§1 表 + §3 + §7 + §8 已改 |
| 2 | "纯路线 a = theater"过死——受管锁定纯 CC(禁 bypass+sandbox Bash+disallowedTools+OTel+CI)能 fail-closed 覆盖部分硬控制 | **部分接受** | §1 执行摘要收紧:写面/粗权限/事件审计/原子 blast-radius 是 fail-closed;仅确定性/异构/审批/完整审计仍 fail-open 需外部 |
| 3 | "thin supervisor 是最小形态"不严谨——MVP 可先 Phase0+OTel+CI+受管 MCP,不必立刻写全 SDK supervisor | **部分接受** | 区分"完整原则⑤的最小可靠形态"(=混合,end-state)vs"MVP 最小"(=受管策略+OTel+CI);分期计划本就如此排,措辞校准 |
| 4 | 红队实测(8 Bash 旁路/500 写风暴/计数器重置/`CLAUDE_CLI=echo`)技术准确,但外推过宽——只证"当前配置+当前实现"fail-open,非"所有 CC 受管配置"fail-open | **接受(收窄范围)** | 明确这些证据 load-bearing 范围 = "Bash 开放且状态/runner 可写";Phase 0 sandbox/禁 Bash 后多数旁路即死。§1 摘要已点明这层 |
| 5 | vendor attestation 太乐观——model-id challenge/签名 token/PATH 检查挡不住能改 runner/env 的 model,本身可能是新剧场 | **接受(收紧)** | §5 异构行:真边界 = runner+keys 在 model 不可写/不可影响的外部进程/服务执行;attestation 只在该外部边界**之内**才有意义,绝非替代 |
| 6 | "先 prototype P8 sink"优先级错——没 Phase 0 地基,sink 覆盖面本身不可信;应 Phase 0 + 审计层一起做,且先用零自研的受管 OTel | **接受** | §7 Phase1 与 §8 首原型改为"Phase 0 锁定 + 受管 OTel"合并原型;自研 HMAC sink 降为高保证内容级才做 |

**反驳/精化**:无整条反驳。唯一对 GPT-5.5 的**精化**(非反驳):它建议 P8"红改黄",我落为**"黄红分层"**而非平移到黄——因为受管 OTel 只覆盖事件/决策级,对 Bash 内副作用(500 文件改)同样盲、且非防篡改 ledger,完整内容级审计仍是红。这比单说"黄"更精确,两头都不 overclaim。

**元教训(再证原则⑤)**:全 Claude workflow 即便做了对抗实测,仍系统性漏看"受管 OTel"这一 **Anthropic 自家能力**——正是同模型共享盲区;一个不同模型(GPT-5.5)一眼看出。结论:关键裁决必须**跨模型**过一遍,绿测/自评不算被验证。