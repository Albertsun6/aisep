# UML 类图出图（`aisep.py diagram --uml`）

实现：`aisep/diagram_uml.py`；验收：`tests/acceptance/test_diagram_uml.py`。管线与 ArchiMate（`aisep/diagram.py`）、C4（`aisep/diagram_c4.py`）相同：Python 从模型选元素，elkjs（`tools/elk`，版本钉死）做 ELK layered 布局，Python 输出 SVG；不存坐标，同一模型生成同样的字节。只读，不进 `gate`。

## 用法

```
$PY tools/aisep.py diagram --uml ClassDiagram --model SLUG [-o OUT.svg] [model files...]
$PY tools/aisep.py diagram --view <arch:Diagram IRI，视点为 umlvp:ClassDiagram> [-o OUT.svg]
$PY tools/aisep.py diagram --uml list [--model SLUG]      # 列出可渲染的 UML 图
```

- 默认输出 `build/views/<slug>/uml-ClassDiagram.svg`；打印 `SUMMARY diagram model=… view=… elements=… relationships=… warnings=…`。
- `--view` 按视点命名空间分派：`c4vp:` 交给 C4，`umlvp:`（`https://meta.linked.archi/uml/viewpoints#`）交给 UML，其余交给 ArchiMate。
- 首批只有类图。`--uml` 后跟其他图种名（如 `UseCaseDiagram`）报 `[Violation]`，退出码 1。
- UML 模块尚未加载 `uml_viewpoints.ttl`，所以声明 `umlvp:ClassDiagram` 视图时 gate 会报 1 条 L3 Warning；加载这一行另开 PR。

## 一张图画什么

- **节点**：断言类型为 `uml:Class`、`Interface`、`DataType`、`Enumeration`、`PrimitiveType` 的模型成员（不含关系资源）。`uml:Component`、`Node`、`Actor`、`UseCase` 等不进类图。投影模式取本模型全部节点；声明视图只取 `arch:inView` 成员。
- **特性**：节点经 `arch:HasPart` 拥有的 `uml:Property`、`uml:Operation`、`uml:EnumerationLiteral`，画进属性栏和操作栏。
- **包**：经 `arch:HasPart` 拥有节点的 `uml:Package` 画成带标签页的框，可嵌套；空包不画。
- **边**：两端都在图中的 Association、Aggregation、Composition、Generalization、Dependency、Abstraction、Realization、InterfaceRealization、Usage。

归属用 `arch:HasPart`：上游的 `uml:namespace` 不是限定关系，过不了 G7。这条约定待 Albert 确认（设计调研 Q1）。

## 记法（UML 2.5.1）

| 项 | 画法 |
|---|---|
| 类 | 名称栏；有特性时加属性栏与操作栏 |
| 抽象类 | 名称斜体，另加 `{abstract}` |
| 接口、枚举、数据类型、基本类型 | 名称上方的关键字 `«interface»`、`«enumeration»`、`«dataType»`、`«primitive»` |
| 属性 | `可见性 [/]名称 [多重性] [= 默认值] [{readOnly}]`；`upper -1` 写 `*`；静态加下划线 |
| 操作 | `可见性 名称()`；抽象斜体，静态加下划线 |
| 泛化 / 实现 | 实线 / 虚线，空心三角在一般端；喂给 ELK 时边反向，一般类排在上面 |
| 聚合 / 组合 | 空心 / 实心菱形在源端（整体端） |
| 依赖、使用、抽象 | 虚线加开放箭头指向 supplier；Usage 标 `«use»`，Abstraction 标 `«abstraction»` |
| 关联 | 实线，无箭头；有 `skos:prefLabel` 时作为线上的名称 |

SVG 元素带 `data-kind`（`element` / `package` / `relationship` / `feature`）、`data-iri`、`data-type`（如 `uml:Class`）、`data-source`、`data-target`、`data-parent`、`data-box`，供前端点选与验收解析。

## 画不出的内容与 warning

上游 UML 词汇没有关联端，也没有属性类型。所以关联两端的多重性、角色名、可导航性，以及属性类型、操作参数，都画不出来（设计调研 Q2）。

只对进了图或挂在图中节点上、却没画出的内容报 `[Warning]`，退出码仍为 0：

1. 声明视图里类型不在类图范围的成员；
2. 两端都在图中、类型不在上表的 UML 关系（如 Include、InformationFlow、Deployment）；
3. 关系资源上写了 `uml:lower`、`upper`、`aggregationKind` 等端属性（gate 放行，但对不上某一端）；
4. 图中节点经 `arch:HasPart` 拥有的、不能画进栏的目标；
5. 归属不唯一（按 IRI 序取第一个）或包嵌套成环；
6. 声明视图里一端不在图中的关系。

与图无关的成员（如指向 DDD 的 `arch:Refines`）静默略过，口径同 ArchiMate 出图。
