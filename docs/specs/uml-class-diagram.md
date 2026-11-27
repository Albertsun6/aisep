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
- 首批只有类图。`--uml` 后跟其他图种名（如 `UseCaseDiagram`），或 `--view` 的视图视点是其他 `umlvp:` 图种（如 `umlvp:UseCaseDiagram`），报 `[Violation]`，退出码 1，不写文件。
- `--uml list` 用 `aisep.core.model_slug` 从模型 IRI 取 slug；模型 IRI 不是 `https://aisep.example/model/<slug>/` 形式时 `--model` 指不到它，不列出 `--model` 命令，改报一条 `[Warning]`。
- UML 模块尚未加载 `uml_viewpoints.ttl`，所以声明 `umlvp:ClassDiagram` 视图时 gate 会报 1 条 L3 Warning；加载这一行另开 PR。

## 一张图画什么

- **节点**：断言类型为 `uml:Class`、`Interface`、`DataType`、`Enumeration`、`PrimitiveType` 的模型成员（不含关系资源）。`uml:Component`、`Node`、`Actor`、`UseCase` 等不进类图。投影模式取本模型全部节点；声明视图只取 `arch:inView` 成员。
- **特性**：节点经 `arch:HasPart` 拥有的 `uml:Property`、`uml:Operation`、`uml:EnumerationLiteral`，画进属性栏和操作栏。
- **包**：经 `arch:HasPart` 拥有节点的 `uml:Package` 画成带标签页的框，可嵌套；空包不画。
- **边**：两端都在图中的 Association、Aggregation、Composition、Generalization、Dependency、Abstraction、Realization、InterfaceRealization、Usage。两端是同一个类元的（自关联、自依赖等）画成 ELK 自环；Generalization 与 InterfaceRealization 例外，UML 不允许它们两端相同（泛化不得成环；接口实现的契约须是 Interface、实现方须是 BehavioredClassifier），不画，单独报 warning 写明原因。

归属用 `arch:HasPart`：上游的 `uml:namespace` 不是限定关系，过不了 G7。这条约定待 Albert 确认（见下文「待定问题」Q1）。

## 首批范围

宁少勿错：只做现有数据或样例用得到、记法确定的部分。

| 项 | 首批 | 理由 |
|---|---|---|
| 类图节点：Class、Interface、DataType、Enumeration、PrimitiveType | 做 | 现有模型与 `modules/uml/tests/valid/order-class-diagram.ttl` 都有类和接口 |
| 关系：上面「边」列的九种 | 做 | 记法确定 |
| 特性栏、包复合框（`arch:HasPart`） | 做，取决于 Q1 | gate 放行，C4 有用 `arch:HasPart` 表达归属的先例；Q1 定为不用 `arch:HasPart` 时降级为只画名称栏 |
| 声明视图 `--view`（`umlvp:ClassDiagram`） | 代码同期做 | 模块加载 `uml_viewpoints.ttl` 另开 PR |
| 用例图、包图 | 不做 | 现有模型里没有 Actor、UseCase、Package，只有词汇没有数据 |
| 组件、部署、组合结构、对象、Profile 图 | 不做 | 组件和部署与 C4、ArchiMate 技术层重叠，现有数据为 0 |
| 活动、状态机、顺序、通信、时序、交互概览 | 不做 | 现有数据为 0；顺序图要另一种布局 |
| 关联端多重性、角色名、可导航性；属性类型；操作参数 | 画不出来 | 上游词汇缺口，见 Q2 |

## 待定问题

- **Q1（待 Albert 定）**：属性、操作归属类，类归属包，是否约定用 `arch:HasPart`（gate 已放行，C4 有先例），还是把 `uml:namespace` 加进 G7 白名单（改 `aisep/core.py`，走合并前评审）。推荐前者：渲染器只读，零改动。选后者时首批只画名称栏。
- **Q2（记为后续）**：是否补关联端词汇（多重性、角色名）。这是上游 vendor 词汇的缺口，要改元模型；不补的话类图没有端标签。本功能不处理。

## 记法（UML 2.5.1）

| 项 | 画法 |
|---|---|
| 类 | 名称栏；有特性时加属性栏与操作栏 |
| 抽象类 | 名称斜体，另加 `{abstract}` |
| 接口、枚举、数据类型、基本类型 | 名称上方的关键字 `«interface»`、`«enumeration»`、`«dataType»`、`«primitive»` |
| 属性 | `可见性 [/]名称 [多重性] [= 默认值] [{readOnly}]`；上界写 `*` 或负整数（词汇约定 `-1`）都显示为 `*`（UML 2.5.1 §7.5 的无上界）；静态加下划线 |
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
6. 声明视图里一端不在图中的关系（`关系在视图中，但有一端不在图中，未画`）；
7. Generalization、InterfaceRealization 两端是同一个类元（写明 UML 不允许的原因）；
8. 特性的 `uml:lower` 不是非负整数，或 `uml:upper` 不是非负整数、`*`、负整数（如 `"many"`）：报 warning，这一行不画多重性；上界不是 `*` 且小于下界（未写的界按 1 计，如只写 `uml:lower 5`）时同样处理（UML 2.5.1 的 upper_ge_lower）。

warning 文案一律中文。

与图无关的成员（如指向 DDD 的 `arch:Refines`）静默略过，口径同 ArchiMate 出图。

## 可证伪验收

`tests/acceptance/test_diagram_uml.py` 由 `aisep.py test` 运行，每条断言打印 CONFIRMED / REFUTED 与证据。期望集合一律由独立的 SPARQL（经 `aisep.py query`）算出，不取自 `aisep/diagram_uml.py`。输入：P = `models/procurement`；C0 = `modules/uml/tests/valid/order-class-diagram.ttl`；C1 = 测试时在临时目录由 C0 追加生成（包、特性、DataType / Enumeration / PrimitiveType、其余各类关系、自关联、自泛化、不支持的 InformationFlow、关联上的 `uml:lower`），不入库。

1. **能出图**：P 恰好 1 个类元、0 条关系、0 条 warning；C0 恰好 4 个节点、3 条关系；不支持的图种（`--uml` 与 `--view` 两条入口）退出码 1。
2. **确定性**：同一模型生成两次字节相同。
3. **ArchiMate / C4 不受影响**：不改 `aisep/diagram.py`、`aisep/diagram_c4.py`；`aisep.py test --no-pytest` 全绿。
4. **成员完整**：每条线的 `data-source` / `data-target` 等于模型的 `arch:source` / `arch:target`（泛化按模型方向记，不按 ELK 喂入方向）；C1 的节点集合 = 投影规则算出的集合；关联资源本身不是节点；`Quotation` 恰好 3 行特性。
5. **记法与方向**：九种关系逐类断言线型、marker 及其所在端；泛化与实现的一般端排在上面；五种类元逐个断言关键字（类无关键字）；抽象类名称斜体并带 `{abstract}`；自关联画成同一框上的自环。
6. **几何**：兄弟框不重叠；节点在包框内；每条线首点在源框边上、末点在目标框边上（容差 1.5px）；正交。
7. **warning 口径**：C1 恰好 3 条（InformationFlow、关联上的 `uml:lower`、自泛化的单独原因），全部中文；多重性 `"*"` 显示为 `[0..*]`，非法界各报 1 条。
8. **`--view` 分派**：`umlvp:ClassDiagram` 视图由 UML 渲染器出图，不出现 ArchiMate 的「其他」分带。
9. **变异对照**：上面的每类断言都先把实现改坏、确认对应断言变红，再还原；改坏后仍绿说明测试本身不合格。各次 PR 的变异清单与结果写在 PR 描述里。
