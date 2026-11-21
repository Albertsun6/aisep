"""Positive control for test_r1_blank_node_approval_shape.py: there the approval commits are hand-built by the fixture;
here the commit comes from the real governance_record_approval, and mergecheck._commit_shape must accept it (None)."""
from aisep import mergecheck
from test_record_approval_review import call, t  # noqa: F401  (t is a fixture)


def test_real_record_approval_commit_is_approval_commit(t):
    r = call(t)
    c = r["commit"]
    assert c and r["duplicate"] is False, r
    assert t.rev("refs/heads/feat/x") == c
    assert t.rev(f"{c}^") == t.head  # the commit sits right on headCommit
    mergecheck._commit_shape.cache_clear()
    assert mergecheck._commit_shape(str(t.root), c) is None
