"""S4b: model_remove (docs/mcp-interface.md §5.5). Acceptance: T17, T18, and T13's "SIGKILL between renames -> gate FAIL"."""
import glob, hashlib, os, signal, subprocess, sys, textwrap

import pytest

from conftest import ROOT, commit_all
from aisep import tools, write_tools as W
from aisep.errors import AisepError

CFG = tools.Config()
M = "https://aisep.example/model/procurement/"
P = "models/procurement/"
HDR = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix arch: <https://meta.linked.archi/core#> .
@prefix am4:  <https://meta.linked.archi/archimate4/onto#> .
@prefix p:    <https://aisep.example/model/procurement/> .
@prefix :     <https://aisep.example/model/b/> .
"""


def snap(repo):
    return {f: hashlib.sha256(open(f, "rb").read()).hexdigest()
            for f in sorted(glob.glob(os.path.join(str(repo), "models", "**", "*"), recursive=True)) if os.path.isfile(f)}


def raises(code, fn, *a, **kw):
    with pytest.raises(AisepError) as e:
        fn(*a, **kw)
    assert e.value.code == code, (e.value.code, e.value.message)
    return e.value


def rm(repo, iri, **kw):
    return W.model_remove(CFG, iri, repo=str(repo), **kw)


def iris(entries, key="iri"):
    return [e[key].replace(M, "") for e in entries]


# ---------------------------------------------------------------- T17

def test_T17_approved_element_is_referenced(repo):
    s = snap(repo)
    e = raises("REFERENCED", rm, repo, "procurement:quoteApproval", cascade=True)
    b = e.details["plan"]["blockers"]
    # exactly the approval record — the derived direct triples of the build graph do not show up (source graph only)
    assert [(x["subject"].replace(M, ""), x["predicate"]) for x in b] == [("approval-20261119-arch-baseline", "aisep:approves")]
    assert "owl:deprecated" in e.hint and snap(repo) == s


def test_T17_cascade_required_then_done(repo):
    s = snap(repo)
    e = raises("CASCADE_REQUIRED", rm, repo, "procurement:quotation")
    plan = e.details["plan"]
    assert iris(plan["delete"]) == ["quotation", "rel-quotationAggregate-realizes-quotation",
                                    "rel-quoteApproval-accesses-quotation", "rel-submitQuotation-accesses-quotation"]
    assert [d["reason"] for d in plan["delete"]] == ["target", "endpoint", "endpoint", "endpoint"]
    assert snap(repo) == s
    r = rm(repo, "procurement:quotation", cascade=True, planDigest=e.details["planDigest"])
    assert r["written"] and {f["path"] for f in r["filesChanged"]} == {P + "am4.ttl", P + "ddd.ttl"}
    assert tools.model_gate(CFG, repo=str(repo))["result"] == "PASS"


def test_T17_bpmn_detach(repo):
    r = rm(repo, "procurement:bpmnReview", cascade=True)
    assert iris(r["plan"]["delete"]) == ["bpmnReview", "sf1", "sf2"]
    assert [(d["subject"].replace(M, ""), d["predicate"], d["object"].replace(M, "")) for d in r["plan"]["detach"]] == \
        [("bpmnQuoteApproval", "bpmn:flowElements", x) for x in ("bpmnReview", "sf1", "sf2")]  # every D member's membership
    t = open(os.path.join(str(repo), P, "bpmn.ttl"), encoding="utf-8").read()
    assert ":bpmnReview" not in t and ":sf1 " not in t and ":sf3" in t
    assert tools.model_gate(CFG, repo=str(repo))["result"] == "PASS"


def test_T17_protected(repo):
    s = snap(repo)
    raises("PROTECTED_RESOURCE", rm, repo, "procurement:approval-20261119-arch-baseline", cascade=True)
    raises("PROTECTED_RESOURCE", rm, repo, M, cascade=True)
    assert snap(repo) == s


def test_T17_cross_model_relationship_blocks(repo):
    os.makedirs(repo / "models" / "b")
    (repo / "models/b/b.ttl").write_text(HDR + "\n<https://aisep.example/model/b/> a arch:Model ; skos:prefLabel \"B\"@zh .\n"
                                         ":user a am4:BusinessActor ; arch:inModel <https://aisep.example/model/b/> ;"
                                         " skos:prefLabel \"用户\"@zh .\n"
                                         ":rel-user-uses-quotation a am4:Access ; arch:inModel <https://aisep.example/model/b/> ;"
                                         " arch:source :user ; arch:target p:supplier .\n", encoding="utf-8")
    commit_all(repo, "model b")
    before = snap(repo)
    e = raises("REFERENCED", rm, repo, "procurement:supplier", cascade=True)
    cm = [x for x in e.details["plan"]["blockers"] if x["reason"] == "cross-model-relationship"]
    assert [(x["subject"], x["predicate"], x["file"]) for x in cm] == \
        [("https://aisep.example/model/b/rel-user-uses-quotation", "arch:target", "models/b/b.ttl")]
    assert snap(repo) == before


def test_T17_relationship_to_relationship(repo):
    with open(os.path.join(str(repo), P, "am4.ttl"), "a", encoding="utf-8") as f:
        f.write("\n:rel-note-on-access a arch:Association ;\n    arch:inModel <" + M + "> ;\n"
                "    arch:source :procurementManager ;\n    arch:target :rel-quoteApproval-accesses-quotation .\n")
    commit_all(repo, "relationship to relationship")
    r = rm(repo, "procurement:quotation", cascade=True, dryRun=True)
    assert {"rel-quoteApproval-accesses-quotation", "rel-note-on-access"} <= set(iris(r["plan"]["delete"]))
    assert r["written"] is False and r["dryRun"] is True


# ---------------------------------------------------------------- T18

def test_T18_determinism_stale_replay_missing(repo):
    s = snap(repo)
    runs = [rm(repo, "procurement:quotation", cascade=True, dryRun=True) for _ in range(10)]
    assert all((r["plan"], r["planDigest"], r["filesChanged"]) == (runs[0]["plan"], runs[0]["planDigest"],
                                                                   runs[0]["filesChanged"]) for r in runs)
    assert snap(repo) == s
    old = runs[0]["planDigest"]
    with open(os.path.join(str(repo), P, "am4.ttl"), "a", encoding="utf-8") as f:
        f.write("\n:rel-procurementManager-accesses-quotation a am4:Access ;\n    arch:inModel <" + M + "> ;\n"
                "    arch:source :procurementManager ;\n    arch:target :quotation .\n")
    s = snap(repo)
    e = raises("PLAN_STALE", rm, repo, "procurement:quotation", cascade=True, planDigest=old)
    assert e.retryable is False and snap(repo) == s
    new = e.details["planDigest"]
    r = rm(repo, "procurement:quotation", cascade=True, planDigest=new)
    assert r["written"] and r["changed"]
    s = snap(repo)
    r = rm(repo, "procurement:quotation", cascade=True, planDigest=new)
    assert r["changed"] is False and r["alreadyAbsent"] is True and snap(repo) == s
    raises("ELEMENT_NOT_FOUND", rm, repo, "procurement:quotation", cascade=True)


# ---------------------------------------------------------------- T13: SIGKILL between renames, then gate FAILs

def test_T13_sigkill_partial_cascade_is_caught_by_gate(repo):
    script = textwrap.dedent(f"""
        import os, signal, sys
        sys.path.insert(0, {ROOT!r})
        from aisep import writer, write_tools as W, tools
        n = []
        def hook(rel):
            n.append(rel)
            if len(n) == 2:
                os.kill(os.getpid(), signal.SIGKILL)
        writer._before_rename = hook
        W.model_remove(tools.Config(), "procurement:quotation", cascade=True, repo={str(repo)!r})
    """)
    p = subprocess.run([sys.executable, "-c", script], capture_output=True)
    assert p.returncode == -signal.SIGKILL
    am4 = open(os.path.join(str(repo), P, "am4.ttl"), encoding="utf-8").read()
    ddd = open(os.path.join(str(repo), P, "ddd.ttl"), encoding="utf-8").read()
    assert ":quotation a" not in am4 and "rel-quotationAggregate-realizes-quotation" in ddd  # half written
    g = tools.model_gate(CFG, repo=str(repo))
    assert g["result"] == "FAIL" and any("rel-quotationAggregate-realizes-quotation" in (f["focus"] or "")
                                         for f in g["findings"] if f["severity"] == "Violation")
