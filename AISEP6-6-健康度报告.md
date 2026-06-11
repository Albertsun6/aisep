# AISEP6-6 — 项目健康度报告

> 评估日期：2026-06-08 ｜ 方法：/project-health（L0 治理 · L1 门禁 · L2 趋势 · L3 AI+异构语义）
> 目标仓库：/Users/yongqian/Desktop/AISEP6-6 ｜ 技术栈：Python ｜ 评估窗口：近 12 月
> 探针：6 ran_ok / 0 tool_failed / 2 skipped（import-linter、pip-audit）｜ L3 异构终审 verdict：**Refine（6 点，已采纳 5 + 1 partial）**

## 健康画像（分层，非单一分数）

```
L0 治理   ●●●○○   CI + 无 secret ✓；但声明 MIT 却无 LICENSE 文件、缺 SECURITY.md / 锁文件、bus factor=1
L1 门禁   核心 ●●●●○ / 全树 ●●●○○   核心 src/aiforge 干净（最差 gates.py CC=20）；死代码/重复/超高复杂度几乎全在【未跟踪】研究文件夹
L2 债震中 ●●●○○   债集中在核心活跃区，头号 = src/aiforge/quality/gates.py（rev5 ∩ CC20）
L3 软维度 ●●●○○   分层清晰，但有 base↔governance 既有循环 import（靠延迟导入绕开）；研究文件夹污染探针基线  [异构 Refine → 已采纳]
```

> **一句话**：核心 `src/aiforge/` 是一个分层清晰、积极复盘（有 HARDENING.md + 异构评审痕迹）的健康代码库；主要健康问题不在核心代码质量，而在 **① 一个未跟踪/未忽略的巨型研究文件夹污染了探针基线、② 一处已知未修的循环 import、③ 发布治理基础件缺失（LICENSE/SECURITY/锁文件）**。

## 维度评分（对照 rubric/thresholds）

| 维度 | 分 | 依据（probes.json 数字 / file:line / 异构 verdict） |
|---|---|---|
| **D0 仓库治理** | **3/5** | `license=false`（但 `pyproject.toml:11` 声明 MIT — 不一致）、`security_policy=false`、`dependency_lockfile=false`（仅 manifest）、`active_authors=1`（bus factor 风险）、`branch_protection=unknown`；**亮点** `ci_present=true`、`committed_secret_risk=false`、`debt_markers=0` |
| **D1 架构及框架合理性** | **3/5** | 核心分层清晰（context/eval/governance/orchestration/quality/runtime 六职责子包；runtime/base.py 抽象 + local/isolation/openhands 多实现）；**但** `HARDENING.md:44` 自承 `base→governance→…→base` 既有循环 import，靠 `src/aiforge/orchestration/__init__.py` 的 PEP562 延迟导入绕开；无架构 fitness function 在 CI 守。[异构 Refine→accept] |
| **D2 代码规范，代码精简** | **核心 4/5** | radon：核心 src 最差仅 `src/aiforge/quality/gates.py:50 _spec_has_acceptance` CC=20（单个离群）；CC≥10 共 55 个函数但**几乎全在未跟踪研究文件夹**（parse_dsl CC=45 等）。核心代码复杂度达标 |
| **D3 目录结构合理性** | **3/5** | 核心 `src/` 优秀（pyproject 只打包 src）；**但**根目录有【未跟踪且未 gitignore】的 `AI工程化…调研/`，`挑战评估/fix_proposal/improved_developer.py` 是 `src/aiforge/orchestration/codegen.py` 的实验副本（21 行重复）。[异构 Refine→accept：是工作树/探针基线污染，非发布包污染] |
| **D4 冗余文件，无用文件** | **核心 4/5** | vulture 死代码=1（在研究文件夹 `fix_proposal/test_improved_developer.py:28` unused import）；jscpd 重复=4.07%（≤10% 可接受，且主要是 `研究文件夹 ↔ src` 的实验副本）。核心近零死代码 |
| **D5 内容隔离，解耦** | **3/5** | 无明显上帝模块；**但**存在 `base↔governance` 循环依赖（`HARDENING.md:44` + `orchestration/__init__.py` 延迟导入证实）= 分层边界被破的真实耦合债；instability 未测（import-linter skip）。[异构 Refine→accept] |
| **D6 技术架构合理性** | **4/5** | L2 hotspots **集中可控**：头号 `src/aiforge/quality/gates.py`（score_norm 1.0，rev5×loc172）= hotspot ∩ 复杂度离群（含 CC20 函数）；其后 test_quality / eval/harness / orchestration/agents / llm / governance/permissions 均核心活跃区。债集中、震中明确 |
| **D7 历史评审的经验教训** | **4/5** | 留档与复盘优秀：`HARDENING.md` 记录 6 个 fix 的 review/merge map（含 `:20` C3「循环自证」撤销、`:31/:44` 异构评审判定），commit `0b7050e`/`c0e21ad` 带 cursor verdict；**但**教训**未固化成可执行规则**——`AGENTS.md:6-8` 定义了子包职责却无 import-linter，CI（`ci.yml`）只有 lint/test/eval |

> 评分口径：核心维度（D2/D4）按**核心 src（tracked + packaged）**打分并显式标注，因 radon/scc/jscpd/vulture 扫了整个工作树（含未跟踪研究文件夹），git 探针（hotspots/governance）只看 tracked。

## L2 技术债震中（churn × complexity hotspots，纯 git+python）

| # | 文件 | revisions | loc | score_norm | 交叉判读 |
|---|---|---|---|---|---|
| 1 | `src/aiforge/quality/gates.py` | 5 | 172 | **1.00** | **头号**：改得最勤的文件 ∩ 含 CC=20 离群函数 `_spec_has_acceptance` → 最高 ROI 重构点 |
| 2 | `tests/test_quality.py` | 5 | 98 | 0.57 | 测试随 gates 高频改，正常 |
| 3 | `src/aiforge/eval/harness.py` | 5 | 67 | 0.39 | 活跃迭代，复杂度不高 |
| 4 | `src/aiforge/orchestration/agents.py` | 2 | 166 | 0.39 | 大文件但低频改，未必债 |
| 5 | `src/aiforge/llm.py` | 4 | 73 | 0.34 | 活跃，小文件 |
| 6 | `src/aiforge/governance/permissions.py` | 3 | 87 | 0.30 | 安全敏感，关注 |

> complexity = LOC 代理（Tornhill 经典）；装了 radon/scc 后可用真圈复杂度复核（已采集，见 L1）。

## L3 软维度评审（AI + cursor-agent 异构终审）

异构终审（GPT-5.5）**实读了仓库文件**，补出主 agent 缺的证据，6 点修订已采纳 5 + 1 partial：

| 异构意见 | 立场 | 处理 |
|---|---|---|
| ① 循环 import 应进 D5 正文，非 caveat（`HARDENING.md:44`、`orchestration/__init__.py` 延迟导入） | **accept** | 核实属实 → D1/D5 降到 3，写入正文 |
| ② "实验代码污染主仓"应精确为"未跟踪工作树污染探针基线"（`pyproject.toml:20` 只打包 src、`.gitignore` 未忽略） | **accept** | 核实属实 → D3 措辞精确化 |
| ③ D7 "git log 痕迹"需附 commit hash | **accept** | 已引 `HARDENING.md` 行号 + `0b7050e`/`c0e21ad` |
| ④ 优先级重排：先清研究文件夹+治理红线，再拆 gates.py | **accept** | 已采纳（见下方"最该先动"） |
| ⑤ 固化不止 import-linter（部分教训靠测试/eval/ADR） | **accept** | 固化清单已区分"可机器检查 / 仅留档" |
| ⑥ 治理缺口应升为"红线" | **partial** | 接受**要突出**+ MIT/LICENSE 不一致是实锤；但按 fail-closed rubric，"红线（requires_human_confirm）"专指 committed secret / 依赖漏洞，治理缺口是**高优先黄线**——不混淆概念，故 partial |

> 所有异构 file:line 经主 agent 独立核实属实（HARDENING.md:44 循环 import / orchestration `__getattr__` 延迟导入 / pyproject MIT 无 LICENSE / CI 无 import-linter / 研究文件夹未 gitignore），未盲信异构方。

## 最该先动的 3+1 件事（异构重排后，按 ROI）

1. **处理研究文件夹** `AI工程化…调研/` — `.gitignore` 加 `AI工程化*调研/` 或移出主仓，**重跑 probes 得可信基线**。它制造了几乎所有 L1 噪声（CC=45 等 + 死代码 + 重复），且未跟踪未忽略。固化：gitignore（可机器检查）。
2. **补 L0 发布治理** — 加 `LICENSE`（MIT，消除 `pyproject.toml:11` 声明与缺文件的不一致）、`SECURITY.md`、锁文件（`pip-compile`/`uv.lock`）、`CODEOWNERS`（应对 bus factor=1）；确认默认分支保护。固化：文件存在性 + 锁文件 CI gate（可机器检查）。
3. **拆 `src/aiforge/quality/gates.py` 的 `_spec_has_acceptance`**（CC=20，top hotspot ∩ 最复杂的核心函数）+ 补测试。固化：radon/ruff complexity gate（新代码 CC<15 即 fail，baseline 容忍存量）。
4. **固化分层边界** — 写 import-linter contracts（对照 `AGENTS.md:6-8` 子包职责 + 禁 `base→governance` 环）进 CI，把那处"已知未修循环 import"变成回归门禁；非机检教训（"无可信 LLM 转人审 / 独立 oracle"）写 ADR（`docs/adr/`）+ eval 场景。

## 固化清单（教训 → 自执行规则，invariant 4）

| 发现 | 固化动作 | 可机器检查? |
|---|---|---|
| `base↔governance` 循环 import | import-linter contracts（AGENTS.md 子包职责 + 禁该环）→ CI | ✅ 是 |
| 未跟踪研究文件夹污染基线 | `.gitignore` 加 `AI工程化*调研/`（或移出仓库） | ✅ 是 |
| 声明 MIT 却无 LICENSE 文件 | 加 `LICENSE`（MIT） | ✅ 是（存在性） |
| 缺 SECURITY.md / 锁文件 | 补 `SECURITY.md`；`pip-compile`/`uv.lock` + CI 校验锁文件 | ✅ 是 |
| bus factor=1 | `CODEOWNERS` + 知识分享 | ⚠️ 部分 |
| `gates.py:_spec_has_acceptance` CC=20 | radon/ruff complexity gate（新代码 CC<15） | ✅ 是 |
| HARDENING「无可信 LLM 转人审 / 独立 oracle」类教训 | 单元测试 / eval 场景 + ADR | ❌ 仅留档+测试 |

## 覆盖边界（诚实声明）

- **自动覆盖**：L0 治理（含 secret 扫描）、L2 hotspots、L1 死代码(vulture)/复杂度(radon+scc)/重复(jscpd)
- **半自动 + 异构**：L3 架构/目录/解耦/历史（4 软维度，经 cursor-agent 异构终审）
- **未覆盖（工具 skip）**：
  - `import-linter`（未装）→ **循环依赖/instability 未经工具自动验证**；本报告的循环 import 结论来自 `HARDENING.md` + 读码，非工具 → 安装：`pipx install import-linter` 后写 `.importlinter` contracts
  - `pip-audit`（未装）→ **依赖漏洞未自动检查** → 安装：`pipx install pip-audit`（或 `osv-scanner`）
- **数据口径**：radon/scc/jscpd/vulture 扫了整个工作树（含未跟踪研究文件夹，已显式区分核心 vs 全树）；hotspots/governance 只看 git tracked。

## Phase 0 成功标准自验

| 必答问题 | 结论 |
|---|---|
| ① 头号技术债 hotspot? | ✅ `src/aiforge/quality/gates.py`（rev5 ∩ CC20） |
| ② committed secret / license / 分支保护? | ✅ 无 secret；**无 LICENSE 文件（却声明 MIT）**；分支保护 unknown（无 GH 远端访问） |
| ③ 死代码/重复/复杂度超阈值? | ✅ 核心达标；超阈值项集中在未跟踪研究文件夹；重复 4.07%（可接受） |
| ④ 循环依赖/分层违规? | ✅ 有 `base↔governance` 循环 import（HARDENING+读码确认；import-linter 未装故未工具验证） |
| ⑤ 目录结构/解耦合理? | ✅ 核心好；研究文件夹污染基线（L3+异构） |
| ⑥ 历史教训这轮还在守? | ✅ 留档优秀（HARDENING.md），但**未固化成可执行规则**（缺口） |

## 评估 Metadata

- **探针**：ran_ok 6（churn_hotspots/governance/vulture/scc/radon/jscpd）/ tool_failed 0 / skipped 2（import-linter、pip-audit）｜ manifest：`/tmp/ph-assess/probes.json`
- **L3 异构终审 verdict**：Refine（6 点）→ 主 agent 判断矩阵 5 accept + 1 partial → **收敛，无需人类裁决**
- **异构方准确性**：6 条 file:line 证据经主 agent 独立核实，全部属实（未盲信）
- **人类介入**：无
- **降级**：import-linter / pip-audit 未装（已标覆盖边界 + 安装指令）；非 fail-closed，主流程未阻断

---

## 改进落地复测（2026-06-08 同日，按本报告执行）

> 原则：每条改动可执行验证（make test/arch/eval 绿 + 重跑探针实测 before→after），不靠"我觉得对了"。

| 改动 | 文件 | before → after（实测） |
|---|---|---|
| 拆 `_spec_has_acceptance`（CC=20） | `src/aiforge/quality/gates.py` | 该函数 **CC 20→6**（拆 3 个具名子谓词 `_has_gherkin/_has_ears/_has_user_story`）；**33 tests 仍全绿**，行为不变 |
| gitignore 研究文件夹 + `.project-health` | `.gitignore` | jscpd 重复率 **4.07%→0.0%**；git 探针/jscpd/scc 均已排除（尊重 gitignore） |
| 补 LICENSE（MIT，消除 pyproject 声明/无文件不一致） | `LICENSE` | 治理 `license` **false→true** |
| 补 SECURITY.md | `SECURITY.md` | 治理 `security_policy` **false→true** |
| 架构 fitness function（固化分层，防 base↔governance 环恶化） | `.importlinter` + `Makefile`(`make arch`) + `.github/workflows/ci.yml` + `requirements-dev.txt` + `AGENTS.md` | **`make arch` = 2 契约 kept / 0 broken**；architecture 探针 skip→present；CI 新增门禁步骤 |

**两条按工程判断主动改判（push back，非 cargo-cult）**：
- **锁文件**：项目刻意零运行时依赖（`pyproject.toml dependencies=[]` + `requirements.txt` 仅注释）→ 给零依赖项目加锁文件是过度，**N/A 而非缺陷**。
- **CODEOWNERS / 分支保护**：AISEP6-6 **无 git 远端**（纯本地仓）→ 两者都是 GitHub 特性，当前加了是摆设；推到 GitHub 后再补。

**仍存的诚实差距**：
- radon / vulture **不尊重 gitignore**，仍扫磁盘上的研究文件夹 → `parse_dsl CC=45` / vulture 死代码=1 仍来自它（**但 src/ 核心干净**：CC≥10 仅 9 个、最高 17）。彻底清需把研究文件夹移出仓库，或增强 /project-health 让 radon/vulture 也尊重 gitignore（skill 层改进，非本项目）。
- `make arch` 的 import-linter 契约目前是 forbidden（锁反向边）；已知 base↔governance 历史循环（`HARDENING.md:44`）未"修复"，但已被 fitness function **框住不再恶化**（符合 thresholds 的 baseline 容忍存量、禁新增）。
- 未触碰会话前既有的未提交改动（`governance/review.py` / `orchestration/__init__.py` / `runtime/base.py`）。

**复测命令（可复现）**：`make test`（33 OK）· `make arch`（2 kept）· `make eval`（四指标正常）· `bash ~/.claude/skills/project-health/probes/run-probes.sh --repo .`

> 注：本报告与 survey 三件套实际位于 `AI工程化开发企业软件系统方案-调研/` 子文件夹；该文件夹已被新加的 `.gitignore` 覆盖（不影响代码改进——代码改动均在仓库根且已被 git 追踪）。
