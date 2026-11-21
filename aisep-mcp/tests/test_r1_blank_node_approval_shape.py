"""第四轮复评 R1（major）：批准提交形状里的空白节点。

docs/metamodel-spec.md §5.9 第 1 步 (c) / 第四轮 R4-8：批准提交新增的文件里，主语只能是那条批准记录和它的可选活动。
`aisep.mergecheck._commit_shape` 只收集命名节点主语，`aisep.diff` 的 Side 又跳过空白节点主语，于是新文件可以夹带
空白节点关系（例如 `:approval-… skos:note [ a am4:Association ; arch:source … ; arch:target … ]`）仍被判为批准提交。

口径：新文件只要出现空白节点主语，或者记录、活动的三元组宾语里有空白节点，`_commit_shape` 就返回非 None。
每个负例都有同一构造器上的正例（无空白节点的批准提交仍为 None、端到端干净）。
"""
from datetime import datetime, timezone

import pytest

from fixtures.topology import Topo

from aisep import mergecheck

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
MAIN = "refs/heads/main"
BRANCH = "feat/x"


@pytest.fixture
def t(template, tmp_path):
    mergecheck._commit_shape.cache_clear()
    return Topo(template, tmp_path)


def feature(t):
    t.checkout("main", new=BRANCH)
    return t.add_element("newThing", "新东西")


def activity(t, head):
    return dict(local=f"activity-20261120110000-{head[:7]}", head=head, base=t.merge_base(head, MAIN), branch=BRANCH)


def shape(t, c):
    mergecheck._commit_shape.cache_clear()
    return mergecheck._commit_shape(str(t.root), c)


def problems(t, head):
    return mergecheck.merge_check(str(t.root), head, MAIN, head_ref=BRANCH, now=NOW)


def assert_file_added_only(t, c):
    """构造自检：c 只新增了一个 governance/*.ttl（形状的 (a)(b) 部分成立，漏洞只能在 (c)）。"""
    out = t.git("diff-tree", "-r", "--no-commit-id", "--name-status", f"{c}^", c).splitlines()
    assert len(out) == 1 and out[0].startswith("A\t") and "/governance/" in out[0], out


# ------------------------------------------------------------------ 负例 1：空白节点主语夹带关系


def test_blank_subject_association_smuggled_is_not_approval_commit(t):
    h = feature(t)
    local = f"approval-20261120110000-architecture-{h[:7]}"
    # 不带 arch:inModel：带上它时 core.build_triples 会因空白节点 IRI 抛 ValueError，打不到 _commit_shape 的漏洞
    smuggle = f"\n:{local} skos:note [ a am4:Association ; arch:source :auditTrail ; arch:target :newThing ] .\n"
    c, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h, local=local, extra_ttl=smuggle)
    assert_file_added_only(t, c)
    assert "am4:Association" in t.git("show", f"{c}:models/procurement/governance/{local}.ttl")

    assert shape(t, c) is not None, "新文件含空白节点主语，不应判为批准提交"

    hits = [p for p in problems(t, c) if p.get("reason") == "not-approval-commit"]
    assert hits, "merge_check 应报 not-approval-commit"
    assert c in {p.get("offendingCommit") for p in hits}, hits


# ------------------------------------------------------------------ 负例 2：记录 / 活动的宾语是空白节点


@pytest.mark.parametrize("bnode", ["[]", '[ skos:prefLabel "x"@zh ]'], ids=["empty", "untyped-with-label"])
def test_record_with_blank_node_object_is_not_approval_commit(t, bnode):
    h = feature(t)
    local = f"approval-20261120110000-architecture-{h[:7]}"
    c, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h, local=local,
                        extra_ttl=f"\n:{local} skos:note {bnode} .\n")
    assert_file_added_only(t, c)
    assert shape(t, c) is not None, f"记录的宾语里有空白节点 {bnode}，不应判为批准提交"


@pytest.mark.parametrize("bnode", ["[]", '[ skos:prefLabel "x"@zh ]'], ids=["empty", "untyped-with-label"])
def test_activity_with_blank_node_object_is_not_approval_commit(t, bnode):
    h = feature(t)
    a = activity(t, h)
    c, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h, activity=a,
                        extra_ttl=f"\n:{a['local']} skos:note {bnode} .\n")
    assert_file_added_only(t, c)
    assert shape(t, c) is not None, f"活动的宾语里有空白节点 {bnode}，不应判为批准提交"


# ------------------------------------------------------------------ 正例：无空白节点的批准提交


@pytest.mark.parametrize("with_activity", [False, True], ids=["record-only", "record+activity"])
def test_plain_approval_commit_still_is_approval_commit(t, with_activity):
    h = feature(t)
    c, _, _ = t.approve("GateArchitecture", ["newThing"], evidence=h,
                        activity=activity(t, h) if with_activity else None)
    assert_file_added_only(t, c)
    assert shape(t, c) is None
    assert problems(t, c) == []
