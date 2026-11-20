"""S7: the server runs tools concurrently (anyio.to_thread), so model_gate / model_findings must be thread-safe.
rdflib's SPARQL parser is not: pyparsing's _trim_arity learns each parse action's arity on its first calls by catching
TypeErrors, unsynchronised, so threads that parse SPARQL for the first time at once raise TypeErrors from inside
pyparsing (e.g. "Param.postParse2() missing 1 required positional argument"). Only a cold process shows it, so every
round is a fresh interpreter whose very first L3 runs are the concurrent ones."""
import json, subprocess, sys

from conftest import ROOT

ROUNDS = 2
SCRIPT = r"""
import json, sys, threading
sys.path.insert(0, sys.argv[1])
from aisep import tools as T
cfg, repo = T.Config(), sys.argv[2]
out = {"errors": [], "results": {}}
def call(i, kind):
    try:
        res = (T.model_gate if kind == "gate" else T.model_findings)(cfg, repo=repo)
        out["results"][f"{i}:{kind}"] = res["findings"]
    except Exception as e:
        out["errors"].append(f"{kind}: {type(e).__name__}: {e}")
threads = [threading.Thread(target=call, args=(i, k)) for i, k in enumerate(("gate", "findings", "gate", "gate"))]
for t in threads: t.start()
for t in threads: t.join()
out["sequential"] = {k: (T.model_gate if k == "gate" else T.model_findings)(cfg, repo=repo)["findings"] for k in ("gate", "findings")}
print(json.dumps(out))
"""


def test_concurrent_gate_and_findings_in_a_cold_process(repo):
    for r in range(ROUNDS):
        p = subprocess.run([sys.executable, "-c", SCRIPT, ROOT, str(repo)], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-2000:]
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert not out["errors"], f"round {r}: {len(out['errors'])} of 4 concurrent calls raised: {out['errors'][:3]}"
        for key, findings in out["results"].items():
            assert findings == out["sequential"][key.split(":")[1]], f"round {r}: concurrent {key} differs from sequential"
