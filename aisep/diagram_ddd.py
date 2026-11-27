"""DDD views → SVG, generated from the model (no coordinates are stored anywhere). Part of `aisep.py diagram`.

Two views (plain names, no viewpoint IRI is minted):
  * ContextMap (scope: a model): its ddd:BoundedContext and ddd:Subdomain members, and the context-map relationships
    between them (ddd:UpstreamDownstream, ddd:CustomerSupplier, ddd:Partnership, ddd:SharedKernel) plus
    ddd:SubdomainImplementation. Where the notation comes from:
      - the Context Mapper context-map generator (github.com/ContextMapper/context-map-generator): lines carry no
        arrow; the upstream end is labelled "U" or "U | OHS, PL", the downstream end "D" or "D | ACL"; Partnership,
        Shared Kernel and Customer-Supplier name their type in the middle; implementation is a grey dashed line (its
        team map's "realizes"). Role abbreviations are the roles' skos:notation.
      - CML syntax ([U,S]->[D,C]): the Customer-Supplier ends "U,S" / "D,C".
      - AISEP's own: the "暴露：…" middle line for exposed aggregates, and subdomains as a second band ("问题空间"),
        so a model without context relationships still shows how its contexts relate to its subdomains.
  * AggregateDiagram (scope: a bounded context B): B as the outer box, every aggregate B owns (ddd:Ownership) as an
    inner box holding the entities and value objects it contains (ddd:Containment); the root (ddd:RootContainment)
    is marked «聚合根». Containment and ownership are drawn as nesting, never as lines (as in Context Mapper's
    PlantUML bounded-context class diagram).

Only DDD relationships are drawn; cross-notation links (aisep:Implementation, am4:Realization, arch:Refines …) are not.
What the model says but cannot be drawn, or is drawn degraded, is a warning naming the IRI; nothing is dropped silently.
Layout is ELK layered (elkjs pinned in tools/elk), fixed options and seed: same model, same bytes.
"""
from html import escape

import pyoxigraph as ox

from aisep.core import NS
from aisep.diagram import MARGIN, elk_layout, f, local, tw, wrap

DDD = "https://aisep.example/ont/ddd#"
SKOS = NS["skos"]
VIEWPOINTS = {"ContextMap": "上下文映射图", "AggregateDiagram": "聚合图"}

# element kind -> (class, Chinese name)
ELEMENTS = {"bc": (DDD + "BoundedContext", "限界上下文"), "sub": (DDD + "Subdomain", "子域"),
            "agg": (DDD + "Aggregate", "聚合"), "ent": (DDD + "Entity", "实体"), "vo": (DDD + "ValueObject", "值对象")}
# relationship kinds, most specific first: (local name, Chinese name, source kind, target kind)
RELS = [("CustomerSupplier", "客户-供应方", "bc", "bc"), ("UpstreamDownstream", "上下游", "bc", "bc"),
        ("Partnership", "合作关系", "bc", "bc"), ("SharedKernel", "共享内核", "bc", "bc"),
        ("SubdomainImplementation", "实现", "bc", "sub"), ("Ownership", "拥有", "bc", "agg"),
        ("RootContainment", "聚合根", "agg", "ent"), ("Containment", "包含", "agg", None)]
MAP_RELS = {"CustomerSupplier", "UpstreamDownstream", "Partnership", "SharedKernel", "SubdomainImplementation"}
SUBTYPE = {"Core": "sub-core", "Supporting": "sub-sup", "Generic": "sub-gen"}
# DDD classes some DDD view draws; members of any other ddd: class are reported by ContextMap
DRAWN = {c for c, _ in ELEMENTS.values()} | {DDD + r[0] for r in RELS}

NODE_W, LEAF_W, BAND_PAD, LABEL_W = 188, 156, 18, 92

STYLE = """
svg{--bg:#ffffff;--fg:#18202d;--muted:#586375;--edge:#3d495b;--band:#f3f5f8;--line:#596071;
 --bc:#dfe9f7;--bc-line:#3c70bf;--sub-core:#f6c9a8;--sub-sup:#fbe3cf;--sub-gen:#f4f0ea;--sub-none:#e2e5ea;
 --agg:#fff7cc;--agg-line:#b59a1f;--root:#fffab8;--root-bar:#d4b106;--leaf:#ffffff;--vo:#eef6ee;--impl:#8f9aab}
@media (prefers-color-scheme:dark){svg{--bg:#151b24;--fg:#e5eaf1;--muted:#9ba6b7;--edge:#a9b3c2;--band:#1b222d;
 --line:#9aa3b2;--bc:#1f3049;--bc-line:#6d9be0;--sub-core:#5a3a24;--sub-sup:#45362a;--sub-gen:#35322e;--sub-none:#29303a;
 --agg:#3a3520;--agg-line:#c9ad3a;--root:#4a4422;--root-bar:#e0c23a;--leaf:#1d242f;--vo:#1f2b22;--impl:#6f7a8b}}
text{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
.bg{fill:var(--bg)} .band{fill:var(--band)} .band-t{font-size:12px;font-weight:600;fill:var(--muted)}
.title{font-size:16px;font-weight:600;fill:var(--fg)} .sub{font-size:11px;fill:var(--muted)}
.bc{fill:var(--bc);stroke:var(--bc-line);stroke-width:1.4}
.sub-core{fill:var(--sub-core)} .sub-sup{fill:var(--sub-sup)} .sub-gen{fill:var(--sub-gen)} .sub-none{fill:var(--sub-none)}
.sd{stroke:var(--line);stroke-width:1.1}
.bnd{fill:none;stroke:var(--bc-line);stroke-width:1.4;stroke-dasharray:7 5}
.agg{fill:var(--agg);stroke:var(--agg-line);stroke-width:1.3} .leaf{fill:var(--leaf);stroke:var(--line);stroke-width:1}
.root{fill:var(--root)} .root-bar{fill:var(--root-bar)} .vo{fill:var(--vo);stroke-dasharray:4 3}
.tt{font-weight:700;font-size:13px;fill:var(--fg)} .ty{font-size:10.5px;fill:var(--muted)}
.badge{font-size:10px;font-weight:600;fill:var(--fg)}
.lbl-h{font-weight:700;font-size:13px;fill:var(--fg)} .lbl-s{font-size:11px;fill:var(--muted)}
.e{fill:none;stroke:var(--edge);stroke-width:2.2} .e-impl{fill:none;stroke:var(--impl);stroke-width:1.3;stroke-dasharray:6 4}
.end{fill:var(--bg);stroke:var(--edge);stroke-width:1} .end-t{font-size:11px;font-weight:600;fill:var(--fg)}
.elab{font-size:11px;fill:var(--fg)} .elab-bg{fill:var(--bg);opacity:.93}
.lg-t{font-size:11px;fill:var(--fg)} .lg-h{font-size:11px;font-weight:600;fill:var(--muted)}
"""

ELK_BASE = {
    "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.randomSeed": "1", "elk.edgeRouting": "ORTHOGONAL",
    "elk.json.shapeCoords": "ROOT", "elk.json.edgeCoords": "ROOT",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    "elk.spacing.nodeNode": "40", "elk.layered.spacing.nodeNodeBetweenLayers": "70",
    "elk.spacing.edgeNode": "16", "elk.spacing.edgeEdge": "10", "elk.spacing.edgeLabel": "4",
}
ELK_MAP = {**ELK_BASE, "elk.partitioning.activate": "true",
           "elk.padding": f"[top={BAND_PAD},left={LABEL_W + BAND_PAD},bottom={BAND_PAD},right={BAND_PAD}]"}
ELK_AGG = {**ELK_BASE, "elk.hierarchyHandling": "INCLUDE_CHILDREN", "elk.padding": "[top=0,left=0,bottom=0,right=0]"}
BOX_PADDING = "[top=50,left=16,bottom=16,right=16]"


# ------------------------------------------------------------------ reading the model

class DDDModel:
    """The DDD members of one model: element kinds, relationship kinds (most specific) and their ends."""

    def __init__(self, ctx, model):
        self.ctx, self.model = ctx, model
        self.members = {x: ts for (x,) in ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inModel <{model}> }}")
                        if (ts := ctx.asserted.get(x))}
        ends = {}
        for x, s, t in sorted(ctx.rows(
                f"SELECT ?x ?s ?t WHERE {{ ?x arch:inModel <{model}> ; arch:source ?s ; arch:target ?t }}")):
            ends.setdefault(x, (s, t))
        self.kind, self.rels = {}, []
        for x in sorted(self.members):
            if x in ends:
                r = next((r for r in RELS if ctx.is_a(x, DDD + r[0])), None)
                if r:
                    self.rels.append((x, r[0], *ends[x]))
            else:
                k = next((k for k, (cls, _) in ELEMENTS.items() if ctx.is_a(x, cls)), None)
                if k:
                    self.kind[x] = k

    def terms(self, x, prop):
        """The objects of (x, prop) as RDF terms (IRI or literal), sorted on their value. A store pattern, not SPARQL
        text, so a value is never spliced into a query."""
        s = x if isinstance(x, ox.NamedNode) else ox.NamedNode(x)
        return sorted({q.object for q in self.ctx.store.quads_for_pattern(s, ox.NamedNode(prop), None)},
                      key=lambda t: (t.value, str(t)))

    def values(self, x, prop):
        return sorted({t.value for t in self.terms(x, prop)})

    def term_name(self, t):
        """Display name of a term: an IRI's label (or local name), a literal's own text."""
        return (self.ctx.label(t.value) or local(t.value)) if isinstance(t, ox.NamedNode) else t.value

    def name(self, x):
        return self.ctx.label(x) or local(x)

    def unsupported(self):
        """Members whose most specific type is a ddd: class no DDD view draws (events, commands, policies …)."""
        out = []
        for x in sorted(self.members):
            ts = [t for t in self.ctx.specific(x) if t.startswith(DDD)]
            if ts and not any(t in DRAWN or any(a in DRAWN for a in self.ctx.ancestors(t)) for t in ts):
                out.append((x, ts[0]))
        return out


def _model_of(ctx, x):
    ms = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{x}> arch:inModel ?m }}"))
    if not ms:
        raise ValueError(f"{x}: no arch:inModel, not a member of any model")
    return ms[0]


def views(ctx, model):
    """The DDD views this model can render: [(viewpoint, scope IRI or None, title)]."""
    m = DDDModel(ctx, model)
    bcs = sorted(x for x, k in m.kind.items() if k == "bc")
    out = [("ContextMap", None, VIEWPOINTS["ContextMap"])] if bcs else []
    owners = {s for _, r, s, t in m.rels if r == "Ownership" and m.kind.get(t) == "agg"}
    out += [("AggregateDiagram", b, f"{VIEWPOINTS['AggregateDiagram']}：{m.name(b)}") for b in bcs if b in owners]
    return out


# ------------------------------------------------------------------ selecting a view

def _roles(m, x, prop, scheme, warnings):
    """(skos:notation, skos:prefLabel) of every role value of x that is an IRI and a concept of scheme; other values
    (wrong scheme, no notation, a literal) are warned, not drawn. Term types decide what an IRI is; nothing is spliced
    into SPARQL."""
    out = []
    for v in m.terms(x, prop):
        ok = isinstance(v, ox.NamedNode) and \
            ox.NamedNode(DDD + scheme) in {t for t in m.terms(v, SKOS + "inScheme") if isinstance(t, ox.NamedNode)}
        notes = [n.value for n in m.terms(v, SKOS + "notation") if isinstance(n, ox.Literal)] if ok else []
        if notes:
            out.append((notes[0], m.term_name(v)))
        else:
            shown = v.value if isinstance(v, ox.NamedNode) else f'"{v.value}"'
            warnings.append(f"{x}: role {shown} is not in ddd:{scheme}, not drawn")
    return sorted(out)


def _context_map(ctx, m, warnings):
    boxes, edges = {}, []
    for x, k in sorted(m.kind.items()):
        if k == "bc":
            ct = m.terms(x, DDD + "contextType")
            boxes[x] = {"iri": x, "kind": "bc", "label": m.name(x), "parent": None, "compound": False,
                        "stereo": "«限界上下文" + (f" · {m.term_name(ct[0])}" if ct else "") + "»"}
        elif k == "sub":
            st = m.terms(x, DDD + "subdomainType")
            boxes[x] = {"iri": x, "kind": "sub", "label": m.name(x), "parent": None, "compound": False,
                        "stereo": "«子域" + (f" · {m.term_name(st[0])}" if st else "") + "»",
                        "fill": SUBTYPE.get(local(st[0].value), "sub-none")
                        if st and isinstance(st[0], ox.NamedNode) else "sub-none"}
    for x, r, s, t in m.rels:
        if r not in MAP_RELS:
            continue
        _, zh, sk, tk = next(d for d in RELS if d[0] == r)
        if m.kind.get(s) != sk or m.kind.get(t) != tk:
            warnings.append(f"{x}: an end is not in this view, not drawn")
            continue
        e = {"iri": x, "type": r, "source": s, "target": t, "tail": None, "head": None, "center": []}
        if r in ("UpstreamDownstream", "CustomerSupplier"):
            up = _roles(m, x, DDD + "upstreamRole", "UpstreamRoleScheme", warnings)
            down = _roles(m, x, DDD + "downstreamRole", "DownstreamRoleScheme", warnings)
            u, d = ("U,S", "D,C") if r == "CustomerSupplier" else ("U", "D")
            e["tail"] = u + (" | " + ", ".join(n for n, _ in up) if up else "")
            e["head"] = d + (" | " + ", ".join(n for n, _ in down) if down else "")
            e["roles"] = up + down  # the legend explains each abbreviation from here, never by re-splitting end text
            if r == "CustomerSupplier":
                e["center"].append(zh)
            exposed = []
            for a in m.terms(x, DDD + "exposedAggregate"):
                if isinstance(a, ox.NamedNode) and m.kind.get(a.value) == "agg":
                    exposed.append(m.name(a.value))
                else:
                    warnings.append(f"{x}: exposed aggregate {a.value} is not an Aggregate, not drawn")
            if exposed:
                e["center"].append("暴露：" + "、".join(sorted(exposed)))
        elif r in ("Partnership", "SharedKernel"):
            if m.values(x, DDD + "upstreamRole") or m.values(x, DDD + "downstreamRole"):
                warnings.append(f"{x}: symmetric relationship has roles, roles not drawn")
            e["center"].append(zh)
        else:
            e["center"].append(zh)
        edges.append(e)
    for x, t in m.unsupported():
        warnings.append(f"{x}: ddd:{local(t)} is not drawn by any DDD view yet")
    # tactical members no AggregateDiagram reaches: an aggregate no bounded context owns, an entity or value object in
    # no aggregate that a bounded context owns
    owned = {t for _, r, s, t in m.rels if r == "Ownership" and m.kind.get(s) == "bc" and m.kind.get(t) == "agg"}
    reached = {t for _, r, s, t in m.rels if r in ("Containment", "RootContainment") and s in owned}
    for x, k in sorted(m.kind.items()):
        if k == "agg" and x not in owned:
            warnings.append(f"{x}: ddd:Aggregate owned by no bounded context (ddd:Ownership), not drawn by any DDD view")
        elif k in ("ent", "vo") and x not in reached:
            warnings.append(f"{x}: ddd:{local(ELEMENTS[k][0])} is in no aggregate a bounded context owns "
                            f"(ddd:Containment), not drawn by any DDD view")
    return boxes, edges


def _aggregates(ctx, m, scope, warnings):
    owned = {}
    for x, r, s, t in m.rels:
        if r == "Ownership" and m.kind.get(t) == "agg":
            owned.setdefault(t, []).append((s, x))
        elif r == "Ownership" and s == scope:
            warnings.append(f"{x}: an end is not in this view, not drawn")
    aggs = sorted(a for a, os_ in owned.items() if any(s == scope for s, _ in os_))
    if not aggs:
        raise ValueError(f"{scope}: this bounded context owns no aggregate (ddd:Ownership), nothing to draw")
    boxes = {scope: {"iri": scope, "kind": "bc", "label": m.name(scope), "parent": None, "compound": True,
                     "stereo": "«限界上下文»"}}
    for a in aggs:
        via = next(x for s, x in owned[a] if s == scope)
        for s, _ in owned[a]:
            if s != scope:
                warnings.append(f"{a}: also owned by {s}")
        boxes[a] = {"iri": a, "kind": "agg", "label": m.name(a), "parent": scope, "compound": True,
                    "stereo": "«聚合»", "via": via}
    roots = {}
    # RootContainment first (stable on IRI order), so a member that one aggregate both contains and has as root keeps
    # its root mark; the same aggregate containing the same member twice is not a conflict and is not warned.
    for x, r, s, t in sorted(m.rels, key=lambda q: q[1] != "RootContainment"):
        if r not in ("Containment", "RootContainment") or s not in aggs:
            continue
        if m.kind.get(t) not in ("ent", "vo"):
            warnings.append(f"{x}: an end is not in this view, not drawn")
            continue
        if t in boxes and boxes[t]["parent"] == s:
            continue
        if t in boxes:
            warnings.append(f"{x}: {t} is already drawn in {boxes[t]['parent']}, not drawn again")
            continue
        boxes[t] = {"iri": t, "kind": m.kind[t], "label": m.name(t), "parent": s, "compound": False, "via": x,
                    "root": False}
        if r == "RootContainment" and m.kind[t] == "ent":
            roots.setdefault(s, t)
    for a in aggs:
        if a in roots and boxes[roots[a]]["parent"] == a:
            boxes[roots[a]]["root"] = True
        else:
            warnings.append(f"{a}: no root entity, drawn without root mark")
    for b in boxes.values():
        if b["kind"] in ("ent", "vo"):
            b["stereo"] = ("«聚合根» " if b["root"] else "") + f"«{ELEMENTS[b['kind']][1]}»"
    return boxes, []


def select(ctx, viewpoint, scope, model=None):
    """(title, subtitle, boxes, edges, warnings, model). ContextMap: model is the scope; AggregateDiagram: scope is a
    bounded context IRI. boxes: {iri: {iri, kind, label, stereo, parent, compound, [fill], [via], [root]}};
    edges: [{iri, type, source, target, tail, head, center}]. Raises ValueError when there is nothing to draw."""
    warnings = []
    if viewpoint == "ContextMap":
        m = DDDModel(ctx, model)
        if not any(k == "bc" for k in m.kind.values()):
            raise ValueError(f"no ddd:BoundedContext in {model}")
        boxes, edges = _context_map(ctx, m, warnings)
        title = f"{VIEWPOINTS[viewpoint]}：{ctx.label(model) or local(model.rstrip('/'))}"
    elif viewpoint == "AggregateDiagram":
        model = _model_of(ctx, scope)
        m = DDDModel(ctx, model)
        if m.kind.get(scope) != "bc":
            raise ValueError(f"{scope} is not a ddd:BoundedContext; AggregateDiagram needs a bounded context")
        boxes, edges = _aggregates(ctx, m, scope, warnings)
        title = f"{VIEWPOINTS[viewpoint]}：{m.name(scope)}"
    else:
        raise ValueError(f"unknown DDD view {viewpoint!r} (one of {sorted(VIEWPOINTS)})")
    n_el = sum(1 for b in boxes.values() if b["kind"] != "bc" or viewpoint == "ContextMap")
    n_rel = len(edges) + sum(1 for b in boxes.values() if b.get("via"))
    sub = (f"{local(model.rstrip('/'))} · {VIEWPOINTS[viewpoint]} · 元素 {n_el} · 关系 {n_rel} · "
           f"由 tools/aisep.py diagram 从模型生成")
    return title, sub, boxes, edges, warnings, model


# ------------------------------------------------------------------ layout

def _lines(b, width):
    """Text lines of a leaf box: (text, css class, font px)."""
    return [(s, "ty", 10.5) for s in wrap(b["stereo"], width - 16, 10.5)] + \
           [(s, "tt", 13) for s in wrap(b["label"], width - 18, 13)]


def _end_size(text):
    return round(tw(text, 11) + 12, 1), 18


def _center_lines(e):
    return [s for c in e["center"] for s in wrap(c, 150, 11)]


def layout(boxes, edges):
    ids = {i: f"n{k}" for k, i in enumerate(sorted(boxes))}
    kids = {}
    for i in sorted(boxes, key=lambda i: (not boxes[i].get("root"), i)):  # the aggregate root first
        kids.setdefault(boxes[i]["parent"], []).append(i)
    flat = not any(b["compound"] for b in boxes.values())

    def node(i):
        b = boxes[i]
        if b["compound"]:
            w = max(LEAF_W + 32, tw(b["label"], 13) + 32, tw(b["stereo"], 11) + 32)
            return {"id": ids[i], "layoutOptions": {"elk.padding": BOX_PADDING, "elk.nodeSize.minimum": f"({round(w, 1)},0)",
                                                    "elk.nodeSize.constraints": "MINIMUM_SIZE"},
                    "children": [node(c) for c in kids.get(i, [])]}
        w = NODE_W if b["kind"] in ("bc", "sub") else LEAF_W
        h = round(max(58, sum(px * 1.38 for _, _, px in _lines(b, w)) + 24), 1)
        n = {"id": ids[i], "width": w, "height": h}
        if flat:
            n["layoutOptions"] = {"elk.partitioning.partition": "1" if b["kind"] == "sub" else "0"}
        return n

    elk_edges = []
    for k, e in enumerate(edges):
        labs = []
        for end, place in (("tail", "TAIL"), ("head", "HEAD")):
            if e[end]:
                w, h = _end_size(e[end])
                labs.append({"id": f"l{k}{end}", "text": e[end], "width": w, "height": h,
                             "layoutOptions": {"elk.edgeLabels.placement": place}})
        cl = _center_lines(e)
        if cl:
            labs.append({"id": f"l{k}center", "text": " ".join(cl), "width": round(max(tw(s, 11) for s in cl) + 8, 1),
                         "height": len(cl) * 15 + 4, "layoutOptions": {"elk.edgeLabels.placement": "CENTER"}})
        elk_edges.append({"id": f"e{k}", "sources": [ids[e["source"]]], "targets": [ids[e["target"]]], "labels": labs})
    graph = {"id": "root", "layoutOptions": ELK_MAP if flat else ELK_AGG,
             "children": [node(i) for i in kids.get(None, [])], "edges": elk_edges}
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
                labels[lab["id"]] = (lab["x"], lab["y"], lab["width"], lab["height"])
    walk(out)
    return ({i: pos[ids[i]] for i in boxes}, [routes[f"e{k}"] for k in range(len(edges))],
            [{end: labels.get(f"l{k}{end}") for end in ("tail", "head", "center")} for k in range(len(edges))],
            out.get("width", 0), out.get("height", 0))


# ------------------------------------------------------------------ rendering

# shape of each box kind: (css class, corner radius). The legend draws its swatches from the same table, so a legend
# entry always looks like what it explains. Entities are square-cornered and solid; value objects rounded, dashed, tinted.
SHAPES = {"bc": ("bc", 14), "boundary": ("bnd", 10), "agg": ("agg", 4), "ent": ("leaf", 3), "root": ("leaf root", 3),
          "vo": ("leaf vo", 10)}


def _shape(b):
    if b["kind"] == "bc":
        return SHAPES["boundary" if b["compound"] else "bc"]
    if b["kind"] == "ent" and b["root"]:
        return SHAPES["root"]
    return SHAPES[b["kind"]]


def _leaf(b, x, y, w, h):
    if b["kind"] == "sub":
        out = [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="2" class="sd {b["fill"]}"/>']
    else:
        cls, rx = _shape(b)
        out = [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{rx}" class="{cls}"/>']
        if b.get("root"):
            out.append(f'<rect x="{f(x)}" y="{f(y)}" width="5" height="{f(h)}" class="root-bar"/>')
    ls = _lines(b, w)
    lh = [px * 1.38 for _, _, px in ls]
    cy = y + h / 2 - sum(lh) / 2
    for k, (s, cls, _) in enumerate(ls):
        cy += lh[k]
        out.append(f'<text x="{f(x + w / 2)}" y="{f(cy - lh[k] * 0.28)}" text-anchor="middle" class="{cls}">{escape(s)}</text>')
    return out


def render(title, sub, boxes, edges):
    pos, routes, labs, gw, gh = layout(boxes, edges)
    top = MARGIN + 52
    flat = not any(b["compound"] for b in boxes.values())
    width = max(MARGIN * 2 + gw, 560)
    role_names = {}  # notation -> prefLabels; one notation shared by two concepts lists both names
    for a, name in sorted({r for e in edges for r in e.get("roles", [])}):
        role_names.setdefault(a, []).append(name)
    kinds = [k for k in ("bc", "boundary", "agg", "ent", "vo") if any(
        (b["kind"] == "bc" and b["compound"] == (k == "boundary")) if k in ("bc", "boundary")
        else (b["kind"] == k and not b.get("root")) for b in boxes.values())]
    cs = any(e["type"] == "CustomerSupplier" for e in edges)
    subfills = sorted({b["fill"] for b in boxes.values() if b["kind"] == "sub"},
                      key=["sub-core", "sub-sup", "sub-gen", "sub-none"].index)
    etypes = [r[0] for r in RELS if any(e["type"] == r[0] for e in edges)]
    legend = [("k", k) for k in kinds] + [("s", s) for s in subfills] + \
             ([("root", None)] if any(b.get("root") for b in boxes.values()) else []) + [("e", t) for t in etypes] + \
             ([("ud", None)] if any(e["tail"] for e in edges) else []) + [("a", a) for a in role_names]
    per_row = max(1, int((width - 2 * MARGIN - 60) // 170))
    y_leg = top + gh + 28
    height = y_leg + 22 + -(-len(legend) // per_row) * 26 + MARGIN
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(width)} {f(height)}" width="{f(width)}" '
           f'height="{f(height)}" role="img" aria-label="{escape(title)}">',
           f"<style>{STYLE}</style>",
           f'<rect class="bg" x="0" y="0" width="{f(width)}" height="{f(height)}"/>',
           f'<text x="{MARGIN}" y="{MARGIN + 14}" class="title">{escape(title)}</text>',
           f'<text x="{MARGIN}" y="{MARGIN + 32}" class="sub">{escape(sub)}</text>']
    if flat:
        for kind, name in (("bc", "解空间 · 限界上下文"), ("sub", "问题空间 · 子域")):
            ys = [(pos[i][1], pos[i][1] + pos[i][3]) for i, b in boxes.items() if b["kind"] == kind]
            if ys:
                y0, y1 = top + min(a for a, _ in ys) - BAND_PAD, top + max(b for _, b in ys) + BAND_PAD
                out.append(f'<rect class="band" x="{MARGIN}" y="{f(y0)}" width="{f(width - 2 * MARGIN)}" '
                           f'height="{f(y1 - y0)}" rx="8"/>')
                for j, s in enumerate(name.split(" · ")):
                    out.append(f'<text class="band-t" x="{MARGIN + 12}" y="{f(y0 + 20 + 16 * j)}">{s}</text>')

    def attrs(i):
        b = boxes[i]
        x, y, w, h = pos[i]
        par = b["parent"] or ""
        return (f'data-iri="{escape(b["iri"])}" data-type="ddd:{local(ELEMENTS[b["kind"]][0])}" '
                f'data-parent="{escape(par)}" data-via="{escape(b.get("via") or "")}" '
                f'data-box="{f(MARGIN + x)} {f(top + y)} {f(w)} {f(h)}"')

    for i in sorted((i for i in boxes if boxes[i]["compound"]), key=lambda i: (boxes[i]["parent"] is not None, i)):
        b, (x, y, w, h) = boxes[i], pos[i]
        x, y = MARGIN + x, top + y
        kind = "boundary" if b["kind"] == "bc" else "aggregate"
        cls, rx = _shape(b)
        out.append(f'<g data-kind="{kind}" {attrs(i)}><title>{escape(b["stereo"] + " " + b["label"])}</title>')
        out.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{rx}" class="{cls}"/>')
        out.append(f'<text x="{f(x + 14)}" y="{f(y + 20)}" class="lbl-s">{escape(b["stereo"])}</text>')
        out.append(f'<text x="{f(x + 14)}" y="{f(y + 37)}" class="lbl-h">{escape(b["label"])}</text></g>')
    for k, e in enumerate(edges):
        d = "M" + " L".join(f"{f(MARGIN + x)},{f(top + y)}" for x, y in routes[k])
        zh = next(r[1] for r in RELS if r[0] == e["type"])
        tip = f'{zh}：{boxes[e["source"]]["label"]} — {boxes[e["target"]]["label"]}'
        out.append(f'<path data-kind="relationship" data-iri="{escape(e["iri"])}" data-type="ddd:{e["type"]}" '
                   f'data-source="{escape(e["source"])}" data-target="{escape(e["target"])}" d="{d}" '
                   f'class="{"e-impl" if e["type"] == "SubdomainImplementation" else "e"}"><title>{escape(tip)}</title></path>')
        for end in ("tail", "head", "center"):
            if not labs[k][end]:
                continue
            lx, ly, lw, lh = MARGIN + labs[k][end][0], top + labs[k][end][1], labs[k][end][2], labs[k][end][3]
            out.append(f'<g data-kind="edge-label" data-end="{end}" data-for="{escape(e["iri"])}" '
                       f'data-box="{f(lx)} {f(ly)} {f(lw)} {f(lh)}">')
            if end == "center":
                out.append(f'<rect x="{f(lx)}" y="{f(ly)}" width="{f(lw)}" height="{f(lh)}" rx="3" class="elab-bg"/>')
                for j, s in enumerate(_center_lines(e)):
                    out.append(f'<text x="{f(lx + lw / 2)}" y="{f(ly + 14 + 15 * j)}" text-anchor="middle" '
                               f'class="elab">{escape(s)}</text>')
            else:
                out.append(f'<rect x="{f(lx)}" y="{f(ly)}" width="{f(lw)}" height="{f(lh)}" rx="2" class="end"/>')
                out.append(f'<text x="{f(lx + lw / 2)}" y="{f(ly + 13)}" text-anchor="middle" class="end-t">'
                           f'{escape(e[end])}</text>')
            out.append("</g>")
    for i in sorted(i for i in boxes if not boxes[i]["compound"]):
        b, (x, y, w, h) = boxes[i], pos[i]
        out.append(f'<g data-kind="element" {attrs(i)}><title>{escape(b["stereo"] + " " + b["label"])}</title>')
        out += _leaf(b, MARGIN + x, top + y, w, h)
        out.append("</g>")
    out.append(f'<text class="lg-h" x="{MARGIN}" y="{f(y_leg + 12)}">图例</text>')
    names = {"sub-core": "核心域", "sub-sup": "支撑域", "sub-gen": "通用域", "sub-none": "子域（未分类）"}
    for n, (what, k) in enumerate(legend):
        lx, yy = MARGIN + 60 + (n % per_row) * 170, y_leg + 22 + (n // per_row) * 26
        out.append(f'<g data-kind="legend-item" data-legend="{escape(what + ":" + (k or ""))}">')
        if what == "k":
            cls, rx = SHAPES[k]
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="{rx}" class="{cls}"/>')
            name = ELEMENTS["bc" if k == "boundary" else k][1]
        elif what == "s":
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="2" class="sd {k}"/>')
            name = names[k]
        elif what == "root":
            cls, rx = SHAPES["root"]
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="{rx}" class="{cls}"/>')
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="5" height="18" class="root-bar"/>')
            name = "聚合根"
        elif what == "e":
            out.append(f'<path d="M{f(lx + 2)},{f(yy + 9)} L{f(lx + 30)},{f(yy + 9)}" '
                       f'class="{"e-impl" if k == "SubdomainImplementation" else "e"}"/>')
            name = next(r[1] for r in RELS if r[0] == k)
        elif what == "ud":
            out.append(f'<rect x="{f(lx)}" y="{f(yy)}" width="30" height="18" rx="2" class="end"/>')
            out.append(f'<text x="{f(lx + 15)}" y="{f(yy + 13)}" text-anchor="middle" class="end-t">U/D</text>')
            name = "上游 / 下游" + ("（S 供应方，C 客户）" if cs else "")
        else:
            out.append(f'<text x="{f(lx)}" y="{f(yy + 13)}" class="end-t">{escape(k)}</text>')
            name = "、".join(role_names[k])
        out.append(f'<text class="lg-t" x="{f(lx + 36)}" y="{f(yy + 13)}">{escape(name)}</text></g>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
