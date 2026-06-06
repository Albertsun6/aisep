"""P0-4 / C4 修复提案 v2（非侵入）——经 cursor-agent 异构评审后重写（评审总判：v1=部分）。

修缺陷 C4：原 LocalSandbox=tempfile+subprocess.run(shell=True)，无隔离。

## v2 相对 v1 的关键修正（采纳评审，见 评审与辩论记录-C4.md）
v1 致命问题：profile 只拦网络+写 home，**不拦读** → 不可信代码可读 ~/.ssh 经 stdout 外泄；
还能写 /tmp 持久化；超时只杀直接子进程；untrusted_safe 只是个硬编码属性（自称安全）。

v2：
  1. **untrusted_safe = 能力自检验证的属性**（不是声称）：后端必须用探针**证明**拦住
     {读 home / 写 home / 写 /tmp / 网络}，全过才算 untrusted_safe=True。证不出 → False → fail-closed。
  2. **更紧 profile**（实测）：deny network + deny **read** home/Users + deny write home/Users//tmp，
     只允许写 workdir → 实测拦住读 home 外泄 + /tmp 持久化，且 python 仍能跑。
  3. **杀进程组**：Popen(start_new_session) + 超时 os.killpg(SIGKILL)，fork 出的子孙也清理。
  4. profile 写文件 + workdir realpath 校验 + 拒绝特殊字符（防 profile 注入）。
  5. RLIMIT_CPU/FSIZE/NPROC/AS（AS 在 macOS 可能无效，诚实标注：真内存限额靠容器 --memory）。
  6. ContainerSandbox 修挂载（-v ro + --tmpfs /tmp）；标 experimental（本环境无 docker，未实跑）。

## 诚实边界
- sandbox-exec 已 deprecated；`allow default` 仍保留 Mach/IPC 面，**不等同容器/microVM**。
- v2 的"安全"= 自检探针通过（拦读/写 home、写 /tmp、网络）；不是形式化沙箱证明。生产首选容器/microVM。
- 仍可读 /etc、/usr 等系统文件（非 home 秘密）；威胁模型聚焦"AI 生成代码外泄用户秘密/持久化/联网/耗资源"。
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Sequence

# 复用 runtime 包既有的 SafeHaltError（避免两个同名异类）
from aiforge.runtime.base import SafeHaltError

NONE, OS_SANDBOX, CONTAINER = "none", "os_sandbox", "container"
_BAD = set('"\\\n\r\t()')


@dataclass
class ExecResult:
    ok: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


def _scrubbed_env(workdir: str) -> dict:
    keep = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
    keep["HOME"] = workdir
    keep["PYTHONDONTWRITEBYTECODE"] = "1"
    return keep


def _rlimits():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024,) * 2)
        for lim in ("RLIMIT_NPROC", "RLIMIT_AS"):
            try:
                resource.setrlimit(getattr(resource, lim), (256 * 1024 * 1024 if lim == "RLIMIT_AS" else 64,) * 2)
            except (ValueError, OSError, AttributeError):
                pass  # macOS 对 RLIMIT_AS 常无效——真内存限额靠容器
    except Exception:
        pass


def _popen_run(argv: Sequence[str], cwd: str, timeout: float, env: dict) -> ExecResult:
    """新会话启动 + 超时杀**整个进程组**（清理 fork 出的子孙）。"""
    p = subprocess.Popen(list(argv), cwd=cwd, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True,
                         preexec_fn=_rlimits)
    try:
        out, err = p.communicate(timeout=timeout)
        return ExecResult(p.returncode == 0, p.returncode, out, err)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            p.communicate(timeout=2)
        except Exception:
            pass
        return ExecResult(False, -1, timed_out=True)


# 自检探针：在沙箱内尝试读/写 home、写 /tmp、联网；真隔离应全部 BLOCKED
def _selftest_probe(real_home: str) -> str:
    return (
        "import os, socket\n"
        "print('PY_RUNS')\n"
        "def chk(t, fn):\n"
        "    try:\n        fn(); print(t + '_OK')\n"
        "    except Exception:\n        print(t + '_BLOCKED')\n"
        f"chk('READ_HOME', lambda: os.listdir({real_home!r}))\n"
        f"chk('WRITE_HOME', lambda: open({real_home!r} + '/.aiforge_probe', 'w'))\n"
        "chk('WRITE_TMP', lambda: open('/tmp/.aiforge_probe', 'w'))\n"
        "chk('NET', lambda: socket.create_connection(('1.1.1.1', 80), 2).close())\n"
    )

_REQUIRED_BLOCKS = ("READ_HOME_BLOCKED", "WRITE_HOME_BLOCKED", "WRITE_TMP_BLOCKED", "NET_BLOCKED")


class Sandbox:
    level = NONE
    name = "abstract"

    def run_python(self, workdir: str, args: Sequence[str], timeout: float = 15.0) -> ExecResult:
        raise NotImplementedError

    def _can_run(self) -> bool:
        return True

    def verify_isolation(self) -> bool:
        """**用探针证明**隔离生效；只有全部 BLOCKED 才返回 True（带缓存）。"""
        cached = getattr(self, "_verified", None)
        if cached is not None:
            return cached
        ok = False
        if self._can_run():
            try:
                with tempfile.TemporaryDirectory(prefix="iso-selftest-") as d:
                    with open(os.path.join(d, "p.py"), "w") as f:
                        f.write(_selftest_probe(os.path.expanduser("~")))
                    out = self.run_python(d, ["p.py"], timeout=10).stdout or ""
                ok = ("PY_RUNS" in out) and all(b in out for b in _REQUIRED_BLOCKS)
            except Exception:
                ok = False
        self._verified = ok
        return ok

    @property
    def untrusted_safe(self) -> bool:
        return self.verify_isolation()


class NoIsolationSandbox(Sandbox):
    """等价原 LocalSandbox：无隔离。仅可信代码用；verify 恒 False。"""
    level = NONE
    name = "no-isolation"

    def run_python(self, workdir, args, timeout=15.0):
        return _popen_run([sys.executable, *args], workdir, timeout, dict(os.environ))

    def verify_isolation(self) -> bool:
        return False


def _safe_subpath(path: str) -> str:
    rp = os.path.realpath(path)
    if any(c in _BAD for c in rp):
        raise SafeHaltError(f"路径含不安全字符，拒绝构造 profile: {rp!r}")
    return rp


class MacSandboxExec(Sandbox):
    """macOS sandbox-exec：deny 网络 + 读/写 home/Users + 写 /tmp，只允许写 workdir。"""
    level = OS_SANDBOX
    name = "macos-sandbox-exec"

    @staticmethod
    def available() -> bool:
        return sys.platform == "darwin" and shutil.which("sandbox-exec") is not None

    def _can_run(self):
        return self.available()

    def _profile(self, workdir: str) -> str:
        home = _safe_subpath(os.path.expanduser("~"))
        wd = _safe_subpath(workdir)
        return (
            "(version 1)\n(allow default)\n(deny network*)\n"
            f'(deny file-read* (subpath "{home}") (subpath "/Users"))\n'
            f'(deny file-write* (subpath "{home}") (subpath "/Users") (subpath "/tmp") (subpath "/private/tmp"))\n'
            f'(allow file-write* (subpath "{wd}"))\n'
        )

    def run_python(self, workdir, args, timeout=15.0):
        prof = tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False, dir=tempfile.gettempdir())
        try:
            prof.write(self._profile(workdir))
            prof.close()
            argv = ["sandbox-exec", "-f", prof.name, sys.executable, *args]
            return _popen_run(argv, workdir, timeout, _scrubbed_env(workdir))
        finally:
            try:
                os.unlink(prof.name)
            except Exception:
                pass


class ContainerSandbox(Sandbox):
    """docker/podman（生产首选）。**experimental**：本环境无可达 daemon，未实跑。"""
    level = CONTAINER
    name = "container"

    def __init__(self, engine="docker", image="python:3.12-slim"):
        self.engine, self.image = engine, image

    @staticmethod
    def available(engine="docker") -> bool:
        if not shutil.which(engine):
            return False
        try:
            return subprocess.run([engine, "info"], capture_output=True, timeout=5).returncode == 0
        except Exception:
            return False

    def _can_run(self):
        return self.available(self.engine)

    def run_python(self, workdir, args, timeout=15.0):
        wd = _safe_subpath(workdir)
        argv = [self.engine, "run", "--rm", "--network", "none",
                "--memory", "256m", "--pids-limit", "128", "--cpus", "1",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{wd}:/work:ro", "-w", "/work",
                self.image, "python", *args]
        return _popen_run(argv, wd, timeout, dict(os.environ))


def select_sandbox(require_untrusted_safe: bool = True, prefer_container: bool = True,
                   _force: Optional[List[str]] = None) -> Sandbox:
    """选最强可用且**自检通过**的隔离。fail-closed：要求不可信安全但无 verify 通过的后端 → SafeHalt。"""
    allowed = set(_force) if _force is not None else {CONTAINER, OS_SANDBOX, NONE}
    candidates = []
    if prefer_container and CONTAINER in allowed:
        candidates.append(ContainerSandbox())
    if OS_SANDBOX in allowed:
        candidates.append(MacSandboxExec())
    for c in candidates:
        if c.verify_isolation():            # 只接受探针证明了隔离的后端
            return c
    if require_untrusted_safe:
        raise SafeHaltError(
            "无可用且自检通过的真隔离后端，按 C4 拒绝执行不可信代码（绝不降级到无隔离）。")
    if NONE in allowed:
        return NoIsolationSandbox()
    raise SafeHaltError("无任何可用执行后端")


def run_untrusted_python(sandbox: Sandbox, workdir: str, args: Sequence[str], timeout: float = 15.0) -> ExecResult:
    """执行不可信代码的**单一入口**：只接受自检通过的后端，否则拒绝。"""
    if not sandbox.verify_isolation():
        raise SafeHaltError(f"后端 {sandbox.name} 未通过隔离自检，拒绝执行不可信代码")
    return sandbox.run_python(workdir, args, timeout)
