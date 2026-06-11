"""AIForge CLI：``demo``/``eval``/``dashboard`` + STEP 0 门禁子命令(gate-* / review-3f)。

门禁子命令永不调模型(契约 04);退出码 0/1/2/3 见契约 03。
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path
from typing import Callable

# 注意:demo/eval/dashboard 的依赖全部 lazy import(评审:gate 子命令路径不得
# 提前加载非 gate 模块,守住契约 04 的 import 边界)。


def _cmd_demo(args: argparse.Namespace) -> int:
    from aiforge.governance.audit import AuditTrail
    from aiforge.governance.permissions import PermissionBroker
    from aiforge.governance.review import review_after_session
    from aiforge.llm import StubCodeLLM
    from aiforge.orchestration.agents import AgentContext
    from aiforge.orchestration.graph import build_default_pipeline
    from aiforge.orchestration.state import PipelineState, Status
    from aiforge.runtime.local import LocalSandbox

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

    if args.csv:
        rc = _export_artifacts_csv(state, args.csv)
        if rc != 0:
            return rc

    print(f"审计事件数: {len(audit)}")
    return 0


def _export_artifacts_csv(state, dest: str) -> int:
    """spec: specs/toy-csv-export — 产物清单导出 CSV(父目录缺失 → stderr + 非 0)。"""
    import csv
    from datetime import datetime

    out = Path(dest)
    if not out.parent.exists():
        print(f"[error] CSV 目标目录不存在: {out.parent}(不自动创建,请先建目录)", file=sys.stderr)
        return 1
    try:
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["kind", "produced_by", "refs", "created_at"])
            for a in state.artifacts:
                writer.writerow([
                    a.kind.value, a.produced_by, " ".join(a.refs),
                    datetime.fromtimestamp(a.created_at).astimezone().isoformat(),
                ])
    except OSError as exc:  # 路径不可写/是目录/权限——spec 非功能:非 0 + 可读诊断
        print(f"[error] CSV 写入失败: {out} — {exc}", file=sys.stderr)
        return 1
    print(f"已导出 {len(state.artifacts)} 行 → {out}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from aiforge.eval.harness import run_eval
    report = run_eval(dataset_path=args.dataset)
    if report.not_production_metric:
        print("⚠️  合成门禁路由自测（StubReviewer + 合成 evidence）——**非生产能力指标**。"
              "真实能力需真实 LLM + 独立 oracle 测试 + 真覆盖率/SAST 工具。")
    print(json.dumps({"kind": report.kind, **report.metrics.as_dict()}, ensure_ascii=False, indent=2))
    if args.dashboard:
        from aiforge.dashboard import write_dashboard
        path = write_dashboard(report, args.dashboard)
        print(f"看板已生成: {path}")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from aiforge.dashboard import write_dashboard
    from aiforge.eval.harness import run_eval
    report = run_eval(dataset_path=args.dataset)
    path = write_dashboard(report, args.out)
    print(f"看板已生成: {path}")
    return 0


# ---------------------------------------------------------- STEP 0 门禁子命令

def _infra_guard(fn: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
    """契约 03:受控路径内未预期异常 → 3 + 可读诊断,绝不含混退出。"""
    @functools.wraps(fn)
    def wrapper(args: argparse.Namespace) -> int:
        from aiforge.harness import InfraError
        try:
            return fn(args)
        except InfraError as exc:
            print(f"[infra] {exc}", file=sys.stderr)
            return 3
        except Exception as exc:  # noqa: BLE001 — fail-closed 兜底
            print(f"[infra] 未预期异常({type(exc).__name__}): {exc}", file=sys.stderr)
            return 3
    return wrapper


def _emit(gate: str, decision: str, msgs: list[str]) -> int:
    from aiforge.harness import exit_code
    for m in msgs:
        print(m)
    code = exit_code(decision)
    print(f"{gate}: {decision} (exit {code})")
    return code


@_infra_guard
def _cmd_gate_spec(args: argparse.Namespace) -> int:
    from aiforge import harness
    spec = Path(args.spec)
    root = harness.find_repo_root(spec if spec.exists() else Path.cwd())
    fid = harness.derive_feature_id(spec, root, args.feature)
    decision, msgs = harness.gate_spec(spec, root, fid, argv=["gate-spec", args.spec])
    return _emit("gate-spec", decision, msgs)


@_infra_guard
def _cmd_gate_trace(args: argparse.Namespace) -> int:
    from aiforge import harness
    d = Path(args.dir)
    root = harness.find_repo_root(d if d.exists() else Path.cwd())
    decision, msgs = harness.gate_trace(d, root, argv=["gate-trace", args.dir])
    return _emit("gate-trace", decision, msgs)


@_infra_guard
def _cmd_gate_judge(args: argparse.Namespace) -> int:
    import hashlib

    from aiforge import harness
    root = harness.find_repo_root(Path.cwd())
    if args.base:
        diff = harness.range_diff(root, args.base)
    else:
        diff = harness.staged_diff(root, staged=args.staged)
    decision, findings = harness.judge_diff(diff)
    msgs = [f"[{f['severity']}] {f['issue']}(静态扫描只升级人审,不裁决)" for f in findings]
    if decision == harness.NEEDS_HUMAN:
        msgs.append("人审清单:确认上述命中是误报或已有补偿控制,放行走契约 07 通道")
    argv = ["gate-judge"] + (["--staged"] if args.staged else []) \
        + (["--base", args.base] if args.base else []) \
        + (["--feature", args.feature] if args.feature else [])
    diff_label = f"<range-diff:{args.base}...HEAD>" if args.base else (
        "<staged-diff>" if args.staged else "<worktree-diff>")
    receipt = harness.build_receipt(
        gate="gate-judge", feature_id=args.feature or harness.WORKSPACE_FEATURE,
        inputs=[{"path": diff_label,
                 "sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest()}],
        decision=decision, repo_root=root, argv=argv,
    )
    harness.write_receipt(receipt, root)
    return _emit("gate-judge", decision, msgs)


@_infra_guard
def _cmd_review_3f(args: argparse.Namespace) -> int:
    from aiforge import harness
    root = harness.find_repo_root(Path.cwd())
    items = harness.review_items(harness.staged_numstat(root, staged=args.staged))
    print("三文件 review 清单:" if items else "无改动,无需 review。")
    for line in items:
        print(f"  - {line}")
    return 0


@_infra_guard
def _cmd_gate_commit(args: argparse.Namespace) -> int:
    from aiforge import harness
    root = harness.find_repo_root(Path.cwd())
    argv = ["gate-commit"] + (["--feature", args.feature] if args.feature else []) \
        + (["--ci"] if args.ci else []) + (["--ack-human"] if args.ack_human else [])
    decision, msgs = harness.gate_commit(
        root, feature=args.feature, ack_human=args.ack_human, ci=args.ci, argv=argv,
    )
    return _emit("gate-commit", decision, msgs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aiforge", description="AI 工程化开发系统")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="端到端规格驱动 + 多 agent 编排")
    p_demo.add_argument("--feature", default="DEMO1")
    p_demo.add_argument("--request", default="新增一个示例功能")
    p_demo.add_argument("--task-type", dest="task_type", default="feature")
    p_demo.add_argument("--approve", action="store_true", help="HITL 中断时自动批准并恢复")
    p_demo.add_argument("--csv", default=None, help="把产物清单导出为 CSV(spec: specs/toy-csv-export)")
    p_demo.set_defaults(func=_cmd_demo)

    p_eval = sub.add_parser("eval", help="跑 eval 集，输出四个生产指标")
    p_eval.add_argument("--dataset", default="eval/dataset.jsonl")
    p_eval.add_argument("--dashboard", default=None, help="同时生成看板到该路径")
    p_eval.set_defaults(func=_cmd_eval)

    p_dash = sub.add_parser("dashboard", help="生成四指标看板 HTML")
    p_dash.add_argument("--dataset", default="eval/dataset.jsonl")
    p_dash.add_argument("--out", default="dashboard/index.html")
    p_dash.set_defaults(func=_cmd_dashboard)

    p_gs = sub.add_parser("gate-spec", help="P1: 校验 spec.md 验收结构(0/1/3)")
    p_gs.add_argument("spec", help="spec.md 路径")
    p_gs.add_argument("--feature", default=None, help="feature id(默认从 specs/<id>/ 推导)")
    p_gs.set_defaults(func=_cmd_gate_spec)

    p_gt = sub.add_parser("gate-trace", help="P2: 校验 specs/<id>/ 文档追溯链(0/1/3)")
    p_gt.add_argument("dir", help="specs/<id>/ 目录")
    p_gt.set_defaults(func=_cmd_gate_trace)

    p_gj = sub.add_parser("gate-judge", help="静态风险三态:0=过 2=转人审(永不调模型)")
    p_gj.add_argument("--staged", action="store_true", help="审 git diff --cached(默认审 HEAD 起的全部改动)")
    p_gj.add_argument("--base", default=None, help="CI 用:审 <base>...HEAD 范围 diff")
    p_gj.add_argument("--feature", default=None)
    p_gj.set_defaults(func=_cmd_gate_judge)

    p_r3 = sub.add_parser("review-3f", help="P7: 三文件 review 必读清单(信息性,exit 0)")
    p_r3.add_argument("--staged", action="store_true")
    p_r3.set_defaults(func=_cmd_review_3f)

    p_gc = sub.add_parser("gate-commit", help="聚合门禁:feature 声明+receipt 链+lint+judge(0/1/2/3)")
    p_gc.add_argument("--feature", default=None, help="本次改动所属 feature(或 env AIFORGE_FEATURE)")
    p_gc.add_argument("--ack-human", action="store_true", dest="ack_human",
                      help="本地人审 ack(仅审计;需 tty;CI 不消费)")
    p_gc.add_argument("--ci", action="store_true", help="CI 模式:忽略本地 ack(只收紧)")
    p_gc.set_defaults(func=_cmd_gate_commit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
