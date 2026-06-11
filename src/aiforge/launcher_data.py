"""spec: specs/feat-launcher-outputs 验收 1-4 — 只读导出各特性阶段产物为 docs/launcher-data.js。

与 project_dashboard / bpmn_status 同性质:只读采集 + 生成,不调模型(契约 04)。
file:// 页面 fetch 被 CORS 拦,故产物为 `window.AIFORGE_LAUNCHER = <严格 JSON>` 的
JS 包裹;转义与输出护栏复用 bpmn_status(单点维护)。产物不入库(.gitignore)。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aiforge.bpmn_status import _check_out, _js_payload

_EXCLUDE_DIRS = frozenset({"contracts", "_workspace"})
# gates key allowlist(验收 1):陌生 receipt 文件名不进数据
_GATE_FILES = ("gate-spec", "gate-trace", "gate-judge", "gate-commit")
_RECEIPT_FIELDS = ("decision", "created_at")
_TEXT_FILES = (("spec", "spec.md"), ("plan", "plan.md"),
               ("tasks", "tasks.md"), ("debate", "REVIEW-debate.md"))


def _safe_in_specs(p: Path, specs_root: Path) -> bool:
    """验收 2:symlink 或 resolve 出 specs 根 → 拒。

    导出器读的必须是入库形态的内容——外部 PR 可在 specs 里放指向 ~/.ssh 等的软链,
    本地跑导出时若跟随,私密内容会被嵌进产物;fail-closed 跳过。
    """
    try:
        if p.is_symlink():
            return False
        return p.resolve().is_relative_to(specs_root.resolve())
    except OSError:
        return False


def _read_text(p: Path, specs_root: Path) -> str | None:
    if not _safe_in_specs(p, specs_root) or not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_receipt(p: Path, specs_root: Path) -> dict | None:
    text = _read_text(p, specs_root)
    if text is None:
        return None
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    return {k: obj.get(k) for k in _RECEIPT_FIELDS}


def collect_launcher(repo_root: Path) -> dict:
    """features = specs/ 一级目录中含 spec.md 者(排除 contracts/_workspace)。"""
    specs_root = repo_root / "specs"
    features: dict = {}
    if specs_root.is_dir():
        for d in sorted(specs_root.iterdir()):
            if not d.is_dir() or d.is_symlink() or d.name in _EXCLUDE_DIRS:
                continue
            if not (d / "spec.md").is_file():
                continue
            feat: dict = {key: _read_text(d / fname, specs_root) for key, fname in _TEXT_FILES}
            outputs: dict = {}
            odir = d / "outputs"
            if odir.is_dir() and not odir.is_symlink():
                # 只收顶层 *.md(验收 1):子目录/二进制/角色 JSON 不展示
                for f in sorted(odir.iterdir()):
                    if f.is_file() and f.suffix == ".md":
                        text = _read_text(f, specs_root)
                        if text is not None:
                            outputs[f.name] = text
            feat["outputs"] = outputs
            gates: dict = {}
            for g in _GATE_FILES:
                r = _read_receipt(d / "gates" / f"{g}.json", specs_root)
                if r is not None:
                    gates[g] = r
            feat["gates"] = gates
            features[d.name] = feat
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "features": features,
    }


def render_js(data: dict) -> str:
    return "window.AIFORGE_LAUNCHER = " + _js_payload(data) + ";\n"


def write_launcher_data(repo_root: Path, out: Path | None = None) -> tuple[Path, int]:
    dest = _check_out(repo_root, out or Path("docs/launcher-data.js"))
    data = collect_launcher(repo_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_js(data), encoding="utf-8")
    return dest, len(data["features"])
