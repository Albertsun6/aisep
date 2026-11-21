"""issue #60：调用方的 SPARQL 在无网络的子进程里执行（aisep/querybox.py），任何查询文本都发不出连接。

判据一律是本机回环监听上的连接计数（listener），不是只看返回了错误。外连目标只用 127.0.0.1 上自己起的监听。
- issue #60 与评审 #56 各轮的绕过样例：经 model_query 零连接；真会外连的报 QUERY_NOT_READONLY
- 不靠 pyoxigraph：子进程施加限制后自己去连 TCP / UDP / IPv6 / unix socket，进程被终止且零连接
- 失败关闭：限制建立不了时子进程不读查询就退出，model_query 报 INTERNAL，零连接
- model_impact 的 focus 用转义也拼不出 SERVICE
"""
import contextlib
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading

import pytest

from aisep import querybox
from aisep import tools as T
from aisep.errors import AisepError
from fixtures.topology import M
from test_l4b_entry_validation import REAL_SERVICE, cfg, listener

_I = chr(0x130)  # İ：lower() 后变两个码点，评审 #56 里让词法扫描下标错位
_E = "\\"
EP = "<http://127.0.0.1:{port}/q>"
PFX = "PREFIX : <http://127.0.0.1:{port}/> PREFIX ex: <http://127.0.0.1:{port}/> "

# 都是 pyoxigraph 0.5.13 会真的外连的写法（test_bypass_really_connects_in_process 证明），按来源分组
BYPASS = {
    # issue #60：main 的 \bSERVICE\b 放行
    "SERVICEex:q": PFX + "SELECT * WHERE { SERVICEex:q { ?a ?b ?c } }",
    # 评审 #56 第一轮：关键字后紧跟冒号（空前缀）
    "SERVICE:q": PFX + "SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "service:q": PFX + "SELECT * WHERE { service:q { ?a ?b ?c } }",
    "SILENT:q": PFX + "SELECT * WHERE { SERVICE SILENT:q { ?a ?b ?c } }",
    # 第二轮：被当成伪 IRI 抹掉
    "伪IRI": PFX + "SELECT * WHERE { FILTER(1<2)SERVICE:q#>\n{ ?a ?b ?c } }",
    "伪IRI里的引号": "SELECT * WHERE { FILTER(1<2&&'>'=?x)SERVICE" + EP + "{ ?a ?b ?c } #'\n}",
    # 第三轮：注释、PREFIX、BASE 里 8 个以上 İ
    "注释里的İ": "# " + _I * 12 + "\n" + PFX + "SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "PREFIX里的İ": "PREFIX x: <http://x.example/" + _I * 40 + "> " + PFX + "SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "BASE里的İ": "BASE <http://x.example/" + _I * 9 + "/> " + PFX + "SELECT * WHERE { SERVICE:q { ?a ?b ?c } }",
    "字符串里的İ": PFX + "SELECT * WHERE { BIND('" + _I * 20 + "' AS ?w) SERVICE:q { ?a ?b ?c } }",
    # 第三轮：字符串与 IRI 内的 "、# 与 # 组合
    "字符串内\\u0022#": "SELECT * WHERE { BIND(\"" + _E + "u0022#\" AS ?z) SERVICE " + EP + " {?a ?b ?c}\n}",
    "IRI内\\u0023": "SELECT * WHERE { VALUES ?u {<http://x.example/A" + _E + "u0023A>} SERVICE " + EP + " {?a ?b ?c}\n}",
    "两者组合": ("SELECT * WHERE { BIND(\"" + _E + "u0022#\" AS ?z) VALUES ?u {<http://x.example/A" + _E + "u0023A>} "
             "SERVICE " + EP + " {?a ?b ?c}\n}"),
    "字符串内\\u0027": "SELECT * WHERE { BIND('" + _E + "u0027' AS ?z) SERVICE " + EP + " {?a ?b ?c} } #'\n",
    # 位置与形式
    "SILENT": "SELECT * WHERE { SERVICE SILENT " + EP + " { ?a ?b ?c } }",
    "FILTER EXISTS里": "SELECT * WHERE { BIND(1 AS ?x) FILTER EXISTS { SERVICE " + EP + " { ?a ?b ?c } } }",
    "子查询里": "SELECT * WHERE { { SELECT * WHERE { SERVICE " + EP + " { ?a ?b ?c } } } }",
    "ASK": "ASK { SERVICE " + EP + " { ?a ?b ?c } }",
    "CONSTRUCT": "CONSTRUCT { ?a ?b ?c } WHERE { SERVICE " + EP + " { ?a ?b ?c } }",
    "制表符与换行": "SELECT * WHERE {\tSERVICE\n\t" + EP + "\t{ ?a ?b ?c } }",
}


def _q(name, port):
    return BYPASS[name].replace("{port}", str(port))


@pytest.mark.parametrize("name", sorted(BYPASS))
def test_bypass_really_connects_in_process(name):
    """前提：不经 model_query、直接交给进程内的 pyoxigraph 时，这些写法确实外连（否则下一条证明不了什么）。"""
    import pyoxigraph as ox
    with listener() as (port, hits):
        try:
            list(ox.Store().query(_q(name, port)))
        except Exception:  # noqa: BLE001 — 只看有没有连接
            pass
    assert hits, f"{name}：pyoxigraph 没有外连"


@pytest.mark.parametrize("classifier", ["on", "off"])
@pytest.mark.parametrize("name", sorted(BYPASS))
def test_bypass_makes_no_connection_through_model_query(repo, monkeypatch, name, classifier):
    """off：关掉只管错误码的词法判定，证明零连接不依赖它（查询进到无网络子进程，联网时被终止）。"""
    if classifier == "off":
        monkeypatch.setattr(T, "_SERVICE_CLAUSE_RE", re.compile(r"(?!)"))
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), _q(name, port))
    assert not hits, f"{name}：model_query 发出了 {len(hits)} 次连接"
    assert ei.value.code == "QUERY_NOT_READONLY", ei.value.to_dict()


@pytest.mark.parametrize("name", sorted(REAL_SERVICE))
def test_t1_guard_samples_make_no_connection_without_classifier(repo, monkeypatch, name):
    """T1 护栏里的 SERVICE 样例，关掉词法判定后仍零连接（没被执行到的 SERVICE 照常返回或报 QUERY_FAILED）。"""
    monkeypatch.setattr(T, "_SERVICE_CLAUSE_RE", re.compile(r"(?!)"))
    with listener() as (port, hits):
        try:
            T.model_query(cfg(repo), REAL_SERVICE[name].replace("{port}", str(port)))
        except AisepError as e:
            assert e.code in ("QUERY_NOT_READONLY", "QUERY_FAILED"), e.to_dict()
    assert not hits


# 不靠 pyoxigraph：施加同一个限制后，子进程自己用各种 socket 去连；进程必须被终止、零连接
_PROBES = {
    "tcp": "s = socket.socket(); s.connect(('127.0.0.1', PORT))",
    "udp": "socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('127.0.0.1', PORT))",
    "ipv6": "socket.socket(socket.AF_INET6).connect(('::1', PORT))",
    "unix": "socket.socket(socket.AF_UNIX).connect(UPATH)",
    "dns": "socket.getaddrinfo('localhost', PORT)",
}


@contextlib.contextmanager
def unix_listener():
    d = tempfile.mkdtemp(dir="/tmp")  # macOS 上 unix socket 路径限长 104，tmp_path 太长
    path = os.path.join(d, "s")
    s = socket.socket(socket.AF_UNIX)
    s.bind(path)
    s.listen(8)
    s.settimeout(0.1)
    hits, stop = [], threading.Event()

    def loop():
        while not stop.is_set():
            try:
                c, _ = s.accept()
            except OSError:
                continue
            hits.append(1)
            c.close()
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    try:
        yield path, hits
    finally:
        stop.set()
        th.join(2)
        s.close()
        shutil.rmtree(d)


def _confined_python(body, port, **kw):
    code = textwrap.dedent(f"""
        import importlib.util, socket, sys
        spec = importlib.util.spec_from_file_location("qb", {querybox.__file__!r})
        qb = importlib.util.module_from_spec(spec); spec.loader.exec_module(qb)
        getattr(qb, "_confine_" + sys.platform)()
        print("confined", flush=True)
    """) + body.replace("PORT", str(port)) + "\nprint('survived', flush=True)\n"
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=30, **kw)


@pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="只在 Linux 与 macOS 上有无网络子进程")
@pytest.mark.parametrize("kind", sorted(_PROBES))
def test_confinement_kills_any_socket_use(kind):
    with listener() as (port, hits), unix_listener() as (upath, uhits):
        p = _confined_python(_PROBES[kind].replace("UPATH", repr(upath)), port)
    assert "confined" in p.stdout, p.stderr
    assert "survived" not in p.stdout, f"{kind}：施加限制后仍能使用 socket"
    assert not hits and not uhits
    if kind not in ("dns",) or sys.platform == "linux":  # macOS 的 getaddrinfo 解析 localhost 可不走 socket
        assert p.returncode == -querybox._KILLED_BY[sys.platform], (p.returncode, p.stderr)


@pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="只在 Linux 与 macOS 上有无网络子进程")
def test_confinement_allows_a_plain_query():
    """对照：限制下正常查询照常跑完（证明上一条的终止来自 socket 使用，不是限制本身让进程起不来）。"""
    with listener() as (port, hits):
        p = _confined_python("import pyoxigraph as ox\nprint(bool(ox.Store().query('ASK {}')))", port)
    assert p.returncode == 0 and "survived" in p.stdout, p.stderr
    assert not hits


def test_child_fails_closed_when_confinement_is_unavailable():
    """限制建立不了（这里用未知平台模拟）：子进程不读查询就退出，不执行、不连接。"""
    with listener() as (port, hits):
        code = (f"import runpy, sys; sys.platform = 'sunos'; "
                f"runpy.run_path({querybox.__file__!r}, run_name='__main__')")
        p = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=30,
                           input=b'{"sparql": "SELECT * WHERE { SERVICE <http://127.0.0.1:%d/q> {?a ?b ?c} }", '
                                 b'"prefixes": {}, "limit": 1}\n' % port)
    assert p.returncode == querybox.CONFINE_FAILED, p
    assert not hits


def test_model_query_fails_closed_without_confinement(repo, monkeypatch):
    monkeypatch.setattr(querybox, "_KILLED_BY", {})
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_query(cfg(repo), "ASK {}")
    assert ei.value.code == "INTERNAL" and not hits


def _is_child(args):
    return list(args[:3]) == [sys.executable, "-I", querybox.__file__]


@pytest.mark.parametrize("child", ["import sys; sys.exit(1)", "pass", "import os, signal; os.kill(os.getpid(), 15)"])
def test_parent_does_not_misread_a_crash_as_a_result(repo, monkeypatch, child):
    """子进程异常退出、没有输出时报错，不当成空结果。"""
    real = subprocess.run
    monkeypatch.setattr(querybox.subprocess, "run",  # 同一个 subprocess 模块也给 git 用：只换查询子进程
                        lambda args, **kw: real(args[:2] + ["-c", child] if _is_child(args) else args, **kw))
    with pytest.raises(AisepError) as ei:
        T.model_query(cfg(repo), "ASK {}")
    assert ei.value.code == "QUERY_FAILED"


# model_impact 不执行调用方的 SPARQL，focus 先过 IRI 校验再拼进查询；转义也拼不出 SERVICE
FOCUS = [
    M + "supplier" + _E + "u003E SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } } #",
    M + "supplier> . SERVICE <http://127.0.0.1:{port}/q> { ?a ?b ?c } } #",
    "<http://127.0.0.1:{port}/q> SERVICE",
]


@pytest.mark.parametrize("i", range(len(FOCUS)))
def test_impact_focus_cannot_reach_the_network(repo, i):
    with listener() as (port, hits):
        with pytest.raises(AisepError) as ei:
            T.model_impact(cfg(repo), focus=FOCUS[i].replace("{port}", str(port)))
    assert not hits
    assert ei.value.code == "INVALID_ARGUMENT", ei.value.to_dict()


def test_query_environment_is_minimal(repo, monkeypatch):
    """子进程不继承调用方的环境变量（PYTHON*、代理等），只给 PATH。"""
    seen = {}
    real = subprocess.run

    def spy(args, **kw):
        if _is_child(args):
            seen.update(kw)
        return real(args, **kw)
    monkeypatch.setattr(querybox.subprocess, "run", spy)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    assert T.model_query(cfg(repo), "ASK { ?s ?p ?o }")["value"] is True
    assert seen and set(seen["env"]) <= {"PATH"} and seen["close_fds"] is True
