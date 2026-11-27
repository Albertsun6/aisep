"""The two read-only view tools (docs/mcp-interface.md §5.15, §5.16): model_list_views, model_render_view.

They only pick what to draw and call the renderers of `tools/aisep.py diagram` (aisep/diagram.py for ArchiMate 4,
aisep/diagram_c4.py for C4); selection, layout and SVG are theirs, unchanged. No view is written (§1)."""
import re

from aisep import core, diagram, diagram_c4, tools
from aisep.errors import AisepError

PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")  # spliced into SPARQL text by the renderers: plain names only


def _parse_ok(ctx):
    if tools._l0_failed(ctx):
        fs = tools._findings(ctx, ("L0",))
        raise AisepError("PARSE_FAILED", "有模型文件解析失败，不出图（图会缺内容）", hint="先修好这些文件（gate 同样会报）",
                         details={"files": sorted(f["file"] for f in fs if f["file"]), "findings": fs})


def _bad(field, message, **details):
    return AisepError("INVALID_ARGUMENT", message, details={"rejectedFields": [field], **details})


def _am4_viewpoints(ctx):
    return sorted({diagram.local(v) for (v,) in ctx.rows(
        f'SELECT DISTINCT ?v WHERE {{ ?v arch:includesConcept ?c FILTER(STRSTARTS(STR(?v), "{diagram.AM4VP}")) }}')})


def _counts_c4(sel):
    return sum(1 for b in sel[2].values() if not b["compound"]), len(sel[3])


# ---------------------------------------------------------------- model_list_views

def _model_views(ctx, model):
    slug = core.model_slug(model)
    views = []
    for (v,) in sorted(ctx.rows(f"SELECT DISTINCT ?v WHERE {{ ?v arch:inModel <{model}> ; a ?t }}")):
        if not ctx.is_a(v, core.ARCH + "Diagram"):
            continue
        vps = sorted(x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ <{v}> arch:viewConformsToViewpoint ?x }}"))
        vp = vps[0] if vps else None
        c4 = bool(vp and vp.startswith(diagram_c4.C4VP))
        members = ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inView <{v}> ; arch:inModel <{model}> }}")
        views.append({"iri": v, "label": ctx.label(v), "notation": "c4" if c4 else "archimate", "viewpoint": vp,
                      "viewpointLabel": (diagram_c4.VIEWPOINTS.get(diagram.local(vp)) if c4 else ctx.label(vp)) if vp else None,
                      "memberCount": len(members), "render": {"view": v}})
    projections = []
    for name in _am4_viewpoints(ctx):
        _, _, elements, rels, _ = diagram.select(ctx, model, viewpoint=name)
        if elements:
            projections.append({"notation": "archimate", "viewpoint": name, "label": ctx.label(diagram.AM4VP + name),
                                "elementCount": len(elements), "relationshipCount": len(rels),
                                "render": {"viewpoint": name, "model": slug}})
    m = diagram_c4.C4Model(ctx, model)
    children = {}
    for c, p in m.parent.items():
        children.setdefault(p, set()).add(m.kind.get(c))
    scopes = [("SystemContext", x) for x, k in m.kind.items() if k == "sys"]
    scopes += [("ContainerDiagram", x) for x, k in m.kind.items() if k == "sys" and children.get(x, set()) & diagram_c4.CONTAINERS]
    scopes += [("ComponentDiagram", x) for x, k in m.kind.items() if k in diagram_c4.CONTAINERS and "comp" in children.get(x, set())]
    envs = sorted({diagram_c4._env(m, x) for x, k in m.kind.items() if k in ("dnode", "inode")} - {""})
    order = list(diagram_c4.VIEWPOINTS)
    for vp, scope in sorted(scopes, key=lambda s: (order.index(s[0]), s[1])):
        n, r = _counts_c4(diagram_c4.select(ctx, vp, scope, model=model))
        projections.append({"notation": "c4", "viewpoint": vp, "label": diagram_c4.VIEWPOINTS[vp], "scope": scope,
                            "scopeLabel": ctx.label(scope), "elementCount": n, "relationshipCount": r,
                            "render": {"c4viewpoint": vp, "of": scope}})
    for env in envs:
        if not PLAIN.fullmatch(env):  # the renderer cannot take it (it goes into SPARQL text); not offered
            continue
        n, r = _counts_c4(diagram_c4.select(ctx, "C4Deployment", env, model=model))
        projections.append({"notation": "c4", "viewpoint": "C4Deployment", "label": diagram_c4.VIEWPOINTS["C4Deployment"],
                            "scope": env, "scopeLabel": env, "elementCount": n, "relationshipCount": r,
                            "render": {"c4viewpoint": "C4Deployment", "of": env, "model": slug}})
    return {"model": model, "slug": slug, "label": ctx.label(model), "views": views, "projections": projections}


def model_list_views(cfg, model=None, repo=None, ref=None):
    with tools.loaded(cfg, repo, ref, model) as (ctx, source):
        _parse_ok(ctx)
        if model is not None:
            models = [f"{core.MODEL_BASE}{core.model_slug(model)}/"]
        else:
            models = sorted({m for (m,) in ctx.rows("SELECT DISTINCT ?m WHERE { ?x arch:inModel ?m }")
                             if m.startswith(core.MODEL_BASE) and core.MODEL_SLUG_RE.fullmatch(m[len(core.MODEL_BASE):-1] or "-")
                             and m.endswith("/")})
        return {"models": [_model_views(ctx, m) for m in models], "source": source}


# ---------------------------------------------------------------- model_render_view

def _shape_of_call(view, viewpoint, model, c4viewpoint, of):
    given = [k for k, v in (("view", view), ("viewpoint", viewpoint), ("c4viewpoint", c4viewpoint)) if v is not None]
    if len(given) != 1:
        raise AisepError("INVALID_ARGUMENT", "view、viewpoint、c4viewpoint 须恰好给一个",
                         hint="三选一：{view} | {viewpoint, model} | {c4viewpoint, of}；可选值见 model_list_views 每项的 render",
                         details={"rejectedFields": given or ["view"]})
    if view is not None and (model is not None or of is not None):
        raise _bad("model" if model is not None else "of", "给了 view 时不接受 model、of（视图自己属于一个模型）")
    if viewpoint is not None:
        if model is None:
            raise _bad("model", "viewpoint 须同时给 model")
        if of is not None:
            raise _bad("of", "viewpoint（ArchiMate 视点）不接受 of；C4 视点用 c4viewpoint")
    if c4viewpoint is not None:
        if of is None:
            raise _bad("of", "c4viewpoint 须同时给 of（软件系统、容器的 IRI，或部署环境名）")
        if model is not None and c4viewpoint != "C4Deployment":
            raise _bad("model", f"{c4viewpoint} 的模型由 of 决定，不接受 model（只有 C4Deployment 可用 model 区分同名环境）")
        if c4viewpoint == "C4Deployment" and not PLAIN.fullmatch(of):
            raise _bad("of", f"C4Deployment 的 of 须为部署环境名（字母开头，只含字母、数字、_、-），收到 {of!r}")


def _iri(ctx, field, name):
    try:
        return core.expand(ctx, name)
    except AisepError as e:
        raise _bad(field, f"{field}：{e.message}") from None


def _model_of(ctx, field, iri):
    ms = sorted(m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{iri}> arch:inModel ?m }}"))
    if not ms:
        raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(iri)} 不是任何模型的成员（没有 arch:inModel）",
                         hint="从 model_list_views 的 render 里取参数", details={"rejectedFields": [field]})
    return ms[0]


def _render(fn, *args):
    try:
        return fn(*args)
    except diagram.RendererUnavailable as e:
        raise AisepError("RENDERER_UNAVAILABLE", f"出图器不可用：{e}", details={"reason": e.reason},
                         hint="在模型仓库根目录跑 `npm ci --prefix tools/elk --ignore-scripts`（需要 Node ≥ 20 在 PATH 上），再重试") from None


def _c4_result(sel, source):
    title, sub, boxes, edges, warnings = sel[:5]
    n, r = _counts_c4(sel)
    svg = _render(diagram_c4.render, title, sub, boxes, edges)
    return {"svg": svg, "title": title, "notation": "c4", "elementCount": n, "relationshipCount": r,
            "warnings": warnings + ([] if n else ["视图里没有元素"]), "source": source}


def model_render_view(cfg, view=None, viewpoint=None, model=None, c4viewpoint=None, of=None, repo=None, ref=None):
    _shape_of_call(view, viewpoint, model, c4viewpoint, of)
    with tools.loaded(cfg, repo, ref, model) as (ctx, source):
        _parse_ok(ctx)
        try:
            if c4viewpoint is not None:
                if c4viewpoint == "C4Deployment":
                    m = f"{core.MODEL_BASE}{core.model_slug(model)}/" if model is not None else None
                    return _c4_result(diagram_c4.select(ctx, c4viewpoint, of, model=m), source)
                scope = _iri(ctx, "of", of)
                _model_of(ctx, "of", scope)
                return _c4_result(diagram_c4.select(ctx, c4viewpoint, scope), source)
            if view is not None:
                v = _iri(ctx, "view", view)
                m = _model_of(ctx, "view", v)
                if not ctx.is_a(v, core.ARCH + "Diagram"):
                    raise _bad("view", f"{core.short(v)} 不是视图（arch:Diagram）")
                vps = sorted(x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ <{v}> arch:viewConformsToViewpoint ?x }}"))
                if vps and vps[0].startswith(diagram_c4.C4VP):
                    return _c4_result(diagram_c4.select(ctx, vps[0], None, view=v), source)
                title, sub, elements, rels, warnings = diagram.select(ctx, m, view=v)
            else:
                known = _am4_viewpoints(ctx)
                if viewpoint not in known:
                    raise _bad("viewpoint", f"没有 ArchiMate 视点 {viewpoint!r}", candidates=known)
                m = f"{core.MODEL_BASE}{core.model_slug(model)}/"
                title, sub, elements, rels, warnings = diagram.select(ctx, m, viewpoint=viewpoint)
        except ValueError as e:  # the renderers' own refusals (wrong kind of scope, unknown environment, …)
            raise AisepError("INVALID_ARGUMENT", f"无法出图：{e}", details={"rejectedFields": [
                "view" if view is not None else "of" if c4viewpoint is not None else "viewpoint"]}) from None
        svg = _render(diagram.render, title, sub, elements, rels)
        return {"svg": svg, "title": title, "notation": "archimate", "elementCount": len(elements),
                "relationshipCount": len(rels), "warnings": warnings + ([] if elements else ["视图里没有元素"]),
                "source": source}
