# AISEP × Claude Code 工程 Harness — 完整使用手册

| | |
|---|---|
| **项目** | AISEP · `github.com/Albertsun6/aisep`(public) |
| **版本** | STEP 0(有头模式,2026-06-11 完整实施) |
| **一句话** | 把 aiforge 七层方法论做成 Claude Code 的企业工程纪律层:薄门禁 CLI + 进程外强制层(GitHub CI)+ 会话内护栏,人当 supervisor。 |
| **基线 tag** | `archive/pre-harness`(harness 之前的状态,随时可回退) |

> 本手册面向**使用者**(人)。给 agent 的指令在 `CLAUDE.md`;架构为什么这么定在 `docs/decisions/`;接口契约在 `specs/contracts/`。

---

## 1. 这套东西是什么

一个把"AI 工程化开发企业软件"的方法论落成**可执行纪律**的骨架。它不替换 Claude Code 引擎,而是在其上叠三件事:

1. **一条薄门禁 CLI**(`python -m aiforge gate-*`)——把规格驱动的质量门(spec 验收结构、追溯链、静态风险、提交聚合)变成命令,**永不调用模型**,退出码可被脚本/CI 消费。
2. **进程外强制层**(GitHub CI `gates` workflow)——唯一"AI 和人都绕不过"的层。本地钩子和会话护栏都只是反馈/防呆。
3. **状态落盘约定**(`specs/<feature-id>/`)——每个特性的 spec/plan/tasks + 门禁回执(receipt)落文件,既是有头模式的状态存储,也是将来自动化 driver 的继承对象。

**核心心智:三层权威**(详见 §5),记住一句话就够——**会话内的一切都不是强制,真强制只在 GitHub CI。**

---

## 2. 快速开始

### 2.1 跑起来(零安装,纯标准库)

```bash
git clone https://github.com/Albertsun6/aisep.git
cd aisep

make test     # 跑全部测试(78 个,无需任何安装)
make demo     # 端到端规格驱动 + 多 agent 编排(mock LLM,离线)
make eval     # eval 四指标
```

> **source-rooted**:本项目用 `PYTHONPATH=src`,不是 pip 安装。`make` 已内置该环境变量;直接调 CLI 时必须自己带上(见 §4)。

### 2.2 启用本地门禁(可选,反馈层)

```bash
make hooks    # = git config core.hooksPath .githooks
```

启用后每次 `git commit` 自动跑 `gate-commit`(feature 声明 + receipt 链 + lint + 静态风险)。这是**反馈层**,可用 `git commit --no-verify` 旁路——明文承认,真拦截在 CI。

### 2.3 装可选开发依赖(lint 需要)

```bash
make install-dev   # 装 ruff + import-linter
```

`gate-commit` 的 lint 步骤是 fails-closed 的:ruff 缺失会让门禁退出码 3(基础设施错误),不是静默放行。

---

## 3. 完整工作流:一个特性怎么走完管线

每个特性一个 `specs/<feature-id>/` 目录(`feature-id` 小写 kebab-case)。阶段顺序与对应门禁:

```
需求  → gate-spec        → 架构   → gate-trace → 拆分 → 实现循环 → gate-judge → gate-commit
spec.md                   plan.md             tasks.md            (developer/reviewer/tester)
```

| 步 | 你做什么 | 跑什么门禁 | 产物 |
|---|---|---|---|
| ① 需求 | 写 `specs/<id>/spec.md`(Gherkin/EARS 验收结构 + 非功能清单) | `gate-spec specs/<id>/spec.md` | spec.md + `gates/gate-spec.json`(receipt) |
| ② 架构 | 写 `plan.md`(声明 `> refs: spec.md`) | — | plan.md |
| ③ 拆分 | 写 `tasks.md`(声明 `> refs: plan.md`,标可并行组) | `gate-trace specs/<id>` | tasks.md + `gates/gate-trace.json` |
| ④ 实现 | 写 `src/` 代码 + `tests/` 测试 | `gate-judge --staged`(随时) | 代码/测试 |
| ⑤ 提交 | `git add` + 提交 | `gate-commit --feature <id>`(钩子自动跑) | `gates/gate-commit.json` |

**铁律**:`src/`、`tests/` 的改动提交时必须声明所属 feature(`--feature <id>` 或 `AIFORGE_FEATURE=<id>`),且该 feature 有过 gate-spec receipt。否则被拒(退出码 1)——这就是"无 spec 不许写代码"的机器强制。

### 用 skill 走需求阶段

会话里直接说"走管线 / 起 spec / 需求工程",会触发 `sdlc-requirements` skill:调 `analyst` 子代理产出 spec 草稿 → 跑 `gate-spec` → 不过则迭代,不带病推进。门禁怎么跑、退出码怎么读,见 `sdlc-gate` skill。

---

## 4. 门禁 CLI 完整参考

所有命令前缀 `PYTHONPATH=src python3 -m aiforge`(或先 `export PYTHONPATH=src`)。

| 命令 | 作用 | 退出码 |
|---|---|---|
| `gate-spec specs/<id>/spec.md` | P1:校验 spec 验收结构,过则落冻结 receipt | 0 过 / 1 缺结构 / 3 基础设施 |
| `gate-spec --check specs/<id>/spec.md` | **只读冻结校验**(CI 用):验 spec 仍合法 **且**已提交 receipt 与当前内容相符,**不重新生成 receipt** | 0 / 1 过期或伪造 / 3 |
| `gate-trace specs/<id>` | P2:校验文档追溯链(plan→spec,tasks→plan 的 `refs` 声明解析) | 0 / 1 链断 / 3 |
| `gate-judge --staged` | 静态风险扫描三态(扫 `git diff --cached`)。**永不调模型** | 0 无命中 / 2 转人审 |
| `gate-judge --base <sha>` | 同上,审 `<sha>...HEAD` 范围(CI 用) | 0 / 2 |
| `review-3f --staged` | P7:三文件 review 必读清单(信息性) | 0 |
| `gate-commit --feature <id>` | 聚合:feature 声明 + receipt 链 + lint + 静态风险 | 0 / 1 / 2 / 3 |
| `gate-commit --ack-human` | 本地人审 ack(needs_human 时,**仅审计**,需 tty) | — |

### 退出码语义(契约 03,所有消费方只认这四个)

| 码 | 含义 | 消费方动作 |
|---|---|---|
| **0** | approved,通过 | 放行 |
| **1** | rejected,内容问题(缺 spec / 链断 / receipt 过期 / lint 未过) | 拒绝,按输出修内容后重跑 |
| **2** | needs_human,转人审 | 不得当通过;本地放行走 `--ack-human`(仅审计),**权威放行=GitHub 人类账号 PR approval** |
| **3** | infra_error,基础设施错误(包 import 失败 / 配置缺失 / receipt 坏 / ruff 缺) | 看 stderr 诊断,修好再来 |

> CI 与本地钩子遇到 **0/1/2/3 之外的任何值**(进程被杀 130/137、超时 124 等)一律按 infra_error 处理,不放行。

### receipt(门禁回执)

每次门禁由 CLI 真实命令写出 `specs/<id>/gates/<gate>.json`,记录:gate 名、输入文件路径+sha256、退出码、decision、git HEAD、时间、工具版本、argv。这是对抗"长程自主静默跳阶段"的机器证据——**跳了 = receipt 缺失 = gate-commit/CI 拒绝**。

- `gate-spec`/`gate-trace` 的 receipt **入库**(冻结链/追溯需要)。
- `gate-commit` 的 receipt 是"记录本次提交"的产物,无法进它自己那个 commit,**被 gitignore**(本地反馈,权威=CI 重跑)。

---

## 5. 三层权威模型(最重要的心智)

| 层 | 机制 | 性质 | 谁能绕过 |
|---|---|---|---|
| **强制层(唯一)** | GitHub CI(`gates` workflow)+ branch protection + CODEOWNERS | 对 AI 和人同等生效 | 仅 repo admin 走 break-glass |
| 反馈层 | 本地 `.githooks/pre-commit`(`core.hooksPath`) | 快速反馈,**明文可旁路**(`--no-verify`、改 hooksPath) | 任何人/任何会话 |
| 会话护栏 | `.claude/settings.json` 的 `permissions.deny` | 会话内摩擦,防呆不防恶 | 改 settings、换无防护会话 |
| 建议层 | `CLAUDE.md` / `constitution.md` / skill 文案 | 模型可无视 | 模型自身 |

**硬规则**:会话内的一切编排(Workflow、Agent 工具、长程会话、本地 hooks)**永远不是强制**——它们是"被约束方自己执行的约束",定义落在模型可写路径。"已强制"四个字只能指向 GitHub 配置生效后的强制层。

### GitHub 强制层配置(已配)

- branch protection on `main`:required status check = **`gates`**(名字钉死),strict、需 PR、需 code-owner 审批。
- CODEOWNERS 保护路径:`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/` → owner `@Albertsun6`。
- ⚠️ **`enforce_admins=false`**(你的裁决:单人仓库 admin 可 bypass)。后果:强制层对 repo admin(你本人)不生效,只对其余主体生效。**多操作者时须重开**:`gh api -X PUT repos/Albertsun6/aisep/branches/main/protection`(把 `enforce_admins` 设 true)。

---

## 6. 十条冻结契约速查

接口级约定,改了就全链断裂或数据不可比——动它们须走 PR + 人审 + 重跑异构评审。全文见 `specs/contracts/`。

| # | 契约 | 一句话 |
|---|---|---|
| 01 | 权威层级 | 唯一强制=GitHub CI;会话内一切不算强制 |
| 02 | 基线与受保护路径 | 基线 tag + feature↔代码声明制 + 受保护路径 |
| 03 | 退出码 | 0/1/2/3;受控路径只产生这四个;fails-closed 用会失败的测试钉死 |
| 04 | 计费边界 | `aiforge` CLI 任何路径永不调模型 |
| 05 | 异构 fail-closed | judge 缺真异构(cursor/codex)→ 转人审,绝不作者模型自审;记评审者身份 |
| 06 | receipt 链 | 每门禁落 receipt;CI 用 `gate-spec --check` 验冻结(不洗白篡改) |
| 07 | `--ack-human` 双层 | 本地 ack 仅审计;权威放行=人类账号 PR approval;CI 不消费 ack |
| 08 | specs 布局 + 双宿主 | 目录契约;agent file-in/file-out、JSON 落 `outputs/`、定序逻辑不进 prompt |
| 09 | 数据与安全 | schema_version / hash 规范化 / secret 不入账 / CI 最小权限 / break-glass |
| 10 | 模型配置 | model/effort 显式配置;被拒参数 fail-closed;记实际模型;厂商事实进 `vendor-facts.md` |

---

## 7. 角色 agent 与阶段 skill

| 资产 | 位置 | 状态 |
|---|---|---|
| `analyst`(需求→spec) | `.claude/agents/analyst.md` | 已物化 |
| 其余角色(architect/developer/reviewer/tester/verifier/judge) | `.claude/agents/` | **按需物化**(上限 7,不是验收指标) |
| `sdlc-requirements`(需求阶段) | `.claude/skills/sdlc-requirements/` | 已建 |
| `sdlc-gate`(门禁说明书) | `.claude/skills/sdlc-gate/` | 已建 |

**双宿主规范**(契约 08):任何角色 agent 必须 file-in/file-out、结构化 JSON 落 `specs/<id>/outputs/<role>.json`、**定序逻辑不写进 prompt**(下一步走哪由人/skill 决定)。规范冻结,提示词文案随用随改。

---

## 8. 配置在哪 / 怎么撤

### 配置位置(全在 repo 内,删除即回退)

| 配置 | 文件 |
|---|---|
| 会话模型/算力/护栏 | `.claude/settings.json`(`model=claude-fable-5`、`effortLevel=xhigh`、deny 清单、Stop 提示 hook) |
| 角色/技能/宪法导入 | `.claude/agents/`、`.claude/skills/sdlc-*`、`CLAUDE.md` |
| 本地钩子 | `.githooks/pre-commit` |
| CI 强制层 | `.github/workflows/gates.yml`、`.github/CODEOWNERS` |
| 契约 | `specs/contracts/`(10 条 + `vendor-facts.md`) |
| 成本台账 | `eval/cost-log.md`(双口径 schema,**/cost 数值留空——本人决定不补**) |

### 怎么撤

- **解本地钩子**:`git config --unset core.hooksPath`(回到无 pre-commit)。
- **关 CI 强制**:GitHub repo → Settings → Branches → 删 `main` 的 protection rule。
- **整体回退**:harness 资产都在上表路径,删除即回退;基线 `git checkout archive/pre-harness` 是 harness 之前的状态。

### 0 号地雷(已处置)

用户级 `~/.claude/settings.json` 的 `defaultMode=bypassPermissions` 保持现状(你的裁决);本 repo 已用项目级 `.claude/settings.json`(`acceptEdits`)覆盖。真锁定(managed-settings/MDM)是强制版事项,本 STEP 0 不建。

---

## 9. 故障排查

| 症状 | 原因 | 解 |
|---|---|---|
| `No module named aiforge` | 没带 `PYTHONPATH=src`(source-rooted,非 pip 安装) | 命令前加 `PYTHONPATH=src`,或用 `make` 目标 |
| 退出码 **3**,提示 ruff 不可用 | lint fails-closed,缺开发依赖 | `make install-dev`(装 ruff) |
| 退出码 **1**,"src/tests 改动必须声明 feature" | 改了代码但没说属于哪个 feature | `gate-commit --feature <id>` 或 `AIFORGE_FEATURE=<id> git commit` |
| 退出码 **1**,"receipt 过期/伪造" | 改了 spec 却没重跑 gate-spec | 重跑 `gate-spec specs/<id>/spec.md` 后重新 `git add` |
| 退出码 **2** 卡住提交 | 静态扫描命中(eval/exec/os.system 等),转人审 | 确认是误报或有补偿控制 → tty 里 `gate-commit --ack-human`(仅本地);权威放行走 PR approval |
| CI `gates` 红但本地绿 | 环境差异(如 verifier 无真隔离后端在 Linux fail-closed) | 看 CI 日志的具体步骤;测试已做环境感知,真红是真问题 |
| pre-commit 没生效 | 没启用 hooksPath | `make hooks` |

---

## 10. 设计依据与延伸阅读

- **怎么用** → 本手册。
- **为什么这么设计** → `docs/decisions/AISEP-ClaudeCode架构决策文档.md`(ADR-001~014)。
- **实施怎么落的** → `docs/plans/AISEP-ClaudeCode有头先行实施方案-v2.md` + `specs/contracts/`。
- **前期怎么论证的** → `docs/research/`(harness 可行性、健康度报告)。
- **异构评审留痕** → `specs/contracts/REVIEW-2026-06-11*.md`(契约包 + M1 代码评审,自报 GPT-5.5)。
- **文档总导航** → `docs/README.md`。

### 当前边界(刻意不做的)

- **Agent SDK driver**(无人值守的进程外编排):四级升级阶梯第一级=人肉定序;硬触发(无人值守/跨会话权威/多操作者)未命中前**刻意不建**(Fable 5"少建设")。
- **强制版**(managed-settings/MDM/OTel/HMAC 审计):交付对象要求真锁时才启动。
- **成本基线**:已决定不补 `/cost` 数值。
- **P6 外部集成**(ERP/GitHub MCP/部署):需外部资源,不在 STEP 0 内。
