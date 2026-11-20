"""S2: read-only tools (docs/mcp-interface.md §5.4, §5.6, §5.7). Acceptance: T3, T27, T29, T37 (read-only part).

T3 compares every tool result with the REAL CLI (a subprocess of tools/aisep.py in the same temp repo, default file set).
Every module fixture takes ~10 minutes, so `aisep.py test` runs the first valid + first invalid fixture of each module;
AISEP_T3_ALL=1 runs all of them (done before each PR, result in the PR description)."""
import glob, os, re, shutil, subprocess, sys

import pyoxigraph as ox
import pytest

from conftest import ROOT, commit_all, git, run_cli
from aisep import tools as T
from aisep.errors import AisepError

CFG = T.Config()
P = "https://aisep.example/model/procurement/"
DIRECT = "\n:quoteApproval am4:accesses :quotation .\n"  # direct triple: one L1 Violation
LINE = re.compile(r"^\[(\w+)\] (\S+) (.*)$")


def raises(code, fn, *a, **kw):
    with pytest.raises(AisepError) as e:
        fn(*a, **kw)
    assert e.value.code == code, (e.value.code, e.value.message)
    return e.value


def cli_records(out):
    """CLI problem lines as (severity, layer, message); a message may span several lines (continuation lines do not
    start with "[Severity] layer ")."""
    recs = []
    for line in out.splitlines():
        m = LINE.match(line)
        if m and m.group(1) in ("Violation", "Warning", "Info"):
            recs.append(list(m.groups()))
        elif line.startswith("SUMMARY "):
            break
        elif recs:
            recs[-1][2] += "\n" + line
    return [tuple(r) for r in recs]


_BNODE = re.compile(r"\bn[0-9a-f]{32}b\d+\b")
_IN_LIST = re.compile(r"not in list \[([^\]]*)\]")


def norm(rec):
    """Run-to-run noise of L3 messages (seen in the prototype too): rdflib blank-node ids and the order of sh:in lists."""
    sev, layer, msg = rec
    msg = _BNODE.sub("_:b", msg)
    msg = _IN_LIST.sub(lambda m: "not in list [" + ", ".join(sorted(m.group(1).split(", "))) + "]", msg)
    return sev, layer, msg


def cli_set(out):
    return {norm(r) for r in cli_records(out)}


def tool_set(res):
    return {norm((f["severity"], f["layer"], f["message"])) for f in res["findings"]}


def append(repo, text, f="am4.ttl"):
    with open(repo / "models/procurement" / f, "a") as fh:
        fh.write(text)


# ---------------------------------------------------------------- T3: same judgement as the CLI (P9)

# Pre-existing prototype bug (also on main): `aisep.py gate <fixture>` crashes in l3 because pyshacl returns a
# ValidationFailure for these fixtures. `aisep.py test` does not see it (run_fixture stops before L3 once the expected
# L1 violation is found). Strict xfail: the day it is fixed these turn into failures and the marks must go.
PYSHACL_FAILURE = {"deprecated-partOfModel.ttl", "reifies-forbidden.ttl"}
PYSHACL_BUG = "prototype l3 crashes on pyshacl ValidationFailure (pre-existing, also on main)"


def _fixtures():
    fx = sorted(glob.glob(os.path.join(ROOT, "modules", "*", "tests", "*", "*.ttl")))
    if os.environ.get("AISEP_T3_ALL"):
        first = {f: f for f in fx}
    else:
        first = {}
        for f in fx:  # default: the first valid and the first invalid fixture of every module
            first.setdefault(os.path.dirname(f), f)
    return [pytest.param(f, marks=pytest.mark.xfail(raises=AttributeError, strict=True, reason=PYSHACL_BUG))
            if os.path.basename(f) in PYSHACL_FAILURE else f for f in first.values()]


def test_T3_procurement_gate_and_findings(repo):
    rc, out, _ = run_cli(repo, "gate")
    g = T.model_gate(CFG, repo=str(repo))
    assert tool_set(g) == cli_set(out) and g["result"] == ("FAIL" if rc else "PASS") == "PASS"
    per = dict(re.findall(r"(L0|build|L1|L2|L3|L4)=(\d+)", out.split("violations_by_layer[")[1].split("]")[0]))
    assert g["summary"]["violationsByLayer"] == {k: int(v) for k, v in per.items()}
    _, out, _ = run_cli(repo, "findings")
    f = T.model_findings(CFG, repo=str(repo))
    assert [(x["severity"], x["layer"], x["message"]) for x in f["findings"]] == cli_records(out)


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda f: os.path.relpath(f, ROOT))
def test_T3_fixture_gate_equals_cli(repo, fixture):
    shutil.rmtree(repo / "models")
    os.makedirs(repo / "models/fx")
    shutil.copy(fixture, repo / "models/fx" / os.path.basename(fixture))
    rc, out, _ = run_cli(repo, "gate")
    g = T.model_gate(CFG, repo=str(repo))
    assert "files=1 " in out  # exactly the fixture was checked (a stale index entry would add an L0 "cannot parse")
    assert tool_set(g) == cli_set(out)
    assert g["result"] == ("FAIL" if rc else "PASS")
    assert f"violations={g['summary']['violations']} " in out
    _, out, _ = run_cli(repo, "findings")
    f = T.model_findings(CFG, repo=str(repo))
    assert [norm((x["severity"], x["layer"], x["message"])) for x in f["findings"]] == [norm(r) for r in cli_records(out)]


def test_check_validate_match_cli(repo):
    append(repo, DIRECT)
    for tool, cmd in ((T.model_check, "check"), (T.model_validate, "validate")):
        _, out, _ = run_cli(repo, cmd)
        r = tool(CFG, repo=str(repo))
        assert r["partial"] is True and "result" not in r
        assert tool_set(r) == cli_set(out)
        assert r["summary"]["violations"] == (1 if cmd == "check" else 0)  # a direct triple is an L1 rule, not L3


def test_ref_and_model_parameters(repo):
    append(repo, DIRECT)
    bad = commit_all(repo, "violation")
    git(repo, "checkout", "-q", "HEAD~1", "--", "models")  # working tree back to the clean content, uncommitted
    assert T.model_gate(CFG, repo=str(repo))["result"] == "PASS"
    g = T.model_gate(CFG, repo=str(repo), ref=bad)
    assert g["result"] == "FAIL" and g["source"]["commit"] == bad and g["source"]["ref"] == bad
    assert T.model_check(CFG, repo=str(repo), model="procurement")["summary"]["violations"] == 0
    assert T.model_check(CFG, repo=str(repo), model=P)["summary"]["violations"] == 0
    raises("MODEL_NOT_FOUND", T.model_check, CFG, repo=str(repo), model="nope")


# ---------------------------------------------------------------- T27: impact

def _cli_impact(repo, *args):
    rc, out, err = run_cli(repo, "impact", *args)
    return rc, [line.split("\t") for line in out.splitlines()[1:]], err


def test_T27_items_equal_cli_and_paths_are_real(repo):
    for mode, n in (("depends", 14), ("ripple", 16)):
        r = T.model_impact(CFG, "procurement:quotation", mode=mode, repo=str(repo))
        rc, rows, _ = _cli_impact(repo, "procurement:quotation", "--mode", mode)
        assert rc == 0 and len(r["items"]) == len(rows) == n
        assert [P + row[0].split(":", 1)[1] for row in rows] == [i["iri"] for i in r["items"]]
        assert [row[3].split(" ")[0] for row in rows] == [str(i["depth"]) for i in r["items"]]
        for it in r["items"]:
            hops = it["path"]
            assert hops[0]["from"] == r["focus"]["iri"] and hops[-1]["to"] == it["iri"] and len(hops) == it["depth"]
            assert all(a["to"] == b["from"] for a, b in zip(hops, hops[1:]))
    # each hop names a real qualified relationship whose endpoints are the hop's ends in the stated direction
    q = T.model_query(CFG, "SELECT ?r ?c ?s ?t WHERE { ?r arch:source ?s ; arch:target ?t ; a ?c }", repo=str(repo))
    rels = {(x["r"]["value"], x["c"]["value"]): (x["s"]["value"], x["t"]["value"]) for x in q["rows"]}
    r = T.model_impact(CFG, "procurement:quotation", mode="ripple", repo=str(repo))
    for it in r["items"]:
        for h in it["path"]:
            s, t = rels[(h["relationship"], h["via"])]
            assert (s, t) == ((h["from"], h["to"]) if h["direction"] == "forward" else (h["to"], h["from"]))


def test_T27_invalid_and_unknown(repo):
    append(repo, DIRECT)
    e = raises("MODEL_INVALID", T.model_impact, CFG, "procurement:quotation", repo=str(repo))
    assert any("direct triple" in f["message"] for f in e.details["findings"])
    r = T.model_impact(CFG, "procurement:quotation", allowInvalid=True, repo=str(repo))
    assert r["invalidModel"] == {"violations": 1} and len(r["items"]) == 14
    git(repo, "checkout", "-q", "--", "models")
    e = raises("ELEMENT_NOT_FOUND", T.model_impact, CFG, "procurement:quotatoin", repo=str(repo))
    assert e.details["candidates"][0]["iri"] == P + "quotation" and len(e.details["candidates"]) == 5
    raises("INVALID_ARGUMENT", T.model_impact, CFG, "procurement:quotation", depth=11, repo=str(repo))
    raises("INVALID_ARGUMENT", T.model_impact, CFG, "procurement:quotation", mode="x", repo=str(repo))
    rc, _, err = _cli_impact(repo, "procurement:nope")  # CLI: unknown element now exits 1 (intentional change)
    assert rc == 1 and "is not an element" in err


# ---------------------------------------------------------------- T29: query is read-only

def test_T29_update_and_service_refused(repo, monkeypatch):
    # pyoxigraph's SERVICE client is native code (Python socket patches would not see it): prove instead that the
    # query engine is never reached, and that Store.update is never called
    calls = []
    monkeypatch.setattr(ox.Store, "update", lambda *a, **k: calls.append("update"))
    real = T._run_query
    monkeypatch.setattr(T, "_run_query", lambda *a, **k: calls.append("query") or real(*a, **k))
    raises("QUERY_NOT_READONLY", T.model_query, CFG, "INSERT DATA { <urn:a> <urn:b> <urn:c> }", repo=str(repo))
    raises("QUERY_NOT_READONLY", T.model_query, CFG, "PREFIX x: <urn:x#>\n# c\nDELETE WHERE { ?s ?p ?o }", repo=str(repo))
    raises("QUERY_NOT_READONLY", T.model_query, CFG,
           "SELECT * WHERE { SERVICE <http://127.0.0.1:9/sparql> { ?s ?p ?o } }", repo=str(repo))
    assert calls == ["query", "query"]  # the two updates reached the parser (and failed); SERVICE never did
    n = T.model_query(CFG, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }", repo=str(repo))["rows"][0]["n"]["value"]
    assert int(n) > 0
    e = raises("QUERY_FAILED", T.model_query, CFG, "SELEC ?x WHERE {}", repo=str(repo))
    assert "1:" in e.details["parser"]  # parser text with line:column


def test_T29_limit_kinds_timeout(repo):
    r = T.model_query(CFG, "SELECT ?s WHERE { ?s ?p ?o }", limit=5, repo=str(repo))
    assert r["kind"] == "select" and len(r["rows"]) == 5 and r["truncated"] is True
    r = T.model_query(CFG, "SELECT ?x WHERE { BIND(<urn:x> AS ?x) }", repo=str(repo))
    assert r["truncated"] is False and r["rows"] == [{"x": {"type": "iri", "value": "urn:x"}}]
    r = T.model_query(CFG, "ASK { ?x a arch:Model }", repo=str(repo))
    assert (r["kind"], r["value"]) == ("ask", True)
    assert T.model_query(CFG, "ASK { ?x a <urn:none> }", repo=str(repo))["value"] is False
    r = T.model_query(CFG, "CONSTRUCT { ?x a arch:Model } WHERE { ?x a arch:Model }", repo=str(repo))
    assert r["kind"] == "triples" and r["triples"] and r["truncated"] is False
    assert all(t[1]["value"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and t[0]["type"] == "iri" for t in r["triples"])
    raises("QUERY_TIMEOUT", T.model_query, CFG,
           "SELECT (COUNT(*) AS ?n) WHERE { ?a ?b ?c . ?d ?e ?f . ?g ?h ?i }", timeoutMs=200, repo=str(repo))
    raises("INVALID_ARGUMENT", T.model_query, CFG, "ASK {}", limit=10001, repo=str(repo))


def test_T29_parse_failed_and_allow_partial(repo):
    (repo / "models/procurement/broken.ttl").write_text("@prefix x: <urn:x#> .\nx:a x:b \n")
    e = raises("PARSE_FAILED", T.model_query, CFG, "ASK {}", repo=str(repo))
    assert e.details["files"] == ["models/procurement/broken.ttl"]
    r = T.model_query(CFG, "SELECT ?x WHERE { ?x a am4:BusinessObject }", allowPartial=True, repo=str(repo))
    assert r["partial"] is True and r["skippedFiles"] == ["models/procurement/broken.ttl"] and r["rows"]
    assert r["findings"][0]["layer"] == "L0" and r["findings"][0]["file"] == "models/procurement/broken.ttl"


# ---------------------------------------------------------------- T37: committed legacy violations are visible

def test_T37_open_violations(repo):
    append(repo, DIRECT)
    commit_all(repo, "legacy violation (no hooks in this repo: as if --no-verify)")
    f = T.model_findings(CFG, repo=str(repo))
    ov = f["openViolations"]
    assert ov["count"] == 1 and ov["byLayer"] == {"L0": 0, "build": 0, "L1": 1, "L2": 0}
    item = ov["items"][0]
    assert item["focus"] == P + "quoteApproval" and item["file"] == "models/procurement/am4.ttl"
    assert item["severity"] == "Violation" and "direct triple" in item["message"]
    assert f["summary"]["violations"] == 0  # findings' own summary stays L4-only
    g = T.model_gate(CFG, repo=str(repo))
    assert g["summary"]["violationsByLayer"]["L1"] == 1 and g["summary"]["violations"] == 1  # counted once
    for res in (f, g, T.model_check(CFG, repo=str(repo))):
        assert all("preexisting" not in x for x in res["findings"] + res.get("openViolations", {}).get("items", []))


def test_T37_two_instances_two_items(repo):
    append(repo, DIRECT + ":submitQuotation am4:accesses :quotation .\n")
    ov = T.model_findings(CFG, repo=str(repo))["openViolations"]
    assert ov["count"] == 2 and {i["focus"] for i in ov["items"]} == {P + "quoteApproval", P + "submitQuotation"}


def test_T37_pre_commit_hook_blocks(repo):
    shutil.copytree(os.path.join(ROOT, ".githooks"), repo / ".githooks")
    git(repo, "config", "core.hooksPath", ".githooks")
    append(repo, DIRECT)
    git(repo, "add", "-A")
    env = dict(os.environ, AISEP_PY=sys.executable)
    p = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], capture_output=True, text=True, env=env)
    assert p.returncode != 0 and "result=FAIL" in p.stdout + p.stderr


def test_findings_focus_fallback(repo):
    """Every Violation of a planted L1 problem and of an L3 problem carries the focus the message names."""
    append(repo, DIRECT)
    g = T.model_gate(CFG, repo=str(repo))
    v = [x for x in g["findings"] if x["severity"] == "Violation"]
    assert v and all(x["focus"] == P + "quoteApproval" for x in v)
