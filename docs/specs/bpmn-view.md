# BPMN 只读出图：`bpmn:Process` → BPMN 2.0 XML（含 BPMNDI）

- 实现：`aisep/diagram_bpmn.py`，CLI `tools/aisep.py diagram --process <IRI> [-o OUT.bpmn]`、`--list-processes`。
- 验收：`tests/acceptance/test_diagram_bpmn.py`（期望值来自独立 SPARQL，配变异对照与 bpmn-moddle 读入校验）。
- 来源：2026-11-27 的选型调研（仓库外的协调笔记，本文是它的精简定稿；调研里的版本号、日期按当日 npm 记录）。
- 新铸 IRI：0。`targetNamespace` 用已有的模型 IRI，元素 `id` 用已有 IRI 的本地名。

## 1. 输出形态

后端只给**标准 BPMN 2.0 XML（语义部分 + BPMNDI 坐标）**，这一阶段不出 SVG。前端将来交给 bpmn-js 的 `NavigatedViewer` 只读显示（只能平移缩放），将来 `model_render_view` 返回时带 `format: "bpmn-xml"`，ArchiMate、C4 照旧是 SVG。

理由：BPMN 记法（任务图标、事件环、网关标记、默认流斜杠）由标准渲染器画，不再自造一套；同一个 `.bpmn` 能拿到 Camunda Modeler、Signavio 等工具里打开；后端出 SVG 只能无头浏览器截图（重、字节不稳定）或自写渲染器，都不划算。坐标就在 Python 里，以后真要静态图可以加 `--format svg`，不影响 XML 契约。代价是前端要引入 bpmn-js（锁版本），并保留 bpmn.io 水印（许可条件）。

## 2. 一张图的边界：一个 `bpmn:Process`

一张 BPMN 图对应一个 `bpmn:Process`，成员就是它的 `bpmn:flowElements`，不声明 `arch:Diagram`。

- BPMN 语义自带边界：一个流程加它的 `flowElements`，对应 XML 里一个 `<process>` 和一个 `BPMNPlane bpmnElement=<流程>`，这也是 bpmn.io、Camunda 的默认单位。成员关系由记法闭合，不需要像 ArchiMate 声明视图那样再推“两端都在视图里的关系”。
- 视图标识就是流程 IRI。给视图列表的建议形态：`{kind: "bpmn-process", iri: <流程 IRI>, label: <prefLabel>}`。
- 将来模型能写 `bpmn:Collaboration`（见 §5）后，再加“一张图 = 一个协作，各参与者的流程画成泳池，消息流跨池”。

**与 ADR-003 视图原语的关系**：ADR-003 把模型底层定为元素、关系、视图三原语，视图原语在模型里落成声明的 `arch:Diagram`（成员用 `arch:inView` 指向它，`docs/metamodel-spec.md`）。BPMN 图不新增一种原语，也不改这条：它和 `aisep.py diagram --viewpoint`（ArchiMate 视点投影）、C4 的 SystemContext 等按范围推出的视图一样，是**从模型算出来的派生视图**，图的成员由已有的元素和关系（这里是 `bpmn:flowElements`）决定，图本身不入库，坐标也不入库（每次重算）。不为每个流程声明一个 `arch:Diagram`，是因为那要给每个流程多铸一个 IRI，且和 BPMN 自带的边界重复、要两处同步。以后若有人确实需要“只画流程的一部分”或给 BPMN 图挂视点，再按 ADR-003 声明 `arch:Diagram`；是否需要一条新 ADR 把“派生视图不声明 `arch:Diagram`”写成通则，留给 Albert 定，本文只做说明。

## 3. 映射（模型 → XML）

| 模型 | XML |
|---|---|
| `bpmn:Process`，`bpmn:processType`、`bpmn:isExecutable` | `<process id processType isExecutable>`，`name` 取 `skos:prefLabel`（zh 优先） |
| 开始、结束、中间捕获/抛出事件；`bpmn:isInterrupting`（只在开始事件上） | `startEvent` 等同名小写元素；`isInterrupting` 属性 |
| `Task`、`UserTask`、`ServiceTask`、`SendTask`、`ReceiveTask`、`ManualTask`、`ScriptTask`、`BusinessRuleTask`、`CallActivity` | 同名小写元素 |
| 五种网关，`bpmn:gatewayDirection`、`bpmn:default` | 同名小写元素，`gatewayDirection`、`default` 属性 |
| `bpmn:SequenceFlow`（限定关系，`arch:source`/`arch:target`） | `<sequenceFlow sourceRef targetRef name>`，节点里补 `<incoming>`/`<outgoing>` |

- **id 与 IRI**：`id` = IRI 本地名，`targetNamespace` = 流程 IRI 去掉本地名的部分（规范 §3 下就是模型 IRI），`targetNamespace + id` 还原 IRI。成员不在这个命名空间时照画，但打 `[Warning]`，说明它的 id 还原不回原 IRI。
- **id 的字符**：XML 要求 `id` 是 NCName；bpmn-moddle（bpmn-js 读入用的解析器）更严，只认 `^[a-z_][\w-.]*$`（不区分大小写，JavaScript 的 `\w` 只含 ASCII）。所以 `审核` 这样的本地名虽是合法 NCName，bpmn-js 读入时会报 `illegal ID` 并丢掉这个元素。实现按两者的交集判定：`[A-Za-z_][A-Za-z0-9_.-]*`，不符合的报 `[Violation]`、不写文件（验收里有 moddle 对照证明这条限制是真的）。现有模型的本地名都符合。
- **文本**：名称都写在属性里。`< & " ' >` 按实体转义；制表、换行、回车写成字符引用 `&#9;` `&#10;` `&#13;`，否则任何 XML 解析器都会把属性值里的它们规范化成空格，名称不能逐字往返；其他 XML 1.0 不允许的字符（C0 控制字符、U+FFFE/FFFF 等）报 `[Violation]`，与写工具拒绝控制字符的口径一致（`docs/mcp-interface.md` §5.2、§5.12）。
- **不导出**：`arch:inModel`、批准记录、`skos:altLabel`、`arch:Refines` 等跨记法关系（BPMN 没有对应物）。`skos:definition` 可映射成 `<documentation>`，暂不做。

## 4. 不支持的结构：打 `[Warning]`，语义和 DI 都不写

不静默丢弃。下面每一项各打一条 `[Warning]`，点名 IRI，退出码仍为 0：

- 不能画的成员：泳道（`laneSets`/`lanes`）、子流程、数据对象、未定型或不是模型成员的成员等；
- 端点不是本图已画节点的顺序流；
- 两端都已画、但没列在本流程 `flowElements` 里的 BPMN 关系（如漏列的 `SequenceFlow`）；
- 流程、已画节点、已画顺序流上其他的 `bpmn:` 语句：事件定义（`eventDefinitions`）、工件（`artifacts`，如 TextAnnotation）、条件表达式（`conditionExpression`）、不在 §3 表里的属性等；
- `default` 指向未画的顺序流。

DI 和语义同进同出，避免 bpmn-js 报“有语义无 DI”。

## 5. 布局与选型

- 布局复用 `tools/elk` 已锁版本的 elkjs（与 ArchiMate、C4 出图同一条管线）：`layered`、方向 RIGHT、正交连线、`randomSeed=1`、`considerModelOrder=NODES_AND_EDGES`；节点尺寸取 bpmn-js 默认（任务 100×80，按名称最多加宽到 200；事件 36×36；网关 50×50）；事件、网关的名称和顺序流标签作为 ELK 标签参与避让；坐标取整。同一模型两次生成字节相同。
- 选它而不选 bpmn.io 的 `bpmn-auto-layout`：1.x 稳定版不排泳道、协作、消息流，分支是网格堆叠；2.0 能力全、承诺逐字节确定，但调研时仍是 alpha。ELK 方案确定、锁版本、零新增运行时依赖，覆盖现有模型的全部元素。
- **重新评估的入口条件**：模型里出现泳道、泳池或消息流（或 G7 白名单放开 `participants`/`processRef`），且 `bpmn-auto-layout` 2.0 发布稳定版。届时用同一套验收跑它，通过就把布局整体换掉，XML 语义部分和接口不变。
- 现有模型写不出协作/泳池、边界事件、嵌套泳道：G7 闭世界规则（`aisep/core.py` 的 `ELEMENT_LINK_OK`）只放行 `flowElements`、`default`、`flowNodeRefs`、`laneSets`、`lanes` 这几个 BPMN 直连属性。要画它们得先改白名单（元模型层面，走合并前评审），不在出图范围内。

## 6. 测试期依赖

`tools/bpmn-check/`：bpmn-moddle，版本与 sha512 钉在 `package-lock.json`，只用于验收的读入校验，不在任何运行路径上。安装见 `AGENTS.md`“环境”一节。
