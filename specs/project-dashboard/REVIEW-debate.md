# project-dashboard 异构评审辩论记录(2026-06-11)

- **评审者**:cursor-agent(`-p --mode ask`),自报 **GPT-5.5**。
- **verdict**:有条件通过(无 XSS / 无 shell 注入 / _PAGE.format 安全;但健壮性 3 处)→ 全部采纳。
- **重点确认**:HTML 转义到位(feature/audit/contract/commit/数字/时间全过 esc;arch/pipe 是静态 Mermaid 非文件输入);`str.format` 不递归解析参数值,`{}` 不可注入;git subprocess 无 shell=True、有 timeout。

| 严重度 | 意见 | 裁决 | 落改 |
|---|---|---|---|
| 中 | `_read`/`_git` 不捕 UnicodeDecodeError,非法 UTF-8 文件会崩(违反"损坏→不崩") | **接受** | `_read` 用 `errors="replace"` + 捕 OSError/UnicodeError;`_git` subprocess 加 `errors="replace"` + 捕 UnicodeError;`test_corrupt_utf8_does_not_crash` |
| 中 | audit jsonl 行是合法 JSON 但非 dict(`[]`/`123`/字符串)→ `_audit_row.get()` AttributeError | **接受** | `_collect_audit` 加 `isinstance(obj, dict)` 过滤;`test_audit_non_dict_line_skipped` |
| 低-中 | `write_project_dashboard` 的 `out` 无护栏,理论上能写进 specs/.aiforge/src/tests | **接受** | 加 `_PROTECTED_OUT_DIRS` 护栏:输出落受保护目录 → raise ValueError(不靠调用方自觉);repo 外允许;`test_refuses_writing_into_protected_dir` |

验证:落改后 108 测试绿(+3)/ruff 0/arch kept;重生成正常。
