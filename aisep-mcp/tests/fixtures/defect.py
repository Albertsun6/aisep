"""先行测试（测试先于实现）的标记方式，替代 fixtures.pending 的做法（评估 TEST-2 / PROG-8）。

pending 把「被测函数不存在」「调用链里抛 NotImplementedError」都变成 XFAIL，实现被删或改名时 CI 照样退出 0。
这里反过来：

- 用 `open_defect(...)` 标记的测试是 `xfail(strict=True, raises=Defect)`。
- 只有测试里**明确识别出那条缺陷**的地方才 `raise Defect`（经 `expect`）；被测函数不存在、改名、抛别的异常、
  夹具前提不成立，都是普通异常或普通 assert，按失败报出，不会变成 XFAIL。
- 实现合入后测试会通过，strict 让 XPASS 变成失败：**实现方必须在同一个 PR 里摘掉标记**，此后这条测试就是普通回归测试。
"""
import pytest


class Defect(AssertionError):
    """测试明确认出了被标记的那条缺陷（只有它会被 open_defect 的 xfail 接住）。"""


def expect(cond, msg):
    if not cond:
        raise Defect(msg)


def open_defect(line, ids):
    """line：负责实现的那条线（如 "L4-B"）；ids：评估里的缺陷编号。"""
    return pytest.mark.xfail(strict=True, raises=Defect,
                             reason=f"{line} 未实现（{ids}）；实现合入时摘掉这个标记")
