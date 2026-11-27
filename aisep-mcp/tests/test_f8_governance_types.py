"""#167 (#137 follow-up F8): write tools and actions never add, change or remove an instance of a governance type
(aisep:ApprovalRecord, aisep:AgentActivity, aisep:AIAgent and their subclasses). models/<slug>/governance.ttl cannot be
refused by path (it is the default file for ordinary elements), so the guard sits on the type, in writer.transaction,
the one door every write tool and action goes through. Also: a write through a symlink into governance/ is refused,
and refusals say why in details.reason (error codes unchanged)."""
import hashlib, os

import pyoxigraph as ox
import pytest

from conftest import commit_all, git
from aisep import tools as T, write_tools as W, writer
from aisep.errors import AisepError

M = "https://aisep.example/model/procurement/"
GOVTTL = "models/procurement/governance.ttl"
GOVDIR = "models/procurement/governance"
REC = M + "approval-20261119-arch-baseline"
PREF = "http://www.w3.org/2004/02/skos/core#prefLabel"
BOT = ("\n:bot a aisep:AIAgent ;\n    arch:inModel <https://aisep.example/model/procurement/> ;\n"
       "    skos:prefLabel \"编码代理\"@zh .\n")
SUBCLASS = ("\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            ":CodingAgent rdfs:subClassOf aisep:AIAgent ; skos:prefLabel \"编码代理类\"@zh .\n")


def cfg(repo):
    return T.Config(allow_roots=(str(repo.parent),))


def snap(repo):
    out = {}
    for d, _, fs in os.walk(repo / "models"):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, repo)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def refused(code, fn, repo, *a, **kw):
    before = snap(repo)
    with pytest.raises(AisepError) as ei:
        fn(cfg(repo), *a, repo=str(repo), **kw)
    assert ei.value.code == code, (ei.value.code, ei.value.args, ei.value.details)
    assert snap(repo) == before
    return ei.value


def append_commit(repo, rel, text):
    with open(repo / rel, "a", encoding="utf-8") as f:
        f.write(text)
    commit_all(repo, "fixture")


# ------------------------------------------------------------------ type-level guard

def test_add_ai_agent_refused(repo):
    e = refused("PROTECTED_RESOURCE", W.model_add_element, repo, "procurement", "aisep:AIAgent", "代理", slug="bot")
    assert e.details["reason"] == "governance-type" and e.details["iri"] == M + "bot", e.details
    assert e.details["types"] == ["aisep:AIAgent"]


def test_add_instance_of_model_subclass_of_ai_agent_refused(repo):
    """A model-level specialisation (G6) of aisep:AIAgent is a governance type too."""
    append_commit(repo, GOVTTL, SUBCLASS)
    e = refused("PROTECTED_RESOURCE", W.model_add_element, repo, "procurement", M + "CodingAgent", "代理", slug="bot")
    assert e.details["reason"] == "governance-type" and e.details["iri"] == M + "bot", e.details


@pytest.mark.parametrize("op", ["labels", "remove"])
def test_change_or_remove_ai_agent_refused(repo, op):
    append_commit(repo, GOVTTL, BOT)
    if op == "labels":
        e = refused("PROTECTED_RESOURCE", W.model_set_labels, repo, M + "bot", prefLabel="改名")
    else:
        e = refused("PROTECTED_RESOURCE", W.model_remove, repo, M + "bot")
    assert e.details["reason"] == "governance-type" and e.details["iri"] == M + "bot", e.details


def test_transaction_refuses_edit_of_approval_record(repo):
    """The guard is in writer.transaction itself, not only at each tool's entry: a plan that changes a record's label
    in governance.ttl (a path check_paths lets through) is refused before anything is written."""
    old = ox.Literal("报价审批流程架构基线批准", language="zh")
    new = ox.Literal("改过的批准", language="zh")
    text = (repo / GOVTTL).read_text(encoding="utf-8")
    assert f'"{old.value}"@zh' in text

    def build(ws, ctx):
        return {"result": {}, "edits": {GOVTTL: text.replace(old.value, new.value)},
                "removed": {GOVTTL: {(REC, PREF, old)}},
                "added": {GOVTTL: [ox.Triple(ox.NamedNode(REC), ox.NamedNode(PREF), new)]}}

    before = snap(repo)
    with pytest.raises(AisepError) as ei:
        writer.transaction(cfg(repo), str(repo), build)
    assert ei.value.code == "PROTECTED_RESOURCE" and ei.value.details["reason"] == "governance-type"
    assert ei.value.details["iri"] == REC and ei.value.details["types"] == ["aisep:ApprovalRecord"]
    assert snap(repo) == before


def test_ordinary_writes_to_governance_ttl_still_work(repo):
    """Positive twin: governance.ttl stays writable for elements that are not governance records."""
    r = W.model_add_element(cfg(repo), "procurement", "arch:Stakeholder", "采购经理", slug="buyer", repo=str(repo))
    assert r["changed"] and r["file"] == GOVTTL
    r = W.model_set_labels(cfg(repo), M + "buyer", prefLabel="采购主管", repo=str(repo))
    assert r["changed"]


# ------------------------------------------------------------------ readable reasons on path refusals

@pytest.mark.parametrize("path,reason", [(GOVDIR + "/x.ttl", "governance-directory"),
                                         ("models/procurement/../x.ttl", "path-not-normalised")])
def test_check_paths_reason(path, reason):
    with pytest.raises(AisepError) as ei:
        writer.check_paths({"edits": {path: ""}})
    assert ei.value.code == "INVALID_ARGUMENT" and ei.value.details == {"file": path, "reason": reason}


# ------------------------------------------------------------------ symlinks into governance/

@pytest.fixture
def govrec(repo):
    os.makedirs(repo / GOVDIR)
    (repo / GOVDIR / "rec.ttl").write_text("@prefix : <https://aisep.example/model/procurement/> .\n", encoding="utf-8")
    commit_all(repo, "governance dir")
    return repo / GOVDIR / "rec.ttl"


@pytest.mark.parametrize("ignored", [False, True])
def test_file_symlink_into_governance_refused(repo, govrec, ignored):
    """models/<slug>/linked.ttl -> governance/rec.ttl: a write tool aimed at the link never reaches the record. Seen by
    the workspace scan, or (ignored, so not part of the model) caught when the file is opened for the write."""
    os.symlink("governance/rec.ttl", repo / "models/procurement/linked.ttl")
    if ignored:
        with open(repo / ".git/info/exclude", "a") as f:
            f.write("models/procurement/linked.ttl\n")
    rec = govrec.read_bytes()
    e = refused("PATH_OUTSIDE_ROOT", W.model_add_element, repo, "procurement", "am4:BusinessObject", "发票",
                slug="invoice", file="models/procurement/linked.ttl")
    assert govrec.read_bytes() == rec and os.path.islink(repo / "models/procurement/linked.ttl"), e.details
    assert not [f for f in os.listdir(repo / GOVDIR) if f != "rec.ttl"]


def test_dir_symlink_into_governance_refused(repo, govrec):
    """models/<slug>/gov -> governance/: a plan naming gov/new.ttl passes the path check (gov is not governance) and is
    refused when the directory is opened without following links."""
    os.symlink("governance", repo / "models/procurement/gov")
    target = "models/procurement/gov/new.ttl"
    triple = ox.Triple(ox.NamedNode(M + "x"), ox.NamedNode(PREF), ox.Literal("x", language="zh"))

    def build(ws, ctx):
        return {"result": {}, "edits": {target: f'<{M}x> <{PREF}> "x"@zh .\n'}, "removed": {}, "added": {target: [triple]}}

    before = snap(repo)
    with pytest.raises(AisepError) as ei:
        writer.transaction(cfg(repo), str(repo), build)
    assert ei.value.code == "PATH_OUTSIDE_ROOT", (ei.value.code, ei.value.details)
    assert snap(repo) == before and sorted(os.listdir(repo / GOVDIR)) == ["rec.ttl"]
