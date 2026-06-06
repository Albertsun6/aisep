import unittest

from aiforge.config import DEFAULT_GOVERNANCE
from aiforge.governance.audit import AuditTrail
from aiforge.governance.permissions import PermissionBroker, PermissionError_
from aiforge.governance.review import review_after_session
from aiforge.orchestration.state import FileChange


class TestPermissions(unittest.TestCase):
    def test_least_privilege_default_deny(self):
        perms = PermissionBroker()
        self.assertTrue(perms.has("read"))
        with self.assertRaises(PermissionError_):
            perms.check("dev", "write")

    def test_grant_records_audit_and_marks_sensitive(self):
        audit = AuditTrail(path=None)
        perms = PermissionBroker(audit=audit)
        ok = perms.grant("dev", "write", reason="impl")
        self.assertTrue(ok)
        auto = perms.grant("dev", "delete", reason="cleanup")
        self.assertFalse(auto)  # 敏感能力不自动通过
        self.assertEqual(len(audit.filter(action="grant")), 2)


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
