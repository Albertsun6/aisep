"""governance_record_approval (docs/mcp-interface.md §5.9, amended by the 第四轮 review / ADR-016).

One call = at most one commit on `branch`, adding exactly one new file models/<slug>/governance/<record local name>.ttl
(one ApprovalRecord, plus the AgentActivity when a new one is created). evidence = headCommit (what the human saw);
baseCommit = merge-base(headCommit, main) is computed here; the time comes from the server's clock. The approval-commit
criterion of step 1 is aisep.mergecheck.approval_commit_problems — the same function the merge-time check runs."""
import hashlib, os, re, subprocess, time
from datetime import datetime, timezone

from aisep import calllog, core, gitio, mergecheck, tools, writer
from aisep.errors import AisepError

AISEP, ARCH, PROV = core.AISEP, core.ARCH, core.NS["prov"]
HEX40 = re.compile(r"^[0-9a-f]{40}\Z")  # \Z, not $: $ also matches before a trailing newline (#77)
SESSION_REF_RE = re.compile(r"[!-~]{1,200}")
ACTIVITY_KEYS = {"agent", "sessionRef", "startedAt", "endedAt", "branch", "label"}
GOV_DIR = "governance"


def _bad(field, msg, reason=None):
    d = {"rejectedFields": [field]}
    if reason:
        d["reason"] = reason
    return AisepError("INVALID_ARGUMENT", msg, details=d)


def _q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iri(ctx, x, field):
    try:
        return core.expand(ctx, x)
    except AisepError:
        raise _bad(field, f"{x!r} 不是可展开的 IRI") from None


# ---------------------------------------------------------------- input checks (§5.9 input table)

def _check_activity(activity, branch, now):
    if activity is None:
        return None
    if not isinstance(activity, dict):
        raise _bad("activity", "activity 须为对象")
    extra = sorted(set(activity) - ACTIVITY_KEYS)
    if extra:
        raise AisepError("INVALID_ARGUMENT", f"activity 不接受：{', '.join(extra)}",
                         details={"rejectedFields": [f"activity.{k}" for k in extra]})
    for k in ("agent", "sessionRef", "startedAt"):
        if not isinstance(activity.get(k), str) or not activity[k].strip():
            raise _bad(f"activity.{k}", f"activity.{k} 必填且非空")
    if not SESSION_REF_RE.fullmatch(activity["sessionRef"]):  # MCP-2: it becomes a commit trailer verbatim
        raise _bad("activity.sessionRef", "activity.sessionRef 只接受可见 ASCII 字符（不含空白与换行），最长 200 个字符")
    if activity.get("branch") is not None and activity["branch"] != branch:
        raise _bad("activity.branch", f"activity.branch {activity['branch']!r} 与 branch {branch!r} 不同")
    start = core.parse_xsd_datetime(activity["startedAt"])
    if start is None:
        raise AisepError("INVALID_DATETIME", f"activity.startedAt {activity['startedAt']!r} 不是合法的 xsd:dateTime",
                         details={"rejectedFields": ["activity.startedAt"]})
    ended_lex = activity.get("endedAt") or _ts(now)
    end = core.parse_xsd_datetime(ended_lex)
    if end is None:
        raise AisepError("INVALID_DATETIME", f"activity.endedAt {ended_lex!r} 不是合法的 xsd:dateTime",
                         details={"rejectedFields": ["activity.endedAt"]})
    if end < start:
        raise AisepError("ACTIVITY_TIME_ORDER", f"activity 结束 {ended_lex} 早于开始 {activity['startedAt']}")
    return dict(activity, endedAt=ended_lex)


def _main_short(root, main_full):
    """Branch short name of the resolved main ref: refs/heads/<b> → <b>; refs/remotes/<remote>/<b> → <b> (the remote
    name is matched against `git remote`, since both it and <b> may contain "/")."""
    if main_full.startswith("refs/heads/"):
        return main_full[len("refs/heads/"):]
    if main_full.startswith("refs/remotes/"):
        rest = main_full[len("refs/remotes/"):]
        for r in sorted(gitio.git(root, "remote")[1].split(), key=len, reverse=True):
            if rest.startswith(r + "/"):
                return rest[len(r) + 1:]
        return rest.split("/", 1)[-1]
    return main_full


def _check_branch(root, branch, main_full):
    if not isinstance(branch, str) or not branch:
        raise _bad("branch", "branch 必填")
    try:
        gitio.validate_branch_name(root, branch)
    except AisepError:
        raise _bad("branch", f"branch 须为分支短名（不接受 refs/…、标签、修订表达式）：{branch!r}") from None
    if not gitio._ref_exists(root, f"refs/heads/{branch}"):
        raise _bad("branch", f"refs/heads/{branch} 不存在（标签、远端跟踪分支都不算）")
    if branch == _main_short(root, main_full):
        raise AisepError("INVALID_ARGUMENT", f"不能直接提交到主分支 {branch}",
                         hint="发布关口：从被发布的提交 R 拉短命批准分支（approval/release-…），再对它批准（§5.9 发布关口）",
                         details={"rejectedFields": ["branch"], "reason": "protected-branch"})


def _is_ancestor(root, a, b):
    return gitio.git(root, "merge-base", "--is-ancestor", a, b)[0] == 0


# ---------------------------------------------------------------- the committed state of the branch (dedupe, names)

def _tip_side(root, tip, slug):
    return mergecheck._side(root, tip, (f"models/{slug}/",))


def _find_duplicate(side, gate, decision, approved_by, approves, evidence):
    for iri in sorted(side.sig):
        if not mergecheck._has_type(side, iri, AISEP + "ApprovalRecord"):
            continue
        r = mergecheck._record(side, iri)
        if (r["gate"], r["decision"], mergecheck._named(side, iri, AISEP + "approvedBy"), set(r["approves"]),
                r["evidence"]) == (gate, decision, [approved_by], set(approves), evidence):
            return iri
    return None


def _find_activity(side, session, head, branch):
    """第四轮复查: the reuse key is (sessionRef, headCommit, branch)."""
    for iri in sorted(side.sig):
        if mergecheck._has_type(side, iri, AISEP + "AgentActivity") and \
                (mergecheck._literal(side, iri, AISEP + "sessionRef"), mergecheck._literal(side, iri, AISEP + "headCommit"),
                 mergecheck._literal(side, iri, AISEP + "branch")) == (session, head, branch):
            return iri
    return None


def _taken_everywhere(root, slug):
    """Local names already used for subjects of models/<slug>/governance/ on any local or remote-tracking branch tip:
    a record or activity created on another branch must not get the same IRI here (they would merge into one subject).
    Two approvals in the same second on branches that have not committed yet can still collide (R4-7 residual risk)."""
    rc, out, _ = gitio.git(root, "for-each-ref", "--format=%(objectname)", "refs/heads", "refs/remotes")
    taken, base = set(), f"{core.MODEL_BASE}{slug}/"
    for tip in sorted(set(out.split())):
        for path, data in gitio.commit_files(root, tip, (f"models/{slug}/{GOV_DIR}/",)).items():
            taken.add(os.path.splitext(os.path.basename(path))[0])
            if isinstance(data, bytes):
                taken |= {s[len(base):] for s in mergecheck_subjects(data) if s.startswith(base)}
    return taken


def mergecheck_subjects(data):
    try:
        return {q.subject.value for q in core.ox.parse(data, format=core.TTL) if isinstance(q.subject, core.ox.NamedNode)}
    except SyntaxError:
        return set()


def _free(base, taken):
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}-{n}"
    return name


# ---------------------------------------------------------------- Turtle of the new file (same layout as the tests)

PREFIXES = """@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:  <http://www.w3.org/ns/prov#> .
@prefix arch:  <https://meta.linked.archi/core#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
"""


def _record_file(model_iri, rec_local, rec, act_local, act):
    head = PREFIXES + f"@prefix :      <{model_iri}> .\n"
    out = head
    if act is not None:
        out += (f"\n:{act_local} a aisep:AgentActivity ;\n    arch:inModel <{model_iri}> ;\n"
                f"    skos:prefLabel {_q(act['label'])}@zh ;\n    prov:wasAssociatedWith <{act['agent']}> ;\n"
                f"    prov:startedAtTime {_q(act['startedAt'])}^^xsd:dateTime ;\n"
                f"    prov:endedAtTime {_q(act['endedAt'])}^^xsd:dateTime ;\n"
                f"    aisep:sessionRef {_q(act['sessionRef'])} ;\n    aisep:branch {_q(act['branch'])} ;\n"
                f"    aisep:headCommit \"{act['headCommit']}\" ;\n    aisep:baseCommit \"{act['baseCommit']}\" .\n")
    objs = " , ".join(f"<{a}>" for a in rec["approves"])
    link = f" ;\n    aisep:activity <{rec['activity']}>" if rec.get("activity") else ""
    out += (f"\n:{rec_local} a aisep:ApprovalRecord ;\n    arch:inModel <{model_iri}> ;\n"
            f"    skos:prefLabel {_q(rec['prefLabel'])}@zh ;\n    aisep:gate aisep:{rec['gate']} ;\n"
            f"    aisep:decision aisep:Decision{rec['decision']} ;\n    aisep:approvedBy <{rec['approvedBy']}> ;\n"
            f"    aisep:approves {objs} ;\n    aisep:evidence \"{rec['evidence']}\" ;\n"
            f"    prov:generatedAtTime \"{rec['generatedAt']}\"^^xsd:dateTime{link} .\n")
    return out


# ---------------------------------------------------------------- worktree checks under the lock (§5.9 step 7)

def _dirty(w, head):
    """None when W's model files equal HEAD's exactly (and nothing under models/ is staged); else details."""
    committed = gitio.commit_files(w, head)
    disk = {}
    for f in gitio.model_files(w):
        try:
            disk[f] = gitio.read_file(w, f)
        except gitio.UnsafeFile as e:
            disk[f] = str(e)
    staged = gitio.git(w, "diff", "--cached", "--name-only", "-z", head, "--", "models/")[1].split("\0")
    staged = [s for s in staged if s]
    if disk == committed and not staged:
        return None
    changed = sorted({f for f in set(disk) | set(committed) if disk.get(f) != committed.get(f)} | set(staged))
    details = {"files": changed}
    if len(changed) == 1 and changed[0] not in committed and re.fullmatch(r"models/[^/]+/governance/[^/]+\.ttl", changed[0]):
        data = disk.get(changed[0])
        if isinstance(data, bytes) and b"aisep:ApprovalRecord" in data:
            details["orphanApproval"] = True
            details["recover"] = _recover(changed[0])
    return details


def _write_new(w, rel, data):
    d, name = os.path.split(rel)
    parent, sub = os.path.split(d)
    try:
        pfd = gitio.open_dir(w, parent)
    except gitio.UnsafeFile:
        raise AisepError("PATH_OUTSIDE_ROOT", f"{parent} 经过符号链接，拒绝写入") from None
    try:
        try:
            os.mkdir(sub, 0o755, dir_fd=pfd)
        except FileExistsError:
            pass
    finally:
        os.close(pfd)
    try:
        dfd = gitio.open_dir(w, d)
    except gitio.UnsafeFile:
        raise AisepError("PATH_OUTSIDE_ROOT", f"{d} 经过符号链接，拒绝写入") from None
    try:
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dfd)
        except FileExistsError:
            raise AisepError("CONFLICT", f"{rel} 已存在", retryable=True) from None
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        os.close(dfd)


def _sha_file(w, rel):
    try:
        return hashlib.sha256(gitio.read_file(w, rel)).hexdigest()
    except (OSError, gitio.UnsafeFile):
        return None


def _recover(rel):
    return f"git rm --cached -q --ignore-unmatch -- {rel} && rm -- {rel}"


def _unstage_and_maybe_delete(w, rel, written_sha, staged=True):
    """Step 8 rollback: "removed" (out of the index, file deleted), "gone" (out of the index, someone else already
    deleted the file), "kept" (out of the index, file changed by someone else and kept; written_sha None never
    deletes), "stuck" (`git rm --cached` failed, e.g. index.lock held: the file stays staged and on disk) or
    "taken" (W's HEAD already tracks the file: another commit took it; index and file are left alone)."""
    if gitio.git(w, "cat-file", "-e", f"HEAD:{rel}")[0] == 0:
        return "taken"
    if staged:
        rc, _, _ = gitio.git(w, "rm", "--cached", "-q", "-f", "--ignore-unmatch", "--", rel)  # -f: index only
        if rc != 0:
            return "stuck"
    if not os.path.lexists(os.path.join(w, rel)):
        calllog.note(files=[])  # ADR-031: the record this call wrote is no longer on disk
        return "gone"
    if written_sha is not None and _sha_file(w, rel) == written_sha:
        os.remove(os.path.join(w, rel))
        calllog.note(files=[])
        return "removed"
    return "kept"


def _taken(w, rel, what, **details):
    """details.commit stays our own approval commit A (only when there is one); C, the commit that took the record, is
    takenByCommit. Not retryable: C is not an approval commit, so a retry stops at STALE_HEAD before the dedupe."""
    c = gitio.git(w, "log", "-1", "--format=%H", "HEAD", "--", rel)[1].strip()
    return AisepError("CONFLICT", f"{what}；{rel} 已被另一个提交 {c[:7]} 带走，未回滚（不动 index 和文件）", retryable=False,
                      hint=f"不要重试（会报 STALE_HEAD）：人工检查提交 {c[:7]}（git show {c[:7]}），决定保留还是撤回其中的"
                           "记录，之后在新的 headCommit 上重新批准",
                      details=dict(details, reason="taken-by-other-commit", takenByCommit=c))


def _stuck(rel, what, **details):
    return AisepError("COMMIT_FAILED", f"{what}；回滚未完成：{rel} 仍在 index 和磁盘上",
                      hint="下一次调用会报 DIRTY_WORKTREE + orphanApproval；人工恢复：" + _recover(rel),
                      details=dict(details, orphanApproval=True, recover=_recover(rel)), retryable=False)


def _kept(code, msg, rel, **details):
    """Every "kept" exit (record file changed by someone else, kept on disk, out of the index): not retryable — an
    unchanged retry meets DIRTY_WORKTREE + orphanApproval."""
    return AisepError(code, msg, retryable=False,
                      hint=f"{rel} 已被别人改过，保留未删；人工检查后清理（{_recover(rel)}），再重新批准",
                      details=dict(details, fileKept=True, recover=_recover(rel)))


# ---------------------------------------------------------------- the tool

def _states(ctx, iris):
    st = {s.value: o.value for s, p, o, _ in ctx.built if p.value == ARCH + "approvalState"}
    short = lambda v: (v or ARCH + "Proposed").rsplit("#", 1)[-1]
    return {i: short(st.get(i)) for i in iris}


def governance_record_approval(cfg, model, gate, decision, approvedBy, approves, branch, headCommit, *,
                               expectedBaseCommit=None, slug=None, prefLabel=None, activity=None, mainRef=None,
                               repo=None, now=None, **extra):
    if extra:
        raise AisepError("INVALID_ARGUMENT", f"不接受的参数：{', '.join(sorted(extra))}（evidence、baseCommit、"
                         "generatedAt 由服务器计算）", details={"rejectedFields": sorted(extra)})
    now = now or datetime.now(timezone.utc)
    if decision not in ("Approved", "Rejected"):
        raise _bad("decision", "decision 须为 Approved 或 Rejected")
    if not isinstance(headCommit, str) or not HEX40.match(headCommit):
        raise _bad("headCommit", "headCommit 须为 40 位十六进制 commit")
    if not isinstance(approves, list) or not approves:
        raise _bad("approves", "approves 须为非空数组")
    if slug is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise _bad("slug", "slug 只接受小写字母、数字和 -")
    core.model_slug(model)  # MCP-5: the same model-name rule as the write and read tools, before any git work
    root = gitio.locate_repo(repo, cfg.allow_roots, cfg.repo)
    main_full, main_commit = gitio.resolve_main(root, mainRef or cfg.main_branch)
    _check_branch(root, branch, main_full)
    head = gitio.resolve_commit(root, headCommit)
    act_in = _check_activity(activity, branch, now)

    # step 1 (U4①): mainline commits only take GateRelease; GateRelease only on a commit of main, without activity
    if gate == "GateRelease":
        if act_in is not None:
            raise AisepError("INVALID_ARGUMENT", "发布关口不是 AI 活动，不接受 activity",
                             details={"rejectedFields": ["activity"]})
        if not _is_ancestor(root, head, main_commit):
            raise _bad("headCommit", f"GateRelease 的 headCommit {head[:7]} 不在主分支上", "release-head-not-on-main")
    elif _is_ancestor(root, mergecheck._effective_content(root, head), main_commit):
        raise _bad("gate", f"{head[:7]} 的有效内容已在主分支上，只能批 GateRelease", "mainline-head-gate-not-release")

    # step 1 (pre-check, no lock): evidence..tip has approval commits only
    tip = gitio.git(root, "rev-parse", f"refs/heads/{branch}")[1].strip()
    _stale(root, head, tip)
    base = gitio.merge_base(root, head, main_commit)
    if expectedBaseCommit is not None and expectedBaseCommit != base:
        raise AisepError("STALE_BASE", f"merge-base 已变为 {base[:7]}（调用方看到的是 {str(expectedBaseCommit)[:7]}）",
                         hint="刷新差异后再批", details={"baseCommit": base, "expectedBaseCommit": expectedBaseCommit})

    # step 3 + input checks on the headCommit snapshot (the gate the human approves is THIS content)
    with tools.loaded(cfg, repo=root, ref=head) as (ctx, _):
        mslug = core.model_slug(model)
        model_iri = f"{core.MODEL_BASE}{mslug}/"
        if not any(ctx.rel(f).startswith(f"models/{mslug}/") for f in ctx.sources):
            raise AisepError("MODEL_NOT_FOUND", f"{head[:7]} 里没有模型 {model}", details={"model": model})
        gates = {g: l for g, l in ctx.rows("SELECT ?g ?l WHERE { ?g skos:inScheme aisep:Gates ; skos:prefLabel ?l "
                                           "FILTER(LANG(?l) = 'zh') }")}
        if AISEP + str(gate) not in gates:
            raise AisepError("GATE_UNKNOWN", f"{gate!r} 不是模块声明的关口",
                             details={"candidates": sorted(g.rsplit("#", 1)[-1] for g in gates), "rejectedFields": ["gate"]})
        boss = _iri(ctx, approvedBy, "approvedBy")
        if not ctx.types(boss):
            raise AisepError("ELEMENT_NOT_FOUND", f"批准人 {core.short(boss)} 在 {head[:7]} 里不存在（不自动建人）",
                             details={"rejectedFields": ["approvedBy"]})
        if ctx.is_a(boss, AISEP + "AIAgent") or not ctx.is_a(boss, ARCH + "Stakeholder"):
            raise AisepError("APPROVER_NOT_ALLOWED", f"{core.short(boss)} 不能批准：批准人须是 arch:Stakeholder，且不能是 AI 代理",
                             details={"rejectedFields": ["approvedBy"]})
        # #73 (MVP): the approver is a Stakeholder of the approved model; a cross-model approver counts in the
        # whole-repository view but not in that model's own view (EG13). Records already on main stay as they are.
        if model_iri not in {m for (m,) in ctx.rows(f"SELECT ?m WHERE {{ <{boss}> arch:inModel ?m }}")}:
            raise AisepError("APPROVER_NOT_ALLOWED", f"{core.short(boss)} 不能批准：批准人须是被批模型 {mslug} 的干系人",
                             details={"rejectedFields": ["approvedBy"], "reason": "approver-not-in-model"})
        objs = [_iri(ctx, a, "approves") for a in approves]
        missing = [a for a in objs if not ctx.types(a)]
        if missing:
            raise AisepError("ELEMENT_NOT_FOUND", f"{', '.join(core.short(a) for a in missing)} 在 {head[:7]} 里不存在",
                             details={"missing": missing, "rejectedFields": ["approves"]})
        if act_in is not None:
            agent = _iri(ctx, act_in["agent"], "activity.agent")
            if not ctx.types(agent) or not any(core.AGENTS & set(ctx.ancestors(t)) for t in ctx.types(agent)):
                raise AisepError("AGENT_NOT_ALLOWED", f"{core.short(agent)} 不是已有的 arch:Stakeholder 或 prov:Agent",
                                 details={"rejectedFields": ["activity.agent"]})
            act_in = dict(act_in, agent=agent)
        if not any(p[1] == "L0" for p in ctx.problems):
            core.run_check(ctx)
            core.l3(ctx)
            core.l4(ctx)
        gfind = tools._findings(ctx, tools.LAYERS)
        gsum = tools._summary(gfind, time.time())
        gres = {"result": "FAIL" if gsum["violations"] else "PASS", "summary": {k: v for k, v in gsum.items() if k != "seconds"}}
        if decision == "Approved" and gres["result"] == "FAIL":
            raise AisepError("GATE_FAILED", f"{head[:7]} 上 gate FAIL（{gsum['violations']} 个违规），不能批准",
                             hint="修好违规后在新提交上重新批准；驳回（Rejected）不要求 PASS",
                             details={"findings": [f for f in gfind if f["severity"] == "Violation"]})
        gate_label = gates[AISEP + gate]
        first_label = ctx.label(objs[0]) or core.short(objs[0])
    label = prefLabel or (f"{gate_label}{'批准' if decision == 'Approved' else '驳回'}：{first_label}"
                          + (f"等 {len(objs)} 项" if len(objs) > 1 else ""))

    # step 7: the worktree of the branch, its lock, re-validation, one commit
    try:
        w = gitio.locate_worktree(root, branch, cfg.allow_roots)
    except AisepError as e:
        if e.code == "WORKTREE_NOT_FOUND" and e.details.get("branchExists") and not e.details.get("prunable"):
            raise AisepError("BRANCH_NOT_CHECKED_OUT", f"分支 {branch} 没有检出的工作区（v1 只在检出的工作区里提交）",
                             hint="git worktree add <目录> " + branch) from None
        raise
    calllog.note(worktree=w)
    with writer.lock(w):
        rc, sym, _ = gitio.git(w, "symbolic-ref", "-q", "HEAD")
        if rc != 0:
            raise AisepError("DETACHED_HEAD", f"{w} 处于 detached HEAD")
        if sym.strip() != f"refs/heads/{branch}":  # W was switched to another branch after locate_worktree
            raise AisepError("CONFLICT", f"{w} 已不在分支 {branch} 上（现为 {sym.strip()}），未提交", retryable=True,
                             details={"reason": "worktree-switched", "worktree": w, "head": sym.strip()})
        tip2 = gitio.git(w, "rev-parse", "HEAD")[1].strip()
        dirty = _dirty(w, tip2)
        if dirty:
            raise AisepError("DIRTY_WORKTREE", "工作区的模型文件与 HEAD 不一致，不把别人的改动卷进批准提交",
                             hint=("上次批准在提交前中断，留下了未提交的记录文件：" + dirty["recover"]) if dirty.get(
                                 "orphanApproval") else "先提交或清理 models/ 下的改动", details=dirty)
        _stale(root, head, tip2)
        side = _tip_side(root, tip2, mslug)
        rec_gate, rec_dec = AISEP + gate, AISEP + "Decision" + decision
        dup = _find_duplicate(side, rec_gate, rec_dec, boss, objs, head)
        if dup:
            f = sorted(side.files.get(dup, ()))
            return {"approval": {"iri": dup, "file": f[0] if f else None}, "activity": None, "evidence": head,
                    "baseCommit": base, "commit": tip2, "branch": branch, "duplicate": True, "gate": gres,
                    "derivedApprovalState": [], "findings": []}
        stamp = now.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        taken = {k[len(model_iri):] for k in side.sig if k.startswith(model_iri)} | _taken_everywhere(root, mslug)
        taken |= {os.path.splitext(n)[0] for n in os.listdir(os.path.join(w, "models", mslug, GOV_DIR))} \
            if os.path.isdir(os.path.join(w, "models", mslug, GOV_DIR)) else set()
        rec_local = _free(f"approval-{stamp}-{slug or (gate[4:].lower() + '-' + head[:7])}", taken)
        act_iri, act_new, act_local = None, None, None
        if act_in is not None:
            act_iri = _find_activity(side, act_in["sessionRef"], head, branch)
            if act_iri is None:
                act_local = _free(f"activity-{stamp}-{head[:7]}", taken | {rec_local})
                act_iri = model_iri + act_local
                act_new = dict(act_in, branch=branch, headCommit=head, baseCommit=base,
                               label=act_in.get("label") or f"AI 活动：{branch}")
        rec = {"gate": gate, "decision": decision, "approvedBy": boss, "approves": objs, "evidence": head,
               "generatedAt": _ts(now), "prefLabel": label, "activity": act_iri}
        rel = f"models/{mslug}/{GOV_DIR}/{rec_local}.ttl"
        text = _record_file(model_iri, rec_local, rec, act_local, act_new)

        # step 6: the candidate (W + the new file) adds no violation, and the new record / activity are valid
        ws = writer.Workspace(w)
        base_ctx = ws.ctx()
        core.run_check(base_ctx)
        cand = ws.ctx({rel: text.encode("utf-8")})
        if not any(p[1] == "L0" for p in cand.problems):
            core.run_check(cand)
        findings, new, _ = writer.judge(base_ctx, cand)
        bad = cand.approval_problems().get(model_iri + rec_local) or \
            (cand.activity_problems().get(act_iri) if act_new else None)
        if new or bad:
            raise AisepError("WRITE_REJECTED", "新的批准记录或活动不合法，未写入：" +
                             (new[0]["message"] if new else " / ".join(sorted(set(bad))))[:300],
                             details={"findings": [f for f in findings if f["severity"] == "Violation"],
                                      "recordProblems": sorted(set(bad or []))})
        before = _states(base_ctx, objs)
        after = _states(cand, objs)

        data = text.encode("utf-8")
        written = hashlib.sha256(data).hexdigest()
        _write_new(w, rel, data)
        calllog.note(files=[{"path": rel, "sha256Before": None, "sha256After": written}])  # ADR-031, until rolled back
        # intent-to-add only: an agent's plain `git commit` in W during this window does not take an i-t-a entry
        # (write-tree skips it); `git commit --only -- rel` then commits the file's content with the hooks as usual
        rc, _, err = gitio.git(w, "add", "--intent-to-add", "--", rel)
        if rc != 0:  # nothing staged (git add takes index.lock or fails as a whole)
            tail = "\n".join(err.strip().splitlines()[-50:])
            undone = _unstage_and_maybe_delete(w, rel, written, staged=False)
            if undone == "taken":
                raise _taken(w, rel, "git add 失败", output=tail)
            if undone == "kept":
                raise _kept("CONFLICT", f"git add 失败，且 {rel} 已被改动：保留文件", rel, output=tail)
            raise AisepError("COMMIT_FAILED", "git add 失败，已删除新建的记录文件", details={"output": tail},
                             retryable="index.lock" in tail)
        if _sha_file(w, rel) != written:
            undone = _unstage_and_maybe_delete(w, rel, None)
            if undone == "taken":
                raise _taken(w, rel, f"{rel} 在提交前被改动")
            if undone == "stuck":
                raise _stuck(rel, f"{rel} 在提交前被改动")
            if undone == "gone":  # index and worktree are clean again: an unchanged retry writes the record anew
                raise AisepError("CONFLICT", f"{rel} 在提交前被删除，已从 index 移除，未提交", retryable=True,
                                 hint="确认没有别的进程在动 governance/ 后重新调用",
                                 details={"reason": "file-deleted-before-commit"})
            raise _kept("CONFLICT", f"{rel} 在提交前被改动，已从 index 移除、保留文件", rel)
        msg = f"aisep: {gate} {decision} {rec_local}"
        cmd = [*gitio.GIT, "-C", w, "-c", "trailer.ifexists=add", "commit", "-q", "--only", "-m", msg,
               "--trailer", f"AISEP-Evidence: {head}"]
        if act_in is not None:
            cmd += ["--trailer", f"AISEP-Session: {act_in['sessionRef']}"]
        p = subprocess.run(cmd + ["--", rel], capture_output=True, text=True)
        if p.returncode != 0:  # step 8: rollback without `git restore`
            undone = _unstage_and_maybe_delete(w, rel, written)
            tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-50:])
            if undone == "taken":
                raise _taken(w, rel, "git commit 失败", output=tail)
            if undone == "stuck":
                raise _stuck(rel, "git commit 失败", output=tail)
            if undone == "kept":
                raise _kept("CONFLICT", f"提交失败，且 {rel} 已被钩子或编辑器改动：保留文件、已移出 index", rel,
                            output=tail)
            raise AisepError("COMMIT_FAILED", "git commit 失败（钩子拒绝或 index.lock 被占用），已回滚",
                             details={"output": tail}, retryable="index.lock" in tail)
        blob = _blob_id(w, data)
        a = _landed(w, root, branch, msg)
        if a is not None and gitio.git(root, "rev-parse", f"{a}:{rel}")[1].strip() != blob:
            a = None  # the tip adds our file but not what we wrote: not taken for ours
        if a is None:  # W was switched during step 6: our commit sits on another branch (or detached)
            raise _misplaced(w, root, branch, msg, rel, written, blob, tip2)
        if gitio.git(w, "rev-parse", f"{a}^")[1].strip() != tip2:  # someone committed between re-check and commit
            rc, _, _ = gitio.git(w, "update-ref", f"refs/heads/{branch}", f"{a}^", a)
            if rc != 0:
                raise AisepError("CONFLICT", f"批准提交 {a[:7]} 之上又有新提交，未自动撤回", retryable=False,
                                 hint="人工检查分支历史", details={"commit": a})
            undone = _unstage_and_maybe_delete(w, rel, written)
            if undone == "taken":
                raise _taken(w, rel, f"提交期间分支有新提交，已撤回提交 {a[:7]}", commit=a)
            if undone == "stuck":
                raise AisepError("STALE_HEAD", f"提交期间分支有新提交，已撤回提交 {a[:7]}，但 {rel} 仍在 index 和磁盘上",
                                 hint="人工恢复：" + _recover(rel), details={
                                     "reason": "concurrent-commit", "orphanApproval": True, "recover": _recover(rel)})
            if undone == "kept":
                raise _kept("STALE_HEAD", f"提交期间分支有新提交，已撤回提交 {a[:7]}；{rel} 已被改动，保留在磁盘上、已移出 index",
                            rel, reason="concurrent-commit")
            raise AisepError("STALE_HEAD", "提交期间分支有新提交，已撤回本次批准", details={"reason": "concurrent-commit"})
    return {"approval": {"iri": model_iri + rec_local, "file": rel},
            "activity": None if act_in is None else {"iri": act_iri, "reused": act_new is None},
            "evidence": head, "baseCommit": base, "commit": a, "branch": branch, "duplicate": False, "gate": gres,
            "derivedApprovalState": [{"iri": o, "before": before[o], "after": after[o]} for o in objs],
            "findings": findings}


def _adds_only(root, c, name, blob=None):
    """True when commit c adds exactly one file, models/<m>/governance/<name>, against its first parent (with blob id
    `blob` when given). rec_local is unique across all refs (_free), so such a commit is this call's; the subject is
    not used (any commit may carry it)."""
    if not c:
        return False
    rc, out, _ = gitio.git(root, "diff-tree", "-r", "--no-commit-id", "--raw", "--no-abbrev", c)
    lines = out.splitlines()
    if rc != 0 or len(lines) != 1:
        return False
    meta, _, path = lines[0].partition("\t")
    f = meta.split()
    return (len(f) == 5 and f[4] == "A" and (blob is None or f[3] == blob)
            and re.fullmatch(rf"models/[^/]+/{GOV_DIR}/{re.escape(name)}", path) is not None)


def _name(msg):
    return msg.rsplit(" ", 1)[-1] + ".ttl"


def _our_commit(w, root, msg, blob, branch, tip2):
    """SHA of this call's commit when it is not the tip of refs/heads/<branch>, checked exactly with _adds_only. Looked
    for at the tips of all branches (W switched to another branch: our commit is that tip) and, without a fixed window
    and without any reflog, along the first parents of refs/heads/<branch> and of W's HEAD back to tip2 (commits
    stacked on ours, e.g. by a post-commit hook): there it is the first-parent descendant of tip2 whose parent is tip2."""
    name, seen = _name(msg), set()
    cands = gitio.git(root, "for-each-ref", "--format=%(objectname)", "refs/heads/")[1].split()
    for start in (f"refs/heads/{branch}", gitio.git(w, "rev-parse", "-q", "--verify", "HEAD")[1].strip()):
        if start:  # oldest first: the commit right after tip2
            cands += gitio.git(root, "rev-list", "--first-parent", "--ancestry-path", "--reverse", f"{tip2}..{start}")[1].split()[:1]
    for c in cands:
        if c not in seen:
            seen.add(c)
            if _adds_only(root, c, name, blob):
                return c
    return None


def _blob_id(w, data):
    return subprocess.run([*gitio.GIT, "-C", w, "hash-object", "--stdin"], input=data,
                          capture_output=True).stdout.decode().strip()


def _landed(w, root, branch, msg):
    """The tip of refs/heads/<branch> when it is this call's commit (_adds_only), else None. Reads neither HEAD (W may
    have been switched to another branch before `git commit`) nor any reflog (may be off or expired)."""
    tip = gitio.git(root, "rev-parse", "-q", "--verify", f"refs/heads/{branch}^{{commit}}")[1].strip()
    return tip if _adds_only(root, tip, _name(msg)) else None


def _misplaced(w, root, branch, msg, rel, written, blob, tip2):
    """`git commit` moved whatever W had checked out. Take our commit (by SHA) back on the branches that point exactly
    at it, with a compare-and-swap update-ref (never refs/heads/<branch>), unstage and delete the record file,
    answer CONFLICT."""
    a = _our_commit(w, root, msg, blob, branch, tip2)
    out = gitio.git(root, "for-each-ref", "--format=%(refname)", f"--points-at={a}", "refs/heads/")[1] if a else ""
    wrong = [(r, a) for r in out.split() if r != f"refs/heads/{branch}"]  # only branches whose tip IS our commit
    details = {"reason": "worktree-switched", "worktree": w, "landedOn": [r for r, _ in wrong], "commit": a}
    if not wrong:  # not a branch tip anywhere (a commit stacked on it, or W was detached): leave index and file alone
        details["reason"] = "commit-stacked" if a else "commit-not-found"
        raise AisepError("CONFLICT", f"批准提交{' ' + a[:7] if a else ''}不在 {branch} 的顶端，也不是任何分支的顶端"
                         f"（{'之上又有新提交' if a else '找不到它'}），未自动撤回", retryable=False,
                         hint=f"人工检查 {w} 的 HEAD 与分支历史，撤回 subject 为 {msg!r} 的提交", details=details)
    stuck = []
    for ref, c in wrong:
        if gitio.git(root, "update-ref", ref, f"{c}^", c)[0] != 0:
            stuck.append(ref)
    if stuck:
        raise AisepError("CONFLICT", f"{w} 在校验期间被切走，批准提交落在 {', '.join(stuck)} 上且未能自动撤回", retryable=False,
                         hint="人工检查这些分支，撤回 subject 为 " + repr(msg) + " 的提交", details=dict(details, stuckOn=stuck))
    undone = _unstage_and_maybe_delete(w, rel, written)
    if undone == "taken":
        raise _taken(w, rel, f"{w} 在校验期间被切走，已撤回落错的提交", **details)
    if undone == "stuck":
        raise AisepError("CONFLICT", f"{w} 在校验期间被切走，已撤回落错的提交，但 {rel} 仍在 index 和磁盘上", retryable=False,
                         hint="人工恢复：" + _recover(rel), details=dict(details, orphanApproval=True, recover=_recover(rel)))
    if undone == "kept":
        raise _kept("CONFLICT", f"{w} 在校验期间被切走，已撤回落错的提交，但 {rel} 已被改动：保留文件、已移出 index", rel,
                    **details)
    raise AisepError("CONFLICT", f"{w} 在校验期间被切到别的分支，已撤回落错的批准提交，{branch} 未改动", retryable=True,
                     details=details)


def _stale(root, head, tip):
    problems = mergecheck.approval_commit_problems(root, head, tip)
    if problems:
        p = problems[0]
        raise AisepError("STALE_HEAD", "分支在 headCommit 之后有非批准提交，请刷新差异后再批",
                         details={"tip": tip, "offendingCommit": p.get("offendingCommit"), "reason": p["reason"],
                                  "problems": problems})
