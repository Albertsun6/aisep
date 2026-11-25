"""Merge-time check (docs/mcp-interface.md §5.9 "合并时校验" / "合并前重算" / "批准专用 PR" / "发布关口" step 4;
ADR-014/015/016). One script for CI and for the pre-merge recompute of whoever executes the merge.

    merge_check(repo, pr_head, target_ref, *, head_ref, now, remote="origin") -> [problem]   ([] = may merge)
    classify_pr(repo, pr_head, target_ref) -> "approval-only" | "normal"
    approval_commit_problems(repo, evidence, tip) -> [problem]   (the step-1 criterion; record_approval calls it too)
    target_unchanged(repo, branch, t_used, *, remote="origin") -> bool                       (R4-11 ②)
    post_merge_verify(repo, new_head, t_used, pr_head, *, head_ref, now) -> [problem]        (R4-11 ③)
    pr_inputs(event, env) -> {"pr_head", "head_ref", "target_ref"}

problem = {"reason", "message", ["offendingCommit"], ["iri"]}; reasons as listed in
aisep-mcp/tests/test_merge_check_negatives.py. Any failing git command is a "git-error" problem (fail closed).

口径: H = pull_request.head.sha; T = the given target (CI: refs/remotes/origin/<main> right after a full fetch); M =
T + `git merge --no-ff --no-commit H` in a scratch worktree, recorded as an unreferenced commit object (parents T, H) so
the read-only tools can read it. No ref and no caller worktree is changed.

Usage (exit 0 = may merge, 1 = problems, printed as JSON):
    python -m aisep.mergecheck --pr-head <sha> --head-ref <branch> --target main        # CI / 合并前重算
    python -m aisep.mergecheck --github-event "$GITHUB_EVENT_PATH"                       # CI, inputs from the event
    python -m aisep.mergecheck --target main --target-unchanged <T used>                 # right before gh pr merge
    python -m aisep.mergecheck --post-merge <new main head> --t-used <T> --pr-head <sha> --head-ref <branch>
"""
import argparse, contextlib, functools, json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone

import pyoxigraph as ox

from aisep import core, diff, gitio, tools
from aisep.errors import AisepError

AISEP, ARCH = core.AISEP, core.ARCH
RECORD, ACTIVITY = AISEP + "ApprovalRecord", AISEP + "AgentActivity"
APPROVES, ACTIVITY_P, GATE, DECISION = AISEP + "approves", AISEP + "activity", AISEP + "gate", AISEP + "decision"
EVIDENCE, GENERATED = AISEP + "evidence", core.NS["prov"] + "generatedAtTime"
HEAD_COMMIT, BASE_COMMIT, BRANCH = AISEP + "headCommit", AISEP + "baseCommit", AISEP + "branch"
GATE_RELEASE, APPROVED = AISEP + "GateRelease", AISEP + "DecisionApproved"
IN_MODEL, SOURCE, TARGET = ARCH + "inModel", ARCH + "source", ARCH + "target"
ADR_UNEXPANDED = {core.A, IN_MODEL, core.NS["ad"] + "relatedConcept"}
HEX40 = re.compile(r"^[0-9a-f]{40}\Z")  # \Z, not $: $ also matches before a trailing newline (#77)
RECORD_FILE = re.compile(r"^models/([^/]+)/governance/([^/]+)\.ttl\Z")
TAG_DATED = re.compile(r"^release/([0-9]{8})-([0-9a-f]{7})\Z")
FUTURE_SLACK = timedelta(minutes=5)
CFG = tools.Config()
_IDENT = {"GIT_AUTHOR_NAME": "aisep-mergecheck", "GIT_AUTHOR_EMAIL": "mergecheck@aisep.invalid",
          "GIT_COMMITTER_NAME": "aisep-mergecheck", "GIT_COMMITTER_EMAIL": "mergecheck@aisep.invalid"}
_GATES = {}  # (models, modules, vendor) tree ids -> model_gate result: same content, same verdict


class _GitError(Exception):
    pass


def _git(repo, *args, ok=(0,)):
    """stdout of a git command; any exit code outside `ok` -> _GitError (fail closed, 口径 G)."""
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=dict(os.environ, **_IDENT))
    if p.returncode not in ok:
        raise _GitError(f"git {' '.join(args)} 退出码 {p.returncode}：{p.stderr.strip()[:300]}")
    return p.stdout if ok == (0,) else (p.returncode, p.stdout)


def _rev(repo, ref):
    return _git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").strip()


def _is_commit(repo, sha):
    return bool(isinstance(sha, str) and HEX40.match(sha)) and _git(repo, "cat-file", "-e", f"{sha}^{{commit}}", ok=(0, 1, 128))[0] == 0


def _is_ancestor(repo, a, b):
    rc, _ = _git(repo, "merge-base", "--is-ancestor", a, b, ok=(0, 1))
    return rc == 0


def _parents(repo, c):
    return _git(repo, "rev-list", "--parents", "-n", "1", c).split()[1:]


def _problem(reason, message, commit=None, iri=None):
    p = {"reason": reason, "message": message}
    if commit:
        p["offendingCommit"] = commit
    if iri:
        p["iri"] = iri
    return p


def _git_problem(e):
    return [_problem("git-error", f"git 命令失败，按失败处理：{e}")]


def _uniq(problems):
    seen, out = set(), []
    for p in problems:
        k = tuple(sorted(p.items()))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


# ---------------------------------------------------------------- source graphs (model_diff's grouping, §5.8)

def _side(repo, commit, prefixes=("models/",)):
    """diff.Side of the model source graph of commit. A file that is not a regular file or does not parse is left
    out here (the gate on the same snapshot reports it)."""
    parsed = {}
    for path, data in gitio.commit_files(repo, commit, prefixes).items():
        if isinstance(data, bytes):
            try:
                parsed[path] = diff._parse(data)
            except SyntaxError:
                pass
    return diff.Side(parsed)


def _has_type(side, iri, cls, classes=None):
    """classes: cls and its IRI subclasses declared on the merge context (modules/, vendor/, models/; #105); without it
    only the model-file subclass chain of side is followed."""
    ks = classes or {cls}
    return any(c in ks for t in side.types(iri) for c in side.chain(t))


def _subclasses(cls, *ctxs):
    """cls and every IRI subclass of it in the loaded contexts: the same closure the approvalState derivation uses."""
    return {cls} | {c for ctx in ctxs for (c,) in ctx.rows(
        f"SELECT DISTINCT ?c WHERE {{ ?c rdfs:subClassOf* <{cls}> FILTER(isIRI(?c)) }}")}


def _named(side, iri, pred):
    return sorted(o.value for o in side.values(iri, pred) if isinstance(o, ox.NamedNode))


def _literal(side, iri, pred):
    vs = [o.value for o in side.values(iri, pred) if isinstance(o, ox.Literal)]
    return vs[0] if len(vs) == 1 else None


def _record(side, iri):
    gates, decs, acts = _named(side, iri, GATE), _named(side, iri, DECISION), _named(side, iri, ACTIVITY_P)
    return {"iri": iri, "gate": gates[0] if gates else None, "decision": decs[0] if decs else None,
            "approves": _named(side, iri, APPROVES), "evidence": _literal(side, iri, EVIDENCE),
            "time": core.parse_xsd_datetime(_literal(side, iri, GENERATED)), "activities": acts}


def _new(S_H, S_T, cls, classes=None):
    return sorted(k for k in S_H.sig if k not in S_T.sig and _has_type(S_H, k, cls, classes))


# predicates whose rdfs:domain is aisep:ApprovalRecord or aisep:AgentActivity (aisep-core onto.ttl): the floor;
# check_bnodes adds every predicate the merge result declares with such a domain
GOV_PREDICATES = {AISEP + p for p in ("gate", "decision", "approvedBy", "approves", "evidence", "activity",
                                       "sessionRef", "branch", "baseCommit", "headCommit")}


def _governance_bnodes(repo, commit, classes, predicates=GOV_PREDICATES):
    """Blank nodes in the model sources of commit that are typed as an approval record / agent activity (classes: those
    two and every IRI subclass declared on the merge result, module or model file; a blank-node subclass in the same
    file is followed too), are themselves such a blank-node subclass, or carry one of their predicates:
    [(path, description)]. A record or activity must be an IRI model element (spec §6.6/§6.7); diff.Side folds a
    referenced blank node into its referrer's signature, so the record checks below would never see it (2026-11-22
    取证疑点一). This scan does not rely on the gate's L1 rule. A file that is not a regular file or does not parse is
    left out (the gate on the same snapshot reports it)."""
    parsed = {}
    for path, data in gitio.commit_files(repo, commit, ("models/",)).items():
        if isinstance(data, bytes):
            try:
                parsed[path] = diff._parse(data)
            except SyntaxError:
                pass
    term = lambda t: "[]" if isinstance(t, ox.BlankNode) else core.short(t) if isinstance(t, ox.NamedNode) else repr(t.value)
    out = []
    for path in sorted(parsed):
        props = {}
        for q in parsed[path]:
            if isinstance(q.subject, ox.BlankNode):
                props.setdefault(q.subject, []).append((q.predicate, q.object))
        gov = lambda o, bs: (isinstance(o, ox.NamedNode) and o.value in classes) or o in bs
        blank_classes = set()  # blank labels are per parse, so the closure stays inside this file
        while True:
            more = {b for b, po in props.items() if b not in blank_classes and any(
                p.value == core.NS["rdfs"] + "subClassOf" and gov(o, blank_classes) for p, o in po)}
            if not more:
                break
            blank_classes |= more
        for b, po in props.items():
            if b in blank_classes or any((p.value == core.A and gov(o, blank_classes)) or p.value in predicates
                                         for p, o in po):
                out.append((path, "[ " + " ; ".join(sorted(f"{term(p)} {term(o)}" for p, o in po)) + " ]"))
    return out


# ---------------------------------------------------------------- the approval-commit criterion (§5.9 step 1)

@functools.lru_cache(maxsize=4096)
def _commit_shape(repo, c):
    """None when commit c satisfies (a)(b)(c) of §5.9 step 1 against its single parent, else why not."""
    parents = _parents(repo, c)
    if len(parents) != 1:
        return f"有 {len(parents)} 个父提交"
    p = parents[0]
    raw = _git(repo, "diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", "--raw", p, c).split("\0")
    entries = [(raw[i].split(), raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
    if len(entries) != 1:
        return f"(b) 改动了 {len(entries)} 个文件，须恰好新增一个文件"
    (_, mode, _, _, status), path = entries[0]
    m = RECORD_FILE.match(path)
    if status != "A" or mode != "100644" or not m:
        return f"(b) {status} {mode} {path}：须是新增的 100644 文件 models/<slug>/governance/<名>.ttl"
    slug, stem = m.groups()
    trailers = [l.strip() for l in _git(repo, "log", "-1", "--format=%(trailers:key=AISEP-Evidence,valueonly)", c).splitlines()
                if l.strip()]
    if len(trailers) != 1:
        return f"(a) 有 {len(trailers)} 个 AISEP-Evidence trailer，须恰好一个"
    prefix = f"models/{slug}/"
    try:
        before, after = _side(repo, p, (prefix,)), _side(repo, c, (prefix,))
    except AisepError as e:  # an unreferenced, shared or cyclic blank node: the record file is not approval-shaped
        if e.code != "DIFF_BNODE_UNSUPPORTED":
            raise
        return f"(c) {e.message}：新文件里不能有空白节点（第四轮 R4-8）"
    changed = [k for k in set(before.sig) | set(after.sig) if before.sig.get(k) != after.sig.get(k)]
    if any(k in before.sig for k in changed):
        return "(c) 源图差异里有修改或删除的主语"
    recs = [k for k in changed if _has_type(after, k, RECORD)]
    acts = [k for k in changed if _has_type(after, k, ACTIVITY)]
    if len(recs) != 1 or len(acts) > 1 or len(changed) != len(recs) + len(acts):
        return f"(c) 新增主语须恰好一条批准记录、至多一个活动，实际：{sorted(changed)}"
    rec = recs[0]
    if acts and acts[0] not in _named(after, rec, ACTIVITY_P):
        return "(c) 新增的活动没有被新记录经 aisep:activity 引用"
    if trailers[0] != _literal(after, rec, EVIDENCE):
        return f"(a) AISEP-Evidence trailer {trailers[0]} 不等于新记录的 aisep:evidence"
    blob = gitio.commit_files(repo, c, (path,)).get(path)
    try:
        quads = list(ox.parse(blob, format=core.TTL))
    except (SyntaxError, TypeError):
        return "(c) 新文件解析失败"
    if any(isinstance(q.subject, ox.BlankNode) or isinstance(q.object, ox.BlankNode) for q in quads):
        return "(c) 新文件里有空白节点主语或宾语，主语只能是新记录及其活动（第四轮 R4-8）"
    if any(isinstance(q.subject, ox.Triple) or isinstance(q.object, ox.Triple) for q in quads):
        return "(c) 新文件里有 RDF 1.2 三元组项，批准记录只能是普通三元组（第四轮 R4-8）"
    file_subjects = {q.subject.value for q in quads if isinstance(q.subject, ox.NamedNode)}
    if file_subjects != {rec, *acts}:
        return f"(c) 新文件里的主语须只有新记录及其活动，实际：{sorted(file_subjects)}（第四轮 R4-8）"
    if any(after.files.get(s) != {path} for s in file_subjects):
        return "(c) 新记录或活动有三元组写在别的文件里（第四轮 R4-8）"
    if rec != f"{core.MODEL_BASE}{slug}/{stem}":
        return f"(c) 文件名 {stem}.ttl 不等于记录本地名（第四轮 R4-8）"
    return None


def _criterion(repo, commits):
    out = []
    for c in commits:
        why = _commit_shape(repo, c)
        if why:
            out.append(_problem("not-approval-commit", f"{c[:7]} 不是批准提交：{why}", commit=c))
    return out


def approval_commit_problems(repo, evidence, tip):
    """§5.9 step 1 criterion over evidence..tip: evidence is tip or an ancestor of it, no merge commit in the range,
    and every commit in it is an approval commit (a)(b)(c). [] = satisfied."""
    try:
        repo = os.fspath(repo)
        tip = _rev(repo, tip)
        if not _is_commit(repo, evidence) or not _is_ancestor(repo, evidence, tip):
            return [_problem("evidence-not-ancestor", f"evidence {evidence} 不是 {tip[:7]} 的祖先")]
        merges = _git(repo, "rev-list", "--min-parents=2", f"{evidence}..{tip}").split()
        if merges:
            return [_problem("merge-commit-in-range", f"{evidence[:7]}..{tip[:7]} 里有合并提交，须在新提交上重新批准",
                             commit=merges[-1])]
        return _criterion(repo, _git(repo, "rev-list", "--reverse", f"{evidence}..{tip}").split())
    except _GitError as e:
        return _git_problem(e)


def _effective_content(repo, c):
    """Follow first parents from c, skipping approval commits (核对轮 4)."""
    while True:
        ps = _parents(repo, c)
        if len(ps) != 1 or _commit_shape(repo, c):
            return c
        c = ps[0]


# ---------------------------------------------------------------- comparison scope of an approved object (核对轮 3)

def _kind(x, *ctxs):
    for ctx in ctxs:
        anc = {a for t in ctx.types(x) for a in ctx.ancestors(t)}
        if ARCH + "Model" in anc:
            return "model"
        if core.NS["ad"] + "Decision" in anc:
            return "adr"
        if anc:
            return "element"
    return "element"


def _scope(side, x, kind):
    keys = {x}
    if kind == "model":
        members = {s for s, ts in side.triples.items() if any(p == IN_MODEL and getattr(o, "value", None) == x for p, o in ts)
                   and not _has_type(side, s, RECORD) and not _has_type(side, s, ACTIVITY)}
        rels = {s for s, ts in side.triples.items() if any(p in (SOURCE, TARGET) and getattr(o, "value", None) in members
                                                            for p, o in ts)}
        keys |= members | rels
    elif kind == "adr":
        keys |= {o.value for p, o in side.triples.get(x, ()) if isinstance(o, ox.NamedNode) and p not in ADR_UNEXPANDED
                 and o.value in side.sig}
    return {k: frozenset(side.sig[k]) for k in keys if k in side.sig}


# ---------------------------------------------------------------- the analysis of one (H, T, M)

@contextlib.contextmanager
def _merged(repo, t, h):
    """M = T + `git merge --no-ff --no-commit H` in a scratch worktree, as an unreferenced commit (parents T, H);
    None on a merge conflict. The scratch worktree is removed again."""
    tmp = tempfile.mkdtemp(prefix="aisep-mergecheck-")
    w = os.path.join(tmp, "m")
    try:
        _git(repo, "-c", "core.hooksPath=/dev/null", "worktree", "add", "-q", "--detach", w, t)
        try:
            rc, _ = _git(w, "merge", "-q", "--no-ff", "--no-commit", h, ok=(0, 1))
            if rc != 0:
                if _git(w, "diff", "--name-only", "--diff-filter=U").strip():
                    yield None
                    return
                raise _GitError(f"git merge {h[:7]} 失败")
            tree = _git(w, "write-tree").strip()
            yield _git(repo, "commit-tree", tree, "-p", t, "-p", h, "-m", "aisep mergecheck: M").strip()
        finally:
            _git(repo, "worktree", "remove", "--force", w, ok=(0, 128))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _git(repo, "worktree", "prune", ok=(0, 128))


def _gate(repo, commit):
    key = tuple(_git(repo, "rev-parse", f"{commit}:models", f"{commit}:modules", f"{commit}:vendor").split())
    if key not in _GATES:
        _GATES[key] = tools.model_gate(CFG, repo=repo, ref=commit)
    return _GATES[key]


def _gate_message(g):
    v = [f["message"] for f in g["findings"] if f["severity"] == "Violation"][:3]
    return f"{g['summary']['violations']} 条违规：" + " / ".join(v)


class _Analysis:
    def __init__(self, repo, h, t, m, now, stack):
        self.repo, self.H, self.T, self.M, self.now = repo, h, t, m, now
        self.S_T, self.S_H, self.S_M = _side(repo, t), _side(repo, h), _side(repo, m)
        self.ctx_T = stack.enter_context(tools.loaded(CFG, repo, ref=t))[0]
        self.ctx_M = stack.enter_context(tools.loaded(CFG, repo, ref=m))[0]
        self._sides = {t: self.S_T, h: self.S_H, m: self.S_M}
        # records / activities by the class closure of T and M, as the derivation sees them (#105)
        self.rec_classes = _subclasses(RECORD, self.ctx_T, self.ctx_M)
        self.act_classes = _subclasses(ACTIVITY, self.ctx_T, self.ctx_M)
        self.new_records = [_record(self.S_H, r) for r in _new(self.S_H, self.S_T, RECORD, self.rec_classes)]
        self.new_activities = _new(self.S_H, self.S_T, ACTIVITY, self.act_classes)
        illegal = self.ctx_M.approval_problems()
        legal = [r for r in self.new_records if r["iri"] not in illegal]
        self.selected = [r for r in legal if not any(
            o is not r and o["gate"] == r["gate"] and set(o["approves"]) >= set(r["approves"]) and o["time"] and r["time"]
            and o["time"] > r["time"] for o in legal)]
        self.passed = set()  # selected records passing every check-3 item
        self.range_ok = set()  # selected records whose evidence..H satisfies the criterion
        self.approval_only = _approval_only(repo, h, t, self.new_records, self.new_activities)

    def side(self, c):
        if c not in self._sides:
            self._sides[c] = _side(self.repo, c)
        return self._sides[c]

    # blank-node records / activities (2026-11-22 取证疑点一): fail closed, independent of the gate
    def check_bnodes(self, commits=None):
        classes = {c for (c,) in self.ctx_M.rows("""SELECT DISTINCT ?c WHERE { ?c rdfs:subClassOf* ?k
                   VALUES ?k { aisep:ApprovalRecord aisep:AgentActivity } FILTER(isIRI(?c)) }""")} | {RECORD, ACTIVITY}
        predicates = {p for (p,) in self.ctx_M.rows("""SELECT DISTINCT ?p WHERE { ?p rdfs:domain ?d .
                      ?d rdfs:subClassOf* ?k VALUES ?k { aisep:ApprovalRecord aisep:AgentActivity } FILTER(isIRI(?p)) }""")
                      } | GOV_PREDICATES
        found = {}
        for name, c in commits or (("PR 头 H", self.H), ("合并结果 M", self.M)):
            for path, desc in _governance_bnodes(self.repo, c, classes, predicates):
                found.setdefault((path, desc), []).append(f"{name}（{c[:7]}）")
        return [_problem("governance-blank-node", f"{'、'.join(where)} 的 {path} 里有空白节点形式的批准记录或活动 {desc}："
                         "批准记录和活动必须是带 arch:inModel 的 IRI（规范 §6.6、§6.7），合并检查无法核对它，按失败处理")
                for (path, desc), where in sorted(found.items())]

    # check 1 (第三轮 E)
    def check1(self):
        out = []
        for x in sorted(self.S_T.sig):
            if not (_has_type(self.S_T, x, RECORD, self.rec_classes) or _has_type(self.S_T, x, ACTIVITY, self.act_classes)):
                continue
            if x not in self.S_M.sig:
                out.append(_problem("governance-record-removed", "目标分支上已有的治理记录被删除（批准只能新增）", iri=x))
            elif self.S_M.sig[x] != self.S_T.sig[x]:
                out.append(_problem("governance-record-modified", "目标分支上已有的治理记录被修改（批准只能新增）", iri=x))
        return out

    # check 3 (per selected record) + approval-only / release rules
    def check3(self):
        out, ranges = [], {}
        for r in self.selected:
            ev, iri, mine = r["evidence"], r["iri"], []
            if not (ev and HEX40.match(ev)):
                out.append(_problem("evidence-not-commit", f"evidence {ev!r} 不是 40 位 commit id", iri=iri))
                continue
            if r["time"] and r["time"] > self.now + FUTURE_SLACK:
                mine.append(_problem("generated-at-future", f"prov:generatedAtTime 晚于检查时间 5 分钟以上", iri=iri))
            if not _is_commit(self.repo, ev):
                out += mine + [_problem("evidence-not-ancestor", f"evidence {ev} 不是本仓库里的提交", iri=iri)]
                continue
            S_ev = self.side(ev)
            for x in r["approves"]:
                if x not in S_ev.sig:
                    mine.append(_problem("approves-missing-at-evidence", f"{core.short(x)} 在 evidence {ev[:7]} 里不存在", iri=x))
            if r["decision"] == APPROVED:
                try:
                    g = _gate(self.repo, ev)
                    if g["result"] != "PASS":
                        mine.append(_problem("evidence-gate-failed", f"evidence {ev[:7]} 的 gate FAIL：{_gate_message(g)}", iri=iri))
                except AisepError as e:
                    mine.append(_problem("evidence-gate-failed", f"evidence {ev[:7]} 跑不了 gate：{e}", iri=iri))
            if ev not in ranges:
                ranges[ev] = approval_commit_problems(self.repo, ev, self.H)
            if ranges[ev]:
                mine += [dict(p, iri=iri) if "offendingCommit" not in p else p for p in ranges[ev]]
            else:
                self.range_ok.add(iri)
            on_main = _is_ancestor(self.repo, _effective_content(self.repo, ev), self.T)
            if r["gate"] == GATE_RELEASE:
                if not _is_ancestor(self.repo, ev, self.T):
                    mine.append(_problem("release-head-not-on-main", f"发布批准的 evidence {ev[:7]} 不在目标分支上", iri=iri))
                if not self.approval_only:
                    mine.append(_problem("release-in-normal-pr", "GateRelease 记录只能出现在批准专用 PR 里", iri=iri))
            elif on_main:
                mine.append(_problem("mainline-head-gate-not-release",
                                     f"evidence {ev[:7]} 的有效内容提交在目标分支上，只能批 GateRelease", iri=iri))
            if on_main and r["activities"]:
                mine.append(_problem("activity-on-mainline-approval", "主线提交上的批准不能带 aisep:activity", iri=iri))
            if not mine:
                self.passed.add(iri)
            out += mine
        return out

    # check 4 (第三轮 Q, G4-6)
    def check4(self, head_ref):
        out = []
        recomputed = {a for r in self.selected for a in r["activities"]}
        for a in self.new_activities:
            branches = [o.value for o in self.S_H.values(a, BRANCH) if isinstance(o, ox.Literal)]
            if branches != [head_ref]:
                out.append(_problem("activity-branch-mismatch", f"aisep:branch {branches} 不等于 PR 源分支 {head_ref}", iri=a))
            if a not in recomputed:
                continue
            head, base = _literal(self.S_H, a, HEAD_COMMIT), _literal(self.S_H, a, BASE_COMMIT)
            if not _is_commit(self.repo, head):
                out.append(_problem("activity-base-mismatch", f"aisep:headCommit {head} 不是提交", iri=a))
                continue
            rc, mb = _git(self.repo, "merge-base", "--all", head, self.T, ok=(0, 1))
            mb = mb.split()
            if len(mb) > 1:
                out.append(_problem("ambiguous-merge-base", f"merge-base({head[:7]}, T) 有 {len(mb)} 个", iri=a))
            elif mb != [base]:
                out.append(_problem("activity-base-mismatch", f"aisep:baseCommit {base} ≠ 重算的 {mb}", iri=a))
        return out

    # check 5 (U3)
    def check5(self):
        g = _gate(self.repo, self.M)
        return [] if g["result"] == "PASS" else [_problem("merge-result-gate-failed", f"合并结果 gate FAIL：{_gate_message(g)}")]

    def _effective_on_m(self, x):
        """Records (legal on M) at the latest instant about x, and whether they agree (§6.6 derivation inputs)."""
        illegal = self.ctx_M.approval_problems()
        by_t = {}
        for rec, ts, dec in self.ctx_M.rows(f"""SELECT ?rec ?time ?dec WHERE {{ GRAPH ?g {{ ?rec aisep:approves <{x}> }}
                {self.ctx_M.src_graph_filter()} ?rec a/rdfs:subClassOf* aisep:ApprovalRecord .
                OPTIONAL {{ ?rec prov:generatedAtTime ?time }} OPTIONAL {{ ?rec aisep:decision ?dec }} }}"""):
            t = core.parse_xsd_datetime(ts)
            if rec not in illegal and t is not None:
                by_t.setdefault(t, {})[rec] = dec
        if not by_t:
            return set(), False
        latest = by_t[max(by_t)]
        return set(latest), len(set(latest.values())) == 1

    # check 6 (U1, 核对轮 1/2/3, R4-2, R4-3, R4-6, G4-2)
    def check6(self):
        out = []
        approved = sorted(str(s.value) for s, p, o, _ in self.ctx_T.built
                          if p.value == ARCH + "approvalState" and o.value == ARCH + "Approved")
        covers = {r["iri"]: r for r in self.selected if r["decision"] == APPROVED and r["iri"] in self.passed}
        for x in approved:
            kind = _kind(x, self.ctx_T, self.ctx_M)
            before, after = _scope(self.S_T, x, kind), _scope(self.S_M, x, kind)
            if before == after:
                continue
            if x in self.S_T.sig and x not in self.S_M.sig:
                out.append(_problem("approved-element-removed", f"{core.short(x)} 在目标分支上是 Approved，不能删除，"
                                    "改用 owl:deprecated + dcterms:isReplacedBy 退役", iri=x))
                continue
            mine = {i for i, r in covers.items() if x in r["approves"]}
            effective, agree = self._effective_on_m(x)
            if not mine:
                why = "本 PR 没有新增覆盖它的 Approved 批准记录"
            elif not (agree and effective & mine):
                why = "覆盖记录在合并结果里不是它的生效记录（须晚于已有批准）"
            else:
                continue
            out.append(_problem("unapproved-change-to-approved", f"{core.short(x)} 在目标分支上是 Approved 且被改动：{why}",
                                iri=x))
        return out

    # check 7 (核对轮 5, 第三轮 I)
    def check7(self):
        out = []
        for r in self.selected:
            if r["iri"] not in self.range_ok:  # evidence..H already rejected: the drift would repeat that verdict
                continue
            S_ev = self.side(r["evidence"])
            for x in r["approves"]:
                kind = _kind(x, self.ctx_M, self.ctx_T)
                if _scope(S_ev, x, kind) != _scope(self.S_M, x, kind):
                    out.append(_problem("approved-content-drifted", f"{core.short(x)} 在 evidence {r['evidence'][:7]} 与"
                                        "合并结果里不同，须在新提交上重新批准", iri=x))
        return out

    # 发布关口 step 4
    def release_tags(self, remote):
        wanted = [r for r in self.selected if r["gate"] == GATE_RELEASE and r["decision"] == APPROVED
                  and r["evidence"] and HEX40.match(r["evidence"])]
        if not wanted:
            return []
        refs = {}
        for line in _git(self.repo, "ls-remote", "--tags", remote).splitlines():
            sha, ref = line.split("\t")
            if ref.endswith("^{}"):
                refs[ref[:-3]] = sha  # peeled value wins
            else:
                refs.setdefault(ref, sha)
        out = []
        for r in wanted:
            ev, named = r["evidence"], []
            for ref, sha in refs.items():
                name = ref[len("refs/tags/"):]
                m = TAG_DATED.match(name)
                if (m and m.group(2) == ev[:7]) or (name.startswith("release/v") and len(name) > len("release/v")):
                    named.append((name, sha))
            if any(sha == ev for _, sha in named):
                continue
            if any(TAG_DATED.match(n) for n, _ in named):
                out.append(_problem("release-tag-mismatch", f"release 标签剥离后不等于 evidence {ev[:7]}", iri=r["iri"]))
            else:
                out.append(_problem("release-tag-missing", f"远端没有指向 {ev[:7]} 的合规 release 标签", iri=r["iri"]))
        return out


def _approval_only(repo, h, t, new_records, new_activities):
    """批准专用 PR rules 1-4 (R2-15, 第三轮 B, U4②)."""
    commits = _git(repo, "rev-list", "--reverse", h, f"^{t}").split()
    if not commits or _git(repo, "rev-list", "--min-parents=2", h, f"^{t}").strip() or _criterion(repo, commits):
        return False
    if not new_records:
        return False
    referenced = {a for r in new_records for a in r["activities"]}
    if any(a not in referenced for a in new_activities):
        return False
    for r in new_records:
        ev = r["evidence"]
        if _is_commit(repo, ev) and _is_ancestor(repo, _effective_content(repo, ev), t):
            if r["gate"] != GATE_RELEASE or r["activities"]:
                return False
    return True


def _prepare(repo, pr_head, target_ref):
    repo = os.path.abspath(os.fspath(repo))
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != "false":
        raise _GitError("浅克隆：rev-list / merge-base 结论不可信（须 fetch-depth: 0）")
    return repo, _rev(repo, pr_head), _rev(repo, target_ref)


def _run(fn):
    try:
        return _uniq(fn())
    except _GitError as e:
        return _git_problem(e)
    except AisepError as e:
        return [_problem("git-error" if e.code in ("REF_NOT_FOUND", "NOT_A_GIT_REPO") else "check-error",
                         f"{e.code}：{e}")]


# ---------------------------------------------------------------- public entry points

def merge_check(repo, pr_head, target_ref, *, head_ref, now, remote="origin"):
    def run():
        r, h, t = _prepare(repo, pr_head, target_ref)
        with _merged(r, t, h) as m, contextlib.ExitStack() as stack:
            if m is None:
                return [_problem("merge-conflict", f"在 T={t[:7]} 上合并 {h[:7]} 冲突，请先解决冲突")]
            try:
                a = _Analysis(r, h, t, m, now, stack)
            except AisepError as e:
                if e.code != "DIFF_BNODE_UNSUPPORTED":
                    raise
                return _bnode_fallback(r, h, t, e)
            return (a.check_bnodes() + a.check1() + a.check3() + a.check4(head_ref) + a.check5() + a.check6()
                    + a.check7() + a.release_tags(remote))
    return _run(run)


def _bnode_fallback(repo, h, t, e):
    """A source graph with an unreferenced, shared or cyclic blank node cannot be diffed (DIFF_BNODE_UNSUPPORTED), so
    no record can be read off it. Fail closed with a structured answer: the error itself, plus the criterion over
    every commit in t..h that claims to be an approval commit (carries an AISEP-Evidence trailer)."""
    out = [_problem("check-error", f"{e.code}：{e}")]
    for c in _git(repo, "rev-list", "--reverse", h, f"^{t}").split():
        if _git(repo, "log", "-1", "--format=%(trailers:key=AISEP-Evidence,valueonly)", c).strip():
            out += _criterion(repo, [c])
    return out


def classify_pr(repo, pr_head, target_ref):
    repo, h, t = _prepare(repo, pr_head, target_ref)
    S_H, S_T = _side(repo, h), _side(repo, t)
    recs = [_record(S_H, x) for x in _new(S_H, S_T, RECORD)]
    return "approval-only" if _approval_only(repo, h, t, recs, _new(S_H, S_T, ACTIVITY)) else "normal"


def target_unchanged(repo, branch, t_used, *, remote="origin"):
    ref = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    try:
        out = _git(os.fspath(repo), "ls-remote", remote, ref).split()
    except _GitError:
        return False
    return bool(out) and out[0] == t_used


def post_merge_verify(repo, new_head, t_used, pr_head, *, head_ref, now):
    def run():
        r = os.path.abspath(os.fspath(repo))
        m, h = _rev(r, new_head), _rev(r, pr_head)
        parents = _parents(r, m)
        if parents == [_rev(r, t_used), h]:
            return []
        with contextlib.ExitStack() as stack:
            a = _Analysis(r, h, parents[0] if parents else m, m, now, stack)
            a.check3()  # covers must pass check 3; its own verdict was given before the merge
            return a.check_bnodes((("合并后的新头", m),)) + a.check5() + a.check6() + a.check7()
    return _run(run)


def pr_inputs(event, env):
    """CI inputs from the pull_request event: the PR head is pull_request.head.sha, never GITHUB_SHA (the platform's
    test merge commit, possibly built on an old target head); T is the freshly fetched remote main (口径 F, G, R4-10)."""
    pr = event["pull_request"]
    return {"pr_head": pr["head"]["sha"], "head_ref": pr["head"]["ref"],
            "target_ref": f"refs/remotes/origin/{pr['base']['ref']}"}


def _target(repo, name):
    if name.startswith("refs/") or HEX40.match(name):
        return name
    return gitio.resolve_main(repo, name)[0]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m aisep.mergecheck", description="AISEP 合并时校验（§5.9）")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--pr-head")
    ap.add_argument("--head-ref", help="PR 源分支短名（pull_request.head.ref）")
    ap.add_argument("--target", default="main", help="目标分支（短名解析为远端跟踪分支）或 ref / commit")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--github-event", help="GitHub 事件 JSON（CI）：从中取 pr-head / head-ref / target")
    ap.add_argument("--now", help="检查时间（xsd:dateTime），缺省为当前 UTC")
    ap.add_argument("--target-unchanged", metavar="T_USED", help="只做 R4-11 ②：远端目标分支仍等于 T_USED 则退出 0")
    ap.add_argument("--post-merge", metavar="NEW_HEAD", help="只做 R4-11 ③：合并后核验")
    ap.add_argument("--t-used", help="--post-merge 时：重算用的 T")
    a = ap.parse_args(argv)
    repo = gitio.locate_repo(a.repo)
    now = core.parse_xsd_datetime(a.now) if a.now else datetime.now(timezone.utc)
    if a.target_unchanged:
        branch = a.target[len("refs/heads/"):] if a.target.startswith("refs/heads/") else a.target
        ok = target_unchanged(repo, branch, a.target_unchanged, remote=a.remote)
        print(json.dumps({"targetUnchanged": ok}))
        return 0 if ok else 1
    if a.github_event:
        with open(a.github_event, encoding="utf-8") as f:
            inp = pr_inputs(json.load(f), dict(os.environ))
        a.pr_head, a.head_ref, a.target = inp["pr_head"], inp["head_ref"], inp["target_ref"]
    if not a.pr_head or not a.head_ref:
        ap.error("需要 --pr-head 与 --head-ref（或 --github-event）")
    if a.post_merge:
        if not a.t_used:
            ap.error("--post-merge 需要 --t-used")
        problems = post_merge_verify(repo, a.post_merge, a.t_used, a.pr_head, head_ref=a.head_ref, now=now)
        print(json.dumps({"newHead": a.post_merge, "problems": problems}, ensure_ascii=False, indent=2))
        return 1 if problems else 0
    target = _target(repo, a.target)
    try:
        t = _rev(repo, target)
    except _GitError as e:
        print(json.dumps({"problems": _git_problem(e)}, ensure_ascii=False, indent=2))
        return 1
    problems = merge_check(repo, a.pr_head, t, head_ref=a.head_ref, now=now, remote=a.remote)
    try:
        cls = None if problems and problems[0]["reason"] == "git-error" else classify_pr(repo, a.pr_head, t)
    except AisepError:  # e.g. DIFF_BNODE_UNSUPPORTED: already reported in problems (merge_check fails closed)
        cls = None
    print(json.dumps({"target": target, "T": t, "H": a.pr_head, "classification": cls,
                      "problems": problems}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
