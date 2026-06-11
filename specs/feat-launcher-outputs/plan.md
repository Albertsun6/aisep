# feat-launcher-outputs · plan(architecture)

> refs: spec.md

## 模块划分(全部沿用 feat-bpmn 已验证模式,无新机制)
1. **`src/aiforge/launcher_data.py`**(新,与 bpmn_status 平级:只读采集+生成)→ 验收 1/2/3/4:
   - `collect_launcher(repo_root) -> dict`:遍历 `specs/` 一级目录(含 spec.md 者,排除 contracts/_workspace);每特性读 spec/plan/tasks/REVIEW-debate 全文(`errors="replace"`,缺失 null);outputs 只收顶层 `*.md`;gates 只读四 gate allowlist 文件名,字段 `{decision, created_at}`;**每个待读路径先过 `_safe_in_specs()`:`is_symlink()` 或 resolve 不在 specs 根内 → 跳过**(验收 2);顶层注入 `generated_at`。
   - `render_js(data) -> str`:`window.AIFORGE_LAUNCHER = ` + 严格 JSON(`<` → `\u003c` 全量替换,复用 bpmn_status._js_payload 同款实现——直接 import 复用,不复制)。
   - `write_launcher_data(repo_root, out=None)`:默认 `docs/launcher-data.js`;保护目录护栏(拒 specs/.aiforge/src/tests)。
2. **`cli.py` + `launcher-data` 子命令**(lazy import,`--out`;打印路径与特性计数)→ 验收 1 + P6 可观测。
3. **`docs/sdlc-launcher.html` 扩展**(在拷入 worktree 的基线上改)→ 验收 5-9:
   - `<script src="launcher-data.js">`(404 容忍 → 降级);
   - 每张阶段卡片加"本阶段产物"`<details>` 区:**首次展开(toggle 事件)才填充**;按 spec 映射表取数;产物 `<pre>` 与 receipt 行全 textContent;无数据/未知 id → "暂无产物 + 导出命令提示";
   - **既有 `gate.innerHTML = ...` 行重构**:`<code>` 子节点 + textContent 拼装(文案与 `s.gate()` 函数不动);全页移除注入式 API token(含注释措辞)。
4. **`tests/test_launcher_data.py`**(新)→ 验收 1/2/3/4 全部 fixture 反例(evil.png/role.json/screens 子目录/unknown.json/templates/游离文件/repo 外软链/坏 UTF-8/保护目录)。
5. **`tests/test_launcher_page.py`**(新)→ 验收 5:静态探针——相对路径/无网络 API/注入式 API 五 token 全禁零豁免(innerHTML/outerHTML/insertAdjacentHTML/document.write/setHTMLUnsafe)/无 http(s) 字样。
6. **`.gitignore` + `docs/launcher-data.js`**(生成物不入库)。

## 数据流
`specs/**`(只读,symlink 拒)→ `launcher-data` CLI → `docs/launcher-data.js`(本地生成物)→ 相对 `<script>` → `window.AIFORGE_LAUNCHER` → 卡片展开时 textContent 填充。无反向写路径;页面零外呼。

## 七层边界
- `launcher_data.py` 归可观测/审计读取侧(与 project_dashboard/bpmn_status 平级);不 import orchestration/runtime/governance;`.importlinter` 不变;不调模型(契约 04)。
- 复用而非复制:`_js_payload` 从 bpmn_status import(转义纪律单点维护)。

## 关键取舍
1. **数据不入库** vs bpmn 的备援源入库:启动台无"必须渲染的图",无数据走降级即可,不需要备援——少一个入库生成物与防漂移测试(Simplicity)。
2. **首次展开才填充**:数据常驻 window,填充即取即用;不做分页/截断(当前 77KB 量级)。
3. **innerHTML 行重构进范围**:零豁免静态探针 > "不碰旧代码"的字面洁癖——本页要渲染攻击者可控全文,这是评审双 lens 一致裁决。

## 影响面 / 红线
- 新增:1 src 模块、1 CLI 子命令、2 测试文件;修改:`docs/sdlc-launcher.html`(扩展+1 行重构)、`cli.py`、`.gitignore`;启动台本体随本特性首次入库。
- 红线:不动门禁/治理/runtime;不引第三方依赖;页面零网络。

## 任务拆解(blast radius ≤10 文件/≤400 行,每任务一个绿 commit)
- **T1** 导出器 + CLI + 全 fixture 测试(launcher_data.py / cli.py / test_launcher_data.py / .gitignore,4 文件)→ 验收 1-4。
- **T2** 启动台扩展 + innerHTML 重构 + 静态探针(sdlc-launcher.html / test_launcher_page.py,2 文件;页面改动行数可能超 400 → 标注人审:用户 review diff)→ 验收 5 + 6-9 实现侧。
- **T3** 浏览器验收执行(chrome-devtools-mcp,验收 6-9)+ 记录入库(outputs/acceptance.md)。
- **T4** cursor 异构评审 + 落改 + REVIEW-debate.md。
- 依赖:T1→T2(页面引数据)→T3→T4;tasks 不另立文件,本节即拆解(特性小,spec+plan 两文件承载,gate-trace 链 plan→spec 已闭合)。
