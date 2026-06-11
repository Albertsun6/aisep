# feat-bpmn · plan(architecture)

> refs: spec.md

## 模块划分

### M1 — 通用工作台
1. **`docs/vendor/bpmn-js@18.18.0/`**(第三方资产,锁版本)→ 验收 1(物料半边)/2/16
   - `bpmn-modeler.production.min.js` + `assets/`(diagram-js.css、bpmn-js.css、bpmn-font 全套)+ `LICENSE` + `SHA256SUMS`(逐文件)。
   - 获取:npm registry tarball → 与 registry 公布的 integrity(sha512)比对 → 解包拷入;核对记录填本 plan 附录(见流程注记)。
2. **`docs/bpmn-workbench.html`**(单文件页,内联 JS/CSS,零构建;只引 `vendor/`、`flows/` 相对路径——与验收 2 探针允许面同口径)。页内模块:
   - **Editor 壳** → 验收 1(行为半边):实例化预构建 bundle 全局 `BpmnJS` modeler,link vendor 三组 CSS(diagram-js.css/bpmn-js.css/bpmn-font);palette 拖拽/连线/label 编辑即 bundle 原生能力。
   - **FileIO** → 验收 3/4 + P6 可观测:打开 = `showOpenFilePicker`(可用时)/`<input type=file>`/拖放;保存 = 特性检测 `'showSaveFilePicker' in window` → 直写(types 限定 `.bpmn`),否则 Blob+`<a download>`(新建默认名 `diagram.bpmn`,打开过沿用原名);**特性检测结果驱动保存按钮文案**(直写/下载);保存成功(含文件名)/失败/降级原因写状态栏(一律 textContent);**文件读失败**(picker 拒权/句柄异常/拖放读取失败)→ 错误区提示,画布保持当前图不丢;**句柄生命周期 fail-closed**:新建/打开/应用 XML 任一替换画布动作即置空句柄,下次保存重走 picker;"保存/另存为"分立按钮;状态栏常驻显示绑定目标文件名。
   - **XmlPanel** → 验收 6/7:画布→XML:监听 `commandStack.changed` → debounce(≤500ms 内)`saveXML({format:true})` → 以 textContent 写入;**竞态防护**:saveXML 是异步 Promise,连续编辑可能乱序回写——用单调序号标记每次调用,过期(序号小于最新)的 resolve 直接丢弃;XML→画布:"应用"按钮 → `importXML`;失败 → 错误区 textContent 显示 + 用 `lastGoodXml` 快照重 import 回滚(**不依赖** bpmn-js 失败后自己留着画布)。
   - **DirtyGuard** → 验收 8:`commandStack.changed` 置 dirty;替换画布动作前 confirm;`beforeunload` 提示。
   - **转义纪律** → 验收 13:`esc()` 助手;凡进自绘 DOM(XML 视图/错误区/文件名/状态栏)一律 textContent 或先转义。
   - **WatermarkGuard** → 验收 15:布局为右下角 `.bjs-powered-by` 保留空位,XML 视图/(M2)详情面板靠左/上停靠,CSS 禁止覆盖该区。
   - **PerfGuard** → P6 性能:文件 >5MB **或** 轻量元素计数(字符串扫 `<bpmn:` 标签数)>2000 → 先 confirm 再 import(覆盖"合法但病态的大图"——小文件高元素数也触发)。
3. **fixtures(入库)** → 验收 5/13:`specs/feat-bpmn/flows/fixture-order.bpmn`(1 pool + 2 lane + 1 exclusive gateway + 1 边界事件 + 带 name 任务);`fixture-xss.bpmn`(name/documentation 含哨兵 payload,供验收 13 复现)。
4. **`tests/test_bpmn_workbench.py`**(stdlib)→ 验收 2/16 + 5 的静态半边:
   - 静态零外呼探针:解析 workbench HTML,断言所有 src/href 是指向 `vendor/`、`flows/` 的相对路径,源码无绝对 http(s) 的 fetch/XHR/sendBeacon/动态 import(xmlns 豁免);
   - vendor 完整性:清单文件齐(modeler JS/3 组 CSS/bpmn-font 字体/LICENSE/SHA256SUMS)+ 逐文件重哈希比对;
   - fixture 健全性:ElementTree 解析 fixture-order.bpmn,断言 pool/lane×2/gateway/边界事件存在。
5. **`AGENTS.md` +1 行**(新增流程图默认 BPMN 的约定,非机器强制)→ spec"存放与呈现约定"。

### M2 — 项目状态接入
6. **`docs/flows/sdlc-pipeline.bpmn`**(事实源)+ **`docs/flows/sdlc-pipeline.js`**(入库的备援加载源,`window.AIFORGE_PIPELINE_XML = <严格 JSON 字符串>`,同 `<` 转义纪律)→ 验收 10/11/12:
   - 为什么要 .js 备援:验收 12 要求 `sdlc-status.js` 缺失/缺 `pipeline_xml` 字段时**管线图仍正常渲染**,而 file:// 下 fetch 不可用(取舍 2)——必须有与状态解耦的静态加载源;
   - 防两份事实漂移:`sdlc-pipeline.js` 由 `bpmn-status` 从 `.bpmn` 生成(`--emit-pipeline`,入库提交),`test_bpmn_status.py` 断言两者内容一致。
7. **`src/aiforge/bpmn_status.py`**(新模块,与 project_dashboard 同性质:只读采集+生成)→ 验收 9:
   - `collect_status(repo_root) -> dict`:读 `.aiforge/audit/gates.jsonl`(沿用 project_dashboard 的容错纪律:坏行/非 dict 跳过),每 gate 取 timestamp 降序首条(相等取文件后出现者),字段 allowlist = `{gate, decision, created_at, feature_id}`;**顶层 `generated_at` 在此注入**(与 stages 同源产生);
   - `render_js(status, pipeline_xml) -> str`:`window.AIFORGE_STATUS = ` + 严格 JSON;序列化后把 `<` 全量替换为 `\u003c`(一招同时中和 `</script>` 与 `<!--`,仍是合法 JSON);
   - `write_bpmn_status(repo_root, out=None)`:默认 `docs/flows/sdlc-status.js`;复用 project_dashboard 的保护目录护栏(拒写 specs/.aiforge/src/tests);`sdlc-pipeline.bpmn` 缺失 → 报错退出非 0,**不写半截产物**(fail-closed)。
8. **`cli.py` 加 `bpmn-status` 子命令**(lazy import,守契约 04 import 边界;`--out`;`--emit-pipeline` 见设计点 6)→ 验收 9;产出纪律:`docs/flows/sdlc-status.js` 为生成物**不入库**(.gitignore +1,同 project-dashboard.html 先例),`sdlc-pipeline.js` 为备援源**入库**。
9. **workbench 项目模式**(同一页面,同一 modeler bundle)→ 验收 11/12/14:
   - 静态 `<script src="flows/sdlc-status.js">`(404 容忍 → `AIFORGE_STATUS` undefined → "暂无数据");
   - 双 `<script src>`:`flows/sdlc-status.js`(状态,404 容忍)+ `flows/sdlc-pipeline.js`(管线备援,入库);
   - 入口按钮 → 校验 `AIFORGE_STATUS`(typeof/字段检查,三种缺损同路径降级)→ 管线 XML 取 `AIFORGE_STATUS.pipeline_xml` **缺损时回退 `AIFORGE_PIPELINE_XML`** → `importXML` → 按映射表 `overlays.add` 徽章(approved/rejected/needs_human 三色,文本先 esc 再拼 HTML);状态缺损只降级徽章("暂无数据"),**管线图照常渲染**(验收 12 两个半边都接住);
   - `element.click` → 详情面板(gate/decision/时间,转义)。映射表在页内为常量 `STAGE_GATES`,与测试断言共用同一份事实(spec 映射表)。
10. **`tests/test_bpmn_status.py`**(stdlib)→ 验收 9/10:fixture gates.jsonl(含并列 timestamp)→ 跑导出 → 断言字段 allowlist/排序/`<` 转义/只读(不动 specs 与审计);解析 sdlc-pipeline.bpmn 断言 6 个 stage id 齐;断言入库的 sdlc-pipeline.js 与 sdlc-pipeline.bpmn 内容一致(防漂移)。

### 横切 — 门禁扫描器 vendor 豁免(2026-06-12 修订新增)
11. **`harness.py::code_only_diff` 增 `repo_root` 可选参 + vendor 哈希验证豁免** → 验收 17:
   - 默认 `repo_root=None` = 行为与现状完全一致(纯文本、零豁免,fail-closed);`gate_judge`/`gate_commit` 调用处传入 repo_root 激活;
   - 豁免判定(全部条件齐才跳过):块两侧路径相同且在 `docs/vendor/` 下 / 不是 SHA256SUMS 本身 / 无可执行 bit(沿用既有强制扫规则,优先级最高)/ 同 vendor 根存在 SHA256SUMS 且含该相对路径条目 / 磁盘当前内容 sha256 与条目一致;
   - `tests/test_judge_vendor_exempt.py`(新):豁免命中 / 篡改不符 / SUMS 缺失 / SUMS 本身被改 / 非 vendor 路径 / exec-bit / repo_root=None 七路径全断言(测试内的危险 token 用字符串拼接构造,避免自触发扫描器)。

## 数据流
- **M1**:用户 `.bpmn` →(picker/拖放)→ `importXML` → 画布;画布 → `commandStack.changed` →(≤500ms)`saveXML` → XML 视图;XML 视图 → 应用 → `importXML`(失败 → 错误区 + lastGoodXml 回滚);保存 → 句柄直写 / Blob 下载。
- **M2**:`gates.jsonl` →(`bpmn-status` 只读,allowlist)→ `sdlc-status.js` →(相对 `<script src>`)→ `window.AIFORGE_STATUS` → `importXML(pipeline_xml)` + overlays 徽章;点击 → 内存内状态查询 → 详情面板(转义)。
- **无任何反向写路径**:页面不写项目状态(spec ③双向定义);唯一写 = 用户手势选择的 `.bpmn` / 下载。

## 与现有七层的边界
- workbench 是 `docs/` 交付物,**不进 src/ 七层**;浏览器侧依赖(bpmn-js)是 vendored JS,**Python 零第三方依赖不变**(AGENTS.md 约束仍守)。
- `bpmn_status.py` 归可观测/审计**读取侧**(与 project_dashboard 平级同性质);不 import orchestration/runtime/governance,`.importlinter` 分层不变;不调模型(契约 04,CLI 走 lazy import 同 project-dashboard 模式)。
- 门禁链改动仅限设计点 11(harness.py 的 vendor 哈希豁免,验收 17)与 CI 的 vendor-provenance 步(scripts/verify_vendor_provenance.py,2026-06-12 异构评审修订);quality/governance/runtime 不动。

## 关键取舍
1. **vendor vs CDN** → vendor:离线可用/防 CDN 投毒/license 允许;代价 repo +<1MB → 验收 1/2/16。
2. **script 包裹 JS vs fetch JSON** → file:// 下 fetch 被 CORS 拦,JS 包裹是唯一零后端路径(spec 机制决策的落实)→ 验收 9/11。
3. **单 modeler bundle 共用**(M1 编辑与 M2 项目模式同页同 bundle),不另引 viewer bundle:省 183KB 不值多一份供应链审计面(Simplicity)。
4. **importXML 失败回滚走 lastGoodXml 快照**:不假设库失败后保留画布,行为自己兜底 → 验收 7。
5. **`<`→`\u003c` 全量替换**而非只转义 `</script>`:更短、不可绕过、仍合法 JSON → 验收 9。
6. **句柄 fail-closed**:替换画布即弃句柄,宁可多弹一次 picker,绝不"打开 B 存回 A" → 验收 4。
7. **水印保留区是布局约束而非事后检查**:面板停靠方向在 CSS 层面避开右下角 → 验收 15。

## 影响面 / 红线
- 新增:`docs/bpmn-workbench.html`、`docs/vendor/bpmn-js@<v>/`、`docs/flows/sdlc-pipeline.bpmn`、`docs/flows/sdlc-pipeline.js`(备援源,入库)、`src/aiforge/bpmn_status.py`、2 个测试文件、2 个 fixture;修改:`cli.py`(+1 子命令)、`AGENTS.md`(+1 行)、`.gitignore`(+`docs/flows/sdlc-status.js`)、`specs/feat-bpmn/plan.md`(实现期回填供应链附录,见流程注记)。
- M1 不依赖 M2;M2 缺席时 M1 页面完整可用(项目模式降级"暂无数据")。
- 红线(2026-06-12 修订):门禁链改动**仅限**验收 17 的哈希验证 vendor 豁免(设计点 11,经用户裁决;cursor 异构评审为 T10 必含项),其余门禁/治理/runtime 不动;不引入 Python 第三方依赖;不在页面内发任何网络请求。

## 不做(承 spec)
流程引擎/多人协同/properties panel/按 feature 过滤状态/存量 Mermaid 迁移。

## 已实测假设(探针证据,非声称)
- **file:// 下 File System Access API 可用**(本 plan 的直写保存根基):2026-06-12 本机 Chrome 无头探针实测,`file://` 页面 `isSecureContext:true`、`showOpenFilePicker/showSaveFilePicker in window` 均为 true——特性检测在"双击打开"主场景能命中直写路径。复现:写入探测 HTML 后 `chrome --headless=new --dump-dom file:///tmp/fsaa-probe.html`。注:API **存在**≠权限必然授予(picker 仍需用户手势,验收 3/4 的手动步骤覆盖);授予失败走 FileIO 的"文件读失败"路径。
- **file:// 下相对 `<script src>` 可加载、404 不中断页面**(双 script 备援设计的前提):script 元素 404 只触发 error 事件,后续脚本照常执行,`AIFORGE_STATUS` 保持 undefined → 走降级,(实现期在验收 12 fixture 中复验)。

## 流程注记(供应链记录与 receipt 刷新)
vendor 落地后,本 plan 的附录补"供应链核对记录"(tarball sha512 integrity 值 + 核对命令输出),随后**重跑 gate-trace 刷新 receipt**——receipt 必须反映文档当前哈希,这是纪律内的合法更新(非绕过):gate-commit 会因哈希不符强制重跑,链自洽。

## 附录:供应链核对记录(2026-06-12 实测填写)
- 来源:`https://registry.npmjs.org/bpmn-js/-/bpmn-js-18.18.0.tgz`(registry 元数据 `https://registry.npmjs.org/bpmn-js/18.18.0`)。
- tarball integrity 比对:registry 公布 `sha512-3pTiqc5M+CRtXCvBjRBFEewqNKDnx0ytuCLucvMRfdhes/EuVr4memcsi6ql+q/1RUbycOL9MyfNcgrwSfnA1w==`;本机 `hashlib.sha512` 实测同值——**MATCH**。
- 取材:仅 `dist/bpmn-modeler.production.min.js`、`dist/assets/`(diagram-js.css、bpmn-js.css、bpmn-font css+font 全套)、`LICENSE`,共 10 文件 + SHA256SUMS,856K,目录树保持 dist 原样(CSS 内相对字体路径不破)。
- SHA256SUMS:`find . -type f ! -name SHA256SUMS | sort | xargs shasum -a 256 > SHA256SUMS`,生成后 `shasum -a 256 -c` 全 OK;`tests/test_bpmn_workbench.py` 持续复核(逐文件重哈希 + 无未锁文件 + license 水印条款在 + bundle 含 BpmnJS/bjs-powered-by)。
