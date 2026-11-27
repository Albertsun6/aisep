"""Rebuild aisep-mcp/tests/.test_durations (per-test seconds that the CI shards are balanced by, see conftest.py) from the
JUnit XML the gate workflow's pytest-shard and negatives-shard jobs upload as artifacts.

    gh run download <run-id> -R Albertsun6/aisep -p 'junit-*' -D /tmp/junit   # one or more runs, all 8 shards each
    python tools/update_test_durations.py /tmp/junit [more dirs or .xml files]

A test's time is JUnit's testcase time (setup + call + teardown); seen in several runs it takes the median, which damps the
2x spread between runner CPUs. The file is rewritten from the given XML alone, so pass every shard of a run: a test that is
missing (deleted, renamed) drops out and is counted as the mean until the next refresh."""
import glob, json, os, statistics, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "aisep-mcp", "tests", ".test_durations")


def nodeid(case):
    # the tests live directly under the pytest rootdir (aisep-mcp/tests) with no test classes, so classname is the module
    return case.get("classname").replace(".", "/") + ".py::" + case.get("name")


def main(paths):
    files = [f for p in paths for f in (glob.glob(os.path.join(p, "**", "*.xml"), recursive=True) if os.path.isdir(p) else [p])]
    if not files:
        sys.exit(f"no JUnit XML under {paths}")
    seen = {}
    for f in files:
        for case in ET.parse(f).iter("testcase"):
            seen.setdefault(nodeid(case), []).append(float(case.get("time") or 0))
    data = {t: round(statistics.median(v), 3) for t, v in sorted(seen.items())}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0, ensure_ascii=False)
        f.write("\n")
    print(f"{len(data)} tests from {len(files)} files, {sum(data.values()):.0f}s in all -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
