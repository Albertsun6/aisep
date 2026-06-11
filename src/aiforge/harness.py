"""文件/git → aiforge 门禁适配层(STEP 0 v2 M1 薄 CLI 核心)。

把吃 PipelineState 的复用核门禁(SpecGate / StaticRiskScanner / review_after_session)
适配到"文件 + git diff"输入,并落 gate receipt(契约 06)。全部 stdlib,**永不调模型**(契约 04)。

退出码契约(契约 03,单点 mapper 见 EXIT):0=approved / 1=rejected / 2=needs_human / 3=infra_error。
诚实边界:
- gate-trace 只校验文档链(spec←plan←tasks 的声明式 refs);代码↔feature 的关联走声明制
  (契约 02:--feature / AIFORGE_FEATURE)由 gate-commit 强制,不在 trace 内。
- isatty / user 信息是审计信号,不是身份认证(契约 07)。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import aiforge
from aiforge.governance.review import review_after_session
from aiforge.orchestration.state import Artifact, ArtifactKind, FileChange, PipelineState
from aiforge.quality.gates import SpecGate
from aiforge.quality.judge import StaticRiskScanner

RECEIPT_SCHEMA_VERSION = 1
APPROVED, REJECTED, NEEDS_HUMAN, INFRA = "approved", "rejected", "needs_human", "infra_error"
# 契约 03:result mapper 单点——受控路径只经由这里产生退出码
EXIT: dict[str, int] = {APPROVED: 0, REJECTED: 1, NEEDS_HUMAN: 2, INFRA: 3}

WORKSPACE_FEATURE = "_workspace"
_CODE_PREFIXES = ("src/", "tests/")
_REFS_RE = re.compile(r"^\s*>?\s*refs:\s*(.+?)\s*$", re.MULTILINE)


class InfraError(RuntimeError):
    """基础设施错误(契约 03 的 3):带可读诊断,绝不静默放行。"""


def exit_code(decision: str) -> int:
    return EXIT[decision]


# ---------------------------------------------------------------- git helpers

def _git(repo_root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:  # git 本体缺失
        raise InfraError(f"git 不可用: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise InfraError(f"git {' '.join(args)} 失败: {exc.stderr.strip()}") from exc
    return out.stdout


def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for cand in (cur, *cur.parents):
        if (cand / ".git").exists():
            return cand
    raise InfraError(f"{start} 不在 git 仓库内(receipt 需要 repo root 与 HEAD)")


def _git_state(repo_root: Path) -> tuple[str | None, bool | None]:
    try:
        head = _git(repo_root, "rev-parse", "HEAD").strip() or None
    except InfraError:
        head = None  # 空仓库无 HEAD:记 null,不阻断(receipt 仍有 inputs hash)
    try:
        dirty = bool(_git(repo_root, "status", "--porcelain").strip())
    except InfraError:
        dirty = None
    return head, dirty


def staged_diff(repo_root: Path, staged: bool = True) -> str:
    return _git(repo_root, "diff", "--cached") if staged else _git(repo_root, "diff", "HEAD")


def staged_numstat(repo_root: Path, staged: bool = True) -> str:
    args = ["diff", "--numstat"] + (["--cached"] if staged else ["HEAD"])
    return _git(repo_root, *args)


def staged_paths(repo_root: Path) -> list[str]:
    return [p for p in _git(repo_root, "diff", "--cached", "--name-only").splitlines() if p]


# ------------------------------------------------------------- hash & receipt

def sha256_file(path: Path) -> str:
    """契约 09:对原始字节计算;symlink 输入 → infra(不跟随)。"""
    if path.is_symlink():
        raise InfraError(f"{path} 是 symlink,gate 输入不跟随 symlink(契约 09)")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel_posix(path: Path, repo_root: Path) -> str:
    return str(PurePosixPath(*path.resolve().relative_to(repo_root.resolve()).parts))


def build_receipt(
    *,
    gate: str,
    feature_id: str,
    inputs: list[dict[str, str]],
    decision: str,
    repo_root: Path,
    argv: list[str],
    ack: dict | None = None,
    reviewer: dict | None = None,
) -> dict:
    head, dirty = _git_state(repo_root)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "gate": gate,
        "feature_id": feature_id,
        "inputs": inputs,
        "exit_code": EXIT[decision],
        "decision": decision,
        "git_head": head,
        "git_dirty": dirty,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "tool": f"aiforge {gate}",
        "aiforge_version": getattr(aiforge, "__version__", "0"),
        "argv": argv,
        "ack": ack,
        "reviewer": reviewer,
    }


def write_receipt(receipt: dict, repo_root: Path) -> Path:
    dest = repo_root / "specs" / receipt["feature_id"] / "gates" / f"{receipt['gate']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def load_receipt(path: Path) -> dict:
    """契约 06/09:不可解析/版本不识别 → InfraError(3),带可读诊断;未知字段忽略。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InfraError(f"receipt 不可解析: {path}(建议删除后重跑对应 gate)— {exc}") from exc
    ver = data.get("schema_version")
    if not isinstance(ver, int) or ver > RECEIPT_SCHEMA_VERSION:
        raise InfraError(
            f"receipt schema_version={ver!r} 高于已知 {RECEIPT_SCHEMA_VERSION}: {path}"
            "(升级 aiforge 或检查该文件来源)"
        )
    return data


# --------------------------------------------------------------------- gates

def derive_feature_id(spec_path: Path, repo_root: Path, declared: str | None) -> str:
    if declared:
        return declared
    try:
        rel = spec_path.resolve().relative_to(repo_root.resolve())
        if len(rel.parts) >= 3 and rel.parts[0] == "specs":
            return rel.parts[1]
    except ValueError:
        pass
    return WORKSPACE_FEATURE


def gate_spec(spec_path: Path, repo_root: Path, feature_id: str, argv: list[str]) -> tuple[str, list[str]]:
    msgs: list[str] = []
    inputs: list[dict[str, str]] = []
    if spec_path.is_symlink():
        raise InfraError(f"{spec_path} 是 symlink(契约 09)")
    if not spec_path.exists() or not spec_path.read_text(encoding="utf-8").strip():
        decision, msgs = REJECTED, ["P1: 无 spec / spec 为空,拒绝推进"]
    else:
        inputs = [{"path": _rel_posix(spec_path, repo_root), "sha256": sha256_file(spec_path)}]
        state = PipelineState(feature_id=feature_id, request="harness:gate-spec")
        state.add_artifact(Artifact(kind=ArtifactKind.SPEC, content=spec_path.read_text(encoding="utf-8"), produced_by="file"))
        res = SpecGate().check(state, {})
        decision = APPROVED if res.passed else REJECTED
        if not res.passed:
            msgs = [res.reason, "缺什么:验收结构需 Gherkin(Given/When/Then) 或 EARS(shall+when/if/while/where) 或 User Story+验收标记,且 ≥40 字符"]
    receipt = build_receipt(gate="gate-spec", feature_id=feature_id, inputs=inputs,
                            decision=decision, repo_root=repo_root, argv=argv)
    write_receipt(receipt, repo_root)
    return decision, msgs


_CHAIN = (("plan.md", "spec.md"), ("tasks.md", "plan.md"))


def gate_trace(feature_dir: Path, repo_root: Path, argv: list[str]) -> tuple[str, list[str]]:
    """P2 语义(文档链):每个存在的下游必须声明 refs 且解析到存在的上游。"""
    msgs: list[str] = []
    spec = feature_dir / "spec.md"
    if not spec.exists() or not spec.read_text(encoding="utf-8").strip():
        decision = REJECTED
        msgs = [f"P2: {feature_dir} 缺 spec.md,追溯链无根"]
    else:
        decision = APPROVED
        for down_name, up_name in _CHAIN:
            down = feature_dir / down_name
            if not down.exists():
                continue
            declared = " ".join(_REFS_RE.findall(down.read_text(encoding="utf-8")))
            if up_name not in declared:
                decision, msgs = REJECTED, [f"P2: {down_name} 未声明上游 refs(需含 `> refs: {up_name}`)"]
                break
            if not (feature_dir / up_name).exists():
                decision, msgs = REJECTED, [f"P2: {down_name} 声明的上游 {up_name} 不存在,链断"]
                break
    inputs = [
        {"path": _rel_posix(p, repo_root), "sha256": sha256_file(p)}
        for p in (feature_dir / n for n in ("spec.md", "plan.md", "tasks.md"))
        if p.exists()
    ]
    fid = derive_feature_id(feature_dir / "spec.md", repo_root, None)
    if fid == WORKSPACE_FEATURE:
        fid = feature_dir.name
    receipt = build_receipt(gate="gate-trace", feature_id=fid, inputs=inputs,
                            decision=decision, repo_root=repo_root, argv=argv)
    write_receipt(receipt, repo_root)
    return decision, msgs


def judge_diff(diff_text: str) -> tuple[str, list[dict]]:
    """纯静态三态(契约 04):扫描命中只升级人审,不硬拒、不放行。"""
    findings = StaticRiskScanner().scan(diff_text)
    return (NEEDS_HUMAN if findings else APPROVED), findings


def review_items(numstat_text: str) -> list[str]:
    changes: list[FileChange] = []
    for line in numstat_text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-" or parts[1] == "-":
            continue
        changes.append(FileChange(path=parts[2], added_lines=int(parts[0]), removed_lines=int(parts[1])))
    review = review_after_session(changes)
    return [
        f"[{'必读' if i.must_fully_review else '抽审'}] {i.path} ({i.lines_changed} 行) — {i.reason}"
        for i in review.items
    ]


# ----------------------------------------------------------------- gate-commit

def check_receipt_chain(repo_root: Path, feature_id: str) -> str | None:
    """契约 06 链校验:问题返回描述(→1);receipt 坏/版本不识别抛 InfraError(→3)。"""
    spec = repo_root / "specs" / feature_id / "spec.md"
    if not spec.exists():
        return f"{feature_id}: 无 specs/{feature_id}/spec.md(无 spec 的代码改动,拒绝)"
    rcpt_path = repo_root / "specs" / feature_id / "gates" / "gate-spec.json"
    if not rcpt_path.exists():
        return f"{feature_id}: 缺 gate-spec receipt(先跑 python -m aiforge gate-spec specs/{feature_id}/spec.md)"
    rcpt = load_receipt(rcpt_path)
    if rcpt.get("decision") != APPROVED:
        return f"{feature_id}: gate-spec receipt decision={rcpt.get('decision')},非 approved"
    want = {i.get("path"): i.get("sha256") for i in rcpt.get("inputs", [])}
    rel = _rel_posix(spec, repo_root)
    if want.get(rel) != sha256_file(spec):
        return f"{feature_id}: receipt 过期/伪造(spec.md hash 不符),重跑 gate-spec"
    return None


def _ack_info() -> dict:
    fd = sys.stdin.fileno() if hasattr(sys.stdin, "fileno") else 0
    try:
        tty = os.ttyname(fd)
    except (OSError, ValueError):
        tty = None
    return {
        "user": os.environ.get("USER") or "unknown",
        "uid": os.getuid(),
        "hostname": socket.gethostname(),
        "tty": tty,
        "at": datetime.now(timezone.utc).astimezone().isoformat(),
    }


def _run_lint(repo_root: Path) -> tuple[str, list[str]]:
    """PreCommitGate 语义(fails-closed):lint 证据必须真实产生;工具缺失=infra。"""
    targets = [d for d in ("src", "tests") if (repo_root / d).is_dir()]
    if not targets:
        return APPROVED, []  # 无可 lint 对象,证据空集但非缺失
    cmd = [sys.executable, "-m", "ruff", "check", *targets]
    try:
        proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise InfraError(f"无法执行 {cmd[0]}: {exc}") from exc
    if "No module named" in (proc.stderr or ""):
        raise InfraError("ruff 不可用(P3 缺 lint 证据,fails-closed):pip install -r requirements-dev.txt")
    if proc.returncode != 0:
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-10:]
        return REJECTED, ["lint 未通过:", *tail]
    return APPROVED, []


def gate_commit(
    repo_root: Path,
    *,
    feature: str | None,
    ack_human: bool,
    ci: bool,
    argv: list[str],
) -> tuple[str, list[str]]:
    msgs: list[str] = []
    ci_mode = ci or bool(os.environ.get("CI"))  # 契约 07:CI 标记只收紧,不放宽
    declared = feature or os.environ.get("AIFORGE_FEATURE") or None

    paths = staged_paths(repo_root)
    # ① feature 声明制(契约 02)
    code_touched = any(p.startswith(_CODE_PREFIXES) for p in paths)
    if code_touched and not declared:
        return REJECTED, ["src/tests 改动必须声明 feature:--feature <id> 或 AIFORGE_FEATURE=<id>(契约 02)"]
    # ② receipt 链(声明 feature + staged 里出现的 specs/<id>/)
    ids = set([declared] if declared else [])
    for p in paths:
        parts = PurePosixPath(p).parts
        if len(parts) >= 2 and parts[0] == "specs" and parts[1] != "contracts":
            ids.add(parts[1])
    ids.discard(WORKSPACE_FEATURE)
    for fid in sorted(i for i in ids if i):
        problem = check_receipt_chain(repo_root, fid)
        if problem:
            return REJECTED, [problem]
    # ③ lint(fails-closed)
    lint_dec, lint_msgs = _run_lint(repo_root)
    if lint_dec != APPROVED:
        return lint_dec, lint_msgs
    # ④ judge(静态三态)+ ack 通道(契约 07)
    decision, findings = judge_diff(staged_diff(repo_root))
    msgs.extend(f"[{f['severity']}] {f['issue']}" for f in findings)
    ack = None
    if decision == NEEDS_HUMAN and ack_human:
        if ci_mode:
            msgs.append("CI 模式忽略 --ack-human(契约 07:CI 永远重跑 gate,不消费本地 ack)")
        elif not sys.stdin.isatty():
            raise InfraError("非 tty 环境不可 --ack-human(审计环境不可满足,契约 07)")
        else:
            ack = _ack_info()
            decision = APPROVED
            msgs.append(f"本地人审 ack 已记录(仅审计,权威放行=PR approval): {ack['user']}@{ack['hostname']}")
    # ⑤ 三文件 review 清单(信息性)
    msgs.extend(review_items(staged_numstat(repo_root)))

    diff_bytes = staged_diff(repo_root).encode("utf-8")
    receipt = build_receipt(
        gate="gate-commit",
        feature_id=declared or WORKSPACE_FEATURE,
        inputs=[{"path": "<staged-diff>", "sha256": hashlib.sha256(diff_bytes).hexdigest()}],
        decision=decision,
        repo_root=repo_root,
        argv=argv,
        ack=ack,
    )
    write_receipt(receipt, repo_root)
    return decision, msgs
