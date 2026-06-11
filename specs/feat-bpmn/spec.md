# feat-bpmn — BPMN 业务流程工作台(bpmn-js 集成,双向交互)

status: active
目标:以 bpmn-js(bpmn.io,v18.18.0)为内核,给项目一个统一的**流程图工具**——核心场景是**业务流程分析**:需求/架构阶段把业务流程画成可编辑、可存档、可追溯的 BPMN 2.0 图。三个方向的"双向":①图↔文件(编辑后存回 `.bpmn`)、②图↔XML 源码联动、③图↔项目状态(管线门禁着色 + 点击只读下钻)。

## 背景与范围
- 痛点:现有流程图(Mermaid)是只读静态图——不能编辑、不能存档复用、更不能承载业务流程分析(BPMN 2.0 语义:泳道/网关/事件);做企业软件的需求分析需要标准建模工具。
- 范围内(两个里程碑,M1 可独立交付):

### M1 — 通用工作台(双向①②)
- `docs/bpmn-workbench.html` 单页,零构建、断网双击可开(bundle vendor 进 repo)。
- 新建/打开(文件选择器或拖放)/编辑 BPMN 图。
- 保存:**特性检测**(`'showSaveFilePicker' in window`,非 UA 嗅探)→ 支持则 File System Access API 直写本地 `.bpmn`(save picker 类型限定 `.bpmn`);不支持(Safari/Firefox)自动降级为下载——新建图默认名 `diagram.bpmn`,打开过的沿用原名;降级对用户可见(按钮文案)。
- XML 源码视图与画布**双向联动**:改图 → XML 刷新;贴 XML → 画布重渲染。

### M2 — 项目状态接入(双向③)
- **③的"双向"定义**(与①②的读写双向语义不同,显式确认):状态数据流入图(着色/徽章)+ 图上交互流回状态查询(点击节点**只读**下钻门禁记录);**写回项目状态被安全条款显式排除**。
- 交付物一:`docs/flows/sdlc-pipeline.bpmn`——六阶段管线的 BPMN 建模,元素 id 按下方映射表(机器可对账)。
- 交付物二:新 CLI 子命令 `python -m aiforge bpmn-status`(只读导出,数据源同 project-dashboard:审计流水)→ 生成 `docs/flows/sdlc-status.js`,内容为 `window.AIFORGE_STATUS = <严格 JSON>`。**机制决策**:file:// 页面 fetch 本地 JSON 会被 CORS 拦截,故用相对 `<script src>` 加载的 JS 包裹——仍零外呼、零后端;导出器必须严格 JSON 序列化并转义 `</script>` 与 `<!--`。
- 状态 schema(字段 allowlist,导出端唯一字段集):`generated_at` / `stages.<gate>` = `{gate, decision, created_at, feature_id}`(每 gate 取审计流水 timestamp 降序首条,相等取文件中后出现者)/ `pipeline_xml`(嵌入管线 XML,项目模式零步加载)。
- 映射表(冻结,验收据此对账):

| BPMN 元素 id | 阶段 | 数据源 gate |
|---|---|---|
| `stage-requirements` | 需求 | gate-spec |
| `stage-architecture` | 架构 | gate-trace |
| `stage-decompose` | 拆解 | —(无门禁,中性显示) |
| `stage-implement` | 实现循环 | —(无门禁,中性显示) |
| `stage-judge-commit` | 判定+提交 | gate-judge / gate-commit |
| `stage-integrate` | 集成 | —(CI 权威,中性显示) |

### 存放与呈现约定(非机器强制)
- 特性级业务流程放 `specs/<feature-id>/flows/*.bpmn`(随 spec 追溯,P2);项目级放 `docs/flows/*.bpmn`。
- **此后项目内新增流程图默认用 BPMN 呈现**;该约定的落点 = 本特性在 `AGENTS.md` 追加一行约定(文档交付物),不构成机器强制。

### 不做
- 不做流程引擎/执行(不是 Camunda Engine——只建模与分析,不跑流程实例);
- 无后端、不调模型(契约 04);页面不起任何 HTTP 服务;
- 不做多人协同/实时同步/版本对比;
- 不迁移现有 Mermaid 图(dashboard/启动台保留;迁移若要做,另立特性);
- 不引入 npm/构建链(官方预构建 bundle vendor 引入,与现有 docs/*.html 同模式);
- 不引入 properties panel 深度属性编辑(独立包且 license 不同,基本建模不需要;要时另立迭代);
- M2 状态为全局视图(每 gate 最近一条),不做按 feature 过滤(要时另立迭代)。

## 验收标准(Gherkin)

> 每条标注验证载体:**[unittest]** = 仓库 stdlib 可执行测试;**[手动]** = 编号步骤人工执行、逐条可判 pass/fail(可后续自动化)。能下沉 unittest 的已下沉。

### M1 — 通用工作台
1. **建模可证伪** [手动]
   - Given 断网状态下双击打开 `docs/bpmn-workbench.html`
   - When 从 palette 拖入 1 个 Task、1 个 End 事件并连线,把 Task label 改为"审批"
   - Then 导出 XML 含恰好 1 个 `<bpmn:task>`(`name="审批"`)与 1 个 `<bpmn:sequenceFlow>`(sourceRef/targetRef 指向对应元素 id);全程网络面板请求数为 0;`document.fonts.check('1em bpmn')` 为 true(图标字体来自 vendor,离线可渲染)。
2. **零外呼静态探针** [unittest]
   - Given `docs/bpmn-workbench.html`
   - Then 所有 script/link/img 的 src/href 为指向 `vendor/`、`flows/` 的相对路径;源码中无指向绝对 http(s) URL 的 fetch/XMLHttpRequest/sendBeacon/动态 import(xmlns 等命名空间字符串豁免)。
3. **保存:直写与降级** [手动]
   - Given 画布上有图
   - When 点"保存"
   - Then 特性检测支持 → save picker(限定 `.bpmn`)直写;不支持(或在 Chromium 中删除 `showSaveFilePicker` 全局模拟)→ 降级为下载且按钮文案变化;两条路径产物均满足三段判据:① stdlib ElementTree 可解析(well-formed);② 根元素为 BPMN 2.0 MODEL 命名空间下的 `definitions`;③ 喂回 `importXML` 成功且 0 error。
4. **保存目标可见,不写错文件** [手动]
   - Given 经 picker 打开文件 A(持有可写句柄),再经拖放打开文件 B
   - When 点"保存"
   - Then 不会写回 A——替换画布的动作(新建/打开/应用粘贴 XML)使旧句柄失效或保存前显式确认目标;UI 常驻显示当前绑定目标文件名,保存成功提示含文件名;"保存"与"另存为"语义分立。
5. **round-trip 不丢失** [手动,fixture 入库]
   - Given 入库 fixture `specs/feat-bpmn/flows/fixture-order.bpmn`(强制包含:1 个 pool + 2 条 lane + 1 个 exclusive gateway + 1 个边界事件 + 若干带 name 的任务)
   - When 工作台打开 → 不改动直接另存
   - Then `importXML` resolve 且 warnings 为空;产物与源 XML 的元素 id 集合、name 属性集合相等(只断言"不丢失",不断言字节一致——bpmn-js 会重排)。
6. **图→XML 联动(有时限)** [手动]
   - Given 画布与 XML 视图并排
   - When 在画布添加/删除一个任务
   - Then `commandStack.changed` 事件后 ≤500ms 内,XML 视图中 `<bpmn:task` 出现次数相应 +1/−1。
7. **XML→图与容错** [手动]
   - When 在 XML 视图粘贴合法 BPMN XML 并应用 → Then 画布重渲染为该图;
   - When 粘贴非法/残缺 XML 并应用 → Then 错误提示显示(textContent),画布保持上一个有效状态,页面不崩。
8. **未保存防丢** [手动]
   - Given 画布有未保存编辑(dirty 标记)
   - When 打开新文件 / 应用粘贴 XML → Then 出现确认提示,确认后才替换;
   - When 关闭页签 → Then beforeunload 提示。

### M2 — 项目状态接入
9. **导出命令契约** [unittest]
   - Given fixture `gates.jsonl`(各 gate 多条、含 timestamp 相等并列)与 `docs/flows/sdlc-pipeline.bpmn`
   - When 跑 `python -m aiforge bpmn-status`
   - Then 生成 `docs/flows/sdlc-status.js`:`window.AIFORGE_STATUS = <严格 JSON>`;字段恰为 allowlist(generated_at/stages/pipeline_xml);每 gate 为 timestamp 降序首条(相等取后出现者);串内已转义 `</script>` 与 `<!--`;命令只读(不写 specs/审计/代码)。
10. **管线图节点 id 契约** [unittest]
    - Given `docs/flows/sdlc-pipeline.bpmn`
    - Then stdlib 解析后,元素 id 集合包含映射表全部 6 个 stage id。
11. **状态着色与下钻** [手动]
    - Given `sdlc-status.js` 存在
    - When 工作台进入"项目模式"
    - Then 自动加载管线图;有 gate 数据的节点按 decision 着色徽章(approved/rejected/needs_human 三态可区分),无门禁阶段中性显示;点击节点显示该阶段最近门禁记录(gate/decision/时间)。
12. **缺失/损坏降级(枚举)** [手动]
    - Given 三种 fixture:`sdlc-status.js` 不存在 / `AIFORGE_STATUS` 非对象 / 合法对象但缺约定字段
    - When 进入项目模式
    - Then 三者一致:管线图按第 5 条判据正常渲染,徽章区显示"暂无数据",无未捕获异常。

### 安全与合规(按里程碑归属验收面)
13. **XSS——M1 面** [手动]
    - Given `.bpmn` 元素 name/documentation 含哨兵 payload `<script>window.__pwned=1</script>` 与 `<img src=x onerror="window.__pwned=1">`
    - When 打开渲染、查看 XML 视图、触发非法 XML 错误提示、显示文件名
    - Then 全程 `window.__pwned === undefined`;凡进自绘 DOM 的面(XML 视图、错误提示、文件名)以转义文本呈现(textContent 含字面 `<script>`)。
14. **XSS——M2 面** [手动]
    - Given 状态数据字段含同款哨兵 payload
    - When 徽章/详情面板渲染(overlays HTML)
    - Then `window.__pwned === undefined`;徽章/详情文本先转义再拼入。
15. **水印合规探针** [手动 DOM 探针]
    - Given 工作台各布局状态(M1:XML 视图展开;M2:徽章与详情面板打开)
    - Then DOM 存在 `.bjs-powered-by` 且 computed style 可见(非 display:none / visibility:hidden / opacity:0 / 移出视口),对其几何中心 `document.elementFromPoint()` 命中该元素或其后代(未被遮挡)。
16. **vendor 完整性** [unittest]
    - Given `docs/vendor/bpmn-js@<version>/`
    - Then 存在 modeler JS、diagram-js.css、bpmn-js.css、bpmn-font(css + 字体文件)、LICENSE 文本与 `SHA256SUMS`;逐文件重新哈希与 SHA256SUMS 一致;`bpmn-workbench.html` 所有资源引用为指向 vendor 的相对路径(与第 2 条联动)。
17. **门禁扫描器的 vendor 哈希验证豁免(fail-closed)** [unittest](2026-06-12 修订新增:minified bundle 含 `eval(`/`exec(` 字样,静态扫描 needs_human 且 CI 不消费本地 ack → CI 永红;经用户裁决改扫描器)
    - Given gate-judge 的 diff 扫描遇到 `docs/vendor/**` 下的文件块
    - Then **仅当**该文件当前内容的 sha256 与同 vendor 目录 `SHA256SUMS` 中的条目完全一致才跳过扫描;以下情形一律照扫:哈希不符 / SHA256SUMS 缺失或无该条目 / 文件是 SHA256SUMS 本身 / 路径不在 docs/vendor/ 下 / 块带可执行 bit / 未提供 repo 根(纯文本调用)。
    - **诚实边界与来源锚(2026-06-12 异构评审修订)**:哈希只证"与入库清单自洽",不证来源。来源的**机器锚** = CI `vendor-provenance` 步:vendor 路径有变更时,将每个 `docs/vendor/<name>@<version>/` 包与 npm registry 官方 tarball 逐字节对账(先验 tarball sha512 integrity,再要求每个 vendored 文件的 sha256 出现在官方 tarball 文件集中),不符 → CI 红(fail-closed,含网络不可达)。人审锚 = P5 超限人审 + plan 供应链记录 + PR approval。豁免判定的内容源 = git index(与磁盘分叉即拒);路径组件硬校验拒 `..`/绝对路径。

## 非功能清单(P6)
- **License 合规(硬约束)**:bpmn.io license 要求 "Powered by bpmn.io" 水印**不得移除、不得遮挡**(不分商用/内部);UI 布局必须为水印保留不被覆盖的位置(验收 15);properties panel 未来若引入,注意其为 MIT(license 与本体不同)。
- **供应链**:预构建 bundle vendor 进 `docs/vendor/bpmn-js@<version>/` 锁定版本(modeler ~0.56MB + assets ~0.4MB,全套 <1MB);**获取时与 npm registry tarball 的 integrity(sha512)比对,核对过程记录在 plan.md**;vendor 目录旁落逐文件 `SHA256SUMS`,unittest 复核防篡改(验收 16);license 文本随 vendor 保留。
- **安全**:① 页面零网络请求(验收 1/2)、无遥测、无 secret;② 唯一写路径 = 用户显式手势选择的 `.bpmn` 文件(save picker 限定类型)或浏览器下载,句柄生命周期受验收 4 约束;页面自身不写 specs/审计/代码;③ XML 只交给 `importXML` 解析,**禁止** innerHTML 注入文件内容;状态数据只允许严格 JSON 语义(script 包裹由导出器严格序列化并转义),**禁止** eval/Function;④ 凡进自绘 DOM 必转义,显式点名四个面:XML 视图、错误提示(一律 textContent)、文件名、overlay 徽章/详情;⑤ M2 导出端沿用 project-dashboard 只读纪律(不调模型、字段 allowlist)。
- **浏览器面**:直写文件仅 Chromium 105+(Chrome/Edge);降级判定基于特性检测(非 UA 嗅探,可在 Chromium 中模拟验证);Safari/Firefox 功能不缺失、只多一步,降级对用户可见。
- **错误处理**:非法 XML / 文件读失败 / 状态缺损 → 显式提示或"暂无数据",页面不崩、画布不丢当前图(验收 7/12);未保存更改有 dirty 防丢(验收 8)。
- **性能**:设计支撑数百元素的流畅编辑;打开超过 5MB 的文件先提示确认;合法但病态的大图不静默假死(给出提示或保持可交互)。
- **可观测**:保存/打开/降级路径在页面内有状态提示(成功/失败/降级原因 + 目标文件名)。

## 追溯
- P1/P2:`.bpmn` 业务流程随 `specs/<feature-id>/flows/` 存档,与需求同链追溯;管线图节点 id 契约(验收 10)使状态↔图可机器对账。
- P6:license 水印(验收 15)、供应链完整性(验收 16)、XSS(验收 13/14)均为**显式验收条目**,不靠自觉。
- 契约 04:工作台与 `bpmn-status` 导出均不调模型;契约 01:本页为本地工具,不构成强制层。
- P9:bpmn-js 经 vendor 锁版本接入;M1 工作台不依赖 CLI(无 M2 也独立可用)。
