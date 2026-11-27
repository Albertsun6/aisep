# DDD 视图出图（ContextMap、AggregateDiagram）

渲染核心在 `aisep/diagram_ddd.py`，命令行入口是 `tools/aisep.py diagram`。和 ArchiMate、C4 出图一样：从模型确定性生成 SVG（同一模型出同样的字节），用 ELK layered 自动布局（elkjs 版本钉在 `tools/elk`），不存坐标，只读，不进 gate。调研与取舍见协调目录 `design-ddd-view-20261127.md`。

## 用法

```sh
$PY tools/aisep.py diagram --list --model procurement                      # 列出这个模型能出的 DDD 视图
$PY tools/aisep.py diagram --viewpoint ContextMap --model workbench        # -> build/views/workbench/ContextMap.svg
$PY tools/aisep.py diagram --viewpoint AggregateDiagram --of procurement:quotationBC
                                                                           # -> build/views/procurement/AggregateDiagram-quotationBC.svg
```

`-o OUT.svg` 指定输出路径；末尾可以给模型文件，默认读 `models/**/*.ttl`。`ContextMap`、`AggregateDiagram` 只是命令行里的视图名，不对应视点 IRI。

## 上下文映射图（ContextMap，范围是一个模型）

- **画什么**：模型里的 `ddd:BoundedContext`（上层「解空间」）和 `ddd:Subdomain`（下层「问题空间」），以及它们之间的 `ddd:UpstreamDownstream`、`ddd:CustomerSupplier`、`ddd:Partnership`、`ddd:SharedKernel`、`ddd:SubdomainImplementation`。关系类型取最具体的一个，例如客户-供应方不会按上下游来画。
- **记法**照搬 Context Mapper 上下文映射图生成器：
  - 线都不带箭头。
  - 上下游关系：源（上游）一端标「U」或「U | OHS, PL」，目标（下游）一端标「D」或「D | ACL」。缩写取角色概念的 `skos:notation`，多个值按字母序排列。
  - 客户-供应方：两端分别标「U,S」「D,C」，有角色时同样跟在「|」后面；线的中部写「客户-供应方」。
  - 合作关系、共享内核：只在线的中部写类型名，两端不标注。
  - 有 `ddd:exposedAggregate` 时，中部追加一行「暴露：<聚合名>」。
  - 「实现」画成灰色虚线。
- **节点**：限界上下文画成圆角框，标「«限界上下文 · 应用»」这样的构造型。子域画成方框，按核心域、支撑域、通用域填色，同时用文字标出类型。
- 每张图带图例，列出图里出现的节点、线型，以及用到的角色缩写的中文全称。

## 聚合图（AggregateDiagram，范围是一个限界上下文）

上下文画成外框；它经 `ddd:Ownership` 拥有的每个聚合画成内框；聚合经 `ddd:Containment` 包含的实体和值对象画在聚合框里。根实体（`ddd:RootContainment`）标「«聚合根»」并加黄色左边条。拥有和包含都用嵌套表示，不画线。

## 不画的内容与提示

图里只画 DDD 关系，跨记法的连接（代码实现、am4 Realization、`arch:Refines` 等）不画。模型里有、但画不出来或者降级画的信息，一律报 `[Warning]` 并点名 IRI，不会静默丢掉：

| 情形 | 处理 |
|---|---|
| 关系有一端不在本图（例如上下游关系的一端是子域） | 这条关系不画 |
| 合作关系或共享内核带了上游 / 下游角色 | 角色不画 |
| 角色取值不在对应的 scheme 里，或者没有 `skos:notation` | 这个值不画 |
| 聚合没有根实体 | 照常画，不标「«聚合根»」 |
| 聚合还被别的上下文拥有 | 照常画，同时提示 |
| `ddd:exposedAggregate` 指向的不是聚合 | 不写进标签 |
| 一个成员被同一张图里的两个聚合包含 | 只画在第一个聚合里 |
| 同一个聚合对同一个成员既有 `ddd:Containment` 又有 `ddd:RootContainment` | 不算冲突，画一次并标「«聚合根»」，不提示 |
| 首批没有视图画的 DDD 成员（领域、团队、上下文映射、领域事件、命令、策略、服务、读模型、事件触发） | 在 ContextMap 里逐个提示 |

以下情况报 `[Violation]`，退出码为 1，不写文件：模型里没有限界上下文；`--of` 指向的不是限界上下文；`--of` 指向的上下文没有任何聚合。

验收测试在 `tests/acceptance/test_diagram_ddd.py`，期望值由 SPARQL 独立算出。
