"""M1 薄 CLI 契约测试(specs/contracts/ 03/04/06/07/09 的钉死方式)。

会失败的测试钉死 fail-closed:把任何一条改回 fails-open,对应断言即红。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiforge import harness
from aiforge.cli import main as cli_main

GHERKIN_SPEC = """# 玩具特性:CSV 导出
status: active

## 验收标准
Given 用户已登录且有数据
When 用户点击导出按钮
Then 系统生成 CSV 文件并提供下载
"""

NO_ACCEPTANCE_SPEC = "# 只有标题没有验收结构的 spec,这是一段足够长的描述文字用来超过最小长度。"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


class _RepoCase(unittest.TestCase):
    """每个用例一个独立临时 git 仓库,cwd 切入(CLI 从 cwd 找 repo root)。"""

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
        # 契约 07:CI env 只收紧——测试里显式清空,避免宿主 CI 环境干扰断言
        self._env = mock.patch.dict(os.environ, {"CI": "", "AIFORGE_FEATURE": ""})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        os.chdir(self._old_cwd)

    # helpers
    def write_spec(self, fid: str = "feat-x", text: str = GHERKIN_SPEC) -> Path:
        p = self.tmp / "specs" / fid / "spec.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def receipt_path(self, fid: str, gate: str) -> Path:
        return self.tmp / "specs" / fid / "gates" / f"{gate}.json"


class TestExitMapper(unittest.TestCase):
    def test_single_point_mapping(self):
        """契约 03:0/1/2/3 唯一映射。"""
        self.assertEqual(harness.EXIT, {"approved": 0, "rejected": 1, "needs_human": 2, "infra_error": 3})


class TestGateSpec(_RepoCase):
    def test_valid_spec_approved_with_receipt(self):
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        rcpt = json.loads(self.receipt_path("feat-x", "gate-spec").read_text())
        self.assertEqual(rcpt["decision"], "approved")
        self.assertEqual(rcpt["schema_version"], 1)
        self.assertTrue(rcpt["run_id"])
        self.assertEqual(rcpt["inputs"][0]["path"], "specs/feat-x/spec.md")
        self.assertEqual(rcpt["inputs"][0]["sha256"], harness.sha256_file(spec))

    def test_missing_spec_rejected(self):
        self.assertEqual(cli_main(["gate-spec", "specs/feat-x/spec.md"]), 1)

    def test_empty_spec_rejected(self):
        spec = self.write_spec(text="   \n")
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 1)

    def test_no_acceptance_structure_rejected(self):
        spec = self.write_spec(text=NO_ACCEPTANCE_SPEC)
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 1)

    def test_symlink_input_is_infra(self):
        """契约 09:gate 输入不跟随 symlink → 3。"""
        real = self.write_spec("feat-real")
        link = self.tmp / "specs" / "feat-link" / "spec.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(real)
        self.assertEqual(cli_main(["gate-spec", str(link)]), 3)


class TestGateSpecCheckFrozen(_RepoCase):
    """probe③ 落改:--check 只读冻结校验,改冻结 spec 不重跑 gate-spec 即被抓。"""

    def test_check_passes_when_receipt_matches(self):
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        self.assertEqual(cli_main(["gate-spec", "--check", str(spec)]), 0)

    def test_check_does_not_write_receipt(self):
        """关键:--check 不重新生成 receipt(否则会洗白篡改)。"""
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        before = self.receipt_path("feat-x", "gate-spec").read_text()
        spec.write_text(GHERKIN_SPEC + "\n篡改但仍结构合法\n")
        self.assertEqual(cli_main(["gate-spec", "--check", str(spec)]), 1)  # 抓到
        after = self.receipt_path("feat-x", "gate-spec").read_text()
        self.assertEqual(before, after, "--check 不得改写 receipt")

    def test_check_rejects_tampered_frozen_spec(self):
        """probe③ 复刻:gate-spec 通过后篡改 spec(仍 Gherkin 合法)→ --check 1。"""
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        spec.write_text(GHERKIN_SPEC + "\n## 偷偷追加(未过 gate)\nGiven x When y Then z\n")
        self.assertEqual(cli_main(["gate-spec", "--check", str(spec)]), 1)

    def test_check_missing_receipt_rejected(self):
        spec = self.write_spec()  # 没跑过 gate-spec,无 receipt
        self.assertEqual(cli_main(["gate-spec", "--check", str(spec)]), 1)

    def test_check_corrupt_receipt_is_infra(self):
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        self.receipt_path("feat-x", "gate-spec").write_text("{bad")
        self.assertEqual(cli_main(["gate-spec", "--check", str(spec)]), 3)


class TestGateTrace(_RepoCase):
    def test_spec_only_passes(self):
        self.write_spec()
        self.assertEqual(cli_main(["gate-trace", "specs/feat-x"]), 0)

    def test_missing_spec_rejected(self):
        (self.tmp / "specs" / "feat-x").mkdir(parents=True)
        self.assertEqual(cli_main(["gate-trace", "specs/feat-x"]), 1)

    def test_plan_without_refs_rejected(self):
        self.write_spec()
        (self.tmp / "specs" / "feat-x" / "plan.md").write_text("# 计划,没有声明上游\n")
        self.assertEqual(cli_main(["gate-trace", "specs/feat-x"]), 1)

    def test_declared_chain_passes(self):
        self.write_spec()
        (self.tmp / "specs" / "feat-x" / "plan.md").write_text("# 计划\n> refs: spec.md\n")
        (self.tmp / "specs" / "feat-x" / "tasks.md").write_text("# 任务\n> refs: plan.md\n")
        self.assertEqual(cli_main(["gate-trace", "specs/feat-x"]), 0)

    def test_broken_upstream_rejected(self):
        """tasks 声明 plan 但 plan 不存在 → 链断。"""
        self.write_spec()
        (self.tmp / "specs" / "feat-x" / "tasks.md").write_text("> refs: plan.md\n")
        self.assertEqual(cli_main(["gate-trace", "specs/feat-x"]), 1)


class TestGateJudge(_RepoCase):
    def test_dangerous_diff_needs_human(self):
        (self.tmp / "danger.py").write_text("x = eval(user_input)\n")
        _git(self.tmp, "add", "danger.py")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_clean_diff_approved(self):
        (self.tmp / "clean.py").write_text("def add(a, b):\n    return a + b\n")
        _git(self.tmp, "add", "clean.py")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 0)

    def test_base_range_diff(self):
        """CI 路径(gates.yml):gate-judge --base 审 base...HEAD 范围 diff。"""
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(self.tmp),
                              capture_output=True, text=True, check=True).stdout.strip()
        (self.tmp / "danger.py").write_text("x = eval(user_input)\n")
        _git(self.tmp, "add", "danger.py")
        _git(self.tmp, "commit", "-qm", "danger")
        self.assertEqual(cli_main(["gate-judge", "--base", base]), 2)


class TestReview3f(_RepoCase):
    def test_informational_exit_zero(self):
        (self.tmp / "auth_module.py").write_text("token = 1\n")
        _git(self.tmp, "add", "auth_module.py")
        self.assertEqual(cli_main(["review-3f", "--staged"]), 0)


class TestGateCommit(_RepoCase):
    def _stage_code(self, content: str = "def f():\n    return 1\n") -> None:
        src = self.tmp / "src"
        src.mkdir(exist_ok=True)
        (src / "mod.py").write_text(content)
        _git(self.tmp, "add", "src/mod.py")

    def _approved_feature(self, fid: str = "feat-x") -> None:
        spec = self.write_spec(fid)
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        _git(self.tmp, "add", "specs")  # 链校验以 index 为准:spec 必须随提交入库

    def test_code_without_feature_declaration_rejected(self):
        """契约 02:src/tests 改动无 feature 声明 → 1(攻击探针①本地半身)。"""
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit"]), 1)

    def test_declared_feature_without_spec_rejected(self):
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "ghost"]), 1)

    def test_unstaged_spec_rejected(self):
        """链校验以 index 为准:spec 只在工作区、没 git add → 1。"""
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 1)

    def test_happy_path(self):
        self._approved_feature()
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 0)
        rcpt = json.loads(self.receipt_path("feat-x", "gate-commit").read_text())
        self.assertEqual(rcpt["decision"], "approved")
        self.assertIsNone(rcpt["ack"])

    def test_tampered_staged_spec_stales_receipt(self):
        """契约 06 篡改测试(TOCTOU 修复):篡改并 stage、不重跑 gate-spec → 1。"""
        self._approved_feature()
        (self.tmp / "specs" / "feat-x" / "spec.md").write_text(GHERKIN_SPEC + "\n偷偷加一行需求\n")
        _git(self.tmp, "add", "specs")  # 篡改版进 index——这才是将被提交的内容
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 1)

    def test_worktree_only_tamper_does_not_block(self):
        """index 语义反面:只改工作区不 stage(不会被提交)→ 不误伤。"""
        self._approved_feature()
        (self.tmp / "specs" / "feat-x" / "spec.md").write_text(GHERKIN_SPEC + "\n工作区草稿\n")
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 0)

    def test_forged_receipt_hash_mismatch(self):
        """契约 06 伪造测试:decision=approved 但 hash 不符 → 1。"""
        self._approved_feature()
        rp = self.receipt_path("feat-x", "gate-spec")
        rcpt = json.loads(rp.read_text())
        rcpt["inputs"][0]["sha256"] = "0" * 64
        rp.write_text(json.dumps(rcpt))
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 1)

    def test_forged_receipt_metadata_mismatch(self):
        """M1 评审 blocker 落改:hash 对但元数据不符(feature_id 串号)→ 1。"""
        self._approved_feature()
        rp = self.receipt_path("feat-x", "gate-spec")
        rcpt = json.loads(rp.read_text())
        rcpt["feature_id"] = "other-feature"
        rp.write_text(json.dumps(rcpt))
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 1)

    def test_feature_id_path_traversal_is_infra(self):
        """M1 评审 blocker 落改:--feature 路径穿越 → 3,receipt 不落 repo 外。"""
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "../evil"]), 3)
        self.assertFalse((self.tmp.parent / "evil").exists())

    def test_corrupt_receipt_is_infra(self):
        """契约 06/03:receipt 不可解析 → 3(同样阻断,诊断不同)。"""
        self._approved_feature()
        self.receipt_path("feat-x", "gate-spec").write_text("{not json")
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 3)

    def test_unknown_schema_version_is_infra(self):
        """契约 09:版本 ≠ 已知(高或低)→ 3,不猜。"""
        for bad_ver in (99, 0):
            self._approved_feature()
            rp = self.receipt_path("feat-x", "gate-spec")
            rcpt = json.loads(rp.read_text())
            rcpt["schema_version"] = bad_ver
            rp.write_text(json.dumps(rcpt))
            self._stage_code()
            self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 3, f"ver={bad_ver}")

    def test_unknown_fields_ignored(self):
        """契约 09:消费者忽略未知字段(新增兼容字段不升版)。"""
        self._approved_feature()
        rp = self.receipt_path("feat-x", "gate-spec")
        rcpt = json.loads(rp.read_text())
        rcpt["future_field"] = {"x": 1}
        rp.write_text(json.dumps(rcpt))
        self._stage_code()
        self.assertEqual(cli_main(["gate-commit", "--feature", "feat-x"]), 0)

    def test_needs_human_without_ack(self):
        (self.tmp / "danger.py").write_text("import os\nos.system(cmd)\n")
        _git(self.tmp, "add", "danger.py")
        self.assertEqual(cli_main(["gate-commit"]), 2)

    def test_ack_non_tty_is_infra(self):
        """契约 07:非 tty --ack-human → 3(审计环境不可满足);传了就查,不等 needs_human。"""
        (self.tmp / "danger.py").write_text("import os\nos.system(cmd)\n")
        _git(self.tmp, "add", "danger.py")
        with mock.patch.object(sys.stdin, "isatty", return_value=False, create=True):
            self.assertEqual(cli_main(["gate-commit", "--ack-human"]), 3)

    def test_ack_non_tty_checked_even_on_clean_diff(self):
        """M1 评审落改:clean diff 下非 tty --ack-human 也 3,语义一致。"""
        (self.tmp / "clean.py").write_text("x = 1\n")
        _git(self.tmp, "add", "clean.py")
        with mock.patch.object(sys.stdin, "isatty", return_value=False, create=True):
            self.assertEqual(cli_main(["gate-commit", "--ack-human"]), 3)

    def test_ack_with_tty_records_audit(self):
        """契约 07:tty 下 ack → 0,receipt.ack 记录最小身份字段(审计,非认证)。"""
        (self.tmp / "danger.py").write_text("import os\nos.system(cmd)\n")
        _git(self.tmp, "add", "danger.py")
        with mock.patch.object(sys.stdin, "isatty", return_value=True, create=True):
            self.assertEqual(cli_main(["gate-commit", "--ack-human"]), 0)
        rcpt = json.loads(self.receipt_path("_workspace", "gate-commit").read_text())
        self.assertEqual(rcpt["decision"], "approved")
        for key in ("user", "uid", "hostname", "at"):
            self.assertIn(key, rcpt["ack"])

    def test_ci_ignores_ack(self):
        """契约 07:CI 永远重跑 gate,不消费本地 ack——伪 tty 也没用。"""
        (self.tmp / "danger.py").write_text("import os\nos.system(cmd)\n")
        _git(self.tmp, "add", "danger.py")
        with mock.patch.object(sys.stdin, "isatty", return_value=True, create=True):
            self.assertEqual(cli_main(["gate-commit", "--ack-human", "--ci"]), 2)


class TestBillingBoundary(unittest.TestCase):
    """契约 04 静态钉死:CLI 源码无模型调用 token(三层之一,承认非完备)。"""

    FORBIDDEN = ("claude -p", "cursor-agent", "codex", "anthropic", "openai")

    def test_no_model_tokens_in_cli_sources(self):
        pkg = Path(__file__).resolve().parents[1] / "src" / "aiforge"
        for name in ("harness.py", "cli.py", "__main__.py"):
            text = (pkg / name).read_text(encoding="utf-8").lower()
            for token in self.FORBIDDEN:
                self.assertNotIn(token, text, f"{name} 含禁用 token: {token}")


class TestMainEntry(unittest.TestCase):
    """契约 03:python -m aiforge 的 usage 错误重映射为 3(2 保留给 needs_human)。"""

    def test_usage_error_maps_to_infra(self):
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH="src")
        proc = subprocess.run([sys.executable, "-m", "aiforge"], cwd=str(repo),
                              env=env, capture_output=True)
        self.assertEqual(proc.returncode, 3)

    def test_string_systemexit_maps_to_infra(self):
        """M1 评审落改:sys.exit("msg") 非 int → 3,绝不映射 0(fail-open 洞)。"""
        from aiforge import __main__ as entry
        with mock.patch("aiforge.cli.main", side_effect=SystemExit("bad")):
            self.assertEqual(entry._main(), 3)
        with mock.patch("aiforge.cli.main", side_effect=SystemExit(None)):
            self.assertEqual(entry._main(), 0)


if __name__ == "__main__":
    unittest.main()
