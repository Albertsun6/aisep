"""本地沙箱 runtime：把变更写入一个隔离工作目录（默认临时目录），命令在该目录内执行。

用于离线 demo / 测试。生产应换成 OpenHands 自托管或 Devin/Ona（见 openhands.py 与 deploy/）。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import List, Optional

from aiforge.config import DEFAULT_GOVERNANCE, GovernanceConfig
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.orchestration.state import FileChange
from aiforge.runtime.base import ExecResult, Runtime


class LocalSandbox(Runtime):
    name = "local-sandbox"

    def __init__(
        self,
        permissions: PermissionBroker,
        config: GovernanceConfig = DEFAULT_GOVERNANCE,
        audit: Optional[AuditTrail] = None,
        workdir: Optional[str] = None,
    ) -> None:
        super().__init__(permissions, config, audit)
        self.workdir = workdir or tempfile.mkdtemp(prefix="aiforge-sandbox-")

    def _apply_impl(self, changes: List[FileChange], contents: dict) -> ExecResult:
        written = []
        for change in changes:
            abspath = os.path.join(self.workdir, change.path)
            os.makedirs(os.path.dirname(abspath) or self.workdir, exist_ok=True)
            with open(abspath, "w", encoding="utf-8") as f:
                f.write(contents.get(change.path, ""))
            written.append(change)
        return ExecResult(ok=True, stdout=f"wrote {len(written)} files", changes=written)

    def run(self, actor: str, command: str) -> ExecResult:
        self.permissions.check(actor, "exec")
        if self.audit is not None:
            self.audit.record(actor, "tool_call", "run", command=command)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            ok = proc.returncode == 0
            if not ok:
                self._note_failure()
            return ExecResult(ok=ok, stdout=proc.stdout, stderr=proc.stderr)
        except subprocess.TimeoutExpired:
            self._note_failure()
            return ExecResult(ok=False, stderr="timeout")
