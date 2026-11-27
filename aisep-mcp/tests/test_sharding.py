"""CI sharding (conftest.assign_shards / AISEP_SHARD): the shards of one collection are a partition of it (union = all tests,
pairwise disjoint), the split depends only on the input, tests with no recorded duration still land somewhere, a group stays
in one shard, and the LPT greedy split stays within one test of the ideal load."""
import importlib.util, json, os, random, subprocess, sys

import pytest

from conftest import DURATIONS, PY, ROOT, assign_shards

_spec = importlib.util.spec_from_file_location("check_shards", os.path.join(ROOT, "tools", "check_shards.py"))
check_shards = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_shards)


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


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("AISEP_SHARD", "AISEP_SHARD_MANIFEST")}
    return dict(env, **extra)


def test_recorded_durations_cover_real_test_ids():
    """The keys of .test_durations must be the nodeids pytest collects now, as conftest sees them (rootdir aisep-mcp/tests,
    so `test_x.py::test_y[...]`). If the nodeid format changes (a new rootdir or ini, a move into a subdirectory) no key
    matches, every test is counted as the mean and the split silently degrades to round-robin by count.

    Threshold: at least 80% of the tests collected now have a recorded duration. The file is refreshed from CI JUnit now and
    then, not on every PR, so tests added or renamed since the last refresh are legitimately missing (the first file covered
    1287 of 1288); a format change drops the share to ~0%. Run from the repo root like the CI shards, with the shard
    variables cleared so the collection is the whole suite and nothing overwrites a CI manifest."""
    d = recorded()
    assert d and all(isinstance(v, (int, float)) and v >= 0 for v in d.values())
    p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "0", "--collect-only",
                        os.path.join("aisep-mcp", "tests")], cwd=ROOT, capture_output=True, text=True, env=clean_env())
    assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
    real = {l for l in p.stdout.splitlines() if "::" in l}
    assert len(real) > 1000, len(real)
    covered = len(real & set(d)) / len(real)
    assert covered >= 0.8, (f"only {covered:.0%} of the {len(real)} collected tests are in .test_durations; "
                            f"e.g. key {sorted(d)[:2]} vs nodeid {sorted(real)[:2]}")


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
        env = clean_env(**({"AISEP_SHARD": spec, "AISEP_SHARD_MANIFEST": str(tmp_path / f"m{spec[0]}.json")} if spec else {}))
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
    manifests = [json.loads((tmp_path / f"m{i}.json").read_text(encoding="utf-8")) for i in range(3)]
    assert check_shards.problems(manifests, 3) == []
    assert [m["count"] for m in manifests] == [len(p) for p in parts] and manifests[0]["total"] == 28
    assert check_shards.main(["3", str(tmp_path)]) == 0


def manifests(n=3, size=30):
    tests, durations = suite(size=size)
    shard = assign_shards(tests, durations, n)
    ids = sorted(t for t, _ in tests)
    return [{"shard": i, "n": n, "total": len(ids), "count": sum(shard[t] == i for t in ids), "all": list(ids),
             "kept": [t for t in ids if shard[t] == i], "sha256": check_shards.digest(ids)} for i in range(n)]


def test_check_shards_accepts_a_partition():
    assert check_shards.problems(manifests(), 3) == []


def test_check_shards_rejects_a_shard_that_collected_a_different_suite():
    """One shard lost a test from its collection (and so from the split): the suite hashes differ, named in the report."""
    ms = manifests()
    lost = ms[1]["all"].pop(5)
    if lost in ms[1]["kept"]:
        ms[1]["kept"].remove(lost)
    ms[1].update(total=len(ms[1]["all"]), count=len(ms[1]["kept"]), sha256=check_shards.digest(ms[1]["all"]))
    bad = check_shards.problems(ms, 3)
    assert bad and "sha256" in bad[0] and lost in bad[0], bad


def test_check_shards_rejects_counts_that_do_not_add_up():
    ms = manifests()
    ms[2]["kept"].pop()
    ms[2]["count"] -= 1
    bad = check_shards.problems(ms, 3)
    assert any("sum to" in p for p in bad) and any("run by no shard" in p for p in bad), bad


def test_check_shards_rejects_a_test_in_two_shards():
    ms = manifests()
    ms[0]["kept"].remove(t := ms[0]["kept"][0])
    ms[1]["kept"].append(t)
    ms[0]["count"] -= 1
    ms[1]["count"] += 1
    ms[2]["kept"].append(ms[1]["kept"][0])
    ms[2]["count"] += 1
    bad = check_shards.problems(ms, 3)
    assert any("in two shards" in p for p in bad), bad


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong n", "tampered"])
def test_check_shards_rejects_missing_or_inconsistent_manifests(change):
    ms = manifests()
    if change == "missing":
        ms.pop()
    elif change == "duplicate":
        ms[2] = dict(ms[1])
    elif change == "wrong n":
        ms[0]["n"] = 4
    else:
        ms[0]["all"].pop()   # list no longer matches the recorded sha256 and total
    assert check_shards.problems(ms, 3)
