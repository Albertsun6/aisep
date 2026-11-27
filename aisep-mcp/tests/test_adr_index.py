"""docs/decisions.md 索引与 docs/adr/ 下的 ADR 文件一一对应、编号唯一（ADR-034）。"""
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROW = re.compile(r"^\| \[ADR-(\d{3})\]\((adr/[^)]+)\) \|")
FILE = re.compile(r"^(\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def _index_rows():
    lines = (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines()
    return [ROW.match(l).groups() for l in lines if ROW.match(l)]


def test_index_matches_adr_files_one_to_one():
    rows = _index_rows()
    assert rows, "索引里没有 ADR 行"
    files = sorted(p.name for p in (ROOT / "docs/adr").iterdir())
    bad = [f for f in files if not FILE.match(f)]
    assert not bad, f"docs/adr/ 下文件名不是 NNN-<slug>.md：{bad}"
    nums = [n for n, _ in rows]
    dup = sorted(n for n, c in Counter(nums).items() if c > 1)
    assert not dup, f"索引里编号重复：{dup}"
    file_nums = [f[:3] for f in files]
    dup = sorted(n for n, c in Counter(file_nums).items() if c > 1)
    assert not dup, f"docs/adr/ 下编号重复：{dup}"
    for n, link in rows:
        assert link[4:7] == n, f"ADR-{n} 的链接 {link} 与编号不符"
    assert sorted(link[4:] for _, link in rows) == files, "索引与 docs/adr/ 下的文件不一一对应"
    assert nums == sorted(nums), "索引没按编号升序"


def test_adr_file_heading_matches_number():
    for p in sorted((ROOT / "docs/adr").glob("*.md")):
        first = p.read_text(encoding="utf-8").split("\n", 1)[0]
        assert re.match(rf"^## ADR-{p.name[:3]} · \d{{4}}-\d{{2}}-\d{{2}}( · .+)?$", first), f"{p.name} 首行：{first!r}"
