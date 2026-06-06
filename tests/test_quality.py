import unittest

from aiforge.orchestration.state import PipelineState, Status
from aiforge.quality.gates import CICDGate, build_default_gates
from aiforge.quality.judge import AgentAsJudge
from aiforge.quality.metrics import TaskOutcome, compute_metrics


class TestGates(unittest.TestCase):
    def _state(self, task_type="feature"):
        return PipelineState(feature_id="G", request="r", task_type=task_type)

    def test_all_gates_pass(self):
        chain = build_default_gates()
        ev = {"lint_ok": True, "coverage": 0.9, "sast_ok": True, "tests_ok": True, "build_ok": True}
        results = chain.run(self._state(), ev)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.passed for r in results))

    def test_low_coverage_blocks_at_pr(self):
        chain = build_default_gates()
        state = self._state()
        results = chain.run(state, {"lint_ok": True, "coverage": 0.5, "sast_ok": True})
        self.assertFalse(results[-1].passed)
        self.assertEqual(results[-1].layer, "pr")
        self.assertEqual(state.status, Status.BLOCKED)

    def test_cicd_is_non_bypassable(self):
        gate = CICDGate()
        self.assertFalse(gate.bypassable)
        res = gate.check(self._state(), {"tests_ok": False})
        self.assertFalse(res.passed)
        self.assertFalse(res.bypassable)

    def test_judge_blocks_high_risk(self):
        verdict = AgentAsJudge().review("改了支付逻辑", risk_keywords=["payment"])
        self.assertFalse(verdict.approved)
        verdict2 = AgentAsJudge().review("加了个工具函数", risk_keywords=["feature"])
        self.assertTrue(verdict2.approved)
        # 三个对抗 persona 都给了意见
        self.assertGreaterEqual(len(verdict2.findings), 3)


class TestMetrics(unittest.TestCase):
    def test_compute(self):
        outcomes = [
            TaskOutcome.make("a", passed_ci=True, needed_human_edit=False, review_loops=1, files_changed=2),
            TaskOutcome.make("b", passed_ci=False, needed_human_edit=True, introduced_regression=True, review_loops=3, files_changed=5),
        ]
        m = compute_metrics(outcomes)
        self.assertEqual(m.n, 2)
        self.assertEqual(m.task_completion_rate, 0.5)
        self.assertEqual(m.regression_introduction_rate, 0.5)
        self.assertEqual(m.avg_review_loop_count, 2.0)
        self.assertEqual(m.avg_blast_radius_on_failure, 5.0)

    def test_empty(self):
        self.assertEqual(compute_metrics([]).n, 0)


if __name__ == "__main__":
    unittest.main()
