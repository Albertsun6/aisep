"""C4 views → SVG, generated from the model (no coordinates are stored anywhere). Phase 2 of `aisep.py diagram`.

What a view contains follows Structurizr's `include *` (docs.structurizr.com/dsl/language#include):
  * SystemContext (scope: a software system S): S plus every person and software system directly connected to S;
  * ContainerDiagram (scope: S): the containers of S, inside S's boundary, plus the people and software systems
    directly connected to those containers;
  * ComponentDiagram (scope: a container C): the components of C, inside C's boundary, plus the people, software
    systems and containers of the same system directly connected to them;
  * C4Deployment (scope: an environment name): the deployment nodes of that environment (nested by arch:HasPart,
    a node without structurizr:environment inherits its parent's) and the containers deployed on them;
  * declared: an `arch:Diagram` whose viewpoint is a c4vp one; its arch:inView C4 members, an element containing
    another member drawn as a boundary around it.
"Directly connected" counts relationships of descendants: a c4:Using whose end is not drawn is lifted to the nearest
drawn ancestor (component → container → system). Like Structurizr's default implied relationships, a lifted one is
drawn only when the two drawn elements have no direct c4:Using in that direction; lifted ones between the same pair
are merged into one line that lists every c4:Using it stands for. arch:Refines (C4 → am4) is never drawn; containment,
arch:HasPart and structurizr:Deployment are drawn as nesting, not as lines.

Shapes and colours follow the `c4node` renderer of the AISEP architecture document. c4_viewpoints.ttl is not loaded:
the four viewpoint IRIs are only named here (c4vp:SystemContext, ContainerDiagram, ComponentDiagram, C4Deployment).
"""
from html import escape

from aisep.core import ARCH, NS
from aisep.diagram import MARGIN, check_xml_text, elk_layout, f, local, tw, wrap

C4 = "https://meta.linked.archi/c4/onto#"
SZ = "https://meta.linked.archi/c4/structurizr#"
C4VP = "https://meta.linked.archi/c4/viewpoints#"
VIEWPOINTS = {"SystemContext": "系统上下文图", "ContainerDiagram": "容器图", "ComponentDiagram": "组件图",
              "C4Deployment": "部署图"}

# kind, class (most specific first), Chinese name, fill class, text class
KINDS = [("extperson", C4 + "ExternalPerson", "外部人员", "c4-ext", "on-ext"),
         ("person", C4 + "Person", "人员", "c4-person", "on"),
         ("extsys", C4 + "ExternalSoftwareSystem", "外部系统", "c4-ext", "on-ext"),
         ("sys", C4 + "SoftwareSystem", "软件系统", "c4-sys", "on"),
         ("db", C4 + "Database", "数据库", "c4-cont", "on"),
         ("mobile", C4 + "MobileApp", "移动应用", "c4-cont", "on"),
         ("spa", C4 + "ClientSideWebApp", "单页应用", "c4-cont", "on"),
         ("cont", C4 + "Container", "容器", "c4-cont", "on"),
         ("comp", C4 + "Component", "组件", "c4-comp", "on-comp"),
         ("inode", SZ + "InfrastructureNode", "基础设施节点", "c4-ext", "on-ext"),
         ("dnode", SZ + "DeploymentNode", "部署节点", "dn", "")]
KIND = {k: (cls, zh, fill, txt) for k, cls, zh, fill, txt in KINDS}
PEOPLE_SYSTEMS = {"person", "extperson", "sys", "extsys"}
SYSTEMS = {"sys", "extsys"}
CONTAINERS = {"cont", "db", "mobile", "spa"}

NODE_W = 200

STYLE = """
svg{--bg:#ffffff;--fg:#18202d;--muted:#586375;--edge:#3d495b;
 --c4-person:#1f3b6e;--c4-sys:#2d58a3;--c4-cont:#3c70bf;--c4-on:#ffffff;--c4-comp:#d6e3f6;--c4-comp-fg:#14233d;
 --c4-ext:#e2e5ea;--c4-ext-fg:#283040;--dn-bg:#f7f9fc;--dn-line:#8f9aab}
@media (prefers-color-scheme:dark){svg{--bg:#151b24;--fg:#e5eaf1;--muted:#9ba6b7;--edge:#a9b3c2;
 --c4-person:#2b4f8c;--c4-sys:#3462b3;--c4-cont:#386ab0;--c4-on:#ffffff;--c4-comp:#213149;--c4-comp-fg:#dbe6f7;
 --c4-ext:#29303a;--c4-ext-fg:#d3d9e1;--dn-bg:#121820;--dn-line:#5d6878}}
text{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.bg{fill:var(--bg)} .title{font-size:16px;font-weight:600;fill:var(--fg)} .sub{font-size:11px;fill:var(--muted)}
.c4-person{fill:var(--c4-person)} .c4-sys{fill:var(--c4-sys)} .c4-cont{fill:var(--c4-cont)}
.c4-comp{fill:var(--c4-comp);stroke:var(--c4-cont);stroke-width:1} .c4-ext{fill:var(--c4-ext);stroke:var(--dn-line);stroke-width:1}
.c4-store-top{fill:none;stroke:rgba(255,255,255,.55);stroke-width:1}
.on{fill:var(--c4-on)} .on-comp{fill:var(--c4-comp-fg)} .on-ext{fill:var(--c4-ext-fg)}
.tt{font-weight:700;font-size:13px} .ty{font-size:10.5px;opacity:.85} .td{font-size:11px}
.bnd{fill:none;stroke:var(--muted);stroke-width:1.2;stroke-dasharray:7 5}
.dn{fill:var(--dn-bg);stroke:var(--dn-line);stroke-width:1.2}
.lbl-h{font-weight:700;font-size:13px;fill:var(--fg)} .lbl-s{font-size:11px;fill:var(--muted)}
.e{fill:none;stroke:var(--edge);stroke-width:1.3} .e-d{stroke-dasharray:6 4}
.mk-f{fill:var(--edge)}
.elab{font-size:11px;fill:var(--fg)} .elab-s{font-size:10px;fill:var(--muted)} .elab-bg{fill:var(--bg);opacity:.93}
.lg-t{font-size:11px;fill:var(--fg)} .lg-h{font-size:11px;font-weight:600;fill:var(--muted)}
"""

MARKERS = """<defs>
<marker id="m-fill" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="10" markerHeight="10" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path class="mk-f" d="M0,1 L10,5 L0,9 Z"/></marker>
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
BOX_PADDING = "[top=48,left=16,bottom=16,right=16]"


# ------------------------------------------------------------------ reading the model

class C4Model:
    """The C4 members of one model: kinds, containment parents, c4:Using, deployments, deployment-node nesting."""

    def __init__(self, ctx, model):
        self.ctx = ctx
        members = {x: ts for (x,) in ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inModel <{model}> }}")
                   if (ts := ctx.asserted.get(x))}
        ends = {}
        for x, s, t in sorted(ctx.rows(
                f"SELECT ?x ?s ?t WHERE {{ ?x arch:inModel <{model}> ; arch:source ?s ; arch:target ?t }}")):
            ends.setdefault(x, (s, t))
        self.kind = {}
        for x in sorted(members):
            if x in ends:
                continue
            k = next((k for k, cls, *_ in KINDS if ctx.is_a(x, cls)), None)
            if k:
                self.kind[x] = k
        self.parent, self.node_parent, self.using, self.deployed = {}, {}, [], []
        for x in sorted(set(ends) & set(members)):
            s, t = ends[x]
            if ctx.is_a(x, C4 + "ContainerContainment") or ctx.is_a(x, C4 + "ComponentContainment"):
                self.parent.setdefault(t, s)
            elif ctx.is_a(x, C4 + "Using"):
                self.using.append((x, s, t))
            elif ctx.is_a(x, SZ + "Deployment"):
                self.deployed.append((s, t))
            elif ctx.is_a(x, ARCH + "HasPart") and self.kind.get(s) == "dnode" and self.kind.get(t) in ("dnode", "inode"):
                self.node_parent.setdefault(t, s)

    def chain(self, x, parents=None):
        """x, its parent, its grandparent, ... (stops on a cycle)."""
        parents = self.parent if parents is None else parents
        seen = []
        while x is not None and x not in seen:
            seen.append(x); x = parents.get(x)
        return seen

    def value(self, x, prop, lang=None):
        flt = f' FILTER(LANGMATCHES(LANG(?v),"{lang}"))' if lang else ""
        vs = sorted(v for (v,) in self.ctx.rows(f"SELECT ?v WHERE {{ <{x}> <{prop}> ?v{flt} }}"))
        return vs[0] if vs else ""


# ------------------------------------------------------------------ selecting a view

def _lift(m, x, drawn):
    return next((y for y in m.chain(x) if y in drawn), None)


def _edges(m, drawn, leaf_of=lambda y: [y]):
    """Lines between drawn leaves for every c4:Using, lifted to the nearest drawn ancestor (Structurizr implied
    relationships: only when no direct c4:Using exists between the two drawn elements in that direction)."""
    direct, implied = [], {}
    for u, s, t in m.using:
        ls, lt = _lift(m, s, drawn), _lift(m, t, drawn)
        if not ls or not lt or ls == lt:
            continue
        if (ls, lt) == (s, t):
            direct.append((u, ls, lt))
        else:
            implied.setdefault((ls, lt), []).append(u)
    pairs = {(s, t) for _, s, t in direct}
    rows = [([u], s, t, False) for u, s, t in direct] + \
           [(sorted(us), s, t, True) for (s, t), us in sorted(implied.items()) if (s, t) not in pairs]
    out = []
    for us, s, t, imp in rows:
        labels = list(dict.fromkeys(m.ctx.label(u) or "" for u in us))
        techs = list(dict.fromkeys(v for u in us if (v := m.value(u, C4 + "technology"))))
        for a in leaf_of(s):
            for b in leaf_of(t):
                out.append({"iris": us, "source": s, "target": t, "a": a, "b": b, "implied": imp,
                            "label": "；".join(x for x in labels if x), "tech": "，".join(techs)})
    return sorted(out, key=lambda e: (e["iris"], e["a"], e["b"]))


def _env(m, x):
    for y in m.chain(x, m.node_parent):
        v = m.value(y, SZ + "environment")
        if v:
            return v
    return ""


def select(ctx, viewpoint, scope, model=None, view=None):
    """(title, subtitle, boxes, edges, warnings, model). boxes: {id: {iri, kind, label, tech, definition, parent, compound,
    instances}}; id is the element IRI, or 'container IRI@node IRI' for a deployed container. edges: see _edges."""
    warnings = []
    if view:
        model = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{view}> arch:inModel ?m }}"))[0]
    elif viewpoint == "C4Deployment" and not model:  # scope is a plain name (checked by the CLI)
        ms = sorted({m for (m,) in ctx.rows(f'SELECT ?m WHERE {{ ?n <{SZ}environment> "{scope}" ; arch:inModel ?m }}')})
        if len(ms) != 1:
            raise ValueError(f"environment {scope!r} " + (f"is in several models {ms}: pass --model" if ms else
                             "has no deployment node (structurizr:environment) in any model"))
        model = ms[0]
    elif viewpoint != "C4Deployment":
        ms = sorted(x for (x,) in ctx.rows(f"SELECT ?m WHERE {{ <{scope}> arch:inModel ?m }}"))
        if not ms:
            raise ValueError(f"{scope}: no arch:inModel, not a member of any model")
        model = ms[0]
    m = C4Model(ctx, model)
    kind, children, boundary = m.kind, {}, None
    for c, p in m.parent.items():
        children.setdefault(p, []).append(c)
    leaf_of = lambda y: [y]
    if view:
        if local(viewpoint) == "C4Deployment":
            raise ValueError(f"{view}: declared deployment views are not supported yet; "
                             "use --viewpoint C4Deployment --of <environment>")
        inview = {x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ ?x arch:inView <{view}> }}")}
        drawn = {x for x in inview if kind.get(x) and kind[x] not in ("dnode", "inode")}
        for x in sorted(inview - drawn):
            if kind.get(x) in ("dnode", "inode"):
                warnings.append(f"{x}: deployment and infrastructure nodes are drawn only in C4Deployment views")
            elif x not in {u for u, _, _ in m.using}:
                warnings.append(f"{x}: in view but not a C4 element, not drawn")
        parent = {x: next((y for y in m.chain(x)[1:] if y in drawn), None) for x in drawn}
        title = ctx.label(view) or local(view)
        vp_name = VIEWPOINTS.get(local(viewpoint), local(viewpoint))
    elif viewpoint == "C4Deployment":
        nodes = {x for x, k in kind.items() if k in ("dnode", "inode") and _env(m, x) == scope}
        nodes |= {y for x in list(nodes) for y in m.chain(x, m.node_parent)}
        if not nodes:
            envs = sorted({_env(m, x) for x, k in kind.items() if k == "dnode"} - {""})
            raise ValueError(f"no deployment node in environment {scope!r} of {model} (environments: {envs})")
        drawn, parent, inst = set(nodes), {x: m.node_parent.get(x) for x in nodes}, {}
        for c, n in sorted(m.deployed):
            if n in nodes and kind.get(c) in CONTAINERS:
                i = f"{c}@{n}"
                drawn.add(i); parent[i] = n; inst.setdefault(c, []).append(i)
        leaf_of = lambda y: inst.get(y, [])
        drawn_elements = set(inst)  # lifting works on elements; leaf_of maps an element to its instances
        title = f"部署图：{scope}"
        vp_name = VIEWPOINTS[viewpoint]
    else:
        k = kind.get(scope)
        want = CONTAINERS if viewpoint == "ComponentDiagram" else SYSTEMS
        if k not in want:
            raise ValueError(f"{scope} is a {KIND[k][1] if k else 'non-C4 element'}; {viewpoint} needs a "
                             + ("container" if viewpoint == "ComponentDiagram" else "software system"))
        top = lambda x: m.chain(x)[-1]
        outer = set()
        if viewpoint == "SystemContext":
            core, boundary = {scope}, None
            for _, s, t in m.using:
                for a, b in ((s, t), (t, s)):
                    if top(a) == scope and top(b) != scope and kind.get(top(b)) in PEOPLE_SYSTEMS:
                        outer.add(top(b))
        elif viewpoint == "ContainerDiagram":
            core, boundary = {c for c in children.get(scope, []) if kind.get(c) in CONTAINERS}, scope
            for _, s, t in m.using:
                for a, b in ((s, t), (t, s)):
                    if _lift(m, a, core) and top(b) != scope and kind.get(top(b)) in PEOPLE_SYSTEMS:
                        outer.add(top(b))
        else:
            core, boundary = {c for c in children.get(scope, []) if kind.get(c) == "comp"}, scope
            system = m.parent.get(scope)
            for _, s, t in m.using:
                for a, b in ((s, t), (t, s)):
                    if a not in core:
                        continue
                    cont = next((y for y in m.chain(b) if kind.get(y) in CONTAINERS), None)
                    if system and top(b) == system and cont and cont != scope:
                        outer.add(cont)
                    elif top(b) != (system or scope) and kind.get(top(b)) in PEOPLE_SYSTEMS:
                        outer.add(top(b))
        drawn = core | outer | ({boundary} if boundary else set())
        parent = {x: (boundary if x in core and boundary else None) for x in drawn}
        title = f"{VIEWPOINTS[viewpoint]}：{ctx.label(scope) or local(scope)}"
        vp_name = VIEWPOINTS[viewpoint]
    compound = {p for p in parent.values() if p} | ({boundary} if boundary else set())
    if viewpoint != "C4Deployment" or view:
        drawn_elements = drawn - compound
    boxes = {}
    for i in sorted(drawn):
        x = i.split("@", 1)[0]
        boxes[i] = {"iri": x, "kind": kind[x], "label": ctx.label(x) or local(x), "tech": m.value(x, C4 + "technology"),
                    "definition": m.value(x, NS["skos"] + "definition", "zh"), "parent": parent.get(i),
                    "compound": i in compound or kind[x] == "dnode",
                    "instances": m.value(x, SZ + "instances") if kind[x] == "dnode" else ""}
    edges = _edges(m, drawn_elements, leaf_of)
    if view:
        drawn_using = {u for e in edges for u in e["iris"]}
        for u, _, _ in m.using:
            if u in inview and u not in drawn_using:
                warnings.append(f"{u}: in view but an end is not drawn, not drawn")
    n_el = sum(1 for b in boxes.values() if not b["compound"])
    sub = (f"{local(model.rstrip('/'))} · {vp_name} · 元素 {n_el} · 关系 {len(edges)} · "
           f"由 tools/aisep.py diagram 从模型生成")
    return title, sub, boxes, edges, warnings, model



# ------------------------------------------------------------------ layout

def _lines(b):
    """Text lines of a leaf box: (text, css class, font px)."""
    typ = "[" + KIND[b["kind"]][1] + ("：" + b["tech"] if b["tech"] else "") + "]"
    out = [(s, "tt", 13) for s in wrap(b["label"], NODE_W - 18, 13)]
    out += [(s, "ty", 10.5) for s in wrap(typ, NODE_W - 14, 10.5)]
    if b["definition"]:
        out += [(s, "td", 11) for s in wrap(b["definition"], NODE_W - 18, 11)]
    return out


def _edge_lines(e):
    out = [(s, "elab", 11) for s in wrap(e["label"], 150, 11)] if e["label"] else []
    if e["tech"]:
        out += [(s, "elab-s", 10) for s in wrap(f"[{e['tech']}]", 150, 10)]
    return out


def _box_title(b):
    typ = KIND[b["kind"]][1] + ("：" + b["tech"] if b["tech"] else "")
    return b["label"], f"[{typ}]" + (f" ×{b['instances']}" if b["instances"] else "")


def layout(boxes, edges):
    ids = {i: f"n{k}" for k, i in enumerate(sorted(boxes))}
    kids = {}
    for i in sorted(boxes):
        kids.setdefault(boxes[i]["parent"], []).append(i)

    def node(i):
        b = boxes[i]
        if b["compound"]:
            h, s = _box_title(b)
            w = max(NODE_W, tw(h, 13) + 32, tw(s, 11) + 32)
            return {"id": ids[i], "layoutOptions": {"elk.padding": BOX_PADDING, "elk.nodeSize.minimum": f"({round(w, 1)},90)",
                                                    "elk.nodeSize.constraints": "MINIMUM_SIZE"},
                    "children": [node(c) for c in kids.get(i, [])]}
        lh = sum(px * 1.38 for _, _, px in _lines(b))
        return {"id": ids[i], "width": NODE_W, "height": round(max(86, lh + 28 + (8 if b["kind"] == "db" else 0)), 1)}

    elk_edges = []
    for k, e in enumerate(edges):
        ls = _edge_lines(e)
        # ELK places (and reserves room for) a label only when it has text
        lab = [{"id": f"l{k}", "text": " ".join(s for s, _, _ in ls), "width": round(max(tw(s, px) for s, _, px in ls) + 8, 1), "height": len(ls) * 15 + 4}] if ls else []
        elk_edges.append({"id": f"e{k}", "sources": [ids[e["a"]]], "targets": [ids[e["b"]]], "labels": lab})
    graph = {"id": "root", "layoutOptions": ELK_OPTIONS, "children": [node(i) for i in kids.get(None, [])],
             "edges": elk_edges}
    out = elk_layout(graph)
    pos = {}

    def walk(n):
        for c in n.get("children", []):
            pos[c["id"]] = (c["x"], c["y"], c["width"], c["height"]); walk(c)
    walk(out)
    routes, labels = {}, {}

    def walk_edges(n):
        for e in n.get("edges", []):
            s = e["sections"][0]
            routes[e["id"]] = [(s["startPoint"]["x"], s["startPoint"]["y"])] + \
                [(p["x"], p["y"]) for p in s.get("bendPoints", [])] + [(s["endPoint"]["x"], s["endPoint"]["y"])]
            for lab in e.get("labels", []):
                labels[e["id"]] = (lab["x"], lab["y"], lab["width"], lab["height"])
        for c in n.get("children", []):
            walk_edges(c)
    walk_edges(out)
    return ({i: pos[ids[i]] for i in boxes}, [routes[f"e{k}"] for k in range(len(edges))],
            [labels.get(f"e{k}") for k in range(len(edges))], out.get("width", 0), out.get("height", 0))


# ------------------------------------------------------------------ rendering

def _leaf(b, x, y, w, h):
    fill, txt = KIND[b["kind"]][2], KIND[b["kind"]][3]
    out, top = [], y
    if b["kind"] == "db":
        ry = 8
        out.append(f'<path d="M{f(x)},{f(y + ry)} a{f(w / 2)},{ry} 0 0 1 {f(w)},0 v{f(h - 2 * ry)} a{f(w / 2)},{ry} 0 0 1 '
                   f'{f(-w)},0 z" class="{fill}"/>')
        out.append(f'<path d="M{f(x)},{f(y + ry)} a{f(w / 2)},{ry} 0 0 0 {f(w)},0" class="c4-store-top"/>')
        top = y + ry
    else:
        rx = 16 if b["kind"] in ("person", "extperson") else 6
        out.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{rx}" class="{fill}"/>')
    ls = _lines(b)
    lh = [px * 1.38 for _, _, px in ls]
    cy = top + (y + h - top) / 2 - sum(lh) / 2
    for k, (s, cls, _) in enumerate(ls):
        cy += lh[k] + (4 if cls == "td" and k and ls[k - 1][1] == "ty" else 0)
        out.append(f'<text x="{f(x + w / 2)}" y="{f(cy - lh[k] * 0.28)}" text-anchor="middle" class="{cls} {txt}">'
                   f'{escape(s)}</text>')
    return out


def render(title, sub, boxes, edges):
    check_xml_text(title, sub, boxes, edges)
    pos, routes, labs, gw, gh = layout(boxes, edges)
    top = MARGIN + 52
    kinds = sorted({b["kind"] for b in boxes.values() if not b["compound"]}, key=[k for k, *_ in KINDS].index)
    bnd = any(b["compound"] and b["kind"] != "dnode" for b in boxes.values())
    dn = any(b["kind"] == "dnode" for b in boxes.values())
    etypes = (["direct"] if any(not e["implied"] for e in edges) else []) + \
             (["implied"] if any(e["implied"] for e in edges) else [])
    width = max(MARGIN * 2 + gw, 560)
    per_row = max(1, int((width - 2 * MARGIN - 60) // 150))
    items = len(kinds) + bnd + dn + len(etypes)
    y_leg = top + gh + 28
    height = y_leg + 22 + -(-items // per_row) * 26 + MARGIN
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" '
           f'height="{f(height)}" role="img" aria-label="{escape(title)}">',
           f"<style>{STYLE}</style>", MARKERS,
           f'<rect class="bg" x="0" y="0" width="{f(width)}" height="{f(height)}"/>',
           f'<text x="{MARGIN}" y="{MARGIN + 14}" class="title">{escape(title)}</text>',
           f'<text x="{MARGIN}" y="{MARGIN + 32}" class="sub">{escape(sub)}</text>']

    def attrs(i):
        b = boxes[i]
        x, y, w, h = pos[i]
        par = boxes[b["parent"]]["iri"] if b["parent"] else ""
        return (f'data-iri="{escape(b["iri"])}" data-type="{escape(local(KIND[b["kind"]][0]))}" '
                f'data-parent="{escape(par)}" data-box="{f(MARGIN + x)} {f(top + y)} {f(w)} {f(h)}"')

    def depth(i):
        n = 0
        while boxes[i]["parent"]:
            i, n = boxes[i]["parent"], n + 1
        return n
    for i in sorted((i for i in boxes if boxes[i]["compound"]), key=lambda i: (depth(i), i)):
        b, (x, y, w, h) = boxes[i], pos[i]
        x, y = MARGIN + x, top + y
        kind = "deployment-node" if b["kind"] == "dnode" else "boundary"
        h1, h2 = _box_title(b)
        out.append(f'<g data-kind="{kind}" {attrs(i)}><title>{escape(h1 + " " + h2)}</title>')
        out.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{6 if kind != "boundary" else 10}" '
                   f'class="{"dn" if kind != "boundary" else "bnd"}"/>')
        out.append(f'<text x="{f(x + 14)}" y="{f(y + 22)}" class="lbl-h">{escape(h1)}</text>')
        out.append(f'<text x="{f(x + 14)}" y="{f(y + 38)}" class="lbl-s">{escape(h2)}</text></g>')
    for k, e in enumerate(edges):
        d = "M" + " L".join(f"{f(MARGIN + x)},{f(top + y)}" for x, y in routes[k])
        sl, tl = boxes[e["a"]]["label"], boxes[e["b"]]["label"]
        tip = ("隐含关系（由下层关系提升）" if e["implied"] else "使用") + f"：{sl} → {tl}" + \
              (f"（{e['label']}）" if e["label"] else "")
        out.append(f'<path data-kind="relationship" data-iri="{escape(" ".join(e["iris"]))}" data-type="c4:Using" '
                   f'data-implied="{"true" if e["implied"] else "false"}" data-source="{escape(e["source"])}" '
                   f'data-target="{escape(e["target"])}" d="{d}" class="e{" e-d" if e["implied"] else ""}" '
                   f'marker-end="url(#m-fill)"><title>{escape(tip)}</title></path>')
        if labs[k]:
            lx, ly, lw, lh = MARGIN + labs[k][0], top + labs[k][1], labs[k][2], labs[k][3]
            out.append(f'<rect x="{f(lx)}" y="{f(ly)}" width="{f(lw)}" height="{f(lh)}" rx="3" class="elab-bg"/>')
            for j, (s, cls, _) in enumerate(_edge_lines(e)):
                out.append(f'<text x="{f(lx + lw / 2)}" y="{f(ly + 14 + 15 * j)}" text-anchor="middle" class="{cls}">'
                           f'{escape(s)}</text>')
    for i in sorted(i for i in boxes if not boxes[i]["compound"]):
        b, (x, y, w, h) = boxes[i], pos[i]
        tip = f'{KIND[b["kind"]][1]}：{b["label"]}' + (f'\n{b["definition"]}' if b["definition"] else "")
        out.append(f'<g data-kind="element" {attrs(i)}><title>{escape(tip)}</title>')
        out += _leaf(b, MARGIN + x, top + y, w, h)
        out.append("</g>")
    out.append(f'<text class="lg-h" x="{MARGIN}" y="{f(y_leg + 12)}">图例</text>')
    legend = [("k", k) for k in kinds] + ([("bnd", None)] if bnd else []) + ([("dn", None)] if dn else []) + \
             [("e", t) for t in etypes]
    for n, (what, k) in enumerate(legend):
        lx, yy = MARGIN + 60 + (n % per_row) * 150, y_leg + 22 + (n // per_row) * 26
        if what == "k":
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="{8 if k in ("person", "extperson") else 3}" '
                       f'class="{KIND[k][2]}"/>')
            name = KIND[k][1]
        elif what in ("bnd", "dn"):
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="4" class="{what}"/>')
            name = "边界" if what == "bnd" else "部署节点"
        else:
            out.append(f'<path d="M{f(lx + 2)},{f(yy + 9)} L{f(lx + 30)},{f(yy + 9)}" '
                       f'class="e{" e-d" if k == "implied" else ""}" marker-end="url(#m-fill)"/>')
            name = "使用" if k == "direct" else "隐含关系"
        out.append(f'<text class="lg-t" x="{f(lx + 36)}" y="{f(yy + 13)}">{name}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
