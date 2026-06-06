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

    def test_judge_conservative_and_content_aware(self):
        """修 C2 后：无可信 LLM 一律转人审；危险内容即便 feature 也不自动放行；高风险类型转人审。"""
        from aiforge.llm import StubReviewerLLM
        # 无可信 LLM(MockLLM) → 保守转人审，连干净变更也不自动放行
        self.assertFalse(AgentAsJudge().review("加个工具函数", task_type="feature").approved)
        # 可信评审 + 干净 + 非高风险 → 自动通过
        self.assertTrue(AgentAsJudge(llm=StubReviewerLLM()).review("加个纯函数", task_type="feature").approved)
        # 危险内容(SQL 注入)即便 task_type=feature 也不自动通过（静态扫描升级人审）
        danger = 'q = f"SELECT * FROM u WHERE n={x}"'
        self.assertFalse(AgentAsJudge(llm=StubReviewerLLM()).review(danger, task_type="feature").approved)
        # 高风险类型 → 转人审
        self.assertFalse(AgentAsJudge(llm=StubReviewerLLM()).review("改支付", task_type="payment").approved)


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
