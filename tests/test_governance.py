import unittest

from aiforge.config import DEFAULT_GOVERNANCE
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import (
    ApprovalAuthority, HumanApprovalTicket, PermissionBroker, PermissionError_,
)
from aiforge.governance.review import review_after_session
from aiforge.orchestration.state import FileChange


class TestPermissions(unittest.TestCase):
    def test_least_privilege_default_deny(self):
        perms = PermissionBroker()
        self.assertTrue(perms.has("dev", "read"))        # 每个 actor 默认有 read
        with self.assertRaises(PermissionError_):
            perms.check("dev", "write")

    def test_sensitive_not_self_granted(self):
        """修 C5：敏感能力 grant() 默认拒绝且**不授予**（原版 bug 会授予）。"""
        audit = AuditTrail(path=None)
        perms = PermissionBroker(audit=audit)
        self.assertTrue(perms.grant("dev", "write", reason="impl"))
        self.assertFalse(perms.grant("dev", "delete", reason="cleanup"))
        self.assertFalse(perms.has("dev", "delete"))           # 关键：未被授予
        self.assertEqual(len(audit.filter(action="grant")), 1)          # 只有 write 真授予
        self.assertEqual(len(audit.filter(action="grant_denied")), 1)   # delete 被拒并记审计

    def test_sensitive_requires_signed_human_ticket(self):
        auth = ApprovalAuthority()
        perms = auth.broker()
        self.assertFalse(perms.grant("dev", "delete", reason="x"))      # agent 自授被拒
        perms.approve(auth.issue("dev", "delete"))                      # 人审签发 ticket → 授予
        self.assertTrue(perms.has("dev", "delete"))
        # 伪造票被验签拒绝
        with self.assertRaises(PermissionError_):
            PermissionBroker().approve(HumanApprovalTicket("dev", "delete", "n", 9e9, "bad"))
        # 防重放
        t = auth.issue("dev", "infra")
        perms.approve(t)
        with self.assertRaises(PermissionError_):
            perms.approve(t)

    def test_per_actor_isolation(self):
        """强化：批准 developer 的 delete，不等于 reviewer 也有（按 actor 隔离）。"""
        auth = ApprovalAuthority()
        perms = auth.broker()
        perms.approve(auth.issue("developer", "delete"))
        self.assertTrue(perms.has("developer", "delete"))
        self.assertFalse(perms.has("reviewer", "delete"))
        with self.assertRaises(PermissionError_):
            perms.check("reviewer", "delete")


class TestReview(unittest.TestCase):
    def test_three_file_review(self):
        changes = [
            FileChange("a.py", added_lines=100),
            FileChange("b.py", added_lines=50),
            FileChange("c.py", added_lines=10),
            FileChange("d.py", added_lines=5),
            FileChange("migrations/001.sql", added_lines=2),
        ]
        review = review_after_session(changes, DEFAULT_GOVERNANCE)
        # top-3 diff 必读 + 高风险路径(migration)必读
        self.assertIn("a.py", review.must_review_paths)
        self.assertIn("migrations/001.sql", review.must_review_paths)
        self.assertNotIn("d.py", review.must_review_paths)


class TestBlastRadiusConfig(unittest.TestCase):
    def test_requires_human_review(self):
        cfg = DEFAULT_GOVERNANCE
        self.assertTrue(cfg.requires_human_review("migration", 1, 1))
        self.assertTrue(cfg.requires_human_review("feature", 999, 1))
        self.assertFalse(cfg.requires_human_review("feature", 1, 1))


if __name__ == "__main__":
    unittest.main()
