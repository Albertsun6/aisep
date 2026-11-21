"""L7「关口页入口」的先行契约测试：只读工具 model_branches（工具还不存在，整份文件现在应当 XFAIL）。

契约来自 ~/Desktop/AISEP/coordination/evidence-20261121/工作台前端与进度推导.md 第 2 节末尾，下面是本测试替草图做的取舍
（实现方有异议就在 PR 里提，不要改断言让它通过）：

- 经 `aisep.server.TOOLS` 注册、走 `server.call`（与其他工具同一条路径，含入参校验）；annotations 与读工具相同
  （readOnly、idempotent、非 openWorld）；出现在 workbench 画像里（agent 画像不作要求）。
- 入参接受通用的 `repo`；其余入参（如 mainRef）不作要求。
- 出参 `{"branches": [...]}`，每项至少有 `branch`、`head`、`remoteHead`、`unpushed`、`mergedIntoMain`、`hasModelChanges`。
  - `branch`：本地分支短名（`feat/model`，不带 `refs/heads/`），和 governance_record_approval 的 branch 入参同一写法。
  - `head`：本地分支头，40 位十六进制。
  - `remoteHead`：`refs/remotes/origin/<branch>` 的提交；没有远端跟踪分支时为 null。
  - `unpushed`：本地有远端没有的提交时为 true（没有远端分支也算）。
  - `mergedIntoMain`：分支头是主分支（与其他工具同一解析规则，先 origin/main）的祖先。
  - `hasModelChanges`：相对主分支的 merge-base，分支改动了 `models/` 下的 .ttl。已合入的分支不作要求。
  - 主分支自己是否出现在列表里不作要求。
- 只读：不改工作区、索引、引用，也不 fetch（不产生 FETCH_HEAD、不改远端跟踪引用）。
  索引也在哈希里：`git status`、带工作区的 `git diff` 可能顺手刷新并重写 index，实现里用 plumbing 命令
  （for-each-ref、rev-parse、merge-base、diff-tree 等），或设 `GIT_OPTIONAL_LOCKS=0`。

实现时摘掉下面的 `L7` 标记（strict：不摘会 XPASS 失败）。只有「工具未注册」被当作 XFAIL；工具注册之后任何断言失败都按失败报出。
"""
import glob, hashlib, os, re, subprocess

import pytest

from aisep import server as S
from aisep import tools as T
from fixtures.defect import expect, open_defect
from fixtures.topology import Topo

L7 = open_defect("L7", "model_branches 契约")
NAME = "model_branches"
FIELDS = {"branch", "head", "remoteHead", "unpushed", "mergedIntoMain", "hasModelChanges"}


def require_tool():
    expect(NAME in S.TOOLS, f"{NAME} 还没在 aisep.server.TOOLS 注册")


@pytest.fixture
def topo(template, tmp_path):
    """main 已推送；四个分支：
    feat/model   改模型，已推送，未合入
    feat/docs    只改非模型文件，未推送
    feat/ahead   改模型，推送后本地又多一个提交
    feat/merged  改模型，已推送，已合入 main（main 已推送）"""
    t = Topo(template, tmp_path)
    t.checkout("main", new="feat/model")
    t.heads = {"feat/model": t.add_element("branchThing", "分支元素")}
    t.push("feat/model")
    t.checkout("main", new="feat/docs")
    t.write("docs/branch-note.md", "只改文档\n")
    t.heads["feat/docs"] = t.commit_all("docs only")
    t.checkout("main", new="feat/ahead")
    t.pushed_ahead = t.add_element("aheadOne", "先推送的")
    t.push("feat/ahead")
    t.heads["feat/ahead"] = t.add_element("aheadTwo", "没推送的")
    t.checkout("main", new="feat/merged")
    t.heads["feat/merged"] = t.add_element("mergedThing", "已合入的")
    t.push("feat/merged")
    t.checkout("main")
    t.git("merge", "-q", "--no-ff", "-m", "merge feat/merged", "feat/merged")
    t.push("main")
    # 夹具前提
    assert t.rev("refs/remotes/origin/main") == t.rev("main")
    assert t.rev("refs/remotes/origin/feat/ahead") == t.pushed_ahead != t.heads["feat/ahead"]
    assert subprocess.run(["git", "-C", str(t.root), "show-ref", "--verify", "--quiet", "refs/remotes/origin/feat/docs"]
                          ).returncode != 0
    assert not os.path.exists(os.path.join(t.git("rev-parse", "--absolute-git-dir"), "FETCH_HEAD"))
    return t


def branches(t):
    res = S.call(T.Config(allow_roots=(str(t.tmp),)), NAME, {"repo": str(t.root)})
    assert not res.is_error, res.content[0].text
    out = res.structured_content
    assert isinstance(out.get("branches"), list), out
    for b in out["branches"]:
        assert FIELDS <= set(b), b
    by = {b["branch"]: b for b in out["branches"]}
    assert len(by) == len(out["branches"]), "同一分支出现了两次"
    return by


def digest(*dirs):
    """工作区所有文件 + 每个 git 目录下的引用、HEAD、index、packed-refs、FETCH_HEAD。"""
    h = hashlib.sha256()
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(str(d), "**", "*"), recursive=True)):
            if os.path.isfile(f) and "__pycache__" not in f and os.sep + "objects" + os.sep not in f:
                h.update(f.encode() + open(f, "rb").read())
        for gd in (os.path.join(str(d), ".git"), str(d)):
            for f in sorted(glob.glob(os.path.join(gd, "refs", "**", "*"), recursive=True)):
                if os.path.isfile(f):
                    h.update(f.encode() + open(f, "rb").read())
            for f in ("HEAD", "index", "packed-refs", "FETCH_HEAD"):
                p = os.path.join(gd, f)
                h.update(p.encode() + (open(p, "rb").read() if os.path.isfile(p) else b"<none>"))
    return h.hexdigest()


# ------------------------------------------------------------------ 注册与画像

@L7
def test_registered_read_only_in_workbench_profile():
    require_tool()
    ann = S.TOOLS[NAME][4]
    assert ann.get("read_only_hint") is True and ann.get("idempotent_hint") is True and ann.get("open_world_hint") is False
    assert not ann.get("destructive_hint")
    assert NAME in S.listed("workbench")
    assert "repo" in S.TOOLS[NAME][2]["properties"]


# ------------------------------------------------------------------ 各分支的 Git 事实

@L7
def test_pushed_unmerged_model_branch(topo):
    require_tool()
    b = branches(topo)["feat/model"]
    h = topo.heads["feat/model"]
    assert re.fullmatch(r"[0-9a-f]{40}", b["head"]) and b["head"] == h
    assert b["remoteHead"] == h and b["unpushed"] is False
    assert b["mergedIntoMain"] is False and b["hasModelChanges"] is True


@L7
def test_unpushed_branch_without_model_changes(topo):
    require_tool()
    b = branches(topo)["feat/docs"]
    assert b["head"] == topo.heads["feat/docs"]
    assert b["remoteHead"] is None and b["unpushed"] is True
    assert b["mergedIntoMain"] is False and b["hasModelChanges"] is False


@L7
def test_local_ahead_of_remote(topo):
    require_tool()
    b = branches(topo)["feat/ahead"]
    assert b["head"] == topo.heads["feat/ahead"] and b["remoteHead"] == topo.pushed_ahead
    assert b["unpushed"] is True and b["mergedIntoMain"] is False and b["hasModelChanges"] is True


@L7
def test_merged_branch(topo):
    require_tool()
    b = branches(topo)["feat/merged"]
    assert b["head"] == b["remoteHead"] == topo.heads["feat/merged"]
    assert b["unpushed"] is False and b["mergedIntoMain"] is True


@L7
def test_merged_is_judged_against_origin_main_not_stale_local_main(topo):
    """与其他工具同一规则：主分支先取 origin/main。本地 main 落后时，已合入 origin/main 的分支仍算已合入。"""
    require_tool()
    t = topo
    t.checkout("main", new="feat/late")
    late = t.add_element("lateThing", "后合入的")
    t.push("feat/late")
    t.git("push", "-q", "origin", "feat/late:main")  # 远端 main 快进到 feat/late，本地 main 不动
    assert t.rev("refs/remotes/origin/main") == late != t.rev("refs/heads/main")
    t.checkout("main")
    assert branches(t)["feat/late"]["mergedIntoMain"] is True


# ------------------------------------------------------------------ 只读

@L7
def test_read_only_and_no_fetch(topo):
    require_tool()
    before = digest(topo.root, topo.origin)
    branches(topo)
    assert digest(topo.root, topo.origin) == before
    assert topo.git("status", "--porcelain") == ""
