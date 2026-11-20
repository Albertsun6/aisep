"""`gate <fixture>` on the forbidden-term fixtures used to crash in l3: aisep-core's ForbiddenTermShape used VALUES,
which SHACL §5.3.1 forbids in pre-bound queries, so pyshacl returned a ValidationFailure instead of a report graph
(only when the shape had focus nodes, i.e. only on these fixtures). Now the shape runs in pyshacl, and any future
engine failure is reported as an L3 Violation instead of a traceback."""
import pytest

from conftest import run_cli

FORBIDDEN = ["modules/aisep-core/tests/invalid/reifies-forbidden.ttl",
             "modules/aisep-core/tests/invalid/deprecated-partOfModel.ttl"]
SHAPES = "modules/aisep-core/shapes.ttl"
FILTER = "$this ?p ?o . FILTER(?p IN (arch:partOfModel, arch:exposedInView, arch:contains, rdf:reifies)) }"
VALUES = "VALUES ?p { arch:partOfModel arch:exposedInView arch:contains rdf:reifies } $this ?p ?o . }"


def l3_lines(out):
    return [l for l in out.splitlines() if l.startswith("[Violation] L3 ")]


@pytest.mark.parametrize("fixture", FORBIDDEN)
def test_gate_forbidden_fixture_reports_l3(repo, fixture):
    rc, out, err = run_cli(repo, "gate", fixture)
    assert "Traceback" not in err, err
    assert rc == 1 and "result=FAIL" in out
    assert any("forbidden term" in l for l in l3_lines(out)), out  # the shape really runs in pyshacl now


def test_gate_engine_failure_is_a_violation(repo):
    """Put the pre-fix VALUES query back: the gate must FAIL with an L3 Violation naming the engine failure."""
    p = repo / SHAPES
    s = p.read_text(encoding="utf-8")
    assert s.count(FILTER) == 1
    p.write_text(s.replace(FILTER, VALUES), encoding="utf-8")
    rc, out, err = run_cli(repo, "gate", FORBIDDEN[0])
    assert "Traceback" not in err, err
    assert rc == 1 and "result=FAIL" in out
    assert any("SHACL engine rejected" in l and "VALUES" in l for l in l3_lines(out)), out
