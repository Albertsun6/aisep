"""UML class diagrams → SVG, generated from the model (no coordinates are stored anywhere). `aisep.py diagram --uml`.

A class diagram is either
  * a projection (`--uml ClassDiagram --model SLUG`): every classifier of the model whose asserted type is in NODE_TYPES;
  * declared: an `arch:Diagram` whose viewpoint is umlvp:ClassDiagram; its arch:inView members of those types.
Edges: every relationship in EDGE_TYPES whose two ends are both drawn. Features (uml:Property, uml:Operation,
uml:EnumerationLiteral) owned by a drawn classifier through arch:HasPart are rows of its compartments; packages
(uml:Package) owning drawn classifiers through arch:HasPart are drawn as frames around them, an empty package is not drawn.
arch:HasPart is the ownership the gate accepts (uml:namespace is not a qualified relationship, G7).

Node and edge sets are named here rather than taken from umlvp:ClassDiagram's arch:includesConcept (uml_viewpoints.ttl
is not loaded by the uml module, and upstream lists features but neither relationships nor packages). uml:Component,
Node, Behavior and the other uml:Class subtypes are not class-diagram nodes. The upstream vocabulary has no association
ends and no property types, so end multiplicities, role names, navigability and attribute types cannot be drawn.

Notation follows UML 2.5.1 (§9 classifiers and features, §10 interfaces and data types, §11 associations, §7.7
dependencies): generalization and realization point a hollow triangle at the general end, with the general classifier
laid out above (the edge is fed to ELK reversed); aggregation / composition put a hollow / filled diamond at the source
(whole) end; dependencies are dashed with an open arrow at the supplier. Layout is the same pipeline as diagram_c4.py:
ELK layered with fixed options and seed, same model → same bytes. A relationship whose two ends are the same classifier
(a reflexive association, a self-dependency …) is drawn as an ELK self-loop, except the types in NO_SELF, which UML
does not allow on one classifier and which get their own warning. Anything that is in the diagram (or hangs on a drawn
classifier) but is not drawn is reported as a warning, never silently dropped. Scope, open questions and the acceptance
list: docs/specs/uml-class-diagram.md.
"""
import re
from html import escape

from aisep.core import ARCH, NS
from aisep.diagram import MARGIN, elk_layout, f, local, tw, wrap

UML = "https://meta.linked.archi/uml/onto#"
UMLVP = "https://meta.linked.archi/uml/viewpoints#"
DIAGRAMS = {"ClassDiagram": "UML 类图"}  # first batch (docs/specs/uml-class-diagram.md「首批范围」)

# asserted uml type -> keyword line (None: plain class)
NODE_TYPES = {"Class": None, "Interface": "«interface»", "DataType": "«dataType»", "Enumeration": "«enumeration»",
              "PrimitiveType": "«primitive»"}
FEATURE_TYPES = ("Property", "Operation", "EnumerationLiteral")
# asserted uml relationship type -> (Chinese name, path class, marker-start, marker-end, keyword, fed to ELK reversed)
EDGE_TYPES = {
    "Association": ("关联", "e", None, None, None, False),
    "Aggregation": ("聚合", "e", "u-dia-h", None, None, False),
    "Composition": ("组合", "e", "u-dia-f", None, None, False),
    "Generalization": ("泛化", "e", None, "u-tri", None, True),
    "InterfaceRealization": ("接口实现", "e e-d", None, "u-tri", None, True),
    "Realization": ("实现", "e e-d", None, "u-tri", None, True),
    "Abstraction": ("抽象", "e e-d", None, "u-open", "«abstraction»", False),
    "Usage": ("使用", "e e-d", None, "u-open", "«use»", False),
    "Dependency": ("依赖", "e e-d", None, "u-open", None, False),
}
EDGE_ORDER = list(EDGE_TYPES)
# relationship types whose two ends may not be the same classifier (anything else on one classifier is a self-loop)
NO_SELF = {"Generalization": "泛化不得成环（UML 2.5.1 Classifier 约束 no_cycles_in_generalization）",
           "InterfaceRealization": "接口实现的契约须是 Interface、实现方须是 BehavioredClassifier，不可能是同一个类元"}
# properties of an association end; on a relationship resource they cannot be tied to either end
END_PROPS = ("lower", "upper", "aggregationKind", "isOrdered", "isUnique", "isReadOnly", "isDerived", "defaultValue")
VIS = {"Public": "+", "Private": "-", "Protected": "#", "PackageVisibility": "~"}
ZH = {"Class": "类", "Interface": "接口", "DataType": "数据类型", "Enumeration": "枚举", "PrimitiveType": "基本类型"}

NODE_MIN_W, NODE_MAX_W, ROW = 150, 300, 16

STYLE = """
svg{--bg:#ffffff;--fg:#18202d;--muted:#586375;--edge:#3d495b;--cls:#fdf6e3;--cls-line:#7a6a45;--pkg:#f6f8fb;--pkg-line:#8f9aab}
@media (prefers-color-scheme:dark){svg{--bg:#151b24;--fg:#e5eaf1;--muted:#9ba6b7;--edge:#a9b3c2;--cls:#2e2a20;--cls-line:#b8a57a;
 --pkg:#121820;--pkg-line:#5d6878}}
text{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.bg{fill:var(--bg)} .title{font-size:16px;font-weight:600;fill:var(--fg)} .sub{font-size:11px;fill:var(--muted)}
.cls{fill:var(--cls);stroke:var(--cls-line);stroke-width:1.1} .sep{stroke:var(--cls-line);stroke-width:1}
.kw{font-size:11px;fill:var(--fg)} .cn{font-size:13px;font-weight:700;fill:var(--fg)} .ab{font-style:italic}
.tag{font-size:10px;fill:var(--muted)} .ft{font-size:12px;fill:var(--fg)} .st{text-decoration:underline}
.pkg{fill:var(--pkg);stroke:var(--pkg-line);stroke-width:1.2} .pkg-t{font-size:12px;font-weight:600;fill:var(--fg)}
.e{fill:none;stroke:var(--edge);stroke-width:1.3} .e-d{stroke-dasharray:6 4}
.mk-s{fill:none;stroke:var(--edge);stroke-width:1.4;stroke-linejoin:round} .mk-f{fill:var(--edge)}
.mk-h{fill:var(--bg);stroke:var(--edge);stroke-width:1.2}
.elab{font-size:11px;fill:var(--fg)} .elab-bg{fill:var(--bg);opacity:.93}
.lg-t{font-size:11px;fill:var(--fg)} .lg-h{font-size:11px;font-weight:600;fill:var(--muted)}
"""

MARKERS = """<defs>
<marker id="u-open" viewBox="0 0 10 10" refX="9.2" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path class="mk-s" d="M1,1 L9,5 L1,9"/></marker>
<marker id="u-tri" viewBox="-1 -1 14 14" refX="12" refY="6" markerWidth="13" markerHeight="13" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-h" d="M0,0 L12,6 L0,12 Z"/></marker>
<marker id="u-dia-f" viewBox="-1 -1 14 12" refX="0" refY="5" markerWidth="14" markerHeight="12" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-f" d="M0,5 L6,1.5 L12,5 L6,8.5 Z"/></marker>
<marker id="u-dia-h" viewBox="-1 -1 14 12" refX="0" refY="5" markerWidth="14" markerHeight="12" orient="auto" markerUnits="userSpaceOnUse"><path class="mk-h" d="M0,5 L6,1.5 L12,5 L6,8.5 Z"/></marker>
</defs>"""

ELK_OPTIONS = {
    "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.randomSeed": "1",
    "elk.hierarchyHandling": "INCLUDE_CHILDREN", "elk.edgeRouting": "ORTHOGONAL",
    "elk.json.shapeCoords": "ROOT", "elk.json.edgeCoords": "ROOT",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.spacing.nodeNode": "36", "elk.layered.spacing.nodeNodeBetweenLayers": "56",
    "elk.spacing.edgeNode": "16", "elk.spacing.edgeEdge": "10", "elk.spacing.edgeLabel": "4",
    "elk.padding": "[top=0,left=0,bottom=0,right=0]",
}
PKG_PADDING = "[top=44,left=16,bottom=16,right=16]"


# ------------------------------------------------------------------ reading the model

def _uml_types(ctx, x):
    """Asserted uml: local names of x."""
    return sorted(local(t) for t in ctx.asserted.get(x, ()) if t.startswith(UML))


def _value(ctx, x, prop):
    vs = sorted(v for (v,) in ctx.rows(f"SELECT ?v WHERE {{ <{x}> <{UML}{prop}> ?v }}"))
    return vs[0] if vs else None


def _true(ctx, x, prop):
    return _value(ctx, x, prop) in ("true", "1")


def _bound(v, upper):
    """Lexical form of a multiplicity bound -> its display text, or None if it is not a legal bound.
    UML 2.5.1 §7.5.4: "*" is the unlimited upper bound; the vocabulary writes it as a negative integer (-1)."""
    v = v.strip()
    if upper and v == "*":
        return "*"
    if not re.fullmatch(r"[+-]?[0-9]+", v):
        return None
    n = int(v)
    if n < 0:
        return "*" if upper else None
    return str(n)


def _mult(ctx, x, warnings):
    lo, up = _value(ctx, x, "lower"), _value(ctx, x, "upper")
    if lo is None and up is None:
        return ""
    lo_t = "1" if lo is None else _bound(lo, False)
    up_t = "1" if up is None else _bound(up, True)
    bad = [f"uml:{p} {v!r}" for p, v, t in (("lower", lo, lo_t), ("upper", up, up_t)) if t is None]
    if bad:
        warnings.append(f"{x}: 多重性 {', '.join(bad)} 不是合法的界（下界为非负整数，上界为非负整数、* 或 -1），多重性未画")
        return ""
    if up_t != "*" and int(up_t) < int(lo_t):  # UML 2.5.1 §7.8.8 upper_ge_lower, also when a bound is the default 1
        warnings.append(f"{x}: 多重性 [{lo_t}..{up_t}] 的上界小于下界（UML 2.5.1 upper_ge_lower；未写的界按 1 计），多重性未画")
        return ""
    return f"[{lo_t}]" if lo_t == up_t else f"[{lo_t}..{up_t}]"


def _feature(ctx, x, warnings):
    """{iri, kind, text, italic, static} for one compartment row."""
    ts = _uml_types(ctx, x)
    kind = next(k for k in FEATURE_TYPES if k in ts)
    name = ctx.label(x) or local(x)
    vis = VIS.get(local(_value(ctx, x, "visibility") or ""), "")
    pre = (vis + " ") if vis else ""
    if kind == "Property":
        text = pre + ("/" if _true(ctx, x, "isDerived") else "") + name
        m = _mult(ctx, x, warnings)
        text += (" " + m if m else "")
        dv = _value(ctx, x, "defaultValue")
        text += (f" = {dv}" if dv is not None else "") + (" {readOnly}" if _true(ctx, x, "isReadOnly") else "")
    elif kind == "Operation":
        text = pre + name + "()"
    else:
        text = name
    return {"iri": x, "kind": kind, "text": text, "italic": kind == "Operation" and _true(ctx, x, "isAbstract"),
            "static": _true(ctx, x, "isStatic")}


def select(ctx, model, view=None, diagram="ClassDiagram"):
    """(title, subtitle, nodes, packages, edges, warnings). nodes: {iri: {type, label, keyword, abstract, package,
    attrs, ops}}; packages: {iri: {label, parent}}; edges: [{iri, type, source, target, label}]."""
    if diagram not in DIAGRAMS:
        raise ValueError(f"UML 图种 {diagram} 暂不支持（首批只有 {', '.join(DIAGRAMS)}）")
    members = {x for (x,) in ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inModel <{model}> }}") if x in ctx.asserted}
    ends = {}
    for x, s, t in sorted(ctx.rows(
            f"SELECT ?x ?s ?t WHERE {{ ?x arch:inModel <{model}> ; arch:source ?s ; arch:target ?t }}")):
        ends.setdefault(x, (s, t))
    warnings = []

    def node_type(x):
        ts = [t for t in _uml_types(ctx, x) if t in NODE_TYPES]
        return ts and not set(_uml_types(ctx, x)) - set(NODE_TYPES) and \
            sorted(ts, key=lambda t: list(NODE_TYPES).index(t))[-1]

    if view:
        inview = {x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ ?x arch:inView <{view}> }}")}
        drawn = {x for x in inview if x in members and x not in ends and node_type(x)}
        title = ctx.label(view) or local(view)
    else:
        inview = set()
        drawn = {x for x in members if x not in ends and node_type(x)}
        title = f"{DIAGRAMS[diagram]}：{local(model.rstrip('/'))}"

    # ownership: arch:HasPart owner -> part (first owner by IRI when there are several)
    owners = {}
    for x in sorted(members & set(ends)):
        if ctx.is_a(x, ARCH + "HasPart"):
            s, t = ends[x]
            owners.setdefault(t, []).append((s, x))
    is_pkg = lambda x: "Package" in _uml_types(ctx, x)
    is_feat = lambda x: any(k in _uml_types(ctx, x) for k in FEATURE_TYPES)
    owner = {}
    for part, os_ in sorted(owners.items()):
        os_ = sorted(os_)
        owner[part] = os_[0][0]
        if len(os_) > 1 and (part in drawn or any(o in drawn for o, _ in os_)):
            warnings.append(f"{part}: 归属不唯一（{', '.join(o for o, _ in os_)}），按 IRI 序取第一个 {os_[0][0]}")

    nodes, feats_of = {}, {}
    for part, o in sorted(owner.items()):
        if o not in drawn:
            continue
        if is_feat(part):
            feats_of.setdefault(o, []).append(part)
        elif not (part in drawn and is_pkg(o)):
            ty = ", ".join(f"uml:{t}" for t in _uml_types(ctx, part)) or "非 UML 元素"
            rel = next(r for s, r in owners[part] if s == o)
            warnings.append(f"{rel}: HasPart 目标 {part}（{ty}）不能画进类元栏，未画")

    # package frames: the chain of owning packages of each drawn node (stops on a cycle)
    packages, pkg_of = {}, {}
    for x in sorted(drawn):
        o = owner.get(x)
        pkg_of[x] = o if o and is_pkg(o) else None
        seen = []
        while o and is_pkg(o) and o not in seen:
            seen.append(o)
            nxt = owner.get(o)
            if nxt in seen:
                warnings.append(f"{o}: 包嵌套成环（{' → '.join(seen + [nxt])}），在 {o} 处截断")
                nxt = None
            packages.setdefault(o, {"label": ctx.label(o) or local(o), "parent": nxt if nxt and is_pkg(nxt) else None})
            o = nxt
    warnings = list(dict.fromkeys(warnings))  # a cycle is met once per node inside it

    for x in sorted(drawn):
        t = node_type(x)
        rows = [_feature(ctx, p, warnings) for p in sorted(feats_of.get(x, []))]
        nodes[x] = {"type": t, "label": ctx.label(x) or local(x), "keyword": NODE_TYPES[t],
                    "abstract": t == "Class" and _true(ctx, x, "isAbstract"), "package": pkg_of[x],
                    "attrs": [r for r in rows if r["kind"] != "Operation"], "ops": [r for r in rows if r["kind"] == "Operation"]}

    edges = []
    for x in sorted(set(ends) & members):
        s, t = ends[x]
        ts = _uml_types(ctx, x)
        if not ts:
            continue  # arch:Refines, arch:HasPart …: not drawn as lines
        cand = [k for k in ts if k in EDGE_TYPES]  # most specific of the asserted supported types
        kind = next((k for k in cand if not any(u != k and UML + k in ctx.ancestors(UML + u) for u in cand)), None)
        if set(ts) - set(EDGE_TYPES):  # e.g. uml:Deployment (a Dependency) is not a class-diagram line
            kind = None
        if s in drawn and t in drawn:
            if kind is None:
                warnings.append(f"{x}: 关系 {', '.join('uml:' + u for u in ts)} 不在类图范围，未画")
                continue
            if s == t and kind in NO_SELF:
                warnings.append(f"{x}: uml:{kind} 的两端是同一个类元 {s}，{NO_SELF[kind]}，未画")
                continue
            bad = [p for p in END_PROPS if _value(ctx, x, p) is not None]
            if bad:
                warnings.append(f"{x}: 关联端属性 {', '.join('uml:' + p for p in bad)} 无法对应到某一端，未画")
            edges.append({"iri": x, "type": kind, "source": s, "target": t, "label": ctx.label(x) or ""})
        elif x in inview:
            warnings.append(f"{x}: 关系在视图中，但有一端不在图中，未画")

    if view:
        drawn_feats = {r["iri"] for n in nodes.values() for r in n["attrs"] + n["ops"]}
        for x in sorted(inview - drawn - set(ends) - drawn_feats - set(packages)):
            ts = ", ".join(f"uml:{t}" for t in _uml_types(ctx, x)) or "非 UML 元素"
            warnings.append(f"{x}: 包里没有图中的类元，未画" if is_pkg(x) else
                            f"{x}: 特性的归属类元不在图中，未画" if is_feat(x) else f"{x}: 类型 {ts} 不在类图范围，未画")
    sub = (f"{local(model.rstrip('/'))} · {DIAGRAMS[diagram]} · 元素 {len(nodes)} · 关系 {len(edges)} · "
           f"由 tools/aisep.py diagram 从模型生成")
    return title, sub, nodes, packages, edges, warnings


# ------------------------------------------------------------------ layout

def _head(n):
    """Name compartment lines: (text, css class, line height)."""
    out = [(n["keyword"], "kw", 14)] if n["keyword"] else []
    out += [(s, "cn" + (" ab" if n["abstract"] else ""), 17) for s in wrap(n["label"], NODE_MAX_W - 24, 13)]
    if n["abstract"]:
        out.append(("{abstract}", "tag", 13))
    return out


def _size(n):
    head = _head(n)
    w = max([NODE_MIN_W] + [tw(s, 13 if c.startswith("cn") else 11) + 24 for s, c, _ in head] +
            [tw(r["text"], 12) + 20 for r in n["attrs"] + n["ops"]])
    h = sum(lh for _, _, lh in head) + 16
    if n["attrs"] or n["ops"]:
        h += 2 * 8 + ROW * (len(n["attrs"]) + len(n["ops"]))
    return round(w, 1), round(h, 1)


def _edge_text(e):
    kw = EDGE_TYPES[e["type"]][4]
    return " ".join(s for s in (kw, e["label"]) if s)


def layout(nodes, packages, edges):
    ids = {i: f"n{k}" for k, i in enumerate(sorted(set(nodes) | set(packages)))}
    kids = {}
    for i in sorted(nodes):
        kids.setdefault(nodes[i]["package"], []).append(i)
    for i in sorted(packages):
        kids.setdefault(packages[i]["parent"], []).append(i)

    def node(i):
        if i in packages:
            w = max(NODE_MIN_W, tw(packages[i]["label"], 12) + 40)
            return {"id": ids[i], "layoutOptions": {"elk.padding": PKG_PADDING, "elk.nodeSize.minimum": f"({round(w, 1)},80)",
                                                    "elk.nodeSize.constraints": "MINIMUM_SIZE"},
                    "children": [node(c) for c in kids.get(i, [])]}
        w, h = _size(nodes[i])
        return {"id": ids[i], "width": w, "height": h}

    elk_edges = []
    for k, e in enumerate(edges):
        a, b = (e["target"], e["source"]) if EDGE_TYPES[e["type"]][5] else (e["source"], e["target"])
        t = _edge_text(e)
        lab = [{"id": f"l{k}", "text": t, "width": round(tw(t, 11) + 8, 1), "height": 18}] if t else []
        elk_edges.append({"id": f"e{k}", "sources": [ids[a]], "targets": [ids[b]], "labels": lab})
    graph = {"id": "root", "layoutOptions": ELK_OPTIONS, "children": [node(i) for i in kids.get(None, [])],
             "edges": elk_edges}
    out = elk_layout(graph)
    pos, routes, labels = {}, {}, {}

    def walk(n):
        for c in n.get("children", []):
            pos[c["id"]] = (c["x"], c["y"], c["width"], c["height"]); walk(c)
        for e in n.get("edges", []):
            s = e["sections"][0]
            routes[e["id"]] = [(s["startPoint"]["x"], s["startPoint"]["y"])] + \
                [(p["x"], p["y"]) for p in s.get("bendPoints", [])] + [(s["endPoint"]["x"], s["endPoint"]["y"])]
            for lab in e.get("labels", []):
                labels[e["id"]] = (lab["x"], lab["y"], lab["width"], lab["height"])
    walk(out)
    rts = []
    for k, e in enumerate(edges):  # a reversed edge is drawn from the model source again
        r = routes[f"e{k}"]
        rts.append(r[::-1] if EDGE_TYPES[e["type"]][5] else r)
    return ({i: pos[ids[i]] for i in ids}, rts, [labels.get(f"e{k}") for k in range(len(edges))],
            out.get("width", 0), out.get("height", 0))


# ------------------------------------------------------------------ rendering

def _class_box(iri, n, x, y, w, h):
    tip = f'{ZH[n["type"]]}：{n["label"]}'
    out = [f'<g data-kind="element" data-iri="{escape(iri)}" data-type="uml:{n["type"]}" '
           f'data-parent="{escape(n["package"] or "")}" data-box="{f(x)} {f(y)} {f(w)} {f(h)}"><title>{escape(tip)}</title>',
           f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" class="cls"/>']
    cy = y + 8
    for s, cls, lh in _head(n):
        cy += lh
        out.append(f'<text x="{f(x + w / 2)}" y="{f(cy - 4)}" text-anchor="middle" class="{cls}">{escape(s)}</text>')
    cy += 8
    if n["attrs"] or n["ops"]:
        for rows in (n["attrs"], n["ops"]):
            out.append(f'<line x1="{f(x)}" y1="{f(cy)}" x2="{f(x + w)}" y2="{f(cy)}" class="sep"/>')
            cy += 4
            for r in rows:
                cls = "ft" + (" ab" if r["italic"] else "") + (" st" if r["static"] else "")
                out.append(f'<text data-kind="feature" data-iri="{escape(r["iri"])}" data-type="uml:{r["kind"]}" '
                           f'x="{f(x + 8)}" y="{f(cy + ROW - 4)}" class="{cls}">{escape(r["text"])}</text>')
                cy += ROW
            cy += 4
    out.append("</g>")
    return out


def render(title, sub, nodes, packages, edges):
    pos, routes, labs, gw, gh = layout(nodes, packages, edges)
    top = MARGIN + 52
    etypes = sorted({e["type"] for e in edges}, key=EDGE_ORDER.index)
    width = max(MARGIN * 2 + gw, 560)
    per_row = max(1, int((width - 2 * MARGIN - 60) // 150))
    y_leg = top + gh + 28
    height = y_leg + 22 + -(-len(etypes) // per_row) * 26 + MARGIN
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" '
           f'height="{f(height)}" role="img" aria-label="{escape(title)}">',
           f"<style>{STYLE}</style>", MARKERS,
           f'<rect class="bg" x="0" y="0" width="{f(width)}" height="{f(height)}"/>',
           f'<text x="{MARGIN}" y="{MARGIN + 14}" class="title">{escape(title)}</text>',
           f'<text x="{MARGIN}" y="{MARGIN + 32}" class="sub">{escape(sub)}</text>']

    def depth(i):
        n = 0
        while packages[i]["parent"]:
            i, n = packages[i]["parent"], n + 1
        return n
    for i in sorted(packages, key=lambda i: (depth(i), i)):
        p, (x, y, w, h) = packages[i], pos[i]
        x, y = MARGIN + x, top + y
        tab = min(w - 8, tw(p["label"], 12) + 20)
        out.append(f'<g data-kind="package" data-iri="{escape(i)}" data-type="uml:Package" '
                   f'data-parent="{escape(p["parent"] or "")}" data-box="{f(x)} {f(y)} {f(w)} {f(h)}">'
                   f'<title>{escape("包：" + p["label"])}</title>')
        out.append(f'<path d="M{f(x)},{f(y)} H{f(x + tab)} V{f(y + 24)} H{f(x + w)} V{f(y + h)} H{f(x)} Z" class="pkg"/>')
        out.append(f'<line x1="{f(x)}" y1="{f(y + 24)}" x2="{f(x + tab)}" y2="{f(y + 24)}" class="sep"/>')
        out.append(f'<text x="{f(x + 10)}" y="{f(y + 17)}" class="pkg-t">{escape(p["label"])}</text></g>')
    for k, e in enumerate(edges):
        name, cls, ms, me, _, _ = EDGE_TYPES[e["type"]]
        d = "M" + " L".join(f"{f(MARGIN + x)},{f(top + y)}" for x, y in routes[k])
        mk = (f' marker-start="url(#{ms})"' if ms else "") + (f' marker-end="url(#{me})"' if me else "")
        tip = f'{name}：{nodes[e["source"]]["label"]} → {nodes[e["target"]]["label"]}' + \
              (f'（{e["label"]}）' if e["label"] else "")
        out.append(f'<path data-kind="relationship" data-iri="{escape(e["iri"])}" data-type="uml:{e["type"]}" '
                   f'data-source="{escape(e["source"])}" data-target="{escape(e["target"])}" d="{d}" class="{cls}"{mk}>'
                   f'<title>{escape(tip)}</title></path>')
        if labs[k]:
            lx, ly, lw, lh = MARGIN + labs[k][0], top + labs[k][1], labs[k][2], labs[k][3]
            out.append(f'<rect x="{f(lx)}" y="{f(ly)}" width="{f(lw)}" height="{f(lh)}" rx="3" class="elab-bg"/>')
            out.append(f'<text x="{f(lx + lw / 2)}" y="{f(ly + 13)}" text-anchor="middle" class="elab">'
                       f'{escape(_edge_text(e))}</text>')
    for i in sorted(nodes):
        x, y, w, h = pos[i]
        out += _class_box(i, nodes[i], MARGIN + x, top + y, w, h)
    out.append(f'<text class="lg-h" x="{MARGIN}" y="{f(y_leg + 12)}">图例</text>')
    for n, t in enumerate(etypes):
        name, cls, ms, me, _, _ = EDGE_TYPES[t]
        lx, yy = MARGIN + 60 + (n % per_row) * 150, y_leg + 22 + (n // per_row) * 26 + 9
        mk = (f' marker-start="url(#{ms})"' if ms else "") + (f' marker-end="url(#{me})"' if me else "")
        out.append(f'<path d="M{f(lx + 2)},{f(yy)} L{f(lx + 34)},{f(yy)}" class="{cls}"{mk}/>')
        out.append(f'<text class="lg-t" x="{f(lx + 42)}" y="{f(yy + 4)}">{name}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
