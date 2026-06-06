"""四指标看板：把 EvalReport 渲染成单文件静态 HTML（零依赖，双击即开）。"""

from __future__ import annotations

import datetime as _dt
import html
import os
from typing import Optional

from aiforge.eval.harness import EvalReport

_TEMPLATE = """<!doctype html>
<html lang="zh">
<head><meta charset="utf-8"><title>AIForge 四指标看板</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}}
header{{padding:24px 32px;border-bottom:1px solid #222}}
h1{{margin:0;font-size:20px}} .sub{{color:#8a8f98;font-size:13px;margin-top:4px}}
.cards{{display:flex;flex-wrap:wrap;gap:16px;padding:24px 32px}}
.card{{flex:1;min-width:200px;background:#171a21;border:1px solid #262b34;border-radius:12px;padding:18px}}
.card .k{{color:#8a8f98;font-size:13px}} .card .v{{font-size:30px;font-weight:700;margin-top:8px}}
.good{{color:#3fb950}} .warn{{color:#d29922}} .bad{{color:#f85149}}
table{{width:calc(100% - 64px);margin:8px 32px 32px;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #262b34}} th{{color:#8a8f98}}
</style></head>
<body>
<header><h1>AIForge · 四个生产指标看板</h1>
<div class="sub">生成于 {ts} · 样本数 N={n}</div></header>
<div class="cards">
  <div class="card"><div class="k">任务完成率 (过CI且无需人改)</div><div class="v {c1}">{m1:.0%}</div></div>
  <div class="card"><div class="k">回归引入率</div><div class="v {c2}">{m2:.0%}</div></div>
  <div class="card"><div class="k">平均 review 轮次</div><div class="v {c3}">{m3:.2f}</div></div>
  <div class="card"><div class="k">失败时平均 blast radius (文件)</div><div class="v {c4}">{m4:.2f}</div></div>
</div>
<table><thead><tr><th>任务</th><th>过CI</th><th>需人改</th><th>回归</th><th>review轮次</th><th>改动文件</th><th>成功</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>
"""


def _cls(value: float, good_below: bool, good: float, warn: float) -> str:
    if good_below:
        return "good" if value <= good else ("warn" if value <= warn else "bad")
    return "good" if value >= good else ("warn" if value >= warn else "bad")


def render_html(report: EvalReport) -> str:
    m = report.metrics
    rows = []
    for o in report.outcomes:
        rows.append(
            "<tr><td>{id}</td><td>{ci}</td><td>{he}</td><td>{rg}</td><td>{rl}</td><td>{fc}</td><td>{ok}</td></tr>".format(
                id=html.escape(o.task_id),
                ci="✓" if o.passed_ci else "✗",
                he="✓" if o.needed_human_edit else "—",
                rg="✗" if o.introduced_regression else "—",
                rl=o.review_loops,
                fc=o.files_changed,
                ok="✓" if o.succeeded else "✗",
            )
        )
    return _TEMPLATE.format(
        ts=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        n=m.n,
        m1=m.task_completion_rate, c1=_cls(m.task_completion_rate, False, 0.8, 0.6),
        m2=m.regression_introduction_rate, c2=_cls(m.regression_introduction_rate, True, 0.05, 0.15),
        m3=m.avg_review_loop_count, c3=_cls(m.avg_review_loop_count, True, 1.2, 2.0),
        m4=m.avg_blast_radius_on_failure, c4=_cls(m.avg_blast_radius_on_failure, True, 5, 10),
        rows="\n".join(rows),
    )


def write_dashboard(report: EvalReport, path: str = "dashboard/index.html") -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(report))
    return path
