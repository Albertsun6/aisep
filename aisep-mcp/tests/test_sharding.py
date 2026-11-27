"""CI sharding (conftest.assign_shards / AISEP_SHARD): the shards of one collection are a partition of it (union = all tests,
pairwise disjoint), the split depends only on the input, tests with no recorded duration still land somewhere, a group stays
in one shard, and the LPT greedy split stays within one test of the ideal load."""
import json, os, random, subprocess, sys

import pytest

from conftest import DURATIONS, PY, assign_shards


def suite(seed=7, size=300):
    rnd = random.Random(seed)
    tests = [(f"test_{i % 17}.py::test_{i}" + (f"[p{i}]" if i % 3 else ""), f"g{i % 4}" if i % 29 == 0 else None)
             for i in range(size)]
    durations = {t: round(rnd.expovariate(0.2), 3) for t, _ in tests if rnd.random() < 0.8}  # ~20% unknown
    return tests, durations


def recorded():
    with open(DURATIONS, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
def test_shards_partition_the_suite(n):
    tests, durations = suite()
    shard = assign_shards(tests, durations, n)
    ids = [t for t, _ in tests]
    assert sorted(shard) == sorted(ids)                       # union = all, no extra
    parts = [{t for t in ids if shard[t] == i} for i in range(n)]
    assert sum(len(p) for p in parts) == len(ids) and set().union(*parts) == set(ids)   # disjoint
    assert all(parts), "a shard got no test"
    assert set(shard.values()) <= set(range(n))


def test_same_input_same_split_whatever_the_order():
    tests, durations = suite()
    a = assign_shards(tests, durations, 5)
    shuffled = tests[:]
    random.Random(1).shuffle(shuffled)
    assert assign_shards(shuffled, dict(reversed(list(durations.items()))), 5) == a


def test_unknown_tests_are_assigned_as_the_mean():
    tests, durations = suite()
    new = [(f"test_new.py::test_{i}", None) for i in range(40)]
    shard = assign_shards(tests + new, durations, 5)
    assert all(t in shard for t, _ in new)
    assert len({shard[t] for t, _ in new}) == 5               # spread out, not piled onto one shard
    assert assign_shards(new, {}, 3) == assign_shards(new, {}, 3)   # no durations at all still splits


def test_a_group_stays_in_one_shard():
    tests, durations = suite()
    shard = assign_shards(tests, durations, 5)
    for g in {g for _, g in tests if g}:
        assert len({shard[t] for t, tg in tests if tg == g}) == 1, g


@pytest.mark.parametrize("n", [3, 5])
def test_lpt_balance_bound(n):
    """Greedy onto the least-loaded shard: the heaviest shard exceeds the mean by at most the heaviest unit."""
    tests, durations = suite(seed=3, size=600)
    known = [durations[t] for t, _ in tests if t in durations]
    mean = sum(known) / len(known)
    w = {t: durations.get(t, mean) for t, _ in tests}
    units = {}
    for t, g in tests:
        units[g or t] = units.get(g or t, 0) + w[t]
    shard = assign_shards(tests, durations, n)
    loads = [sum(w[t] for t in w if shard[t] == i) for i in range(n)]
    assert max(loads) <= sum(loads) / n + max(units.values()) + 1e-9, loads


def test_recorded_durations_cover_real_test_ids():
    d = recorded()
    assert d and all(isinstance(v, (int, float)) and v >= 0 for v in d.values())
    assert all("::" in t and "@" not in t for t in d)


def test_aisep_shard_collections_partition_a_real_run(tmp_path):
    """End to end through pytest_collection_modifyitems: AISEP_SHARD=i/3 collections of a small suite (with a group and
    tests missing from .test_durations) are disjoint, cover it, and the grouped tests share a shard."""
    here = os.path.dirname(os.path.abspath(__file__))
    (tmp_path / "conftest.py").write_text(open(os.path.join(here, "conftest.py"), encoding="utf-8").read(), encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    body = ["import pytest"] + [f"def test_{i}(): pass" for i in range(20)]
    body += [f"@pytest.mark.xdist_group('g')\ndef test_grouped_{i}(): pass" for i in range(3)]
    body += ["@pytest.mark.parametrize('x', range(5))\ndef test_param(x): pass"]
    (tmp_path / "test_tiny.py").write_text("\n".join(body) + "\n", encoding="utf-8")
    (tmp_path / ".test_durations").write_text(json.dumps({f"test_tiny.py::test_{i}": float(i) for i in range(12)}),
                                              encoding="utf-8")
    def collect(spec):
        env = dict(os.environ, **({"AISEP_SHARD": spec} if spec else {}))
        env.pop("AISEP_SHARD", None) if not spec else None
        p = subprocess.run([PY, "-m", "pytest", "-p", "no:xdist", "-p", "no:cacheprovider", "--collect-only", "-q"],
                           cwd=tmp_path, capture_output=True, text=True, env=env)
        assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
        return [l for l in p.stdout.splitlines() if "::" in l]
    every = collect(None)
    assert len(every) == 28
    parts = [collect(f"{i}/3") for i in range(3)]
    assert sorted(sum(parts, [])) == sorted(every)            # union = all, and (as a multiset) no test twice
    assert all(parts)
    assert len({i for i, p in enumerate(parts) for t in p if "test_grouped_" in t}) == 1
