"""The write path shared by the model_* write tools (docs/mcp-interface.md §5.1, §3.4).

lock -> read the workspace (§3.3 file set, safe open) -> baseline L0-L2 -> build candidate texts -> graph-equivalence
assertion -> candidate L0-L2 -> reject on NEW Violations (instance-key multiset) -> dryRun stops here -> per-file hash
check + temp/fsync/rename -> unlock. Nothing is staged or committed. Text edits are per subject block: appended blocks
for new resources, re-rendered blocks for changed ones; every other byte of a file is kept."""
import contextlib, fcntl, hashlib, os, re

import pyoxigraph as ox

from aisep import core, gitio
from aisep.errors import AisepError

TTL = ox.RdfFormat.TURTLE
LOCK_NAME = "aisep-write.lock"
XSD_STRING = core.NS["xsd"] + "string"
# governance records and declarations (#167): approval records, AI activities, AI agent declarations
GOVERNANCE_TYPES = (core.AISEP + "ApprovalRecord", core.AISEP + "AgentActivity", core.AISEP + "AIAgent")
MODEL_PATH = re.compile(r"models/[A-Za-z0-9][A-Za-z0-9_-]*(/[^/]+)+")


def sha(b):
    return hashlib.sha256(b).hexdigest() if b is not None else None


# ---------------------------------------------------------------- Turtle subject-block lexer

def statements(text):
    """[(start, end)] of the top-level statements of a Turtle text (directives included); comments and whitespace
    between statements are not part of any statement. Knows strings (short/long, both quotes), IRIs and comments."""
    out, i, n, start, depth = [], 0, len(text), None, 0
    while i < n:
        c = text[i]
        if start is None:
            if c.isspace():
                i += 1
                continue
            if c == "#":
                j = text.find("\n", i)
                i = n if j < 0 else j + 1
                continue
            start, depth = i, 0
            if re.match(r"(?i)(PREFIX|BASE)\b", text[i:i + 6]):  # SPARQL-style directive: ends after its IRI
                j = text.find(">", i)
                out.append((start, j + 1))
                start, i = None, j + 1
                continue
        if c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "<":
            i = text.find(">", i) + 1
        elif c in "\"'":
            q3 = text[i:i + 3]
            if q3 in ('"""', "'''"):
                j = i + 3
                while True:
                    j = text.find(q3, j)
                    if text[j - 1] != "\\":
                        break
                    j += 1
                i = j + 3
            else:
                j = i + 1
                while text[j] != c:
                    j += 2 if text[j] == "\\" else 1
                i = j + 1
        elif c in "[(":
            depth += 1
            i += 1
        elif c in "])":
            depth -= 1
            i += 1
        elif c == "." and depth == 0 and (i + 1 == n or text[i + 1].isspace() or text[i + 1] == "#"):
            out.append((start, i + 1))
            start, i = None, i + 1
        else:
            i += 1
    if start is not None:
        raise SyntaxError("unterminated statement")
    return out


def _is_directive(stmt):
    return bool(re.match(r"(?i)\s*(@prefix|@base|PREFIX|BASE)\b", stmt))


def file_prefixes(text):
    return {m.group(1): m.group(2) for m in re.finditer(r"(?im)^\s*@?prefix\s+([\w.-]*):\s*<([^>]*)>", text)}


def parse(text):
    return list(ox.parse(text.encode(), format=TTL))


def canon(triples):
    ds = ox.Dataset(ox.Quad(t.subject, t.predicate, t.object) for t in triples)
    ds.canonicalize(ox.CanonicalizationAlgorithm.UNSTABLE)
    return set(ds)


# ---------------------------------------------------------------- rendering

_LOCAL = re.compile(r"^[A-Za-z_][\w-]*\Z|^\Z")


def term(t, pfx):
    if isinstance(t, ox.NamedNode):
        if t.value == core.A:
            return "a"
        for k, ns in sorted(pfx.items(), key=lambda kv: -len(kv[1])):
            if t.value.startswith(ns) and _LOCAL.match(t.value[len(ns):]) and t.value != ns:
                return f"{k}:{t.value[len(ns):]}"
        return f"<{t.value}>"
    if isinstance(t, ox.Literal):
        s = '"' + t.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
        if t.language:
            return f"{s}@{t.language}"
        if t.datatype.value != XSD_STRING:
            return f"{s}^^{term(t.datatype, pfx)}"
        return s
    raise AisepError("EDIT_UNSAFE", "要渲染的块里有空白节点，不自动改写")


def render_block(subject, pairs, pfx):
    """`:s a T ;` then one predicate-object per line, indented 4 — the models/procurement layout."""
    pairs = sorted(pairs, key=lambda po: po[0].value != core.A)  # rdf:type first, otherwise keep order
    head = term(subject, pfx)
    lines = [f"{term(p, pfx)} {term(o, pfx)}" for p, o in pairs]
    return head + " " + " ;\n    ".join(lines) + " ."


def ensure_prefixes(text, needed):
    """Insert @prefix lines for needed {prefix: ns} missing from text, after its last @prefix line."""
    have = file_prefixes(text)
    missing = {k: v for k, v in needed.items() if k not in have}
    clash = [k for k in needed if k in have and have[k] != needed[k]]
    if clash:
        raise AisepError("EDIT_UNSAFE", f"文件里的前缀 {clash} 与要写入的命名空间不同", details={"prefixes": clash})
    if not missing:
        return text
    lines = "".join(f"@prefix {k}: <{v}> .\n" for k, v in sorted(missing.items()))
    last = None
    for m in re.finditer(r"(?im)^\s*@prefix\b[^\n]*\n", text):
        last = m
    if last is None:
        return lines + text
    return text[:last.end()] + lines + text[last.end():]


def used_prefixes(block, pfx):
    return {k: pfx[k] for k in set(re.findall(r"(?<![\w<\"])([\w-]*):(?=[\w-]|\s)", re.sub(r'"[^"]*"|<[^>]*>', "", block)))
            if k in pfx}


def append_block(text, block, pfx):
    text = ensure_prefixes(text, used_prefixes(block, pfx))
    if text and not text.endswith("\n"):
        text += "\n"
    return text + ("\n" if text else "") + block + "\n"


def _shares_line(text, s0, s1):
    """Another statement on the same physical line as text[s0:s1] (comments do not count)."""
    before = text[text.rfind("\n", 0, s0) + 1:s0]
    end = text.find("\n", s1)
    after = text[s1:len(text) if end < 0 else end].strip()
    return bool(before.strip()) or (bool(after) and not after.startswith("#"))


def _in_place(stmt, hit, extra, pfx):
    """Edit the statement text in place when every removed value has a same-predicate replacement whose old text
    occurs exactly once (keeps the author's layout, comments and line breaks); new values are added before the final
    '.'. None when that is not possible (the caller re-renders the statement)."""
    extra = list(extra)
    for t in hit:
        rep = next((po for po in extra if po[0].value == t.predicate.value), None)
        old = term(t.object, pfx)
        if rep is None or stmt.count(old) != 1:
            return None
        extra.remove(rep)
        stmt = stmt.replace(old, term(rep[1], pfx))
    if extra:
        stmt = stmt[:-1].rstrip() + " ;\n    " + " ;\n    ".join(f"{term(p, pfx)} {term(o, pfx)}" for p, o in extra) + " ."
    return stmt


def rewrite_blocks(text, remove, add_by_subject):
    """Re-render the statements holding a triple of `remove` or the rdf:type statement of a subject in add_by_subject
    (added pairs go there unless a statement of the same subject+predicate is being re-rendered). A statement with more
    than one named subject, or with blank nodes, is not rewritten automatically -> EDIT_UNSAFE."""
    pfx = file_prefixes(text)
    header = "".join(f"@prefix {k}: <{v}> .\n" for k, v in pfx.items())
    spans = statements(text)
    plans = []
    for s0, s1 in spans:
        stmt = text[s0:s1]
        if _is_directive(stmt):
            continue
        ts = parse(header + stmt)
        subjects = {t.subject for t in ts}
        hit = [t for t in ts if (t.subject.value, t.predicate.value, t.object) in remove]
        plans.append([s0, s1, ts, subjects, hit])
    targets = {}
    for subj, pairs in add_by_subject.items():
        for p, o in pairs:
            same_pred = [pl for pl in plans if any(t.subject.value == subj and t.predicate.value == p.value for t in pl[4])]
            typed = [pl for pl in plans if any(t.subject.value == subj and t.predicate.value == core.A for t in pl[2])]
            host = (same_pred or typed or [None])[0]
            if host is None:
                raise AisepError("EDIT_UNSAFE", f"找不到 {subj} 的主语块", details={"iri": subj})
            targets.setdefault(id(host), (host, []))[1].append((p, o))
    out, pos = [], 0
    for pl in plans:
        s0, s1, ts, subjects, hit = pl
        extra = targets.get(id(pl), (None, []))[1]
        if not hit and not extra:
            continue
        if len(subjects) != 1 or any(isinstance(x, ox.BlankNode) for t in ts for x in (t.subject, t.object)) \
                or _shares_line(text, s0, s1):
            raise AisepError("EDIT_UNSAFE", "要改的语句里有多个主语、空白节点，或与别的语句写在同一行，不自动改写，请手工编辑",
                             details={"statement": text[s0:s1][:200]})
        inplace = _in_place(text[s0:s1], hit, extra, pfx)
        if inplace is not None:
            out.append(text[pos:s0] + inplace)
            pos = s1
            continue
        subj = next(iter(subjects))
        keep, extra = [], list(extra)
        for t in ts:  # a replacement takes the place of the first removed value of its predicate
            if t in hit:
                same = next((po for po in extra if po[0].value == t.predicate.value), None)
                if same is not None:
                    keep.append(same)
                    extra.remove(same)
            else:
                keep.append((t.predicate, t.object))
        if not keep and not extra:  # nothing left: drop the statement and its line break
            out.append(text[pos:s0])
            pos = s1 + (1 if text[s1:s1 + 1] == "\n" else 0)
            continue
        out.append(text[pos:s0] + render_block(subj, keep + extra, pfx))
        pos = s1
    out.append(text[pos:])
    return "".join(out)


# ---------------------------------------------------------------- the transaction

@contextlib.contextmanager
def lock(root):
    """flock on <git-dir>/aisep-write.lock of the written worktree; LOCKED (retryable) when another process holds it."""
    rc, gd, _ = gitio.git(root, "rev-parse", "--absolute-git-dir")
    fd = os.open(os.path.join(gd.strip(), LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AisepError("LOCKED", "另一个写入正在进行（同一工作区的写锁被占用）", hint="稍后重试") from None
        yield
    finally:
        os.close(fd)


def locate_worktree_root(cfg, repo):
    path = repo or cfg.repo or os.getcwd()
    rc, out, err = gitio.git(path, "rev-parse", "--is-bare-repository")
    if (rc == 0 and out.strip() == "true") or gitio.bare_refused(err):
        raise AisepError("NOT_A_WORKTREE", f"{path} 是裸仓库，没有工作区可写")
    return gitio.locate_repo(repo, cfg.allow_roots, cfg.repo)


class Workspace:
    """The worktree's model files as read at the start of the transaction (rel path -> bytes)."""

    def __init__(self, root):
        self.root, self.data = root, {}
        for f in gitio.model_files(root):
            try:
                self.data[f] = gitio.read_file(root, f)
            except gitio.UnsafeFile as e:
                if str(e) == "symlink":  # a link anywhere in the model tree would let the write land outside the worktree
                    raise AisepError("PATH_OUTSIDE_ROOT", f"{f} 的路径经过符号链接，拒绝写入", details={"file": f}) from None
                raise AisepError("PARSE_FAILED", f"{f} 读不了（{e}），先修好再写", details={"file": f, "error": str(e)}) from None

    def ctx(self, overrides=None):
        files = dict(self.data, **(overrides or {}))
        mods = core.discover(self.root)
        return core.Ctx(mods, [os.path.join(self.root, f) for f in sorted(files)], root=self.root,
                        read=lambda p: files[os.path.relpath(p, self.root)])

    def text(self, f):
        return self.data[f].decode("utf-8") if f in self.data else ""


def _instances(ctx):
    """Instance keys (§5.1 step 5) with their structured findings, L0-L2 only."""
    from aisep.tools import _Focus, _finding
    fo = _Focus(ctx)
    res = []
    for inst in ctx.instances:
        if inst[1] not in ("L0", "build", "L1", "L2"):
            continue
        f = _finding(fo, *inst)
        key = (f["severity"], f["layer"], f["rule"], f["focus"], f["message"]) + ((f["file"],) if f["focus"] is None else ())
        res.append((key, f))
    return res


def judge(base_ctx, cand_ctx):
    """(findings of the candidate with `preexisting`, new Violations, preexisting Violation count)."""
    seen = {}
    for key, _ in _instances(base_ctx):
        seen[key] = seen.get(key, 0) + 1
    order = {"Violation": 0, "Warning": 1}
    out = []
    for key, f in sorted(_instances(cand_ctx), key=lambda kf: (order.get(kf[1]["severity"], 2), kf[1]["layer"], kf[1]["message"])):
        pre = seen.get(key, 0) > 0
        if pre:
            seen[key] -= 1
        out.append(dict(f, preexisting=pre))
    new = [f for f in out if f["severity"] == "Violation" and not f["preexisting"]]
    return out, new, sum(1 for f in out if f["severity"] == "Violation" and f["preexisting"])


def check_equivalence(ws, edits, removed, added):
    """§5.1 step 6: each candidate file's graph == old graph − planned removals + planned additions (per file)."""
    for f, new_text in edits.items():
        old = parse(ws.text(f)) if f in ws.data else []
        rem = {r for r in removed.get(f, ())}
        want = [t for t in old if (t.subject.value, t.predicate.value, t.object) not in rem] + list(added.get(f, ()))
        try:
            got = parse(new_text)
        except SyntaxError as e:
            raise AisepError("EDIT_UNSAFE", f"生成的 {f} 不能解析：{e}", details={"file": f}) from None
        if canon(got) != canon(want):
            raise AisepError("EDIT_UNSAFE", f"生成的 {f} 与计划的增删不一致，未写入", details={"file": f})


def _open_dir(root, reldir):
    try:
        return gitio.open_dir(root, reldir)
    except gitio.UnsafeFile:
        raise AisepError("PATH_OUTSIDE_ROOT", f"{reldir} 经过符号链接或不是目录，拒绝写入", details={"dir": reldir}) from None
    except FileNotFoundError:
        raise AisepError("MODEL_NOT_FOUND", f"{reldir} 不存在", details={"dir": reldir}) from None


def _before_rename(rel):  # test hook (T13): runs after the hash check, before each rename
    pass


def write_files(root, edits, before):
    """§3.4 steps 2-3: all temp files first (fsync), then per file: hash check -> rename. A failure part-way restores
    the files already renamed from the original bytes, unless they changed again (then CONFLICT, nothing touched)."""
    staged = []
    try:
        for f, text in sorted(edits.items()):
            d, name = os.path.split(f)
            dfd = _open_dir(root, d)
            tmp = f".{name}.aisep-tmp-{os.getpid()}"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dfd)
            data = text.encode("utf-8")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            staged.append((f, dfd, tmp, name, data))
        done = []
        try:
            for f, dfd, tmp, name, data in staged:
                try:
                    current = gitio.read_file(root, f)
                except FileNotFoundError:
                    current = None
                except gitio.UnsafeFile:
                    raise AisepError("PATH_OUTSIDE_ROOT", f"{f} 变成了符号链接或非普通文件", details={"file": f}) from None
                if sha(current) != sha(before.get(f)):
                    raise AisepError("CONFLICT", f"{f} 在写入期间被外部修改，未覆盖", hint="重新调用", details={"file": f})
                _before_rename(f)
                os.rename(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
                done.append((f, dfd, name, data))
            for _, dfd, _, _, _ in staged:
                os.fsync(dfd)
        except BaseException:
            # finish the rollback first, skipping (keeping) every file changed from outside since our rename: only
            # those are left half-written, and details.keptFiles lists them all, not just the first one met
            kept = []
            for f, dfd, name, data in reversed(done):
                try:
                    now = gitio.read_file(root, f)
                except OSError:
                    now = None
                if sha(now) != sha(data):
                    kept.append(f)
                    continue
                if before.get(f) is None:
                    os.unlink(name, dir_fd=dfd)
                else:
                    fd = os.open(f".{name}.aisep-restore", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644,
                                 dir_fd=dfd)
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(before[f])
                        fh.flush()
                        os.fsync(fh.fileno())
                    os.rename(f".{name}.aisep-restore", name, src_dir_fd=dfd, dst_dir_fd=dfd)
            if kept:
                raise AisepError("CONFLICT", f"回滚时发现 {', '.join(kept)} 又被改动，保留现场（其余文件已回滚）",
                                 details={"file": kept[0], "kept": True, "keptFiles": kept}, retryable=False)
            raise
    finally:
        for f, dfd, tmp, name, data in staged:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp, dir_fd=dfd)
            os.close(dfd)


def check_paths(plan):
    """Every file a plan touches is a normalised repo-relative models/<slug>/... path: no empty, '.' or '..' segment, no
    leading '/', and not under models/<slug>/governance/ (any case). The write tools build these paths from validated slugs; this is the last line before the disk."""
    for key in ("edits", "removed", "added"):
        for f in plan.get(key) or {}:
            if not isinstance(f, str) or not MODEL_PATH.fullmatch(f) or any(x in (".", "..") for x in f.split("/")):
                raise AisepError("INVALID_ARGUMENT", f"要写的路径 {f!r} 不是规范化的 models/<slug>/ 路径，未写入",
                                 details={"file": f, "reason": "path-not-normalised"})
            parts = f.split("/")
            if len(parts) > 3 and parts[2].lower() == "governance":
                # approval records are made only by Albert through the approval tool, never by a write tool or action
                raise AisepError("INVALID_ARGUMENT", f"要写的路径 {f!r} 在 models/<slug>/governance/ 下（批准记录专用），未写入",
                                 details={"file": f, "reason": "governance-directory"})


def _governance_members(ctx):
    """{model member: [protected classes it is an instance of]} over GOVERNANCE_TYPES (subclasses included)."""
    out = {}
    for x, ts in ctx.asserted.items():
        hit = sorted({k for t in ts for k in GOVERNANCE_TYPES if k in ctx.ancestors(t)})
        if hit:
            out[x] = hit
    return out


def check_governance(base_ctx, cand_ctx, removed, added):
    """Type-level guard (#167): no write tool or action adds, changes or removes a triple about an instance of a
    governance type, nor makes a resource one (directly or through a new subclass). Paths cannot carry this rule:
    models/<slug>/governance.ttl is also the default file for ordinary elements."""
    before, after = _governance_members(base_ctx), _governance_members(cand_ctx)
    touched = {s for rem in removed.values() for s, _, _ in rem} | {t.subject.value for add in added.values() for t in add}
    hits = sorted((touched & (before.keys() | after.keys())) | (before.keys() ^ after.keys()))
    if hits:
        x = hits[0]
        kinds = [core.short(k) for k in after.get(x) or before.get(x)]
        raise AisepError("PROTECTED_RESOURCE", f"{core.short(x)} 是治理记录（{'、'.join(kinds)}），写工具与动作不能新增、修改或删除",
                         hint="批准只能由批准人经 governance_record_approval 记录；AI 代理声明改动走合并前评审的 PR",
                         details={"reason": "governance-type", "iri": x, "types": kinds, "iris": hits})


def transaction(cfg, repo, build, dry_run=False):
    """Run one write. build(ws, base_ctx) -> dict(result=…, edits={rel: text}, removed={rel: {(s,p,o)}},
    added={rel: [Triple]}) or dict(result=…, edits={}) for a no-op (changed:false)."""
    root = locate_worktree_root(cfg, repo)
    with lock(root):
        ws = Workspace(root)
        base_ctx = ws.ctx()
        if any(p[1] == "L0" for p in base_ctx.problems):
            from aisep.tools import _findings
            raise AisepError("PARSE_FAILED", "工作区里有模型文件解析失败，先修好再写",
                             details={"findings": _findings(base_ctx, ("L0",))})
        core.run_check(base_ctx)
        plan = build(ws, base_ctx)
        check_paths(plan)
        result = plan["result"]
        if not plan["edits"]:
            findings, _, pre = judge(base_ctx, base_ctx)
            return dict(result, changed=False, filesChanged=[], findings=findings, preexistingViolations=pre)
        check_equivalence(ws, plan["edits"], plan.get("removed", {}), plan.get("added", {}))
        cand = ws.ctx({f: t.encode("utf-8") for f, t in plan["edits"].items()})
        check_governance(base_ctx, cand, plan.get("removed", {}), plan.get("added", {}))
        if not any(p[1] == "L0" for p in cand.problems):
            core.run_check(cand)
        findings, new, pre = judge(base_ctx, cand)
        if new:
            raise AisepError("WRITE_REJECTED", f"写入会新增 {len(new)} 个违规，已拒绝：{new[0]['message'][:200]}",
                             hint="按违规原文修改参数后重试（原文通常给出修法）", details={"findings": [f for f in findings
                                                                                     if f["severity"] == "Violation"]})
        files_changed = [{"path": f, "sha256Before": sha(ws.data.get(f)), "sha256After": sha(t.encode("utf-8"))}
                         for f, t in sorted(plan["edits"].items())]
        if not dry_run:
            write_files(root, plan["edits"], {f: ws.data.get(f) for f in plan["edits"]})
        return dict(result, changed=True, dryRun=bool(dry_run), filesChanged=files_changed, findings=findings,
                    preexistingViolations=pre)
