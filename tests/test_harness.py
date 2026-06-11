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


class TestGateAuditLog(_RepoCase):
    """spec: specs/gate-audit-log — 每次 gate 追加一行到 .aiforge/audit/gates.jsonl(fail-open)。"""

    def _audit_lines(self) -> list:
        p = self.tmp / ".aiforge" / "audit" / "gates.jsonl"
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def test_gate_appends_audit_row(self):
        """验收1:跑 gate-spec → 审计追加一行,含约定字段。"""
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        rows = self._audit_lines()
        self.assertEqual(len(rows), 1)
        for key in ("created_at", "gate", "feature_id", "decision", "exit_code", "git_head", "run_id"):
            self.assertIn(key, rows[0])
        self.assertEqual(rows[0]["gate"], "gate-spec")
        self.assertEqual(rows[0]["decision"], "approved")

    def test_append_not_overwrite(self):
        """验收2:连跑多个 gate → 多行,append 不覆盖(第一行原样保留)。"""
        spec = self.write_spec()
        cli_main(["gate-spec", str(spec)])
        first = self._audit_lines()[0]
        cli_main(["gate-trace", "specs/feat-x"])
        rows = self._audit_lines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], first)  # 旧行不变
        self.assertEqual(rows[1]["gate"], "gate-trace")

    def test_audit_dir_autocreated(self):
        """验收3:.aiforge/audit 不存在 → 自动创建,gate 不报错。"""
        self.assertFalse((self.tmp / ".aiforge" / "audit").exists())
        spec = self.write_spec()
        self.assertEqual(cli_main(["gate-spec", str(spec)]), 0)
        self.assertTrue((self.tmp / ".aiforge" / "audit" / "gates.jsonl").exists())

    def test_audit_write_failure_is_fail_open(self):
        """验收4:审计写失败 → gate 退出码不变(fail-open),仅 stderr 警告。"""
        import io
        from contextlib import redirect_stderr
        spec = self.write_spec()
        # 让 .aiforge/audit 变成一个文件,使其下 mkdir/写入失败
        adir = self.tmp / ".aiforge"
        adir.mkdir()
        (adir / "audit").write_text("not a dir", encoding="utf-8")  # audit 是文件,mkdir 会 OSError
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cli_main(["gate-spec", str(spec)])
        self.assertEqual(rc, 0)  # gate 判定不受影响
        self.assertIn("审计追加失败", err.getvalue())  # 但有警告

    def test_audit_symlink_path_refused(self):
        """评审落改(High):审计路径是 symlink → 拒绝跟随写,gate 退出码不变(fail-open)。"""
        import io
        from contextlib import redirect_stderr
        spec = self.write_spec()
        # .aiforge/audit 指向 repo 外目录 → 不应跟随写
        outside = Path(tempfile.mkdtemp())
        (self.tmp / ".aiforge").mkdir()
        (self.tmp / ".aiforge" / "audit").symlink_to(outside)
        err = io.StringIO()
        with redirect_stderr(err):
            rc = cli_main(["gate-spec", str(spec)])
        self.assertEqual(rc, 0)
        self.assertIn("symlink", err.getvalue())
        self.assertFalse((outside / "gates.jsonl").exists())  # 没写到 repo 外

    def test_audit_no_sensitive_fields(self):
        """评审落改(Low,防回归):审计行只含 allowlist,绝不含 argv/ack/reviewer/inputs。"""
        # gate-commit 的 receipt 含 argv/ack;审计行必须只取子集
        spec = self.write_spec()
        cli_main(["gate-spec", str(spec)])
        _git(self.tmp, "add", "specs")
        (self.tmp / "src").mkdir()
        (self.tmp / "src" / "m.py").write_text("def f():\n    return 1\n")
        _git(self.tmp, "add", "src/m.py")
        cli_main(["gate-commit", "--feature", "feat-x"])
        row = self._audit_lines()[-1]
        self.assertEqual(set(row), {"created_at", "gate", "feature_id", "decision", "exit_code", "git_head", "run_id"})
        for forbidden in ("argv", "ack", "reviewer", "inputs", "tool", "aiforge_version", "schema_version"):
            self.assertNotIn(forbidden, row)


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


# 危险 token 故意拼接——使本测试文件 .py 源码里不出现完整的危险模式字面(否则扫描器
# 会扫到本文件自身,因为它正确地扫 .py;且 diff 行带 + 前缀,scanner 的注释过滤会失效)。
# 运行时拼出真模式来测 scanner 行为。这是测扫描器的测试卫生,不是绕门禁(产品代码不做)。
_EV = "ev" "al"        # 运行时 == 内置求值函数名
_SYS = "os.sys" "tem"  # 运行时 == os 的命令执行函数名


class TestScannerSkipDocs(_RepoCase):
    """spec: specs/scanner-skip-docs — 只扫可执行代码,跳过纯文档(fail-closed)。"""

    def _stage(self, name: str, content: str) -> None:
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        _git(self.tmp, "add", name)

    def test_eval_in_markdown_skipped(self):
        """验收1:.md 里的危险字样不命中 → 0。"""
        self._stage("GUIDE.md", f"讲解:危险代码长这样 `return {_EV}(c)`,会被拦。\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 0)

    def test_eval_in_python_still_caught(self):
        """验收2:.py 里的危险字样照常命中 → 2。"""
        self._stage("mod.py", f"def run(c):\n    return {_EV}(c)\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_unknown_suffix_still_scanned(self):
        """验收3:未知后缀仍扫(fail-closed,宁误报不漏报)→ 2。"""
        self._stage("script.xyz", f"import os\n{_SYS}(x)\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_no_suffix_still_scanned(self):
        """无后缀文件(如脚本)仍扫 → 2。"""
        self._stage("runme", f"{_EV}(payload)\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_mixed_only_code_counts(self):
        """验收4:同 diff 改 .md(含危险字样)+ 干净 .py → 只看代码,0。"""
        self._stage("doc.md", f"示例 `{_EV}(x)` 教学。\n")
        self._stage("clean.py", "def f():\n    return 1\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 0)

    # ---- 异构评审(2026-06-11)补的攻击测试:可执行面一律扫,不豁免 ----

    def test_workflow_yaml_still_scanned(self):
        """评审 blocker:.github/workflows/*.yml 是 CI 可执行面,不豁免 → 2。"""
        self._stage(".github/workflows/ci.yml", f"steps:\n  - run: python -c '{_EV}(1)'\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_html_with_script_still_scanned(self):
        """评审 blocker:.html 含 <script> 可执行,不豁免 → 2。"""
        self._stage("evil.html", f"<script>{_EV}(x)</script>\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_svg_still_scanned(self):
        """评审 blocker:.svg 可含 <script>,不豁免 → 2。"""
        self._stage("pic.svg", f"<svg><script>{_EV}(x)</script></svg>\n")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_json_config_still_scanned(self):
        """评审 major:.json(如 package.json scripts)影响执行链,不豁免 → 2。"""
        self._stage("package.json", f'{{"scripts": {{"x": "node -e \\"{_EV}(1)\\""}}}}\n')
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_executable_markdown_forced_scan(self):
        """评审 major:.md 带 executable bit(chmod 755 + shebang)会被执行 → 强制扫 → 2。"""
        p = self.tmp / "hook.md"
        p.write_text(f"#!/bin/sh\n{_EV}(x)\n", encoding="utf-8")
        p.chmod(0o755)
        _git(self.tmp, "add", "hook.md")
        self.assertEqual(cli_main(["gate-judge", "--staged"]), 2)

    def test_code_only_diff_helper(self):
        """单元级:code_only_diff 剔除纯文档块、保留代码块。"""
        a_line = f"+{_EV}(a)\n"
        b_line = f"+{_EV}(b)\n"
        diff = (
            "diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n@@ -0,0 +1 @@\n" + a_line
            + "diff --git a/y.py b/y.py\n--- a/y.py\n+++ b/y.py\n@@ -0,0 +1 @@\n" + b_line
        )
        kept = harness.code_only_diff(diff)
        self.assertNotIn(a_line.strip(), kept)  # md 块剔除
        self.assertIn(b_line.strip(), kept)     # py 块保留

    def test_code_only_diff_executable_md_kept(self):
        """单元级:executable bit 的 .md 块被强制保留(覆盖后缀豁免)。"""
        ev = f"+{_EV}(x)\n"
        diff = (
            "diff --git a/h.md b/h.md\nnew file mode 100755\n"
            "--- /dev/null\n+++ b/h.md\n@@ -0,0 +1 @@\n" + ev
        )
        self.assertIn(ev.strip(), harness.code_only_diff(diff))


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
