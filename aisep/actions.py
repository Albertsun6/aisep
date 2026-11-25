"""Action catalogue (docs/mcp-interface.md §5.13, §5.14): model_list_actions, model_apply_action.

An action is DATA (aisep/action_catalog.json): a named list of steps, each naming one of the closed set of atomic
operations below (the plan functions of the existing write tools), plus hint-level guards. This module only reads the
catalogue, validates the parameters, resolves step arguments, runs the steps' plan functions one after another on an
in-memory overlay of the workspace and hands the merged plan to ONE writer.transaction. Legality is whatever that
transaction's L0-L2 judgement of the candidate graph says; nothing here defines what a legal model is. Guards are
advice (PRECONDITION_FAILED), not invariants: a direct edit is not bound by them and `gate` does not know them.
No state is kept: no execution record, no log, no git add, no commit."""
import copy, hashlib, json, os, re

import jsonschema
import pyoxigraph as ox

from aisep import core, tools, write_tools, writer
from aisep.errors import AisepError

CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_catalog.json")
# the closed set of atomic operations: name -> (plan-function factory, allowed args, required args, yields an IRI)
OPS = {
    "add_element": (write_tools.add_element_build,
                    {"model", "type", "prefLabel", "altLabel", "slug", "definition", "attributes", "file"},
                    {"model", "type", "prefLabel"}, True),
    "add_relationship": (write_tools.add_relationship_build, {"type", "source", "target", "model", "file"},
                         {"type", "source", "target"}, True),
    "set_labels": (write_tools.set_labels_build, {"iri", "prefLabel", "altLabel", "definition"}, {"iri"}, True),
    "remove": (write_tools.remove_build, {"iri"}, {"iri"}, False),
}
DESTRUCTIVE_OPS = {"remove"}  # derived by the executor; the catalogue has no field that could lower it
MODIFYING_ARG = {"set_labels": "iri", "remove": "iri"}  # ops that change an EXISTING resource, and the argument naming it
REF_KEYS = ("const", "param", "stepIri", "modelOf")
ID_RE = r"^[a-z][a-z0-9-]{0,63}\Z"  # \Z, not $: $ also matches before a trailing newline (#77)
# an IRI parameter is a full IRI of a model member: https://aisep.example/model/<slug>/<local name>
IRI_RE = re.compile(re.escape(core.MODEL_BASE) + r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9._~%-]+")
IMPACT_DEPTH, IMPACT_ITEMS = 3, 50
MISSING = object()

_STR = {"type": "string"}
ACTION_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["id", "title", "params", "steps"],
    "properties": {
        "id": {"type": "string", "pattern": ID_RE}, "title": _STR, "description": _STR,
        "params": {"type": "object"}, "iriParams": {"type": "array", "items": _STR},
        "guards": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "ask", "expect", "hint"],
            "properties": {"id": {"type": "string", "pattern": ID_RE}, "ask": _STR, "bind": {"type": "object"},
                           "expect": {"type": "boolean"}, "hint": {"type": "string", "minLength": 1}}}},
        "steps": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "op", "args"],
            "properties": {"id": {"type": "string", "pattern": ID_RE}, "op": _STR, "args": {"type": "object"}}}},
    },
}


# ---------------------------------------------------------------- catalogue

def _is_ref(v):
    return isinstance(v, dict) and len(v) == 1 and next(iter(v)) in REF_KEYS


def _check_value(v, where, props, earlier, problems, allow_step=True):
    """A step argument is one of the four references, or a list / object whose leaves are such references."""
    if _is_ref(v):
        (k, x), = v.items()
        if k in ("param", "modelOf") and x not in props:
            problems.append(f"{where}：引用了未声明的参数 {x!r}")
        elif k == "stepIri" and (not allow_step or x not in earlier):
            problems.append(f"{where}：stepIri 只能引用前面产出 IRI 的步骤，{x!r} 不是")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _check_value(x, f"{where}[{i}]", props, earlier, problems, allow_step)
    elif isinstance(v, dict) and v and not any(k in REF_KEYS for k in v):
        for k, x in v.items():
            _check_value(x, f"{where}.{k}", props, earlier, problems, allow_step)
    else:
        problems.append(f"{where}：取值只能是 {{const}}、{{param}}、{{stepIri}}、{{modelOf}} 之一（或由它们组成的列表、对象）")


def _ref_key(v):
    """A comparable key for a {param} / {const} / {stepIri} reference; None for anything else."""
    if _is_ref(v):
        (k, x), = v.items()
        if k in ("param", "const", "stepIri"):
            return k, json.dumps(x, sort_keys=True, ensure_ascii=False)
    return None


def _overlap_problems(steps):
    """Two steps acting on the same IRI make a replay fail (a step is then no longer a no-op: PLAN_STALE, PLAN_REQUIRED,
    IRI_EXISTS, ELEMENT_NOT_FOUND), so the catalogue may not hold such an action. Decided on the references alone:
    a set_labels / remove step on what an earlier step of the same action created ({stepIri}); two set_labels / remove
    steps naming the same {param} or {const}; a remove step naming the same {param} / {const} as an end of an
    add_relationship step (the cascade deletes that relationship). Two DIFFERENT parameters that the caller sets to the
    same IRI, or an add_element whose slug equals a removed IRI, depend on run-time values and are not caught here."""
    problems, touched = [], {}
    for s in steps:
        arg = MODIFYING_ARG.get(s["op"]) if s["op"] in OPS else None
        key = _ref_key(s["args"].get(arg)) if arg else None
        if key is None:
            continue
        if key[0] == "stepIri":
            problems.append(f"步骤 {s['id']}：{s['op']} 作用于本动作里前一步新建的资源（{s['args'][arg]['stepIri']}），"
                            "同一动作里先建后改或先建后删，重放会被拒")
        elif key in touched:
            problems.append(f"步骤 {s['id']} 与步骤 {touched[key]} 作用于同一个目标 IRI，重放会被拒")
        else:
            touched[key] = s["id"]
    for r in steps:
        key = _ref_key(r["args"].get("iri")) if r["op"] == "remove" else None
        if key is None or key[0] == "stepIri":
            continue
        for a in steps:
            if a["op"] == "add_relationship" and key in (_ref_key(a["args"].get("source")), _ref_key(a["args"].get("target"))):
                problems.append(f"步骤 {r['id']} 删除的资源是步骤 {a['id']} 新增关系的端点，级联会删掉它，重放会被拒")
    return problems


def _definition_problems(d):
    errs = sorted(jsonschema.Draft202012Validator(ACTION_SCHEMA).iter_errors(d), key=lambda e: list(e.absolute_path))
    if errs:
        return [f"{'/'.join(map(str, e.absolute_path)) or '(动作)'}：{e.message[:200]}" for e in errs]
    problems = []
    schema = d["params"]
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        return [f"params 不是合法的 JSON Schema：{e.message[:200]}"]
    props = schema.get("properties", {})
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False or not isinstance(props, dict):
        problems.append("params 须为 type: object、additionalProperties: false 的 JSON Schema")
        props = props if isinstance(props, dict) else {}
    for p in d.get("iriParams", ()):
        if not isinstance(props.get(p), dict) or props[p].get("type") != "string":
            problems.append(f"iriParams：{p!r} 不是 params 里声明的字符串参数")
    earlier, seen = set(), set()
    for s in d["steps"]:
        if s["id"] in seen:
            problems.append(f"步骤 id 重复：{s['id']}")
        seen.add(s["id"])
        if s["op"] not in OPS:
            problems.append(f"步骤 {s['id']}：未知操作 {s['op']!r}（只认 {', '.join(sorted(OPS))}）")
            continue
        _, allowed, required, yields = OPS[s["op"]]
        for a in sorted(set(s["args"]) - allowed):
            problems.append(f"步骤 {s['id']}：操作 {s['op']} 没有参数 {a!r}")
        for a in sorted(required - set(s["args"])):
            problems.append(f"步骤 {s['id']}：操作 {s['op']} 缺必填参数 {a!r}")
        for a, v in s["args"].items():
            _check_value(v, f"步骤 {s['id']}.{a}", props, earlier, problems)
        if yields:
            earlier.add(s["id"])
    problems += _overlap_problems(d["steps"])
    gids = set()
    for g in d.get("guards", ()):
        if g["id"] in gids:
            problems.append(f"guard id 重复：{g['id']}")
        gids.add(g["id"])
        where = f"guard {g['id']}"
        bind = g.get("bind", {})
        for var, v in bind.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var) or not _is_ref(v):
                problems.append(f"{where}：bind 须为 变量名 -> {{param}} / {{modelOf}} / {{const}}")
            else:
                _check_value(v, f"{where}.bind.{var}", props, (), problems, allow_step=False)
        if not re.match(r"\s*ASK\b", g["ask"]) or re.search(r"\bSERVICE\b", g["ask"], re.I):
            problems.append(f"{where}：只能是只读的 SPARQL ASK（不带 PREFIX 声明，不许 SERVICE）")
            continue
        try:  # syntax, and every bound variable must be visible in the query (pyoxigraph refuses it otherwise)
            ox.Store().query(core.SPARQL_PREFIXES + g["ask"], use_default_graph_as_union=True,
                             substitutions={ox.Variable(v): ox.NamedNode("urn:aisep:probe") for v in bind
                                            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v)})
        except (SyntaxError, ValueError, RuntimeError, OSError) as e:
            problems.append(f"{where}：查询不能执行：{str(e)[:200]}")
    return problems


def definition_digest(d):
    return "sha256:" + hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_catalog(path=None):
    """[(definition, problems)] in file order, read from disk on every call (no cache: a changed definition takes effect
    at once and makes older planDigests stale). An entry with problems is listed as invalid and cannot be applied."""
    path = path or CATALOG_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        entries = doc["actions"]
        if not isinstance(entries, list):
            raise ValueError("actions 不是列表")
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise AisepError("INTERNAL", f"动作目录 {os.path.basename(path)} 读不了：{type(e).__name__}: {str(e)[:200]}") from None
    out = []
    for d in entries:  # one bad definition is listed as invalid; it never makes the whole catalogue unreadable
        try:
            problems = _definition_problems(d) if isinstance(d, dict) else ["动作定义须为对象"]
        except Exception as e:  # noqa: BLE001 — a definition shape the checks above did not foresee
            problems = [f"定义校验出错：{type(e).__name__}: {str(e)[:200]}"]
        out.append((d, problems))
    ids = [d.get("id") if isinstance(d, dict) and isinstance(d.get("id"), str) else None for d, _ in out]
    for (d, problems), aid in zip(out, ids):  # every copy of a duplicated id is invalid, not just the later ones
        if aid is not None and ids.count(aid) > 1:
            problems.append(f"动作 id 重复：{aid}")
    return out, doc.get("version")


def _destructive(d):
    return any(s["op"] in DESTRUCTIVE_OPS for s in d["steps"])


def model_list_actions(cfg, **extra):
    """Read-only: the catalogue with each action's parameter schema. The result depends on the catalogue; the tool
    list of the server does not."""
    write_tools._no_extra(extra)
    entries, version = load_catalog()
    actions = []
    for d, problems in entries:
        if problems:
            aid = d.get("id") if isinstance(d, dict) else None
            actions.append({"id": aid if isinstance(aid, str) else None, "valid": False, "problems": problems})
            continue
        destructive = _destructive(d)
        actions.append({"id": d["id"], "title": d["title"], "description": d.get("description", ""), "valid": True,
                        "params": d["params"], "iriParams": list(d.get("iriParams", ())),
                        "destructive": destructive, "requiresPlanDigest": destructive,
                        "guards": [{"id": g["id"], "hint": g["hint"]} for g in d.get("guards", ())],
                        "steps": [{"id": s["id"], "op": s["op"]} for s in d["steps"]],
                        "definitionDigest": definition_digest(d)})
    return {"catalogVersion": version, "operations": sorted(OPS), "actions": actions}


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
    errors = list(jsonschema.Draft202012Validator(d["params"]).iter_errors(params))
    if errors:
        fields = set()
        for e in errors:
            _rejected(e, fields)
        raise AisepError("INVALID_ARGUMENT", f"动作 {d['id']} 的参数不合规：{errors[0].message[:200]}",
                         hint="按 model_list_actions 返回的 params schema 修改",
                         details={"rejectedFields": sorted(f"params.{f}" for f in fields)})
    for name in d.get("iriParams", ()):
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


def _resolve(v, params, iris, model_of):
    """The value of a step argument; MISSING when it depends on an optional parameter that was not given (the
    enclosing list item, or the whole argument, is then left out)."""
    if _is_ref(v):
        (k, x), = v.items()
        if k == "const":
            return x
        if k == "param":
            return params.get(x, MISSING)
        if k == "stepIri":
            return iris[x]
        return model_of(x)
    if isinstance(v, list):
        return [r for r in (_resolve(x, params, iris, model_of) for x in v) if r is not MISSING]
    out = {k: _resolve(x, params, iris, model_of) for k, x in v.items()}
    return MISSING if any(r is MISSING for r in out.values()) else out


def _failed_guards(d, params, ctx, model_of):
    """Guards whose ASK result differs from `expect`. Parameters reach the query only as pre-bound terms
    (substitutions), never as query text. A guard bound to an optional parameter that was not given is skipped."""
    failed = []
    for g in d.get("guards", ()):
        subs, skip = {}, False
        for var, ref in g.get("bind", {}).items():
            (k, x), = ref.items()
            val = _resolve(ref, params, {}, model_of)
            if val is MISSING:
                skip = True
            elif k == "modelOf" or (k == "param" and x in d.get("iriParams", ())):
                subs[ox.Variable(var)] = ox.NamedNode(val)
            elif isinstance(val, str):
                subs[ox.Variable(var)] = ox.Literal(val)
            else:
                raise AisepError("INVALID_ARGUMENT", f"guard {g['id']} 的绑定 {var} 不是字符串",
                                 details={"rejectedFields": [f"params.{x}"]})
        if skip:
            continue
        got = bool(ctx.store.query(core.SPARQL_PREFIXES + g["ask"], use_default_graph_as_union=True, substitutions=subs))
        if got != g["expect"]:
            failed.append({"id": g["id"], "hint": g["hint"]})
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
    entries, _ = load_catalog()
    found = [(d, p) for d, p in entries if isinstance(d, dict) and d.get("id") == action]
    if not found:
        raise AisepError("INVALID_ARGUMENT", f"没有动作 {action!r}", hint="用 model_list_actions 看目录",
                         details={"rejectedFields": ["action"],
                                  "available": [d["id"] for d, p in entries if not p]})
    d, problems = found[0]
    if problems or len(found) > 1:
        raise AisepError("INVALID_ARGUMENT", f"动作 {action} 的定义无效，不能执行：{(problems or ['id 重复'])[0]}",
                         details={"rejectedFields": ["action"], "problems": problems})
    params = {} if params is None else params
    _check_params(d, params)
    destructive = _destructive(d)
    ddigest = definition_digest(d)
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
            factory, _, required, _ = OPS[step["op"]]
            args = {a: r for a, r in ((a, _resolve(v, params, iris, model_of)) for a, v in step["args"].items())
                    if r is not MISSING}
            lacking = sorted(required - set(args))
            if lacking:
                raise AisepError("INVALID_ARGUMENT", f"步骤 {step['id']} 缺必填参数 {', '.join(lacking)}（对应的动作参数没给）",
                                 details={"step": step["id"], "rejectedFields": lacking})
            try:
                if step["op"] == "remove":  # always the full cascade: the caller sees the plan first (two-phase)
                    plan = factory(args["iri"], cascade=True, dryRun=dryRun, planDigest=planDigest,
                                   verify_digest=False)(cur_ws, cur_ctx)
                else:
                    plan = factory(**args)(cur_ws, cur_ctx)
            except AisepError as e:
                if step["op"] == "remove" and isinstance(args["iri"], str):
                    targets.append(args["iri"])
                e.details.pop("planDigest", None)  # model_remove's own digest is not valid for model_apply_action
                e.details.setdefault("step", step["id"])
                raise
            res = dict(plan["result"])
            if step["op"] == "remove":
                targets.append(res["target"])
                res.pop("planDigest", None)
                res.pop("written", None)
                if res.get("plan"):
                    cascade.append(dict(res["plan"], step=step["id"], target=res["target"]))
            if "iri" in res:
                iris[step["id"]] = res["iri"]
            steps_out.append({"id": step["id"], "op": step["op"], "changed": bool(plan["edits"]), "result": res})
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
        result = {"action": d["id"], "definitionDigest": ddigest, "destructive": destructive, "steps": steps_out,
                  "iris": iris, "planDigest": planDigest}
        if destructive:
            result["cascade"] = cascade
        if not edits:  # replay: every step is a no-op on this workspace -> changed:false, guards are not run
            return {"result": result, "edits": {}}
        failed = _failed_guards(d, params, ctx, model_of)
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
