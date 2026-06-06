# OpenHands 自托管接入（Phase 3）

企业私有化 / 合规优先选 OpenHands：开源、可自托管（Docker/K8s）、Large Codebase SDK（跨系统映射依赖、按序编排、多 agent 并行不冲突）、模型无关、原生接 GitHub/GitLab/CI。

## 启动

```bash
cd deploy/openhands
export LLM_API_KEY=...                 # 走 AI Gateway 或自有推理
export LLM_MODEL=anthropic/claude-sonnet-4-5
docker compose up -d
# UI: http://localhost:3000
```

## 接到 AIForge

在编排中把 `LocalSandbox` 换成 `OpenHandsRuntime`：

```python
from aiforge.governance.permissions import PermissionBroker
from aiforge.runtime.openhands import OpenHandsRuntime

perms = PermissionBroker()
runtime = OpenHandsRuntime(perms, endpoint="http://localhost:3000", api_key="...")
```

未配置 `endpoint` 时，`OpenHandsRuntime` 对所有写动作**安全停机**（宪法 P4），不会静默执行。

## 多 agent 并行（Large Codebase SDK 语义）

`OpenHandsRuntime.plan_parallel_batches(tasks, dependencies)` 按依赖拓扑分批：批内并行（受 `max_parallel_agents` 限制）、批间按序，避免并行冲突。生产中由 OpenHands 真实调度执行。

## 备选 runtime

- **Devin Enterprise**：托管、VPC、SSO/审计；注意 ACU 计费（约 $2.25/ACU）成本不可预测。
- **Ona**：编排层也在 VPC 内，强合规场景更友好。
- **Tabnine**：air-gapped 自托管，金融/国防。

通过实现 `aiforge.runtime.base.Runtime` 子类即可接入（宪法 P9 选型可替换）。
