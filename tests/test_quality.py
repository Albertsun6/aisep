import unittest

from aiforge.llm import StubReviewerLLM
from aiforge.orchestration.state import Artifact, ArtifactKind, PipelineState, Status
from aiforge.quality.gates import CICDGate, SpecGate, build_default_gates
from aiforge.quality.judge import AgentAsJudge
from aiforge.quality.metrics import TaskOutcome, compute_metrics

_STRUCTURED_SPEC = "User Story: As a user I want X, so that Y. 验收标准 Given a When b Then c."
_FULL_EV = {"lint_ok": True, "coverage": 0.9, "sast_ok": True, "tests_ok": True,
            "build_ok": True, "diff_summary": "def solution():\n    return 42"}


def _trusted_chain():
    # eval/测试需**显式**注入可信评审替身(默认门禁是保守的，不带 stub)
    return build_default_gates(judge=AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True))


class TestGates(unittest.TestCase):
    def _state(self, task_type="feature", with_spec=True, with_code=True,
               status=Status.DONE, verified=True):
        s = PipelineState(feature_id="G", request="r", task_type=task_type)
        s.status = status
        if verified:
            s.verification = {"tests_ok": True, "reason": "", "tests_run": 1}
        if with_spec:
            s.add_artifact(Artifact(ArtifactKind.SPEC, _STRUCTURED_SPEC, "analyst", refs=["G"]))
            s.add_artifact(Artifact(ArtifactKind.PLAN, "plan", "architect", refs=["spec"]))
            s.add_artifact(Artifact(ArtifactKind.TASKS, "tasks", "architect", refs=["plan"]))
        if with_code:
            s.add_artifact(Artifact(ArtifactKind.CODE, "solution.py", "developer", refs=["tasks"]))
            s.add_artifact(Artifact(ArtifactKind.TEST, "test.py", "tester", refs=["code"]))
        return s

    def test_all_gates_pass(self):
        results = _trusted_chain().run(self._state(), dict(_FULL_EV))
        self.assertEqual(len(results), 8)   # status+spec+precommit+pr+trace+completeness+cicd+canary
        self.assertTrue(all(r.passed for r in results), [(r.name, r.reason) for r in results])

    def test_default_pr_is_conservative(self):
        """默认门禁不带 stub 评审 → 干净变更也不自动放行(转人审)。"""
        results = build_default_gates().run(self._state(), dict(_FULL_EV))
        self.assertTrue(any(r.layer == "pr" and not r.passed for r in results))

    def test_non_done_status_blocked_first(self):
        """StatusGate 白名单：非 DONE(HALTED/NEEDS_HUMAN) 在链首被拦。"""
        for st in (Status.HALTED, Status.NEEDS_HUMAN, Status.BLOCKED):
            results = _trusted_chain().run(self._state(status=st), dict(_FULL_EV))
            self.assertEqual(results[0].layer, "status")
            self.assertFalse(results[0].passed)

    def test_missing_verification_blocked(self):
        """CompletenessGate：DONE 但 verifier 从没跑(verification=None) → 拒绝(不再"有才查")。"""
        results = _trusted_chain().run(self._state(verified=False), dict(_FULL_EV))
        self.assertFalse(all(r.passed for r in results))
        self.assertTrue(any(r.layer == "complete" and not r.passed for r in results))

    def test_empty_diff_blocked_at_pr(self):
        """PRGate：空 diff_summary 不得绕过(judge 不审空内容)。"""
        ev = dict(_FULL_EV); ev["diff_summary"] = "   "
        results = _trusted_chain().run(self._state(), ev)
        self.assertTrue(any(r.layer == "pr" and not r.passed for r in results))

    def test_no_spec_blocked_at_spec(self):
        results = _trusted_chain().run(self._state(with_spec=False), dict(_FULL_EV))
        self.assertTrue(any(r.layer == "spec" and not r.passed for r in results))

    def test_fails_closed_empty_evidence(self):
        results = _trusted_chain().run(self._state(), {"diff_summary": "x"})
        self.assertFalse(all(r.passed for r in results))

    def test_low_coverage_blocks_at_pr(self):
        state = self._state()
        results = _trusted_chain().run(state, {"lint_ok": True, "coverage": 0.5, "sast_ok": True,
                                               "diff_summary": "x"})
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
        # 显式可信评审 + 干净 + 非高风险 → 自动通过
        self.assertTrue(AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True).review("加个纯函数", task_type="feature").approved)
        # 危险内容(SQL 注入)即便 task_type=feature 也不自动通过（静态扫描升级人审）
        danger = 'q = f"SELECT * FROM u WHERE n={x}"'
        self.assertFalse(AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True).review(danger, task_type="feature").approved)
        # 高风险类型 → 转人审
        self.assertFalse(AgentAsJudge(llm=StubReviewerLLM(), trust_llm=True).review("改支付", task_type="payment").approved)

    def test_judge_trust_requires_explicit_opt_in(self):
        """回归(STEP 0 v2 首批③):挂真 LLM 不自动可信——默认 trust_llm=False,绝不静默放行。

        原地雷(judge.py:81):trust_llm = not isinstance(llm, MockLLM) → 接通真模型即 trusted,
        重开自称修掉的 C2。本测试钉死翻转后的语义,改回去即红。
        """
        from aiforge.llm import StubReviewerLLM
        # 非 MockLLM 但未显式 opt-in → 不可信 → 干净变更也转人审而非自动通过
        verdict = AgentAsJudge(llm=StubReviewerLLM()).review("加个纯函数", task_type="feature")
        self.assertFalse(verdict.approved)
        self.assertTrue(verdict.requires_human)
        # MockLLM 即便显式 trust_llm=True 也不信(fail-closed,只会更保守)
        verdict = AgentAsJudge(trust_llm=True).review("加个纯函数", task_type="feature")
        self.assertFalse(verdict.approved)
        self.assertTrue(verdict.requires_human)


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
