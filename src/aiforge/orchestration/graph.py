"""Supervisor 图引擎（复刻 LangGraph 的 StateGraph 心智模型，零依赖）。

特性（对齐生产编排所需）：
- 显式节点序列 + 确定性路由（不靠 LLM 字符串匹配选下一步）。
- checkpoint 持久化：每步快照，支持崩溃/中断后恢复。
- HITL 中断：节点把 state 置为 NEEDS_HUMAN 即暂停，approve 后 resume 继续。
- 安全停机：HALTED / BLOCKED 立即停止，不继续推进。

真实接入时可把每个节点替换为 LangGraph 节点、checkpointer 换成 Postgres/Redis。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from aiforge.orchestration.agents import ROLE_NODES, AgentContext
from aiforge.orchestration.state import PipelineState, Status

NodeFn = Callable[[PipelineState, AgentContext], PipelineState]

# 推进会停止的状态（HITL / 安全停机 / 门禁阻断）
_STOP_STATES = {Status.NEEDS_HUMAN, Status.HALTED, Status.BLOCKED}


class InMemoryCheckpointer:
    """按 feature_id 保存每步快照，支持取最新恢复。"""

    def __init__(self) -> None:
        self._store: dict[str, list[PipelineState]] = {}

    def save(self, state: PipelineState) -> None:
        self._store.setdefault(state.feature_id, []).append(copy.deepcopy(state))

    def latest(self, feature_id: str) -> PipelineState | None:
        snaps = self._store.get(feature_id)
        return copy.deepcopy(snaps[-1]) if snaps else None

    def history(self, feature_id: str) -> list[PipelineState]:
        return list(self._store.get(feature_id, []))


@dataclass
class Supervisor:
    nodes: list[str]
    ctx: AgentContext
    node_impls: dict[str, NodeFn] = field(default_factory=lambda: dict(ROLE_NODES))
    checkpointer: InMemoryCheckpointer = field(default_factory=InMemoryCheckpointer)

    def _next_index(self, state: PipelineState) -> int:
        """根据已完成的 current_node 确定从哪个节点继续（支持 resume）。"""
        if state.current_node is None:
            return 0
        if state.current_node in self.nodes:
            return self.nodes.index(state.current_node) + 1
        return 0

    def invoke(self, state: PipelineState, start_index: int = 0) -> PipelineState:
        state.status = Status.RUNNING
        for idx in range(start_index, len(self.nodes)):
            node_name = self.nodes[idx]
            impl = self.node_impls[node_name]
            state = impl(state, self.ctx)
            self.checkpointer.save(state)
            if state.status in _STOP_STATES:
                state.log("supervisor", "interrupted", at=node_name, status=state.status.value)
                return state
        if state.status not in _STOP_STATES:
            state.status = Status.DONE
        self.checkpointer.save(state)
        return state

    def resume(self, feature_id: str, approve: bool = True) -> PipelineState:
        """从 checkpoint 恢复。approve=True 表示人审通过，继续后续节点。"""
        state = self.checkpointer.latest(feature_id)
        if state is None:
            raise KeyError(f"无 {feature_id} 的 checkpoint 可恢复")
        if state.status == Status.HALTED and not approve:
            return state
        if state.status in (Status.NEEDS_HUMAN, Status.HALTED) and approve:
            state.needs_human_reason = None
            state.status = Status.RUNNING
            if self.ctx.audit is not None:
                self.ctx.audit.record("human", "approve", feature_id)
        elif state.status == Status.BLOCKED:
            # 门禁阻断不允许人工"绕过"，必须修复后重跑（宪法 P3）
            return state
        return self.invoke(state, start_index=self._next_index(state))


DEFAULT_PIPELINE = ["analyst", "architect", "tasks", "developer", "reviewer", "tester", "verifier"]


def build_default_pipeline(ctx: AgentContext | None = None) -> Supervisor:
    return Supervisor(nodes=list(DEFAULT_PIPELINE), ctx=ctx or AgentContext())
