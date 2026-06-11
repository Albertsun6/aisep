"""spec: specs/toy-csv-export — 验收标准 1/2/3 的可执行对应(自举试运行特性)。"""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from aiforge.cli import main as cli_main


class TestDemoCsvExport(unittest.TestCase):
    def test_export_writes_header_and_rows(self):
        """验收 1:demo --csv 生成 UTF-8 CSV,首行表头,每个 artifact 一行。"""
        out = Path(tempfile.mkdtemp()) / "out.csv"
        self.assertEqual(cli_main(["demo", "--approve", "--csv", str(out)]), 0)
        with out.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["kind", "produced_by", "refs", "created_at"])
        self.assertGreater(len(rows), 1, "至少导出一个 artifact")

    def test_missing_parent_dir_fails_loudly(self):
        """验收 2:父目录不存在 → 非 0 + stderr 可读诊断,不静默吞错。"""
        out = Path(tempfile.mkdtemp()) / "no" / "such" / "dir" / "out.csv"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertNotEqual(cli_main(["demo", "--approve", "--csv", str(out)]), 0)
        self.assertFalse(out.exists())
        self.assertIn("目录不存在", stderr.getvalue())

    def test_unwritable_target_fails_loudly(self):
        """评审落改:目标是目录等 OSError → 非 0 + 可读诊断,不裸 traceback。"""
        out = Path(tempfile.mkdtemp())  # 目标本身是目录 → open 必失败
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertNotEqual(cli_main(["demo", "--approve", "--csv", str(out)]), 0)
        self.assertIn("CSV 写入失败", stderr.getvalue())

    def test_no_flag_no_file(self):
        """验收 3:不传 --csv 行为与现状一致,不产生文件。"""
        before = set(Path.cwd().glob("*.csv"))
        self.assertEqual(cli_main(["demo", "--approve"]), 0)
        self.assertEqual(set(Path.cwd().glob("*.csv")), before)


if __name__ == "__main__":
    unittest.main()
