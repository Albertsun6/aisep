"""The read-only MCP tools as plain functions (docs/mcp-interface.md §5.4, §5.6, §5.7): model_check, model_validate,
model_findings, model_gate, model_query, model_impact. Each returns the tool's structuredContent (a dict) or raises
AisepError; the MCP shell (aisep/server.py) only wraps them. Judgement is the prototype's (aisep/core.py) unchanged."""
import contextlib, difflib, os, re, threading, time
from dataclasses import dataclass

import pyoxigraph as ox

from aisep import core, gitio
from aisep.errors import AisepError

LAYERS = ("L0", "build", "L1", "L2", "L3", "L4")
QUERY_LIMIT, QUERY_LIMIT_MAX, QUERY_TIMEOUT_MS = 1000, 10000, 10000
IMPACT_MAX_ITEMS = 500


@dataclass(frozen=True)
class Config:
    """Server start-up parameters (§3.3): --allow-root (repeatable), --repo, --main-branch."""
    allow_roots: tuple = ()
    repo: str | None = None
    main_branch: str = "main"


# ---------------------------------------------------------------- loading: workspace or a commit's snapshot (§3.3)

@contextlib.contextmanager
def loaded(cfg, repo=None, ref=None, model=None):
    """Yields (ctx, source). Without ref: the worktree's files (§3.3 file set, safe open). With ref: that commit's
    models/ modules/ vendor/ materialised to a temp dir. model: only models/<slug>/ files."""
    slug = None if model is None else core.model_slug(model)
    root = gitio.locate_repo(repo, cfg.allow_roots, cfg.repo)
    with contextlib.ExitStack() as stack:
        if ref is None:
            missing = [d for d in ("modules", "vendor") if not os.path.isdir(os.path.join(root, d))]
            if missing:  # e.g. `repo` pointing at a nested repository planted in a checkout (SEC-3)
                raise AisepError("MODULES_NOT_IN_REF", f"工作区 {root} 里没有 {'、'.join(m + '/' for m in missing)}，无法检查",
                                 details={"repo": root, "missing": missing})
            base, files, commit = root, gitio.model_files(root), None
        else:
            commit = gitio.resolve_commit(root, ref)
            base, files = stack.enter_context(gitio.snapshot(root, commit))
            stack.callback(core.forget_paths, base)
        if slug is not None:
            files = [f for f in files if f.startswith(f"models/{slug}/")]
            if not files:
                raise AisepError("MODEL_NOT_FOUND", f"没有模型 {model}（models/{slug}/ 下没有 .ttl 文件）",
                                 details={"model": model})
        ctx = core.Ctx(core.discover(base), [os.path.join(base, f) for f in files], root=base,
                       read=lambda f: gitio.read_file(base, os.path.relpath(f, base)))
        yield ctx, {"repo": root, "ref": ref, "commit": commit}


# ---------------------------------------------------------------- findings (§7.3)

_FOCUS_RE = re.compile(r"^(?:\[[^\]]+\] )?(\S+?)(?: \([^)]*\))?(?: path=\S+)?: ")


class _Focus:
    """Fallback focus for add() call sites that do not pass one: the leading `short-name:` of the message, expanded,
    kept only when it is a subject written in a model source (§7.3)."""

    def __init__(self, ctx):
        self.ctx, self.file_of = ctx, {}
        for f, qs in ctx.src_quads.items():
            for q in qs:
                self.file_of.setdefault(q.subject.value, ctx.rel(f))

    def __call__(self, text):
        m = _FOCUS_RE.match(text)
        if not m:
            return None
        tok = m.group(1)
        try:
            iri = tok if "://" in tok or tok.startswith("urn:") else core.expand(self.ctx, tok)
        except AisepError:
            return None
        return iri if iri in self.file_of else None


def _finding(focus_of, sev, layer, text, focus=None, rule=None, file=None):
    focus = focus or focus_of(text)
    return {"severity": sev, "layer": layer, "rule": rule, "focus": focus,
            "file": file or (focus_of.file_of.get(focus) if focus else None), "message": text}


def _findings(ctx, layers):
    """Display findings: deduplicated and ordered like the CLI report (core.shown)."""
    focus_of, first = _Focus(ctx), {}
    for inst in ctx.instances:
        first.setdefault(inst[:3], inst)
    return [_finding(focus_of, *first.get(p, p)) for p in core.shown(ctx.problems, layers)]


def _summary(findings, t0):
    n = lambda s: sum(1 for f in findings if f["severity"] == s)
    return {"violations": n("Violation"), "warnings": n("Warning"), "infos": n("Info"),
            "violationsByLayer": {l: sum(1 for f in findings if f["layer"] == l and f["severity"] == "Violation") for l in LAYERS},
            "seconds": round(time.time() - t0, 2)}


def _l0_failed(ctx):
    return any(p[1] == "L0" for p in ctx.problems)


# ---------------------------------------------------------------- §5.4

def model_check(cfg, repo=None, ref=None, model=None):
    t0 = time.time()
    with loaded(cfg, repo, ref, model) as (ctx, source):
        layers = ("L0",)
        if not _l0_failed(ctx):
            core.run_check(ctx)
            layers = ("L0", "L1", "L2")
        fs = _findings(ctx, layers)
    return {"partial": True, "summary": _summary(fs, t0), "findings": fs, "source": source}


def model_validate(cfg, repo=None, ref=None, model=None):
    t0 = time.time()
    with loaded(cfg, repo, ref, model) as (ctx, source):
        if not _l0_failed(ctx):
            core.l3(ctx)
        fs = _findings(ctx, ("L0", "L3"))
    return {"partial": True, "summary": _summary(fs, t0), "findings": fs, "source": source}


def model_findings(cfg, repo=None, ref=None, model=None):
    """L4 (never FAIL) plus openViolations: every L0-L2 Violation instance of the same content, not de-duplicated."""
    t0 = time.time()
    with loaded(cfg, repo, ref, model) as (ctx, source):
        core.l4(ctx)
        fs = _findings(ctx, ("L0", "L4"))
        summary = _summary(fs, t0)
        if not _l0_failed(ctx):
            core.run_check(ctx)
        focus_of = _Focus(ctx)
        order = {"Violation": 0, "Warning": 1}
        inst = sorted((i for i in ctx.instances if i[0] == "Violation" and i[1] in ("L0", "build", "L1", "L2")),
                      key=lambda i: (order.get(i[0], 2), i[1], i[2]))
        items = [_finding(focus_of, *i) for i in inst]
    return {"partial": True, "summary": summary, "findings": fs, "source": source,
            "openViolations": {"count": len(items),
                               "byLayer": {l: sum(1 for i in items if i["layer"] == l) for l in ("L0", "build", "L1", "L2")},
                               "items": items}}


def model_gate(cfg, repo=None, ref=None, model=None):
    """G10: L0..L4 on one build. A FAIL is a normal result, not a tool error."""
    t0 = time.time()
    with loaded(cfg, repo, ref, model) as (ctx, source):
        if not _l0_failed(ctx):
            core.run_check(ctx)
            core.l3(ctx)
            core.l4(ctx)
        fs = _findings(ctx, LAYERS)
    summary = _summary(fs, t0)
    return {"result": "FAIL" if summary["violations"] else "PASS", "summary": summary, "findings": fs, "source": source}


# ---------------------------------------------------------------- §5.6

_UPDATE_RE = re.compile(r"(?is)^(?:\s|#[^\n]*(?:\n|$)|PREFIX\s+[\w.-]*:\s*<[^>]*>|BASE\s*<[^>]*>)*"
                        r"(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD|WITH)\b")
# MCP-1: SERVICE counts only where the SPARQL grammar can read a keyword. The scanner walks the text token by token:
# strings, comments, variables and language tags are skipped (?service, 'service', "# service" are data); a prefixed
# name is skipped unless "service" could be read out of it as the keyword (its prefix contains it: SERVICE:q,
# service:q, SERVICEex:q; or it follows '.', ':' or '\' inside the local name) - am4:Service and ex:aService are data.
# An IRI-shaped token "<...>" is skipped as an IRI, but when it holds '(' ')' or a quote its '<' may be a less-than
# (FILTER(1<2)SERVICE:q#>, FILTER(1<2&&'>'=?x)SERVICE...): both readings are scanned and either one finding the
# keyword counts. Anything else is matched WITHOUT word boundaries (1SERVICE, )SERVICE), on the text itself (not on
# a lower-cased copy, whose indexes shift after U+0130). The SPARQL spec allows \uXXXX / \UXXXXXXXX codepoint escapes
# anywhere in the query text; pyoxigraph 0.5 does not decode them in keyword position (SyntaxError, no request), but
# the decoded text is scanned as well, as a safety margin. A doubtful token is read as the keyword. The differential
# fuzz test (test_l4b_extra.py) checks that whatever this lets through, pyoxigraph never sends a request for.
_TOKEN = re.compile(r"""
      (?P<str> '''(?:[^'\\]|\\.|'(?!''))*''' | \"\"\"(?:[^"\\]|\\.|"(?!""))*\"\"\"
             | '(?:[^'\\\n\r]|\\.)*' | "(?:[^"\\\n\r]|\\.)*" )
    | (?P<iri> <[^<>"{}|^`\\\x00-\x20]*> )
    | (?P<comment> \#[^\n\r]* )
    | (?P<var> [?$]\w+ )
    | (?P<lang> @[A-Za-z]+(?:-[A-Za-z0-9]+)* )
    | (?P<bnode> _:[\w.-]* )
    | (?P<pname> (?P<prefix>[^\W\d_][\w.-]*)?:(?P<local>(?:[\w.:%-]|\\.)*) )
    """, re.X)
_ESCAPE_RE = re.compile(r"\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})")
_GLUED_SERVICE = re.compile(r"(?i)[.:\\]service")
_SERVICE = re.compile(r"(?i)service")  # matched on the text itself: str.lower() can change the length (U+0130)


def _decode_escapes(text):
    def one(m):
        n = int(m.group(1) or m.group(2), 16)
        return chr(n) if n <= 0x10FFFF else m.group(0)
    return _ESCAPE_RE.sub(one, text)


def _scan_service(text):
    """True when some reading of `text` has the SERVICE keyword. Positions reachable by any reading are visited in
    order; a token's end (and, for a doubtful IRI, the position after its '<') becomes reachable."""
    n, reach = len(text), {0}
    for pos in range(n):
        if pos not in reach:
            continue
        if _SERVICE.match(text, pos):
            return True
        m = _TOKEN.match(text, pos)
        kind = m.lastgroup if m else None
        if m and m.group("pname") is not None:
            if _SERVICE.search(m.group("prefix") or "") or _GLUED_SERVICE.search(m.group("local")):
                return True
        elif kind == "lang" and _SERVICE.search(m.group()):
            return True
        elif kind == "iri" and any(c in m.group() for c in "()'"):
            reach.add(pos + 1)  # the '<' may be a less-than: rescan the token's inside as well
        reach.add(m.end() if m and m.end() > pos else pos + 1)
    return False


def _has_service(sparql):
    return any(_scan_service(t) for t in (sparql, _decode_escapes(sparql)))


def _term(v):
    if isinstance(v, ox.NamedNode):
        return {"type": "iri", "value": v.value}
    if isinstance(v, ox.BlankNode):
        return {"type": "bnode", "value": v.value}
    t = {"type": "literal", "value": v.value}
    if v.language:
        t["lang"] = v.language
    else:
        t["datatype"] = v.datatype.value
    return t


def _run_query(ctx, sparql, limit):
    res = ctx.store.query(sparql, prefixes=ctx.prefixes, use_default_graph_as_union=True)
    if isinstance(res, (ox.QueryBoolean, bool)):
        return {"kind": "ask", "value": bool(res)}
    rows = []
    if isinstance(res, ox.QueryTriples):
        for tr in res:
            if len(rows) == limit:
                return {"kind": "triples", "triples": rows, "truncated": True}
            rows.append([_term(tr.subject), _term(tr.predicate), _term(tr.object)])
        return {"kind": "triples", "triples": rows, "truncated": False}
    names = [v.value for v in res.variables]
    for sol in res:
        if len(rows) == limit:
            return {"kind": "select", "variables": names, "rows": rows, "truncated": True}
        rows.append({n: _term(sol[n]) for n in names if sol[n] is not None})
    return {"kind": "select", "variables": names, "rows": rows, "truncated": False}


def model_query(cfg, sparql, limit=QUERY_LIMIT, timeoutMs=QUERY_TIMEOUT_MS, allowPartial=False, repo=None, ref=None):
    if not isinstance(limit, int) or not 1 <= limit <= QUERY_LIMIT_MAX:
        raise AisepError("INVALID_ARGUMENT", f"limit 须为 1–{QUERY_LIMIT_MAX}", details={"rejectedFields": ["limit"]})
    if not isinstance(sparql, str):
        raise AisepError("INVALID_ARGUMENT", "sparql 须为字符串", details={"rejectedFields": ["sparql"]})
    if _has_service(sparql):  # pyoxigraph would really send the HTTP request (F6)
        raise AisepError("QUERY_NOT_READONLY", "查询里有 SERVICE，不允许访问外部端点",
                         hint="去掉 SERVICE 子句，只查本地模型")
    with loaded(cfg, repo, ref) as (ctx, source):
        out = {"source": source}
        if _l0_failed(ctx):
            skipped = sorted(f["file"] for f in _findings(ctx, ("L0",)) if f["file"])
            if not allowPartial:
                raise AisepError("PARSE_FAILED", f"{len(skipped)} 个模型文件解析失败，查询结果会不完整",
                                 hint="修好这些文件；只为诊断时传 allowPartial: true",
                                 details={"files": skipped, "findings": _findings(ctx, ("L0",))})
            out.update(partial=True, skippedFiles=skipped, findings=_findings(ctx, ("L0",)))
        box = {}

        def work():
            try:
                box["result"] = _run_query(ctx, sparql, limit)
            except BaseException as e:  # noqa: BLE001 — re-raised in the caller's thread
                box["error"] = e

        th = threading.Thread(target=work, daemon=True)
        th.start()
        th.join(timeoutMs / 1000)
        if th.is_alive():  # the worker cannot be interrupted; it is abandoned (daemon) and its result discarded
            raise AisepError("QUERY_TIMEOUT", f"查询超过 {timeoutMs} 毫秒", hint="加 LIMIT 或收窄模式后重试")
        if "error" in box:
            e = box["error"]
            if isinstance(e, SyntaxError) and _UPDATE_RE.match(sparql):
                raise AisepError("QUERY_NOT_READONLY", "只接受 SELECT/ASK/CONSTRUCT/DESCRIBE，不接受更新语句")
            if isinstance(e, (SyntaxError, OSError, ValueError, RuntimeError)):  # RuntimeError: e.g. an unbound SERVICE endpoint
                raise AisepError("QUERY_FAILED", f"查询失败：{e}", details={"parser": str(e)})
            raise e
        out.update(box["result"])
    out.setdefault("findings", [])
    return out


# ---------------------------------------------------------------- §5.7

def _candidates(ctx, name, n=5):
    members = [x for (x,) in ctx.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x arch:inModel ?m }} {ctx.src_graph_filter()} }}")]
    want = name.rsplit("/", 1)[-1].split(":")[-1].lower()
    score = lambda x: max(difflib.SequenceMatcher(None, want, x.rsplit("/", 1)[-1].lower()).ratio(),
                          difflib.SequenceMatcher(None, want, ctx.label(x).lower()).ratio())
    return [{"iri": x, "label": ctx.label(x)} for x in sorted(members, key=lambda x: (-score(x), x))[:n]]


def model_impact(cfg, focus, mode="depends", depth=3, allowInvalid=False, repo=None, ref=None):
    if mode not in ("depends", "ripple"):
        raise AisepError("INVALID_ARGUMENT", f"mode 须为 depends 或 ripple，收到 {mode!r}", details={"rejectedFields": ["mode"]})
    if not isinstance(depth, int) or not 1 <= depth <= 10:
        raise AisepError("INVALID_ARGUMENT", "depth 须为 1–10 的整数", details={"rejectedFields": ["depth"]})
    with loaded(cfg, repo, ref) as (ctx, source):
        if not _l0_failed(ctx):
            core.run_check(ctx)  # G9
        viol = [f for f in _findings(ctx, ("L0", "L1", "L2")) if f["severity"] == "Violation"]
        if viol and not allowInvalid:
            raise AisepError("MODEL_INVALID", f"模型有 {len(viol)} 个 L0–L2 违规，拒绝计算影响面",
                             hint="先修好违规；确需在不合法模型上看影响面时传 allowInvalid: true",
                             details={"findings": viol})
        try:
            start = core.expand(ctx, focus)
        except AisepError as e:
            raise AisepError("INVALID_ARGUMENT", f"focus：{e.message}", details={"rejectedFields": ["focus"]}) from None
        if not ctx.types(start):
            raise AisepError("ELEMENT_NOT_FOUND", f"{core.short(start)} 不是已加载模型里的元素",
                             hint="从 details.candidates 里选一个 IRI 重试", details={"candidates": _candidates(ctx, start)})
        arrow = {"→": "forward", "←": "backward", "~": "related"}
        items = [{"iri": x, "label": ctx.label(x), "types": ctx.types(x), "depth": d, "related": rel,
                  "path": [{"from": a, "relationship": r, "via": c,
                            "direction": arrow[ar], "to": b} for a, r, c, ar, b in hops]}
                 for d, x, hops, rel in core.impact_hops(ctx, start, depth, mode)]
        out = {"focus": {"iri": start, "label": ctx.label(start), "types": ctx.types(start)},
               "mode": mode, "depth": depth, "invalidModel": {"violations": len(viol)} if viol else None,
               "items": items[:IMPACT_MAX_ITEMS], "truncated": len(items) > IMPACT_MAX_ITEMS,
               "findings": viol, "source": source}
    return out
