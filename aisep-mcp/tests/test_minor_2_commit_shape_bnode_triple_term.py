"""mergecheck._commit_shape / _criterion on approval-shaped commits whose new file carries content the criterion must
reject without crashing (docs/mcp-interface.md §5.9 step 1 (c), 第四轮 R4-8).

Contract (independent test author):
  (a) the new file also holds a blank node nobody references (`[] a … .`), or a blank node shared by two subjects:
      _commit_shape does not raise and returns a non-empty string; _criterion returns one problem with
      reason "not-approval-commit" for that commit; `python -m aisep.mergecheck` over a PR containing it prints a
      structured JSON result and no Traceback.
  (b) the new file holds an RDF 1.2 triple term (`<<( s p o )>>` as an object): _commit_shape returns a non-empty
      string (not an approval commit).
Every commit is built by fixtures.topology.Topo.approve, so (a)(b) of the shape hold and only the new file differs."""
import json, os, subprocess, sys

import pytest

from fixtures.topology import Topo

from aisep import mergecheck

MAIN = "refs/heads/main"
BRANCH = "feat/x"
NOW = "2026-11-20T12:00:00Z"


@pytest.fixture
def t(template, tmp_path):
    mergecheck._commit_shape.cache_clear()
    return Topo(template, tmp_path)


def approval_with(t, extra):
    t.checkout("main", new=BRANCH)
    h = t.add_element("newThing", "新东西")
    local = f"approval-20261120110000-architecture-{h[:7]}"
    c, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h, local=local,
                        extra_ttl=extra.format(local=local))
    out = t.git("diff-tree", "-r", "--no-commit-id", "--name-status", f"{c}^", c).splitlines()
    assert len(out) == 1 and out[0].startswith("A\t") and "/governance/" in out[0], out  # construction self-check
    return c


def shape(t, c):
    mergecheck._commit_shape.cache_clear()
    return mergecheck._commit_shape(str(t.root), c)


BNODE_CASES = {
    "unreferenced": "\n[] a am4:BusinessObject .\n",
    "shared-by-two-subjects": "\n:{local} skos:note _:b .\n:auditTrail skos:note _:b .\n_:b skos:prefLabel \"x\"@zh .\n",
}


@pytest.mark.parametrize("case", sorted(BNODE_CASES))
def test_blank_node_shape_returns_reason(t, case):
    c = approval_with(t, BNODE_CASES[case])
    why = shape(t, c)
    assert isinstance(why, str) and why, why


@pytest.mark.parametrize("case", sorted(BNODE_CASES))
def test_blank_node_criterion_reports_not_approval_commit(t, case):
    c = approval_with(t, BNODE_CASES[case])
    mergecheck._commit_shape.cache_clear()
    ps = mergecheck._criterion(str(t.root), [c])
    assert len(ps) == 1, ps
    assert ps[0]["reason"] == "not-approval-commit", ps
    assert ps[0].get("offendingCommit") == c, ps


@pytest.mark.parametrize("case", sorted(BNODE_CASES))
def test_blank_node_cli_structured_no_traceback(t, case):
    c = approval_with(t, BNODE_CASES[case])
    t.push(BRANCH)
    p = subprocess.run([sys.executable, "-m", "aisep.mergecheck", "--repo", str(t.root), "--pr-head", c,
                        "--head-ref", BRANCH, "--target", "main", "--now", NOW],
                       cwd=str(t.root), capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH=str(t.root)))
    assert "Traceback" not in p.stderr, p.stderr[-2000:]
    assert p.returncode in (0, 1), (p.returncode, p.stderr[-2000:])
    out = json.loads(p.stdout)
    assert isinstance(out.get("problems"), list), out
    assert any(x.get("reason") == "not-approval-commit" and x.get("offendingCommit") == c for x in out["problems"]), \
        out["problems"]


def test_triple_term_object_is_not_approval_commit(t):
    c = approval_with(t, "\n:{local} skos:note <<( :auditTrail skos:note :newThing )>> .\n")
    path = t.git("diff-tree", "-r", "--no-commit-id", "--name-only", f"{c}^", c)
    assert "<<(" in t.git("show", f"{c}:{path}")  # the triple term really is in the committed file
    why = shape(t, c)
    assert isinstance(why, str) and why, why
