import unittest

from aiforge.config import GovernanceConfig
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker
from aiforge.orchestration.agents import AgentContext
from aiforge.orchestration.graph import build_default_pipeline
from aiforge.orchestration.state import ArtifactKind, PipelineState, Status
from aiforge.runtime.local import LocalSandbox


def _ctx(config=None):
    audit = AuditTrail(path=None)
    perms = PermissionBroker(audit=audit)
    rt = LocalSandbox(perms, config=config) if config else LocalSandbox(perms)
    kwargs = {"runtime": rt, "permissions": perms, "audit": audit}
    if config:
        kwargs["config"] = config
    return AgentContext(**kwargs), audit


class TestPipeline(unittest.TestCase):
    def test_feature_runs_to_done(self):
        ctx, _ = _ctx()
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="X1", request="加个端点", task_type="feature")
        state = sup.invoke(state)
        self.assertEqual(state.status, Status.DONE)
        kinds = {a.kind for a in state.artifacts}
        # 端到端产出规格驱动全链 artifact
        for k in (ArtifactKind.SPEC, ArtifactKind.PLAN, ArtifactKind.TASKS,
                  ArtifactKind.CODE, ArtifactKind.REVIEW, ArtifactKind.TEST):
            self.assertIn(k, kinds)

    def test_high_risk_triggers_hitl_then_resume(self):
        ctx, _ = _ctx()
        sup = build_default_pipeline(ctx)
        state = PipelineState(feature_id="M1", request="加索引并迁移", task_type="migration")
        state = sup.invoke(state)
        self.assertEqual(state.status, Status.NEEDS_HUMAN)
        self.assertIsNotNone(state.needs_human_reason)
        # 人审通过后恢复，继续到 tester 完成
        resumed = sup.resume("M1", approve=True)
        self.assertEqual(resumed.status, Status.DONE)
        self.assertIn(ArtifactKind.TEST, {a.kind for a in resumed.artifacts})

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
