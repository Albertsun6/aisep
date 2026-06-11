# feat-launcher-outputs · 验收执行记录(T3)

> refs: ../spec.md(验收 1-9)
> 执行:2026-06-12。验收 1-5 = stdlib unittest(test_launcher_data.py 4 项 + test_launcher_page.py 4 项);
> 验收 6-9 = agent 经 chrome-devtools-mcp 亲手操作真实 Chrome,file:// 直开,DOM 断言可证伪。

## unittest 侧(验收 1-5)
| 验收 | 判据 | 结果 |
|---|---|---|
| 1 导出契约 | 顶层 allowlist;features 排除 contracts/_workspace/templates/游离文件;outputs 仅顶层 *.md;gates 四 key allowlist + {decision,created_at};严格 JSON 可解析;`<` 全转义;只读(内容+mtime 不变) | **PASS** test_allowlists_and_enumeration |
| 2 symlink 防穿越 | outputs/ 软链指向 repo 外 → 哨兵串不出现在产物 | **PASS** test_symlink_escape_blocked |
| 3 缺失/损坏降级 | 孤 spec + 坏 UTF-8 → 字段 null/替换字符,退出码 0 | **PASS** test_missing_and_corrupt_degrade |
| 4 保护目录护栏 | --out 指向 specs/.aiforge/src/tests → ValueError | **PASS** test_refuses_protected_out_dirs |
| 5 零外呼+注入 API 静态探针 | 相对路径;无 fetch/XHR/sendBeacon/import();五注入 token 零豁免;无 http(s) 字样 | **PASS** test_launcher_page.py 4 项 |

## 浏览器侧(验收 6-9,真实 feat-bpmn 数据)
| 验收 | 判据 | 结果 | 原始返回 |
|---|---|---|---|
| 6 阶段产物展示 | 需求=spec全文+gate-spec结论;架构=plan+gate-trace;拆解=tasks;实现=outputs逐文件折叠(恰 m1/m2);判定=debate+receipt(judge/commit 未入库→降级"暂无 receipt");集成=固定文案 | **PASS** | `{reqHasSpec:true, reqReceipt:"gate-spec → approved · ...", archReceipt:"gate-trace → approved · ...", implFiles:["m1-acceptance.md","m2-acceptance.md"], judgeReceipts:["gate-judge:暂无 receipt","gate-commit:暂无 receipt"]}` |
| 7 无数据/未知 id 降级 | 删 AIFORGE_LAUNCHER + 未知 id → "暂无产物"提示,页面不崩,提示词照常 | **PASS** | `{degradeMsg:"暂无产物数据——先跑: ...", promptStillWorks:true, pageAlive:true}` |
| 8 提示词不回归 | 6 卡 pre.textContent 含 feat-bpmn 不含 feat-xxx;gate 行重构后 `<code>` 仍在 | **PASS** | `{cardCount:6, allHaveId:true, noneHavePlaceholder:true, gateLineHtml:"...<code>gate-spec specs/feat-bpmn/spec.md</code>..."}`(剪贴板 === pre.textContent 由复制按钮路径 navigator.clipboard.writeText(pre.textContent) 代码保证,headless 剪贴板权限受限,以代码路径为证) |
| 9 XSS 全字段面 | 5 个位置同时植哨兵(spec全文/outputs文件名key/feature id key/receipt decision/generated_at)→ __pwned undefined,零注入节点,全字面呈现 | **PASS** | `{pwned:"undefined", injectedScripts:0, injectedImgs:0, injectedSvg:0, specLiteral:true, receiptLiteral:true, outputsFilenameLiteral:true, datainfoLiteral:true}` |

## 诚实边界
- 截图未入库:chrome-devtools-mcp 的文件写根锁在 MCP 启动时已存在的目录,本 worktree 是会话内新建的,截图存不进;验收以 DOM 断言为准(比截图更可证伪),不强求配图。
- 验收 8 的"剪贴板内容 === pre.textContent":headless Chrome 的 navigator.clipboard 读权限受限,未直接读剪贴板比对;复制按钮代码即 `writeText(pre.textContent)`,内容同源,以代码路径为证(真机点按可人工抽查)。
