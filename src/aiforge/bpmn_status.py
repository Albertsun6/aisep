"""spec: specs/feat-bpmn 验收 9 — 只读导出门禁状态为 docs/flows/sdlc-status.js。

与 project_dashboard 同性质:只读采集 + 生成,不调模型(契约 04)。
file:// 页面 fetch 本地 JSON 被 CORS 拦,故产物是 `window.AIFORGE_STATUS = <严格 JSON>`
的 JS 包裹;序列化后 `<` 全量替换为 unicode 转义,中和 </script> 与 <!--。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_AUDIT_REL = ".aiforge/audit/gates.jsonl"
_PIPELINE_REL = "docs/flows/sdlc-pipeline.bpmn"
# 验收 9 字段 allowlist:stages 内每条仅这些键;顶层仅 generated_at/stages/pipeline_xml
_STAGE_FIELDS = ("gate", "decision", "created_at", "feature_id")
# 只读报告不得写进规格/审计/代码区(同 project_dashboard 护栏)
_PROTECTED_OUT_DIRS = ("specs", ".aiforge", "src", "tests", ".git")


def collect_status(repo_root: Path) -> dict:
    """每 gate 取 created_at 降序首条(相等取文件中后出现者);坏行/非 dict 跳过。"""
    stages: dict = {}
    p = repo_root / _AUDIT_REL
    if p.exists():
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, UnicodeError):
            lines = []
        for line in lines:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            gate = obj.get("gate")
            if not isinstance(gate, str) or not gate:
                continue
            row = {k: obj.get(k) for k in _STAGE_FIELDS}
            prev = stages.get(gate)
            # ISO 时间串字典序可比;>= 使相等时后出现者覆盖(验收 9 并列规则)
            if prev is None or str(row.get("created_at") or "") >= str(prev.get("created_at") or ""):
                stages[gate] = row
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
    }


def _js_payload(obj: object) -> str:
    # `<` → unicode 转义:仍是合法 JSON,同时杀死 </script> 与 <!-- 注入面
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def render_js(status: dict, pipeline_xml: str) -> str:
    payload = dict(status)
    payload["pipeline_xml"] = pipeline_xml
    return "window.AIFORGE_STATUS = " + _js_payload(payload) + ";\n"


def render_pipeline_js(pipeline_xml: str) -> str:
    """入库的备援源(plan 设计点 6):状态文件缺损时管线图仍可渲染(验收 12)。"""
    return "window.AIFORGE_PIPELINE_XML = " + _js_payload(pipeline_xml) + ";\n"


def _check_out(repo_root: Path, out: Path) -> Path:
    out = out if out.is_absolute() else repo_root / out
    try:
        rel = out.resolve().relative_to(repo_root.resolve())
        if rel.parts and rel.parts[0] in _PROTECTED_OUT_DIRS:
            raise ValueError(f"拒绝写入保护目录 {rel.parts[0]}/(只读报告不改规格/审计/代码)")
    except ValueError as e:
        if "拒绝写入" in str(e):
            raise
        # repo 外路径:允许(用户显式指定)
    return out


def write_bpmn_status(repo_root: Path, out: Path | None = None,
                      emit_pipeline: bool = False) -> Path:
    """fail-closed:管线图缺失 → 抛错,不写半截产物。"""
    pipeline_p = repo_root / _PIPELINE_REL
    if not pipeline_p.exists():
        raise FileNotFoundError(f"缺 {_PIPELINE_REL}(先建管线图,验收 10)")
    pipeline_xml = pipeline_p.read_text(encoding="utf-8")
    dest = _check_out(repo_root, out or Path("docs/flows/sdlc-status.js"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_js(collect_status(repo_root), pipeline_xml), encoding="utf-8")
    if emit_pipeline:
        side = dest.parent / "sdlc-pipeline.js"
        side.write_text(render_pipeline_js(pipeline_xml), encoding="utf-8")
    return dest
