import unittest

from aiforge.config import GovernanceConfig
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.llm import StubCodeLLM
from aiforge.orchestration.agents import AgentContext
from aiforge.orchestration.codegen import select_isolated_or_none
from aiforge.orchestration.graph import build_default_pipeline
from aiforge.orchestration.state import ArtifactKind, PipelineState, Status
from aiforge.runtime.local import LocalSandbox

# spec: specs/ci-isolation-contract — verifier 在无真隔离后端时 fail-closed 为 BLOCKED
# (C4/P4)。真隔离仅 macOS sandbox-exec;Linux CI 无后端 → 走 fail-closed 契约。
_ISOLATION = select_isolated_or_none() is not None


def _ctx(config=None):
    audit = AuditTrail(path=None)
    perms = PermissionBroker(audit=audit)
    rt = LocalSandbox(perms, config=config) if config else LocalSandbox(perms)
    # StubCodeLLM：产出真代码/真测试，使流水线端到端跑通真验证（MockLLM 会安全停机）
    kwargs = {"runtime": rt, "permissions": perms, "audit": audit, "llm": StubCodeLLM()}
    if config:
        kwargs["config"] = config
    return AgentContext(**kwargs), audit


class TestPipeline(unittest.TestCase):
    def test_feature_runs_to_done(self):
        ctx, _ = _ctx()
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="X1", request="加个端点", task_type="feature")
        state = sup.invoke(state)
        kinds = {a.kind for a in state.artifacts}
        if _ISOLATION:
            # 有真隔离:端到端到 DONE,产出规格驱动全链 artifact
            self.assertEqual(state.status, Status.DONE)
            for k in (ArtifactKind.SPEC, ArtifactKind.PLAN, ArtifactKind.TASKS,
                      ArtifactKind.CODE, ArtifactKind.REVIEW, ArtifactKind.TEST):
                self.assertIn(k, kinds)
        else:
            # 无真隔离:verifier C4 fail-closed → BLOCKED(契约,不是缺陷);仍产出到 TEST
            self.assertEqual(state.status, Status.BLOCKED)
            self.assertEqual((state.verification or {}).get("reason"), "no-isolation")
            for k in (ArtifactKind.SPEC, ArtifactKind.CODE, ArtifactKind.TEST):
                self.assertIn(k, kinds)

    def test_high_risk_triggers_hitl_then_resume(self):
        ctx, _ = _ctx()
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="M1", request="加索引并迁移", task_type="migration")
        state = sup.invoke(state)
        self.assertEqual(state.status, Status.NEEDS_HUMAN)
        self.assertIsNotNone(state.needs_human_reason)
        # 人审通过后恢复;有隔离 → DONE,无隔离 → verifier fail-closed BLOCKED(C4)
        resumed = sup.resume("M1", approve=True)
        self.assertIn(ArtifactKind.TEST, {a.kind for a in resumed.artifacts})
        if _ISOLATION:
            self.assertEqual(resumed.status, Status.DONE)
        else:
            self.assertEqual(resumed.status, Status.BLOCKED)
            self.assertEqual((resumed.verification or {}).get("reason"), "no-isolation")

    def test_checkpoint_history_recorded(self):
        ctx, _ = _ctx()
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="H1", request="x", task_type="feature")
        sup.invoke(state)
        self.assertGreaterEqual(len(sup.checkpointer.history("H1")), 6)

    def test_blast_radius_safe_halt(self):
        tiny = GovernanceConfig(max_lines_per_change=1, max_files_per_change=1)
        ctx, audit = _ctx(config=tiny)
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="BR1", request="写很多行", task_type="feature")
        state = sup.invoke(state)
        self.assertEqual(state.status, Status.HALTED)
        self.assertTrue(any(e.action == "halt" for e in audit.events))


if __name__ == "__main__":
    unittest.main()
