import os
import tempfile
import unittest

from aiforge.context.agents_md import find_agents_md_chain, load_nearest_agents_md
from aiforge.context.code_index import build_index
from aiforge.context.memory import ContextWindow
from aiforge.context.skills import Skill, SkillRegistry


class TestAgentsMd(unittest.TestCase):
    def test_nested_chain_nearest_last(self):
        root = tempfile.mkdtemp()
        sub = os.path.join(root, "pkg", "deep")
        os.makedirs(sub)
        with open(os.path.join(root, "AGENTS.md"), "w") as f:
            f.write("ROOT")
        with open(os.path.join(root, "pkg", "AGENTS.md"), "w") as f:
            f.write("PKG")
        chain = find_agents_md_chain(os.path.join(sub, "x.py"), root)
        self.assertEqual([os.path.basename(os.path.dirname(p)) for p in chain][:1], [os.path.basename(root)])
        merged = load_nearest_agents_md(os.path.join(sub, "x.py"), root)
        # 最近(PKG)在末尾
        self.assertTrue(merged.index("ROOT") < merged.index("PKG"))


class TestSkills(unittest.TestCase):
    def test_progressive_disclosure(self):
        loaded = {"n": 0}

        def body():
            loaded["n"] += 1
            return "FULL BODY"

        reg = SkillRegistry()
        reg.register(Skill("db", "数据库迁移技能", triggers=["migration", "数据库"], _loader=body))
        # 清单只暴露元信息，不触发 body 加载
        self.assertIn("db", reg.manifest())
        self.assertEqual(loaded["n"], 0)
        selected = reg.select("需要做数据库 migration")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].load_body(), "FULL BODY")
        self.assertEqual(loaded["n"], 1)


class TestMemory(unittest.TestCase):
    def test_compaction_and_clearing(self):
        cw = ContextWindow(compact_trigger_tokens=50)
        for _i in range(5):
            cw.add("user", "x" * 100, kind="tool_result")
        # 触发过 compaction（消息被压缩成更少条）
        self.assertTrue(any(m["kind"] == "compaction" for m in cw.messages))
        cleared = cw.clear_tool_results(keep_last=1)
        self.assertGreaterEqual(cleared, 0)

    def test_cross_session_memory(self):
        cw = ContextWindow()
        cw.remember("arch", "微服务")
        self.assertEqual(cw.recall("arch"), "微服务")


class TestCodeIndex(unittest.TestCase):
    def test_index_and_dependents(self):
        idx = build_index("src/aiforge")
        self.assertTrue(idx.search("Supervisor"))
        self.assertTrue(len(idx.symbols) > 20)


if __name__ == "__main__":
    unittest.main()
