# scanner-skip-docs 异构评审辩论记录(2026-06-11)

- **评审者**:cursor-agent(`-p --mode ask`),自报 **GPT-5.5**。原文存档 `REVIEW-2026-06-11-cursor.txt`。
- **verdict**:需修(豁免集合过宽,已含真实可执行面)→ 全部采纳后收窄。
- **背景**:本特性把 gate-judge 静态扫描改为"按文件类型分流",首版豁免集合过宽。

## 辩论矩阵(全部接受 — cursor 的安全意见均成立)

| 严重度 | 意见 | 裁决 | 落改 |
|---|---|---|---|
| blocker | `.yml/.yaml` 是 CI 可执行面(`run: python -c 'eval(...)'`/`curl\|sh`/泄 secret),整块跳过=漏扫 | **接受** | 从豁免移除;新增 `test_workflow_yaml_still_scanned` |
| blocker | `.html/.svg` 含 `<script>`+CDN,会在浏览器执行,eval 在 JS 同样是风险 | **接受** | 从豁免移除;新增 `test_html_with_script_still_scanned`/`test_svg_still_scanned` |
| major | executable bit:`payload.md` 带 shebang + chmod 755 会被执行,只看后缀漏掉 | **接受** | 解析 `new file mode/new mode`,executable bit 强制扫(覆盖后缀豁免);新增 `test_executable_markdown_forced_scan`/`test_code_only_diff_executable_md_kept` |
| major | `.json/.toml/.ini/.cfg/.lock` 过宽(package.json scripts/pyproject build/tox commands 影响执行链) | **接受** | 从豁免移除;新增 `test_json_config_still_scanned` |
| major | diff parser 对 quoted path/`diff --cc` 覆盖不足,但失败时 fail-closed(保留=误报非漏报) | **接受(确认 fail-closed)** | 保留"解析失败保守保留"语义;edge case 测试覆盖 rename/new file 等 |
| minor | `_EV`/`_SYS` 拼接技巧可接受,但测试覆盖不足 | **接受** | 补 yaml/html/svg/json/可执行 md 攻击测试(共 +5),证明可执行面被扫 |

## 收窄结果

豁免白名单从 23 个后缀(含 html/yml/json/svg/cfg…)收窄到 **只 12 个确定纯文档/图片**:
`.md .markdown .rst .txt` + `.png .jpg .jpeg .gif .webp .ico .pdf .m4a`。
其余(代码/配置/HTML/SVG/CI workflow/可执行 bit/未知/无后缀)**一律仍扫**。

## 已知代价(诚实记录)

收窄后,`.html` 不再豁免——`docs/GETTING-STARTED.html` 含 `eval(c)` 教学示例 + `<script>`(Mermaid CDN),提交时 gate-judge 会 needs_human(合法:HTML 可含可执行脚本,scanner 不分展示/script)。这是经评审权衡后**接受的代价**:宁可文档 HTML 的安全示例需人审,不可漏扫真实 HTML/CI 可执行面。该 .html 的提交按 needs_human 走人审通道(契约 07)。
