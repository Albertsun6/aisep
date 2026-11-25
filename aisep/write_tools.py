"""Write tools model_add_element, model_add_relationship, model_set_labels, model_remove, model_set_attributes
(docs/mcp-interface.md §5.1-5.3, §5.5, §5.10, §5.12).
Validation is the prototype's L0-L2 on the candidate graph (no second rule set); these functions only decide WHAT to
write and WHERE, then hand the edit to aisep.writer.transaction."""
import difflib, os, re

import pyoxigraph as ox

from aisep import core, writer
from aisep.errors import AisepError

SKOS = core.SKOS
PREF, ALT, DEF = SKOS + "prefLabel", SKOS + "altLabel", SKOS + "definition"
IN_MODEL, SOURCE, TARGET = core.ARCH + "inModel", core.ARCH + "source", core.ARCH + "target"
SUBCLASS = core.NS["rdfs"] + "subClassOf"
MODULE_FILE = {"am4": "am4.ttl", "bpmn": "bpmn.ttl", "uml": "uml.ttl", "ddd": "ddd.ttl", "ext-code": "code.ttl",
               "ext-verification": "verification.ttl"}  # everything else -> governance.ttl (§5.1 table)
SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
LABEL_MAX, DEFINITION_MAX = 200, 4000
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
RDF_TYPE = core.A
LABEL_LIMITS = {PREF: LABEL_MAX, ALT: LABEL_MAX, DEF: DEFINITION_MAX}
UNSET = object()
PROTECTED_TYPES = {core.AISEP + "ApprovalRecord", core.AISEP + "AgentActivity"}


# ---------------------------------------------------------------- helpers

def _no_extra(extra):
    """Unknown arguments are a tool execution error naming them, not a TypeError (§3.1, contract of the S4 tests)."""
    if extra:
        raise AisepError("INVALID_ARGUMENT", f"不接受的参数：{', '.join(sorted(extra))}",
                         details={"rejectedFields": sorted(extra)})


def _bad(field, msg):
    return AisepError("INVALID_ARGUMENT", msg, details={"rejectedFields": [field]})


def _model(ws, model):
    """A bare slug or the full model IRI (with or without its trailing '/'); anything path-like is an argument error,
    and the slug must name an existing models/<slug>/ directory with exactly that spelling (case-insensitive file
    systems would otherwise accept 'Procurement')."""
    slug = core.model_slug(model)
    mdir = os.path.join(ws.root, "models")
    if slug not in (os.listdir(mdir) if os.path.isdir(mdir) else ()) or not os.path.isdir(os.path.join(mdir, slug)):
        raise AisepError("MODEL_NOT_FOUND", f"没有模型 {model}（models/{slug}/ 不存在）", details={"model": model})
    return slug, f"{core.MODEL_BASE}{slug}/"


def _check_text(field, v, limit, allow_newline=False):
    """Labels are one line of plain text: no control or line-separator characters (a label must not be able to forge a
    separate line in a tool's text output, SEC-7), at most `limit` characters. A definition may hold newlines."""
    bad = _CONTROL.search(v.replace("\n", "") if allow_newline else v)
    if bad:
        raise _bad(field, f"{field} 不能含控制字符或换行（U+{ord(bad.group()):04X}）")
    if len(v) > limit:
        raise _bad(field, f"{field} 最长 {limit} 个字符（现为 {len(v)}）")


def _pfx(ws, f, model_iri):
    """Prefixes for rendering into file f: the file's own, else the prototype's, plus ':' = the model namespace."""
    p = dict(core.NS)
    p[""] = model_iri
    p.update(writer.file_prefixes(ws.text(f)))
    return p


def _classes(ctx):
    """Declared classes: owl:Class / rdfs:Class in module graphs + model-declared specialisations (R1)."""
    onto = {c for (c,) in ctx.rows(f"SELECT DISTINCT ?c WHERE {{ GRAPH ?g {{ ?c a ?k }} {ctx.onto_graph_filter()} "
                                    "VALUES ?k { owl:Class rdfs:Class } }")}
    model = {c for (c,) in ctx.rows(f"SELECT DISTINCT ?c WHERE {{ GRAPH ?g {{ ?c rdfs:subClassOf ?d }} {ctx.src_graph_filter()} }}")}
    return onto | model


def _resolve_class(ctx, name, field="type"):
    try:
        iri = core.expand(ctx, name)
    except AisepError:
        iri = None
    known = _classes(ctx)
    if iri not in known:
        want = name.split(":")[-1].split("#")[-1].lower()
        cands = sorted(known, key=lambda c: -difflib.SequenceMatcher(None, want, c.rsplit("#", 1)[-1].rsplit("/", 1)[-1].lower()).ratio())
        raise AisepError("UNKNOWN_TYPE", f"{name} 不是已加载模块声明的类", hint="从 details.candidates 里选一个",
                         details={"candidates": [core.short(c) for c in cands[:5]], "rejectedFields": [field]})
    abstract = {c for (c,) in ctx.rows(f"SELECT ?c WHERE {{ GRAPH ?g {{ ?c arch:isAbstractClass true }} {ctx.onto_graph_filter()} }}")}
    if iri in core.ABSTRACT_ROOTS or iri in abstract:
        raise AisepError("ABSTRACT_TYPE", f"{core.short(iri)} 是抽象类，不能直接实例化", details={"rejectedFields": [field]})
    return iri


def _subject_triples(ctx):
    """subject IRI -> [(file rel, Triple)] over the source files."""
    out = {}
    for f, qs in ctx.src_quads.items():
        for q in qs:
            if isinstance(q.subject, ox.NamedNode):
                out.setdefault(q.subject.value, []).append((ctx.rel(f), ox.Triple(q.subject, q.predicate, q.object)))
    return out


def _type_file(st, iri):
    return next((f for f, t in st.get(iri, ()) if t.predicate.value == core.A), None)


def declaring_module(ctx, cls):
    """§5.1: the module that declares a class. Language namespaces by aisep:ownsNamespace; the shared aisep# namespace
    by which module's own aisep:loads file declares the class (F15). Model specialisations follow their parent."""
    seen = set()
    while cls not in seen:
        seen.add(cls)
        parents = [d for (d,) in ctx.rows(f"SELECT ?d WHERE {{ GRAPH ?g {{ <{cls}> rdfs:subClassOf ?d }} {ctx.src_graph_filter()} }}")]
        if not parents:
            break
        cls = parents[0]
    if not cls.startswith(core.AISEP):
        o = core.owner(ctx.mods, cls)
        return o.name if o else None
    graphs = [g for (g,) in ctx.rows(f"SELECT DISTINCT ?g WHERE {{ GRAPH ?g {{ <{cls}> a ?k }} {ctx.onto_graph_filter()} }}")]
    for g in graphs:
        f = g[len(core.ONTO_G):]
        for m in ctx.mods:
            if any(ctx.rel(x) == f for x in m.loads) and f.startswith(f"modules/{m.name}/"):
                return m.name
    return None


def default_element_file(ctx, slug, cls):
    return f"models/{slug}/{MODULE_FILE.get(declaring_module(ctx, cls), 'governance.ttl')}"


def default_relationship_file(st, slug, source, target):
    """§5.1: both ends in one file -> it; else the end that is not in am4.ttl; neither in am4.ttl -> the source's."""
    fs, ft = _type_file(st, source), _type_file(st, target)
    if fs == ft and fs:
        return fs
    am4 = f"models/{slug}/am4.ttl"
    if fs == am4 and ft:
        return ft
    return fs or ft or am4


def _check_file(slug, f):
    if not isinstance(f, str) or not re.fullmatch(rf"models/{re.escape(slug)}/[^/]+\.ttl", f):
        raise _bad("file", f"file 必须是 models/{slug}/ 下的 .ttl 文件")
    return f


def _member(ctx, st, iri_in, field):
    try:
        iri = core.expand(ctx, iri_in)
    except AisepError:
        iri = iri_in
    if not any(t.predicate.value == IN_MODEL for _, t in st.get(iri, ())):
        from aisep.tools import _candidates
        raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(iri)} 不是本仓库模型的成员", hint="从 details.candidates 里选",
                         details={"candidates": _candidates(ctx, iri), "rejectedFields": [field]})
    return iri


def _camel(s):
    words = re.findall(r"[A-Za-z0-9]+", s)
    return (words[0][0].lower() + words[0][1:] + "".join(w[0].upper() + w[1:] for w in words[1:])) if words else ""


def _lit(v, lang):
    return ox.Literal(v, language=lang)


# ---------------------------------------------------------------- §5.2

def add_element_build(model, type, prefLabel, altLabel=None, slug=None, definition=None, attributes=None, file=None):
    """The plan function of model_add_element (argument checks here, the rest in build(ws, ctx)); aisep.actions
    composes it with other plan functions inside one writer.transaction."""
    if not isinstance(prefLabel, str) or not prefLabel.strip():
        raise _bad("prefLabel", "prefLabel 不能为空")
    _check_text("prefLabel", prefLabel, LABEL_MAX)
    for name, v in (("altLabel", altLabel), ("definition", definition)):
        if v is not None and not isinstance(v, str):
            raise _bad(name, f"{name} 须为字符串")
    if altLabel:
        _check_text("altLabel", altLabel, LABEL_MAX)
    if definition:
        _check_text("definition", definition, DEFINITION_MAX, allow_newline=True)
    if slug is None:
        if not altLabel:
            raise _bad("slug", "slug 与 altLabel 都没给，无法生成 IRI（不自动拼音）")
        slug = _camel(altLabel)
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise _bad("slug", f"slug {slug!r} 须匹配 ^[A-Za-z][A-Za-z0-9]*$")

    def build(ws, ctx):
        mslug, model_iri = _model(ws, model)
        cls = _resolve_class(ctx, type)
        if PROTECTED_TYPES & set(ctx.ancestors(cls)):  # approval records and AI activities never come from a write tool
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(cls)} 是批准记录或 AI 活动，不能经写工具新增",
                             hint="批准只能由批准人经 governance_record_approval 记录", details={"rejectedFields": ["type"]})
        if core.ARCH + "QualifiedRelationship" in ctx.ancestors(cls):
            raise _bad("type", f"{core.short(cls)} 是关系类，请用 model_add_relationship")
        iri = model_iri + slug
        s = ox.NamedNode(iri)
        triples = [ox.Triple(s, ox.NamedNode(core.A), ox.NamedNode(cls)),
                   ox.Triple(s, ox.NamedNode(IN_MODEL), ox.NamedNode(model_iri)),
                   ox.Triple(s, ox.NamedNode(PREF), _lit(prefLabel, "zh"))]
        if altLabel:
            triples.append(ox.Triple(s, ox.NamedNode(ALT), _lit(altLabel, "en")))
        if definition:
            triples.append(ox.Triple(s, ox.NamedNode(DEF), _lit(definition, "zh")))
        for a in attributes or ():
            if not isinstance(a, dict) or set(a) != {"predicate", "value"} or not isinstance(a["value"], dict):
                raise _bad("attributes", "attributes 每项须为 {predicate, value}")
            v = a["value"]
            try:  # pyoxigraph rejects a bad IRI, language tag or non-string value with ValueError/TypeError (MCP-5)
                if set(v) == {"iri"}:
                    o = ox.NamedNode(core.expand(ctx, v["iri"]))
                elif "value" in v and set(v) <= {"value", "datatype", "lang"}:
                    o = ox.Literal(v["value"], language=v.get("lang")) if v.get("lang") else \
                        ox.Literal(v["value"], datatype=ox.NamedNode(core.expand(ctx, v["datatype"]))) if v.get("datatype") else \
                        ox.Literal(v["value"])
                else:
                    raise _bad("attributes", "attributes.value 须为 {iri} 或 {value, datatype?, lang?}")
                p = ox.NamedNode(core.expand(ctx, a["predicate"]))
            except (ValueError, TypeError) as e:
                raise _bad("attributes", f"attributes 里有不合法的 IRI、语言标签或值：{e}") from None
            except AisepError as e:  # core.expand refused an IRI or prefix (its own error names no field)
                if "rejectedFields" in e.details:
                    raise
                raise _bad("attributes", f"attributes 里有不合法的 IRI 或前缀名：{e.message}") from None
            if p.value == RDF_TYPE:  # one element, one type (hard rule 3); the type is the `type` argument
                raise _bad("attributes", "attributes 不能写 rdf:type，类型只由 type 参数给出")
            if p.value in LABEL_LIMITS and isinstance(o, ox.Literal):  # same rules as the named arguments (SEC-7)
                _check_text("attributes", o.value, LABEL_LIMITS[p.value], allow_newline=p.value == DEF)
            triples.append(ox.Triple(s, p, o))
        st = _subject_triples(ctx)
        f = _check_file(mslug, file) if file else default_element_file(ctx, mslug, cls)
        pfx = _pfx(ws, f, model_iri)
        block = writer.render_block(s, [(t.predicate, t.object) for t in triples], pfx)
        result = {"iri": iri, "file": f, "turtle": block}
        if iri in st:
            if writer.canon([t for _, t in st[iri]]) == writer.canon(triples):
                return {"result": dict(result, file=_type_file(st, iri) or f), "edits": {}}
            raise AisepError("IRI_EXISTS", f"{core.short(iri)} 已存在且内容不同（元素的 slug 就是身份，不自动加 -2）",
                             hint="换一个 slug，或用 model_set_labels 改名称",
                             details={"existing": {"types": [core.short(t.object) for _, t in st[iri] if t.predicate.value == core.A],
                                                   "label": ctx.label(iri)}})
        return {"result": result, "edits": {f: writer.append_block(ws.text(f), block, pfx)}, "added": {f: triples}}

    return build


def model_add_element(cfg, model, type, prefLabel, altLabel=None, slug=None, definition=None, attributes=None,
                      file=None, dryRun=False, repo=None, **extra):
    _no_extra(extra)
    return writer.transaction(cfg, repo, add_element_build(model, type, prefLabel, altLabel, slug, definition,
                                                           attributes, file), dryRun)


# ---------------------------------------------------------------- §5.3

def add_relationship_build(type, source, target, model=None, file=None):
    """The plan function of model_add_relationship."""

    def build(ws, ctx):
        st = _subject_triples(ctx)
        s_iri, t_iri = _member(ctx, st, source, "source"), _member(ctx, st, target, "target")
        cls = _resolve_class(ctx, type)
        if PROTECTED_TYPES & set(ctx.ancestors(cls)):
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(cls)} 是批准记录或 AI 活动，不能经写工具新增",
                             details={"rejectedFields": ["type"]})
        if core.ARCH + "QualifiedRelationship" not in ctx.ancestors(cls):
            raise _bad("type", f"{core.short(cls)} 不是限定关系类，元素请用 model_add_element")
        if model is None:
            m = next(t.object.value for _, t in st[s_iri] if t.predicate.value == IN_MODEL)
        else:
            m = model
        mslug, model_iri = _model(ws, m)
        for r, ts in st.items():  # idempotent: same class, same endpoints -> the existing resource
            p = {(t.predicate.value, t.object.value) for _, t in ts}
            if (core.A, cls) in p and (SOURCE, s_iri) in p and (TARGET, t_iri) in p:
                return {"result": {"iri": r, "file": _type_file(st, r), "turtle": None}, "edits": {}}
        uf = ctx.nearest(cls, ctx.uf)
        verb = re.split(r"[#/]", uf)[-1] if uf else (lambda n: n[:1].lower() + n[1:])(re.split(r"[#/]", cls)[-1])
        local = lambda x: x.rsplit("/", 1)[-1]
        base = f"{model_iri}rel-{local(s_iri)}-{verb}-{local(t_iri)}"
        iri, n = base, 1
        while iri in st:  # a different relationship class already took the name (F12)
            n += 1
            iri = f"{base}-{n}"
        s = ox.NamedNode(iri)
        triples = [ox.Triple(s, ox.NamedNode(core.A), ox.NamedNode(cls)),
                   ox.Triple(s, ox.NamedNode(IN_MODEL), ox.NamedNode(model_iri)),
                   ox.Triple(s, ox.NamedNode(SOURCE), ox.NamedNode(s_iri)),
                   ox.Triple(s, ox.NamedNode(TARGET), ox.NamedNode(t_iri))]
        f = _check_file(mslug, file) if file else default_relationship_file(st, mslug, s_iri, t_iri)
        pfx = _pfx(ws, f, model_iri)
        block = writer.render_block(s, [(t.predicate, t.object) for t in triples], pfx)
        return {"result": {"iri": iri, "file": f, "turtle": block},
                "edits": {f: writer.append_block(ws.text(f), block, pfx)}, "added": {f: triples}}

    return build


def model_add_relationship(cfg, type, source, target, model=None, file=None, dryRun=False, repo=None, **extra):
    _no_extra(extra)
    return writer.transaction(cfg, repo, add_relationship_build(type, source, target, model, file), dryRun)


# ---------------------------------------------------------------- §5.10

def set_labels_build(iri, prefLabel=UNSET, altLabel=UNSET, definition=UNSET):
    """The plan function of model_set_labels."""
    if prefLabel is UNSET and altLabel is UNSET and definition is UNSET:
        raise AisepError("INVALID_ARGUMENT", "prefLabel、altLabel、definition 至少给一个",
                         details={"rejectedFields": ["prefLabel", "altLabel", "definition"]})
    if prefLabel is not UNSET and (not isinstance(prefLabel, str) or not prefLabel.strip()):
        raise _bad("prefLabel", "prefLabel 不能为空，也不能删除（恰好一个 @zh 名称）")
    for name, v in (("altLabel", altLabel), ("definition", definition)):
        if v is not UNSET and v is not None and (not isinstance(v, str) or not v.strip()):
            raise _bad(name, f"{name} 须为非空字符串，或 null 表示删除")
    for name, v, limit in (("prefLabel", prefLabel, LABEL_MAX), ("altLabel", altLabel, LABEL_MAX),
                           ("definition", definition, DEFINITION_MAX)):
        if isinstance(v, str):
            _check_text(name, v, limit, allow_newline=name == "definition")

    def build(ws, ctx):
        st = _subject_triples(ctx)
        x = _member(ctx, st, iri, "iri")
        types = {t.object.value for _, t in st[x] if t.predicate.value == core.A}
        if any(PROTECTED_TYPES & set(ctx.ancestors(c)) for c in types):
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 是批准记录或 AI 活动，只追加不修改",
                             hint="改结论请写一条更晚的批准记录")
        mslug = next(t.object.value for _, t in st[x] if t.predicate.value == IN_MODEL)[len(core.MODEL_BASE):].strip("/")
        outside = sorted({f for f, _ in st[x] if not f.startswith(f"models/{mslug}/")})
        if outside:
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 的三元组有一部分在别的模型目录里，不改别人的模型",
                             details={"files": outside})
        spec = [(PREF, "zh", prefLabel), (ALT, "en", altLabel), (DEF, "zh", definition)]
        before = {k: next((t.object.value for _, t in st[x] if t.predicate.value == p and isinstance(t.object, ox.Literal)
                           and (t.object.language or "") == lang), None)
                  for k, (p, lang, _) in zip(("prefLabel", "altLabel", "definition"), spec)}
        removed, added, adds = {}, {}, {}
        type_file = _type_file(st, x)
        for p, lang, v in spec:
            if v is UNSET:
                continue
            old = [(f, t) for f, t in st[x] if t.predicate.value == p and isinstance(t.object, ox.Literal)
                   and (t.object.language or "") == lang]
            if v is not None and [t.object.value for _, t in old] == [v]:
                continue  # unchanged
            for f, t in old:
                removed.setdefault(f, set()).add((t.subject.value, p, t.object))
            if v is not None:
                f = old[0][0] if old else type_file
                nt = ox.Triple(ox.NamedNode(x), ox.NamedNode(p), _lit(v, lang))
                added.setdefault(f, []).append(nt)
                adds.setdefault(f, {}).setdefault(x, []).append((nt.predicate, nt.object))
        after = {k: before[k] if v is UNSET else v for k, (_, _, v) in zip(("prefLabel", "altLabel", "definition"), spec)}
        result = {"iri": x, "before": before, "after": after}
        files = sorted(set(removed) | set(added))
        edits = {f: writer.rewrite_blocks(ws.text(f), removed.get(f, set()), adds.get(f, {})) for f in files}
        return {"result": result, "edits": edits, "removed": removed, "added": added}

    return build


def model_set_labels(cfg, iri, prefLabel=UNSET, altLabel=UNSET, definition=UNSET, dryRun=False, repo=None, **extra):
    _no_extra(extra)
    return writer.transaction(cfg, repo, set_labels_build(iri, prefLabel, altLabel, definition), dryRun)


# ---------------------------------------------------------------- §5.5

DETACH = {core.ARCH + "inView"} | {core.NS["bpmn"] + p for p in ("flowElements", "flowNodeRefs", "lanes", "laneSets")}
NOT_REMOVABLE = {core.ARCH + "Model"}


def _kind(ctx, st, iri):
    preds = {t.predicate.value for _, t in st.get(iri, ())}
    if SOURCE in preds and TARGET in preds:
        return "relationship"
    if any({core.ARCH + "Diagram", core.ARCH + "Catalog", core.ARCH + "Matrix"} & set(ctx.ancestors(t.object.value))
           for _, t in st.get(iri, ()) if t.predicate.value == core.A):
        return "view"
    return "element"


def remove_plan(ctx, st, target):
    """§5.5 steps 1-4 on the SOURCE graph: (delete entries, detach entries, blockers, triples to remove per file)."""
    model_iri = next(t.object.value for _, t in st[target] if t.predicate.value == IN_MODEL)
    mdir = f"models/{model_iri[len(core.MODEL_BASE):].strip('/')}/"
    D, reason = [target], {target: "target"}
    blockers = {}

    def block(s, p, f, why):
        blockers.setdefault((s, p, f), why)
    changed = True
    while changed:  # step 2: relationship closure (relationships pointing to relationships included)
        changed = False
        for r, ts in sorted(st.items()):
            if r in reason:
                continue
            ends = [(f, t) for f, t in ts if t.predicate.value in (SOURCE, TARGET) and t.object.value in reason]
            if not ends:
                continue
            r_model = next((t.object.value for _, t in ts if t.predicate.value == IN_MODEL), None)
            if r_model == model_iri:
                D.append(r)
                reason[r] = "endpoint"
                changed = True
            else:
                for f, t in ends:
                    block(r, t.predicate.value, f, "cross-model-relationship")
    remove, detach = {}, []
    for d in D:  # step 3: the members' own triples, only inside the target's model directory
        for f, t in st.get(d, ()):
            if f.startswith(mdir):
                remove.setdefault(f, set()).add((d, t.predicate.value, t.object))
            else:
                block(d, t.predicate.value, f, "other-model-subject")
    members = set(D)
    for s, ts in sorted(st.items()):  # step 4: external references to D
        if s in members:
            continue
        for f, t in ts:
            if not (isinstance(t.object, ox.NamedNode) and t.object.value in members):
                continue
            p = t.predicate.value
            if not f.startswith(mdir):
                block(s, p, f, "other-model")
            elif p in DETACH:
                detach.append({"subject": s, "predicate": core.short(p), "object": t.object.value, "file": f})
                remove.setdefault(f, set()).add((s, p, t.object))
            else:
                block(s, p, f, "referenced")
    for f, qs in ctx.src_quads.items():  # blank-node references to D are not handled automatically
        for q in qs:
            if isinstance(q.subject, ox.BlankNode) and isinstance(q.object, ox.NamedNode) and q.object.value in members:
                block(str(q.subject), q.predicate.value, ctx.rel(f), "referenced")
    delete = sorted(({"iri": d, "kind": _kind(ctx, st, d), "reason": reason[d]} for d in D), key=lambda e: e["iri"])
    plan = {"delete": delete, "detach": sorted(detach, key=lambda e: (e["subject"], e["predicate"], e["object"])),
            "blockers": [{"subject": s, "predicate": core.short(p), "file": f, "reason": why}
                         for (s, p, f), why in sorted(blockers.items())]}
    return plan, remove


def plan_digest(target, plan, files):
    """sha256 over the target, the plan and the current bytes of every file the plan touches: any later change to
    those files (even a comment) makes an old digest stale (T18)."""
    import hashlib, json
    return "sha256:" + hashlib.sha256(json.dumps({"target": target, "plan": plan, "files": files}, sort_keys=True,
                                                 ensure_ascii=False).encode()).hexdigest()


def remove_build(iri, cascade=False, dryRun=False, planDigest=None, verify_digest=True):
    """The plan function of model_remove. verify_digest=False (aisep.actions, which binds its own digest over the
    whole action) skips the PLAN_STALE comparison; planDigest then only marks a replay (alreadyAbsent)."""

    def build(ws, ctx):
        st = _subject_triples(ctx)
        try:
            target = core.expand(ctx, iri)
        except AisepError:
            target = iri
        if target not in st:
            if planDigest is not None:  # the delete already happened (response lost, replayed)
                return {"result": {"target": target, "plan": None, "planDigest": planDigest, "written": False,
                                   "alreadyAbsent": True}, "edits": {}}
            from aisep.tools import _candidates
            raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(target)} 不存在", hint="从 details.candidates 里选",
                             details={"candidates": _candidates(ctx, target)})
        types = {t.object.value for _, t in st[target] if t.predicate.value == core.A}
        if any((PROTECTED_TYPES | NOT_REMOVABLE) & set(ctx.ancestors(c)) for c in types):
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(target)} 是批准记录、AI 活动或模型本身，不能删除")
        if not any(t.predicate.value == IN_MODEL for _, t in st[target]):
            raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(target)} 不是模型成员")
        plan, remove = remove_plan(ctx, st, target)
        digest = plan_digest(target, plan, {f: writer.sha(ws.data.get(f)) for f in sorted(remove)})
        details = {"plan": plan, "planDigest": digest}
        if verify_digest and planDigest is not None and planDigest != digest:
            raise AisepError("PLAN_STALE", "计划已变化（文件在 dryRun 之后被改过）", hint="先用 dryRun: true 取新计划",
                             details=details)
        if plan["blockers"]:
            raise AisepError("REFERENCED", f"{core.short(target)} 被 {len(plan['blockers'])} 处引用，不能删除",
                             hint="改用 owl:deprecated true + dcterms:isReplacedBy 退役，元素会推导为 Superseded（§6.6、§7.2）",
                             details=details)
        if not cascade and (len(plan["delete"]) > 1 or plan["detach"]):
            raise AisepError("CASCADE_REQUIRED", f"删除 {core.short(target)} 会连带 {len(plan['delete']) - 1} 个关系、"
                             f"摘除 {len(plan['detach'])} 条成员关系", hint="确认后传 cascade: true 和 planDigest",
                             details=details)
        if any(isinstance(o, ox.BlankNode) for rs in remove.values() for _, _, o in rs):
            raise AisepError("EDIT_UNSAFE", "要删的三元组挂着空白节点，不自动删除，请手工编辑", details=details)
        edits = {f: writer.rewrite_blocks(ws.text(f), rs, {}) for f, rs in sorted(remove.items())}
        return {"result": {"target": target, "plan": plan, "planDigest": digest, "written": not dryRun,
                           "alreadyAbsent": False},
                "edits": edits, "removed": remove}

    return build


def model_remove(cfg, iri, cascade=False, dryRun=False, planDigest=None, repo=None, **extra):
    _no_extra(extra)
    return writer.transaction(cfg, repo, remove_build(iri, cascade, dryRun, planDigest), dryRun)


# ---------------------------------------------------------------- §5.12

_USE_LABELS = "名称、英文名、定义请用 model_set_labels"
_NEW_REL = "关系端点不能改（改端点 = 删掉旧关系、新建一个）"
NOT_SETTABLE = {RDF_TYPE: "类型不能改（改类型不在本版）", IN_MODEL: "所属模型不能改", SOURCE: _NEW_REL, TARGET: _NEW_REL,
                PREF: _USE_LABELS, ALT: _USE_LABELS, DEF: _USE_LABELS}
XSD_STRING = core.NS["xsd"] + "string"


def _attr_value(o):
    """A term in the shape of the `value` argument: {iri} or {value, lang?, datatype?} (a blank node: {bnode})."""
    if isinstance(o, ox.NamedNode):
        return {"iri": o.value}
    if isinstance(o, ox.BlankNode):
        return {"bnode": o.value}
    if o.language:
        return {"value": o.value, "lang": o.language}
    return {"value": o.value} if o.datatype.value == XSD_STRING else {"value": o.value, "datatype": o.datatype.value}


def _attr_values(objects):
    return sorted((_attr_value(o) for o in objects), key=lambda v: sorted(v.items()))


def _settable(ctx, name, field):
    try:
        p = core.expand(ctx, name)
    except AisepError as e:
        raise _bad(field, f"{field} 里有不合法的 IRI 或前缀名：{e.message}") from None
    if p in NOT_SETTABLE:
        raise _bad(field, f"{field} 不能含 {core.short(p)}：{NOT_SETTABLE[p]}")
    return p


def set_attributes_build(iri, set=None, unset=None):
    """The plan function of model_set_attributes."""
    return _set_attributes_build(iri, set, unset)


def _set_attributes_build(iri, new, drop):  # not set/unset: the body uses the builtin set()
    if not new and not drop:
        raise AisepError("INVALID_ARGUMENT", "set、unset 至少给一个，且不能都为空", details={"rejectedFields": ["set", "unset"]})
    for field, v in (("set", new), ("unset", drop)):
        if v is not None and not isinstance(v, list):
            raise _bad(field, f"{field} 须为数组")

    def build(ws, ctx):
        want = {}  # predicate IRI -> the complete list of its new values ([] = unset), in argument order
        for a in new or ():
            if not isinstance(a, dict) or set(a) != {"predicate", "value"} or not isinstance(a["value"], dict):
                raise _bad("set", "set 每项须为 {predicate, value}")
            p, v = _settable(ctx, a["predicate"], "set"), a["value"]
            try:  # pyoxigraph rejects a bad IRI, language tag or non-string value with ValueError/TypeError
                if set(v) == {"iri"}:
                    o = ox.NamedNode(core.expand(ctx, v["iri"]))
                elif "value" in v and set(v) <= {"value", "datatype", "lang"}:
                    o = ox.Literal(v["value"], language=v.get("lang")) if v.get("lang") else \
                        ox.Literal(v["value"], datatype=ox.NamedNode(core.expand(ctx, v["datatype"]))) if v.get("datatype") else \
                        ox.Literal(v["value"])
                else:
                    raise _bad("set", "set 的 value 须为 {iri} 或 {value, datatype?, lang?}")
            except (ValueError, TypeError) as e:
                raise _bad("set", f"set 里有不合法的 IRI、语言标签或值：{e}") from None
            except AisepError as e:  # core.expand refused an IRI or prefix (its own error names no field)
                if "rejectedFields" in e.details:
                    raise
                raise _bad("set", f"set 里有不合法的 IRI 或前缀名：{e.message}") from None
            if o not in want.setdefault(p, []):
                want[p].append(o)
        for name in drop or ():
            p = _settable(ctx, name, "unset")
            if want.get(p):
                raise AisepError("INVALID_ARGUMENT", f"{core.short(p)} 同时出现在 set 和 unset 里",
                                 details={"rejectedFields": ["set", "unset"]})
            want[p] = []
        st = _subject_triples(ctx)
        try:
            x = core.expand(ctx, iri)
        except AisepError:
            x = iri
        types = {t.object.value for _, t in st.get(x, ()) if t.predicate.value == core.A}
        if any(NOT_REMOVABLE & set(ctx.ancestors(c)) for c in types):  # the model resource is not a member of itself
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 是模型本身，不经写工具修改")
        x = _member(ctx, st, iri, "iri")
        if any(PROTECTED_TYPES & set(ctx.ancestors(c)) for c in types):
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 是批准记录或 AI 活动，只追加不修改",
                             hint="改结论请写一条更晚的批准记录")
        mslug = next(t.object.value for _, t in st[x] if t.predicate.value == IN_MODEL)[len(core.MODEL_BASE):].strip("/")
        outside = sorted({f for f, _ in st[x] if not f.startswith(f"models/{mslug}/")})
        if outside:
            raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 的三元组有一部分在别的模型目录里，不改别人的模型",
                             details={"files": outside})
        type_file = _type_file(st, x)
        before, after, removed, added, adds = {}, {}, {}, {}, {}
        for p, objs in want.items():
            old = [(f, t) for f, t in st[x] if t.predicate.value == p]
            have = {t.object for _, t in old}
            before[p], after[p] = _attr_values(have), _attr_values(objs)
            gone = [(f, t) for f, t in old if t.object not in objs]  # values that stay are left where they are
            if any(isinstance(t.object, ox.BlankNode) for _, t in gone):  # a fresh parse relabels it: the plan could not name it
                raise AisepError("EDIT_UNSAFE", f"{core.short(p)} 的现有值是空白节点，不自动改写，请手工编辑")
            for f, t in gone:
                removed.setdefault(f, set()).add((x, p, t.object))
            f = gone[0][0] if gone else type_file  # a file where rewrite_blocks finds a statement of x to put them in
            for o in objs:
                if o not in have:
                    nt = ox.Triple(ox.NamedNode(x), ox.NamedNode(p), o)
                    added.setdefault(f, []).append(nt)
                    adds.setdefault(f, {}).setdefault(x, []).append((nt.predicate, nt.object))
        files = sorted(set(removed) | set(added))
        edits = {f: writer.rewrite_blocks(ws.text(f), removed.get(f, set()), adds.get(f, {})) for f in files}
        for f, ts in added.items():  # writer.term leaves U+000D raw, which a short string may not hold: escape it here
            for body in {writer.term(ox.Literal(t.object.value), {}) for t in ts
                         if isinstance(t.object, ox.Literal) and "\r" in t.object.value}:
                edits[f] = edits[f].replace(body, body.replace("\r", "\\r"))  # step 6 (graph equivalence) still judges it
        return {"result": {"iri": x, "before": before, "after": after}, "edits": edits, "removed": removed, "added": added}

    return build


def model_set_attributes(cfg, iri, set=None, unset=None, dryRun=False, repo=None, **extra):
    """Replace, per predicate, ALL values the subject has on it (`set`) or drop them (`unset`). Which predicates are
    legal is decided by L1 on the candidate graph (closed world, hand-written approvalState), not by a list here."""
    _no_extra(extra)
    return writer.transaction(cfg, repo, set_attributes_build(iri, set, unset), dryRun)
