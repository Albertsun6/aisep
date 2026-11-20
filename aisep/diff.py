"""model_diff (docs/mcp-interface.md §5.8): semantic diff of the model SOURCE graphs, grouped by subject IRI.

Two modes for the head side: a Git ref (committed content only, read from Git objects) or {"worktree": <branch>} (the
disk content of the worktree where that branch is checked out, uncommitted and untracked changes included). The base
side is always a commit (default: merge-base of the head-side commit and the main branch). Nothing is ever written.
Only L0 (parsing) is applied; the ontology is not loaded (kinds come from the model triples alone)."""
import hashlib

import pyoxigraph as ox

from aisep import core, gitio
from aisep.errors import AisepError

ARCH, AISEP_NS = core.ARCH, core.AISEP
RDF_TYPE, SUBCLASS = core.A, core.NS["rdfs"] + "subClassOf"
IN_VIEW, IN_MODEL, SOURCE, TARGET = ARCH + "inView", ARCH + "inModel", ARCH + "source", ARCH + "target"
PREF_LABEL = core.SKOS + "prefLabel"
VIEW_TYPES = {ARCH + "Diagram", ARCH + "Catalog", ARCH + "Matrix"}
GOV_TYPES = {AISEP_NS + "ApprovalRecord", AISEP_NS + "AgentActivity"}
KINDS = ("element", "relationship", "view", "governance", "schema", "other")
MAX_ITEMS = 2000
REREAD = 3
PARSE_CALLS = 0  # number of files parsed (tests assert the fast paths parse nothing)


def _zero_counts():
    return {k: {"added": 0, "modified": 0, "removed": 0} for k in KINDS}


# ---------------------------------------------------------------- parsing and grouping

def _parse(data):
    global PARSE_CALLS
    PARSE_CALLS += 1
    return list(ox.parse(data, format=ox.RdfFormat.TURTLE))


class Side:
    """One side of the diff: subject IRI -> signature {(p, canonical o)}, plus the files each subject's triples are in."""

    def __init__(self, parsed):
        self.sig, self.files, self.triples = {}, {}, {}
        for path, quads in parsed.items():
            canon = _bnode_canon(path, quads)
            for q in quads:
                s, p, o = q.subject, q.predicate.value, q.object
                if isinstance(s, ox.BlankNode):
                    continue  # embedded in its single referrer's signature
                if p == IN_VIEW and isinstance(o, ox.NamedNode):  # membership belongs to the view, not the element
                    key, item = o.value, ("^" + IN_VIEW, str(s))
                else:
                    key, item = s.value, (p, canon(o))
                self.sig.setdefault(key, set()).add(item)
                self.files.setdefault(key, set()).add(path)
                self.triples.setdefault(key, []).append((p, o))
        self.subclass = {}  # model-file single-parent specialisation (R1), for view/governance kinds
        for key, ts in self.triples.items():
            for p, o in ts:
                if p == SUBCLASS and isinstance(o, ox.NamedNode):
                    self.subclass.setdefault(key, o.value)

    def values(self, iri, pred):
        return [o for p, o in self.triples.get(iri, ()) if p == pred]

    def types(self, iri):
        return sorted({o.value for o in self.values(iri, RDF_TYPE) if isinstance(o, ox.NamedNode)})

    def label(self, iri):
        ls = [o for o in self.values(iri, PREF_LABEL) if isinstance(o, ox.Literal)]
        zh = [l.value for l in ls if (l.language or "").startswith("zh")]
        return (zh or [l.value for l in ls] or [None])[0]

    def chain(self, t):
        seen = [t]
        while t in self.subclass and self.subclass[t] not in seen:
            t = self.subclass[t]
            seen.append(t)
        return seen

    def kind(self, iri):
        preds = {p for p, _ in self.sig.get(iri, ())}
        if SOURCE in preds and TARGET in preds:
            return "relationship"
        reach = {c for t in self.types(iri) for c in self.chain(t)}
        if reach & VIEW_TYPES:
            return "view"
        if reach & GOV_TYPES:
            return "governance"
        if SUBCLASS in preds:
            return "schema"
        if IN_MODEL in preds:
            return "element"
        return "other"

    def endpoint(self, iri, pred):
        vs = [o.value for o in self.values(iri, pred) if isinstance(o, ox.NamedNode)]
        return vs[0] if vs else None


def _bnode_canon(path, quads):
    """Tree-shaped blank nodes only: each referenced by exactly one triple and acyclic; its sorted (p, o) pairs are
    embedded in the referrer's signature. Shared, cyclic or unreferenced blank nodes -> DIFF_BNODE_UNSUPPORTED."""
    props, refs = {}, {}
    for q in quads:
        if isinstance(q.subject, ox.BlankNode):
            props.setdefault(q.subject, []).append((q.predicate.value, q.object))
        if isinstance(q.object, ox.BlankNode):
            refs[q.object] = refs.get(q.object, 0) + 1
    for b in props:
        if refs.get(b, 0) != 1:
            why = "shared" if refs.get(b, 0) > 1 else "unreferenced"
            raise AisepError("DIFF_BNODE_UNSUPPORTED", f"{path} 里有{'被共享' if why == 'shared' else '无人引用'}的空白节点",
                             details={"file": path, "bnode": str(b), "reason": why})

    def canon(o, stack=()):
        if not isinstance(o, ox.BlankNode):
            return str(o)
        if o in stack:
            raise AisepError("DIFF_BNODE_UNSUPPORTED", f"{path} 里的空白节点成环", details={"file": path, "bnode": str(o),
                                                                                      "reason": "cycle"})
        return "[" + "; ".join(sorted(f"<{p}> {canon(v, stack + (o,))}" for p, v in props.get(o, ()))) + "]"

    for b in props:  # cycles among blank nodes that are only referenced by each other
        canon(b)
    return canon


def _parse_side(files, side, commit):
    """Committed side: every file must parse (DIFF_PARSE_FAILED otherwise)."""
    parsed = {}
    for path, data in sorted(files.items()):
        if isinstance(data, str):
            raise AisepError("DIFF_PARSE_FAILED", f"{side} 侧 {path} 不是普通文件（{data}）",
                             details={"side": side, "commit": commit, "file": path, "error": data})
        try:
            parsed[path] = _parse(data)
        except SyntaxError as e:
            raise AisepError("DIFF_PARSE_FAILED", f"{side} 侧 {path} 解析失败：{e}",
                             details={"side": side, "commit": commit, "file": path, "error": str(e)}) from None
    return parsed


def _subjects(data):
    try:
        return {q.subject.value for q in ox.parse(data, format=ox.RdfFormat.TURTLE) if isinstance(q.subject, ox.NamedNode)}
    except SyntaxError:
        return set()


# ---------------------------------------------------------------- reading the worktree (§5.8 step 4)

def _read_worktree(w, head_commit, prefixes):
    """One consistent read of W: {path: bytes | "symlink" | "not-regular"}. HEAD, the file set and every file's sha256
    are taken before and after; a difference (a save, delete or commit meanwhile) -> read again, at most REREAD times."""
    def once():
        head = gitio.git(w, "rev-parse", "HEAD")[1].strip()
        flags = gitio.index_flags(w)
        paths = [p for p in gitio.model_files(w) if p.startswith(prefixes)]
        missing_skip = sorted(p for p, t in flags.items() if t == "S" and p.endswith(".ttl") and p.startswith(prefixes)
                              and p not in paths)
        files = {}
        for p in paths:
            try:
                files[p] = gitio.read_file(w, p)
            except gitio.UnsafeFile as e:
                files[p] = str(e)
            except FileNotFoundError:
                files[p] = None  # deleted between listing and reading: the second pass will differ
        if missing_skip:  # sparse checkout: a skip-worktree file absent from disk counts as its HEAD blob
            files.update(gitio.commit_files(w, head, tuple(missing_skip)))
        digest = {p: hashlib.sha256(v).hexdigest() if isinstance(v, bytes) else v for p, v in files.items()}
        return head, digest, files

    for _ in range(REREAD):
        h1, d1, files = once()
        h2, d2, _ = once()
        if (h1, d1) == (h2, d2) and None not in files.values():
            return h1, files
    raise AisepError("WORKTREE_CHANGED", "读取期间工作区一直在变（重读 3 次仍不一致）", retryable=True,
                     hint="稍后重试 model_diff")


def _worktree_clean(w, head_commit, prefixes):
    """True when W's model files certainly equal headCommit's: no assume-unchanged / skip-worktree flag, no sparse
    checkout (git status is silent about those), and `git status` (without optional locks) reports nothing."""
    if gitio.sparse_checkout(w) or any(t == "S" or t.islower() for p, t in gitio.index_flags(w).items()
                                        if p.startswith(prefixes)):
        return False
    rc, out, _ = gitio.git(w, "--no-optional-locks", "status", "--porcelain", "--untracked-files=all", "--",
                           *[p.rstrip("/") + "/" for p in prefixes])
    return rc == 0 and not out.strip()


# ---------------------------------------------------------------- the tool

def _has_models(repo, commit):
    return bool(gitio.tree_entries(repo, commit, "models"))


def _changed_prefixes(repo, base, head, model):
    """Model directories whose tree hash differs between the two commits (only these are read and parsed)."""
    b, h = gitio.tree_entries(repo, base, "models"), gitio.tree_entries(repo, head, "models")
    names = sorted(n for n in set(b) | set(h) if b.get(n) != h.get(n))  # full paths: models/<slug>, models/x.ttl
    if model is not None:
        names = [n for n in names if n == f"models/{model}"]
    return tuple(f"{n}/" if (b.get(n) or h.get(n))[1] == "tree" else n for n in names)


def model_diff(cfg, head, base=None, mainRef=None, detail="summary", model=None, repo=None):
    if detail not in ("summary", "items", "triples"):
        raise AisepError("INVALID_ARGUMENT", "detail 须为 summary、items 或 triples", details={"rejectedFields": ["detail"]})
    if base is not None and not isinstance(base, str):
        raise AisepError("INVALID_ARGUMENT", "base 只接受 Git 引用字符串", details={"rejectedFields": ["base"]})
    root = gitio.locate_repo(repo, cfg.allow_roots, cfg.repo)
    slug = None if model is None else model[len(core.MODEL_BASE):].strip("/").split("/")[0] \
        if model.startswith(core.MODEL_BASE) else model
    prefixes_all = (f"models/{slug}/",) if slug else ("models/",)

    if isinstance(head, dict):
        extra = sorted(set(head) - {"worktree"})
        if extra or "worktree" not in head:
            raise AisepError("INVALID_ARGUMENT", "head 对象只接受 worktree 一个键", details={"rejectedFields": extra or ["head"]})
        w = gitio.locate_worktree(root, head["worktree"], cfg.allow_roots)
        head_commit = gitio.git(w, "rev-parse", "HEAD")[1].strip()
        head_info = {"kind": "worktree", "branch": head["worktree"], "headCommit": head_commit, "dirty": False}
    elif isinstance(head, str):
        w, head_commit = None, gitio.resolve_commit(root, head)
        head_info = {"kind": "ref", "ref": head, "commit": head_commit}
    else:
        raise AisepError("INVALID_ARGUMENT", "head 须为 Git 引用字符串或 {worktree: 分支名}", details={"rejectedFields": ["head"]})

    if base is not None:
        base_commit, main_full = gitio.resolve_commit(root, base), None
    else:
        main_full, main_commit = gitio.resolve_main(root, mainRef or cfg.main_branch)
        base_commit = gitio.merge_base(root, head_commit, main_commit)
    out = {"base": {"ref": base, "commit": base_commit, "viaMergeBase": base is None, "mainRef": main_full},
           "head": head_info, "incomplete": False, "failedFiles": [], "indeterminate": [],
           "counts": _zero_counts(), "changedElementCount": 0, "touchedElementCount": 0}
    if detail != "summary":
        out.update(items=[], touchedElements=[], moves=[], truncated=False)

    base_has = _has_models(root, base_commit)
    if w is not None and not _worktree_clean(w, head_commit, prefixes_all):
        head_commit_read, head_files = _read_worktree(w, head_commit, prefixes_all)
        if head_commit_read != head_commit:  # committed meanwhile: report the HEAD we actually read against
            head_commit = head_info["headCommit"] = head_commit_read
        committed = gitio.commit_files(root, head_commit, prefixes_all)
        head_info["dirty"] = committed != head_files
        head_has = bool(head_files)
        prefixes = prefixes_all
    else:  # Git ref mode, or a clean worktree = its HEAD commit (fast path applies)
        head_has = _has_models(root, head_commit)
        head_files = None
        if base_has and head_has:
            prefixes = _changed_prefixes(root, base_commit, head_commit, slug)
            if not prefixes:  # identical model trees: nothing to parse
                out.update(baseHasModels=True, headHasModels=True)
                return out
        else:
            prefixes = prefixes_all
    out.update(baseHasModels=base_has, headHasModels=head_has)
    if not base_has and not head_has:
        return out

    base_files = gitio.commit_files(root, base_commit, prefixes) if base_has else {}
    B = Side(_parse_side(base_files, "base", base_commit))
    failed, indeterminate = [], set()
    if head_files is None:
        H = Side(_parse_side(gitio.commit_files(root, head_commit, prefixes) if head_has else {}, "head", head_commit))
    else:
        parsed = {}
        for path, data in sorted(head_files.items()):
            if not path.startswith(prefixes):
                continue
            if isinstance(data, str):
                failed.append({"file": path, "error": data})
                continue
            try:
                parsed[path] = _parse(data)
            except SyntaxError as e:
                failed.append({"file": path, "error": str(e)})
        H = Side(parsed)
        if failed:
            committed = gitio.commit_files(root, head_commit, prefixes)
            for f in failed:  # the failed file's subjects as committed are undecidable, never "removed"
                for src in (base_files.get(f["file"]), committed.get(f["file"])):
                    if isinstance(src, bytes):
                        indeterminate |= _subjects(src)
            HC = Side({p: _parse(d) for p, d in committed.items() if isinstance(d, bytes) and _ok(d)})
            # renamed-then-broken, or moved into the broken file: anything committed but not in a parsed head file
            indeterminate |= {k for k in set(B.sig) | set(HC.sig) if k not in H.sig}
            for v, sig in list(B.sig.items()) + list(H.sig.items()):
                if any(p == "^" + IN_VIEW and o in indeterminate for p, o in sig):
                    indeterminate.add(v)
    out.update(incomplete=bool(failed), failedFiles=failed, indeterminate=sorted(indeterminate))

    items, moves = [], []
    for iri in sorted(set(B.sig) | set(H.sig)):
        if iri in indeterminate:
            continue
        b, h = B.sig.get(iri), H.sig.get(iri)
        if b == h:
            if B.files[iri] != H.files[iri]:
                moves.append({"iri": iri, "files": {"base": sorted(B.files[iri]), "head": sorted(H.files[iri])}})
            continue
        change = "added" if b is None else "removed" if h is None else "modified"
        side = B if change == "removed" else H
        it = {"iri": iri, "kind": side.kind(iri), "change": change, "types": side.types(iri), "label": side.label(iri),
              "files": {"base": sorted(B.files.get(iri, ())), "head": sorted(H.files.get(iri, ()))}}
        if change == "modified":
            it["changedPredicates"] = sorted({IN_VIEW if p == "^" + IN_VIEW else p for p, _ in b ^ h})
            if B.types(iri) != H.types(iri):
                it["typeChanged"] = True
        if it["kind"] == "relationship":
            for end, pred in (("source", SOURCE), ("target", TARGET)):
                e = side.endpoint(iri, pred)
                it[end] = {"iri": e, "label": side.label(e) or B.label(e)} if e else None
        if detail == "triples":
            it["triples"] = {"added": sorted([p, o] for p, o in (h or set()) - (b or set())),
                             "removed": sorted([p, o] for p, o in (b or set()) - (h or set()))}
        items.append(it)

    counts = _zero_counts()
    for it in items:
        counts[it["kind"]][it["change"]] += 1
    touched = {it["iri"] for it in items if it["kind"] == "element"}
    for it in items:
        if it["kind"] == "relationship":
            sides = (B,) if it["change"] == "removed" else (H,) if it["change"] == "added" else (B, H)
            for s in sides:
                for pred in (SOURCE, TARGET):
                    e = s.endpoint(it["iri"], pred)
                    if e and e not in indeterminate and (H if e in H.sig else B).kind(e) == "element":
                        touched.add(e)
    out.update(counts=counts, changedElementCount=sum(counts["element"].values()), touchedElementCount=len(touched))
    if detail != "summary":
        out.update(items=items[:MAX_ITEMS], truncated=len(items) > MAX_ITEMS, touchedElements=sorted(touched), moves=moves)
    return out


def _ok(data):
    try:
        _parse(data)
        return True
    except SyntaxError:
        return False
