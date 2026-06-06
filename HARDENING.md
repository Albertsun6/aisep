# AIForge 安全/正确性硬化（分支 `aiforge-hardening`）

> 本分支把对 AIForge 的 6 个缺陷修复落地进 `src/`。`main` 仍是原始基线，本分支与之**清晰可分、可回滚**。
> 来历：先对基线做了可执行的缺陷评估（见仓库外 `…/挑战评估/`，含 PoC + 异构评审记录），每个 fix 都经
> cursor-agent（GPT-5.5）异构评审 + 对抗辩论后才落地。

## 一句话

> 让 AIForge 从"演示控制流的空心脚手架"变成"**真生成代码 → 隔离里真验证 → 硬化门禁**，且无真实 LLM/隔离时**诚实停机/转人审**而非造假"的系统。

## 修了什么（缺陷 → 修复 → 落地实证）

| 提交 | 缺陷 | 修复 | 可执行实证 |
|---|---|---|---|
| `fix(C4)` | "沙箱"= `shell=True` 临时目录，无隔离 | 新增 `runtime/isolation.py`：**自检验证**的隔离后端（macOS sandbox-exec / 容器）+ `select_sandbox()` fail-closed | 落地模块实测拦读 home/写 home/写 tmp/网络、killpg、无隔离则拒执行 |
| `fix(C1)` | developer 写死 `return "<id>"`、tester 恒 `assert True` | `codegen.py`：LLM 输出**成为真代码**；`verifier` 节点在 C4 隔离里**真跑** unittest（变异反作弊）；无真 LLM **诚实停机** | developer→`return 42`、verifier `tests_ok=True`、`MockLLM`→halt |
| `fix(C2)` | Agent-as-Judge 只看 task_type 关键词，persona 意见被丢弃 | 内容感知（静态扫描 + 结构化 LLM 面板）；无可信 LLM/命中/高风险→**转人审**，绝不自动放行 | 危险 feature→PR `passed=False`（原 True），干净→True 不误杀 |
| `fix(C5)` / `fix(C5)+` | `grant()` 无条件授予敏感能力，可自授 delete | 敏感能力默认拒绝；只能凭 **HMAC 签名人审 ticket** 授予；**per-actor** + actor 绑定 + 防重放 | agent 自授 delete→`has=False`；developer 的 delete≠reviewer；伪造/重放票被拒 |
| `fix(C6)` | 无 spec 照样过门禁、refs 不校验、PreCommit fails-open | `SpecGate`(P1)+`TraceabilityGate`(P2)+`StatusGate`(白名单 DONE)+`CompletenessGate`(CODE/TEST+verifier 真过)+全门 **fails-closed**；风险表单一来源 | 无 spec→拦于 SpecGate；零证据→fails-closed；非 DONE/缺验证→拦；默认门禁**不带 stub 评审**(转人审) |
| `fix(C3)` → **已撤销** | eval 指标由 `dataset.evidence` 手喂（量的是 fixture） | 曾改用 verifier 真实结果驱动，但**异构落地评审指出那是循环自证**(同一 stub 既产码又产测试，会掩盖 dataset 的回归信号)，故**撤销**；dataset oracle 仍权威 | eval 现明确标注为**合成门禁路由自测**(非生产指标)；真 C3 需真实 LLM + 独立 oracle 测试 |

## 验证

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q   # 33 测试全过
PYTHONPATH=src python3 -m aiforge.cli demo                # 端到端 → DONE
PYTHONPATH=src python3 -m aiforge.cli eval               # 合成门禁路由自测(非生产指标)
```

> 注：落地的 **diff 本身也经了多轮异构评审**（cursor-agent）。第 1 轮判"否"，修了 4 个洞（默认门禁误用 stub
> 评审、judge 审 request 而非真代码、C3 eval 循环自证、HALTED 仍可能过门禁）；第 2 轮判"部分"，进一步把
> 健康门拆成 StatusGate(白名单 DONE)+CompletenessGate(verifier 必须存在且真过)、PRGate 拒空 diff、eval
> 输出加合成标记。收敛。

## 诚实的边界 / 刻意的保守默认（不是 bug）

- **默认门禁是保守的**：`build_default_gates()` 的 PR 门**不带** stub 评审——无可信 LLM → 转人审，绝不自动放行。离线 demo/eval/测试需**显式**注入 `AgentAsJudge(llm=StubReviewerLLM())`；**生产必须接真模型**。
- **judge 审真实代码**：PRGate 缺 `diff_summary`（真实代码 diff）即 fails-closed，不退回 request 文本。
- **无真实 LLM 时**：developer 诚实停机；MockLLM 路径不造假。
- **无真隔离时**（非 macOS 且无 docker）：verifier fail-closed（不在无隔离下执行生成代码）。
- **C3 未落地**：eval 是合成门禁路由自测；自生成测试不能覆盖 dataset 的 oracle 失败信号。真 C3 需真实 LLM + 独立 oracle 测试 + 真覆盖率/SAST 工具。
- **变异校验有限**：能挡空测试，挡不住"常量实现 + 配套常量测试"——根因是测试与代码同源，需独立 oracle（同上）。
- `runtime/local.py` 的 `LocalSandbox` 仍无隔离——**仅供可信代码**；不可信执行已改走 `isolation`。
- 已知遗留：`runtime/__init__` 顶层 import isolation（轻量，stdlib-only）；以及 `base→governance→…→base` 的**既有**循环 import——`import aiforge.runtime` 作为首个 import 会触发，按正常依赖顺序无碍（不在本次范围内修）。
- 更强的（C6 逐 artifact-id 追溯、per-actor 已做）作为后续增强，避免过度工程。

## 如何合并

```bash
git diff main..aiforge-hardening      # 审改动（17 文件 / +904 −131）
git checkout main && git merge aiforge-hardening
# 如需 PR：先配 remote 再 push（本分支尚无 remote）
```

落地依赖序固定且已在代码里强制：**C4(隔离) → C1(执行)**。
