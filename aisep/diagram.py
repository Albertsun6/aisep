"""ArchiMate 4 views → SVG, generated from the model (no coordinates are stored anywhere).

A view is either
  * declared: an `arch:Diagram` member of the model (`{model}view-{slug}`, spec §3); its elements and relationships are
    the model members that name it with `arch:inView`, plus every relationship whose two ends are both in the view;
  * a viewpoint projection: every model element whose asserted type is in the viewpoint's `arch:includesConcept`
    (vendor archimate4_viewpoints.ttl), plus every relationship whose two ends are both in the view.

Layout is ELK layered (elkjs, pinned in tools/elk/package-lock.json, run with Node) with fixed options and seed;
each ArchiMate domain band is an ELK partition, so bands stack top to bottom. Shapes, icons and colours follow the `amnode` renderer
of the AISEP architecture document. The output is a pure function of the model: same model, same bytes.
"""
import json, os, re, subprocess
from html import escape

from aisep.core import ARCH, NS

AM4 = NS["am4"]
AM4VP = NS["am4vp"]
SKOS = NS["skos"]

# ------------------------------------------------------------------ notation tables

# domain bands, top to bottom: (key, superclass in am4, Chinese title)
BANDS = [("mot", "MotivationElement", "动机"), ("str", "StrategyElement", "策略"),
         ("biz", "BusinessDomainElement", "业务"), ("com", "CommonDomainElement", "通用"),
         ("app", "ApplicationDomainElement", "应用"), ("tech", "TechnologyDomainElement", "技术"),
         ("imp", "ImplementationAndMigrationDomainElement", "实施与迁移"), ("oth", None, "其他")]

# am4 element local name -> (shape, icon); shapes: rect round cut obj event wave junction
SHAPES = {
    "BusinessActor": ("rect", "actor"), "Role": ("rect", "role"), "Collaboration": ("rect", "collab"),
    "BusinessInterface": ("rect", "ainterface"), "ApplicationInterface": ("rect", "ainterface"),
    "TechnologyInterface": ("rect", "ainterface"), "Service": ("round", "service"), "Process": ("round", "process"),
    "Function": ("round", "function"), "Event": ("event", None), "Path": ("rect", "path"),
    "BusinessObject": ("obj", None), "DataObject": ("obj", None), "ApplicationComponent": ("rect", "comp"),
    "Node": ("rect", "node"), "SystemSoftware": ("rect", "syssw"), "Artifact": ("rect", "artifact"),
    "Stakeholder": ("cut", "role"), "Driver": ("cut", "driver"), "Goal": ("cut", "goal"),
    "Outcome": ("cut", "outcome"), "Principle": ("cut", "principle"), "Requirement": ("cut", "requirement"),
    "Assessment": ("cut", None), "Value": ("cut", None), "Meaning": ("cut", None),
    "WorkPackage": ("round", "workpackage"), "Deliverable": ("wave", "deliverable"), "Plateau": ("rect", "plateau"),
    "AndJunction": ("junction", None), "OrJunction": ("junction", None),
}

ICON = {
    "actor": [("c", 8, 2.6, 2.2), ("p", "M8,4.8 V8.6 M4,6.3 H12 M8,8.6 L5,12 M8,8.6 L11,12")],
    "role": [("p", "M5,2 H12 A2.6,4 0 0 1 12,10 H5"), ("e", 5, 6, 2.6, 4)],
    "collab": [("c", 6, 6, 4.2), ("c", 10.5, 6, 4.2)],
    "service": [("r", 1, 3, 14, 7, 3.5)],
    "process": [("p", "M1,5 H10 V2.5 L15,6.5 L10,10.5 V8 H1 Z")],
    "function": [("p", "M2,4 L8,1 L14,4 V12 L8,9 L2,12 Z")],
    "comp": [("r", 4, 1, 11, 10, 0), ("r", 1.5, 3, 5, 2.4, 0), ("r", 1.5, 7, 5, 2.4, 0)],
    "ainterface": [("c", 11, 6, 3.4), ("p", "M1,6 H7.6")],
    "node": [("p", "M1,4 L4,1 H15 V9 L12,12 H1 Z M1,4 H12 V12 M12,4 L15,1")],
    "syssw": [("c", 7, 7, 4.4), ("p", "M6.5,2.8 A4.4,4.4 0 0 1 13.2,6.8")],
    "artifact": [("p", "M3,0.5 H10 L13,3.5 V11.5 H3 Z M10,0.5 V3.5 H13")],
    "driver": [("c", 8, 6, 4.6), ("p", "M8,0.4 V11.6 M2.4,6 H13.6 M4,2 L12,10 M12,2 L4,10"), ("cf", 8, 6, 1.5)],
    "goal": [("c", 8, 6, 5.4), ("c", 8, 6, 3.2), ("cf", 8, 6, 1.1)],
    "outcome": [("c", 7, 7, 4.6), ("c", 7, 7, 2.4), ("p", "M8,6 L14.5,0.5 M11.8,0.5 H14.5 V3.2")],
    "principle": [("r", 4, 0.5, 8, 11, 0), ("p", "M8,2.6 V7.4"), ("cf", 8, 9.4, 0.7)],
    "requirement": [("p", "M4.5,1 H15 L11.5,11 H1 Z")],
    "workpackage": [("p", "M12.8,8.5 A5,4.6 0 1 1 9.5,1.5"), ("p", "M8.2,-0.4 L10.2,1.6 L8.2,3.6")],
    "deliverable": [("p", "M1,1 H15 V9 Q11.5,6.6 8,9 T1,9 Z")],
    "plateau": [("p", "M5,2 H15 M3,6 H13 M1,10 H11")],
    "path": [("p", "M1,6 H15"), ("p", "M4,3.5 L1,6 L4,8.5 M12,3.5 L15,6 L12,8.5")],
}

# am4 relationship local name -> (path class, marker-start, marker-end); nearest ancestor wins (ReadAccess → Access …)
EDGES = {
    "Serving": ("e", None, "m-open"), "Realization": ("e e-dot", None, "m-tri"),
    "Assignment": ("e", "m-dot", "m-fill"), "Access": ("e e-acc", None, None),
    "ReadAccess": ("e e-acc", "m-open-s", None), "WriteAccess": ("e e-acc", None, "m-open-s"),
    "ReadWriteAccess": ("e e-acc", "m-open-s", "m-open-s"), "Flow": ("e e-d", None, "m-fill"),
    "Triggering": ("e", None, "m-fill"), "Composition": ("e", "m-dia-f", None),
    "Aggregation": ("e", "m-dia-h", None), "Influence": ("e e-d", None, "m-open"),
    "Association": ("e", None, None), "DirectedAssociation": ("e", None, "m-open"),
    "Specialization": ("e", None, "m-tri"),
}

ZH = {"MotivationElement": "动机", "Requirement": "需求", "Driver": "驱动因素", "Goal": "目标", "Outcome": "成果",
      "Principle": "原则", "Stakeholder": "干系人", "Assessment": "评估", "Value": "价值", "Meaning": "含义",
      "Role": "角色", "Process": "过程", "Function": "功能", "Service": "服务", "Event": "事件",
      "BusinessActor": "业务参与者", "BusinessObject": "业务对象", "DataObject": "数据对象",
      "ApplicationComponent": "应用组件", "ApplicationInterface": "应用接口", "Node": "节点",
      "SystemSoftware": "系统软件", "Artifact": "制品", "WorkPackage": "工作包", "Deliverable": "可交付物",
      "Plateau": "平台期", "Collaboration": "协作", "Serving": "服务于", "Realization": "实现",
      "Assignment": "指派", "Access": "访问", "ReadAccess": "读", "WriteAccess": "写", "ReadWriteAccess": "读写",
      "Flow": "流", "Triggering": "触发", "Composition": "组合", "Aggregation": "聚合", "Influence": "影响",
      "Association": "关联", "DirectedAssociation": "有向关联", "Specialization": "特化"}

NODE_W, BAND_PAD, LABEL_W, MARGIN = 168, 18, 64, 20

STYLE = """
svg{--bg:#ffffff;--fg:#18202d;--muted:#586375;--edge:#3d495b;--band:#f3f5f8;
 --am-biz:#fff4b3;--am-app:#c4edf7;--am-tech:#ccedc4;--am-mot:#ddd9f7;--am-imp:#fadcdc;--am-com:#eae4d7;
 --am-str:#f5deaa;--am-oth:#e2e5ea;--am-fg:#1c2230;--am-stroke:#596071}
@media (prefers-color-scheme:dark){svg{--bg:#151b24;--fg:#e5eaf1;--muted:#9ba6b7;--edge:#a9b3c2;--band:#1b222d;
 --am-biz:#4a4526;--am-app:#1e4550;--am-tech:#23442a;--am-mot:#38355b;--am-imp:#4c2e31;--am-com:#453e35;
 --am-str:#4d3f24;--am-oth:#33393f;--am-fg:#eef0f4;--am-stroke:#9aa3b2}}
text{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.bg{fill:var(--bg)} .band{fill:var(--band)} .band-t{font-size:12px;font-weight:600;fill:var(--muted)}
.title{font-size:16px;font-weight:600;fill:var(--fg)} .sub{font-size:11px;fill:var(--muted)}
.am{stroke:var(--am-stroke);stroke-width:1.1} .am-t{font-size:12px;font-weight:500;fill:var(--am-fg)}
.am-biz{fill:var(--am-biz)} .am-app{fill:var(--am-app)} .am-tech{fill:var(--am-tech)} .am-mot{fill:var(--am-mot)}
.am-imp{fill:var(--am-imp)} .am-com{fill:var(--am-com)} .am-str{fill:var(--am-str)} .am-oth{fill:var(--am-oth)}
.ico{fill:none;stroke:var(--am-fg);stroke-width:1.1;stroke-linecap:round;stroke-linejoin:round}
.ico-f{fill:var(--am-fg);stroke:none}
.e{fill:none;stroke:var(--edge);stroke-width:1.3} .e-d{stroke-dasharray:6 4} .e-dot{stroke-dasharray:2 3}
.e-acc{stroke-dasharray:1.5 3}
.mk-s{fill:none;stroke:var(--edge);stroke-width:1.4;stroke-linejoin:round} .mk-f{fill:var(--edge)}
.mk-h{fill:var(--bg);stroke:var(--edge);stroke-width:1.2}
.lg-t{font-size:11px;fill:var(--fg)} .lg-h{font-size:11px;font-weight:600;fill:var(--muted)}
"""

MARKERS = """<defs>
<marker id="m-open" viewBox="0 0 10 10" refX="9.2" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path class="mk-s" d="M1,1 L9,5 L1,9"/></marker>
<marker id="m-open-s" viewBox="0 0 10 10" refX="9.2" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path class="mk-s" d="M1,1 L9,5 L1,9"/></marker>
<marker id="m-fill" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path class="mk-f" d="M0,1 L10,5 L0,9 Z"/></marker>
<marker id="m-tri" viewBox="-1 -1 14 14" refX="12" refY="6" markerWidth="13" markerHeight="13" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-h" d="M0,0 L12,6 L0,12 Z"/></marker>
<marker id="m-dot" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="8" markerHeight="8" orient="auto" markerUnits="userSpaceOnUse"><circle class="mk-f" cx="4" cy="4" r="3"/></marker>
<marker id="m-dia-f" viewBox="-1 -1 14 12" refX="0" refY="5" markerWidth="14" markerHeight="12" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-f" d="M0,5 L6,1.5 L12,5 L6,8.5 Z"/></marker>
<marker id="m-dia-h" viewBox="-1 -1 14 12" refX="0" refY="5" markerWidth="14" markerHeight="12" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-h" d="M0,5 L6,1.5 L12,5 L6,8.5 Z"/></marker>
</defs>"""


def local(iri):
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def f(v):
    """Fixed-precision number for stable output."""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


# ------------------------------------------------------------------ selecting a view

def _members(ctx, model):
    """Model members written in the sources: iri -> asserted types."""
    rows = ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inModel <{model}> }}")
    return {x: ctx.asserted.get(x, []) for (x,) in rows if x in ctx.asserted}


def _am4_type(ctx, types):
    """The most specific asserted am4 type local name, or None."""
    am = sorted(t for t in types if t.startswith(AM4))
    am = [t for t in am if not any(u != t and t in ctx.ancestors(u) for u in am)]
    return local(am[0]) if am else None


def select(ctx, model, view=None, viewpoint=None):
    """(title, subtitle, elements, relationships, warnings). elements: [{iri,type,label,band,definition}];
    relationships: [{iri,type,source,target}]. Exactly one of view / viewpoint."""
    members = _members(ctx, model)
    ends = {}  # a relationship with several sources/targets is an L1 Violation; still pick deterministically
    for x, s, t in sorted(ctx.rows(
            f"SELECT ?x ?s ?t WHERE {{ ?x arch:inModel <{model}> ; arch:source ?s ; arch:target ?t }}")):
        ends.setdefault(x, (s, t))
    warnings = []
    if view:
        if view not in members or not ctx.is_a(view, ARCH + "Diagram"):
            raise ValueError(f"{view} is not an arch:Diagram in model {model}")
        vps = sorted(v for (v,) in ctx.rows(f"SELECT ?v WHERE {{ <{view}> arch:viewConformsToViewpoint ?v }}"))
        inview = {x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ ?x arch:inView <{view}> }}")}
        elem_iris = {x for x in inview if x in members and x not in ends}
        explicit_rels = {x for x in inview if x in ends}
        title, vp = ctx.label(view) or local(view), (vps[0] if vps else None)
    else:
        vp = AM4VP + viewpoint  # the CLI accepts only a plain viewpoint name
        concepts = {c for (c,) in ctx.rows(f"SELECT ?c WHERE {{ <{vp}> arch:includesConcept ?c }}")}
        if not concepts:
            raise ValueError(f"unknown viewpoint or viewpoint without arch:includesConcept: {vp}")
        elem_iris = {x for x, ts in members.items() if x not in ends and set(ts) & concepts}
        explicit_rels = set()
        title = None
    concepts = {c for (c,) in ctx.rows(f"SELECT ?c WHERE {{ <{vp}> arch:includesConcept ?c }}")} if vp else set()
    vp_label = (ctx.label(vp) or local(vp)) if vp else "（未声明视点）"
    title = title or vp_label
    elements = []
    for x in sorted(elem_iris):
        types = members[x]
        if concepts and not set(types) & concepts:
            warnings.append(f"{x}: type not in viewpoint {local(vp)}")
        band = next((k for k, sup, _ in BANDS if sup and ctx.is_a(x, AM4 + sup)), "oth")
        d = ctx.rows(f'SELECT ?d WHERE {{ <{x}> skos:definition ?d FILTER(LANGMATCHES(LANG(?d),"zh")) }}')
        elements.append({"iri": x, "type": _am4_type(ctx, types) or local(sorted(types)[0]), "label": ctx.label(x),
                         "band": band, "definition": d[0][0] if d else ""})
    rels = []
    for x in sorted(set(ends) & set(members)):
        s, t = ends[x]
        if s in elem_iris and t in elem_iris and s != t:
            rels.append({"iri": x, "type": _am4_type(ctx, members[x]) or local(sorted(members[x])[0]),
                         "source": s, "target": t})
        elif x in explicit_rels:
            warnings.append(f"{x}: in view but an end is not, not drawn")
    sub = f"{local(model.rstrip('/'))} · {vp_label} · 元素 {len(elements)} · 关系 {len(rels)} · 由 tools/aisep.py diagram 从模型生成"
    return title, sub, elements, rels, warnings


# ------------------------------------------------------------------ text metrics

def tw(s, px):
    w = 0.0
    for ch in s:
        c = ord(ch)
        if c > 0x2E80: w += px
        elif ch.isupper(): w += px * 0.64
        elif ch.isalnum(): w += px * 0.56
        elif ch == " ": w += px * 0.3
        else: w += px * 0.42
    return w


def wrap(s, max_w, px):
    lines, cur = [], ""
    for ch in s:
        if tw(cur + ch, px) > max_w and cur.strip() and ch not in "，。、；：）」』！？,.;:)":
            lines.append(cur.strip()); cur = ch
        else:
            cur += ch
    if cur.strip():
        lines.append(cur.strip())
    return lines or [""]


# ------------------------------------------------------------------ layout (ELK, tools/elk)

ELK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "elk")
# Fixed options and a fixed seed: the same graph always gets the same coordinates (asserted by test_diagram.py).
ELK_OPTIONS = {
    "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.randomSeed": "1",
    "elk.partitioning.activate": "true", "elk.edgeRouting": "ORTHOGONAL",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.spacing.nodeNode": "28", "elk.layered.spacing.nodeNodeBetweenLayers": "46",
    "elk.spacing.edgeNode": "14", "elk.spacing.edgeEdge": "8",
    "elk.padding": f"[top=0,left={LABEL_W + BAND_PAD},bottom=0,right={BAND_PAD}]",
}


class RendererUnavailable(RuntimeError):
    """No layout, so no SVG: elkjs not installed (`elkjs-missing`), node not on PATH (`node-missing`), ELK ran out of
    time (`layout-timeout`) or failed or printed no JSON (`layout-failed`). A RuntimeError, so the CLI's handling is
    unchanged; the MCP view tool maps it to one error code."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


ELK_TIMEOUT = 120  # seconds


def elk_layout(graph):
    """Run tools/elk/layout.cjs (elkjs, pinned in tools/elk/package-lock.json) on an ELK JSON graph."""
    if not os.path.isdir(os.path.join(ELK_DIR, "node_modules", "elkjs")):
        raise RendererUnavailable("elkjs-missing", "elkjs is not installed: run `npm ci --prefix tools/elk --ignore-scripts`")
    try:
        p = subprocess.run(["node", os.path.join(ELK_DIR, "layout.cjs")], input=json.dumps(graph), cwd=ELK_DIR,
                           capture_output=True, text=True, timeout=ELK_TIMEOUT)
    except FileNotFoundError:
        raise RendererUnavailable("node-missing", "node is not on PATH (needed by elkjs; Node >= 20)") from None
    except subprocess.TimeoutExpired:
        raise RendererUnavailable("layout-timeout", f"ELK layout did not finish in {ELK_TIMEOUT} s") from None
    if p.returncode != 0:
        raise RendererUnavailable("layout-failed", f"ELK layout failed: {p.stderr.strip()[-400:]}")
    try:  # a JSONDecodeError is a ValueError, which callers read as "bad input": it is the layout that failed
        return json.loads(p.stdout)
    except ValueError:
        raise RendererUnavailable("layout-failed", f"ELK layout printed no JSON: {p.stdout.strip()[:200]!r}") from None


# XML 1.0 Char (production [2]); anything else (C0 controls but tab/LF/CR, U+FFFE/FFFF, lone surrogates) makes the
# document not well-formed, and no escape can carry it. The SVG renderers refuse such text rather than drop it silently.
NOT_XML_CHAR = re.compile("[^\t\n\r\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


class TextNotXml(ValueError):
    """Model text has a character XML 1.0 cannot carry. Its own class, so callers map only this refusal to
    `text-not-xml` and any other ValueError from a renderer stays an internal error."""


def check_xml_text(*values):
    """Raise TextNotXml if a string anywhere in values (dicts, lists, tuples, sets walked) has a character XML 1.0
    cannot carry. Run before layout, so a refused view costs no node process."""
    stack = list(values)
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            c = NOT_XML_CHAR.search(v)
            if c:
                raise TextNotXml(f"model text contains U+{ord(c.group()):04X}, a character XML 1.0 cannot carry: {v[:80]!r}")
        elif isinstance(v, dict):
            stack.extend(v.keys()); stack.extend(v.values())
        elif isinstance(v, (list, tuple, set, frozenset)):
            stack.extend(v)


def layout(elements, rels, lines):
    """{iri: (x, y, w, h)}, {rel iri: [(x, y), ...]} from ELK. Nodes are sized by their wrapped labels; each ArchiMate
    domain band is an ELK partition, so bands come out top to bottom without overlapping."""
    order = [k for k, _, _ in BANDS]
    nid = {e["iri"]: f"n{i}" for i, e in enumerate(elements)}
    graph = {"id": "root", "layoutOptions": ELK_OPTIONS,
             "children": [{"id": nid[e["iri"]], "width": NODE_W, "height": max(54, 22 + 16 * len(lines[e["iri"]])),
                           "layoutOptions": {"elk.partitioning.partition": str(order.index(e["band"]))}}
                          for e in elements],
             "edges": [{"id": f"e{i}", "sources": [nid[r["source"]]], "targets": [nid[r["target"]]]}
                       for i, r in enumerate(rels)]}
    out = elk_layout(graph)
    pos = {c["id"]: (c["x"], c["y"], c["width"], c["height"]) for c in out.get("children", [])}
    routes = {}
    for e in out.get("edges", []):
        s = e["sections"][0]
        routes[e["id"]] = [(s["startPoint"]["x"], s["startPoint"]["y"])] + \
                          [(b["x"], b["y"]) for b in s.get("bendPoints", [])] + [(s["endPoint"]["x"], s["endPoint"]["y"])]
    return ({e["iri"]: pos[nid[e["iri"]]] for e in elements},
            {r["iri"]: routes[f"e{i}"] for i, r in enumerate(rels)}, out.get("width", 0), out.get("height", 0))



# ------------------------------------------------------------------ rendering

def _shape(e, x, y, w, h):
    shape = SHAPES.get(e["type"], ("rect", None))[0]
    cls = f'am am-{e["band"]}'
    if shape in ("rect", "obj"):
        out = [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="1.5" class="{cls}"/>']
        if shape == "obj":
            out.append(f'<line x1="{f(x)}" y1="{f(y + 16)}" x2="{f(x + w)}" y2="{f(y + 16)}" class="am"/>')
        return out
    if shape == "round":
        return [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="12" class="{cls}"/>']
    if shape == "cut":
        c = 10
        return [f'<path d="M{f(x + c)},{f(y)} H{f(x + w - c)} L{f(x + w)},{f(y + c)} V{f(y + h - c)} L{f(x + w - c)},'
                f'{f(y + h)} H{f(x + c)} L{f(x)},{f(y + h - c)} V{f(y + c)} Z" class="{cls}"/>']
    if shape == "event":
        return [f'<path d="M{f(x)},{f(y)} H{f(x + w - h / 2)} A{f(h / 2)},{f(h / 2)} 0 0 1 {f(x + w - h / 2)},{f(y + h)} '
                f'H{f(x)} L{f(x + 14)},{f(y + h / 2)} Z" class="{cls}"/>']
    if shape == "wave":
        return [f'<path d="M{f(x)},{f(y)} H{f(x + w)} V{f(y + h - 8)} Q{f(x + w * 0.75)},{f(y + h - 20)} {f(x + w / 2)},'
                f'{f(y + h - 8)} T{f(x)},{f(y + h - 8)} Z" class="{cls}"/>']
    return [f'<circle cx="{f(x + w / 2)}" cy="{f(y + h / 2)}" r="7" class="{cls}"/>']  # junction


def _icon(name, ox, oy):
    out = []
    for d in ICON.get(name or "", []):
        if d[0] in ("c", "cf"):
            out.append(f'<circle cx="{f(ox + d[1])}" cy="{f(oy + d[2])}" r="{f(d[3])}" class="{"ico" if d[0] == "c" else "ico-f"}"/>')
        elif d[0] == "e":
            out.append(f'<ellipse cx="{f(ox + d[1])}" cy="{f(oy + d[2])}" rx="{f(d[3])}" ry="{f(d[4])}" class="ico"/>')
        elif d[0] == "r":
            out.append(f'<rect x="{f(ox + d[1])}" y="{f(oy + d[2])}" width="{f(d[3])}" height="{f(d[4])}" rx="{f(d[5])}" class="ico"/>')
        else:
            out.append(f'<path d="{d[1]}" transform="translate({f(ox)},{f(oy)})" class="ico"/>')
    return out


def render(title, sub, elements, rels):
    check_xml_text(title, sub, elements, rels)
    by = {e["iri"]: e for e in elements}
    lines = {e["iri"]: wrap(e["label"], NODE_W - 48, 12) for e in elements}
    box, route, gw, gh = layout(elements, rels, lines) if elements else ({}, {}, 0, 0)
    top = MARGIN + 46 + BAND_PAD  # graph origin
    width = max(MARGIN * 2 + gw, 560)
    # bands: vertical extent of each band's nodes (ELK partitions do not interleave)
    bands = []
    for key, _, name in BANDS:
        ys = [(box[e["iri"]][1], box[e["iri"]][1] + box[e["iri"]][3]) for e in elements if e["band"] == key]
        if ys:
            bands.append((name, top + min(a for a, _ in ys) - BAND_PAD, top + max(b for _, b in ys) + BAND_PAD))
    y = top + gh + BAND_PAD + 24
    etypes = sorted({(e["band"], e["type"]) for e in elements}, key=lambda t: ([b[0] for b in BANDS].index(t[0]), t[1]))
    rtypes = sorted({r["type"] for r in rels})
    per_row = max(1, int((width - 2 * MARGIN - 60) // 150))
    leg_rows = -(-len(etypes) // per_row) + -(-len(rtypes) // per_row)
    height = y + 22 + leg_rows * 26 + MARGIN

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" '
           f'height="{f(height)}" role="img" aria-label="{escape(title)}">',
           f"<style>{STYLE}</style>", MARKERS,
           f'<rect class="bg" x="0" y="0" width="{f(width)}" height="{f(height)}"/>',
           f'<text x="{MARGIN}" y="{MARGIN + 14}" class="title">{escape(title)}</text>',
           f'<text x="{MARGIN}" y="{MARGIN + 32}" class="sub">{escape(sub)}</text>']
    for name, y0, y1 in bands:
        out.append(f'<rect class="band" x="{MARGIN}" y="{f(y0)}" width="{f(width - 2 * MARGIN)}" height="{f(y1 - y0)}" rx="8"/>')
        out.append(f'<text class="band-t" x="{MARGIN + 12}" y="{f(y0 + 20)}">{name}</text>')
    for r in rels:
        pts = [(MARGIN + x, top + y_) for x, y_ in route[r["iri"]]]
        d = "M" + " L".join(f"{f(x)},{f(y_)}" for x, y_ in pts)
        cls, ms, me = EDGES.get(r["type"], ("e", None, None))
        mk = (f' marker-start="url(#{ms})"' if ms else "") + (f' marker-end="url(#{me})"' if me else "")
        tip = f'{ZH.get(r["type"], r["type"])}：{by[r["source"]]["label"]} → {by[r["target"]]["label"]}'
        out.append(f'<path data-kind="relationship" data-iri="{escape(r["iri"])}" data-type="am4:{escape(r["type"])}" '
                   f'data-source="{escape(r["source"])}" data-target="{escape(r["target"])}" '
                   f'd="{d}" class="{cls}"{mk}><title>{escape(tip)}</title></path>')
    for n in sorted(box):
        e = by[n]
        x, y0, w, h = MARGIN + box[n][0], top + box[n][1], box[n][2], box[n][3]
        shape, icon = SHAPES.get(e["type"], ("rect", None))
        tip = f'{ZH.get(e["type"], e["type"])}：{e["label"]}' + (f'\n{e["definition"]}' if e["definition"] else "")
        out.append(f'<g data-kind="element" data-iri="{escape(n)}" data-type="am4:{escape(e["type"])}" '
                   f'data-box="{f(x)} {f(y0)} {f(w)} {f(h)}"><title>{escape(tip)}</title>')
        out += _shape(e, x, y0, w, h)
        out += _icon(icon, x + w - 21, y0 + 6)
        t0 = y0 + (16 if shape == "obj" else 0)
        ty = t0 + (y0 + h - t0) / 2 - 8 * len(lines[n]) + 12
        for k, s in enumerate(lines[n]):
            out.append(f'<text x="{f(x + w / 2)}" y="{f(ty + 16 * k)}" text-anchor="middle" class="am-t">{escape(s)}</text>')
        out.append("</g>")
    out.append(f'<text class="lg-h" x="{MARGIN}" y="{f(y + 12)}">图例</text>')
    ly = y + 22
    for i, (band, t) in enumerate(etypes):
        lx, yy = MARGIN + 60 + (i % per_row) * 150, ly + (i // per_row) * 26
        out += _shape({"type": t, "band": band}, lx, yy, 30, 18)
        out += _icon(SHAPES.get(t, ("rect", None))[1], lx + 7, yy + 3)
        out.append(f'<text class="lg-t" x="{f(lx + 36)}" y="{f(yy + 13)}">{escape(ZH.get(t, t))}</text>')
    ly += -(-len(etypes) // per_row) * 26
    for i, t in enumerate(rtypes):
        lx, yy = MARGIN + 60 + (i % per_row) * 150, ly + (i // per_row) * 26 + 9
        cls, ms, me = EDGES.get(t, ("e", None, None))
        mk = (f' marker-start="url(#{ms})"' if ms else "") + (f' marker-end="url(#{me})"' if me else "")
        out.append(f'<path d="M{f(lx + 2)},{f(yy)} L{f(lx + 32)},{f(yy)}" class="{cls}"{mk}/>')
        out.append(f'<text class="lg-t" x="{f(lx + 40)}" y="{f(yy + 4)}">{escape(ZH.get(t, t))}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
