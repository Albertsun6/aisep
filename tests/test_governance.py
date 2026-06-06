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
        self.assertTrue(perms.has("read"))
        with self.assertRaises(PermissionError_):
            perms.check("dev", "write")

    def test_sensitive_not_self_granted(self):
        """修 C5：敏感能力 grant() 默认拒绝且**不授予**（原版 bug 会授予）。"""
        audit = AuditTrail(path=None)
        perms = PermissionBroker(audit=audit)
        self.assertTrue(perms.grant("dev", "write", reason="impl"))
        self.assertFalse(perms.grant("dev", "delete", reason="cleanup"))
        self.assertFalse(perms.has("delete"))           # 关键：未被授予
        self.assertEqual(len(audit.filter(action="grant")), 1)          # 只有 write 真授予
        self.assertEqual(len(audit.filter(action="grant_denied")), 1)   # delete 被拒并记审计

    def test_sensitive_requires_signed_human_ticket(self):
        auth = ApprovalAuthority()
        perms = auth.broker()
        self.assertFalse(perms.grant("dev", "delete", reason="x"))      # agent 自授被拒
        perms.approve(auth.issue("delete"))                              # 人审签发 ticket → 授予
        self.assertTrue(perms.has("delete"))
        # 伪造票被验签拒绝；同票重放被拒
        with self.assertRaises(PermissionError_):
            PermissionBroker().approve(HumanApprovalTicket("delete", "n", 9e9, "bad"))
        t = auth.issue("infra")
        perms.approve(t)
        with self.assertRaises(PermissionError_):
            perms.approve(t)                                             # 防重放


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
