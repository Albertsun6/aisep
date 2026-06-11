# feat-bpmn · M1 验收执行记录(T4)

> refs: ../spec.md(验收 1-8/13/15)
> 执行:2026-06-12,agent 经 chrome-devtools-mcp(v1.2,--experimentalVision)**亲手操作真实 Chrome**,
> file:// 直开 worktree 页面;每条判据可证伪、有原始返回值。另有 stdlib unittest 静态半边(tests/)与
> headless 烟测(commit 28c9d0a 信息)在前。

## 执行方式与诚实边界(先读)
- **真实输入**:palette 点击-放置、坐标双击、键盘输入"审批"、global-connect 连线——全部 CDP 受信鼠标/键盘事件,非 API 直调。bpmn-js 的 palette 原生交互模型即"点工具→点画布放置",**未执行"按住-拖动"手势**(MCP 无该原语;放置结果以 XML 断言为准)。
- **文件选择器 mock**:`showSaveFilePicker`/`showOpenFilePicker` 为系统原生对话框,任何自动化都无法操控;按 spec 验收 3 明文允许的方式以 duck-typed 句柄模拟,**测的是页面自身的保存/打开/句柄生命周期逻辑**;真实对话框弹出行为属浏览器职责。
- **工具痕迹两则(页面无责,已插桩复跑排除)**:① evaluate 的 dialogAction 会留下浏览器层悬挂对话框,污染后续点击时序——曾造成"拒绝后画布被替换"的假象,经 confirm 插桩干净复跑证明页面行为正确;② 一次 CDP 超时令虚拟鼠标左键滞留按下,后续 click_at 误触发按钮——改走 DOM 事件路径完成。

## 逐条结果

| 验收 | 判据(可证伪) | 结果 | 原始证据 |
|---|---|---|---|
| 1 建模 | 恰 1 个 `<bpmn:task>` 且 name="审批";恰 1 条 sequenceFlow 且 source=Task/target=EndEvent;`document.fonts.check('1em bpmn')`=true | **PASS** | `{"taskCount":1,"taskNamed":true,"flowCount":1,"flowWiring":{...sourceIsTask:true,targetIsEnd:true},"fontLoaded":true}` |
| 2 零外呼 | 静态探针(unittest TestZeroEgress 4 项)+ file:// 离线加载就绪 | **PASS** | 134 测试绿;页面状态"就绪(直写模式)" |
| 3 保存直写 | 特性检测命中→按钮文案"保存";写入 1 次+close;状态含文件名;产物三段判据:DOMParser well-formed / 根=BPMN MODEL ns definitions / 喂回 importXML 0 error 0 warning | **PASS** | `{"status":"已保存到: diagram.bpmn","writes":1,"closed":true}`;`{"importOk":true,"warnings":0}`;`{"wellFormed":true,"rootIsBpmnDefinitions":true}` |
| 4 句柄生命周期 | picker 打开→目标栏带"(直写)";新建(替换画布)后→目标栏**无**"(直写)"(句柄已弃) | **PASS** | 步骤 4 后 `"目标: test.bpmn(直写)"`;新建后 `"目标: diagram.bpmn"` |
| 5 round-trip | 打开步骤 3 产物→"审批"task 与连线完整还原 | **PASS** | `{"taskName":"审批","flowOk":true,"status":"已加载: test.bpmn"}`(注:fixture-order 的 pool/lane round-trip 由 unittest TestFixtures 静态覆盖结构,浏览器侧本记录用自建图验证) |
| 6 图→XML 联动 | commandStack.changed 后 XML 视图刷新(debounce 300ms≤500ms) | **PASS**(实现侧) | 代码路径 + 步骤 1 中 XML 视图内容随编辑变化;精确计时未单测 |
| 7 坏 XML 容错 | 应用非法 XML→错误区 textContent 显示原因;画布保持原图 | **PASS** | `{"errbar":"加载失败(画布保持原图): unparsable content...","taskSurvived":"审批","elementCount":5}` |
| 8 防丢护栏 | dirty 时新建→confirm 弹出;**拒绝**→画布原样(插桩 confirm 返回 false);**接受**→替换且句柄弃 | **PASS** | confirmLog `[{returned:false}→保留, {returned:true}→替换]`;两路径画布状态均断言 |
| 13 XSS(M1 面) | 三个哨兵 payload(script 标签/img onerror/混合实体)经画布渲染+XML 视图后:`window.__pwned`=undefined;label 字面呈现;canvas 内无 script/img 注入;XML 视图保持实体 | **PASS** | `{"pwned":"undefined","labelsLiteral":["<script>window.__pwned=1</script>",...],"scriptTagInjected":false,"imgInjected":false}` |
| 15 水印(M1+M2 最拥挤布局) | `.bjs-powered-by` 存在/computed 可见/视口内/几何中心 elementFromPoint 命中自身(未遮挡)——XML 面板+详情面板**全开**时测 | **PASS** | `{"exists":true,"visible":true,"inViewport":true,"notOccluded":true}` |

## 残余事项(如实)
- 验收 3 的 Safari/Firefox 真机降级与"在 Chromium 删除全局模拟降级"未在本记录执行(特性检测分支已由代码+按钮文案机制覆盖;真机抽查可后补)。
- 验收 6 的 ≤500ms 时限未精确计时(debounce 设 300ms,机制成立)。
- beforeunload 提示(验收 8 后半)未自动化(关页签场景,浏览器原生 UI)。
