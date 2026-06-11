import os
import unittest

from aiforge.config import GovernanceConfig
from aiforge.eval.harness import run_eval
from aiforge.governance.permissions import PermissionBroker, PermissionError_
from aiforge.orchestration.codegen import select_isolated_or_none
from aiforge.orchestration.state import FileChange
from aiforge.runtime.base import SafeHaltError
from aiforge.runtime.local import LocalSandbox
from aiforge.runtime.openhands import OpenHandsRuntime

# spec: specs/ci-isolation-contract — eval 经 StatusGate(要求 DONE);无真隔离时 verifier
# fail-closed BLOCKED → 全部止于 StatusGate,门禁路由无法被演练。真隔离仅 macOS sandbox-exec。
_ISOLATION = select_isolated_or_none() is not None


class TestEval(unittest.TestCase):
    def test_run_eval_dataset_metrics(self):
        path = os.path.join("eval", "dataset.jsonl")
        report = run_eval(dataset_path=path)
        m = report.metrics
        self.assertEqual(m.n, 8)
        if _ISOLATION:
            # eval = 合成门禁路由自测(StubCode/StubReviewer + 合成 evidence)，非生产能力指标。
            # dataset oracle 权威:F001/F002/F008 过链;F005 覆盖率不足、F007 dataset tests_ok=False
            # (回归信号保留)、B003/M004/F006 高风险转人审。
            self.assertAlmostEqual(m.task_completion_rate, 3 / 8, places=4)
            self.assertAlmostEqual(m.regression_introduction_rate, 1 / 8, places=4)
            self.assertGreater(m.avg_blast_radius_on_failure, 0)
        else:
            # 无真隔离:verifier C4 fail-closed → 全部 BLOCKED,止于 StatusGate(契约,非缺陷)。
            # eval 此时无法演练门禁路由——task_completion 必为 0;回归计数仍来自 dataset 标记。
            self.assertAlmostEqual(m.task_completion_rate, 0.0, places=4)
            self.assertAlmostEqual(m.regression_introduction_rate, 1 / 8, places=4)


class TestLocalRuntime(unittest.TestCase):
    def test_apply_requires_write_permission(self):
        perms = PermissionBroker()
        rt = LocalSandbox(perms)
        with self.assertRaises(PermissionError_):
            rt.apply("dev", [FileChange("x.py", 1)], {"x.py": "y"})

    def test_apply_writes_and_enforces_blast_radius(self):
        perms = PermissionBroker()
        perms.grant("dev", "write", reason="t")
        rt = LocalSandbox(perms)
        res = rt.apply("dev", [FileChange("a/x.py", 3)], {"a/x.py": "print(1)\n"})
        self.assertTrue(res.ok)
        self.assertTrue(os.path.exists(os.path.join(rt.workdir, "a/x.py")))

        tiny = GovernanceConfig(max_files_per_change=1, max_lines_per_change=1)
        rt2 = LocalSandbox(perms, config=tiny)
        with self.assertRaises(SafeHaltError):
            rt2.apply("dev", [FileChange("big.py", 999)], {"big.py": "x"})


class TestOpenHandsAdapter(unittest.TestCase):
    def test_safe_halt_when_unconfigured(self):
        perms = PermissionBroker()
        perms.grant("dev", "write", reason="t")
        rt = OpenHandsRuntime(perms, endpoint=None)
        self.assertFalse(rt.configured)
        with self.assertRaises(SafeHaltError):
            rt.apply("dev", [FileChange("x.py", 1)], {"x.py": "y"})

    def test_parallel_batches_topological(self):
        perms = PermissionBroker()
        rt = OpenHandsRuntime(perms, endpoint="http://x", max_parallel_agents=2)
        deps = {"b": ["a"], "c": ["a"], "d": ["b", "c"]}
        batches = rt.plan_parallel_batches(["a", "b", "c", "d"], deps)
        self.assertEqual(batches[0], ["a"])
        self.assertEqual(set(batches[1]), {"b", "c"})
        self.assertEqual(batches[-1], ["d"])

    def test_cycle_detection(self):
        perms = PermissionBroker()
        rt = OpenHandsRuntime(perms, endpoint="http://x")
        with self.assertRaises(ValueError):
            rt.plan_parallel_batches(["a", "b"], {"a": ["b"], "b": ["a"]})


if __name__ == "__main__":
    unittest.main()
