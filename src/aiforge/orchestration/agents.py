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


def _dev_prompt(state: PipelineState) -> str:
    spec = state.latest(ArtifactKind.SPEC)
    return (f"需求：{state.request}\n规格：{spec.content if spec else state.request}\n"
            "只输出实现该需求的 Python，定义顶层 `solution`（可用 ```python 围栏）。不要解释。")


def developer_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """实现（修 C1）：用 LLM 产出**成为真代码**（非注释），非法/无 solution → 安全停机（不造假 stub）；
    经 runtime 沙箱落盘（强制权限 + blast radius + 安全停机，保留 P4/P5）。"""
    from aiforge.orchestration.codegen import defines_solution, extract_code  # 延迟导入避免既有循环
    state.current_node = "developer"
    code = extract_code(ctx.llm.complete("You are the Developer. 只输出代码。", _dev_prompt(state)), defines_solution)
    if not code:
        state.status = Status.HALTED
        state.needs_human_reason = "developer 未产出合法且定义 solution 的代码（无真实 codegen 时安全停机，不造假 stub）"
        _emit(ctx, "developer", "halt", "code", reason=state.needs_human_reason)
        state.log("developer", "safe_halt", reason=state.needs_human_reason)
        return state
    code_path = f"solution_{state.feature_id}.py"
    ctx.file_contents[code_path] = code
    change = FileChange(path=code_path, added_lines=code.count("\n") + 1)
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
    """生成**真实测试**（修 C1，不再 assert True）；非法/不引用 solution → 安全停机。"""
    from aiforge.orchestration.codegen import extract_code, is_test_module
    state.current_node = "tester"
    test_prompt = f"为需求写 unittest：import solution 并断言其行为，类继承 unittest.TestCase。需求：{state.request}"
    test_src = extract_code(ctx.llm.complete("You are the Tester. 只输出测试代码。", test_prompt), is_test_module)
    if not test_src:
        state.status = Status.HALTED
        state.needs_human_reason = "tester 未产出合法且引用 solution 的测试（无真实 codegen 时安全停机）"
        state.log("tester", "safe_halt", reason=state.needs_human_reason)
        return state
    test_path = f"test_solution_{state.feature_id}.py"
    ctx.file_contents[test_path] = test_src
    state.file_changes.append(FileChange(path=test_path, added_lines=test_src.count("\n") + 1))
    state.add_artifact(Artifact(ArtifactKind.TEST, test_path, "tester", refs=["code"]))
    state.log("tester", "produced_tests", path=test_path)
    return state


def verifier_node(state: PipelineState, ctx: AgentContext) -> PipelineState:
    """在 C4 隔离 runtime 里**真跑**生成的测试，记录真实 tests_ok（修 C1/缓解 C3）。

    无可用真隔离 → fail-closed（BLOCKED，不在无隔离下执行不可信代码）。"""
    from aiforge.orchestration.codegen import run_generated, select_isolated_or_none
    state.current_node = "verifier"
    code = state.latest(ArtifactKind.CODE)
    test = state.latest(ArtifactKind.TEST)
    if code is None or test is None:
        return state  # 上游已停机/无产物
    code_src = ctx.file_contents.get(code.content, "")
    test_src = ctx.file_contents.get(test.content, "")
    sandbox = select_isolated_or_none()
    if sandbox is None:
        state.status = Status.BLOCKED
        state.needs_human_reason = "无可用真隔离 runtime（C4），拒绝执行生成代码做验证"
        state.verification = {"tests_ok": False, "reason": "no-isolation"}
        state.log("verifier", "blocked", reason=state.needs_human_reason)
        return state
    vr = run_generated(code_src, test_src, isolated_runtime=sandbox)
    state.verification = {"tests_ok": vr.tests_ok, "reason": vr.reason, "tests_run": vr.tests_run}
    state.log("verifier", "verified", tests_ok=vr.tests_ok, reason=vr.reason)
    if not vr.tests_ok:
        state.status = Status.BLOCKED
        state.needs_human_reason = f"验证未过: {vr.reason}"
        _emit(ctx, "verifier", "decision", "blocked", reason=vr.reason)
    return state


ROLE_NODES = {
    "analyst": analyst_node,
    "architect": architect_node,
    "tasks": planner_tasks,
    "developer": developer_node,
    "reviewer": reviewer_node,
    "tester": tester_node,
    "verifier": verifier_node,
}
