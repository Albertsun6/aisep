"""spec: specs/feat-launcher-outputs 验收 1-4 — 导出契约/symlink 防穿越/降级/护栏(纯 stdlib)。"""
import json
import tempfile
import unittest
from pathlib import Path

from aiforge import launcher_data as ld

SENTINEL = "SSH-PRIVATE-KEY-SENTINEL-do-not-leak"


class _Repo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.feat = self.root / "specs" / "feat-a"
        (self.feat / "outputs" / "screens").mkdir(parents=True)
        (self.feat / "gates").mkdir(parents=True)
        (self.feat / "spec.md").write_text("# 特性A\n", encoding="utf-8")
        (self.feat / "plan.md").write_text("> refs: spec.md\n", encoding="utf-8")
        (self.feat / "tasks.md").write_text("- T1\n", encoding="utf-8")
        (self.feat / "outputs" / "a.md").write_text("验收记录\n", encoding="utf-8")
        (self.feat / "outputs" / "evil.png").write_bytes(b"\x89PNG\x00binary")
        (self.feat / "outputs" / "role.json").write_text("{}", encoding="utf-8")
        (self.feat / "outputs" / "screens" / "x.png").write_bytes(b"\x89PNG")
        (self.feat / "gates" / "gate-spec.json").write_text(
            '{"decision":"approved","created_at":"2026-06-12","argv":["secret-arg"]}', encoding="utf-8")
        (self.feat / "gates" / "gate-trace.json").write_text(
            '{"decision":"approved","created_at":"2026-06-12"}', encoding="utf-8")
        (self.feat / "gates" / "unknown.json").write_text(
            '{"decision":"evil"}', encoding="utf-8")
        # 必须被排除的邻居们
        (self.root / "specs" / "contracts").mkdir()
        (self.root / "specs" / "contracts" / "01-x.md").write_text("# 契约\n")
        (self.root / "specs" / "_workspace").mkdir()
        (self.root / "specs" / "_workspace" / "spec.md").write_text("# 草稿\n")
        (self.root / "specs" / "templates").mkdir()  # 无顶层 spec.md
        (self.root / "specs" / "templates" / "spec-template.md").write_text("# 模板\n")
        (self.root / "specs" / "README.md").write_text("# 游离文件\n")

    def _payload(self) -> dict:
        dest, n = ld.write_launcher_data(self.root)
        text = dest.read_text(encoding="utf-8").strip()
        prefix = "window.AIFORGE_LAUNCHER = "
        self.assertTrue(text.startswith(prefix))
        body = text[len(prefix):].rstrip(";")
        self.assertNotIn("<", body)  # `<` 全量转义
        return json.loads(body)  # 严格 JSON——任意 JS 注入即红


class TestExportContract(_Repo):
    def test_allowlists_and_enumeration(self):
        spec_path = self.feat / "spec.md"
        before = (spec_path.read_bytes(), spec_path.stat().st_mtime_ns)
        data = self._payload()
        self.assertEqual(set(data), {"generated_at", "features"})  # 顶层 allowlist
        self.assertEqual(set(data["features"]), {"feat-a"})  # 排除规则全中
        f = data["features"]["feat-a"]
        self.assertEqual(set(f), {"spec", "plan", "tasks", "debate", "outputs", "gates"})
        self.assertEqual(set(f["outputs"]), {"a.md"})  # png/json/子目录不入
        self.assertEqual(set(f["gates"]), {"gate-spec", "gate-trace"})  # unknown.json 不入
        self.assertEqual(set(f["gates"]["gate-spec"]), {"decision", "created_at"})  # argv 被滤
        self.assertIsNone(f["debate"])  # 缺失 → null
        self.assertEqual((spec_path.read_bytes(), spec_path.stat().st_mtime_ns), before)  # 只读

    def test_symlink_escape_blocked(self):
        """验收 2(评审反例):软链指向 repo 外 → 哨兵串不得出现在产物。"""
        outside = self.root / "outside-secret.txt"
        outside.write_text(SENTINEL, encoding="utf-8")
        (self.feat / "outputs" / "evil.md").symlink_to(outside)
        dest, _ = ld.write_launcher_data(self.root)
        self.assertNotIn(SENTINEL, dest.read_text(encoding="utf-8"))
        data = self._payload()
        self.assertNotIn("evil.md", data["features"]["feat-a"]["outputs"])

    def test_gates_parent_symlink_blocked(self):
        """验收 2 评审反例(2026-06-12 Med):gates 父目录软链不得让 A 串读 B 的 receipt。"""
        victim = self.root / "specs" / "feat-victim"
        (victim / "gates").mkdir(parents=True)
        (victim / "spec.md").write_text("# 受害\n", encoding="utf-8")
        (victim / "gates" / "gate-judge.json").write_text(
            '{"decision":"approved","created_at":"2026-06-12"}', encoding="utf-8")
        attacker = self.root / "specs" / "feat-attacker"
        attacker.mkdir()
        (attacker / "spec.md").write_text("# 攻击者\n", encoding="utf-8")
        (attacker / "gates").symlink_to(victim / "gates")  # 父目录软链借别人的 receipt
        data = self._payload()
        self.assertEqual(data["features"]["feat-attacker"]["gates"], {})  # 串读被拒

    def test_missing_and_corrupt_degrade(self):
        """验收 3:孤 spec 特性 + 坏 UTF-8 → 降级不崩。"""
        bare = self.root / "specs" / "feat-bare"
        bare.mkdir()
        (bare / "spec.md").write_bytes(b"# \xff\xfe bad\n")
        data = self._payload()
        f = data["features"]["feat-bare"]
        self.assertIn("�", f["spec"])  # 坏字节替换呈现
        self.assertIsNone(f["plan"])
        self.assertEqual(f["outputs"], {})
        self.assertEqual(f["gates"], {})

    def test_refuses_protected_out_dirs(self):
        for prot in ("specs/x.js", ".aiforge/x.js", "src/x.js", "tests/x.js"):
            with self.assertRaises(ValueError):
                ld.write_launcher_data(self.root, Path(prot))


if __name__ == "__main__":
    unittest.main()
