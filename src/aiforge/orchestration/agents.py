"""角色 agent（Analyst / Architect / Developer / Reviewer / Tester）。

每个角色是一个对 PipelineState 操作的节点函数；角色间只经 PipelineState 通信。
共享依赖打包进 AgentContext（llm / runtime / 权限 / 审计 / skills / 治理配置），
便于把 mock 替换为真实实现（宪法 P9）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.context.skills import SkillRegistry
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.llm import LLMClient, MockLLM
from aiforge.orchestration.state import (
    Artifact,
    ArtifactKind,
    FileChange,
    PipelineState,
    Status,
    Task,
)
from aiforge.runtime.base import Runtime, SafeHaltError


@dataclass
class AgentContext:
    llm: LLMClient = field(default_factory=MockLLM)
    runtime: Optional[Runtime] = None
    permissions: Optional[PermissionBroker] = None
    audit: Optional[AuditTrail] = None
    skills: SkillRegistry = field(default_factory=SkillRegistry)
    config: GovernanceConfig = DEFAULT_GOVERNANCE
    # 由 Developer 落盘的文件内容缓存：path -> text
    file_contents: Dict[str, str] = field(default_factory=dict)


def _emit(ctx: AgentContext, actor: str, action: str, target: str, **detail: object) -> None:
    if ctx.audit is not None:
        ctx.audit.record(actor, action, target, **detail)


def analyst_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """需求澄清 + 验收标准（产出 SPEC 的雏形，供规格驱动对照）。"""
    state.current_node = "analyst"
    out = ctx.llm.complete("You are the Analyst.", state.request)
    spec = state.add_artifact(
        Artifact(ArtifactKind.SPEC, out, "analyst", refs=[state.feature_id])
    )
    _emit(ctx, "analyst", "decision", "spec", artifact_refs=spec.refs)
    state.log("analyst", "produced_spec")
    return state


def architect_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """模块边界 + 数据流（产出 PLAN，引用 SPEC，保证可追溯 P2）。"""
    state.current_node = "architect"
    spec = state.latest(ArtifactKind.SPEC)
    out = ctx.llm.complete("You are the Architect.", spec.content if spec else state.request)
    refs = [a.kind.value for a in state.artifacts if a.kind == ArtifactKind.SPEC]
    state.add_artifact(Artifact(ArtifactKind.PLAN, out, "architect", refs=refs))
    state.log("architect", "produced_plan")
    return state


def planner_tasks(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """任务拆分（产出 TASKS，每个任务回链到需求 P2）。"""
    state.current_node = "tasks"
    plan = state.latest(ArtifactKind.PLAN)
    out = ctx.llm.complete("You are the Architect.", "拆分任务: " + (plan.content if plan else ""))
    state.add_artifact(Artifact(ArtifactKind.TASKS, out, "architect", refs=["plan"]))
    if not state.tasks:
        state.tasks = [
            Task(id=f"{state.feature_id}-t1", title="实现核心逻辑", task_type=state.task_type, refs=["AC1"]),
            Task(id=f"{state.feature_id}-t2", title="补充错误处理与日志", task_type="feature", refs=["AC2"]),
        ]
    state.log("tasks", "produced_tasks", n=len(state.tasks))
    return state


def developer_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """实现：经 runtime 沙箱落盘（强制权限 + blast radius + 安全停机）。"""
    state.current_node = "developer"
    out = ctx.llm.complete("You are the Developer.", state.request)
    code_path = f"src/feature_{state.feature_id}.py"
    body = f'"""Generated for {state.feature_id}."""\n\n# {out}\n\n\ndef run():\n    return "{state.feature_id}"\n'
    ctx.file_contents[code_path] = body
    change = FileChange(path=code_path, added_lines=body.count("\n") + 1)
    state.file_changes.append(change)
    state.add_artifact(Artifact(ArtifactKind.CODE, code_path, "developer", refs=["tasks"]))

    if ctx.runtime is not None:
        if ctx.permissions is not None:
            ctx.permissions.grant("developer", "write", reason="实现任务需要写代码")
        try:
            ctx.runtime.apply("developer", [change], ctx.file_contents)
        except SafeHaltError as exc:
            state.status = Status.HALTED
            state.needs_human_reason = str(exc)
            _emit(ctx, "developer", "halt", code_path, reason=str(exc))
            state.log("developer", "safe_halt", reason=str(exc))
            return state
    state.log("developer", "produced_code", path=code_path)
    return state


def reviewer_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """审查：检查非功能需求（80% 问题）。高风险变更标记 HITL。"""
    state.current_node = "reviewer"
    out = ctx.llm.complete("You are the Reviewer.", state.request)
    state.add_artifact(Artifact(ArtifactKind.REVIEW, out, "reviewer", refs=["code"]))
    if ctx.config.requires_human_review(state.task_type, state.files_changed, state.lines_changed):
        state.status = Status.NEEDS_HUMAN
        state.needs_human_reason = (
            f"task_type={state.task_type} 或改动面超限，强制人审（HITL）"
        )
        _emit(ctx, "reviewer", "decision", "hitl", reason=state.needs_human_reason)
        state.log("reviewer", "needs_human", reason=state.needs_human_reason)
    return state


def tester_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """生成测试（产出 TEST，引用 CODE）。"""
    state.current_node = "tester"
    out = ctx.llm.complete("You are the Tester.", state.request)
    test_path = f"tests/test_feature_{state.feature_id}.py"
    body = f"def test_{state.feature_id}():\n    # {out}\n    assert True\n"
    ctx.file_contents[test_path] = body
    state.file_changes.append(FileChange(path=test_path, added_lines=body.count("\n") + 1))
    state.add_artifact(Artifact(ArtifactKind.TEST, test_path, "tester", refs=["code"]))
    state.log("tester", "produced_tests", path=test_path)
    return state


ROLE_NODES = {
    "analyst": analyst_node,
    "architect": architect_node,
    "tasks": planner_tasks,
    "developer": developer_node,
    "reviewer": reviewer_node,
    "tester": tester_node,
}
