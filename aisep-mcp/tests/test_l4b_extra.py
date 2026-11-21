"""L4-B 补充回归：先行测试（test_l4b_entry_validation.py）之外、实现时发现或顺带守护的几条。

- 评审 #56 里的粘连写法、伪 IRI、字符串与 IRI 内转义：查询进程无网络（issue #60），都报 QUERY_NOT_READONLY 且零连接；差分模糊
- gitio.read_file / open_dir 拒绝 `.`、`..`、空段
- 批准路径与读工具共用模型 slug 校验
- SEC-3：检出里伪造的嵌套仓库不执行它的 fsmonitor、过滤器
- core.short() 对 `/` 结尾的模型 IRI 保持完整
"""
import os

import pytest

from aisep import approval as A
from aisep import core, gitio
from aisep import tools as T
from aisep.errors import AisepError
from conftest import git
from fixtures.topology import M, Topo
from test_l4b_entry_validation import cfg, listener


# 评审 #56 第一轮（blocker）：粘在关键字后的前缀名、伪 IRI 里的 SERVICE。pyoxigraph 都把它们读成 SERVICE 并真的外连。
GLUED = {
    "SERVICE:q": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "OPTIONAL service:q": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { OPTIONAL{ service:q { ?a ?b ?c } } }",
    "伪IRI": "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { FILTER(1<2)SERVICE:q#>\n{ ?a ?b ?c } }",
    "伪IRI里的引号": "SELECT * WHERE { FILTER(1<2&&'>'=?x)SERVICE<http://127.0.0.1:{port}/q>{ ?a ?b ?c } #'\n}",
    # 评审 #56 第三轮：字符串与 IRI 里的转义（pyoxigraph 在这两处解码 \uXXXX），旧扫描器把后面的 SERVICE 当成注释吞掉
    "字符串与IRI内转义": ("SELECT * WHERE { BIND(\"\\u0022#\" AS ?z) VALUES ?u {<http://x.example/A\\u0023A>} "
                   "SERVICE <http://127.0.0.1:{port}/q> {?a ?b ?c}\n}"),
    "真IRI里的引号": "SELECT * WHERE { OPTIONAL { ?s ?p <http://x.example/a'b> } SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } #'\n}",
}


@pytest.mark.parametrize("name", sorted(GLUED))
def test_glued_service_really_connects_without_the_filter(name):
    """前提：这些写法在不加过滤时 pyoxigraph 确实发起连接（否则下面的拒绝测试证明不了什么）。"""
    import pyoxigraph as ox
    with listener() as (port, hits):
        try:
            list(ox.Store().query(GLUED[name].replace("{port}", str(port))))
        except Exception:  # noqa: BLE001 — 没有 HTTP 响应，pyoxigraph 报错；只看有没有连接
            pass
    assert hits, f"{name}：pyoxigraph 没有把它读成 SERVICE"


@pytest.mark.parametrize("name", sorted(GLUED))
def test_glued_service_is_refused(repo, name):
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), GLUED[name].replace("{port}", str(port)))
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()
    assert not hits


@pytest.mark.parametrize("rel", ["models/../models/procurement/am4.ttl", "./models/procurement/am4.ttl",
                                 "models//procurement/am4.ttl", "models/procurement/.", ".."])
def test_read_file_refuses_unnormalised_paths(repo, rel):
    with pytest.raises(gitio.UnsafeFile):
        gitio.read_file(str(repo), rel)


@pytest.mark.parametrize("rel", ["models/..", "../x", "models/./procurement"])
def test_open_dir_refuses_dot_segments(repo, rel):
    with pytest.raises(gitio.UnsafeFile):
        gitio.open_dir(str(repo), rel)


def test_read_file_and_open_dir_still_work(repo):
    assert gitio.read_file(str(repo), "models/procurement/am4.ttl")
    os.close(gitio.open_dir(str(repo), "models/procurement/"))


@pytest.mark.parametrize("model", ["procurement/", "../procurement", "https://aisep.example/model/procurement/../x/"])
def test_approval_rejects_malformed_model_before_git(template, tmp_path, model):
    t = Topo(template, tmp_path)
    t.checkout("main", new="feat/x")
    head = t.add_element("newThing", "新东西")
    with pytest.raises(AisepError) as ei:
        A.governance_record_approval(T.Config(allow_roots=(str(t.tmp),)), model=model, gate="GateArchitecture",
                                     decision="Approved", approvedBy=M + "chiefArchitect", approves=[M + "newThing"],
                                     branch="feat/x", headCommit=head, repo=str(t.root))
    assert ei.value.code == "INVALID_ARGUMENT" and ei.value.details["rejectedFields"] == ["model"]
    assert t.rev("refs/heads/feat/x") == head


def test_short_keeps_slash_terminated_model_iri():
    assert core.short(M) == M
    assert core.short(M + "supplier") == "procurement:supplier"


# 评审 #56 第一、二轮（major）：检出里的伪 .git 子目录（嵌套仓库）不能执行它 config 里的命令：fsmonitor（ls-files）、
# filter.<x>.smudge（带 ref 的快照走 git archive）、filter.<x>.clean（model_diff 的 worktree 模式走 git status）。
# 伪仓库带齐 modules/ vendor/ models/，免得在 git 命令之前就因缺目录被拒、测不到开关。
def _planted_repo(repo, marker):
    import shutil
    evil = repo / "models" / "evil"
    evil.mkdir(parents=True)
    for d in ("modules", "vendor", "models/procurement"):
        shutil.copytree(repo / d, evil / d)
    (evil / ".gitattributes").write_text("*.ttl filter=x\n")
    git(evil, "init", "-q", "-b", "main")
    git(evil, "add", "--", ".")
    git(evil, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    cmd = f"echo hit >> '{marker}'; cat"
    git(evil, "config", "filter.x.smudge", cmd)
    git(evil, "config", "filter.x.clean", cmd)
    git(evil, "config", "core.fsmonitor", f"echo hit >> '{marker}'; false")
    os.utime(evil / "models" / "procurement" / "am4.ttl", (1, 1))  # stat 变了，git status 会重跑 clean
    return evil


CALLS = {
    "model_check": lambda c, e: T.model_check(c, repo=str(e)),
    "model_gate": lambda c, e: T.model_gate(c, repo=str(e)),
    "model_check(ref)": lambda c, e: T.model_check(c, repo=str(e), ref="HEAD"),
    "model_diff(worktree)": lambda c, e: __import__("aisep.diff").diff.model_diff(c, head={"worktree": "main"},
                                                                                  repo=str(e)),
}


@pytest.mark.parametrize("name", sorted(CALLS))
def test_sec3_nested_repo_does_not_run_its_config(repo, tmp_path, name):
    marker = tmp_path / "MARKER"
    evil = _planted_repo(repo, marker)
    assert not marker.exists(), "夹具：搭建时不该触发"
    err = None
    try:
        CALLS[name](cfg(repo), evil)
    except Exception as e:  # noqa: BLE001 — 先判标记文件，再判异常类型
        err = e
    assert not marker.exists(), f"{name}(repo=<伪 .git 子目录>) 执行了它 config 里的命令；结果：{err!r}"
    assert isinstance(err, AisepError) and err.details.get("reason") == "nested-repository", repr(err)


def test_fsmonitor_is_off_for_every_git_call(tmp_path):
    """第二道防线：即使是允许的仓库，服务器的 git 调用也不跑 core.fsmonitor。"""
    marker = tmp_path / "MARKER"
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q")
    (r / "a.ttl").write_text("")
    git(r, "config", "core.fsmonitor", f"echo hit >> '{marker}'; false")
    assert git(r, "-c", "core.fsmonitor=", "ls-files") is not None and not marker.exists()
    gitio.git(str(r), "ls-files", "--others")
    gitio.git(str(r), "status", "--porcelain")
    assert not marker.exists()
    git(r, "status", "--porcelain", check=False)
    assert marker.exists(), "夹具：不加开关时 git 确实会跑这个 fsmonitor"


# 评审 #56 第二、三轮：差分模糊。原先以词法判定为对象；issue #60 起查询在无网络子进程里执行、不再识别文本，判据改成：
# 抽样的每条变形查询（加随机字符级变异）经 querybox.run（model_query 用的同一函数）执行，无论被接受还是报错都零连接；
# 同一批里抽一部分直接交给进程内的 pyoxigraph，确认这批变形里确有真会外连的。
_I = chr(0x130)  # İ：lower() 后变成两个码点
_PADS = ["", " ", "# c\n", "# " + _I * 12 + "\n", "#" + _I * 30 + "\n",
         "PREFIX x: <http://x.example/" + _I * 40 + "> ", "BASE <http://x.example/" + _I * 9 + "/> "]
_KEYWORDS = ["SERVICE", "service", "SeRvIcE", "\\" + "u0053ERVICE", chr(0x17F) + "ervice"]
_E = "\\"  # 一个字面反斜杠：SPARQL 的码点转义
_BEFORE = [" ", "{}", "BIND(1 AS ?x)", "FILTER(1<2)", "OPTIONAL{}", "?s ?p ?o .", "FILTER(1<2&&'>'=?y)",
           "BIND('" + _I * 20 + "' AS ?w)",
           # 字符串与 IRI 内的转义（评审 #56 第三轮的维度）：解出引号、#、> 后改变后文的切分
           'BIND("' + _E + 'u0022#" AS ?z) ', "VALUES ?u {<http://x.example/A" + _E + "u0023A>} ",
           "BIND('" + _E + "u0027' AS ?z) ", "VALUES ?u {<http://x.example/A" + _E + "u0041>} "]
_AFTER = [" ", "", " SILENT ", "#c\n", "\t"]
_ENDPOINTS = ["<http://127.0.0.1:{port}/q>", ":q", "?e"]


def _fuzz_queries(port):
    for pad in _PADS:
        for kw in _KEYWORDS:
            for before in _BEFORE:
                for after in _AFTER:
                    for ep in _ENDPOINTS:
                        values = "VALUES ?e {<http://127.0.0.1:{port}/q>} " if ep == "?e" else ""
                        q = (pad + "PREFIX : <http://127.0.0.1:{port}/> SELECT * WHERE { " + values + before + kw + after
                             + ep + "{ ?a ?b ?c } } #'\n")
                        yield q.replace("{port}", str(port))


def _run(q):
    import pyoxigraph as ox
    try:
        list(ox.Store().query(q))
    except Exception:  # noqa: BLE001 — 只看有没有连接
        pass


_MUT = ["SERVICE", "service", " ", "#", "\n", "'", '"', "<", ">", ":", "{", "}", _E + "u0053", _E + "u0022", _I, "?e "]


def _mutate(rng, q):
    for _ in range(rng.randint(1, 4)):
        i = rng.randrange(len(q) + 1)
        q = q[:i] + rng.choice(_MUT) + q[i + rng.choice((0, 0, 1)):]
    return q


def test_service_differential_fuzz():
    import random, time
    from aisep import querybox
    import pyoxigraph as ox
    seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    with listener() as (port, hits), listener() as (port2, hits2):
        pick = sorted(rng.sample(range(len(list(_fuzz_queries(0)))), 150))
        base = [list(_fuzz_queries(p)) for p in (port, port2)]
        mutated = [_mutate(random.Random(seed + i), base[0][i]) for i in pick]
        queries = [base[0][i] for i in pick] + mutated
        outcomes = {}
        for q in queries:
            try:
                querybox.run(ox.Store(), q, {}, 10, 10)
                outcomes["accepted"] = outcomes.get("accepted", 0) + 1
            except Exception as e:  # noqa: BLE001 — 只看有没有连接；结果分布写进失败信息
                outcomes[type(e).__name__] = outcomes.get(type(e).__name__, 0) + 1
        for i in pick[::5]:
            _run(base[1][i])
        time.sleep(0.3)  # listener 线程记账
    assert not hits, f"{len(hits)} 次连接来自无网络子进程里执行的查询（seed={seed}，结果分布 {outcomes}）"
    assert hits2, f"抽样直接交给 pyoxigraph 的变形一次也没外连：这批变形测不到真 SERVICE（seed={seed}）"
    assert outcomes.get("NetworkAttempt"), f"没有一条被认出为联网尝试（seed={seed}，{outcomes}）"


# 评审 #56 第三轮：两层嵌套（gitdir 文件指回被拒的伪仓库）、伪造的 linked worktree 管理目录（commondir 指向真 .git，
# 主仓库开着 extensions.worktreeConfig，管理目录里的 config.worktree 会被读）都要被拒，且不执行其中的过滤器
def _two_level(repo, marker):
    evil = _planted_repo(repo, marker)
    sub = evil / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git\n")
    return sub


def _forged_linked_worktree(repo, marker):
    import shutil
    git(repo, "config", "extensions.worktreeConfig", "true")
    adm = repo / "models" / "adm"
    adm.mkdir(parents=True)
    wt = repo / "models" / "fakewt"
    for d in ("modules", "vendor", "models/procurement"):
        shutil.copytree(repo / d, wt / d)
    (wt / ".gitattributes").write_text("*.ttl filter=x\n")
    (wt / ".git").write_text(f"gitdir: {adm}\n")
    (adm / "HEAD").write_text(git(repo, "rev-parse", "HEAD").strip() + "\n")
    (adm / "commondir").write_text(os.path.relpath(repo / ".git", adm) + "\n")
    (adm / "gitdir").write_text(f"{wt / '.git'}\n")
    cmd = f"echo hit >> '{marker}'; cat"
    (adm / "config.worktree").write_text(f"[filter \"x\"]\n\tsmudge = {cmd}\n\tclean = {cmd}\n")
    return wt


FORGED = {"two-level": _two_level, "forged-linked-worktree": _forged_linked_worktree}


@pytest.mark.parametrize("call", ["model_check", "model_check(ref)", "model_diff(worktree)"])
@pytest.mark.parametrize("kind", sorted(FORGED))
def test_sec3_forged_worktrees_are_refused(repo, tmp_path, kind, call):
    marker = tmp_path / "MARKER"
    target = FORGED[kind](repo, marker)
    assert git(target, "rev-parse", "--show-toplevel").strip() == os.path.realpath(target), "夹具：git 把它当成工作区"
    assert not marker.exists()
    err = None
    try:
        CALLS[call](cfg(repo), target)
    except Exception as e:  # noqa: BLE001 — 先判标记文件，再判异常类型
        err = e
    assert not marker.exists(), f"{call}(repo=<{kind}>) 执行了过滤器；结果：{err!r}"
    assert isinstance(err, AisepError) and err.code == "NOT_A_GIT_REPO", repr(err)


def test_registered_worktree_inside_main_checkout_is_accepted(repo):
    """正向：放在主检出工作区内部、登记过的 linked worktree（本机 .claude/worktrees/* 的布局）照常可用。"""
    wt = repo / ".claude" / "worktrees" / "x"
    git(repo, "worktree", "add", "-q", "-b", "x", str(wt))
    assert T.model_check(cfg(repo), repo=str(wt))["summary"]["violations"] == 0
    assert T.model_check(cfg(repo), repo=str(repo))["summary"]["violations"] == 0
