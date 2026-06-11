"""执行 runtime：隔离沙箱中应用变更 / 跑命令，强制经权限与 blast-radius 检查。

- ``LocalSandbox`` = 无隔离（仅可信代码）。执行**不可信**(LLM 生成)代码必须用 ``isolation``：
  ``select_sandbox()`` 选出**自检通过**的真隔离后端，否则 fail-closed 拒绝（修 C4）。
"""

from aiforge.runtime.base import ExecResult, Runtime, SafeHaltError
from aiforge.runtime.isolation import (
    ContainerSandbox,
    MacSandboxExec,
    NoIsolationSandbox,
    Sandbox,
    run_untrusted_python,
    select_sandbox,
)
from aiforge.runtime.local import LocalSandbox

__all__ = [
    "Runtime", "ExecResult", "SafeHaltError", "LocalSandbox",
    "Sandbox", "NoIsolationSandbox", "MacSandboxExec", "ContainerSandbox",
    "select_sandbox", "run_untrusted_python",
]
