# AISEP × Claude Code — 有头先行实施方案(STEP 0)

| | |
|---|---|
| **日期** | 2026-06-10 |
| **状态** | **已被 v2 取代**(2026-06-11,经 cursor 异构评审 + 对抗证伪修订)→ 见同目录 `AISEP-ClaudeCode有头先行实施方案-v2.md`;本文保留为历史记录 |
| **前置** | `../decisions/AISEP-ClaudeCode架构决策文档.md`(ADR-001~010)+ 本轮两次评审结论 |
| **一句话** | 功能版组件(agents/skills/hooks/CLAUDE.md/复用核)全部落地,但 **supervisor 由人担任(有头交互模式)**;Agent SDK driver(ADR-003)推迟到明确触发条件出现;**真·代码强制层放在 git hook + CI,不依赖 CC**。 |

---

## 0. 决策依据(评审结论摘要)

1. **计费**:6-15 起无头/Agent SDK 走单独月度额度(API 价);有头交互继续走订阅。验证期跑量在有头侧≈零边际成本。
2. **功能版组件与 driver 解耦**:`.claude/agents/`、skills、hooks、CLAUDE.md、MCP、aiforge 核在有头模式下原样可用;两条路线唯一差异是"代码当 supervisor"还是"人当 supervisor"。本方案产出的全部资产将来被 driver 路线**原样继承**,无沉没成本。
3. **有头模式的真实弱点**是门禁退化为建议(人可能跳过阶段)。对策不是提前写 driver,而是把强制点移到 **CC 进程外**:pre-commit hook + CI 跑 aiforge 门禁——不可绕过、零 CC 额度、且功能版/强制版通用。
4. driver 的缺口(状态落盘、输出契约、HITL resume、`--bare` 防御)全部推迟,随 driver 一起做。

### 升级到 driver(ADR-003)的触发条件(任一即启动)
- [ ] decompose 经常拆出 ≥3 个特性需要并行;
- [ ] 实证发生"跳门禁"(纪律衰减);
- [ ] 需要无人值守运行(CI 触发 / 夜间批量);
- [ ] 操作者 >1 人,流程不能靠个人自觉。

---

## 1. 总体形态

```
人(supervisor:定序、审批、resume)
 └─ Claude Code 交互会话(引擎)
     ├─ CLAUDE.md ← @import constitution.md(宪法,建议层)
     ├─ .claude/agents/*.md     角色子代理(7 个)
     ├─ .claude/skills/         阶段 skills(P3/PA/decompose/integrate/gate)
     ├─ .claude/settings.json   hooks(会话内护栏)+ 权限白名单
     └─ Bash → python -m aiforge ...(薄 CLI,调用复用核)
进程外(真强制,AI/人都绕不过):
 ├─ .git/hooks/pre-commit → make gate-commit
 └─ GitHub Actions → make gate-feature(门禁链 fails-closed)
```

产物落盘约定:每个特性一个 `specs/<feature-id>/` 目录,内含 `spec.md`(冻结)、`plan.md`、`tasks.md`。这就是有头模式的"状态存储",将来 driver 直接复用。

---

## 2. 交付物清单

### M1 · 薄 CLI:把 aiforge 核暴露给 CC(唯一要写的代码)

现状:`gates.py` 吃 `PipelineState + evidence`,有头会话里没有 PipelineState。需要一个**文件/git → 门禁**的适配层,新增 `src/aiforge/harness.py` + `cli.py` 子命令(全部 stdlib,遵守层边界):

| 子命令 | 输入 | 复用 | 输出/退出码 |
|---|---|---|---|
| `aiforge gate-spec <file>` | spec.md 路径 | `SpecGate`(P1,EARS/Gherkin/User Story 校验) | 过=0,缺验收结构=1 并打印缺什么 |
| `aiforge gate-trace <dir>` | specs/<id>/ 目录 + git 内代码引用 | `TraceabilityGate`(P2)语义 | 0/1 |
| `aiforge gate-judge [--staged]` | `git diff` 文本 | `StaticRiskScanner` + `AgentAsJudge` 三态裁决 | approved=0;needs_human=2(打印人审清单);rejected=1 |
| `aiforge review-3f [--staged]` | `git diff --numstat` → `FileChange` | `review_after_session`(P7 三文件 review) | 打印必读清单 |
| `aiforge gate-commit` | 聚合:lint + gate-judge + review-3f | `PreCommitGate` 语义(fails-closed) | 0/1/2 |

诚实边界:离线时 `AgentAsJudge` 无可信 LLM → 按现有语义一律 `needs_human`(exit 2),**不静默放行**;人审通过后用 `--ack-human` 落一条审计记录再放行。

验收:每个子命令有 `tests/test_harness.py` 用例;`make test`、`make arch`(import-linter)全绿。

### M2 · CLAUDE.md + 角色子代理 + 阶段 skills(纯 Markdown)

**`CLAUDE.md`(根目录,薄)**:`@constitution.md` + `@AGENTS.md` 导入,避免三处复制;另加一段"SDLC 纪律":任何特性必须按 requirements → gate → architecture → gate → decompose → 实现循环 → integrate 走,每阶段产物落 `specs/<id>/`,阶段切换前必须跑对应 `aiforge gate-*` 并把结果贴回会话。

**`.claude/agents/`(7 个,与 `orchestration/agents.py` 节点职责一一对应)**:

| 文件 | 职责(来自现有节点) | 工具白名单要点 |
|---|---|---|
| `analyst.md` | 需求澄清 + EARS/Gherkin 验收标准 → spec.md | Read/Grep;**禁 Write 代码、禁 Bash** |
| `architect.md` | 模块边界 + 数据流 + ADR → plan.md | Read/Grep/Glob;禁改码 |
| `developer.md` | 按 tasks 实现;P4 安全停机:无法安全完成 state-mutating 任务时停下上报,禁止吞错/谎报 | Read/Write/Edit/Bash(受 hooks 拦截) |
| `reviewer.md` | 对照 P6 非功能清单(错误处理/安全/可观测/限流/审计)审 diff | Read/Grep;禁 Write |
| `tester.md` | 产出 unittest;只写 tests/,禁改 src/ | Read/Write(限 tests/)/Bash(只跑测试) |
| `verifier.md` | 沙箱真跑 `make test` + 集成验证,输出证据 | Bash/Read |
| `judge.md` | 汇总 reviewer/tester/静态扫描,给 SEVERITY 裁决;**异构评审走 skill 调 cursor-agent,缺真异构 → 明示"转人审",绝不自评自过** | Read/Bash(只跑 `aiforge gate-judge`) |

**`.claude/skills/`(5 个)**:

| skill | 输入 → 输出 | 内嵌门禁 |
|---|---|---|
| `sdlc-requirements` | 原始需求 → `specs/<id>/spec.md` | 末步必跑 `aiforge gate-spec`,不过则迭代,不得带病推进 |
| `sdlc-architecture` | spec.md → plan.md(+ADR) | 对照 `.importlinter` 分层红线自查 |
| `sdlc-decompose` | plan.md → tasks.md(特性拆分 + 依赖序) | 标注可并行组;>P5 blast-radius 上限的任务必须再拆 |
| `sdlc-integrate` | 各特性产物 → 装配 + `make test` 全量 | 跑 `aiforge gate-trace` + `gate-commit` |
| `sdlc-gate` | 当前阶段名 → 跑对应 gate-* 并解读结果 | 即"门禁怎么跑"的使用说明书,供其他 skill 引用 |

异构评审(ADR-006)在 `judge.md`/`sdlc-gate` 里以 Bash 调 `cursor-agent`/`codex` 实现;二者不可用时输出"异构缺席,转人审"——fail-closed 语义保留,只是执行者是人。

### M3 · hooks + 权限白名单(会话内护栏,宽松版)

`.claude/settings.json`(项目级,入库):
- `permissions.deny`:`Bash(git push --force*)`、`Bash(rm -rf /*)`、`Read(.env*)`、`Write(.env*)`、`Write(constitution.md)`(P0:宪法只能人改);
- PreToolUse hook:命中 `governance/permissions.py` 同源的危险模式(os.system / 裸写盘已由代码约定管,这里拦 shell 层等价物)→ exit 2 硬拦;
- Stop hook:会话结束提示跑 `aiforge review-3f`(提示,不拦)。

功能版边界(对齐 ADR-002):hooks 只护会话内;"AI 改掉 settings 本身"不在本版设防范围,留给强制版 managed-settings。

### M4 · 进程外强制层 + 成本测量

1. **pre-commit**(`.git/hooks/` 或 pre-commit 框架):跑 `aiforge gate-commit`,exit≠0 拒绝提交。
2. **CI**(`.github/workflows/gates.yml`):PR 上跑 `make test` + `make arch` + `aiforge gate-spec`(对 PR 涉及的 specs)+ `aiforge gate-judge`(对 PR diff);任一失败禁止合并。**这是有头路线里唯一"AI 和人都绕不过"的层,对应 P3。**
3. **Makefile** 新增:`gate-commit`、`gate-feature`(聚合)。
4. **成本测量**:`settings.json` `env` 开 `CLAUDE_CODE_ENABLE_TELEMETRY=1` + OTLP/file exporter(或最低配:每次管线跑完记 `/cost` 到 `eval/cost-log.md`)。验收标准:**得出"单特性全管线 token 与美元成本"一个实数**——这是将来 driver 决策(ADR-009 额度够不够)的输入。

---

## 3. 实施顺序与验收

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1(先做) | `harness.py` + CLI 子命令 + 测试 | `make test`/`make arch` 绿;5 个子命令可独立跑 |
| M2 | CLAUDE.md / agents×7 / skills×5 | 有头会话里:`/agents` 可见 7 角色;对一个玩具需求走完 requirements→gate-spec 闭环 |
| M3 | settings.json hooks + deny | 实测:改 `.env`、写 `constitution.md`、force-push 均被拦 |
| M4 | pre-commit + CI + 成本记录 | 故意提交无 spec 的代码 → CI 红;跑通**一个真实小特性**全管线,产出成本实数 |
| 试运行 | 用本管线给 aiforge 本身做一个真特性(自举) | 七阶段产物齐、门禁全过、三文件 review 完成、成本入账 |

预计代码量:M1 约 200~300 行 + 测试;M2/M3 纯 Markdown/JSON;M4 约 50 行 YAML/Make。

---

## 4. 对《架构决策文档》的连带修订

1. §0 删除/修正 "`backends.py`" 表述(仓库不存在该文件,异构 runner 实为从零写,落点在 M2 的 judge skill)。
2. ADR-005 澄清矛盾:**阶段间门禁 = 进程外强制(本方案 M4 的 pre-commit/CI;driver 版为 driver 代码),hooks 仅会话内护栏**;删除"质量门→hooks 当报告"的归位。
3. 新增 **ADR-011(本方案)**:有头先行,driver 按 §0 触发条件启动;状态存储 = `specs/<id>/` 文件约定。
4. 新增 **ADR-012(占位,随 driver 生效)**:driver 不依赖 `-p` 自动发现(防 `--bare` 默认翻转),所有加载项显式传 + 钉死 CLI/SDK 版本。

---

## 5. 风险与边界(诚实清单)

- **门禁覆盖缺口**:有头模式拦不住"整个阶段被跳过",只能在 commit/PR 边界兜底——阶段内的过程纪律仍靠人,此为本方案接受的残余风险(触发条件②的监测对象)。
- **judge 离线即转人审**:验证期每个特性至少一次人审介入,这是 fail-closed 的代价,不是 bug。
- **`.claude/` 资产与 `AGENTS.md` 双轨**:Cursor 读 AGENTS.md,CC 读 CLAUDE.md;用 @import 保持单一事实源,新约定只写 AGENTS.md/constitution.md。
- **成本数据偏差**:有头会话含人的来回讨论,token 高于纯无头管线;估算 driver 成本时按上界使用。
