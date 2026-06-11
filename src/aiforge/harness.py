"""文件/git → aiforge 门禁适配层(STEP 0 v2 M1 薄 CLI 核心)。

把吃 PipelineState 的复用核门禁(SpecGate / StaticRiskScanner / review_after_session)
适配到"文件 + git"输入,并落 gate receipt(契约 06)。全部 stdlib,**永不调模型**(契约 04)。

退出码契约(契约 03,单点 mapper 见 EXIT):0=approved / 1=rejected / 2=needs_human / 3=infra_error。
诚实边界(经 M1 异构评审收敛,见 specs/contracts/REVIEW-2026-06-11.md):
- receipt 链的 spec 内容以 **git index(待提交内容)** 为准——绕过 index 校验的手写 receipt
  由 CI 重跑上游 gate 兜底(权威层);
- 本地 lint 检查工作区快照(反馈层);CI 对已提交树重跑 make lint(权威);
- gate-trace 只校验文档链;代码↔feature 关联走声明制(契约 02),由 gate-commit 强制;
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
# feature id:首字符限 [a-z0-9_](允许 _workspace),全串无 / 与前导点 → 杜绝路径穿越
_FID_RE = re.compile(r"^[a-z0-9_][a-z0-9._-]{0,99}$")


class InfraError(RuntimeError):
    """基础设施错误(契约 03 的 3):带可读诊断,绝不静默放行。"""


def exit_code(decision: str) -> int:
    return EXIT[decision]


def validate_feature_id(fid: str) -> str:
    """receipt 路径以 feature id 拼装——不合法 id = 路径穿越面,直接 infra。"""
    if not _FID_RE.match(fid or ""):
        raise InfraError(
            f"feature id 不合法: {fid!r}(需匹配 ^[a-z0-9_][a-z0-9._-]{{0,99}}$,禁止 / 与前导点)"
        )
    return fid


# ---------------------------------------------------------------- git helpers

def _git_raw(repo_root: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=text, check=True
        )
    except FileNotFoundError as exc:  # git 本体缺失
        raise InfraError(f"git 不可用: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.strip() if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace").strip()
        raise InfraError(f"git {' '.join(args)} 失败: {err}") from exc


def _git(repo_root: Path, *args: str) -> str:
    return _git_raw(repo_root, *args).stdout


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


# 禁外部 diff driver/textconv(评审:git diff 本身是命令执行面)
_DIFF_GUARDS = ("-c", "diff.external=", "diff", "--no-ext-diff", "--no-textconv")


def staged_diff(repo_root: Path, staged: bool = True) -> str:
    tail = ["--cached"] if staged else ["HEAD"]
    return _git(repo_root, *_DIFF_GUARDS, *tail)


def staged_numstat(repo_root: Path, staged: bool = True) -> str:
    tail = ["--numstat", "-z"] + (["--cached"] if staged else ["HEAD"])
    return _git(repo_root, *_DIFF_GUARDS, *tail)


def staged_paths(repo_root: Path) -> list[str]:
    out = _git(repo_root, *_DIFF_GUARDS, "--cached", "--name-only", "-z")
    return [p for p in out.split("\0") if p]


def range_diff(repo_root: Path, base: str) -> str:
    """CI 用:base...HEAD 的合并基 diff(契约 01 探针/gates.yml)。"""
    return _git(repo_root, *_DIFF_GUARDS, f"{base}...HEAD")


def index_blob(repo_root: Path, rel_posix: str) -> bytes | None:
    """读 git index 中的文件内容(= 本次将被提交的版本);不在 index → None。"""
    try:
        return _git_raw(repo_root, "show", f":{rel_posix}", text=False).stdout
    except InfraError:
        return None


# ------------------------------------------------------------- hash & receipt

def sha256_file(path: Path) -> str:
    """契约 09:对原始字节计算;symlink 输入 → infra(不跟随)。"""
    if path.is_symlink():
        raise InfraError(f"{path} 是 symlink,gate 输入不跟随 symlink(契约 09)")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_no_symlink(path: Path) -> str:
    if path.is_symlink():
        raise InfraError(f"{path} 是 symlink,gate 输入不跟随 symlink(契约 09)")
    return path.read_text(encoding="utf-8")


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
        "feature_id": validate_feature_id(feature_id),
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
    fid = validate_feature_id(receipt["feature_id"])
    gates_dir = repo_root / "specs" / fid / "gates"
    # 路径上任一已存在组件是 symlink → 拒(防 receipt 被导出 repo 外)
    probe = repo_root
    for part in ("specs", fid, "gates"):
        probe = probe / part
        if probe.is_symlink():
            raise InfraError(f"{probe} 是 symlink,receipt 不写入 symlink 路径(契约 09)")
    gates_dir.mkdir(parents=True, exist_ok=True)
    dest = gates_dir / f"{receipt['gate']}.json"
    if dest.is_symlink():
        raise InfraError(f"{dest} 是 symlink,拒绝覆盖(契约 09)")
    dest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_audit(receipt, repo_root)  # spec: gate-audit-log(旁路,fail-open)
    return dest


# receipt 同 gate 重跑会覆盖;审计是 append-only 本地时间线,补"何时跑过哪些 gate"(spec: gate-audit-log)。
# **诚实定位**:本地流水,非防篡改(可删改;真防篡改=HMAC 链+外部 sink,契约 06 强制版推迟)。
_AUDIT_FIELDS = ("created_at", "gate", "feature_id", "decision", "exit_code", "git_head", "run_id")


def _append_audit(receipt: dict, repo_root: Path) -> None:
    """fail-open(supervisor 拍板):写失败只 stderr 警告,绝不改 gate 判定/退出码。"""
    try:
        audit_dir = repo_root / ".aiforge" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        row = {k: receipt.get(k) for k in _AUDIT_FIELDS}  # 子集字段,无文件内容/secret
        with (audit_dir / "gates.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[audit] 审计追加失败(旁路,不影响门禁): {exc}", file=sys.stderr)


def load_receipt(path: Path) -> dict:
    """契约 06/09:不可解析/版本≠1 → InfraError(3),带可读诊断;未知字段忽略。"""
    if path.is_symlink():
        raise InfraError(f"receipt {path} 是 symlink,拒绝读取(契约 09)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InfraError(f"receipt 不可解析: {path}(建议删除后重跑对应 gate)— {exc}") from exc
    ver = data.get("schema_version")
    if ver != RECEIPT_SCHEMA_VERSION:
        raise InfraError(
            f"receipt schema_version={ver!r} ≠ 已知 {RECEIPT_SCHEMA_VERSION}: {path}"
            "(高于=升级 aiforge;其他=检查文件来源,勿手写 receipt)"
        )
    return data


# --------------------------------------------------------------------- gates

def derive_feature_id(spec_path: Path, repo_root: Path, declared: str | None) -> str:
    if declared:
        return validate_feature_id(declared)
    try:
        rel = spec_path.resolve().relative_to(repo_root.resolve())
        if len(rel.parts) >= 3 and rel.parts[0] == "specs":
            return validate_feature_id(rel.parts[1])
    except ValueError:
        pass
    return WORKSPACE_FEATURE


def _spec_decision(spec_path: Path, feature_id: str) -> tuple[str, list[str]]:
    """SpecGate 结构校验(只读,不写 receipt)。"""
    if not spec_path.exists() or not spec_path.read_text(encoding="utf-8").strip():
        return REJECTED, ["P1: 无 spec / spec 为空,拒绝推进"]
    state = PipelineState(feature_id=feature_id, request="harness:gate-spec")
    state.add_artifact(Artifact(kind=ArtifactKind.SPEC, content=spec_path.read_text(encoding="utf-8"), produced_by="file"))
    res = SpecGate().check(state, {})
    if res.passed:
        return APPROVED, []
    return REJECTED, [res.reason, "缺什么:验收结构需 Gherkin(Given/When/Then) 或 EARS(shall+when/if/while/where) 或 User Story+验收标记,且 ≥40 字符"]


def gate_spec(spec_path: Path, repo_root: Path, feature_id: str, argv: list[str]) -> tuple[str, list[str]]:
    validate_feature_id(feature_id)
    if spec_path.is_symlink():
        raise InfraError(f"{spec_path} 是 symlink(契约 09)")
    decision, msgs = _spec_decision(spec_path, feature_id)
    inputs = (
        [{"path": _rel_posix(spec_path, repo_root), "sha256": sha256_file(spec_path)}]
        if decision == APPROVED else []
    )
    receipt = build_receipt(gate="gate-spec", feature_id=feature_id, inputs=inputs,
                            decision=decision, repo_root=repo_root, argv=argv)
    write_receipt(receipt, repo_root)
    return decision, msgs


def gate_spec_check(spec_path: Path, repo_root: Path, feature_id: str) -> tuple[str, list[str]]:
    """**只读冻结校验**(CI 用,契约 02/06):验证 spec 仍结构合法 **且** 已存在的
    gate-spec receipt 与当前 spec 内容相符——**不重新生成 receipt**。

    catches:改了冻结 spec 但不重跑 gate-spec(receipt 过期)→ 1;伪造 receipt(结构非法/
    hash 不符)→ 1;无 receipt → 1;receipt 坏/版本不识别 → 3。
    """
    validate_feature_id(feature_id)
    if spec_path.is_symlink():
        raise InfraError(f"{spec_path} 是 symlink(契约 09)")
    decision, msgs = _spec_decision(spec_path, feature_id)
    if decision != APPROVED:
        return decision, msgs
    rcpt_path = spec_path.parent / "gates" / "gate-spec.json"
    if not rcpt_path.exists():
        return REJECTED, [f"冻结校验:缺 gate-spec receipt({rcpt_path}),spec 未经门禁冻结"]
    rcpt = load_receipt(rcpt_path)
    if rcpt.get("gate") != "gate-spec" or rcpt.get("feature_id") != feature_id:
        return REJECTED, [f"冻结校验:receipt 元数据不符(gate={rcpt.get('gate')!r}, feature_id={rcpt.get('feature_id')!r})"]
    if rcpt.get("decision") != APPROVED or rcpt.get("exit_code") != 0:
        return REJECTED, [f"冻结校验:receipt decision={rcpt.get('decision')},非 approved"]
    rel = _rel_posix(spec_path, repo_root)
    want = {i.get("path"): i.get("sha256") for i in rcpt.get("inputs", []) if isinstance(i, dict)}
    if want.get(rel) != sha256_file(spec_path):
        return REJECTED, [
            "冻结校验:spec.md 内容与 receipt 记录的 hash 不符——改了冻结 spec 却未重跑 gate-spec"
            "(或 receipt 被伪造)。授权变更须走 specs/contracts/02 流程后重跑 gate-spec。"
        ]
    return APPROVED, [f"冻结校验通过:{rel} 与 receipt 一致"]


_CHAIN = (("plan.md", "spec.md"), ("tasks.md", "plan.md"))


def gate_trace(feature_dir: Path, repo_root: Path, argv: list[str]) -> tuple[str, list[str]]:
    """P2 语义(文档链):每个存在的下游必须声明 refs 且解析到存在的上游。"""
    msgs: list[str] = []
    for name in ("spec.md", "plan.md", "tasks.md"):
        p = feature_dir / name
        if p.is_symlink():
            raise InfraError(f"{p} 是 symlink(契约 09)")
    spec = feature_dir / "spec.md"
    if not spec.exists() or not _read_no_symlink(spec).strip():
        decision = REJECTED
        msgs = [f"P2: {feature_dir} 缺 spec.md,追溯链无根"]
    else:
        decision = APPROVED
        for down_name, up_name in _CHAIN:
            down = feature_dir / down_name
            if not down.exists():
                continue
            declared = " ".join(_REFS_RE.findall(_read_no_symlink(down)))
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
        fid = validate_feature_id(feature_dir.name)
    receipt = build_receipt(gate="gate-trace", feature_id=fid, inputs=inputs,
                            decision=decision, repo_root=repo_root, argv=argv)
    write_receipt(receipt, repo_root)
    return decision, msgs


# **极窄**白名单:只跳过确定不会被执行的纯文档/图片(spec: scanner-skip-docs)。
# 经异构评审(2026-06-11,GPT-5.5)收窄:**不**豁免 .html/.svg(含 <script>)、.yml/.yaml
# (CI 可执行面)、.json/.toml/.cfg(影响执行链)——这些一律仍扫。fail-closed:其余(代码/
# 配置/未知/无后缀/可执行 bit)全扫。
_SKIP_SUFFIXES = frozenset({
    ".md", ".markdown", ".rst", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".m4a",
})
_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)\s*$")
# 块内 mode 行:`new file mode 100755` / `new mode 100755`——owner/group/other 任一 x 位即可执行
_MODE_RE = re.compile(r"^(?:new file mode|new mode) (\d{6})\s*$")


def code_only_diff(diff_text: str) -> str:
    """从 git diff 文本里剔除"确定纯文档"块,其余(含可执行面)全留(spec: scanner-skip-docs)。

    按 `diff --git a/<p> b/<p>` 分块;两侧后缀都在 _SKIP_SUFFIXES → tentatively 跳过;
    但块内若出现 executable bit(mode 100755 等)→ **强制保留**(覆盖后缀豁免);
    解析不出文件名/mode → 保守保留(当代码扫,fail-closed)。
    """
    lines = diff_text.splitlines(keepends=True)
    out: list[str] = []
    keep = True  # 进入第一个 diff --git 之前的内容(罕见)保守保留
    for line in lines:
        stripped = line.rstrip("\n")
        m = _DIFF_GIT_RE.match(stripped)
        if m:
            sa = PurePosixPath(m.group(1)).suffix.lower()
            sb = PurePosixPath(m.group(2)).suffix.lower()
            # 仅当**两侧**都是已知纯文档后缀才(暂)跳过(改名/类型变化时保守扫)
            keep = not (sa in _SKIP_SUFFIXES and sb in _SKIP_SUFFIXES)
        else:
            mode_m = _MODE_RE.match(stripped)
            if mode_m and (int(mode_m.group(1), 8) & 0o111):
                keep = True  # executable bit → 强制扫本块(覆盖后缀豁免)
        if keep:
            out.append(line)
    return "".join(out)


def judge_diff(diff_text: str) -> tuple[str, list[dict]]:
    """纯静态三态(契约 04):扫描命中只升级人审,不硬拒、不放行。

    只扫可执行代码(剔除纯文档/数据文件,spec: scanner-skip-docs)——文档里引用
    eval/os.system 是教学/记录,不构成 RCE。fail-closed:未知后缀仍扫。
    """
    findings = StaticRiskScanner().scan(code_only_diff(diff_text))
    return (NEEDS_HUMAN if findings else APPROVED), findings


def review_items(numstat_z: str) -> list[str]:
    """解析 ``git diff --numstat -z``(NUL 分隔;rename 记录占 3 个 token)。"""
    changes: list[FileChange] = []
    toks = numstat_z.split("\0")
    i = 0
    while i < len(toks):
        tok = toks[i]
        if not tok:
            i += 1
            continue
        parts = tok.split("\t")
        if len(parts) < 3:
            i += 1
            continue
        added, removed, path = parts[0], parts[1], parts[2]
        if path == "":  # rename/copy:后续两个 token 是旧名、新名
            path = toks[i + 2] if i + 2 < len(toks) else ""
            i += 3
        else:
            i += 1
        if added == "-" or removed == "-" or not path:  # binary / 异常
            continue
        changes.append(FileChange(path=path, added_lines=int(added), removed_lines=int(removed)))
    review = review_after_session(changes)
    return [
        f"[{'必读' if it.must_fully_review else '抽审'}] {it.path} ({it.lines_changed} 行) — {it.reason}"
        for it in review.items
    ]


# ----------------------------------------------------------------- gate-commit

def check_receipt_chain(repo_root: Path, feature_id: str) -> str | None:
    """契约 06 链校验(本地反馈层;CI 重跑上游 gate 才是权威):

    问题返回描述(→1);receipt 坏/版本不识别抛 InfraError(→3)。
    spec 内容以 **git index** 为准——staged 篡改逃不掉,worktree 噪声不误伤。
    """
    validate_feature_id(feature_id)
    rel = f"specs/{feature_id}/spec.md"
    blob = index_blob(repo_root, rel)
    if blob is None:
        if not (repo_root / rel).exists():
            return f"{feature_id}: 无 {rel}(无 spec 的代码改动,拒绝)"
        return f"{feature_id}: {rel} 未加入 index(spec 必须随提交入库:git add specs/{feature_id})"
    rcpt_path = repo_root / "specs" / feature_id / "gates" / "gate-spec.json"
    if not rcpt_path.exists():
        return f"{feature_id}: 缺 gate-spec receipt(先跑 aiforge gate-spec {rel})"
    rcpt = load_receipt(rcpt_path)
    # 元数据校验(评审 blocker:不只比 hash)
    if rcpt.get("gate") != "gate-spec" or rcpt.get("feature_id") != feature_id:
        return f"{feature_id}: receipt 元数据不符(gate={rcpt.get('gate')!r}, feature_id={rcpt.get('feature_id')!r})"
    if rcpt.get("decision") != APPROVED or rcpt.get("exit_code") != 0:
        return f"{feature_id}: gate-spec receipt decision={rcpt.get('decision')},非 approved"
    want = {i.get("path"): i.get("sha256") for i in rcpt.get("inputs", []) if isinstance(i, dict)}
    if rel not in want:
        return f"{feature_id}: receipt inputs 不含 {rel},不可信"
    if want[rel] != hashlib.sha256(blob).hexdigest():
        return f"{feature_id}: receipt 过期/伪造(index 中 spec.md hash 不符),重跑 gate-spec 后重新 add"
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
    """PreCommitGate 语义(fails-closed)。诚实边界:lint 的是工作区快照(反馈层),
    CI 对已提交树重跑 make lint(权威)。ruff 退出码:0=过 1=内容问题 ≥2=工具自身问题。"""
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
    if proc.returncode == 0:
        return APPROVED, []
    if proc.returncode == 1:
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-10:]
        return REJECTED, ["lint 未通过:", *tail]
    raise InfraError(f"ruff 自身错误(exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[-300:]}")


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
    if declared:
        validate_feature_id(declared)
    # 契约 07:--ack-human 的审计环境前置检查(传了就查,不等 needs_human)
    if ack_human and not ci_mode and not sys.stdin.isatty():
        raise InfraError("非 tty 环境不可 --ack-human(审计环境不可满足,契约 07)")

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
    # ③ lint(fails-closed;工作区快照,CI 权威)
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
