"""spec: specs/feat-bpmn 验收 9/10 — 状态导出契约 + 管线图节点 id 契约(纯 stdlib)。"""
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from aiforge import bpmn_status as bs

REPO = Path(__file__).resolve().parents[1]
STAGE_IDS = {
    "stage-requirements", "stage-architecture", "stage-decompose",
    "stage-implement", "stage-judge-commit", "stage-integrate",
}
NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

MINI_PIPELINE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'id="d" targetNamespace="http://t"><bpmn:process id="p">'
    '<bpmn:task id="stage-requirements"/></bpmn:process></bpmn:definitions>'
)


class TestPipelineIdContract(unittest.TestCase):
    """验收 10:入库管线图含映射表全部 6 个 stage id。"""

    def test_six_stage_ids_present(self):
        root = ET.parse(REPO / "docs" / "flows" / "sdlc-pipeline.bpmn").getroot()
        ids = {el.get("id") for el in root.iter() if el.get("id")}
        self.assertTrue(STAGE_IDS <= ids, f"缺 stage id: {STAGE_IDS - ids}")

    def test_committed_pipeline_js_consistent(self):
        """plan 设计点 6:入库备援源与 .bpmn 内容一致(防两份事实漂移)。"""
        js_p = REPO / "docs" / "flows" / "sdlc-pipeline.js"
        self.assertTrue(js_p.exists(), "缺入库备援源 sdlc-pipeline.js(--emit-pipeline 生成)")
        payload = js_p.read_text(encoding="utf-8").strip()
        prefix = "window.AIFORGE_PIPELINE_XML = "
        self.assertTrue(payload.startswith(prefix))
        xml = json.loads(payload[len(prefix):].rstrip(";"))
        bpmn = (REPO / "docs" / "flows" / "sdlc-pipeline.bpmn").read_text(encoding="utf-8")
        self.assertEqual(xml, bpmn)


class TestExportContract(unittest.TestCase):
    """验收 9:字段 allowlist / 降序并列 / `<` 转义 / 只读 / fail-closed。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "docs" / "flows").mkdir(parents=True)
        (self.root / "docs" / "flows" / "sdlc-pipeline.bpmn").write_text(
            MINI_PIPELINE, encoding="utf-8")
        adir = self.root / ".aiforge" / "audit"
        adir.mkdir(parents=True)
        self.audit = adir / "gates.jsonl"
        self.audit.write_text(
            '{"gate":"gate-spec","decision":"rejected","created_at":"2026-01-01","feature_id":"a","extra":"drop-me"}\n'
            'not-json\n'
            '[]\n'
            '{"gate":"gate-spec","decision":"approved","created_at":"2026-01-02","feature_id":"a"}\n'
            '{"gate":"gate-judge","decision":"rejected","created_at":"2026-01-03","feature_id":"b"}\n'
            '{"gate":"gate-judge","decision":"needs_human","created_at":"2026-01-03","feature_id":"c"}\n',
            encoding="utf-8")

    def _payload(self, dest: Path) -> dict:
        text = dest.read_text(encoding="utf-8").strip()
        prefix = "window.AIFORGE_STATUS = "
        self.assertTrue(text.startswith(prefix))
        self.assertNotIn("<", text[len(prefix):])  # `<` 全量转义(杀 </script> 与 <!--)
        return json.loads(text[len(prefix):].rstrip(";"))

    def test_export_allowlist_order_and_readonly(self):
        before = self.audit.read_bytes()
        dest = bs.write_bpmn_status(self.root)
        data = self._payload(dest)
        self.assertEqual(set(data), {"generated_at", "stages", "pipeline_xml"})  # 顶层恰为 allowlist
        self.assertEqual(set(data["stages"]["gate-spec"]),
                         {"gate", "decision", "created_at", "feature_id"})  # extra 被 allowlist 滤掉
        self.assertEqual(data["stages"]["gate-spec"]["decision"], "approved")  # 降序首条
        self.assertEqual(data["stages"]["gate-judge"]["decision"], "needs_human")  # 并列取后出现者
        self.assertEqual(data["pipeline_xml"], MINI_PIPELINE)
        self.assertEqual(self.audit.read_bytes(), before)  # 只读:审计未被改

    def test_emit_pipeline_writes_consistent_side_file(self):
        bs.write_bpmn_status(self.root, emit_pipeline=True)
        side = self.root / "docs" / "flows" / "sdlc-pipeline.js"
        payload = side.read_text(encoding="utf-8").strip()
        prefix = "window.AIFORGE_PIPELINE_XML = "
        self.assertEqual(json.loads(payload[len(prefix):].rstrip(";")), MINI_PIPELINE)

    def test_missing_pipeline_fails_closed(self):
        (self.root / "docs" / "flows" / "sdlc-pipeline.bpmn").unlink()
        with self.assertRaises(FileNotFoundError):
            bs.write_bpmn_status(self.root)
        self.assertFalse((self.root / "docs" / "flows" / "sdlc-status.js").exists())  # 无半截产物

    def test_audit_missing_graceful(self):
        self.audit.unlink()
        data = self._payload(bs.write_bpmn_status(self.root))
        self.assertEqual(data["stages"], {})

    def test_refuses_protected_out_dirs(self):
        for prot in ("specs/x.js", ".aiforge/x.js", "src/x.js", "tests/x.js"):
            with self.assertRaises(ValueError):
                bs.write_bpmn_status(self.root, Path(prot))


if __name__ == "__main__":
    unittest.main()
