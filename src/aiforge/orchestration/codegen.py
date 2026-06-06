"""代码抽取 + 真验证回路（修 C1，配合 C4 隔离）。

- extract_code：从 LLM 输出抽取**成为代码**（不是注释），取最后一个满足契约的代码块。
- run_generated：把生成的代码+测试在**隔离 runtime**(C4)里真跑 unittest，tests_ok 来自真实运行
  （不再 assert True、不再数据集手喂，缓解 C3）；变异校验反作弊；默认拒绝在无隔离下执行不可信代码。
"""
from __future__ import annotations

import ast
import json
import re
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

_FENCE = re.compile(r"(?:```|~~~)[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)(?:```|~~~)", re.S | re.I)
FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "shutil", "sys", "pathlib", "ctypes",
                     "multiprocessing", "importlib", "urllib", "http", "requests", "ftplib",
                     "smtplib", "pickle", "marshal", "builtins"}


def _parses(src: str) -> bool:
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def defines_solution(src: str) -> bool:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == "solution"
               for n in ast.walk(tree))


def is_test_module(src: str) -> bool:
    if "solution" not in src:
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    has_case = any(isinstance(n, ast.ClassDef) and any(
        (isinstance(b, ast.Attribute) and b.attr == "TestCase") or (isinstance(b, ast.Name) and b.id == "TestCase")
        for b in n.bases) for n in ast.walk(tree))
    has_testfn = any(isinstance(n, ast.FunctionDef) and n.name.startswith("test") for n in ast.walk(tree))
    return has_case or has_testfn


def extract_code(llm_text: str, contract: Callable[[str], bool]) -> str:
    if not llm_text:
        return ""
    blocks = [b.strip() for b in _FENCE.findall(llm_text)]
    good = [b for b in blocks if _parses(b) and contract(b)]
    if good:
        return good[-1]
    whole = llm_text.strip()
    if not blocks and _parses(whole) and contract(whole):
        return whole
    return ""


def scan_forbidden(src: str) -> List[str]:
    hits: set = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    hits.add(a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in FORBIDDEN_IMPORTS:
            hits.add(n.module.split(".")[0])
    return sorted(hits)


@dataclass
class VerifyResult:
    tests_ok: bool
    output: str
    halted: bool = False
    reason: str = ""
    tests_run: int = 0


_RUNNER = (
    "import json, unittest\n"
    "r = unittest.TestResult()\n"
    "try:\n"
    "    s = unittest.TestLoader().loadTestsFromName('test_solution')\n"
    "    s.run(r)\n"
    "    out = {'testsRun': r.testsRun, 'failures': len(r.failures), 'errors': len(r.errors), 'skipped': len(r.skipped)}\n"
    "except BaseException as e:\n"
    "    out = {'testsRun': 0, 'failures': 0, 'errors': 1, 'skipped': 0}\n"
    "print('RUNNER_JSON:' + json.dumps(out))\n"
)
_MUTANT = "def solution(*a, **k):\n    return None\n"


def _run_once(code_src: str, test_src: str, timeout: float, runner) -> Tuple[bool, int, int, str]:
    with tempfile.TemporaryDirectory(prefix="aiforge-verify-") as d:
        import os
        for name, src in (("solution.py", code_src), ("test_solution.py", test_src), ("_runner.py", _RUNNER)):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(src)
        res = runner(d, timeout)
        if getattr(res, "timed_out", False):
            return False, 0, 0, "TIMEOUT"
        out = (res.stdout or "") + (res.stderr or "")
        line = next((l for l in out.splitlines() if l.startswith("RUNNER_JSON:")), None)
        if not line:
            return False, 0, 0, out[-300:]
        j = json.loads(line[len("RUNNER_JSON:"):])
        meaningful = j["testsRun"] - j["skipped"]
        return (meaningful >= 1 and j["failures"] == 0 and j["errors"] == 0), j["testsRun"], meaningful, out[-300:]


def run_generated(code_src: str, test_src: str, isolated_runtime=None,
                  allow_unsafe: bool = False, timeout: float = 15.0) -> VerifyResult:
    """真验证回路。默认要求隔离 runtime(C4)；allow_unsafe 仅离线自测且仍受 forbidden-import 拦截。"""
    if isolated_runtime is not None:
        if not getattr(isolated_runtime, "untrusted_safe", False):
            return VerifyResult(False, "", halted=True, reason="传入 runtime 非 untrusted_safe，拒绝")
        sandbox = isolated_runtime
    elif allow_unsafe:
        forb = scan_forbidden(code_src) + scan_forbidden(test_src)
        if forb:
            return VerifyResult(False, "", halted=True, reason=f"无隔离下含高危 import {sorted(set(forb))}，拒绝")
        from aiforge.runtime.isolation import NoIsolationSandbox
        sandbox = NoIsolationSandbox()
    else:
        return VerifyResult(False, "", halted=True,
                            reason="拒绝在无隔离 runtime 下执行 LLM 生成代码（C4）。传入隔离 runtime 或 allow_unsafe。")
    runner = lambda d, t: sandbox.run_python(d, ["_runner.py"], t)
    ok_real, run_real, meaningful_real, out_real = _run_once(code_src, test_src, timeout, runner)
    if run_real == 0 or meaningful_real == 0:
        return VerifyResult(False, out_real, reason="测试 0 用例/全 skip，判无效")
    if not ok_real:
        return VerifyResult(False, out_real, reason="测试未通过", tests_run=run_real)
    ok_mut, _, _, out_mut = _run_once(_MUTANT, test_src, timeout, runner)
    if ok_mut:
        return VerifyResult(False, out_mut, reason="变异校验失败：测试对错误实现仍通过=空测试", tests_run=run_real)
    return VerifyResult(True, out_real, tests_run=run_real)


def select_isolated_or_none():
    """优先真隔离(C4)；不可用则返回 None（调用方据此 fail-closed 或降级自测）。"""
    try:
        from aiforge.runtime.isolation import select_sandbox
        return select_sandbox(require_untrusted_safe=True, prefer_container=False)
    except Exception:
        return None
