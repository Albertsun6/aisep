"""spec: specs/feat-bpmn — BPMN 工作台静态探针(vendor 完整性/零外呼;纯 stdlib,不起浏览器)。"""
import hashlib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "docs" / "vendor" / "bpmn-js@18.18.0"


class TestVendorIntegrity(unittest.TestCase):
    """验收 16:vendor 清单齐 + SHA256SUMS 逐文件复核 + license 合规物料。"""

    REQUIRED = (
        "bpmn-modeler.production.min.js",
        "assets/diagram-js.css",
        "assets/bpmn-js.css",
        "assets/bpmn-font/css/bpmn.css",
        "assets/bpmn-font/font/bpmn.woff2",
        "assets/bpmn-font/font/bpmn.woff",
        "LICENSE",
        "SHA256SUMS",
    )

    def test_required_files_present(self):
        for rel in self.REQUIRED:
            self.assertTrue((VENDOR / rel).is_file(), f"vendor 缺 {rel}")

    def test_sha256sums_match(self):
        """逐文件重哈希与 SHA256SUMS 一致(防篡改;格式同 `shasum -a 256`)。"""
        sums = (VENDOR / "SHA256SUMS").read_text(encoding="utf-8").strip().splitlines()
        self.assertGreater(len(sums), 0)
        for line in sums:
            digest, _, rel = line.partition("  ")
            p = VENDOR / rel.strip()
            self.assertTrue(p.is_file(), f"SHA256SUMS 列了不存在的 {rel}")
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(actual, digest, f"{rel} 哈希不符(被改动?)")

    def test_sha256sums_cover_all_files(self):
        """vendor 内不允许有未被 SHA256SUMS 锁住的文件(防夹带)。"""
        sums = (VENDOR / "SHA256SUMS").read_text(encoding="utf-8")
        listed = {line.partition("  ")[2].strip() for line in sums.strip().splitlines()}
        on_disk = {
            str(p.relative_to(VENDOR))
            for p in VENDOR.rglob("*")
            if p.is_file() and p.name != "SHA256SUMS"
        }
        self.assertEqual(on_disk, listed)

    def test_license_has_watermark_clause(self):
        """bpmn.io license 的水印条款是硬合规依据,必须随 vendor 入库。"""
        text = (VENDOR / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("watermark", text)

    def test_bundle_exposes_global_and_watermark_code(self):
        """预构建 bundle 含全局名 BpmnJS 与水印代码(bjs-powered-by)——不得用改动过的 bundle。"""
        js = (VENDOR / "bpmn-modeler.production.min.js").read_text(encoding="utf-8", errors="replace")
        self.assertIn("BpmnJS", js)
        self.assertIn("bjs-powered-by", js)


if __name__ == "__main__":
    unittest.main()
