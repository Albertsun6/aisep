"""项目状态可视化总览(spec: specs/project-dashboard)。

`aiforge project-dashboard` 读 specs/ + 审计流水 + git + 契约,生成一份人性化的单页
HTML,让人不用读代码/对话就看懂整个项目。**只读生成**:不调模型(契约 04)、不改任何
specs/审计/代码;所有从文件读入、嵌进 HTML 的动态内容**强制 html.escape**(防 XSS/注入)。
"""
from __future__ import annotations

import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_AUDIT_REL = ".aiforge/audit/gates.jsonl"
_SKIP_SPEC_DIRS = {"contracts", "_workspace"}
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.MULTILINE)
_GATE_ORDER = ("gate-spec", "gate-trace", "gate-commit")


def esc(value: object) -> str:
    """所有嵌进 HTML 的动态内容都过这里(契约/spec 安全要求:防 XSS/注入)。"""
    return html.escape("" if value is None else str(value), quote=True)


# ----------------------------------------------------------------- collect

def _git(repo_root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True,
            text=True, errors="replace", timeout=10,  # errors=replace:坏编码不崩(评审落改)
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""


def _read(path: Path) -> str:
    # errors=replace + 捕 OSError/UnicodeError:文件缺失/损坏/非法 UTF-8 都降级为空,不崩(评审落改)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return ""


def _first(rx: re.Pattern, text: str, default: str = "") -> str:
    m = rx.search(text)
    return m.group(1).strip() if m else default


def _collect_features(repo_root: Path) -> list:
    specs = repo_root / "specs"
    feats = []
    if not specs.is_dir():
        return feats
    for d in sorted(p for p in specs.iterdir() if p.is_dir()):
        if d.name in _SKIP_SPEC_DIRS:
            continue
        spec = d / "spec.md"
        if not spec.exists():
            continue
        text = _read(spec)
        gates = sorted(
            p.stem for p in (d / "gates").glob("*.json")
        ) if (d / "gates").is_dir() else []
        feats.append({
            "id": d.name,
            "title": _first(_TITLE_RE, text, d.name),
            "status": _first(_STATUS_RE, text, "—"),
            "gates": gates,
        })
    return feats


def _collect_audit(repo_root: Path, limit: int = 25) -> list:
    rows = []
    p = repo_root / _AUDIT_REL
    if not p.exists():
        return rows
    for ln in _read(p).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        if isinstance(obj, dict):  # 评审落改:合法 JSON 但非 dict(如 []、123)视为坏行跳过
            rows.append(obj)
    return list(reversed(rows))[:limit]  # 最近的在前


def _collect_contracts(repo_root: Path) -> list:
    d = repo_root / "specs" / "contracts"
    out = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("[0-9]*.md")):  # 只列编号契约(01..10),跳过 README/REVIEW/vendor
        out.append({"file": p.name, "title": _first(_TITLE_RE, _read(p), p.stem)})
    return out


def _count_tests(repo_root: Path) -> int:
    d = repo_root / "tests"
    if not d.is_dir():
        return 0
    n = 0
    for f in d.glob("test_*.py"):
        n += len(re.findall(r"^\s*def test_", _read(f), re.MULTILINE))
    return n


def collect_state(repo_root: Path) -> dict:
    """只读采集项目当前状态。任一源缺失/损坏 → 优雅降级(空),不抛。"""
    features = _collect_features(repo_root)
    audit = _collect_audit(repo_root)
    contracts = _collect_contracts(repo_root)
    commit_count = _git(repo_root, "rev-list", "--count", "HEAD").strip()
    recent = [
        ln for ln in _git(repo_root, "log", "--oneline", "-12", "--no-color").splitlines() if ln
    ]
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "features": features,
        "audit": audit,
        "contracts": contracts,
        "commit_count": commit_count or "—",
        "recent_commits": recent,
        "test_count": _count_tests(repo_root),
        "audit_runs": len(audit),
    }


# ------------------------------------------------------------------ render

_ARCH_MERMAID = """flowchart TD
    H["人 supervisor 定方向 审批"] --> ENG["Claude Code 交互会话 引擎"]
    ENG --> CLI["门禁 CLI python -m aiforge 纯静态 永不调模型"]
    ENG --> SPECS["specs id 状态落盘 spec plan tasks receipt"]
    CLI --> CI["GitHub CI gates 唯一真强制"]
    classDef person fill:#fef3c7,stroke:#f59e0b,color:#92400e
    classDef engine fill:#ecfdf5,stroke:#10b981,color:#064e3b
    classDef enforce fill:#dbeafe,stroke:#3b82f6,color:#1e40af
    class H person
    class ENG,CLI,SPECS engine
    class CI enforce"""

_PIPE_MERMAID = """flowchart LR
    R["需求 spec.md"] --> GS{"gate-spec"}
    GS --> A["架构 plan/tasks"]
    A --> GT{"gate-trace"}
    GT --> I["实现 代码+测试"]
    I --> GJ{"gate-judge"}
    GJ --> C{"gate-commit"}
    C --> X["异构评审 cursor"]
    X --> P["push + CI gates"]
    classDef s fill:#ecfdf5,stroke:#10b981,color:#064e3b
    classDef g fill:#fef3c7,stroke:#f59e0b,color:#92400e
    class R,A,I,X,P s
    class GS,GT,GJ,C g"""


def _stat_card(num, label):
    return (f'<div class="stat"><div class="stat-num">{esc(num)}</div>'
            f'<div class="stat-label">{esc(label)}</div></div>')


def _feature_card(f):
    badges = " ".join(
        f'<span class="pill pill-ok">{esc(g)}</span>' for g in f["gates"]
    ) or '<span class="pill pill-muted">未跑门禁</span>'
    st = esc(f["status"])
    st_cls = "pill-ok" if st == "active" else "pill-muted"
    return (
        '<div class="feat">'
        f'<div class="feat-head"><code>{esc(f["id"])}</code>'
        f'<span class="pill {st_cls}">{st}</span></div>'
        f'<div class="feat-title">{esc(f["title"])}</div>'
        f'<div class="feat-gates">{badges}</div>'
        '</div>'
    )


def _audit_row(r):
    dec = esc(r.get("decision", "—"))
    cls = {"approved": "pill-ok", "rejected": "pill-warn",
           "needs_human": "pill-warn", "infra_error": "pill-info"}.get(dec, "pill-muted")
    ts = esc(str(r.get("created_at", ""))[:19].replace("T", " "))
    return (f'<tr><td class="mono">{ts}</td><td><code>{esc(r.get("gate","—"))}</code></td>'
            f'<td>{esc(r.get("feature_id","—"))}</td>'
            f'<td><span class="pill {cls}">{dec}</span></td></tr>')


def render_html(state: dict) -> str:
    feats = state["features"]
    feat_html = "".join(_feature_card(f) for f in feats) or \
        '<div class="empty">暂无特性(specs/ 下还没有特性目录)</div>'
    audit_html = "".join(_audit_row(r) for r in state["audit"]) or \
        '<tr><td colspan="4" class="empty">暂无门禁运行记录(.aiforge/audit/gates.jsonl 为空)</td></tr>'
    contracts_html = "".join(
        f'<li><code>{esc(c["file"])}</code> {esc(c["title"])}</li>' for c in state["contracts"]
    ) or '<li class="empty">暂无契约</li>'
    commits_html = "".join(
        f'<div class="commit"><code>{esc(c[:9])}</code> {esc(c[10:])}</div>'
        for c in state["recent_commits"]
    ) or '<div class="empty">暂无提交</div>'

    return _PAGE.format(
        generated_at=esc(state["generated_at"]),
        n_feat=esc(len(feats)),
        n_contracts=esc(len(state["contracts"])),
        n_runs=esc(state["audit_runs"]),
        stat_feat=_stat_card(len(feats), "已建特性"),
        stat_contracts=_stat_card(len(state["contracts"]), "冻结契约"),
        stat_runs=_stat_card(state["audit_runs"], "门禁运行(近)"),
        stat_tests=_stat_card(state["test_count"], "测试"),
        stat_commits=_stat_card(state["commit_count"], "提交"),
        arch=_ARCH_MERMAID,
        pipe=_PIPE_MERMAID,
        features=feat_html,
        audit=audit_html,
        contracts=contracts_html,
        commits=commits_html,
    )


# 这是只读报告生成,只许写文档产物——绝不写进代码/规格/审计目录(评审落改:护栏不靠调用方自觉)
_PROTECTED_OUT_DIRS = ("specs", ".aiforge", "src", "tests", ".git")


def write_project_dashboard(repo_root: Path, out: Path | None = None) -> Path:
    dest = out or (repo_root / "docs" / "project-dashboard.html")
    # 护栏:输出路径若落在受保护目录(代码/规格/审计)→ 拒绝(spec:只生成 HTML 到 docs/,不改其它)
    try:
        rel = dest.resolve().relative_to(repo_root.resolve())
        if rel.parts and rel.parts[0] in _PROTECTED_OUT_DIRS:
            raise ValueError(
                f"project-dashboard 是只读报告,拒绝写入受保护目录 {rel.parts[0]}/;"
                f"请输出到 docs/ 或 repo 外"
            )
    except ValueError as exc:
        if "拒绝写入" in str(exc):
            raise
        # relative_to 抛 ValueError = dest 在 repo 外,允许(用户显式指定的外部路径)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_html(collect_state(repo_root)), encoding="utf-8")
    return dest


# 视觉骨架(与 docs 的 HTML 手册同风格:中性灰白 + emerald,避免 AI slop)。
# {placeholders} 全部来自 render_html,且都已 esc。架构/管线 Mermaid 是静态内嵌(无动态数据)。
_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AISEP × Claude Code Harness — 项目总览</title>
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{startOnLoad:true,theme:"base",themeVariables:{{
    fontFamily:'"PingFang SC","Noto Sans SC",system-ui,sans-serif',
    primaryColor:"#ecfdf5",primaryTextColor:"#064e3b",primaryBorderColor:"#10b981",lineColor:"#475569"}},
    flowchart:{{curve:"basis",padding:16}}}});
</script>
<style>
  :root{{--ink:#0f172a;--soft:#334155;--line:#e2e8f0;--bg:#fafaf9;--accent:#047857;--asoft:#ecfdf5}}
  html{{scroll-behavior:smooth;scroll-padding-top:64px}}
  body{{font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--bg);line-height:1.7}}
  h1,h2,h3{{font-weight:700;letter-spacing:-.01em}} h2{{scroll-margin-top:64px;font-size:1.25rem;margin-bottom:.8rem}}
  code,.mono{{font-family:"JetBrains Mono","SF Mono",ui-monospace,Menlo,monospace}}
  code{{background:#f1f5f9;padding:.05rem .35rem;border-radius:4px;font-size:.85em}}
  a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:1.4rem 1.6rem;margin-bottom:1.4rem}}
  .pill{{display:inline-block;padding:.08rem .5rem;border-radius:999px;font-size:.7rem;font-weight:600;white-space:nowrap}}
  .pill-ok{{background:#d1fae5;color:#065f46}} .pill-warn{{background:#fef3c7;color:#92400e}}
  .pill-info{{background:#dbeafe;color:#1e40af}} .pill-muted{{background:#f1f5f9;color:#475569}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:.8rem}}
  .stat{{background:var(--asoft);border:1px solid #a7f3d0;border-radius:10px;padding:.9rem;text-align:center}}
  .stat-num{{font-size:1.8rem;font-weight:800;color:var(--accent);font-family:"JetBrains Mono",monospace}}
  .stat-label{{font-size:.78rem;color:var(--soft);margin-top:.2rem}}
  .feats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.9rem}}
  .feat{{border:1px solid var(--line);border-radius:10px;padding:.9rem 1rem;background:#fff}}
  .feat-head{{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem}}
  .feat-title{{font-size:.9rem;color:var(--soft);margin-bottom:.5rem;line-height:1.4}}
  .feat-gates{{display:flex;flex-wrap:wrap;gap:.3rem}}
  table{{border-collapse:collapse;width:100%;font-size:.85rem}}
  th{{background:#f1f5f9;text-align:left;font-weight:600}} th,td{{border:1px solid var(--line);padding:.4rem .6rem}}
  tbody tr:hover{{background:#f8fafc}} .tablewrap{{overflow-x:auto}}
  .mermaid{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:1.4rem;margin:.5rem 0;text-align:center}}
  .empty{{color:#94a3b8;font-size:.85rem;padding:.5rem}}
  .commit{{font-size:.82rem;padding:.25rem 0;border-bottom:1px dashed var(--line)}} .commit:last-child{{border:none}}
  ul.contracts{{list-style:none;padding:0;font-size:.88rem}} ul.contracts li{{padding:.3rem 0;border-bottom:1px dashed var(--line)}}
  nav{{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.95);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}}
  .nav-in{{max-width:1100px;margin:0 auto;padding:.7rem 1.2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;font-size:.85rem}}
  .nav-in a{{color:var(--soft)}} .wrap{{max-width:1100px;margin:0 auto;padding:1.4rem 1.2rem}}
  @media print{{nav{{display:none}}}}
</style>
</head>
<body>
<nav><div class="nav-in">
  <strong style="color:#0f172a">AISEP × Claude Code Harness</strong>
  <a href="#overview">概览</a><a href="#arch">架构</a><a href="#pipeline">管线</a>
  <a href="#features">特性</a><a href="#audit">门禁时间线</a><a href="#contracts">契约</a><a href="#journey">历程</a>
  <span style="margin-left:auto;color:#94a3b8">生成于 {generated_at}</span>
</div></nav>
<div class="wrap">

<section id="overview" class="card">
  <h1 class="text-2xl mb-2" style="color:#0f172a">项目总览</h1>
  <p style="color:#334155;margin-bottom:1rem">
    这是把 <strong>aiforge 七层工程方法论</strong> 做成 <strong>Claude Code 的企业工程纪律层</strong> 的骨架:
    一条永不调模型的门禁 CLI + 进程外强制层(GitHub CI)+ 会话内护栏,<strong>人当 supervisor</strong>。
    每个特性走 需求→门禁→实现→异构评审→提交 的管线,状态落盘到 <code>specs/&lt;id&gt;/</code>。
    本页读项目真实状态生成,<strong>重跑即最新</strong>。
  </p>
  <div class="stats">
    {stat_feat}{stat_contracts}{stat_runs}{stat_tests}{stat_commits}
  </div>
  <p style="margin-top:1rem;font-size:.85rem;color:#64748b">
    上手 → <a href="GETTING-STARTED.md">手把手教程</a> ·
    查命令 → <a href="USER-GUIDE.md">参考手册</a> ·
    部署 → <a href="DEPLOY.md">DEPLOY</a> · 重新生成本页 → <code>make dashboard-project</code>
  </p>
</section>

<section id="arch" class="card">
  <h2>架构:谁在执行什么</h2>
  <div class="mermaid">{arch}</div>
  <p style="font-size:.85rem;color:#64748b">三层权威:GitHub CI = <strong>唯一真强制</strong>;本地钩子 = 反馈层(可旁路);会话护栏 = 防呆不防恶。会话内的一切都不算强制。</p>
</section>

<section id="pipeline" class="card">
  <h2>管线:一个特性怎么走完</h2>
  <div class="mermaid">{pipe}</div>
</section>

<section id="features" class="card">
  <h2>已建特性 <span class="pill pill-muted">{n_feat}</span></h2>
  <div class="feats">{features}</div>
</section>

<section id="audit" class="card">
  <h2>门禁运行时间线 <span class="pill pill-muted">最近 {n_runs}</span></h2>
  <p style="font-size:.82rem;color:#64748b;margin-bottom:.6rem">来自 <code>.aiforge/audit/gates.jsonl</code>(append-only 本地流水,writer-only 非防篡改)。</p>
  <div class="tablewrap"><table>
    <thead><tr><th>时间</th><th>门禁</th><th>特性</th><th>结果</th></tr></thead>
    <tbody>{audit}</tbody>
  </table></div>
</section>

<section id="contracts" class="card">
  <h2>冻结契约 <span class="pill pill-muted">{n_contracts}</span></h2>
  <p style="font-size:.82rem;color:#64748b;margin-bottom:.5rem">接口级约定,改了走 PR + 人审 + 异构评审。全文见 <code>specs/contracts/</code>。</p>
  <ul class="contracts">{contracts}</ul>
</section>

<section id="journey" class="card">
  <h2>最近历程 <span class="pill pill-muted">git</span></h2>
  {commits}
</section>

<footer style="text-align:center;color:#94a3b8;font-size:.78rem;margin:1rem 0 2rem">
  由 <code>aiforge project-dashboard</code> 读真实状态生成 · {generated_at} · 单文件 HTML,重跑即最新
</footer>
</div>
</body>
</html>"""
