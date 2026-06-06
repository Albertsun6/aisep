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
| `fix(C6)` | 无 spec 照样过门禁、refs 不校验、PreCommit fails-open | `SpecGate`(P1)+`TraceabilityGate`(P2)+全门 **fails-closed**，真接进 `build_default_gates`；风险表单一来源 | 无 spec+证据齐全→拦于 SpecGate；零证据→fails-closed；统一表含 infra/config |
| `fix(C3)` | eval 指标由 `dataset.evidence` 手喂（量的是 fixture） | eval 的 `tests_ok` 改由 **verifier 真实运行**驱动 | 翻转 dataset 的 tests_ok 不再影响指标（两同任务→完成率 1.0） |

## 验证

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q   # 29 测试全过
PYTHONPATH=src python3 -m aiforge.cli demo                # 端到端 → DONE
PYTHONPATH=src python3 -m aiforge.cli eval                # 指标由真验证驱动
```

## 诚实的边界 / 刻意的保守默认（不是 bug）

- **无真实 LLM 时**：developer 诚实停机、PR/spec 转人审。离线靠 `StubCodeLLM`/`StubReviewerLLM` 跑通端到端；**生产必须接真模型**。
- **无真隔离时**（非 macOS 且无 docker）：verifier fail-closed（不在无隔离下执行生成代码）。
- **C3 仅 `tests_ok` 维度已修**：coverage/SAST/lint/regression 仍为外部证据（系统尚未真跑覆盖率/SAST/既有回归套件）。
- `runtime/local.py` 的 `LocalSandbox` 仍无隔离——**仅供可信代码**；不可信执行已改走 `isolation`。
- 更强的（如 C6 逐 artifact-id 追溯）作为后续增强，未塞进本分支（避免过度工程）。

## 如何合并

```bash
git diff main..aiforge-hardening      # 审改动（17 文件 / +904 −131）
git checkout main && git merge aiforge-hardening
# 如需 PR：先配 remote 再 push（本分支尚无 remote）
```

落地依赖序固定且已在代码里强制：**C4(隔离) → C1(执行)**。
