"""core build_triples X1 Violation (blank node carrying arch:inModel in a model source): the finding must point at the
source file and be stable across builds.

Contract (independent test author): for the layer "build" Violation in ctx.instances
  - its file field == the repo-relative path of the source file (e.g. models/procurement/x1-blank.ttl);
  - the message contains that relative path;
  - two independent builds (two fresh Ctx) give exactly the same message string;
  - the message has no "::";
  - the message has no `_:` followed by a store-generated random blank node id.
Shapes as in test_r4_own1_x1.py."""
import os, re

import pytest

from aisep import core, gitio
from test_r4_own1_x1 import BLANK_CASES, X1_PREFIXES

REL = "models/procurement/x1-blank.ttl"


def _ctx(root):
    files = sorted(gitio.model_files(root))
    assert REL in files, files
    return core.Ctx(core.discover(root), [os.path.join(root, f) for f in files], root=root)


def _x1(ctx):
    hits = [i for i in ctx.instances if i[0] == "Violation" and i[1] == "build"]
    assert len(hits) == 1, hits
    return hits[0]


@pytest.mark.parametrize("case", sorted(BLANK_CASES))
def test_x1_violation_names_file_and_is_stable(repo, case):
    root = str(repo)
    with open(os.path.join(root, REL), "w", encoding="utf-8") as f:
        f.write(X1_PREFIXES + BLANK_CASES[case])
    sev, layer, msg, focus, rule, file = _x1(_ctx(root))
    msg2 = _x1(_ctx(root))[2]

    assert file == REL, (file, msg)
    assert REL in msg, msg
    assert msg == msg2, (msg, msg2)
    assert "::" not in msg, msg
    # a generated blank node label: `_:` followed by a long run of id characters (pyoxigraph emits 32 hex digits)
    assert not re.search(r"_:[0-9A-Za-z]{8,}", msg), msg
