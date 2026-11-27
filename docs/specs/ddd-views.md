# DDD 视图出图（ContextMap、AggregateDiagram）

渲染核心在 `aisep/diagram_ddd.py`，命令行入口是 `tools/aisep.py diagram`。和 ArchiMate、C4 出图一样：从模型确定性生成 SVG（同一模型出同样的字节），用 ELK layered 自动布局（elkjs 版本钉在 `tools/elk`），不存坐标，只读，不进 gate。关键取舍见文末「设计取舍」。

## 用法

```sh
$PY tools/aisep.py diagram --ddd list --model procurement                  # 列出这个模型能出的 DDD 视图
$PY tools/aisep.py diagram --viewpoint ContextMap --model workbench        # -> build/views/workbench/ContextMap.svg
$PY tools/aisep.py diagram --viewpoint AggregateDiagram --of procurement:quotationBC
                                                                           # -> build/views/procurement/AggregateDiagram-quotationBC.svg
```

`-o OUT.svg` 指定输出路径；末尾可以给模型文件，默认读 `models/**/*.ttl`。`ContextMap`、`AggregateDiagram` 只是命令行里的视图名，不对应视点 IRI。`AggregateDiagram` 的模型取自 `--of` 所在的模型；同时给了 `--model` 而 `--of` 不在该模型里时报用法错误（退出码 2），不静默忽略。

`--ddd list` 只列视图、不出图，同时给 `--view`、`--viewpoint`、`--of` 或 `-o` 时报用法错误（退出码 2），不静默忽略。列表开关写成「记法名 + list」，和 UML 的 `--uml list` 同一写法；BPMN 那边是 `--list-processes`。几个出图 PR 都合并后，再统一成一个列出全部视图的写法，届时另开 PR。

## 上下文映射图（ContextMap，范围是一个模型）

- **画什么**：模型里的 `ddd:BoundedContext`（上层「解空间」）和 `ddd:Subdomain`（下层「问题空间」），以及它们之间的 `ddd:UpstreamDownstream`、`ddd:CustomerSupplier`、`ddd:Partnership`、`ddd:SharedKernel`、`ddd:SubdomainImplementation`。关系类型取最具体的一个，例如客户-供应方不会按上下游来画。
- **记法出处**分三类：
  - 照 Context Mapper 上下文映射图生成器（`context-map-generator` 的 `ContextMapGenerator`）：
    - 线都不带箭头。
    - 上下游关系：源（上游）一端标「U」或「U | OHS, PL」，目标（下游）一端标「D」或「D | ACL」。缩写取角色概念的 `skos:notation`，多个值按字母序排列。
    - 合作关系、共享内核只在线的中部写类型名，两端不标注；客户-供应方也在中部写类型名。类型名用中文（合作关系、共享内核、客户-供应方）。
    - 「实现」画成灰色虚线：借用该生成器团队图里 realizes 的画法。
  - 来自 CML 语法（`[U,S]->[D,C]`）：客户-供应方两端标「U,S」「D,C」，有角色时同样跟在「|」后面。
  - AISEP 扩展（Context Mapper 的映射图里没有）：
    - 有 `ddd:exposedAggregate` 时，中部追加一行「暴露：<聚合名>」（思路来自 Context Mapper 的 PlantUML 组件图，那里把暴露的聚合写在边上）。
    - 子域画成下层「问题空间」，上下文在上层「解空间」。现有模型几乎没有上下文之间的关系，不画子域的话图上只剩几个孤立的框。
- **节点**：限界上下文画成圆角框，标「«限界上下文 · 应用»」这样的构造型。子域画成方框，按核心域、支撑域、通用域填色，同时用文字标出类型。
- 每张图带图例，列出图里出现的节点、线型，以及用到的角色缩写及其全称（取角色概念的 `skos:prefLabel`，直接从画出的角色收集，不从端点文字反切）。「S 供应方，C 客户」只在图里有客户-供应方关系时写。

## 聚合图（AggregateDiagram，范围是一个限界上下文）

上下文画成虚线外框（边界）；它经 `ddd:Ownership` 拥有的每个聚合画成黄色内框；聚合经 `ddd:Containment` 包含的实体和值对象画在聚合框里。实体是直角实线框，值对象是圆角虚线框、淡绿底，两者另有「«实体»」「«值对象»」构造型。根实体（`ddd:RootContainment`）标「«聚合根»」并加黄色左边条。拥有和包含都用嵌套表示，不画线（同 Context Mapper 的 PlantUML 限界上下文类图）。图例里每一项的样式和图里同类框一致。

## 不画的内容与提示

图里只画 DDD 关系，跨记法的连接（代码实现、am4 Realization、`arch:Refines` 等）不画。模型里有、但画不出来或者降级画的信息，一律报 `[Warning]` 并点名 IRI，不会静默丢掉：

| 情形 | 处理 |
|---|---|
| 关系有一端不在本图（例如上下游关系的一端是子域） | 这条关系不画 |
| 合作关系或共享内核带了上游 / 下游角色 | 角色不画 |
| 角色取值不是 IRI（例如字面量），不在对应的 scheme 里，或者没有 `skos:notation` | 这个值不画；是不是 IRI 按 RDF 项的类型判断，取值不拼进 SPARQL |
| 聚合没有根实体 | 照常画，不标「«聚合根»」 |
| 聚合还被别的上下文拥有 | 照常画，同时提示 |
| `ddd:exposedAggregate` 指向的不是聚合 | 不写进标签 |
| 一个成员被同一张图里的两个聚合包含 | 只画在第一个聚合里 |
| 同一个聚合对同一个成员既有 `ddd:Containment` 又有 `ddd:RootContainment` | 不算冲突，画一次并标「«聚合根»」，不提示 |
| 首批没有视图画的 DDD 成员（领域、团队、上下文映射、领域事件、命令、策略、服务、读模型、事件触发） | 在 ContextMap 里逐个提示 |
| 没有任何限界上下文拥有的聚合；不在任何「被上下文拥有的聚合」里的实体、值对象 | 任何聚合图都画不到，在 ContextMap 里逐个提示 |

以下情况报 `[Violation]`，退出码为 1，不写文件：模型里没有限界上下文；`--of` 指向的不是限界上下文；`--of` 指向的上下文没有任何聚合。

验收测试在 `tests/acceptance/test_diagram_ddd.py`，期望值由 SPARQL 独立算出。

## 设计取舍

- **先做 DDD 两张图**：模型里已有子域、限界上下文、聚合和根实体，合法样例 `modules/ddd/tests/valid/context-map-legal.ttl` 覆盖全部战略关系；首批只做上下文映射图和聚合图。
- **不铸 IRI**：视图名只是命令行和代码里的名字，不铸视点 IRI，不改 `modules/`、`models/`。
- **复用而不改动 ArchiMate/C4 出图**：只 import `aisep.diagram` 的 `MARGIN`、`elk_layout`、`f`、`local`、`tw`、`wrap`，`diagram.py`、`diagram_c4.py` 零改动，两者的输出字节不变。
- **布局用 ELK，不用 Graphviz**：仓库已锁 elkjs，Graphviz 要另装二进制；ELK 的边标签参与布局，端点标注交给 `elk.edgeLabels.placement` 的 `TAIL` / `HEAD`。这个选项只是提示，所以验收里有几何断言（U 标注靠近上游框、D 标注靠近下游框）。节点用矩形而不是 Context Mapper 的椭圆：中文要折行，线端也按矩形边验收。
- **只画 DDD 关系**：跨记法的连接不画，和 C4 出图不画 `arch:Refines` 一致。
- **warning 的口径**：只在模型里的信息画不出来或者被降级画时报 `[Warning]`，并点名 IRI；孤立的上下文、没写子域类型这类模型事实不报。`diagram` 只跑 L0，L3 违规的模型也会走到渲染器，所以渲染器对角色取值、聚合根等做防御，不假设模型合法。
- **首批不做**：以 `ddd:ContextMap` 元素为范围的图（模块里没有映射到上下文的成员关系）、团队图（没有团队到上下文的关系类）、事件流视图（事件没有归属到上下文，也没有数据）、Separate Ways 与 Big Ball of Mud（本体没有对应词汇）。
- **借鉴而不复制文字**：记法参考 Context Mapper（Apache-2.0）的生成器源码与 CML 语法；DDD Crew 的材料只借鉴「小图回答具体问题、图带图例」的思路，不引入其文字（规范 §11）。
