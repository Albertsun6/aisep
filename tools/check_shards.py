"""Guard against tests silently falling out of the CI shards (gate.yml: the `pytest` and `negatives` summary jobs).

Each shard job runs pytest with AISEP_SHARD=i/n and AISEP_SHARD_MANIFEST=<file>; conftest.py writes there, before it
filters, the sha256 of the sorted nodeids it collected (the whole suite), that list, and the nodeids it kept. Every shard
must have collected the same suite, and the kept lists must split it exactly; otherwise a test that one shard dropped from
its collection (a different checkout, an import that failed only there) would be run by no shard and nobody would notice.

    python tools/check_shards.py <n> <dir with the n manifests, searched recursively>

Exit 0 and a one-line summary when the manifests agree, else exit 1 and print each problem."""
import glob, hashlib, json, os, sys


def digest(ids):
    """sha256 of the sorted nodeids, one per line; conftest.py writes the same."""
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def problems(manifests, n):
    """manifests: [dict as conftest.py writes it] -> list of problems (empty when the n shards partition one suite)."""
    out = []
    by_shard = {}
    for m in manifests:
        by_shard.setdefault(m.get("shard"), []).append(m)
    for i in sorted(set(range(n)) | set(by_shard), key=str):
        got = by_shard.get(i, [])
        if len(got) != 1 or i not in range(n) or got[0].get("n") != n:
            out.append(f"shard {i}: {len(got)} manifest(s), n={[m.get('n') for m in got]}; want exactly one per shard 0..{n - 1}, n={n}")
    if out:
        return out
    shards = [by_shard[i][0] for i in range(n)]
    for i, m in enumerate(shards):
        if digest(m["all"]) != m["sha256"] or len(m["all"]) != m["total"] or len(m["kept"]) != m["count"]:
            out.append(f"shard {i}: manifest is not self-consistent (sha256/total/count vs its lists)")
    ref = shards[0]
    for i, m in enumerate(shards[1:], 1):
        if m["sha256"] != ref["sha256"]:
            a, b = set(ref["all"]), set(m["all"])
            out.append(f"shard {i}: collected suite sha256 {m['sha256'][:12]} ({m['total']} tests) != shard 0's "
                       f"{ref['sha256'][:12]} ({ref['total']} tests); only in shard 0: {sorted(a - b)[:20]}, "
                       f"only in shard {i}: {sorted(b - a)[:20]}")
    if out:
        return out
    total = ref["total"]
    counts = [m["count"] for m in shards]
    if sum(counts) != total:
        out.append(f"per-shard counts {counts} sum to {sum(counts)}, the collected suite has {total}")
    kept = [t for m in shards for t in m["kept"]]
    missing, extra = set(ref["all"]) - set(kept), set(kept) - set(ref["all"])
    twice = sorted({t for t in kept if kept.count(t) > 1}) if len(kept) != len(set(kept)) else []
    if missing or extra or twice:
        out.append(f"shards do not partition the suite: run by no shard {sorted(missing)[:20]}, not in the suite "
                   f"{sorted(extra)[:20]}, in two shards {twice[:20]}")
    return out


def main(argv):
    n, root = int(argv[0]), argv[1]
    manifests = []
    for f in sorted(glob.glob(os.path.join(root, "**", "*.json"), recursive=True)):
        with open(f, encoding="utf-8") as fh:
            manifests.append(json.load(fh))
    bad = problems(manifests, n)
    for p in bad:
        print(f"[shard-check] {p}")
    if bad:
        return 1
    print(f"[shard-check] {n} shards, one suite of {manifests[0]['total']} tests (sha256 {manifests[0]['sha256'][:12]}), "
          f"counts {[m['count'] for m in sorted(manifests, key=lambda m: m['shard'])]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
