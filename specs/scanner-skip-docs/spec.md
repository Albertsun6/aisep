# scanner-skip-docs — 静态风险扫描只跳过"确定纯文档",可执行面一律扫

status: active
目标:`gate-judge` 的静态风险扫描(StaticRiskScanner)按文件类型分流——**只**跳过确定不会被执行的纯文档(.md/.txt 等),其余(代码、配置、HTML/SVG、CI workflow、可执行 bit 文件、未知/无后缀)**一律仍扫**,消除"纯文档里写 eval/os.system 教学示例反被拦"的误报,**同时不降低对可执行面的安全保证**。

## 背景与范围
- 现状:`judge_diff` 把整段 `git diff` 喂给扫描器,不分文件类型;纯文档里引用危险模式被当风险命中(误报)。
- 范围内:在 diff 层按文件分块,**仅**跳过极窄的"确定纯文档/图片"后缀白名单;**executable bit 强制扫描**(覆盖后缀豁免)。
- **不做**:不豁免任何可执行/可含脚本/配置类文件(经异构评审,2026-06-11:.html/.svg 含 `<script>`、.yml/.yaml 是 CI 可执行面、.json/.toml/.cfg 影响执行链——全部保留扫描)。

## 验收标准(Gherkin)
- Given 一段 diff 只在 `.md` 文件里新增了危险调用(如 eval)
  When 跑 gate-judge
  Then 不命中、退出码 0(markdown 不执行)。
- Given 一段 diff 在 `.py` 文件里新增了危险调用
  When 跑 gate-judge
  Then 命中、退出码 2(代码风险照常拦)。
- Given 一段 diff 在 `.yml`(如 .github/workflows 下)里新增危险调用
  When 跑 gate-judge
  Then 仍命中、退出码 2(CI workflow 是可执行面,不豁免)。
- Given 一段 diff 在 `.html` 文件里新增危险调用(如 `<script>` 内)
  When 跑 gate-judge
  Then 仍命中、退出码 2(HTML 含可执行脚本,不豁免)。
- Given 一个 `.md` 文件被设为可执行(new file mode 100755,带 shebang)
  When 跑 gate-judge
  Then 仍命中、退出码 2(executable bit 覆盖后缀豁免)。
- Given 一段 diff 在未知后缀或无后缀文件里新增危险调用
  When 跑 gate-judge
  Then 仍命中、退出码 2(fail-closed:不确定的当代码扫)。

## 非功能清单(P6)
- 安全(**核心**):缩面改动必须 fail-closed 且极保守——跳过白名单**只含确定不执行的纯文档/图片**(.md/.markdown/.rst/.txt + 常见图片二进制);其余一律扫;executable bit 强制扫;rename 两侧都在白名单才跳;diff 解析失败保留(当代码扫)。
- 错误处理:mode 行/路径解析不出 → 保守保留;
- 可观测:跳过的文件不影响 receipt 结构;
- 限流/审计:N/A。
