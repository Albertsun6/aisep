"""spec: specs/project-dashboard — 项目总览生成器(只读、HTML 转义防注入、优雅降级)。"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from aiforge import project_dashboard as pd


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=str(cwd), check=True, capture_output=True)


class _Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _git(self.tmp, "init", "-q")
        _git(self.tmp, "config", "user.email", "t@t")
        _git(self.tmp, "config", "user.name", "t")
        (self.tmp / "README.md").write_text("x\n")
        _git(self.tmp, "add", "README.md")
        _git(self.tmp, "commit", "-qm", "init")

    def _spec(self, fid, title="# 玩具特性\nstatus: active\n", gates=()):
        d = self.tmp / "specs" / fid
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.md").write_text(title, encoding="utf-8")
        if gates:
            (d / "gates").mkdir(exist_ok=True)
            for g in gates:
                (d / "gates" / f"{g}.json").write_text("{}", encoding="utf-8")


class TestCollect(_Repo):
    def test_features_collected_excluding_contracts_workspace(self):
        self._spec("feat-a", gates=("gate-spec",))
        self._spec("feat-b")
        (self.tmp / "specs" / "contracts").mkdir(parents=True)
        (self.tmp / "specs" / "contracts" / "01-x.md").write_text("# 契约一\n")
        (self.tmp / "specs" / "_workspace").mkdir(parents=True)
        (self.tmp / "specs" / "_workspace" / "spec.md").write_text("# 草稿\n")
        state = pd.collect_state(self.tmp)
        ids = [f["id"] for f in state["features"]]
        self.assertEqual(ids, ["feat-a", "feat-b"])  # contracts/_workspace 排除
        self.assertEqual(state["features"][0]["gates"], ["gate-spec"])
        self.assertEqual(len(state["contracts"]), 1)

    def test_audit_graceful_when_missing(self):
        """验收:无审计文件 → 空,不崩。"""
        state = pd.collect_state(self.tmp)
        self.assertEqual(state["audit"], [])
        self.assertEqual(state["audit_runs"], 0)

    def test_audit_parsed_newest_first(self):
        adir = self.tmp / ".aiforge" / "audit"
        adir.mkdir(parents=True)
        (adir / "gates.jsonl").write_text(
            '{"created_at":"2026-01-01","gate":"gate-spec","decision":"approved"}\n'
            '{"created_at":"2026-01-02","gate":"gate-commit","decision":"rejected"}\n'
            'not-json-skip-me\n',
            encoding="utf-8",
        )
        state = pd.collect_state(self.tmp)
        self.assertEqual(len(state["audit"]), 2)  # 坏行跳过
        self.assertEqual(state["audit"][0]["gate"], "gate-commit")  # 最近在前


class TestRenderSecurity(_Repo):
    def test_html_escaped_no_injection(self):
        """**安全核心**:spec 标题含 <script> → 必须转义,不得原样注入页面。"""
        self._spec("evil", title="# <script>alert(1)</script>\nstatus: <b>x</b>\n")
        state = pd.collect_state(self.tmp)
        out = pd.render_html(state)
        self.assertNotIn("<script>alert(1)</script>", out)  # 原样脚本不在
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)  # 转义后在
        self.assertNotIn("<b>x</b>", out)  # status 也转义

    def test_feature_id_escaped(self):
        # feature id 来自目录名,也走 esc
        out = pd.render_html({
            "generated_at": "2026", "features": [
                {"id": "a<b", "title": "t&u", "status": "active", "gates": []}],
            "audit": [], "contracts": [], "commit_count": "1",
            "recent_commits": [], "test_count": 0, "audit_runs": 0,
        })
        self.assertIn("a&lt;b", out)
        self.assertIn("t&amp;u", out)


class TestGenerateE2E(_Repo):
    def test_generate_writes_html_with_sections(self):
        self._spec("feat-a", gates=("gate-spec", "gate-trace"))
        out = pd.write_project_dashboard(self.tmp, self.tmp / "out.html")
        self.assertTrue(out.exists())
        html = out.read_text(encoding="utf-8")
        for sec in ("overview", "arch", "pipeline", "features", "audit", "contracts", "journey"):
            self.assertIn(f'id="{sec}"', html)
        self.assertIn("feat-a", html)

    def test_default_out_path(self):
        dest = pd.write_project_dashboard(self.tmp, None)
        self.assertEqual(dest, self.tmp / "docs" / "project-dashboard.html")
        self.assertTrue(dest.exists())

    def test_idempotent_reflects_current_state(self):
        """验收:重跑反映最新状态(加了特性 → 卡片变多)。"""
        self._spec("feat-a")
        pd.write_project_dashboard(self.tmp, self.tmp / "d.html")
        first = (self.tmp / "d.html").read_text(encoding="utf-8")
        self.assertNotIn("feat-b", first)
        self._spec("feat-b")
        pd.write_project_dashboard(self.tmp, self.tmp / "d.html")
        second = (self.tmp / "d.html").read_text(encoding="utf-8")
        self.assertIn("feat-b", second)  # 最新状态

    def test_empty_project_does_not_crash(self):
        """无特性/无审计 → 优雅降级,命令不崩。"""
        out = pd.write_project_dashboard(self.tmp, self.tmp / "e.html")
        html = out.read_text(encoding="utf-8")
        self.assertIn("暂无", html)  # 降级文案


class TestReviewFixes(_Repo):
    """异构评审落改(2026-06-11):损坏文件/非 dict 审计/输出护栏。"""

    def test_corrupt_utf8_does_not_crash(self):
        """评审①:spec.md 非法 UTF-8 → 降级不崩。"""
        d = self.tmp / "specs" / "bad"
        d.mkdir(parents=True)
        (d / "spec.md").write_bytes(b"# \xff\xfe bad bytes\nstatus: active\n")
        state = pd.collect_state(self.tmp)  # 不应抛
        self.assertEqual(state["features"][0]["id"], "bad")

    def test_audit_non_dict_line_skipped(self):
        """评审②:审计行是合法 JSON 但非 dict([]、123、字符串)→ 跳过,不崩。"""
        adir = self.tmp / ".aiforge" / "audit"
        adir.mkdir(parents=True)
        (adir / "gates.jsonl").write_text(
            '[]\n123\n"hello"\n{"gate":"gate-spec","decision":"approved"}\n', encoding="utf-8"
        )
        state = pd.collect_state(self.tmp)
        self.assertEqual(len(state["audit"]), 1)  # 只有 dict 行
        # render 不崩(_audit_row 只拿到 dict)
        self.assertIn("gate-spec", pd.render_html(state))

    def test_refuses_writing_into_protected_dir(self):
        """评审③:输出路径落在 specs/.aiforge/src/tests → 拒绝(只读报告不改代码/规格)。"""
        for prot in ("specs/x.html", ".aiforge/x.html", "src/x.html", "tests/x.html"):
            with self.assertRaises(ValueError):
                pd.write_project_dashboard(self.tmp, self.tmp / prot)
        # docs/ 与 repo 外允许
        ok = pd.write_project_dashboard(self.tmp, self.tmp / "docs" / "ok.html")
        self.assertTrue(ok.exists())


if __name__ == "__main__":
    unittest.main()
