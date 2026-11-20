"""Git topology builders for the merge-time check tests (docs/mcp-interface.md §5.9, §11 T38–T40, T43).

Everything lives in a tmp_path repo plus a local bare repo used as `origin` (release tags are pushed there, never to
GitHub). The builders write approval commits in exactly the shape `governance_record_approval` produces (§5.9 step 5/7):
one new file `models/procurement/governance/<local>.ttl`, mode 100644, one ApprovalRecord (+ at most one AgentActivity
it references), one `AISEP-Evidence` trailer. Deviations (forged trailer, symlink, two records …) are explicit options.
"""
import os, shutil, subprocess
from datetime import datetime, timezone

M = "https://aisep.example/model/procurement/"
GOV = "models/procurement/governance"
AM4 = "models/procurement/am4.ttl"
NOW = "2026-11-20T12:00:00Z"  # injected clock for merge_check(now=…); new records are generated before it

PREFIXES = """@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:  <http://www.w3.org/ns/prov#> .
@prefix arch:  <https://meta.linked.archi/core#> .
@prefix am4:   <https://meta.linked.archi/archimate4/onto#> .
@prefix aisep: <https://aisep.example/ont/aisep#> .
@prefix :      <https://aisep.example/model/procurement/> .
"""


def stamp(at):
    """yyyymmddHHMMSS of an xsd:dateTime, normalised to UTC (record / activity IRIs, §5.9 step 5, 第四轮 R4-7)."""
    d = datetime.fromisoformat(at.replace("Z", "+00:00"))
    return (d.astimezone(timezone.utc) if d.tzinfo else d).strftime("%Y%m%d%H%M%S")


def git(cwd, *args, check=True, env=None):
    p = subprocess.run(["git", "-C", str(cwd), "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        raise AssertionError(f"fixture: git {' '.join(args)} failed: {p.stderr}")
    return p.stdout.strip()


# ------------------------------------------------------------------ turtle snippets

def element_ttl(local, label, typ="am4:BusinessObject"):
    return f"\n:{local} a {typ} ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"{label}\"@zh .\n"


def activity_ttl(local, head, base, branch, session="ao-session-1", agent=":codingBot",
                 started="2026-11-20T09:00:00Z", ended="2026-11-20T10:00:00Z"):
    return (f"\n:{local} a aisep:AgentActivity ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"AI 活动：{branch}\"@zh ;\n"
            f"    prov:wasAssociatedWith {agent} ;\n"
            f"    prov:startedAtTime \"{started}\"^^xsd:dateTime ;\n    prov:endedAtTime \"{ended}\"^^xsd:dateTime ;\n"
            f"    aisep:sessionRef \"{session}\" ;\n    aisep:branch \"{branch}\" ;\n"
            f"    aisep:headCommit \"{head}\" ;\n    aisep:baseCommit \"{base}\" .\n")


def record_ttl(local, gate, approves, evidence, at="2026-11-20T11:00:00Z", decision="Approved",
               approved_by=":chiefArchitect", activity=None):
    objs = ", ".join(a if a.startswith("<") else f":{a}" for a in approves)
    act = f" ;\n    aisep:activity :{activity}" if activity else ""
    return (f"\n:{local} a aisep:ApprovalRecord ;\n    arch:inModel <{M}> ;\n    skos:prefLabel \"{gate}{decision}\"@zh ;\n"
            f"    aisep:gate aisep:{gate} ;\n    aisep:decision aisep:Decision{decision} ;\n"
            f"    aisep:approvedBy {approved_by} ;\n    aisep:approves {objs} ;\n"
            f"    aisep:evidence \"{evidence}\" ;\n    prov:generatedAtTime \"{at}\"^^xsd:dateTime{act} .\n")


# ------------------------------------------------------------------ the repository

class Topo:
    """A tmp repo whose `main` is the procurement example plus a baseline (see `baseline`), and a bare `origin`."""

    def __init__(self, template, tmp_path):
        self.tmp = tmp_path
        self.root = tmp_path / "repo"
        self.origin = tmp_path / "origin.git"
        shutil.copytree(template, self.root)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "user.email", "t@example.invalid")
        self.c0 = self.commit_all("procurement")
        self.baseline()
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True, capture_output=True)
        git(self.root, "remote", "add", "origin", str(self.origin))
        self.push("main")

    # -- low level
    def git(self, *a, **kw):
        return git(self.root, *a, **kw)

    def rev(self, ref="HEAD"):
        return self.git("rev-parse", ref)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as f:
            return f.read()

    def write(self, rel, text, mode="w"):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), mode, encoding="utf-8") as f:
            f.write(text)

    def commit_all(self, msg, trailers=(), date=None):
        self.git("add", "-A")
        # trailer.ifexists=add: git's default (addIfDifferentNeighbor) folds two identical trailers into one, which
        # would silently turn the "two AISEP-Evidence trailers" deviation into a valid approval commit
        args = ["-c", "trailer.ifexists=add", "commit", "-q", "-m", msg] + [x for t in trailers for x in ("--trailer", t)]
        env = None
        if date:
            env = dict(os.environ, GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
        git(self.root, *args, env=env)
        return self.rev()

    def trailer_count(self, commit, key="AISEP-Evidence"):
        return len(self.git("log", "-1", f"--format=%(trailers:key={key},valueonly)", commit).split())

    def checkout(self, ref, new=None):
        self.git("checkout", "-q", *(["-b", new] if new else []), ref)

    def push(self, *refs):
        self.git("push", "-q", "origin", *refs)

    # -- baseline on main (T): an approved standalone element, a Rejected record, an agent stakeholder
    def baseline(self):
        self.write(AM4, element_ttl("auditTrail", "审计轨迹"), "a")
        self.write("models/procurement/governance.ttl",
                   "\n:codingBot a arch:Stakeholder ;\n    arch:inModel <" + M + "> ;\n    skos:prefLabel \"编码代理\"@zh .\n", "a")
        self.base_activity = M + f"activity-20261119100000-{self.c0[:7]}"
        self.write(f"{GOV}/approval-20261119120000-architecture-audittrail.ttl", PREFIXES + activity_ttl(
            f"activity-20261119100000-{self.c0[:7]}", self.c0, self.c0, "feat/audit", session="ao-session-0",
            started="2026-11-19T09:00:00Z", ended="2026-11-19T10:00:00Z") + record_ttl(
            "approval-20261119120000-architecture-audittrail", "GateArchitecture", ["auditTrail"], self.c0,
            at="2026-11-19T12:00:00Z", activity=f"activity-20261119100000-{self.c0[:7]}"))
        self.base_record = M + "approval-20261119120000-architecture-audittrail"
        self.base_rejected = M + "approval-20261119130000-requirements-rejected"
        self.write(f"{GOV}/approval-20261119130000-requirements-rejected.ttl", PREFIXES + record_ttl(
            "approval-20261119130000-requirements-rejected", "GateRequirements", ["supplier"], self.c0,
            at="2026-11-19T13:00:00Z", decision="Rejected"))
        self.base = self.commit_all("baseline: approved :auditTrail, rejected :supplier")

    # -- model edits (content commits)
    def add_element(self, local, label, msg=None, rel=AM4):
        self.write(rel, (PREFIXES if not os.path.exists(self.path(rel)) else "") + element_ttl(local, label), "a")
        return self.commit_all(msg or f"add {local}")

    def relabel(self, local, new_label, msg=None):
        """Change the @zh prefLabel of :local in am4.ttl (a `modified` element)."""
        txt = self.read(AM4)
        head = f":{local} a "
        i = txt.index(head)
        j = txt.index("skos:prefLabel \"", i) + len("skos:prefLabel \"")
        k = txt.index("\"@zh", j)
        self.write(AM4, txt[:j] + new_label + txt[k:])
        return self.commit_all(msg or f"relabel {local}")

    def remove_block(self, local, rel=AM4, msg=None):
        """Delete the subject block `:local a …` (up to the terminating ' .\\n') — a `removed` element."""
        txt = self.read(rel)
        i = txt.index(f"\n:{local} a ")
        j = txt.index(" .\n", i) + 3
        self.write(rel, txt[:i] + "\n" + txt[j:])
        return self.commit_all(msg or f"remove {local}")

    def add_relationship(self, local, typ, src, tgt, msg=None):
        self.write(AM4, f"\n:{local} a {typ} ;\n    arch:inModel <{M}> ;\n    arch:source :{src} ; arch:target :{tgt} .\n", "a")
        return self.commit_all(msg or f"add {local}")

    # -- approval commits (shape of §5.9 step 7) and deliberate deviations
    def approve(self, gate, approves, evidence=None, *, local=None, at="2026-11-20T11:00:00Z", decision="Approved",
                activity=None, extra_ttl="", trailer=None, path=None, symlink=False, executable=False, date=None,
                approved_by=":chiefArchitect"):
        """Commit one approval record. evidence defaults to HEAD (the commit the human looked at). activity: dict of
        activity_ttl kwargs (local/head/base/branch…) or None. Returns (commit, record_local, record_iri)."""
        evidence = evidence or self.rev()
        local = local or f"approval-{stamp(at)}-{gate.lower()[4:]}-{evidence[:7]}"
        body = PREFIXES
        if activity:
            body += activity_ttl(**activity)
        body += record_ttl(local, gate, approves, evidence, at=at, decision=decision, approved_by=approved_by,
                           activity=activity["local"] if activity else None) + extra_ttl
        rel = path or f"{GOV}/{local}.ttl"
        if symlink:  # the commit adds only the link (mode 120000); its target lives outside the repository
            target = self.tmp / f"{local}.target.ttl"
            target.write_text(body, encoding="utf-8")
            os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
            os.symlink(str(target), self.path(rel))
        else:
            self.write(rel, body)
        if executable:
            os.chmod(self.path(rel), 0o755)
        c = self.commit_all(f"aisep: {gate} {decision} {local}",
                            trailers=[f"AISEP-Evidence: {trailer if trailer is not None else evidence}"], date=date)
        return c, local, M + local

    def activity_only(self, local, head, base, branch):
        """A commit adding only an AgentActivity that no new record references (§5.9 approval-only PR rule 3)."""
        self.write(f"{GOV}/{local}.ttl", PREFIXES + activity_ttl(local, head, base, branch))
        return self.commit_all(f"aisep: activity {local}", trailers=[f"AISEP-Evidence: {head}"])

    def record_block(self, rel):
        """The subject blocks of an existing record file without its prefix header (to copy into another file)."""
        return self.read(rel)[len(PREFIXES):]

    def set_model_label(self, new_label, msg=None):
        txt = self.read(AM4)
        old = '<' + M + '> a arch:Model ;\n    skos:prefLabel "采购"@zh'
        assert old in txt, "fixture: model header changed"
        self.write(AM4, txt.replace(old, old.replace("采购", new_label)))
        return self.commit_all(msg or "relabel the model")

    def retarget(self, rel_local, new_target, msg=None):
        """Change arch:target of the qualified relationship :rel_local in am4.ttl."""
        txt = self.read(AM4)
        i = txt.index(f"\n:{rel_local} a ")
        j = txt.index("arch:target :", i) + len("arch:target :")
        k = txt.index(" .", j)
        self.write(AM4, txt[:j] + new_target + txt[k:])
        return self.commit_all(msg or f"retarget {rel_local}")

    def merge_base(self, a, b):
        return self.git("merge-base", a, b)

    def tag(self, name, target, annotated=False, push=True, force=False):
        args = ["tag"] + (["-a", "-m", name] if annotated else []) + (["-f"] if force else []) + [name, target]
        self.git(*args)
        if push:
            self.git("push", "-q", *(["-f"] if force else []), "origin", f"refs/tags/{name}")
