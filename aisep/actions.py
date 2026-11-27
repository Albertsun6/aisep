"""Action catalogue (docs/mcp-interface.md §5.13, §5.14): model_list_actions, model_apply_action.

An action is an aisep:ActionType defined in RDF in modules/ext-actions/catalog.ttl (vocabulary in onto.ttl, L3 shapes
EA1-EA11 in shapes.ttl): parameters (sh:parameter), an ordered rdf:List of steps each invoking one of the closed set
of basic actions below (the plan functions of the existing write tools), plus hint-level guards
(sh:SPARQLAskValidator, ASK true = pass). This module only reads the catalogue, re-checks every definition on its own
(X1-X10: it cannot assume `gate` ran), validates the parameters, resolves step arguments, runs the steps' plan
functions one after another on an in-memory overlay of the workspace and hands the merged plan to ONE
writer.transaction. Legality is whatever that transaction's L0-L2 judgement of the candidate graph says; nothing here
defines what a legal model is. Guards are advice (PRECONDITION_FAILED), not invariants: a direct edit is not bound by
them and `gate` does not know them. No state is kept: no execution record, no log, no git add, no commit."""
import copy, hashlib, json, os, re

import jsonschema
import pyoxigraph as ox
from rdflib import Graph
from rdflib.compare import to_canonical_graph

from aisep import calllog, core, gitio, querybox, tools, write_tools, writer
from aisep.errors import AisepError

CATALOG = "modules/ext-actions/catalog.ttl"  # relative to the served worktree, next to the modules it loads
MANIFEST = "metamodel.ttl"  # in the catalogue's directory; its owl:versionInfo is the catalogVersion
CATALOG_PATH = None  # when set (tests), this file is read instead of <worktree>/modules/ext-actions/catalog.ttl

RDF, SH, XSD, SKOS = core.NS["rdf"], core.NS["sh"], core.NS["xsd"], core.NS["skos"]
AI, A, NIL = core.AISEP, core.A, core.NS["rdf"] + "nil"
DCT_ID, VERSION = core.NS["dcterms"] + "identifier", core.NS["owl"] + "versionInfo"
XSD_STRING = XSD + "string"
GUARD_TIMEOUT_S = tools.QUERY_TIMEOUT_MS / 1000  # per guard; a badly written ASK (e.g. a cartesian product) must not hang


def _op(tool, build, scalar, lists, required, yields, modifies):
    return {"tool": tool, "build": build, "scalar": set(scalar), "lists": set(lists), "required": set(required),
            "yields": yields, "modifies": modifies}


# the closed set of basic actions (onto.ttl declares the same five individuals, shapes.ttl EA6 lists them in sh:in):
# plan function, scalar / list arguments, required arguments, whether the step yields an IRI, whether its `iri`
# argument names an EXISTING resource it changes
OPS = {
    AI + "BasicAddElement": _op("model_add_element", write_tools.add_element_build,
                                ("model", "type", "prefLabel", "altLabel", "slug", "definition", "file"), ("attributes",),
                                ("model", "type", "prefLabel"), True, False),
    AI + "BasicAddRelationship": _op("model_add_relationship", write_tools.add_relationship_build,
                                     ("type", "source", "target", "model", "file"), (), ("type", "source", "target"),
                                     True, False),
    AI + "BasicSetLabels": _op("model_set_labels", write_tools.set_labels_build,
                               ("iri", "prefLabel", "altLabel", "definition"), (), ("iri",), True, True),
    AI + "BasicSetAttributes": _op("model_set_attributes", write_tools.set_attributes_build, ("iri",), ("set", "unset"),
                                   ("iri",), True, True),
    AI + "BasicRemove": _op("model_remove", write_tools.remove_build, ("iri",), (), ("iri",), False, True),
}
DESTRUCTIVE_OPS = {AI + "BasicRemove"}  # derived by the executor; the catalogue has no field that could lower it
ITEM_LISTS = {"attributes", "set"}  # list arguments whose items are {predicate, value}; `unset` items are predicates

ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")  # \Z, not $: $ also matches before a trailing newline (#77)
ACTION_IRI_RE = re.compile(re.escape(AI) + r"Action[A-Z][A-Za-z0-9]*\Z")
SEMVER_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")
VAR_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
# an IRI parameter is a full IRI of a model member: https://aisep.example/model/<slug>/<local name>
IRI_RE = re.compile(re.escape(core.MODEL_BASE) + r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9._~%-]+")
IMPACT_DEPTH, IMPACT_ITEMS = 3, 50
MISSING = object()

# predicates each node may carry (rdf:type is free on the nodes SHACL leaves open to it)
ACTION_KEYS = {A, DCT_ID, SKOS + "prefLabel", SKOS + "definition", VERSION, SH + "parameter", AI + "guard", AI + "steps"}
STEP_KEYS = {A, DCT_ID, AI + "invokes", AI + "binding"}
SOURCES = {AI + "constant": "const", AI + "fromParameter": "param", AI + "fromStep": "step", AI + "modelOf": "modelOf"}
BINDING_KEYS = {A, AI + "argument", AI + "attributePredicate"} | set(SOURCES)
PARAM_KEYS = {A, SH + "path", SH + "datatype", SH + "nodeKind", SH + "optional", SH + "description"}
GUARD_KEYS = {A, DCT_ID, SH + "ask", SH + "message"}


# ---------------------------------------------------------------- reading the catalogue

class _Graph:
    """subject -> [(predicate IRI, object term)] of one parse of the catalogue file."""

    def __init__(self, quads):
        self.out = {}
        for q in quads:
            self.out.setdefault(q.subject, []).append((q.predicate.value, q.object))

    def vals(self, n, p):
        return [o for pp, o in self.out.get(n, ()) if pp == p]

    def keys(self, n):
        return {p for p, _ in self.out.get(n, ())}

    def closure(self, n):
        """n and every blank node reachable from it through objects (list nodes included)."""
        seen, todo = [], [n]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.append(x)
            todo += [o for _, o in self.out.get(x, ()) if isinstance(o, ox.BlankNode)]
        return seen


def _is_str(t):
    return isinstance(t, ox.Literal) and not t.language and t.datatype.value == XSD_STRING


def _is_zh(t):
    return isinstance(t, ox.Literal) and bool(t.language) and (t.language == "zh" or t.language.startswith("zh-"))


def _show(t):
    return core.short(t.value) if isinstance(t, ox.NamedNode) else str(t)


def _closed(g, n, allowed, where, rule, P):
    extra = sorted(g.keys(n) - allowed)
    if extra:
        P.append(f"{rule} {where}：不认识的谓词 {', '.join(core.short(p) for p in extra)}")


def _ident(g, n, where, rule, P):
    vs = g.vals(n, DCT_ID)
    if len(vs) != 1 or not _is_str(vs[0]) or not ID_RE.match(vs[0].value):
        P.append(f"{rule} {where}：须恰好一个 dcterms:identifier，匹配 ^[a-z][a-z0-9-]{{0,63}} 且到此为止（不含换行）")
        return None
    return vs[0].value


def _param(g, n, P):
    where = f"参数 {_show(n)}"
    if not isinstance(n, ox.BlankNode):
        P.append(f"EA8 {where}：参数须为空白节点")
        return None
    _closed(g, n, PARAM_KEYS, where, "EA8", P)
    paths, dts, nks = g.vals(n, SH + "path"), g.vals(n, SH + "datatype"), g.vals(n, SH + "nodeKind")
    opts, descs = g.vals(n, SH + "optional"), g.vals(n, SH + "description")
    bad = len(paths) != 1 or not isinstance(paths[0], ox.NamedNode)
    bad |= (len(dts), len(nks)) not in ((1, 0), (0, 1))
    bad |= any(t.value != XSD_STRING for t in dts) or any(t.value != SH + "IRI" for t in nks)
    bad |= len(opts) > 1 or any(not isinstance(t, ox.Literal) or t.datatype.value != XSD + "boolean"
                                or t.value not in ("true", "false", "1", "0") for t in opts)
    bad |= len(descs) > 1 or not all(_is_zh(t) for t in descs)
    if bad:
        P.append(f"EA8 {where}：须恰好一个 IRI 形式的 sh:path；sh:datatype xsd:string 与 sh:nodeKind sh:IRI 恰好一个；"
                 "sh:optional 至多一个布尔值；sh:description 至多一个 @zh")
        return None
    name = re.split(r"[#/]", paths[0].value)[-1]
    if not VAR_RE.match(name):
        P.append(f"X7 {where}：参数名（sh:path 的本地名）{name!r} 须为合法的变量名 [A-Za-z_][A-Za-z0-9_]*")
        return None
    return {"name": name, "path": paths[0].value, "iri": bool(nks),
            "optional": bool(opts) and opts[0].value in ("true", "1"),
            "description": descs[0].value if descs else ""}


def _guard(g, n, params, P):
    where = f"guard {_show(n)}"
    if not isinstance(n, ox.BlankNode) or ox.NamedNode(SH + "SPARQLAskValidator") not in g.vals(n, A):
        P.append(f"EA9 {where}：guard 须为类型 sh:SPARQLAskValidator 的空白节点")
        return None
    _closed(g, n, GUARD_KEYS, where, "EA9", P)
    gid = _ident(g, n, where, "EA9", P)
    asks, msgs = g.vals(n, SH + "ask"), g.vals(n, SH + "message")
    if len(asks) != 1 or not _is_str(asks[0]) or len(msgs) != 1 or not _is_zh(msgs[0]):
        P.append(f"EA9 {where}：须恰好一个字符串 sh:ask 和一个 @zh 的 sh:message")
        return None
    if gid is None:
        return None
    ask, where = asks[0].value, f"guard {gid}"
    if not re.match(r"\s*ASK\b", ask) or re.search(r"\bSERVICE\b", ask, re.I):
        P.append(f"X8 {where}：只能是只读的 SPARQL ASK（不带 PREFIX 声明，不许 SERVICE）")
        return None
    names = sorted({m for m in re.findall(r"[?$]([A-Za-z_][A-Za-z0-9_]*)", ask) if m in params})
    try:  # syntax, and every pre-bound parameter must be in scope (pyoxigraph refuses it otherwise)
        ox.Store().query(core.SPARQL_PREFIXES + ask, use_default_graph_as_union=True,
                         substitutions={ox.Variable(v): ox.NamedNode("urn:aisep:probe") if params[v]["iri"]
                                        else ox.Literal("probe") for v in names})
    except (SyntaxError, ValueError, RuntimeError, OSError) as e:
        P.append(f"X8 {where}：查询不能执行：{str(e)[:200]}")
        return None
    return {"id": gid, "ask": ask, "hint": msgs[0].value, "vars": names}


def _members(g, head, P):
    """The members of a well-formed rdf:List (X2); None when it is not one."""
    out, seen, n = [], [], head
    while n != ox.NamedNode(NIL):
        if not isinstance(n, ox.BlankNode) or n in seen or g.keys(n) != {RDF + "first", RDF + "rest"} \
                or len(g.vals(n, RDF + "first")) != 1 or len(g.vals(n, RDF + "rest")) != 1:
            P.append("X2 aisep:steps 不是良构的表（每个表节点恰好一个 rdf:first、一个 rdf:rest，以 rdf:nil 结尾，无环）")
            return None
        seen.append(n)
        out.append(g.vals(n, RDF + "first")[0])
        n = g.vals(n, RDF + "rest")[0]
    if len(set(out)) != len(out):
        P.append("X2 aisep:steps 的成员有重复")
        return None
    return out


def _binding(g, n, where, P):
    if not isinstance(n, ox.BlankNode):
        P.append(f"EA7 {where}：绑定须为空白节点")
        return None
    _closed(g, n, BINDING_KEYS, where, "EA7", P)
    args, preds = g.vals(n, AI + "argument"), g.vals(n, AI + "attributePredicate")
    srcs = [(SOURCES[p], o) for p, o in g.out.get(n, ()) if p in SOURCES]
    if len(args) != 1 or not _is_str(args[0]) or len(srcs) != 1 or len(preds) > 1 \
            or any(not isinstance(t, ox.NamedNode) for t in preds):
        P.append(f"EA7 {where}：绑定须恰好一个字符串 aisep:argument、恰好一个取值来源"
                 "（aisep:constant / fromParameter / fromStep / modelOf），aisep:attributePredicate 至多一个 IRI")
        return None
    kind, o = srcs[0]
    if (kind == "const" and isinstance(o, ox.BlankNode)) or (kind in ("param", "modelOf") and not isinstance(o, ox.NamedNode)):
        P.append(f"EA7 {where}：aisep:constant 须为 IRI 或字面量，aisep:fromParameter / modelOf 须为参数的 sh:path IRI")
        return None
    return {"arg": args[0].value, "pred": preds[0].value if preds else None, "kind": kind, "obj": o}


def _steps(g, members, params, P):
    """Steps with resolved bindings: {id, op, scalar: {arg: src}, lists: {arg: [(predicate, src)]}} (EA5-EA7, X3-X5)."""
    by_path = {p["path"]: p for p in params.values()}
    out, ids, earlier = [], [], {}  # earlier: step node -> step id, for the steps before the current one that yield
    for m in members:
        where = f"步骤 {_show(m)}"
        if not isinstance(m, ox.BlankNode) or ox.NamedNode(AI + "ActionStep") not in g.vals(m, A):
            P.append(f"EA5 {where}：表成员须为类型 aisep:ActionStep 的空白节点")
            return None
        _closed(g, m, STEP_KEYS, where, "EA6", P)
        sid = _ident(g, m, where, "EA6", P)
        inv = g.vals(m, AI + "invokes")
        if len(inv) != 1 or not isinstance(inv[0], ox.NamedNode) or inv[0].value not in OPS:
            P.append(f"EA6 {where}：须恰好调用一个基本动作（{', '.join(core.short(o) for o in sorted(OPS))}），"
                     f"现为 {', '.join(_show(t) for t in inv) or '无'}")
            return None
        if sid is None:
            return None
        where, op = f"步骤 {sid}", OPS[inv[0].value]
        if sid in ids:
            P.append(f"X9 步骤 id 重复：{sid}")
        ids.append(sid)
        scalar, lists = {}, {}
        for b in sorted(g.vals(m, AI + "binding"), key=str):
            b = _binding(g, b, where, P)
            if b is None:
                continue
            arg, kind, o = b["arg"], b["kind"], b["obj"]
            if kind in ("param", "modelOf"):
                if o.value not in by_path:
                    P.append(f"X4 {where}.{arg}：引用了本动作没有声明的参数 {core.short(o.value)}")
                    continue
                p = by_path[o.value]
                if kind == "modelOf" and not p["iri"]:
                    P.append(f"X4 {where}.{arg}：aisep:modelOf 只能指向 IRI 参数，{p['name']} 不是")
                    continue
                src = (kind, p["name"])
            elif kind == "step":
                if o not in earlier:
                    P.append(f"X5 {where}.{arg}：aisep:fromStep 只能指向本动作里排在前面、且产出 IRI 的步骤")
                    continue
                src = ("step", earlier[o])
            else:
                src = ("const", o)
            if arg in op["scalar"]:
                if b["pred"] is not None or arg in scalar:
                    P.append(f"X3 {where}.{arg}：标量入参只能有一个绑定，且不能带 aisep:attributePredicate")
                elif kind == "const" and isinstance(o, ox.Literal) and not _is_str(o):
                    P.append(f"X3 {where}.{arg}：标量入参的常量只能是 IRI 或普通字符串字面量")
                else:
                    scalar[arg] = src
            elif arg in ITEM_LISTS & op["lists"]:
                if b["pred"] is None or kind == "modelOf":
                    P.append(f"X3 {where}.{arg}：每项须带 aisep:attributePredicate，取值不能用 aisep:modelOf")
                else:
                    lists.setdefault(arg, []).append((b["pred"], src))
            elif arg in op["lists"]:  # unset: a list of predicates
                if b["pred"] is not None or kind != "const" or not isinstance(o, ox.NamedNode):
                    P.append(f"X3 {where}.{arg}：每项只能是 aisep:constant <谓词 IRI>")
                else:
                    lists.setdefault(arg, []).append((None, src))
            else:
                P.append(f"X3 {where}：{op['tool']} 没有入参 {arg!r}（只认 {', '.join(sorted(op['scalar'] | op['lists']))}）")
        for a in sorted(op["required"] - set(scalar)):
            P.append(f"X3 {where}：{op['tool']} 缺必填入参 {a!r}")
        if inv[0].value == AI + "BasicSetAttributes" and not lists:
            P.append(f"X3 {where}：model_set_attributes 的 set、unset 至少绑定一项")
        out.append({"id": sid, "op": inv[0].value, "scalar": scalar, "lists": lists})
        if op["yields"]:
            earlier[m] = sid
    return out


def _overlap_problems(steps):
    """X6. Two steps acting on the same IRI make a replay fail (a step is then no longer a no-op: PLAN_STALE,
    PLAN_REQUIRED, IRI_EXISTS, ELEMENT_NOT_FOUND), so the catalogue may not hold such an action. Decided on the
    bindings alone: a set_labels / set_attributes / remove step on what an earlier step of the same action created
    (aisep:fromStep); two such steps naming the same parameter or constant; a remove step naming the same parameter /
    constant as an end of an add_relationship step (the cascade deletes that relationship). Two DIFFERENT parameters
    the caller sets to the same IRI, or an add_element whose slug equals a removed IRI, depend on run-time values and
    are not caught here."""
    def key(src):
        return None if src is None or src[0] == "modelOf" else (src[0], str(src[1]))

    problems, touched = [], {}
    for s in steps:
        if not OPS[s["op"]]["modifies"]:
            continue
        k = key(s["scalar"].get("iri"))
        if k is None:
            continue
        if k[0] == "step":
            problems.append(f"X6 步骤 {s['id']}：{OPS[s['op']]['tool']} 作用于本动作里前一步新建或改过的资源（{k[1]}），重放会被拒")
        elif k in touched:
            problems.append(f"X6 步骤 {s['id']} 与步骤 {touched[k]} 作用于同一个目标 IRI，重放会被拒")
        else:
            touched[k] = s["id"]
    for r in steps:
        k = key(r["scalar"].get("iri")) if r["op"] in DESTRUCTIVE_OPS else None
        if k is None or k[0] == "step":
            continue
        for a in steps:
            if a["op"] == AI + "BasicAddRelationship" and k in (key(a["scalar"].get("source")), key(a["scalar"].get("target"))):
                problems.append(f"X6 步骤 {r['id']} 删除的资源是步骤 {a['id']} 新增关系的端点，级联会删掉它，重放会被拒")
    return problems


def _definition(g, a):
    """(definition, problems) of one aisep:ActionType subject (X1 = the EA rules again, X2-X9)."""
    P = []
    if not isinstance(a, ox.NamedNode) or not ACTION_IRI_RE.match(a.value):
        P.append(f"EA1 动作 {_show(a)}：须为形如 aisep:Action<驼峰名> 的 IRI")
    _closed(g, a, ACTION_KEYS, "动作", "EA1", P)
    other = sorted(_show(t) for t in g.vals(a, A) if t != ox.NamedNode(AI + "ActionType"))
    if other:
        P.append(f"EA11 动作：只能是 aisep:ActionType，不能另带类型 {', '.join(other)}")
    aid = _ident(g, a, "动作", "EA2", P)
    titles, defs, vers = g.vals(a, SKOS + "prefLabel"), g.vals(a, SKOS + "definition"), g.vals(a, VERSION)
    if len(titles) != 1 or not _is_zh(titles[0]) or len(defs) > 1 or not all(_is_zh(t) for t in defs):
        P.append("EA3 动作：skos:prefLabel 须恰好一个 @zh，skos:definition 至多一个 @zh")
    if len(vers) != 1 or not _is_str(vers[0]) or not SEMVER_RE.match(vers[0].value):
        P.append("EA4 动作：须恰好一个 owl:versionInfo，形如 <主>.<次>.<修订>")
    params = {}
    for n in sorted(g.vals(a, SH + "parameter"), key=str):
        p = _param(g, n, P)
        if p is None:
            continue
        if p["name"] in params:
            P.append(f"X7 参数名重复：{p['name']}")
        params[p["name"]] = p
    guards = [x for x in (_guard(g, n, params, P) for n in sorted(g.vals(a, AI + "guard"), key=str)) if x is not None]
    gids = [x["id"] for x in guards]
    P += [f"X9 guard id 重复：{i}" for i in sorted({i for i in gids if gids.count(i) > 1})]
    heads, steps = g.vals(a, AI + "steps"), None
    if len(heads) != 1 or heads[0] == ox.NamedNode(NIL):
        P.append("EA5 动作：须恰好一个非空的 aisep:steps 表")
    else:
        members = _members(g, heads[0], P)
        if members is not None:
            steps = _steps(g, members, params, P)
    if steps is not None:
        P += _overlap_problems(steps)
    d = {"iri": a.value if isinstance(a, ox.NamedNode) else None, "id": aid,
         "title": titles[0].value if titles else None, "description": defs[0].value if defs else "",
         "version": vers[0].value if vers else None,
         "params": sorted(params.values(), key=lambda p: p["name"]), "guards": sorted(guards, key=lambda x: x["id"]),
         "steps": steps}
    return d, P


def definition_digest(g, a):
    """sha256 over the closed description of the action: its own triples plus those of every blank node reachable
    from it (list nodes included), blank nodes canonicalised, N-Triples lines sorted. IRI objects are not followed, so
    relabelling a basic action in onto.ttl does not make a dryRun stale."""
    ts = [ox.Triple(n, ox.NamedNode(p), o) for n in g.closure(a) for p, o in g.out.get(n, ())]
    rg = Graph().parse(data=ox.serialize(ts, format=ox.RdfFormat.N_TRIPLES).decode("utf-8"), format="nt")
    lines = sorted(to_canonical_graph(rg).serialize(format="nt").strip().splitlines())
    return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _catalog_path(cfg):
    """The catalogue both tools read: always the served worktree's (the server's --repo, cwd by default), never the
    worktree a call's `repo` names. A definition edited in an unmerged worktree must not take effect there before it
    went through a PR, and model_apply_action must run exactly what model_list_actions lists (#160)."""
    if CATALOG_PATH:
        return CATALOG_PATH
    return os.path.join(gitio.locate_repo(None, cfg.allow_roots, cfg.repo), CATALOG)


def load_catalog(path):
    """([(definition, problems)] sorted by IRI, catalogVersion), read from disk on every call (no cache: a changed
    definition takes effect at once and makes older planDigests stale). An entry with problems is listed as invalid
    and cannot be applied; one bad definition never makes the others unusable. No catalogue file -> no actions."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        return [], None
    rel = CATALOG if CATALOG_PATH is None else os.path.basename(path)
    try:
        quads = list(ox.parse(input=data, format=core.TTL))
    except (SyntaxError, ValueError) as e:
        raise AisepError("PARSE_FAILED", f"动作目录 {rel} 不能解析：{str(e)[:200]}", hint="先修好这个文件（gate 同样会报）",
                         details={"file": rel, "error": str(e)[:200]}) from None
    g = _Graph(quads)
    version = None
    try:
        mq = ox.parse(path=os.path.join(os.path.dirname(path), MANIFEST), format=core.TTL)
        version = next((q.object.value for q in mq if q.predicate.value == VERSION
                        and q.subject.value.startswith("https://aisep.example/module/")), None)
    except (OSError, SyntaxError, ValueError):
        pass
    subjects = sorted({s for s, ps in g.out.items() if (A, ox.NamedNode(AI + "ActionType")) in ps},
                      key=lambda s: (not isinstance(s, ox.NamedNode), s.value if isinstance(s, ox.NamedNode) else str(s)))
    out = []
    for a in subjects:  # each definition is checked on its own: an exception marks only this one invalid
        try:
            d, problems = _definition(g, a)
            if not problems:
                d["definitionDigest"] = definition_digest(g, a)
        except Exception as e:  # noqa: BLE001 — a definition shape the checks above did not foresee
            d = {"iri": a.value if isinstance(a, ox.NamedNode) else None, "id": None}
            ids = g.vals(a, DCT_ID)
            if len(ids) == 1 and isinstance(ids[0], ox.Literal):
                d["id"] = ids[0].value
            problems = [f"定义校验出错：{type(e).__name__}: {str(e)[:200]}"]
        out.append((d, problems))
    ids = [d.get("id") for d, _ in out]
    owner = {}  # X10: a blank node in the description of two actions
    for d_p, a in zip(out, subjects):
        for n in g.closure(a):
            if isinstance(n, ox.BlankNode):
                owner.setdefault(n, []).append(d_p)
    for (d, problems), aid in zip(out, ids):  # X9: every copy of a duplicated id is invalid, not just the later ones
        if aid is not None and ids.count(aid) > 1:
            problems.append(f"X9 动作 id 重复：{aid}")
    for n, owners in owner.items():
        if len(owners) > 1:
            for d, problems in owners:
                msg = "X10 有空白节点同时属于两个动作的定义"
                if msg not in problems:
                    problems.append(msg)
    for d, problems in out:
        if problems:
            d.pop("definitionDigest", None)
    return out, version


def _destructive(d):
    return any(s["op"] in DESTRUCTIVE_OPS for s in d["steps"])


def _schema(d):
    """The JSON Schema of the parameters, derived from sh:parameter (every parameter is a string)."""
    props = {p["name"]: dict({"type": "string"}, **({"description": p["description"]} if p["description"] else {}))
             for p in d["params"]}
    return {"type": "object", "properties": props, "required": [p["name"] for p in d["params"] if not p["optional"]],
            "additionalProperties": False}


def _iri_params(d):
    return [p["name"] for p in d["params"] if p["iri"]]


def model_list_actions(cfg, **extra):
    """Read-only: the catalogue with each action's parameter schema. The result depends on the catalogue; the tool
    list of the server does not."""
    write_tools._no_extra(extra)
    entries, version = load_catalog(_catalog_path(cfg))
    actions = []
    for d, problems in entries:
        if problems:
            actions.append({"id": d.get("id"), "iri": d.get("iri"), "valid": False, "problems": problems})
            continue
        destructive = _destructive(d)
        actions.append({"id": d["id"], "iri": d["iri"], "title": d["title"], "description": d["description"],
                        "version": d["version"], "valid": True, "params": _schema(d), "iriParams": _iri_params(d),
                        "destructive": destructive, "requiresPlanDigest": destructive,
                        "guards": [{"id": x["id"], "hint": x["hint"]} for x in d["guards"]],
                        "steps": [{"id": s["id"], "op": OPS[s["op"]]["tool"]} for s in d["steps"]],
                        "definitionDigest": d["definitionDigest"]})
    return {"catalogVersion": version, "operations": sorted(o["tool"] for o in OPS.values()), "actions": actions}


# ---------------------------------------------------------------- parameters

def _rejected(err, acc):
    if err.validator == "additionalProperties" and isinstance(err.instance, dict):
        acc.update(set(err.instance) - set(err.schema.get("properties", {})))
    elif err.validator == "required":
        acc.update(n for n in err.validator_value if n not in (err.instance or {}))
    elif err.absolute_path:
        acc.add(str(err.absolute_path[0]))
    return acc


def _check_params(d, params):
    errors = list(jsonschema.Draft202012Validator(_schema(d)).iter_errors(params))
    if errors:
        fields = set()
        for e in errors:
            _rejected(e, fields)
        raise AisepError("INVALID_ARGUMENT", f"动作 {d['id']} 的参数不合规：{errors[0].message[:200]}",
                         hint="按 model_list_actions 返回的 params schema 修改",
                         details={"rejectedFields": sorted(f"params.{f}" for f in fields)})
    for name in _iri_params(d):
        v = params.get(name)
        if v is None:
            continue
        ok = isinstance(v, str) and IRI_RE.fullmatch(v) is not None
        if ok:
            try:
                ox.NamedNode(v)
            except ValueError:
                ok = False
        if not ok:
            raise AisepError("INVALID_ARGUMENT", f"params.{name} 须为模型成员的完整 IRI（{core.MODEL_BASE}<模型>/<名>）",
                             details={"rejectedFields": [f"params.{name}"]})


def _resolve(src, iri_params, params, iris, model_of, scalar):
    """The value of one binding; MISSING when it depends on an optional parameter that was not given (the list item,
    or the whole scalar argument, is then left out). Scalars are strings; list items are {iri} / {value, ...}."""
    kind, x = src
    if kind == "const":
        if isinstance(x, ox.NamedNode):
            return x.value if scalar else {"iri": x.value}
        if scalar:
            return x.value
        if x.language:
            return {"value": x.value, "lang": x.language}
        return {"value": x.value} if x.datatype.value == XSD_STRING else {"value": x.value, "datatype": x.datatype.value}
    if kind == "param":
        v = params.get(x, MISSING)
        if v is MISSING or scalar:
            return v
        return {"iri": v} if x in iri_params else {"value": v}
    if kind == "step":
        return iris[x] if scalar else {"iri": iris[x]}
    return model_of(x)


def _args(step, iri_params, params, iris, model_of):
    args = {}
    for a, src in step["scalar"].items():
        v = _resolve(src, iri_params, params, iris, model_of, True)
        if v is not MISSING:
            args[a] = v
    for a, items in step["lists"].items():
        if a in ITEM_LISTS:
            vals = [{"predicate": p, "value": v} for p, v in
                    ((p, _resolve(src, iri_params, params, iris, model_of, False)) for p, src in items) if v is not MISSING]
            vals.sort(key=lambda i: (i["predicate"], json.dumps(i["value"], sort_keys=True, ensure_ascii=False)))
        else:  # unset
            vals = sorted(src[1].value for _, src in items)
        if vals:
            args[a] = vals
    return args


def _failed_guards(d, params, ctx):
    """Guards whose ASK is false. Parameters reach the query only as pre-bound terms ($name, substitutions), never as
    query text. A guard that uses an optional parameter that was not given is skipped. Each ASK runs in querybox's
    network-less child with a timeout (GUARD_TIMEOUT_S)."""
    failed, iri_params = [], set(_iri_params(d))
    for x in d["guards"]:
        if any(params.get(v) is None for v in x["vars"]):
            continue
        subs = {v: {"type": "iri" if v in iri_params else "literal", "value": params[v]} for v in x["vars"]}
        where = {"action": d["id"], "guard": x["id"]}
        try:
            res = querybox.run(ctx.store, core.SPARQL_PREFIXES + x["ask"], {}, 1, GUARD_TIMEOUT_S, subs)
        except querybox.Timeout:
            raise AisepError("QUERY_TIMEOUT", f"动作 {d['id']} 的前置检查 {x['id']} 超过 {GUARD_TIMEOUT_S:g} 秒，未写入",
                             hint="这条 guard 的查询写法有问题（例如笛卡尔积），要改 catalog.ttl 里的定义；原样重试没有用",
                             details=where, retryable=False) from None
        except querybox.NetworkAttempt:
            raise AisepError("QUERY_NOT_READONLY", f"动作 {d['id']} 的前置检查 {x['id']} 试图访问外部端点，执行它的进程已被终止",
                             details=where) from None
        except querybox.Unavailable as e:
            raise AisepError("INTERNAL", f"本机无法建立无网络的查询进程，前置检查未执行：{e}", details=where) from None
        if not res["value"]:
            failed.append({"id": x["id"], "hint": x["hint"]})
    return failed


def _plan_digest(action, ddigest, params, files):
    """Binds a dryRun to its execution: the action, its definition, the parameters, and for every file the plan
    touches the bytes before and after. A change to any of them makes an older digest stale."""
    return "sha256:" + hashlib.sha256(json.dumps(
        {"action": action, "definitionDigest": ddigest, "params": params, "files": files},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _impact(cfg, repo, targets):
    """model_impact summary (who depends on the target), kept apart from the cascade closure of the remove plan."""
    out = []
    for t in targets:
        try:
            r = tools.model_impact(cfg, focus=t, mode="depends", depth=IMPACT_DEPTH, allowInvalid=True, repo=repo)
        except AisepError as e:
            out.append({"focus": t, "error": {"code": e.code, "message": e.message}})
            continue
        items = r["items"]
        out.append({"focus": t, "mode": "depends", "depth": IMPACT_DEPTH, "count": len(items),
                    "truncated": bool(r["truncated"]) or len(items) > IMPACT_ITEMS, "invalidModel": r["invalidModel"],
                    "items": [{"iri": i["iri"], "label": i["label"], "types": i["types"], "depth": i["depth"]}
                              for i in items[:IMPACT_ITEMS]]})
    return out


# ---------------------------------------------------------------- execution

def model_apply_action(cfg, action, params=None, dryRun=False, planDigest=None, repo=None, **extra):
    write_tools._no_extra(extra)
    writer.locate_worktree_root(cfg, repo)  # `repo` is still checked first; it selects the models written, nothing else
    entries, _ = load_catalog(_catalog_path(cfg))  # the served catalogue, not `repo`'s
    found = [(d, p) for d, p in entries if d.get("id") == action]
    if not found:
        raise AisepError("INVALID_ARGUMENT", f"没有动作 {action!r}", hint="用 model_list_actions 看目录",
                         details={"rejectedFields": ["action"],
                                  "available": sorted(d["id"] for d, p in entries if not p)})
    d, problems = found[0]
    if problems or len(found) > 1:
        raise AisepError("INVALID_ARGUMENT", f"动作 {action} 的定义无效，不能执行：{(problems or ['id 重复'])[0]}",
                         details={"rejectedFields": ["action"], "problems": problems})
    calllog.note(action={"version": d["version"], "definitionDigest": d["definitionDigest"]})  # ADR-031
    params = {} if params is None else params
    calllog.note(iris=[params[k] for k in _iri_params(d) if isinstance(params.get(k), str)])  # ADR-031
    _check_params(d, params)
    destructive, ddigest, iri_params = _destructive(d), d["definitionDigest"], set(_iri_params(d))
    targets = []  # IRIs the remove steps act on (for the impact summary)

    def build(ws, ctx):
        base_st = write_tools._subject_triples(ctx)

        def model_of(name):
            v = params.get(name)
            if v is None:
                return MISSING
            m = next((t.object.value for _, t in base_st.get(v, ()) if t.predicate.value == write_tools.IN_MODEL), None)
            if m is None:
                raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(v)} 不是本仓库模型的成员", hint="从 details.candidates 里选",
                                 details={"candidates": tools._candidates(ctx, v), "rejectedFields": [f"params.{name}"]})
            return m

        cur_ws, cur_ctx = ws, ctx
        edits, added, removed, steps_out, iris, cascade = {}, {}, {}, [], {}, []
        for n, step in enumerate(d["steps"]):
            op = OPS[step["op"]]
            args = _args(step, iri_params, params, iris, model_of)
            lacking = sorted(op["required"] - set(args))
            if lacking:
                raise AisepError("INVALID_ARGUMENT", f"步骤 {step['id']} 缺必填参数 {', '.join(lacking)}（对应的动作参数没给）",
                                 details={"step": step["id"], "rejectedFields": lacking})
            try:
                if step["op"] in DESTRUCTIVE_OPS:  # always the full cascade: the caller sees the plan first (two-phase)
                    plan = op["build"](args["iri"], cascade=True, dryRun=dryRun, planDigest=planDigest,
                                       verify_digest=False)(cur_ws, cur_ctx)
                else:
                    plan = op["build"](**args)(cur_ws, cur_ctx)
            except AisepError as e:
                if step["op"] in DESTRUCTIVE_OPS and isinstance(args["iri"], str):
                    targets.append(args["iri"])
                e.details.pop("planDigest", None)  # model_remove's own digest is not valid for model_apply_action
                e.details.setdefault("step", step["id"])
                raise
            res = dict(plan["result"])
            if step["op"] in DESTRUCTIVE_OPS:
                targets.append(res["target"])
                res.pop("planDigest", None)
                res.pop("written", None)
                if res.get("plan"):
                    cascade.append(dict(res["plan"], step=step["id"], target=res["target"]))
            if "iri" in res:
                iris[step["id"]] = res["iri"]
            steps_out.append({"id": step["id"], "op": op["tool"], "changed": bool(plan["edits"]), "result": res})
            if not plan["edits"]:
                continue
            edits.update(plan["edits"])
            for f, rs in (plan.get("removed") or {}).items():
                if f in added:  # a triple added by an earlier step and removed again nets out
                    added[f] = [t for t in added[f] if (t.subject.value, t.predicate.value, t.object) not in rs]
                removed.setdefault(f, set()).update(rs)
            for f, ts in (plan.get("added") or {}).items():
                added.setdefault(f, []).extend(ts)
            if n + 1 < len(d["steps"]):  # the next step plans on top of this one, as a second tool call would
                over = {f: t.encode("utf-8") for f, t in edits.items()}
                cur_ws = copy.copy(ws)
                cur_ws.data = dict(ws.data, **over)
                cur_ctx = ws.ctx(over)
                if any(p[1] == "L0" for p in cur_ctx.problems):
                    raise AisepError("EDIT_UNSAFE", f"步骤 {step['id']} 之后的中间结果不能解析，未写入",
                                     details={"step": step["id"]})
                core.run_check(cur_ctx)
        result = {"action": d["id"], "actionIri": d["iri"], "definitionDigest": ddigest, "destructive": destructive,
                  "steps": steps_out, "iris": iris, "planDigest": planDigest}
        if destructive:
            result["cascade"] = cascade
        # steps that change a file and change it back net out: a file whose merged text equals the workspace bytes
        # is not an edit (e.g. two parameters given the same IRI at call time, which X6 cannot see)
        edits = {f: t for f, t in edits.items() if t.encode("utf-8") != ws.data.get(f)}
        added = {f: v for f, v in added.items() if f in edits}
        removed = {f: v for f, v in removed.items() if f in edits}
        if not edits:  # replay: the merged plan is a no-op on this workspace -> changed:false, guards are not run
            return {"result": result, "edits": {}}
        failed = _failed_guards(d, params, ctx)
        if failed:
            raise AisepError("PRECONDITION_FAILED", f"动作 {d['id']} 的前置检查没过：{failed[0]['hint']}",
                             hint=failed[0]["hint"], details={"action": d["id"], "failedGuards": failed})
        digest = _plan_digest(d["id"], ddigest, params,
                              {f: [writer.sha(ws.data.get(f)), writer.sha(t.encode("utf-8"))] for f, t in sorted(edits.items())})
        result["planDigest"] = digest
        details = {"action": d["id"], "planDigest": digest, "steps": steps_out, "files": sorted(edits)}
        if destructive:
            details["cascade"] = cascade
        if planDigest is not None and planDigest != digest:
            raise AisepError("PLAN_STALE", "计划已变化（模型文件、动作定义或参数在 dryRun 之后变了）",
                             hint="先用 dryRun: true 取新计划", details=details)
        if destructive and not dryRun and planDigest is None:
            raise AisepError("PLAN_REQUIRED", f"动作 {d['id']} 含删除步骤，必须先 dryRun 再带 planDigest 执行",
                             hint="看过 details 里的计划与影响摘要后，带 details.planDigest 重新调用", details=details)
        return {"result": result, "edits": edits, "removed": removed, "added": added}

    try:
        res = writer.transaction(cfg, repo, build, dryRun)
    except AisepError as e:
        if destructive and targets and e.code in ("PLAN_REQUIRED", "PLAN_STALE", "REFERENCED"):
            e.details["impact"] = _impact(cfg, repo, targets)
        raise
    if destructive and dryRun and res.get("changed"):
        res["impact"] = _impact(cfg, repo, targets)
    return res
