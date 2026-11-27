"""S7: the server runs tools concurrently (anyio.to_thread), so model_gate / model_findings must be thread-safe.
rdflib's SPARQL parser is not: pyparsing's _trim_arity learns each parse action's arity on its first calls by catching
TypeErrors, unsynchronised, so threads that parse SPARQL for the first time at once raise TypeErrors from inside
pyparsing (e.g. "Param.postParse2() missing 1 required positional argument"). Only a cold process shows it, so every
round is a fresh interpreter whose very first L3 runs are the concurrent ones.

Left to chance the threads reach their first SPARQL parse seconds apart (L1/L2 and the turtle loads come first), and
one round in several slipped through without the lock. So the script lines them up exactly where the race is: every
SPARQL text rdflib parses goes through rdflib.plugins.sparql.processor.parseQuery (prepareQuery and Graph.query
alike), and the wrapper below holds each gate thread at its first parse until all of them are there (Barrier). With
core's L3 lock only one thread can be inside L3, so the barrier never fills: that thread waits MEET seconds, the
barrier breaks and everyone carries on (a broken barrier no longer blocks). Without the lock all gate threads start
the same cold parse together, which fails nearly every time, and a filled barrier is itself the proof that L3 ran
unserialised, so the test does not hinge on pyparsing actually mis-learning."""
import json, subprocess, sys

import pytest

from conftest import ROOT

ROUNDS = 2
SCRIPT = r"""
import json, sys, threading
sys.path.insert(0, sys.argv[1])
from aisep import tools as T
import rdflib.plugins.sparql.processor as P
KINDS, MEET = ("gate", "findings", "gate", "gate"), 5.0  # model_findings runs no L3, so it never reaches parseQuery
cfg, repo = T.Config(), sys.argv[2]
out = {"errors": [], "results": {}, "parsers": 0, "met": False}
start, meet, seen = threading.Barrier(len(KINDS)), threading.Barrier(KINDS.count("gate")), set()
parse = P.parseQuery
def first_parse_together(*a, **k):
    me = threading.get_ident()
    if me not in seen:
        seen.add(me)
        try:
            meet.wait(MEET)
            out["met"] = True
        except threading.BrokenBarrierError:
            pass
    return parse(*a, **k)
P.parseQuery = first_parse_together
def call(i, kind):
    start.wait()
    try:
        res = (T.model_gate if kind == "gate" else T.model_findings)(cfg, repo=repo)
        out["results"][f"{i}:{kind}"] = res["findings"]
    except Exception as e:
        out["errors"].append(f"{kind}: {type(e).__name__}: {e}")
threads = [threading.Thread(target=call, args=(i, k)) for i, k in enumerate(KINDS)]
for t in threads: t.start()
for t in threads: t.join()
P.parseQuery = parse
out["parsers"] = len(seen)
out["sequential"] = {k: (T.model_gate if k == "gate" else T.model_findings)(cfg, repo=repo)["findings"] for k in ("gate", "findings")}
print(json.dumps(out))
"""


# Each round is its own test case (a fresh interpreter either way), so the rounds can run on different workers and shards
# instead of one ~60 s test in a single shard.
@pytest.mark.parametrize("r", range(ROUNDS))
def test_concurrent_gate_and_findings_in_a_cold_process(repo, r):
    p = subprocess.run([sys.executable, "-c", SCRIPT, ROOT, str(repo)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-2000:]
    out = json.loads(p.stdout.strip().splitlines()[-1])
    # the hook must actually see L3's SPARQL parses, or this test silently stops lining the threads up
    assert out["parsers"] >= 1, f"round {r}: no SPARQL text went through rdflib's processor.parseQuery"
    assert not out["errors"], (f"round {r}: {len(out['errors'])} of 4 concurrent calls raised "
                               f"(gate threads met at the first parse: {out['met']}): {out['errors'][:3]}")
    # the race is timing-dependent, its cause is not: gate threads parsing SPARQL at the same moment means L3 is
    # not serialised, even in a round where pyparsing happened to learn every arity right
    assert not out["met"], f"round {r}: all gate threads were inside L3's first SPARQL parse at once (L3 not serialised)"
    for key, findings in out["results"].items():
        assert findings == out["sequential"][key.split(":")[1]], f"round {r}: concurrent {key} differs from sequential"
