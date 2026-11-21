# 临时：证伪验证用，确认某一分片失败时必需检查 pytest 为失败。下一个提交删除本文件。
def test_ci_canary_must_fail():
    assert False, "deliberate failure for CI falsification"
