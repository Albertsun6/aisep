"""spec: specs/feat-req-5step — R1-R5 渐进细化门禁(gate-intent / gate-scope / gate-spec 升级 / 链扩展)。

用例 1:1 对应 spec.md 验收 1-16;fixture 模式镜像 test_harness.py(_RepoCase)。
"""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiforge import harness
from aiforge.cli import main as cli_main

INTENT_OK = """# feat-x 意图简报
track: standard
source: 2026-06-12 业务会议纪要

## problem
运营导出数据要找开发,人工成本高。

## users
运营同学(每周导出 3 次)。

## 成功指标
自助导出成功率 ≥99%,零开发介入。

## non-goals
不做定时批量调度;不做权限体系改造。

## appetite
2 人日。
"""

DISCOVERY_OK = """# feat-x 发现与范围
## in
- CSV 导出按钮 — refs: intent#problem
- 导出结果下载链接 — refs: intent.md

## out
- 定时批量调度(non-goal)
- Excel 格式
"""

SPEC_WITH_TRACE = """# 玩具特性:CSV 导出
status: active

> refs: scope.md

## 验收标准
Given 用户已登录且有数据
When 用户点击导出按钮
Then 系统生成 CSV 文件并提供下载
"""

SPEC_NO_TRACE = SPEC_WITH_TRACE.replace("> refs: scope.md\n", "")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


class _RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self._old_cwd = os.getcwd()
        self.tmp = Path(tempfile.mkdtemp())
        _git(self.tmp, "init", "-q")
        _git(self.tmp, "config", "user.email", "t@test")
        _git(self.tmp, "config", "user.name", "t")
        (self.tmp / "README.md").write_text("init\n")
        _git(self.tmp, "add", "README.md")
        _git(self.tmp, "commit", "-qm", "init")
        os.chdir(self.tmp)
        self._env = mock.patch.dict(os.environ, {"CI": "", "AIFORGE_FEATURE": ""})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        os.chdir(self._old_cwd)

    # helpers
    def write(self, rel: str, text: str) -> Path:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_cli(self, *argv: str) -> tuple:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = cli_main(list(argv))
        return code, buf.getvalue()

    def receipt(self, fid: str, gate: str) -> dict:
        p = self.tmp / "specs" / fid / "gates" / f"{gate}.json"
        return json.loads(p.read_text(encoding="utf-8"))


class TestGateIntent(_RepoCase):
    def test_approved_with_receipt(self):
        """验收 1:必填节齐全 + track 合法 → 0,receipt 字段与 hash 相符。"""
        p = self.write("specs/feat-x/intent.md", INTENT_OK)
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 0)
        self.assertIn("gate-intent: approved", out)
        r = self.receipt("feat-x", "gate-intent")
        self.assertEqual(r["gate"], "gate-intent")
        self.assertEqual(r["feature_id"], "feat-x")
        self.assertEqual((r["exit_code"], r["decision"]), (0, "approved"))
        self.assertEqual(r["schema_version"], 1)
        self.assertEqual(r["inputs"][0]["path"], "specs/feat-x/intent.md")
        self.assertEqual(r["inputs"][0]["sha256"], harness.sha256_file(p))

    def test_rejected_missing_section(self):
        """验收 2:缺 non-goals 节 → 1,诊断点名;仍写 receipt(rejected)。"""
        text = INTENT_OK.replace("## non-goals\n不做定时批量调度;不做权限体系改造。\n", "")
        self.write("specs/feat-x/intent.md", text)
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("non-goals", out)
        r = self.receipt("feat-x", "gate-intent")
        self.assertEqual((r["exit_code"], r["decision"]), (1, "rejected"))

    def test_rejected_empty_section(self):
        """验收 2(空节变体):节存在但空白 → 1。"""
        text = INTENT_OK.replace("不做定时批量调度;不做权限体系改造。\n", "\n")
        self.write("specs/feat-x/intent.md", text)
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("non-goals", out)

    def test_rejected_bad_track(self):
        """验收 3:track 非法值 → 1,诊断含非法值与允许集合。"""
        self.write("specs/feat-x/intent.md", INTENT_OK.replace("track: standard", "track: turbo"))
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("turbo", out)
        self.assertIn("fast/standard/epic", out)

    def test_infra_missing_or_unparseable(self):
        """验收 4:文件不存在 / 解析不到任何节标题 → 3,不写 receipt、不落 0。"""
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 3)
        self.assertFalse((self.tmp / "specs/feat-x/gates/gate-intent.json").exists())
        self.write("specs/feat-x/intent.md", "track: fast\n没有任何二级标题的损坏结构\n")
        code, out = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 3)


class TestGateScope(_RepoCase):
    def _ok_setup(self):
        self.write("specs/feat-x/intent.md", INTENT_OK)
        return self.write("specs/feat-x/discovery.md", DISCOVERY_OK)

    def test_approved_with_receipt(self):
        """验收 5:in 项均 refs intent + out 非空 → 0,receipt 指向 discovery.md。"""
        p = self._ok_setup()
        code, out = self.run_cli("gate-scope", "--feature", "feat-x")
        self.assertEqual(code, 0)
        self.assertIn("gate-scope: approved", out)
        r = self.receipt("feat-x", "gate-scope")
        self.assertEqual(r["gate"], "gate-scope")
        self.assertEqual(r["inputs"][0]["path"], "specs/feat-x/discovery.md")
        self.assertEqual(r["inputs"][0]["sha256"], harness.sha256_file(p))

    def test_rejected_in_item_without_refs(self):
        """验收 6:in 项缺 refs → 1,诊断点名该项。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        self.write("specs/feat-x/discovery.md",
                   DISCOVERY_OK.replace("- CSV 导出按钮 — refs: intent#problem", "- CSV 导出按钮"))
        code, out = self.run_cli("gate-scope", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("未追溯", out)
        self.assertIn("CSV 导出按钮", out)

    def test_rejected_empty_out(self):
        """验收 7:out 表为空 → 1(没有显式排除 = 没做范围决策)。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        self.write("specs/feat-x/discovery.md", DISCOVERY_OK.split("## out")[0] + "## out\n\n")
        code, out = self.run_cli("gate-scope", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("out 表为空", out)

    def test_infra_missing_or_no_tables(self):
        """验收 8:discovery.md 不存在 / 解析不出 in+out 两表 → 3。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        code, _ = self.run_cli("gate-scope", "--feature", "feat-x")
        self.assertEqual(code, 3)
        self.write("specs/feat-x/discovery.md", "# 只有标题\n随便一段文字\n")
        code, _ = self.run_cli("gate-scope", "--feature", "feat-x")
        self.assertEqual(code, 3)


class TestGateSpecUpgrade(_RepoCase):
    def test_clarification_marker_rejected_then_pass(self):
        """验收 9:裸残留标记 → 1;删除后 → 0。代码格式内的提及不误伤(plan §1)。"""
        bad = SPEC_NO_TRACE + "\n[NEEDS CLARIFICATION: 导出上限多大?]\n"
        self.write("specs/feat-x/spec.md", bad)
        code, out = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 1)
        self.assertIn("NEEDS CLARIFICATION", out)
        self.write("specs/feat-x/spec.md", SPEC_NO_TRACE)
        code, _ = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 0)
        # 反引号内 = 讨论该标记,不拒
        quoted = SPEC_NO_TRACE + "\n门禁会拒绝残留的 `[NEEDS CLARIFICATION` 标记。\n"
        self.write("specs/feat-x/spec.md", quoted)
        code, _ = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 0)

    def test_trace_chain_only_when_intent_exists(self):
        """验收 10:intent 存在且 spec 无 refs → 1;补 `> refs: scope.md` → 0。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        self.write("specs/feat-x/spec.md", SPEC_NO_TRACE)
        code, out = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 1)
        self.assertIn("trace 链断", out)
        self.write("specs/feat-x/spec.md", SPEC_WITH_TRACE)
        code, _ = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 0)


class TestTracks(_RepoCase):
    def test_fast_track_short_path(self):
        """验收 11:fast——gate-intent 必跑;gate-spec 不要求 scope/discovery/clarifications 存在。"""
        self.write("specs/feat-x/intent.md", INTENT_OK.replace("track: standard", "track: fast"))
        code, _ = self.run_cli("gate-intent", "--feature", "feat-x")
        self.assertEqual(code, 0)
        # 无 discovery/scope/clarifications,spec 带 trace 回 intent 即可过
        self.write("specs/feat-x/spec.md", SPEC_WITH_TRACE.replace("> refs: scope.md", "> refs: intent.md"))
        code, _ = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 0)
        self.assertIn("track: fast", (self.tmp / "specs/feat-x/intent.md").read_text(encoding="utf-8"))

    def test_standard_track_all_gates(self):
        """验收 12:standard——三 gate 全 0,各自落 receipt。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        self.write("specs/feat-x/discovery.md", DISCOVERY_OK)
        self.write("specs/feat-x/spec.md", SPEC_WITH_TRACE)
        for gate, argv in (("gate-intent", ("gate-intent", "--feature", "feat-x")),
                           ("gate-scope", ("gate-scope", "--feature", "feat-x")),
                           ("gate-spec", ("gate-spec", "specs/feat-x/spec.md"))):
            code, _ = self.run_cli(*argv)
            self.assertEqual(code, 0, gate)
            self.assertEqual(self.receipt("feat-x", gate)["decision"], "approved")

    def test_epic_track_structure_only(self):
        """验收 13:epic——gate-intent/gate-scope 过;子 feature 回流不被机器强制。"""
        self.write("specs/feat-x/intent.md", INTENT_OK.replace("track: standard", "track: epic"))
        self.write("specs/feat-x/discovery.md", DISCOVERY_OK)
        self.assertEqual(self.run_cli("gate-intent", "--feature", "feat-x")[0], 0)
        self.assertEqual(self.run_cli("gate-scope", "--feature", "feat-x")[0], 0)


class TestReceiptChainExtension(_RepoCase):
    def _spec_ready(self, fid: str = "feat-x", spec_text: str = SPEC_NO_TRACE) -> None:
        self.write(f"specs/{fid}/spec.md", spec_text)
        code, _ = self.run_cli("gate-spec", f"specs/{fid}/spec.md")
        self.assertEqual(code, 0)

    def test_commit_requires_gate_intent_when_intent_exists(self):
        """验收 14:有 intent.md 但链上缺 gate-intent receipt → gate-commit 1,点名。"""
        self.write("specs/feat-x/intent.md", INTENT_OK)
        self._spec_ready(spec_text=SPEC_WITH_TRACE)
        self.write("src/aif.py", "X = 1\n")
        _git(self.tmp, "add", "src", "specs")
        code, out = self.run_cli("gate-commit", "--feature", "feat-x")
        self.assertEqual(code, 1)
        self.assertIn("gate-intent", out)

    def test_legacy_feature_without_intent_unaffected(self):
        """验收 15:无 intent.md 的存量 feature,gate-intent 检查不触发。"""
        self._spec_ready()
        self.write("src/aif.py", "X = 1\n")
        _git(self.tmp, "add", "src", "specs")
        problem = harness.check_receipt_chain(self.tmp, "feat-x")
        self.assertIsNone(problem)

    def test_legacy_spec_not_broken_by_new_checks(self):
        """验收 16:存量 spec(无标记、无 intent.md)行为与升级前一致 → 0。"""
        self.write("specs/feat-x/spec.md", SPEC_NO_TRACE)
        code, _ = self.run_cli("gate-spec", "specs/feat-x/spec.md")
        self.assertEqual(code, 0)
        code, out = self.run_cli("gate-spec", "specs/feat-x/spec.md", "--check")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
