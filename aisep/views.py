"""The two read-only view tools (docs/mcp-interface.md §5.15, §5.16): model_list_views, model_render_view.

They only pick what to draw and call the renderers of `tools/aisep.py diagram` (aisep/diagram.py for ArchiMate 4,
aisep/diagram_c4.py for C4, aisep/diagram_uml.py for UML class diagrams, aisep/diagram_ddd.py for DDD, aisep/diagram_bpmn.py
for BPMN processes); selection, layout and output are theirs, unchanged. BPMN comes back as BPMN 2.0 XML (format
"bpmn-xml", for a BPMN viewer such as bpmn-js), everything else as SVG (format "svg"). No view is written (§1)."""
import re

from aisep import core, diagram, diagram_bpmn, diagram_c4, diagram_ddd, diagram_uml, tools
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
        uml = bool(vp and vp.startswith(diagram_uml.UMLVP))
        members = ctx.rows(f"SELECT DISTINCT ?x WHERE {{ ?x arch:inView <{v}> ; arch:inModel <{model}> }}")
        vplabel = (diagram_c4.VIEWPOINTS.get(diagram.local(vp)) if c4 else
                   (diagram_uml.DIAGRAMS.get(vp[len(diagram_uml.UMLVP):]) or ctx.label(vp)) if uml else ctx.label(vp)) if vp else None
        views.append({"iri": v, "label": ctx.label(v), "notation": "c4" if c4 else "uml" if uml else "archimate",
                      "viewpoint": vp, "viewpointLabel": vplabel, "memberCount": len(members), "render": {"view": v}})
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
    projections += _bpmn_projections(ctx, model) + _uml_projections(ctx, model, slug) + _ddd_projections(ctx, model, slug)
    return {"model": model, "slug": slug, "label": ctx.label(model), "views": views, "projections": projections}


def _bpmn_projections(ctx, model):
    """One item per bpmn:Process of the model that draws at least one flow node. A process the renderer refuses (a
    label XML cannot carry, a local name bpmn-js cannot load as an id, ...) is not offered: `diagram --process` says why."""
    out = []
    for p, label, m in diagram_bpmn.processes(ctx):
        if m != model:
            continue
        try:
            sel, _ = diagram_bpmn.select(ctx, p)
        except ValueError:
            continue
        if sel["nodes"]:
            out.append({"notation": "bpmn", "viewpoint": "Process", "label": "BPMN 流程", "scope": p,
                        "scopeLabel": label or diagram.local(p), "elementCount": len(sel["nodes"]),
                        "relationshipCount": len(sel["flows"]), "render": {"process": p}})
    return out


def _uml_projections(ctx, model, slug):
    out = []
    for kind, label in diagram_uml.DIAGRAMS.items():
        _, _, nodes, _, edges, _ = diagram_uml.select(ctx, model, diagram=kind)
        if nodes:
            out.append({"notation": "uml", "viewpoint": kind, "label": label, "elementCount": len(nodes),
                        "relationshipCount": len(edges), "render": {"umldiagram": kind, "model": slug}})
    return out


def _ddd_projections(ctx, model, slug):
    """The views `diagram --ddd list` offers: the context map, and an aggregate diagram per bounded context that owns
    an aggregate."""
    out = []
    for vp, scope, _ in diagram_ddd.views(ctx, model):
        try:
            sel = diagram_ddd.select(ctx, vp, scope, model=model if scope is None else None)
        except ValueError:
            continue
        n, r = diagram_ddd.counts(sel[2], sel[3])
        item = {"notation": "ddd", "viewpoint": vp, "label": diagram_ddd.VIEWPOINTS[vp]}
        if scope is None:
            item.update(elementCount=n, relationshipCount=r, render={"dddviewpoint": vp, "model": slug})
        else:
            item.update(scope=scope, scopeLabel=ctx.label(scope) or diagram.local(scope), elementCount=n,
                        relationshipCount=r, render={"dddviewpoint": vp, "of": scope})
        out.append(item)
    return out


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

ENTRIES = ("view", "viewpoint", "c4viewpoint", "umldiagram", "dddviewpoint", "process")


def _shape_of_call(view, viewpoint, model, c4viewpoint, of, umldiagram=None, dddviewpoint=None, process=None):
    given = [k for k, v in zip(ENTRIES, (view, viewpoint, c4viewpoint, umldiagram, dddviewpoint, process)) if v is not None]
    if len(given) != 1:
        raise AisepError("INVALID_ARGUMENT", "、".join(ENTRIES) + " 须恰好给一个",
                         hint="六选一：{view} | {viewpoint, model} | {c4viewpoint, of} | {umldiagram, model} | "
                              "{dddviewpoint: ContextMap, model} | {dddviewpoint: AggregateDiagram, of} | {process}；"
                              "可选值见 model_list_views 每项的 render",
                         details={"rejectedFields": given or ["view"]})
    for key, value in (("view", view), ("process", process)):
        if value is not None and (model is not None or of is not None):
            raise _bad("model" if model is not None else "of", f"给了 {key} 时不接受 model、of（它自己属于一个模型）")
    if umldiagram is not None:
        if model is None:
            raise _bad("model", "umldiagram 须同时给 model")
        if of is not None:
            raise _bad("of", "umldiagram 不接受 of")
    if dddviewpoint == "ContextMap":
        if model is None:
            raise _bad("model", "dddviewpoint=ContextMap 须同时给 model")
        if of is not None:
            raise _bad("of", "dddviewpoint=ContextMap 不接受 of（画整个模型的上下文映射）")
    if dddviewpoint == "AggregateDiagram":
        if of is None:
            raise _bad("of", "dddviewpoint=AggregateDiagram 须同时给 of（限界上下文的 IRI）")
        if model is not None:
            raise _bad("model", "dddviewpoint=AggregateDiagram 的模型由 of 决定，不接受 model")
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


def _render(field, fn, *args):
    """The renderer's own failures, mapped here and not by the selection's `except ValueError` (a layout that printed
    no JSON is a JSONDecodeError, a ValueError, but not the caller's fault: elk_layout raises RendererUnavailable)."""
    try:
        return fn(*args)
    except diagram.RendererUnavailable as e:
        raise AisepError("RENDERER_UNAVAILABLE", f"出图器不可用：{e}", details={"reason": e.reason},
                         hint="在模型仓库根目录跑 `npm ci --prefix tools/elk --ignore-scripts`（需要 Node ≥ 20 在 PATH 上），"
                              "再重试；reason 为 layout-timeout、layout-failed 时看 message 里 ELK 的输出") from None
    except diagram.TextNotXml as e:  # check_xml_text: model text with a character XML 1.0 cannot carry (same refusal as the CLI)
        raise _text_not_xml(field, e) from None


def _text_not_xml(field, e):
    return AisepError("INVALID_ARGUMENT", f"无法出图：{e}", hint="把模型文本里的控制字符去掉（写工具本就拒绝写入它们）",
                      details={"rejectedFields": [field], "reason": "text-not-xml"})


def _result(notation, title, n, r, warnings, source, svg=None, bpmn=None):
    """One shape for every notation: format "svg" carries `svg` (the field of the first version, kept), format
    "bpmn-xml" carries `content`."""
    out = {"format": "svg", "svg": svg} if bpmn is None else {"format": "bpmn-xml", "content": bpmn}
    return {**out, "title": title, "notation": notation, "elementCount": n, "relationshipCount": r,
            "warnings": warnings + ([] if n else ["视图里没有元素"]), "source": source}


def _c4_result(field, sel, source):
    title, sub, boxes, edges, warnings = sel[:5]
    n, r = _counts_c4(sel)
    svg = _render(field, diagram_c4.render, title, sub, boxes, edges)
    return _result("c4", title, n, r, warnings, source, svg=svg)


def _uml_kind(view, vp):
    kind = vp[len(diagram_uml.UMLVP):]
    if kind not in diagram_uml.DIAGRAMS:
        raise _bad("view", f"{core.short(view)} 的视点 umlvp:{kind} 暂不支持（首批只有 "
                           f"{', '.join('umlvp:' + k for k in diagram_uml.DIAGRAMS)}）")
    return kind


def model_render_view(cfg, view=None, viewpoint=None, model=None, c4viewpoint=None, of=None, umldiagram=None,
                      dddviewpoint=None, process=None, repo=None, ref=None):
    _shape_of_call(view, viewpoint, model, c4viewpoint, of, umldiagram, dddviewpoint, process)
    field = ("view" if view is not None else "of" if of is not None else "viewpoint" if viewpoint is not None else
             "umldiagram" if umldiagram is not None else "dddviewpoint" if dddviewpoint is not None else "process")
    with tools.loaded(cfg, repo, ref, model) as (ctx, source):
        _parse_ok(ctx)
        c4sel = uml = ddd = bpmn = None
        try:  # selection only; rendering (and its failures) is outside, in _render
            if c4viewpoint is not None:
                if c4viewpoint == "C4Deployment":
                    m = f"{core.MODEL_BASE}{core.model_slug(model)}/" if model is not None else None
                    c4sel = diagram_c4.select(ctx, c4viewpoint, of, model=m)
                else:
                    scope = _iri(ctx, "of", of)
                    _model_of(ctx, "of", scope)
                    c4sel = diagram_c4.select(ctx, c4viewpoint, scope)
            elif view is not None:
                v = _iri(ctx, "view", view)
                m = _model_of(ctx, "view", v)
                if not ctx.is_a(v, core.ARCH + "Diagram"):
                    raise _bad("view", f"{core.short(v)} 不是视图（arch:Diagram）")
                vps = sorted(x for (x,) in ctx.rows(f"SELECT ?x WHERE {{ <{v}> arch:viewConformsToViewpoint ?x }}"))
                if vps and vps[0].startswith(diagram_c4.C4VP):
                    c4sel = diagram_c4.select(ctx, vps[0], None, view=v)
                elif vps and vps[0].startswith(diagram_uml.UMLVP):
                    uml = diagram_uml.select(ctx, m, view=v, diagram=_uml_kind(v, vps[0]))
                else:
                    title, sub, elements, rels, warnings = diagram.select(ctx, m, view=v)
            elif umldiagram is not None:
                uml = diagram_uml.select(ctx, f"{core.MODEL_BASE}{core.model_slug(model)}/", diagram=umldiagram)
            elif dddviewpoint is not None:
                if dddviewpoint == "ContextMap":
                    ddd = diagram_ddd.select(ctx, dddviewpoint, None, model=f"{core.MODEL_BASE}{core.model_slug(model)}/")
                else:
                    scope = _iri(ctx, "of", of)
                    _model_of(ctx, "of", scope)
                    ddd = diagram_ddd.select(ctx, dddviewpoint, scope)
            elif process is not None:
                p = _iri(ctx, "process", process)
                _model_of(ctx, "process", p)
                bpmn = diagram_bpmn.select(ctx, p)
            else:
                known = _am4_viewpoints(ctx)
                if viewpoint not in known:
                    raise _bad("viewpoint", f"没有 ArchiMate 视点 {viewpoint!r}", candidates=known)
                m = f"{core.MODEL_BASE}{core.model_slug(model)}/"
                title, sub, elements, rels, warnings = diagram.select(ctx, m, viewpoint=viewpoint)
        except diagram.TextNotXml as e:  # BPMN checks its text while selecting (the SVG renderers do it in _render)
            raise _text_not_xml(field, e) from None
        except ValueError as e:  # the selection's own refusals (wrong kind of scope, unknown environment, …)
            raise AisepError("INVALID_ARGUMENT", f"无法出图：{e}", details={"rejectedFields": [field]}) from None
        if c4sel is not None:
            return _c4_result(field, c4sel, source)
        if uml is not None:
            title, sub, nodes, packages, edges, warnings = uml
            svg = _render(field, diagram_uml.render, title, sub, nodes, packages, edges)
            return _result("uml", title, len(nodes), len(edges), warnings, source, svg=svg)
        if ddd is not None:
            title, sub, boxes, edges, warnings, _ = ddd
            svg = _render(field, diagram_ddd.render, title, sub, boxes, edges)
            return _result("ddd", title, *diagram_ddd.counts(boxes, edges), warnings, source, svg=svg)
        if bpmn is not None:
            sel, warnings = bpmn
            xml = _render(field, diagram_bpmn.render, sel)
            return _result("bpmn", sel["label"] or diagram.local(sel["process"]), len(sel["nodes"]), len(sel["flows"]),
                           warnings, source, bpmn=xml)
        svg = _render(field, diagram.render, title, sub, elements, rels)
        return _result("archimate", title, len(elements), len(rels), warnings, source, svg=svg)
