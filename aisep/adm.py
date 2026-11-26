"""ADM 向导（docs/specs/adm-wizard.md）：按阶段从模型查出「已有什么、缺什么」，可选生成交付物 Markdown。

检查项是 docs/queries/adm/*.rq，文件头注释声明 adm-phase、section、kind（inventory / gap）、title、source（gap 必填）。
模型范围写在查询里唯一的一行 VALUES ?model { <…> }，运行时换成 --model 指定的模型。
只读：不写文件（--out 除外，由 tools/aisep.py 处理）、不存任何进度状态（ADR-013）；有缺口也不算失败。
"""
import glob
import os
import re

from aisep import gitio
from aisep.core import ROOT, Ctx, discover, l4, short, shown
from aisep.errors import AisepError

PHASES = {  # 顺序即总纲 §3 裁剪后 ADM 的顺序
    "01-vision": "架构愿景",
    "requirements": "需求管理",
    "02-business": "业务架构",
    "03-data": "数据架构",
    "04-app-tech": "应用 + 技术架构",
    "05-roadmap": "路线图",
    "governance": "治理（实施治理与变更管理）",
}
MANUAL = {  # 交付物里要人写的叙述节（取各阶段 template.md 的节名），只放占位
    "01-vision": ["1. 背景与问题陈述", "8. 待决问题与风险"],
    "requirements": ["1. 访谈记录（AI 追问的结论）", "2. 业务语言复述 + 业务流程"],
    "02-business": ["6. 待决问题与风险"],
    "03-data": ["8. 待决问题与假设"],
    "04-app-tech": ["4. 集成方式", "9. 待决问题与假设"],
    "05-roadmap": ["2. 差距分析（机会与解决方案）", "6. 风险、依赖与迁移策略", "9. 待决问题与假设"],
    "governance": [],
}
QUERY_DIR = os.path.join("docs", "queries", "adm")
VALUES_RE = re.compile(r"VALUES\s+\?model\s*\{\s*<[^>]*>\s*\}")
HEADER_KEYS = ("adm-phase", "section", "kind", "title")


def load_checks(root=ROOT, paths=None):
    """[{file, phase, section, kind, title, source, query}] in file-name order; a malformed file is an error.
    paths 给出时只读这些检查项文件（调试单条或新写的查询，可在 docs/queries/adm/ 之外），按给出的顺序。"""
    checks = []
    for path in paths if paths else sorted(glob.glob(os.path.join(root, QUERY_DIR, "*.rq"))):
        shown_name = path if paths else f"{QUERY_DIR}/{os.path.basename(path)}"
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as e:
            raise AisepError("INVALID_ARGUMENT", f"读不了检查项 {shown_name}：{e}")
        meta = {}
        for line in text.splitlines():
            if not line.startswith("#"):
                break
            k, sep, v = line[1:].partition(":")
            if sep and k.strip() in HEADER_KEYS + ("source",):
                meta[k.strip()] = v.strip()
        name = os.path.basename(path)
        missing = [k for k in HEADER_KEYS if not meta.get(k)]
        if meta.get("kind") == "gap" and not meta.get("source"):
            missing.append("source")
        if missing or meta["adm-phase"] not in PHASES or meta["kind"] not in ("inventory", "gap") \
                or len(VALUES_RE.findall(text)) != 1:
            raise AisepError("INVALID_ARGUMENT", f"{shown_name}: 文件头缺 {missing or '合法取值'}，或 VALUES ?model 行不是恰好一行")
        checks.append({"file": name, "phase": meta["adm-phase"], "section": meta["section"], "kind": meta["kind"],
                       "title": meta["title"], "source": meta.get("source", ""), "query": text})
    return checks


def _sort_key(section, order):
    m = re.match(r"(\d+)\.", section)
    return (int(m.group(1)) if m else 1000, order)


def _provenance(root):
    rc, head, _ = gitio.git(root, "rev-parse", "--short=12", "HEAD")
    if rc != 0:
        return "不在 Git 检出中"
    _, dirty, _ = gitio.git(root, "--no-optional-locks", "status", "--porcelain", "--", "models", QUERY_DIR)
    return f"提交 {head.strip()}" + ("（models/ 或检查项有未提交改动）" if dirty.strip() else "")


def run(phase, slug, files, read=None, root=ROOT, check_files=None):
    """查一个阶段：返回 {sections: [(section, inventory_rows, gaps)], l4: [...], problems: [...], only: [...]}。
    check_files 给出时只跑这些检查项（only 列出其文件名），它们的 adm-phase 都必须是 phase。"""
    model = f"https://aisep.example/model/{slug}/"
    checks = load_checks(root, check_files)
    if check_files:
        wrong = [c["file"] for c in checks if c["phase"] != phase]
        if wrong:
            raise AisepError("INVALID_ARGUMENT", f"检查项 {'、'.join(wrong)} 的 adm-phase 不是 {phase}")
    else:
        checks = [c for c in checks if c["phase"] == phase]
    ctx = Ctx(discover(), files, read=read)
    l0 = [p for p in ctx.problems if p[1] == "L0"]
    if l0:
        return {"problems": l0}
    if not bool(ctx.store.query(f"ASK {{ <{model}> a <https://meta.linked.archi/core#Model> }}",
                                use_default_graph_as_union=True)):
        raise AisepError("MODEL_NOT_FOUND", f"模型 {model} 不存在（没有 arch:Model 声明）")
    sections = {}
    for c in checks:
        q = VALUES_RE.sub(f"VALUES ?model {{ <{model}> }}", c["query"])
        res = ctx.store.query(q, prefixes=ctx.prefixes, use_default_graph_as_union=True)
        names = [v.value for v in res.variables]
        rows = [{n: ("" if s[n] is None else (short(s[n]) if n in ("element", "type") else s[n].value)) for n in names}
                for s in res]
        sec = sections.setdefault(c["section"], {"order": len(sections), "inventory": None, "gaps": []})
        if c["kind"] == "inventory":
            sec["inventory"] = (sec["inventory"] or []) + rows
        else:
            sec["gaps"].append((c, rows))
    l4(ctx)
    prefix = short(model + "x")[:-1]
    found = [p for p in shown(ctx.problems, ("L4",)) if p[2].startswith(prefix)]
    ordered = sorted(sections.items(), key=lambda kv: _sort_key(kv[0], kv[1]["order"]))
    return {"sections": [(s, v["inventory"], v["gaps"]) for s, v in ordered], "l4": found, "problems": [],
            "only": [c["file"] for c in checks] if check_files else []}


def _cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def render(phase, slug, result, deliverable=False, root=ROOT):
    """Markdown。deliverable=True 时按阶段模板补上人写的叙述节占位。"""
    cmd = f"tools/aisep.py adm {phase} --model {slug}" + (" --deliverable" if deliverable else "")
    out = [f"# {PHASES[phase]}（{phase}）{'交付物' if deliverable else '现状'} · 模型 {slug}", "",
           f"> 由 `{cmd}` 从模型生成，依据{_provenance(root)}。以模型为准，重跑即更新；本文件不记录进度状态（ADR-013）。",
           "> 关口评审在 MVP 期间暂停（ADR-024 第 6 款）：入口条件里的批准一项只显示、不判定。",
           (f"> 只跑了指定的检查项：{'、'.join(f'`{f}`' for f in result['only'])}；不是本阶段的完整报告。"
            if result.get("only") else
            f"> 检查项见 `docs/queries/adm/{phase}-*.rq`，结构见阶段模板 `docs/adm/{phase}/template.md`。"), ""]
    blocks = [(s, "auto", inv, gaps) for s, inv, gaps in result["sections"]]
    if deliverable:
        blocks += [(s, "manual", None, []) for s in MANUAL[phase]]
    blocks.sort(key=lambda b: _sort_key(b[0], 0 if b[1] == "auto" else 1))
    empty, ngaps = [], 0
    for section, kind, inv, gaps in blocks:
        out += [f"## {section}", ""]
        if kind == "manual":
            out += ["<!-- 人工填写：见阶段模板同名节的提示 -->", ""]
            continue
        if inv is not None:
            if inv:
                out += [f"已有 {len(inv)} 个：", "", "| 元素 | 名称 | 类型 |", "|---|---|---|"]
                out += [f"| `{r['element']}` | {_cell(r.get('label', ''))} | `{r.get('type', '')}` |" for r in inv]
                out.append("")
            else:
                empty.append(section)
                out += ["本节还没有元素。", ""]
        for c, rows in gaps:
            if not rows:
                continue
            ngaps += len(rows)
            out.append(f"缺口：{c['title']}（{c['source']}）")
            out += [f"- `{r['element']}` {_cell(r.get('label', ''))}"
                    + (f"：{_cell(r['detail'])}" if r.get("detail") else "") for r in rows]
            out.append("")
    out += ["## 汇总", "", f"- 空节 {len(empty)} 个" + (f"：{'、'.join(empty)}" if empty else ""),
            f"- 缺口 {ngaps} 条", ""]
    out += ["## L4 发现项（本模型）", ""]
    out += [f"- [{s}] {t}" for s, _, t in result["l4"]] or ["- 无"]
    out += ["", "门禁结论以 `tools/aisep.py gate` 为准；本报告不改变 gate 结论。", ""]
    return "\n".join(out)


def overview(root=ROOT):
    checks = load_checks(root)
    lines = ["ADM 向导：tools/aisep.py adm <阶段> --model <slug> [--check 检查项.rq]... [--deliverable] [--out 路径]", "", "阶段：",]
    for p, name in PHASES.items():
        n = lambda k: sum(1 for c in checks if c["phase"] == p and c["kind"] == k)
        lines.append(f"  {p:<14}{name}：清单查询 {n('inventory')} 条，缺口查询 {n('gap')} 条")
    return "\n".join(lines) + "\n"
