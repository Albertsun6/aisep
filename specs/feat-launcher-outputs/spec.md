# feat-launcher-outputs — 启动台展示每阶段产物(+ 启动台本体转正入库)

status: active
目标:SDLC 启动台(`docs/sdlc-launcher.html`)目前只发提示词;本特性让它**把每个阶段的真实产物也展示出来**——输入 feature id 后,各阶段卡片可展开查看该阶段的 spec/plan/tasks 全文、gate receipt 结论、验收记录与评审辩论,人审点"看产物"不再需要翻目录。同时把启动台本体(此前未入库的草稿文件)经本管线**转正入库**(评审裁定:这是交付前置而非夹带——要改它就必须提交它)。

## 背景与范围
- 痛点:有头模式的人审点(确认需求/确认 plan/过目验收)需要看产物,现在用户得自己去 specs/ 翻文件;启动台文件本身也是黑户(2026-06-11 会话产物,从未提交)。
- 数据机制(复用 feat-bpmn 已实测的约束与解法):file:// 页面 fetch 本地文件被 CORS 拦 → 新增只读 CLI `python -m aiforge launcher-data` → 生成 `docs/launcher-data.js`,内容 `window.AIFORGE_LAUNCHER = <严格 JSON>`(序列化后 `<` 全量替换为 `\u003c`);启动台以相对 `<script src>` 加载,404 容忍。**产物不入库**(.gitignore +1,同 sdlc-status.js 先例)——消除"往入库数据文件里塞任意 JS"的攻击面;新克隆无数据走降级路径(验收 7)。
- 数据 schema(顶层 allowlist):`generated_at` / `features.<id>` = `{ spec, plan, tasks, debate, outputs, gates }`:
  - **features 枚举规则**:`specs/` **一级目录中含 spec.md 者**,排除 `contracts/`、`_workspace`(templates/examples/游离文件因无顶层 spec.md 自然排除);
  - 文本字段(spec/plan/tasks/debate)= 对应文件全文(UTF-8,坏字节替换;缺失 → null);
  - **outputs 只收 `outputs/` 顶层(不递归)的 `*.md`**——子目录(如 screens/ 截图)、二进制、其他扩展名(角色 JSON)一律不入数据;
  - **gates key 钉死为四 gate allowlist**(gate-spec/trace/judge/commit),每条只取 `{decision, created_at}`(不嵌 argv/inputs/路径);陌生 receipt 文件名不进数据;
  - **symlink 防穿越(评审 High)**:任何待读路径 `is_symlink()` 或 resolve 后不在 specs 根内 → 跳过降级为 null——导出器读的必须是入库形态的内容,不许经软链读到 repo 外(否则外部 PR 可借本地导出外泄 `~/.ssh` 等)。
- 阶段 ↔ 产物映射(展示用,冻结):

| 阶段卡片 | 展示产物 |
|---|---|
| 需求 | `spec.md` 全文 + `gate-spec` receipt 结论 |
| 架构 | `plan.md` 全文 + `gate-trace` receipt 结论 |
| 拆解 | `tasks.md` 全文 |
| 实现循环 | `outputs/` 顶层每个 `*.md` 一个独立折叠项 |
| 判定+提交 | `REVIEW-debate.md` 全文 + `gate-judge`/`gate-commit` receipt 结论 |
| 集成 | 固定提示(集成产物 = merge commit 与 CI,页面不展示) |

- **范围内的既有代码重构(评审裁决,双 lens 一致)**:现有页面 `gate.innerHTML = s.gate(esc(id))` 行重写为 DOM 构建(createElement/textContent + `<code>` 子节点),**全页移除 HTML 注入式 API**——零豁免的静态探针是本页即将渲染攻击者可控全文的前提,不打折。
- **不做**:
  - 不做 Markdown 渲染(产物以 `<pre>` 等宽文本呈现;美化另立迭代);
  - 不做实时刷新(重跑 `launcher-data` 才更新);
  - 无后端、不调模型(契约 04)、页面零外呼;
  - **不改提示词文案与生成函数**(收窄后的范围栅栏:gate 行的渲染方式重写在范围内,文案与 `s.prompt/s.gate` 逻辑不动);
  - 不做截断/分页/虚拟滚动(当前全部特性 markdown 约 77KB,不值得;页面侧唯一约束:产物 `<pre>` **首次展开才填充**);
  - 不展示 `specs/contracts/`、`_workspace`、outputs 子目录与非 md 文件。

## 验收标准(Gherkin)

> 载体:**[unittest]** = stdlib 可执行;**[浏览器]** = chrome-devtools-mcp 亲手操作实测(模式已沉淀)。

1. **导出契约** [unittest]
   - Given 临时 repo:`specs/feat-a/`(spec/plan/tasks + outputs/{a.md, evil.png, role.json, screens/x.png} + gates/{gate-spec.json, gate-trace.json, unknown.json})、`specs/contracts/`、`specs/_workspace`、`specs/templates/`(无顶层 spec.md)、`specs/README.md`(游离文件)
   - When 跑 `python -m aiforge launcher-data`
   - Then 生成 `docs/launcher-data.js`:前缀恰为 `window.AIFORGE_LAUNCHER = `,余下部分可被 `json.loads` 严格解析(任意 JS 注入即红);顶层字段恰为 allowlist;`features` 恰含 feat-a(contracts/_workspace/templates/README.md 均不入);outputs 恰含 a.md(png/json/子目录不入);gates 恰含两条已知 receipt 且字段恰为 {decision, created_at}(unknown.json 不入);JS 串内无字面 `<`;命令只读(specs 内容与 mtime 不变)。
2. **symlink 防穿越** [unittest](评审反例)
   - Given `specs/feat-a/outputs/evil.md` 是指向 repo 外文件(含哨兵串)的软链
   - When 导出
   - Then 哨兵串**不出现**在产物任何位置,对应条目降级(不入 outputs),命令不崩。
3. **缺失/损坏降级** [unittest]
   - Given 特性目录只有 spec.md(无 plan/tasks/outputs/receipt),或某 `*.md` 含非法 UTF-8
   - When 导出
   - Then 缺失字段为 null/空对象;坏字节以替换字符呈现(仅限 `*.md` 自身);退出码 0。
4. **保护目录护栏** [unittest]
   - When `--out` 指向 specs/.aiforge/src/tests → Then 拒绝(ValueError),同先例。
5. **零外呼与注入 API 静态探针** [unittest]
   - Given `docs/sdlc-launcher.html`
   - Then 所有资源引用为相对路径;无 fetch/XMLHttpRequest/sendBeacon/动态 import;**注入式 API token 全禁且零豁免**:innerHTML、outerHTML、insertAdjacentHTML、document.write、setHTMLUnsafe 均不得出现(含注释);整页源码**无 `http://` 与 `https://` 字样**(平坦禁令,现状即满足;未来需豁免再走行级 allowlist 先例)。
6. **阶段产物展示(逐阶段判据)** [浏览器]
   - Given `launcher-data.js` 含 feat-bpmn 真实数据,输入 feature id = feat-bpmn
   - Then 需求区 = spec.md 全文(等宽)+ gate-spec 的 decision/时间;架构区 = plan.md 全文 + gate-trace 结论;拆解区 = tasks.md 全文;实现循环区 = outputs 顶层 `*.md` 逐文件折叠(feat-bpmn 恰 2 项:m1/m2-acceptance);判定区 = REVIEW-debate.md 全文 + receipt 区(feat-bpmn 的 judge/commit receipt 未入库 → 此处按降级"暂无 receipt"验收;**正向展示由 unittest fixture 的合成 receipt 覆盖**,见验收 1);集成区 = 固定提示文案。
7. **无数据/未知 id 降级** [浏览器]
   - Given `launcher-data.js` 不存在,或输入 id 不在数据里
   - Then 产物区显示"暂无产物"与导出命令提示,页面不崩,提示词功能照常(按验收 8 判据)。
8. **提示词功能不回归(可证伪)** [浏览器]
   - Given 输入 feature id = feat-bpmn
   - Then 6 张卡片 `pre.textContent` 均含 `feat-bpmn` 且不含占位符 `feat-xxx`;点任一复制按钮后剪贴板内容 === 该卡 `pre.textContent`;gate 提示行含该 id 的命令且 `<code>` 样式仍在(重构后防回归)。
9. **XSS(全字段面)** [浏览器]
   - Given 数据中以下位置**同时**植入哨兵(`<script>window.__pwned=1</script>` / `<img src=x onerror=...>`):spec 全文、outputs **文件名 key**、feature id key、receipt decision 字段、generated_at
   - When 展示各阶段产物与数据生成时间
   - Then `window.__pwned === undefined`;全部以字面文本呈现;页面无注入节点(`script/img` 计数为 0)。

## 非功能清单(P6)
- **安全**:① 导出端只读 + 输出护栏 + symlink 防穿越(验收 2/4);② receipt/gates 双 allowlist(字段与 key);③ 页面动态内容一律 textContent,注入式 API 全禁零豁免(验收 5);④ `<` 全量转义在导出端;⑤ 零网络、无 secret;产物不入库,新增暴露面为零(导出会把本地未提交的 specs 草稿写进本地产物——与 dashboard 先例同性质,产物不入库故不扩散)。
- **错误处理**:文件缺失/损坏/软链 → 字段降级,导出不崩;页面无数据 → 显式提示。
- **性能**:当前量级直载(约 77KB);页面侧首次展开才填充 `<pre>`;超大场景的告警/截断属未来迭代,本期不做(Simplicity)。
- **可观测**:导出命令打印输出路径与特性计数;页面产物区显示 generated_at(转义,验收 9 覆盖)。

## 追溯
- P2:阶段 ↔ 产物映射让人审点直接对着追溯链产物做确认。
- P6:XSS 全字段面/只读/软链/降级均为显式验收条目。
- 契约 04:导出器不调模型;契约 01:本页为本地工具,不构成强制层;契约 08:outputs 的角色 JSON 不展示(只收 *.md),与该契约的落盘约定不冲突。
- 启动台本体经本特性转正:此前为未入库草稿(2026-06-11),随本特性提交并纳入管线纪律。
