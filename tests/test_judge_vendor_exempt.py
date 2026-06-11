"""spec: specs/feat-bpmn 验收 17 — gate 扫描器的 vendor 哈希验证豁免(fail-closed 七路径)。

测试内的危险 token 用拼接构造,避免本文件自身触发扫描器。
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from aiforge.harness import APPROVED, NEEDS_HUMAN, judge_diff

RISKY = "ev" + "al(" + "'x')"  # 拼接构造,勿写成连续 token


def _diff_block(path: str, payload: str, exec_bit: bool = False) -> str:
    mode = "new file mode 100755\n" if exec_bit else "new file mode 100644\n"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"{mode}"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1 @@\n"
        f"+{payload}\n"
    )


class TestVendorExempt(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.pkg = self.root / "docs" / "vendor" / "lib@1.0.0"
        self.pkg.mkdir(parents=True)

    def _put(self, rel: str, content: str, in_sums: bool = True, sums_digest: str = None):
        p = self.pkg / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        if in_sums:
            digest = sums_digest or hashlib.sha256(content.encode("utf-8")).hexdigest()
            sums = self.pkg / "SHA256SUMS"
            old = sums.read_text(encoding="utf-8") if sums.exists() else ""
            sums.write_text(old + f"{digest}  {rel}\n", encoding="utf-8")
        return f"docs/vendor/lib@1.0.0/{rel}"

    def test_verified_vendor_file_exempt(self):
        """①命中豁免:磁盘内容哈希与 SUMS 一致 → 含危险 token 的 vendor 块不进扫描。"""
        rel = self._put("bundle.min.js", f"x={RISKY};")
        decision, findings = judge_diff(_diff_block(rel, f"x={RISKY};"), self.root)
        self.assertEqual(decision, APPROVED)
        self.assertEqual(findings, [])

    def test_tampered_hash_mismatch_scanned(self):
        """②篡改:SUMS 记的是别的内容 → 照扫,needs_human。"""
        rel = self._put("bundle.min.js", f"x={RISKY};",
                        sums_digest=hashlib.sha256(b"other").hexdigest())
        decision, _ = judge_diff(_diff_block(rel, f"x={RISKY};"), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_sums_missing_scanned(self):
        """③SUMS 缺失/无条目 → 照扫。"""
        rel = self._put("bundle.min.js", f"x={RISKY};", in_sums=False)
        decision, _ = judge_diff(_diff_block(rel, f"x={RISKY};"), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_sums_file_itself_always_scanned(self):
        """④清单本身被改且夹带危险 token → 永远照扫。"""
        sums = self.pkg / "SHA256SUMS"
        sums.write_text(f"deadbeef  x.js # {RISKY}\n", encoding="utf-8")
        rel = "docs/vendor/lib@1.0.0/SHA256SUMS"
        decision, _ = judge_diff(_diff_block(rel, f"junk {RISKY}"), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_non_vendor_path_scanned(self):
        """⑤vendor 前缀之外(即使同样有 SUMS 结构)→ 照扫。"""
        d = self.root / "src" / "lib@1.0.0"
        d.mkdir(parents=True)
        content = f"x={RISKY};"
        (d / "bundle.min.js").write_text(content, encoding="utf-8")
        (d / "SHA256SUMS").write_text(
            f"{hashlib.sha256(content.encode()).hexdigest()}  bundle.min.js\n", encoding="utf-8")
        decision, _ = judge_diff(_diff_block("src/lib@1.0.0/bundle.min.js", content), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_exec_bit_overrides_exemption(self):
        """⑥可执行 bit → 强制扫,豁免失效(沿用既有最高优先级规则)。"""
        rel = self._put("bundle.min.js", f"x={RISKY};")
        decision, _ = judge_diff(_diff_block(rel, f"x={RISKY};", exec_bit=True), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_no_repo_root_scanned(self):
        """⑦不传 repo_root(纯文本调用)→ 零豁免,行为与旧版一致。"""
        rel = self._put("bundle.min.js", f"x={RISKY};")
        decision, _ = judge_diff(_diff_block(rel, f"x={RISKY};"))
        self.assertEqual(decision, NEEDS_HUMAN)

    def test_symlinked_target_not_exempt(self):
        """⑧symlink 目标不豁免(契约 09)。"""
        real = self.root / "outside.js"
        content = f"x={RISKY};"
        real.write_text(content, encoding="utf-8")
        (self.pkg / "bundle.min.js").symlink_to(real)
        sums = self.pkg / "SHA256SUMS"
        sums.write_text(
            f"{hashlib.sha256(content.encode()).hexdigest()}  bundle.min.js\n", encoding="utf-8")
        decision, _ = judge_diff(
            _diff_block("docs/vendor/lib@1.0.0/bundle.min.js", content), self.root)
        self.assertEqual(decision, NEEDS_HUMAN)


if __name__ == "__main__":
    unittest.main()
