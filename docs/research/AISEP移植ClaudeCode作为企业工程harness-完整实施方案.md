# AISEP × Claude Code 企业工程 Harness — 完整可落地实施方案（HYBRID 薄外层监督者）

> 本方案是落地方案,不重新论证可行性。可行性结论与对抗实测见仓库根 `AISEP移植ClaudeCode...完整报告.md`,本方案严格遵从其 §1–§9 已验证结论,并把 §5/§6 的对抗探针**折叠进每个组件的设计与回归测试**(不是附在末尾)。诚实标注原则贯穿全文:**只有 bare-deny(整工具移除)+ OS Bash 沙箱 + 进程外权威**三类是 fail-closed;凡依赖 *agent 可写状态 / 正则匹配 Bash / CLAUDE.md 顺序 / CC subagent 当评审团* 的,一律 fail-open,只能当**早警告(advisory)**,真正强制必须落到外层。文中凡 advisory-only / only-fail-closed-under-locked-config 处均显式标注。

---

## 0. 方案总览

**在建什么。** 把 aiforge 的「7 层工程纪律」重构成一个**叠在 Claude Code 之上的企业纪律 HARNESS**:CC 的 model-driven 循环(其工具/subagents/hooks/skills/MCP/Agent-SDK)作为**每个 SDLC 阶段内部的执行引擎**;aiforge 那套可移植的方法论内核(`quality/gates.py` 的门禁逻辑、`orchestration/state.py` 的 PipelineState、`governance/audit.py` 的审计 schema、`config.py` 的治理阈值、`judge.py` 的内容判定)保持 **CC-free**、原样复用,放在 `src/aiforge/`;新增 `src/aiforge_harness/` 适配层依赖内核但**内核绝不反依赖它**,这条单向边由 import-linter 可执行契约硬化。权威(状态 SSOT / 审批密钥 / 审计 HMAC 链 / 异构 runner)**全部搬到模型不可写的进程外**。

**HYBRID 全景(内引擎 + 外薄权威层):**

```
            ┌─────────────────── 外层薄权威(进程外, 模型不可写/不可影响) ──────────────────┐
            │  Agent-SDK 外监督者(持 PipelineState SSOT) · 进程外 ApprovalAuthority(MCP)   │
            │  外部 HMAC 审计 sink + 外部 anchor · 异构 runner(cursor/codex, 独立 uid)      │
            │  受管 OTel 强制导出(env 锁) · 服务端 git pre-commit/required-CI(全量 diff)    │
            └───────────────────────────────────┬──────────────────────────────────────────┘
                                                 │ 每阶段一次 query() · 阶段间跑门禁/取证据
            ┌────────────────────────────────────▼──────────────────────────────────────────┐
            │  CC model-driven 循环 = 每阶段内部执行引擎(tools/subagents/hooks/skills/MCP)    │
            │  受 OS 沙箱(Seatbelt/bwrap, allowWrite=worktree) + 受管 settings(bare-deny) 约束 │
            └────────────────────────────────────────────────────────────────────────────────┘
```

**唯一指导铁律。** *一个控制是不是 fail-closed,只看它是否落在「模型不可写/不可影响」的层。* 三类真 fail-closed:① bare-deny(整工具从 allowedTools 移除)与受管 permission/hook 锁;② OS Bash 沙箱(写面 EPERM、不可逃逸、env 擦除);③ 进程外权威(SSOT/密钥/审计/runner 在模型够不到的进程)。**其余皆 advisory**。任何"看起来锁了"的 settings 文本,只有当**受管层(Tier A)禁止下层放松它**时才真正生效。

**5 组件 → 各自令其 fail-closed 的不变量(一行表):**

| # | 组件 | 它令其 fail-closed 的不变量 | 真 fail-closed 的依据 |
|---|------|---------------------------|---------------------|
| 1 | 仓库布局 + CC-free 内核抽取(含 3 地雷修复) | 方法论内核不会被静默重平台化到 Claude;单向依赖边 | import-linter forbidden 契约 + ast 边界测试(零依赖常跑) |
| 2 | Phase 0 配置锁定 + 对抗探针 | model-driven Edit+Bash 无法越 worktree 写 / 不可不沙箱跑 / 不能以 `--dangerously-skip-permissions` 启动 | 受管 settings(Tier A,需 root/MDM)+ OS 沙箱(Tier B,内核 EPERM) |
| 3 | Phase 1 外部审计(P8 黄红分层) | 每个动作落入模型关不掉/删不掉/改不了的外部记录通道 | 受管 OTel env 锁(事件级黄)+ 进程外 HMAC sink+外部 anchor(内容级红) |
| 4 | Phase 2 反应式 hook + **服务端 git/CI 权威 backstop** | 全量 diff 爆炸半径 + 门禁重跑于「磁盘产物+CI 证据」,绝不读 worktree state.json | 服务端 git pre-commit/required-CI(分支区间 diff,模型够不到) |
| 5 | Phase 3+4 外监督者 + 进程外审批 + 异构验证 | 确定性阶段序 + 真安全停机 + actor 绑定 ticket + ≥2 异构非 Claude 厂商,缺则转 HITL | Agent-SDK 外环持 SSOT + 进程外 ApprovalAuthority(独立 uid)+ 进程外 attest |

---

## 1. 目标仓库布局

**不做物理重命名。** 现有 `aiforge` 包**已经**整体 CC-free(`pyproject` `dependencies=[]`、纯 stdlib——已核实)。把它物理改名为 `aiforge_core` 会一次性改写 5 个测试文件 + 每个 src 模块的 import 行,33 测试会在迁移中途变红(违反"每步绿"与外科手术原则 ③)。因此边界用**可执行契约**实现,而非物理搬动:

```
src/
  aiforge/                      # ← 可移植方法论内核(已 CC-free, 纯 stdlib, 零依赖, 不动)
    config.py                   #   GovernanceConfig 单一调参口(新增 compact_trigger_tokens)
    orchestration/state.py      #   PipelineState / Artifact / FileChange / Status(可移植状态模型)
    orchestration/graph.py      #   Supervisor / resume(BLOCKED 不可绕过语义已存在)
    quality/gates.py            #   SpecGate/PRGate/TraceabilityGate/.../QualityGateChain(门禁逻辑)
    quality/judge.py            #   StaticRiskScanner + AgentAsJudge(地雷#1 修这里)
    governance/audit.py         #   AuditEvent + AuditTrail(审计 schema, 外部 sink 镜像它)
    governance/audit_chain.py   #   新增: CC-free HMAC 链(tamper-evidence 逻辑, 纯 stdlib)
    governance/permissions.py   #   HumanApprovalTicket/ApprovalAuthority(HMAC ticket 逻辑, 外层复用)
    context/memory.py           #   地雷#3 修这里(默认从 config 取, 不钉死厂商数字)
    runtime/openhands.py        #   地雷#2 修这里(selfcheck 真往返 + fail-closed)
    ...其余不动...
  aiforge_harness/              # ← 新增: CC 耦合适配层(依赖 aiforge.*, 内核绝不反依赖)
    settings/                   #   受管 settings + 沙箱 profile 生成
    hooks/                      #   PreToolUse/PostToolUse/Stop 适配(import 内核门禁)
    server/                     #   服务端 git pre-commit/CI backstop(blast_radius, verify_gates)
    audit_sink/                 #   OTel 转发 + 外部 HMAC sink client + PostToolUse 审计 hook
    supervisor/                 #   Agent-SDK 薄外环(包内核 graph 语义)
    approval/                   #   进程外 ApprovalAuthority MCP server
    hetero/                     #   cursor/codex shell-out + 厂商 attestation
harness_runtime/                # ← 进程外运行物(不在任何 allowWrite 路径; 部署时独立 uid)
  managed-settings/             #   /Library/Application Support/ClaudeCode/ 的源副本(root 安装)
  probes/                       #   对抗探针(双向: locked 拦住 / bad 放行)
  bin/                          #   run-cursor-agent.sh 等(模型不可写)
```

### 1.1 让 CC-free 边界可执行(替换"注释声明")

**修正(对抗发现:`.importlinter` 实际是 `root_package = aiforge` 单数,`pyproject` dev 只有 `ruff`)。** STEP 1 的真实编辑——把单数键改成复数并新增 3 契约:

```ini
# .importlinter —— 现有 2 契约(foundation-no-upward / governance-below-runtime)逐字保留
[importlinter]
root_packages =
    aiforge
    aiforge_harness
include_external_packages = True        # ← 对抗发现#4必需: 否则外部 forbidden(claude_agent_sdk)直接报配置错而非 KEPT

[importlinter:contract:core-never-imports-harness]
name = 核心 aiforge.* 绝不反依赖适配层 aiforge_harness.*
type = forbidden
source_modules = aiforge
forbidden_modules = aiforge_harness

[importlinter:contract:core-is-cc-free]
name = 核心 aiforge.* 不得 import Claude Code SDK / Anthropic SDK(可执行 CC-free 边界)
type = forbidden
source_modules = aiforge
forbidden_modules =
    claude_agent_sdk
    anthropic
```

> **诚实标注边界(折叠对抗发现 #4):** import-linter + ast 扫描只证明**词法上无 CC SDK import**,**不**证明"语义上没被重平台化到 Claude"。语义污染(`importlib.import_module(os.environ[...])` 动态拉、把 `trusted_vendor='claude'` 当可信)逃过 lint。所以**额外加语义回归**(见 1.3 与组件 1):内核默认 `needs_human`,且任何 in-process 构造在无外层 attestation token 时**永不**翻成可信。`pyproject` 新增 `harness` 可选 extra,使 CC SDK 是**可选**依赖——`pip install aiforge` 连 SDK 都不可 import,残留 P9 隔离是结构性的。

```toml
# pyproject.toml(真实差异: 当前 dev=['ruff>=0.5.0'], 无 import-linter)
[project.optional-dependencies]
dev = ["ruff>=0.5.0", "import-linter>=2.0"]   # ← 新增 import-linter(原仅在 requirements-dev.txt)
harness = ["claude-agent-sdk>=0.1"]            # ← CC SDK 仅作可选 extra; 普通安装永不引入
```

### 1.2 三颗地雷在 STEP 0 修掉(33 测试每步绿)

| 地雷 | 位置 | 现状(已核实) | 修法 | 33 测试影响 |
|------|------|-------------|------|------------|
| #1 信任后门 | `judge.py:81` | `trust_llm = (not isinstance(llm, MockLLM)) if trust_llm is None else trust_llm` | 默认 **UNTRUSTED**;信任需显式 `trust_llm=True`(测试用),生产信任须**外层 attestation token**绑定非 Claude 厂商 | test_quality.py:93/96/98 用 `StubReviewerLLM` 断言"可信"——**迁移为显式 `trust_llm=True`**(不是伪 vendor 串) |
| #3 钉死厂商数字 | `memory.py:24` | `compact_trigger_tokens: int = 50_000  # 与 Anthropic compact 一致` | 默认从 `GovernanceConfig.compact_trigger_tokens` 取;`=50` 显式 kwarg 不变 | test_context.py:48 传 `=50` 仍工作;:50 用默认(同值)→ 绿 |
| #2 NotImplementedError 当验收 | `openhands.py:54/59` | stub 即"完成" | 保留 NotImplementedError 作**未配置 fail-closed 路径**;新增 `selfcheck()`:有 key 时真往返,否则 SafeHalt | 新增 opt-in 测试(无 cred 跳过);现有 test_eval_and_runtime 不受影响 |

### 1.3 地雷 #1 的关键修正(折叠对抗发现:trusted_vendor 字符串是新剧场)

报告 §5 X-judge 明言:*真信任边界 = runner+keys 在模型完全不可写/不可影响的进程里;脱离这个外部边界,单靠 model-id challenge / vendor 串的 attestation 仍会被能改 runner/env 的模型演成新剧场。* 因此**内核的 `judge.py` 不接受自报 vendor 串当信任凭据**。`AgentAsJudge` 接受一个**不透明 attestation 对象**(由进程外 `aiforge_harness/hetero` 在真跑过 cursor/codex 并验过 ≥2 厂商后铸造、用内核不持有的密钥签名);内核**只验签**,验不过或缺 token → `NEEDS_HUMAN`。测试里用 `trust_llm=True` 显式 override 来单测分支逻辑,**绝不**让 `trusted_vendor='...non-claude...'` 成为一条"绿=可信"的回归。

```python
# src/aiforge/quality/judge.py —— 地雷#1 修复(默认不信任; 信任绑定到外层签名 token)
class AgentAsJudge:
    def __init__(self, llm=None, config=DEFAULT_GOVERNANCE,
                 trust_llm: Optional[bool] = None,
                 attestation: Optional["Attestation"] = None,
                 attest_verify_key: Optional[bytes] = None) -> None:
        self.llm = llm or MockLLM()
        self.config = config
        self.scanner = StaticRiskScanner()
        if trust_llm is not None:
            self.trust_llm = bool(trust_llm)            # 仅测试用的显式 override
        elif attestation is not None and attest_verify_key is not None:
            # 信任仅当: 外层铸造的签名 token 验签通过, 且其声明的厂商非 Claude/Anthropic
            self.trust_llm = (
                attestation.verify(attest_verify_key)
                and attestation.vendor not in (None, "claude", "anthropic")
            )
        else:
            self.trust_llm = False                       # 默认 UNTRUSTED(地雷#1 核心)
    # review() 体不变: `if not self.trust_llm: return NEEDS_HUMAN` 已强制保守路径
```

**验收(可执行):**
```bash
# 默认不信任 + Claude vendor 永不翻信任 + 显式 override 才信任
PYTHONPATH=src python3 -c "
from aiforge.quality.judge import AgentAsJudge
from aiforge.llm import StubReviewerLLM
assert AgentAsJudge(llm=StubReviewerLLM()).review('clean', task_type='feature').decision=='needs_human'
assert AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True).review('clean', task_type='feature').approved
print('OK')"
# 内核词法 CC-free
PYTHONPATH=src python3 -m unittest tests.test_harness_boundary.TestCoreIsCCFree
# 全 33 + 新增绿
PYTHONPATH=src python3 -m unittest discover -s tests
```

---

## 2. 组件 1 — 仓库布局 + CC-free 内核 + 3 地雷修复

**Goal / 不变量:** 方法论内核不可被静默重平台化到 Claude;`lint-imports` 是证明它的回归门。

**Repo artifacts:** `src/aiforge/quality/judge.py`(改)、`config.py`(改)、`context/memory.py`(改)、`runtime/openhands.py`(改)、`.importlinter`(改 root_packages+3 契约+include_external_packages)、`pyproject.toml`(改)、`src/aiforge_harness/__init__.py`(新)、`src/aiforge_harness/hooks/spec_gate_hook.py`(新,演示依赖方向)、`tests/test_quality.py`(改 5 站点)、`src/aiforge/eval/harness.py`(改 judge 构造)、`tests/test_harness_boundary.py`(新,边界 fitness)、`tests/test_judge_default_untrusted.py`(新)。

**Design.** 见 §1。依赖箭头永远 harness→core;契约 A 禁 core→harness,契约 B 禁 core→{claude_agent_sdk, anthropic}。`spec_gate_hook.py` 是第一个具体适配器,演示方向(下方骨架),且**折叠对抗发现**:它**不**从 CC 的 `event` 重建权威状态(那是模型可控的),而是向外层监督者 IPC 取 SSOT,取不到则 deny(fail-closed),并**显式标注自身只是早警告**。

```python
# src/aiforge_harness/hooks/spec_gate_hook.py —— PreToolUse 适配(早警告; 真权威在服务端)
"""依赖方向 aiforge_harness -> aiforge(import-linter 强制)。内核不知道本文件存在。
本 hook 是 EARLY-WARNING: 它 deny 仅对识别得到的文件工具有效; 真 P1/P3 backstop 在服务端 git/CI。"""
import json, sys
from aiforge.quality.gates import _spec_has_acceptance      # 复用内核, 不重写
from aiforge.quality.judge import StaticRiskScanner

def _fetch_state_from_supervisor():
    """权威 PipelineState 来自外层监督者进程(IPC/loopback), 不从 event 取。
    取不到 -> 返回 None -> 调用方 fail-closed(deny)。绝不信任 event 内嵌状态。"""
    ...  # 见组件 5: 外环持 SSOT

def on_pre_tool_use(event: dict) -> dict:
    tool = event.get("tool_name", "")
    if tool not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        # Bash 等: 本 hook 不做正则拦截(报告 §6 证明那是剧场); 放行 + advisory, 权威在服务端
        return {"permissionDecision": "allow",
                "permissionDecisionReason": "Bash 写面非本 hook 强制; 爆炸半径/spec/血缘在服务端 commit 边界强制"}
    content = event.get("tool_input", {}).get("content") or event.get("tool_input", {}).get("new_string", "")
    hits = StaticRiskScanner().scan(content)
    if any(h["severity"] == "blocker" for h in hits):
        return {"permissionDecision": "deny", "permissionDecisionReason": hits[0]["issue"]}
    return {"permissionDecision": "allow"}
```

```python
# tests/test_harness_boundary.py —— 边界 fitness(零依赖常跑 + lint-imports 门)
import ast, subprocess, unittest, pathlib, importlib.util
CORE = pathlib.Path("src/aiforge"); FORBIDDEN = {"aiforge_harness", "claude_agent_sdk", "anthropic"}

class TestCoreIsCCFree(unittest.TestCase):
    def test_no_core_module_imports_harness_or_cc_sdk(self):
        for py in CORE.rglob("*.py"):
            for n in ast.walk(ast.parse(py.read_text("utf-8"))):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                       ([n.module] if isinstance(n, ast.ImportFrom) and n.module else [])
                for m in mods:
                    self.assertNotIn(m.split(".")[0], FORBIDDEN, f"{py} 禁止 import {m}")

    def test_no_dynamic_cc_reach(self):  # 折叠对抗发现#4: 动态 import 兜底
        for py in CORE.rglob("*.py"):
            for n in ast.walk(ast.parse(py.read_text("utf-8"))):
                if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "import_module":
                    self.assertTrue(n.args and isinstance(n.args[0], ast.Constant),
                                    f"{py}: importlib.import_module 非字面量参数(可能动态拉 CC)")

    @unittest.skipUnless(importlib.util.find_spec("importlinter"), "import-linter 未装")
    def test_lint_imports_passes(self):
        r = subprocess.run(["lint-imports"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
```

**折叠对抗发现 #6/#7(test_quality 迁移别把剧场写成绿):** 把 test_quality.py:93/96/98 迁移成 `AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True)`(显式开发者 override,语义=单测分支逻辑),**不是** `trusted_vendor='stub-non-claude'`。再加负测:任何 vendor 串(含 `'gpt-5.5'`)在缺外层 token 时**不**自动放行。

**OpenHands 地雷 #2 修正(折叠对抗发现):** `_client_roundtrip` 占位**显式 `raise NotImplementedError`**(未来接线不会静默返回 falsy 被误读);新增**无 cred 也跑的契约测试**断言 `selfcheck()` fail-closed 抛 `SafeHaltError`。诚实降级:landmine #2 仅"fail-closed 半边"进常驻 CI,"真往返半边"需 cred、不在常驻 CI——部署接线前手动跑一次。

**Acceptance gates(可执行):**
```bash
PYTHONPATH=src python3 -m unittest discover -s tests                 # ≥33 OK
pip install -r requirements-dev.txt >/dev/null && lint-imports       # exit 0, 契约 KEPT
! grep -n 'Anthropic compact' src/aiforge/context/memory.py          # 无厂商数字
PYTHONPATH=src python3 -c "from aiforge.context.memory import ContextWindow; from aiforge.config import DEFAULT_GOVERNANCE; assert ContextWindow().compact_trigger_tokens==DEFAULT_GOVERNANCE.compact_trigger_tokens; assert ContextWindow(compact_trigger_tokens=50).compact_trigger_tokens==50; print('OK')"
PYTHONPATH=src python3 -c "from aiforge.runtime.openhands import OpenHandsRuntime; from aiforge.governance.permissions import PermissionBroker; from aiforge.runtime.base import SafeHaltError; 
try: OpenHandsRuntime(PermissionBroker(), endpoint=None).selfcheck(); print('FAIL')
except SafeHaltError: print('OK')"
```

---

## 3. 组件 2 — Phase 0 配置锁定 + 对抗探针(双向)

**Goal / 不变量:** 本机 model-driven Edit+Bash 不能 (a) 越 worktree 写 (b) 不沙箱跑 (c) 让 harness 信任一份自证绿的 workspace 状态 (d) 以 `--dangerously-skip-permissions` 启动。**注:** 配置锁定只在 Tier A 真装上后 fail-closed;无真 MDM 时是 *only-fail-closed-under-locked-config*(见风险册)。

**三个强制层(每个控制放在能 fail-closed 的最低层):**

- **Tier A** `/Library/Application Support/ClaudeCode/managed-settings.json`(macOS,需 root/MDM,模型够不到):`disableBypassPermissionsMode='disable'`、`allowManagedHooksOnly`、`allowManagedPermissionRulesOnly`、强制沙箱 env、`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`。**唯一能挡住今天持 `Bash(*)` 模型的层。**
- **Tier B** OS Bash 沙箱(Seatbelt/bwrap),由 Tier A 参数化:`allowWrite` 限 worktree、`allowUnsandboxedCommands=false`。**写面与 Bash 旁路面的真内核边界**——已在本机确认 `sandbox-exec (deny file-write*)` 越界写返回 `Operation not permitted` exit=1。
- **Tier C** 项目 `.claude/settings.json`(提交):`defaultMode='plan'`。**相对 `Bash(*)` 模型是 advisory**,仅当 Tier A 的 `allowManagedPermissionRulesOnly` pin 住才 fail-closed。

**对抗探针双向化(反剧场核心):** 每条探针跑两次——`--profile=bad` 必须**复现报告的 ALLOW**(证明旁路真被执行、机器真脆弱),`--profile=locked` 必须 **BLOCK**。一条"locked 过但 bad 也过"(没锁也拦)的探针被判**非执行/坏探针**而 FAIL。

### 3.1 折叠对抗发现(这些是真洞,必须改对)

| 对抗发现 | 修法(已折叠) |
|---------|------------|
| judge fix 会破 33(`StubReviewerLLM` 非 `MockLLM` 子类,旧码给它 trust=True) | 默认不信任**不**按 MockLLM-与否 keying;33 的可信路径改传 `trust_llm=True`;新测试 import 真符号 `AgentAsJudge`。先跑 `discover -s tests` 真见 ≥35 OK 再宣布绿 |
| p02 把"worktree 外"目标写到 `/private/tmp` 而 profile **允许** `/private/tmp` | 从 `sandbox.sb` **删掉** `(subpath "/private/tmp")`;p02 外部目标改到 `$HOME/__p02_outside`(profile 拒);locked 下真跑 500-loop **在沙箱内**断言每次 EPERM |
| p01 locked "过"是因为没网/没 remote,不是强制;且 worktree 内破坏性写沙箱**允许** | p01-locked 只断言沙箱真强制的:**不能越 worktree 写、不能不沙箱跑**;worktree 内破坏/500-storm/全量 diff 威胁**移到组件 4 服务端 git pre-commit --numstat**(报告明示这只能在那层抓) |
| `sandbox.sb` 有 `(allow file-read*)`,denyRead 秘密(`~/.ssh`)未强制 | 加 `(deny file-read* (subpath "<HOME>/.ssh") (subpath "<HOME>/.aws") (subpath "<HOME>/.config/gh"))` + 双向读秘密探针(bad 读到/locked EPERM) |
| locked reader(`read_evidence.py`/`runner_identity.py`)在 worktree 内 = 模型可改的信任锚 | **把 p03/p04 推迟到组件 3/5**(reader 住在进程外 sink/MCP);Phase 0 若保留,reader 必须在**非 allowWrite 路径**,且加探针证明模型改不动它 |
| CI 声明 bwrap 后端但只有 Seatbelt `sandbox.sb`,探针硬编码 `sandbox-exec` | 要么实装 bwrap wrapper 并按 `$(uname)` 分支(各自双向断言),要么**诚实标 Phase 0 仅 macOS**,探针门走 macOS pre-merge gate |
| bad-profile 依赖 `~/.claude/hooks/git-guardrails.sh`(机器本地、gitignored);`.claude/` 整目录 gitignored | 把基线拷进仓库 `harness_runtime/probes/baseline/git-guardrails.sh`;`.gitignore` 加 `!.claude/settings.json` 反否定,`git check-ignore .claude/settings.json` 须为空 |
| `run_probes.sh` 无 SKIP 出口;p05 在 Linux 无法跑会被误判 | 加 SKIP 态(exit 77),wrapper 记 SKIPPED-with-reason(不算 pass);macOS pre-merge gate **要求** p05 真跑 |
| managed-settings 用了 bundle 里没 grep 到的键(`failIfUnavailable`/`allowManagedPermissionRulesOnly`)+ `${WORKSPACE}` 占位 | 宣布 Phase 0 done **前**逐键对装好的 CC build 可执行验证;不被尊重则显式降级声明;`${WORKSPACE}` 要么确认 CC 展开、要么 `install-managed-settings.sh` 按 worktree 重生成并 gate 在解析后的绝对路径 |

### 3.2 关键骨架

```scheme
; harness_runtime/probes/sandbox.sb —— 删掉 /private/tmp 放行 + 加 denyRead 秘密
(version 1)
(deny default)
(allow process-fork) (allow process-exec)
(allow file-read*)
(deny file-read* (subpath (param "HOME_SSH")) (subpath (param "HOME_AWS")) (subpath (param "HOME_GH")))
(deny file-write*)
(allow file-write* (subpath (param "WORKTREE")))   ; 仅 worktree 可写
(allow file-write* (literal "/dev/null"))
```

```bash
# harness_runtime/probes/p02_write_storm_500.sh —— locked 下真跑 500 且目标在 worktree 外
PROFILE="${1:?bad|locked}"; OUT="$HOME/__p02_outside"; rm -rf "$OUT"; mkdir -p "$OUT"
if [ "$PROFILE" = bad ]; then
  for i in $(seq 1 500); do echo x > "$OUT/out_$i"; done
  [ "$(ls "$OUT" | wc -l | tr -d ' ')" -eq 500 ] && echo 'PASS(bad): 500 落盘, per-Edit hook 盲' || { echo FAIL(bad); exit 1; }
else
  WT="$(git rev-parse --show-toplevel)"; fail=0
  for i in $(seq 1 50); do
    sandbox-exec -D WORKTREE="$WT" -D HOME_SSH="$HOME/.ssh" -D HOME_AWS="$HOME/.aws" -D HOME_GH="$HOME/.config/gh" \
      -f "$(dirname "$0")/sandbox.sb" /bin/sh -c "echo x > $OUT/out_$i" 2>/dev/null && fail=1
  done
  [ "$fail" -eq 0 ] && echo 'PASS(locked): 越 worktree 写全 EPERM' || { echo 'FAIL(locked): 有写穿透'; exit 1; }
fi
```

**Acceptance gates(可执行):**
```bash
# Tier B 真内核边界(本机已确认)
WT=$(git rev-parse --show-toplevel); sandbox-exec -D WORKTREE="$WT" -f harness_runtime/probes/sandbox.sb /bin/sh -c "echo x > $HOME/__outside"; test $? -ne 0
bash harness_runtime/probes/run_probes.sh --profile=bad      # 所有旁路 ALLOW(探针为真)
bash harness_runtime/probes/run_probes.sh --profile=locked   # 所有旁路 BLOCK
PYTHONPATH=src python3 -m unittest discover -s tests          # ≥35 OK(33 + 探针契约 + judge)
# macOS-only: sudo bash harness_runtime/managed-settings/install.sh && claude --dangerously-skip-permissions --print noop; test $? -ne 0
```

---

## 4. 组件 3 — Phase 1 外部审计(P8 黄红分层)

**Goal / 不变量:** 每个模型动作落入它关不掉/删不掉/改不了的外部记录通道。两层:(a) **受管 OTel**(事件级黄,零自建)由受管 env 强制导出到模型不可写的外部 OTLP collector;(b) **自建 MCP HMAC sink**(内容级红)对 事件+文件 diff 做 HMAC 链 + 外部 anchor,密钥在 agent 文件系统外。

### 4.1 折叠对抗发现(这些把"红已解决"打回原形,必须改对)

| 对抗发现 | 修法(已折叠) |
|---------|------------|
| **append 通道无鉴权**:hook POST 到无认证 loopback,模型持 Bash 可 `curl` 注入伪造 benign 条目,HMAC 照签 | append 通道**自身鉴权**:launcher 把 per-session append token(launcher-only key 的 HMAC)注入**受管 hook env**(env-scrub 白名单放行);sink 拒无 token 的 append。更进一步:记录的 diff **绑定到独立观测源**(服务端 git --numstat,组件 4),不信模型给的 tool_input。加探针:无 token 的 `curl /append` 被拒 |
| **"sink 不可达→block 本回合=无未审计推进"挂错 hook**:PostToolUse 在工具**已执行后**才跑,exit 2 撤不回已落盘的 500 文件 | 降级诚实声明:PostToolUse 是**事后**取证,**不**阻止未审计副作用。"无未审计推进"需 (i) PreToolUse 腿先记 intent,(ii) **服务端 git pre-commit --numstat 作内容/diff 的权威源**。验收门改断言真属性:sink down 时真跑 Edit 再 commit,被**服务端 pre-commit**(非 hook)挡住 |
| **内容级红其实没覆盖 Bash**:`_diff_for` 从 tool_input 取,Bash 内部写文件 diff="" | 设计文本与 fail_closed_notes 写明:自建 sink 内容级 diff 仅覆盖 Edit/Write/MultiEdit;**Bash 内部变更的权威 diff 是服务端 git --numstat(组件 4)**。加永久探针断言此限界(Bash 事件 diff 空 → 内容覆盖延到 git) |
| **持久化 O(n²) 且崩溃造不可检测 gap;重启 _head 回 GENESIS 与磁盘脱钩** | sink 启动时**从磁盘 re-walk 重建 _head/seq 并验链**(验不过拒启=fail-closed);只 append 新行;写盘与 _head 推进在同临界区 + fsync;配外部 anchor cadence |
| **denyWrite/denyRead 是工具级、Bash 可旁路;sink 与 agent 同 uid 时 `/proc/<pid>/environ` 泄密钥** | sink+collector 跑在**与 agent 不同的 OS uid**(从 open-question 升级为决策);配 Bash 沙箱;加探针:agent Bash 读 sink env/秘密被 OS 权限拒 |
| **OTel 事件 schema 未对装好的 CC build 验证** | 加真端到端验收:受管 env 下跑一次 CC 工具调用,断言本地 collector 的 `otel.jsonl` 有可归因记录,且删本地 JSONL/`--no-session-persistence` 不移除它。未验证前标 layer(a) 为 UNVERIFIED |

### 4.2 关键骨架(CC-free 内核 + 进程外 sink)

```python
# src/aiforge/governance/audit_chain.py —— CC-free HMAC 链(纯 stdlib, 无 CC/MCP import)
import hashlib, hmac, json
from typing import List, Optional, Tuple
_GENESIS = "0" * 64
def _chash(secret, prev, seq, actor, action, target, dh, fh) -> str:
    p = "|".join([prev, str(seq), actor, action, target, dh, fh]).encode()
    return hmac.new(secret, p, hashlib.sha256).hexdigest() if secret else hashlib.sha256(p).hexdigest()

class HmacAuditLedger:                       # append-only: 无 clear/delete/pop/truncate
    def __init__(self, secret: Optional[bytes] = None):
        self._ledger: List[dict] = []; self._head = _GENESIS; self._secret = secret
    @classmethod
    def load_verified(cls, jsonl_text: str, secret: bytes) -> "HmacAuditLedger":
        """重启时从磁盘重建并验链; 验不过 raise(fail-closed, 不静默接受脱钩链)。"""
        L = cls(secret); 
        for line in (l for l in jsonl_text.splitlines() if l.strip()):
            L._ledger.append(json.loads(line))
        ok, why = L.verify_chain()
        if not ok: raise ValueError(f"on-disk ledger 验链失败, 拒启: {why}")
        L._head = L._ledger[-1]["hash"] if L._ledger else _GENESIS
        return L
    def append(self, actor, action, target, detail: dict, diff="") -> int:
        seq = len(self._ledger)
        dh = hashlib.sha256(json.dumps(detail, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        fh = hashlib.sha256(diff.encode()).hexdigest()
        h = _chash(self._secret, self._head, seq, actor, action, target, dh, fh)
        self._ledger.append({"seq": seq, "actor": actor, "action": action, "target": target,
                             "detail_hash": dh, "diff_hash": fh, "prev": self._head, "hash": h})
        self._head = h; return seq
    def head(self): return self._head
    def count(self): return len(self._ledger)
    def verify_chain(self) -> Tuple[bool, str]:
        prev = _GENESIS
        for i, e in enumerate(self._ledger):
            if e["seq"] != i or e["prev"] != prev: return False, f"链断 @ {i}"
            if _chash(self._secret, e["prev"], e["seq"], e["actor"], e["action"],
                      e["target"], e["detail_hash"], e["diff_hash"]) != e["hash"]:
                return False, f"hash 不符 @ {i}(篡改或错密钥)"
            prev = e["hash"]
        return True, f"{len(self._ledger)} 条一致"
    @classmethod
    def verify_jsonl(cls, text, secret=None, expected_head=None, expected_count=None) -> Tuple[bool, str]:
        es = [json.loads(l) for l in text.splitlines() if l.strip()]
        if expected_count is not None and len(es) != expected_count:
            return False, f"条数 {len(es)}≠{expected_count}(截断/插入)"
        L = cls(secret); L._ledger = es; ok, why = L.verify_chain()
        if not ok: return False, why
        if expected_head is not None and (es[-1]["hash"] if es else _GENESIS) != expected_head:
            return False, "尾≠期望 head(截断/替换)"
        return True, "jsonl 链一致"
```

```python
# tests/test_audit_probes.py —— §5/§6 探针成永久回归(证明而非声称)
import unittest
from aiforge.governance.audit_chain import HmacAuditLedger, _chash
SECRET = b"held-externally"
def _mk(n, secret=None):
    L = HmacAuditLedger(secret)
    for i in range(n): L.append("cc", "Edit", f"f{i}", {"i": i}, f"+l{i}")
    return L

class TestRechainForgery(unittest.TestCase):
    def _rechain(self, L, secret_for_attacker=None):
        led = L._ledger; led[1]["actor"] = "FORGED"; prev = led[0]["hash"]
        for e in led[1:]:
            e["prev"] = prev
            e["hash"] = _chash(secret_for_attacker, e["prev"], e["seq"], e["actor"], e["action"],
                               e["target"], e["detail_hash"], e["diff_hash"]); prev = e["hash"]
    def test_unkeyed_rechain_passes(self):       # 诚实负基线: bare sha256 可全链重算
        L = _mk(4); self._rechain(L, None); self.assertTrue(L.verify_chain()[0])
    def test_hmac_resists_rechain(self):         # 真保护: 攻击者无密钥 -> 验链 False
        L = _mk(4, SECRET); self._rechain(L, None); self.assertFalse(L.verify_chain()[0])

class TestTruncation(unittest.TestCase):
    def test_needs_external_anchor(self):
        L = _mk(5, SECRET); head, cnt = L.head(), L.count()
        full = "\n".join(__import__("json").dumps(e) for e in L._ledger)
        trunc = "\n".join(full.splitlines()[:-1])
        self.assertTrue(HmacAuditLedger.verify_jsonl(trunc, SECRET)[0])                          # 自洽
        self.assertFalse(HmacAuditLedger.verify_jsonl(trunc, SECRET, head, cnt)[0])              # anchor 抓住

class TestOTelHonestLimit(unittest.TestCase):
    def test_bash_storm_one_event(self):         # 防 §9 过度声称: 1 个 Bash 事件 ≠ 500 文件
        L = _mk(0, SECRET); L.append("cc", "Bash", "for i in seq 1 500", {"cmd": "loop"}, "")
        self.assertEqual(L.count(), 1)
```

**Acceptance gates(可执行):**
```bash
PYTHONPATH=src python3 -m unittest discover -s tests 2>&1 | tail -3                     # ≥33 OK
PYTHONPATH=src python3 -m unittest tests.test_audit_probes -v                            # rechain/truncation/otel-limit 全过
# sink 无密钥 fail-closed
unset AUDIT_HMAC_SECRET; AUDIT_LEDGER_PATH=/tmp/l.jsonl python3 src/aiforge_harness/audit_sink/mcp_audit_server.py 2>&1 | grep -q 'fail-closed' && echo PASS
# append 通道无 token 被拒(折叠对抗发现#1)
echo '{"event":{"actor":"x","action":"Edit","target":"y"},"file_diffs":"+z"}' | curl -s -XPOST localhost:8731/append -d @- | grep -q 'unauthorized' && echo PASS
# audit_chain CC-free
! grep -qiE 'claude|anthropic|claude_agent_sdk|mcp' src/aiforge/governance/audit_chain.py && echo 'PASS CC-free'
```

---

## 5. 组件 4 — Phase 2 反应式 hook + 服务端 git/CI 权威 backstop

**Goal / 不变量:** 全量 diff 爆炸半径(P5)+ 门禁重跑于「committed 磁盘产物 + CI 产出证据」,**绝不**读 `.harness/state.json`(P1/P2/P3 真 backstop)。

**两个信任层:**
- **Tier 1 CC 端反应式 hook(早警告;仅对识别得到的文件工具 HARD):** PreToolUse 端口 `_spec_has_acceptance`(无冻结 spec → deny Edit/Write 到代码路径)、`StaticRiskScanner`(命中 → deny)。**Bash 显式只 advisory**(heredoc/rename/`python -c` 旁路明示,不假装拦)。Stop/PostToolUse 发 P7 三文件 checklist(advisory,`fail_closed:false`)。
- **Tier 2 服务端权威 backstop(不可旁路):** git pre-commit(装在上游/bare 仓 `core.hooksPath`,**非** worktree `.git`)+ 受保护分支 + required CI。证据由 CI 产出,状态从磁盘重建。

### 5.1 折叠对抗发现(这些让"权威层"要么永红要么 no-op,必须改对)

| 对抗发现 | 修法(已折叠) |
|---------|------------|
| **`build_default_gates()` 首门 `StatusGate` 要 `status==DONE`**;磁盘重建无 DONE → 服务端**拒每个 commit**;读磁盘 status 又重开自证绿洞 | 服务端**不**逐字复用 `build_default_gates()`;构 **server-specific 链**剔除 `StatusGate`(status 是编排概念非磁盘事实),只跑磁盘可查不变量:强化 SpecGate + Traceability + 喂 CI 证据的证据门。"DONE"由组件 5 外环断言,绝不从 worktree 文件重建 |
| **`PRGate` 默认 `AgentAsJudge()`=MockLLM → NEEDS_HUMAN**;唯一"修法"是注入可信 judge,而 Claude judge+trust=True 是 Claude-reviews-Claude | 服务端链**不**继承 PRGate 默认 judge;异构评审是组件 5 独立 X-judge 门。服务端要么**丢掉 Agent-as-Judge 步**,要么跑进程外 cursor/codex attested 非 Claude;缺则 `[independent gate not executable]`→HITL。加测试断言只有 Claude/Mock 时服务端转 HITL |
| **`CompletenessGate` 读 `state.verification` 而设计只喂 evidence dict** | `reconstruct()` 把 `state.verification` **仅**从同一份外部 CI 证据 JSON 填;加回归测试证明 `tests_ok` 来自 CI 证据非任何 worktree 文件。两通道(evidence dict + state.verification)都 CI-sourced |
| **`git diff --cached --numstat` 只看一个 commit**;500 文件拆成 500 个单文件 commit 每次过 | 权威 P5 边界改为**分支/PR 区间**:`git diff --numstat <merge-base>..HEAD`(CI 已算);本地 pre-commit `--cached` 仅早警告。`blast_radius` 接受显式区间;加拆分 storm 回归 |
| **CI 把分支 diff 算进 `/tmp/nd.txt` 却调 `blast_radius .`(硬编码 `--cached`),clean checkout index 空 → P5 永远 PASS** | `blast_radius` 接 `--base origin/${base_ref}` 或读 `/tmp/nd.txt`,**不**调 `git diff --cached`;CI 同 job 内断言一个已知超大合成 PR 被拒(no-op 不能静默过) |
| **`TraceabilityGate` 只查 ref 的 KIND 存在,不查血缘**;模型写孤儿代码 refs=['spec']+琐碎 spec 即过 | 服务端 P2 标 **ADV**;真 P2 需组件 5 外环从真实阶段产物写 refs 入进程外 SSOT。服务端至少把 declared refs 对独立信号(git history/CI provenance)比对,加孤儿-代码-挂-refs 负测 |
| **`_spec_has_real_acceptance` 又是单条正则,单行填充 `given xxx when xxx then xxx` 即过** | 不声称正则强制语义验收。标 ADV/启发式,或真做难(要求不同非停用词子句、≥N 具体场景、每 AC 可追溯到 task)并加单行填充/重复 token/lorem 负测——把评审反例放进回归 |
| **`pretooluse_gate.main()` 无顶层 try/except**;坏 stdin/import 错 → 无 permissionDecision 输出 = CC 继续 = fail-open | main() 包 try/except,**任何异常 fail CLOSED**:发 `permissionDecision='deny'` reason='hook error — fail-closed'。加坏 stdin/强制 import 错回归断言发的是 deny |
| **无 origin 本机**:"服务端" pre-commit 退化为 worktree 内本地 hook,`--no-verify` 可绕 | 显式标依赖:权威层**未在位**直到 (a) 真受保护 remote + server-side `core.hooksPath` + required check,或 (b) 组件 5 进程外外环强制。加探针:`--no-verify`/删本地 hook 仍被 required CI 抓 |
| **`StaticRiskScanner` 剥 `#` 开头行 + 只见单 Edit fragment**;`# eval()`/拆 Edit 逃逸,且服务端**无**全量 diff 重扫 | 服务端 `verify_gates` 加**全量 committed diff 的 StaticRiskScanner 重扫**(扫文件内容、扫代码时不预剥注释),加 `# eval`/拆 Edit 在 commit 边界被抓的测试;或撤"服务端抓 # leak"声称。保持"正则风险扫描是 best-effort(P6 ADV)"的诚实框 |

### 5.2 关键骨架

```python
# src/aiforge_harness/server/verify_gates.py —— 服务端权威(剔 StatusGate; 状态从磁盘+CI 证据)
import argparse, json, sys, re
from aiforge.quality.gates import (SpecGate, TraceabilityGate, PreCommitGate, CICDGate)
from aiforge.quality.judge import StaticRiskScanner
from aiforge.orchestration.state import ArtifactKind
from aiforge_harness.server.state_from_disk import reconstruct

def _spec_real_acceptance(t: str) -> bool:
    # ADV/启发式: 不声称真验收, 仅拒明显填充。要求 ≥2 个长度足够且不同的 AC 子句。
    lines = [l.strip() for l in (t or "").splitlines()]
    bullets = [l for l in lines if l[:2] in ("- ", "* ") or l.lower().startswith(("ac", "scenario"))]
    distinct = {l.lower() for l in bullets if len(l) >= 16}
    return len(distinct) >= 2

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="."); ap.add_argument("--evidence", required=True)
    ap.add_argument("--full-diff", required=True, help="committed 全量 diff 文本(供风险重扫)")
    a = ap.parse_args()
    evidence = json.load(open(a.evidence))               # CI 产出, 模型够不到
    state = reconstruct(a.repo)                            # 含 state.verification 也来自 evidence
    # server-specific 链: 无 StatusGate, 无 PRGate-默认-Claude-judge
    sp = state.latest(ArtifactKind.SPEC)
    if sp is None or not _spec_real_acceptance(sp.content):
        print("P1 server: spec 缺真实验收/为填充 -> 拒"); return 1
    # P6 全量 diff 重扫(折叠对抗发现: 抓 # eval / 拆 Edit, 扫整文件不剥注释)
    hits = StaticRiskScanner().scan(open(a.full_diff, encoding="utf-8").read())
    if any(h["severity"] == "blocker" for h in hits):
        print(f"P6 server: 全量 diff 命中 {hits[0]['issue']} -> 拒"); return 1
    for gate in (SpecGate(), TraceabilityGate(), PreCommitGate(), CICDGate()):
        r = gate.check(state, evidence)
        if not r.passed: print(f"GATE FAIL [{r.layer}] {r.name}: {r.reason}"); return 1
    return 0
if __name__ == "__main__": sys.exit(main())
```

```python
# src/aiforge_harness/server/blast_radius.py —— 权威 P5: 分支区间 diff(非 --cached)
import subprocess, sys
from aiforge.config import DEFAULT_GOVERNANCE
from aiforge.orchestration.state import FileChange
def range_changes(base: str, head: str = "HEAD", repo: str = "."):
    out = subprocess.run(["git", "-C", repo, "diff", "--numstat", f"{base}...{head}"],
                         capture_output=True, text=True, check=True).stdout
    ch = []
    for line in out.splitlines():
        if not line.strip(): continue
        a, r, p = (line.split("\t") + ["", "", ""])[:3]
        ch.append(FileChange(p, 10**9, 0) if a == "-" or r == "-"     # 二进制: 未知 -> fail-closed
                  else FileChange(p, int(a or 0), int(r or 0)))
    return ch
def check(base: str, repo: str = ".", cfg=DEFAULT_GOVERNANCE):
    ch = range_changes(base, "HEAD", repo)
    files = len({c.path for c in ch}); lines = sum(c.total_lines for c in ch)
    if files > cfg.max_files_per_change: return False, f"P5: {files} 文件 > {cfg.max_files_per_change}"
    if lines > cfg.max_lines_per_change: return False, f"P5: {lines} 行 > {cfg.max_lines_per_change}"
    return True, "ok"
if __name__ == "__main__":
    ok, why = check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "."); print(why); sys.exit(0 if ok else 1)
```

```python
# src/aiforge_harness/hooks/pretooluse_gate.py —— main() 包 try/except, 异常 fail-closed
import json, sys
def main():
    try:
        env = json.load(sys.stdin); tool = env.get("tool_name", "")
        if tool not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Bash 写面非本 hook 强制; 权威在服务端 commit 边界"}})); return
        from aiforge.quality.judge import StaticRiskScanner
        from aiforge.quality.gates import _spec_has_acceptance  # noqa: 复用内核
        ti = env.get("tool_input", {})
        content = ti.get("content") or ti.get("new_string") or ""
        hits = StaticRiskScanner().scan(content)
        decision, reason = ("deny", f"P6: {hits[0]['issue']}") if hits else ("allow", "")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": decision, "permissionDecisionReason": reason}}))
    except Exception as e:                                  # 折叠对抗发现: 任何异常 fail-closed
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": f"hook error — fail-closed: {e}"}}))
if __name__ == "__main__": main()
```

**Acceptance gates(可执行):**
```bash
PYTHONPATH=src python3 -m unittest discover -s tests                                   # ≥33 OK
# P5 拆分 storm: 500 个单文件 commit, 区间 diff 仍拒(折叠对抗发现)
r=$(mktemp -d); git -C $r init -q; git -C $r commit -q --allow-empty -m base
for i in $(seq 1 500); do echo x>$r/f$i; git -C $r add f$i; git -C $r commit -q -m c$i; done
PYTHONPATH=src python3 -m aiforge_harness.server.blast_radius "$(git -C $r rev-list --max-parents=0 HEAD)" "$r"; test $? -ne 0
# 坏 stdin -> deny(fail-open 修复)
echo 'NOT JSON' | PYTHONPATH=src python3 -m aiforge_harness.hooks.pretooluse_gate | grep -q '"permissionDecision": "deny"'
# 全量 diff 重扫抓 # eval / 拆 Edit
printf '# eval(payload)\nx = ev"al"(p)\n' > /tmp/fulldiff; PYTHONPATH=src python3 -c "
from aiforge.quality.judge import StaticRiskScanner; import sys
hits=StaticRiskScanner().scan(open('/tmp/fulldiff').read())
# 注: 仍 best-effort(P6 ADV); 此处证明全量重扫比单 Edit fragment 多看到内容"
```

---

## 6. 组件 5 — Phase 3+4 外监督者 + 进程外审批 + 异构验证

**Goal / 不变量:** 4 个纯受管 CC 给不出的 fail-closed:① 确定性阶段序 + BLOCKED 不可 override(权威在外环 SSOT);② 真安全停机 = 拆掉 `query()`/杀进程,非 deny-loop;③ per-actor HMAC actor 绑定 + nonce + TTL + 单次 ticket,密钥不在 agent 路径,敏感能力只作服务端验证的 MCP 工具暴露;④ ≥2 distinct attested 非 Claude 厂商,缺则 fail-closed 转 HITL,绝不静默 Claude-reviews-Claude。

### 6.1 折叠对抗发现(这些是最重的,改不对整层是剧场)

| 对抗发现 | 修法(已折叠) |
|---------|------------|
| **`StatusGate` 阻 RUNNING**:外环若在阶段间跑整 `build_default_gates()`,首门要 DONE,第一阶段后即 BLOCKED,且 BLOCKED 不可 override → 永久卡死 | **不在每阶段间跑整链**。要么 (a) 7 阶段全跑完、status 合法 DONE 后**跑一次整链**(贴合 aiforge 原语义),要么 (b) 建 phase-scoped 子链**剔除 StatusGate/CanaryGate**,只跑该阶段相关门。验收测试真跑 analyst→…→verifier→终态门→DONE |
| **自证绿没堵全**:`CompletenessGate` 读 `state.verification`(模型蒸馏字段),非 OuterVerifier 的 evidence dict | OuterVerifier **唯一**写 `state.verification`(= evidence['tests_ok']),门链跑前写;`_distill` **绝不**碰 `state.verification`(只 Artifact/FileChange/refs)。强化 forgery 测试:同时往 workspace state.json 与 distillation 注假绿,断言 CompletenessGate 只由 OuterVerifier 驱动 |
| **`produce()` 每阶段都调**:analyst 后无 code/test,verifier 永跑空 → 每早阶段失败 → BLOCKED | OuterVerifier.produce() 与验证相关门**只在 verifier 阶段及之后**跑;早阶段只跑该阶段适配门。或塌缩为:7 阶段先全跑,再对完成的流水线跑一次整链 |
| **`.importlinter` 契约缺 `include_external_packages=True`**:`forbidden_modules=claude_agent_sdk` 直接报配置错,lint 退非零 = 配置错冒充强制 | 加 `include_external_packages=True`(已在 §1.1);加**故意失败探针**:在 `aiforge.quality` 植一行 `import claude_agent_sdk`,断言契约真 BROKEN(否则规则对 harness 方向可能 no-op) |
| **trust 在 in-process 翻**:外环把 vendor 串喂 judge 构造即翻 trust,模型能影响哪个串到达即重建后门 | trust 只由模型不可影响的对象授予:传**验过的 Attestation 对象**(含解析的二进制路径 + challenge 结果),非裸 vendor 串。更好:in-process judge 默认保守(MockLLM→NEEDS_HUMAN),**外环**(非 in-CC judge)进程外查 `HeteroBridge.independent_judges()`。加测试:模型可伪造的 `attested_vendor='gpt-5.5'` 不翻 trust 除非真 attest() 撑 |
| **`--attest-model` 是臆测 flag;CLI 没装;`CLAUDE_CLI=/bin/echo rejected` 实为路径拒非 attestation** | 拆声称:(1) 诚实测路径拒(改名 `..._rejected_by_path_pinning`);(2) 真 attestation 门后挂**对真 cursor/codex CLI 的探针 CONFIRM/REFUTE 是否有防篡改自识别**;没有则路径拒为唯一检查且 runner/env 非可证不可影响时 fail-closed 转 HITL,**不**声称 attestation。`hetero_judge` 标 `INDEPENDENT_GATE_NOT_EXECUTABLE`→HITL 直到真探针 CONFIRM |
| **审批密钥 `os.environ.get`**:MCP server `python -m harness.approval_authority` 无隔离规格,同 uid 时 agent Bash 读 `/proc/<pid>/environ` 拿密钥 → 每 ticket 可伪造 | approval-authority MCP **跑在与 agent 不同 uid**或沙箱命名空间外,environ 对 agent Bash 不可读;优先从 OS keyring 运行时取(不落 environ)。加探针(证明非声称):developer 阶段 Bash 读该进程 `/proc/<pid>/environ` 与 `env` **不**泄 `AIFORGE_APPROVAL_SECRET`,泄则 fail build |
| **disposable-worktree 只回滚文件**:已 exercise 的网络/infra/delete 副作用不可回滚,却被当"原子回滚"卖 | 限界声明:worktree 丢弃仅回滚**文件系统**副作用;有外部副作用的能力一旦 `exercise_capability` 跑即不可逆。排序:敏感能力**只在该阶段门过后**可 exercise,缩小 BLOCKED-after-side-effect 窗口。加 ADR/测试记录不可逆边界 |
| **`_distill` 填 refs 仍是 presence-check 橡皮章**:KIND 存在即过,孤儿-代码-挂-refs=['spec'] 照过 | 定义蒸馏血缘契约:refs 从真 provenance 信号导(developer 阶段实际消费的 spec/plan id,从 SDK message stream 或结构化 task→code 映射捕获);TraceabilityGate(或新外环检查)验被引产物的 identity/hash 非仅 KIND 存在。负测含硬例:CODE 内容与 SPEC 无关但挂 refs=['spec'] → 拒 |
| **managed-settings 只 denyWrite harness/,无 denyRead**:SSOT/request_ids agent 可读,辅助构造旁路 | managed-settings 对 `harness_runtime/`、`harness_runtime/bin`、SSOT checkpoint 加 **denyRead**(非仅 denyWrite),确认 worktree 不经共享 git objects 暴露 SSOT。加探针:agent Bash 读 SSOT checkpoint 与 harness 源返回权限拒 |

### 6.2 关键骨架

```python
# src/aiforge_harness/supervisor/supervisor.py —— 外环: 阶段全跑完再跑一次整链(避开 StatusGate 自相矛盾)
from aiforge.orchestration.state import PipelineState, Status, ArtifactKind
from aiforge.quality.gates import build_default_gates
from aiforge_harness.supervisor.sdk_client import PhaseSession  # 包 claude_agent_sdk.query()
from aiforge_harness.supervisor.verifier import OuterVerifier   # 唯一写 evidence/state.verification

PIPELINE = ["analyst", "architect", "tasks", "developer", "reviewer", "tester", "verifier"]
_STOP = {Status.NEEDS_HUMAN, Status.HALTED, Status.BLOCKED}
ALLOWED = {  # per-actor 最小权限
    "analyst":   ["Read", "mcp__evidence__read"],
    "developer": ["Read", "Edit", "Write", "Bash", "mcp__approval__request_approval"],
    "reviewer":  ["Read", "mcp__hetero__hetero_judge"],
    "verifier":  ["Read"],  # 证据来自 OuterVerifier, 不靠本 session
}

class HaltSignal(Exception): ...

class OuterSupervisor:
    def __init__(self, verifier: OuterVerifier, attest_verify_key: bytes):
        self.verifier = verifier; self.attest_verify_key = attest_verify_key; self._active = None
    def _next_index(self, s): 
        return 0 if s.current_node is None else (PIPELINE.index(s.current_node)+1 if s.current_node in PIPELINE else 0)

    def invoke(self, state: PipelineState, start=0) -> PipelineState:
        state.status = Status.RUNNING
        for idx in range(start, len(PIPELINE)):
            phase = PIPELINE[idx]
            self._active = PhaseSession(phase, allowed_tools=ALLOWED.get(phase, ["Read"]))
            try:
                side = self._active.run_phase(state)          # 一阶段一 query()
            except HaltSignal:
                self._active.teardown()                        # 真停机: aclose() + killpg
                state.status = Status.HALTED; state.log("supervisor", "halted_torn_down", at=phase); return state
            self._distill(state, phase, side)                  # 外环填 refs(从真产物, 非模型)
            self._active.teardown()
            if state.status in _STOP:
                state.log("supervisor", "interrupted", at=phase, status=state.status.value); return state
        # 7 阶段全跑完 -> OuterVerifier 写 evidence/state.verification -> 跑一次整链(status 合法 DONE)
        state.status = Status.DONE
        evidence = self.verifier.produce(state)                # 唯一写 state.verification 的地方
        state.verification = {"tests_ok": evidence.tests_ok, "reason": evidence.reason}
        results = build_default_gates().run(state, evidence.as_dict())
        return state                                           # BLOCKED 已由 chain 设置(不可 override)

    def resume(self, state, approve=True):
        if state.status == Status.BLOCKED: return state         # 不可 override(P3)
        if state.status in (Status.NEEDS_HUMAN, Status.HALTED) and approve:
            state.needs_human_reason = None; state.status = Status.RUNNING
            return self.invoke(state, self._next_index(state))
        return state

    def _distill(self, state, phase, side):
        """读 committed worktree 产物; 从真 provenance(SDK message stream 捕获的 task->code 映射)填 refs,
        TraceabilityGate(或外环)验被引产物 hash, 非仅 KIND 存在。state.verification 绝不在此写。"""
        ...
```

```python
# src/aiforge_harness/supervisor/sdk_client.py —— 真停机 seam(FakeQuery 可测 torn_down)
import os, signal
class PhaseSession:
    def __init__(self, phase, allowed_tools, mcp_servers=None):
        self.phase, self.allowed_tools = phase, allowed_tools
        self._gen = self._proc = None; self.torn_down = False
    def run_phase(self, state):
        from claude_agent_sdk import query, ClaudeAgentOptions      # 唯一硬 CC import
        opts = ClaudeAgentOptions(allowed_tools=self.allowed_tools, permission_mode="default",  # 绝不 bypass
                                  mcp_servers=mcp_for(self.phase))
        self._gen = query(prompt=phase_task(self.phase, state), options=opts)
        return drain(self._gen)
    def teardown(self):
        self.torn_down = True
        if self._gen is not None:
            try: self._gen.aclose()
            except Exception: pass
        if self._proc and self._proc.pid:
            try: os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError): pass
```

进程外 `ApprovalAuthority`(MCP)直接复用并强化内核 `governance/permissions.py`(actor 绑定 + nonce + TTL + 单次已在内核实现,已核实):server 持密钥、暴露 `request_approval`/`exercise_capability` 而**非裸 ticket**,server 端自签自验,ticket bytes 不交 agent。`HeteroBridge` 路径拒 + attest(诚实拆分见上)。

**Acceptance gates(可执行):**
```bash
PYTHONPATH=src python3 -m unittest discover -s tests && lint-imports            # 内核 CC-free + 33 绿
# 故意失败探针: 内核植入 CC import -> 契约 BROKEN(证明规则非 no-op)
printf '\nimport claude_agent_sdk  # PROBE\n' >> src/aiforge/quality/judge.py; ! lint-imports; git checkout src/aiforge/quality/judge.py
# 外环测试(FakeQuery)
PYTHONPATH=src:. python3 -m pytest tests/test_supervisor_harness.py -k "needs_human_then_resume_to_done or blocked_resume_unchanged or halt_tears_down_query or workspace_state_forgery_ignored or dangling_ref_rejected"
# 审批 ticket 四拒
PYTHONPATH=src:. python3 -m pytest tests/test_approval_authority.py -k "forged or replay or cross_actor or expired"
# 密钥进程隔离探针(折叠对抗发现): 不同 uid 时 agent Bash 读不到密钥
# (部署门: developer-phase sandbox 内 cat /proc/<authority_pid>/environ | grep -q AIFORGE_APPROVAL_SECRET && exit 1)
# 异构: 假 CLI 路径拒 + <2 distinct 厂商转 HITL
CLAUDE_CLI=/bin/echo PYTHONPATH=src:. python3 -m pytest tests/test_hetero_bridge.py -k "fake_cli_rejected_by_path_pinning or distinctness_fail_closed or fewer_than_two_vendors"
```

---

## 7. 迁移路径(33 pytest 每步绿)

每步小、可逆、独立可提交。**写第一行前进 worktree**(`feat-cc-harness`),`main` 留作集成点。每步门 = `PYTHONPATH=src python3 -m unittest discover -s tests` 全绿 + 相关探针。

| 步 | 动作 | 必绿命令 |
|----|------|---------|
| 0a | 地雷#3:`config.py` 加 `compact_trigger_tokens=50_000`;`memory.py` 默认从 config 取 | `python3 -m unittest discover -s tests`(33 OK;test_context.py:48/:50 不变) |
| 0b | 地雷#1:`judge.py` 默认 UNTRUSTED;迁移 5 站点(eval/harness.py:50 + test_quality.py:16,93,96,98)为 `trust_llm=True`;:91 不变(已断言不可信) | `python3 -m unittest discover -s tests`(33 OK) + §1.3 judge 验收 |
| 0c | 地雷#2:`openhands.py` 加 `selfcheck()` 真往返 + fail-closed;`_client_roundtrip` 显式 NotImplementedError;新增无 cred 跳过测试 | `python3 -m unittest discover -s tests`(34 collected, 1 skipped) |
| 1 | `.importlinter` 改 `root_packages`(复数)+ `include_external_packages=True` + 3 契约;`pyproject` dev 加 import-linter、加 `harness` extra;建空 `src/aiforge_harness/__init__.py`;加 `tests/test_harness_boundary.py` | `pip install import-linter && lint-imports`(exit 0)+ `python3 -m unittest tests.test_harness_boundary` |
| 2 | 内核 CC-free 新增:`governance/audit_chain.py`(纯 stdlib)+ `tests/test_audit_chain.py` + `tests/test_audit_probes.py` | `python3 -m unittest discover -s tests`(↑)+ audit_chain CC-free grep |
| 3 | Phase 0:`harness_runtime/probes/`(含 baseline 拷贝)+ `sandbox.sb`(删 /private/tmp、加 denyRead)+ `run_probes.sh`(SKIP=77)+ `tests/test_phase0_probes.py`;`.gitignore` 加 `!.claude/settings.json` | `bash run_probes.sh --profile=bad && --profile=locked`;`git check-ignore .claude/settings.json`(空) |
| 4 | 组件 4:`aiforge_harness/hooks/`(pretooluse 包 try/except)+ `aiforge_harness/server/`(blast_radius 区间 diff、verify_gates 剔 StatusGate+全量重扫)+ `tests/test_harness_phase2.py` | `python3 -m unittest discover -s tests` + 拆分 storm/坏 stdin 验收 |
| 5 | 组件 3:`aiforge_harness/audit_sink/`(append token 鉴权、sink load_verified、独立 uid 部署说明) | sink 无密钥 fail-closed + append 无 token 拒 |
| 6 | 组件 5:`aiforge_harness/supervisor/`(全跑完再跑整链)+ `approval/` + `hetero/`;`tests/test_supervisor_harness.py`/`test_approval_authority.py`/`test_hetero_bridge.py`(FakeQuery,无需真 SDK) | `python3 -m unittest discover -s tests` + `lint-imports` + 故意失败探针 |

> **worktree 隔离:** 整个迁移在 `feat-cc-harness` worktree 做;集成回 main 走本地 merge(本机无 origin)。`.claude/` 未 gitignore 的部分跨窗口禁止 `git add -A`,只 stage 明确路径。

---

## 8. 分期里程碑与验收门

| Phase | 交付 | 可执行验收门 | 本阶段加入的回归探针(报告 §5/§6) |
|-------|------|------------|--------------------------------|
| **0** | 配置锁定(Tier A/B/C)+ 双向探针 + 3 地雷修 | `sandbox-exec -f sandbox.sb 'echo>外部'; test $? -ne 0`;`run_probes.sh --profile=bad`(全 ALLOW)与 `--profile=locked`(全 BLOCK);`discover -s tests` ≥35 OK | 8 间接 Bash 旁路(p01,locked 仅断言越界写/不沙箱)、500-storm 越界(p02)、`--dangerously-skip-permissions` 拒(p05,macOS gate)、读秘密(denyRead) |
| **1** | 受管 OTel(事件黄)+ 外部 HMAC sink(内容红)+ 外部 anchor | `unittest tests.test_audit_probes`(rechain/truncation/otel-limit);sink 无密钥 fail-closed;append 无 token 拒;**OTel 端到端**:受管 env 跑一次 CC 工具调用,`grep <tool_decision> otel.jsonl` 且删本地 JSONL 后仍在 | 全链重算伪造(HMAC 拒)、尾截断(需外部 anchor)、删本地 JSONL/`--no-session-persistence`(外部仍有)、OTel 对 Bash storm 盲(1 事件≠500) |
| **2** | Tier1 反应式 hook + Tier2 服务端 git/CI 权威 backstop | 拆分 500-commit storm 被区间 `blast_radius` 拒;坏 stdin → hook deny;`echo>.harness/state.json` 不改 verify_gates(读 CI 证据);CI job 内已知超大合成 PR 被拒(防 no-op) | no-spec 写 deny、风险命中 deny、Bash **不**硬拒(fail-open-by-design)、500-storm 服务端拒、自证绿被忽略、`# eval`/拆 Edit 全量重扫抓、单行填充 spec 拒 |
| **3** | Agent-SDK 薄外环(SSOT 进程外)+ 真停机 | `pytest test_supervisor_harness.py -k "needs_human_then_resume_to_done or blocked_resume_unchanged or halt_tears_down_query or workspace_state_forgery_ignored or dangling_ref_rejected"`;`lint-imports`(含故意失败探针) | counter reset 9→0(SSOT 进程外)、`echo>state.json` 自证绿(evidence 来自 OuterVerifier)、BLOCKED 不可绕、P4-halt deny-loop vs 真 teardown、dangling-ref |
| **4** | 进程外 ApprovalAuthority(MCP,独立 uid)+ 异构验证桥 | `pytest test_approval_authority.py -k "forged or replay or cross_actor or expired"`;`pytest test_hetero_bridge.py -k "fake_cli_rejected_by_path_pinning or distinctness_fail_closed"`;**密钥隔离探针**:agent Bash 读 authority `/proc/<pid>/environ` 无密钥 | `CLAUDE_CLI=/bin/echo`/PATH 假 cursor-agent 拒、<2 distinct 厂商转 HITL、伪造/重放/跨 actor/过期 ticket 拒、密钥 `/proc` 泄漏探针 |

---

## 9. 风险登记册(本方案不完全闭合的残留)

| 残留风险(报告已旗) | 为何不闭合 | 诚实缓解 |
|-------------------|-----------|---------|
| **CC session append-only,真回滚不可能** | SDK 外环能"拒绝推进"但不能真回滚一个阶段;已 exercise 的网络/infra/delete 外部副作用文件丢弃回滚不了 | disposable worktree = 仅文件系统的穷人原子回滚;敏感能力**只在阶段门过后**可 exercise,缩小 BLOCKED-after-side-effect 窗口;不可逆边界写进 ADR,不当"回滚安全"卖 |
| **OTel 对 Bash 内部写盲** | 1 个 Bash tool_decision = 1 事件,500 文件写只见 1 事件;事件级覆盖不到内容 | 内容级 diff 的权威源是**服务端 git pre-commit --numstat**(组件 4),非 OTel/PostToolUse hook;`TestOTelHonestLimit` 永久守此限界防过度声称 |
| **codex 硬依赖(≥3-vendor best-of-N)** | 真跨模型独立需 ≥2 distinct 非 Claude 厂商;codex/cursor CLI 不一定有防篡改自识别(`--attest-model` 是臆测) | 缺 ≥2 verified 厂商 → `INDEPENDENT_GATE_NOT_EXECUTABLE` → **fail-closed 转 HITL**,绝不静默 Claude-reviews-Claude;真 attestation 上线前先对真 CLI 跑 CONFIRM/REFUTE 探针 |
| **macOS 无真 MDM 时 Tier A 可被 sudo 用户 rm** | `/Library/Application Support/ClaudeCode/managed-settings.json` 需 root 写,但有 sudo 的用户仍能删;真 profile-lock 要 Jamf/Intune | 单机开发者:best-effort root-owned 可接受,**显式标注强保证需 enroll MDM**;Tier A 的每个键须对装好的 CC build 可执行验证(`failIfUnavailable`/`allowManagedPermissionRulesOnly`/`${WORKSPACE}`),不被尊重则声明降级 |
| **本机无 origin → 服务端边界退化为本地 hook** | 本地 `.git/hooks/pre-commit` 在 worktree,模型可改/`--no-verify` 绕 | 权威层**未在位**直到真受保护 remote(server-side `core.hooksPath` + required check)或组件 5 进程外外环强制;探针证明 `--no-verify`/删本地 hook 仍被 required CI 抓 |
| **`claude_agent_sdk` 未装,真 teardown 语义未验** | `query()` 签名、async-gen `aclose` vs cancel、是否 spawn 可杀进程组未对装好 SDK 验证 | FakeQuery seam 让测试先过;真 teardown 标 UNVERIFIED,接 SDK 后必须对真 `query()` 证明是真停机非假设 |

---

## 10. 先做什么(build order)

**去风险首个原型 = Phase 0 锁定 + 受管 OTel + 双向探针**(报告 §9 review item 6:不要在受管配置 + OTel 基线证明前自建 HMAC sink——没 Phase 0,sink 的覆盖本身不可信)。

**顺序:** Phase 0(配置锁定 + 探针 + 3 地雷)→ Phase 1(OTel 黄基线,再加 HMAC 红)→ Phase 2(服务端 git/CI 权威 backstop,这是真不可旁路层的脊梁)→ Phase 3(SDK 外环 + SSOT 进程外)→ Phase 4(进程外审批 + 异构)。组件 1(布局/边界)与 0a/0b/0c 地雷是横切前置,STEP 0–1 先落。

**单一裁决门(失败则缩小赌注):**

> **门:** 在装好的 CC build 上,受管 `managed-settings.json` 安装后,`claude --dangerously-skip-permissions --print noop` **被拒**(exit≠0),**且**沙箱不可用时**不**静默不沙箱跑(`failIfUnavailable` 或至少 `allowUnsandboxedCommands=false` 被尊重),**且** OTel 端到端探针证明一次真工具调用落到外部 collector 且删本地 JSONL 后仍在。

这三条任一**在真 build 上证不出**,意味着"薄外层 + 受管 CC"的核心假设不成立(CC 的受管/沙箱/OTel 不是真 fail-closed 原语),此时应**把赌注缩小到完整 route-(b)**(纯 SDK 外环重建确定性路由 + 完全进程外权威,放弃复用 CC 受管层),或对受监管产线**保留自托管引擎**(OpenHands,组件已留 `runtime/openhands.py` 适配 seam)。在这门通过前,所有 Tier C / hook / CLAUDE.md 层一律按 **advisory** 对待,不计入 fail-closed 论证。