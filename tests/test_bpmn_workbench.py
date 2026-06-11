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


class TestFixtures(unittest.TestCase):
    """验收 5/13 前置:fixture 结构健全(ElementTree 静态断言,不起浏览器)。"""

    NS = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    }
    FLOWS = REPO / "specs" / "feat-bpmn" / "flows"

    def test_order_fixture_required_elements(self):
        import xml.etree.ElementTree as ET
        root = ET.parse(self.FLOWS / "fixture-order.bpmn").getroot()
        self.assertEqual(len(root.findall(".//bpmn:participant", self.NS)), 1)  # pool
        self.assertEqual(len(root.findall(".//bpmn:lane", self.NS)), 2)
        self.assertEqual(len(root.findall(".//bpmn:exclusiveGateway", self.NS)), 1)
        self.assertEqual(len(root.findall(".//bpmn:boundaryEvent", self.NS)), 1)
        named_tasks = [t for t in root.findall(".//bpmn:task", self.NS) if t.get("name")]
        self.assertGreaterEqual(len(named_tasks), 2)
        # DI 在,bpmn-js 才有图可画(空 plane = 渲染空白,验收 5 直接失败)
        self.assertEqual(len(root.findall(".//bpmndi:BPMNDiagram", self.NS)), 1)
        shapes = root.findall(".//bpmndi:BPMNShape", self.NS)
        nodes = root.findall(".//bpmn:process//*[@id]", self.NS)
        self.assertGreaterEqual(len(shapes), 8)
        self.assertGreater(len(nodes), 0)

    def test_xss_fixture_carries_sentinel_payloads(self):
        import xml.etree.ElementTree as ET
        root = ET.parse(self.FLOWS / "fixture-xss.bpmn").getroot()
        names = [el.get("name", "") for el in root.iter() if el.get("name")]
        joined = "\n".join(names)
        self.assertIn("<script>window.__pwned=1</script>", joined)  # XML 解码后是活 payload
        self.assertIn('onerror="window.__pwned=1"', joined)
        docs = root.findall(".//bpmn:documentation", self.NS)
        self.assertTrue(any("<script>" in (d.text or "") for d in docs))


if __name__ == "__main__":
    unittest.main()
