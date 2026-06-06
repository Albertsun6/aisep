"""AIForge CLI：``demo`` 端到端编排、``eval`` 跑四指标、``dashboard`` 生成看板。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from aiforge.dashboard import write_dashboard
from aiforge.eval.harness import run_eval
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.governance.review import review_after_session
from aiforge.llm import StubCodeLLM
from aiforge.orchestration.agents import AgentContext
from aiforge.orchestration.graph import build_default_pipeline
from aiforge.orchestration.state import PipelineState, Status
from aiforge.runtime.local import LocalSandbox


def _cmd_demo(args: argparse.Namespace) -> int:
    audit = AuditTrail(path=None)
    perms = PermissionBroker(audit=audit)
    perms.grant("developer", "write", reason="demo")
    runtime = LocalSandbox(perms, audit=audit)
    ctx = AgentContext(runtime=runtime, permissions=perms, audit=audit, llm=StubCodeLLM())

    supervisor = build_default_pipeline(ctx)
    state = PipelineState(feature_id=args.feature, request=args.request, task_type=args.task_type)
    state = supervisor.invoke(state)

    print(f"== 流水线结束: status={state.status.value} 节点止于 {state.current_node} ==")
    print(f"产出 artifact: {[a.kind.value for a in state.artifacts]}")
    print(f"改动文件: {state.files_changed} 个 / {state.lines_changed} 行")

    if state.status == Status.NEEDS_HUMAN:
        print(f"[HITL] 需人审: {state.needs_human_reason}")
        review = review_after_session(state.file_changes, ctx.config)
        print("三文件 review 清单:")
        for item in review.items:
            mark = "必读" if item.must_fully_review else "抽审"
            print(f"  - [{mark}] {item.path} ({item.lines_changed} 行) — {item.reason}")
        if args.approve:
            print("[HITL] 人审通过，恢复流水线...")
            state = supervisor.resume(state.feature_id, approve=True)
            print(f"== 恢复后: status={state.status.value} ==")

    print(f"审计事件数: {len(audit)}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    report = run_eval(dataset_path=args.dataset)
    print(json.dumps(report.metrics.as_dict(), ensure_ascii=False, indent=2))
    if args.dashboard:
        path = write_dashboard(report, args.dashboard)
        print(f"看板已生成: {path}")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    report = run_eval(dataset_path=args.dataset)
    path = write_dashboard(report, args.out)
    print(f"看板已生成: {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="aiforge", description="AI 工程化开发系统")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="端到端规格驱动 + 多 agent 编排")
    p_demo.add_argument("--feature", default="DEMO1")
    p_demo.add_argument("--request", default="新增一个示例功能")
    p_demo.add_argument("--task-type", dest="task_type", default="feature")
    p_demo.add_argument("--approve", action="store_true", help="HITL 中断时自动批准并恢复")
    p_demo.set_defaults(func=_cmd_demo)

    p_eval = sub.add_parser("eval", help="跑 eval 集，输出四个生产指标")
    p_eval.add_argument("--dataset", default="eval/dataset.jsonl")
    p_eval.add_argument("--dashboard", default=None, help="同时生成看板到该路径")
    p_eval.set_defaults(func=_cmd_eval)

    p_dash = sub.add_parser("dashboard", help="生成四指标看板 HTML")
    p_dash.add_argument("--dataset", default="eval/dataset.jsonl")
    p_dash.add_argument("--out", default="dashboard/index.html")
    p_dash.set_defaults(func=_cmd_dashboard)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
