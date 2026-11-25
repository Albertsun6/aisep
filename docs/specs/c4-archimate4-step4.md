# C4 与 ArchiMate 4 双模型：第 4 步实施说明（C4 模块与 AISEP 规则）

- 对应规范：[c4-archimate4-dual-model.md](c4-archimate4-dual-model.md) 第 9 节第 4 步、第 7 节
- 沿用关口 A 的四项决定（[核实报告 §9.3](c4-archimate4-verification.md)）：
  - 跨模型关联用 `arch:refines`；
  - 一个数据库对应多个逻辑数据对象时，先在 am4 侧聚合，数据库再 refines 聚合后的那个；
  - C4 模块的层级是 design；
  - 上游已升到 core 0.7.0。
- 本步不含第 5 步（示例系统）和第 6 步（生成视图与 arc42）。

## 1. 模块

`modules/c4/metamodel.ttl`，模块 IRI `https://aisep.example/module/c4`，基本属性：

| 项 | 取值 |
| --- | --- |
| 类型 | Language |
| 版本 | 0.1.0 |
| `aisep:notationLevel` | `aisep:LevelDesign` |
| `aisep:inheritsHubRules` | `false` |
| 拥有的命名空间 | `c4/onto#`、`c4/structurizr#` |
| 加载 | core、archimate4_onto、c4_onto、c4_structurizr |
| shapes | 上游 `c4_shapes`、`c4_structurizr-shapes`（原样），加 AISEP 自己的 `modules/c4/shapes.ttl` |

- **双模型**：C4 不做成 ArchiMate 的视图，模块里没有 `align.ttl`，即不声明任何 C4 ⊑ am4 公理。C4 与 am4 之间只能用 `arch:Refines` 连接，方向是从 C4 指向 am4（§7.1、§7.2，已有 L1 规则）。C4 自己的关系连到 am4 元素会被判为记法混用，见负例 `dual-c4-using-to-am4.ttl`。
- **不加载的上游文件**：c4 的 viewpoints、notation、deliverable-templates（没有规则用到）；core-vis、edgy（CC-BY-SA）。
- **上游文件**没有任何改动。`vendor/MANIFEST.json` 只更新了由加载代码推导的 `loaded` / `loadedBy` 两个字段，新增被加载的是 `c4_onto`、`c4_structurizr`、`c4_shapes`、`c4_structurizr-shapes`。

## 2. 第 7 节 AISEP 规则怎么落实

| 规范第 7 节的规则 | 级别 | 实现 | 应失败的样例 | 应通过的样例 |
| --- | --- | --- | --- | --- |
| R1 本方 `c4:SoftwareSystem` 恰好关联一个 `am4:ApplicationComponent` | 第一级 | `c4ash:SystemRefinesOneComponentShape` | `r1-system-without-component`、`r1-system-refines-not-component` | `dual-model-ok` |
| R1 反之亦然 | 第一级 | `c4ash:ComponentRefinedByOneSystemShape`（至多一个，见 §4 偏离 1） | `r1-component-two-systems` | `dual-model-ok` |
| R2 每个 `c4:Container` 恰好属于一个 `c4:SoftwareSystem` | 第一级 | `c4ash:ContainerInOneSystemShape`（上游 `c4/shapes` 没有这条，核实报告 §5） | `r2-container-without-system`、`r2-container-two-systems` | `dual-model-ok` |
| R3 每个 `c4:Database` 至少关联一个 `am4:DataObject` | 第一级 | `c4ash:DatabaseRefinesDataObjectShape`；“至多一个”由已有的 §7.2 主锚唯一规则保证（关口 A） | `r3-database-without-dataobject`、`r3-database-refines-two-dataobjects` | `dual-model-ok`（数据库 refines 聚合后的 DataObject） |
| R4 每条关系同时有直接谓词和限定资源，且端点一致 | 第一级 | 不另写 shape，见 §4 偏离 2 | `r4-direct-uses-triple` | 所有 valid 样例 |
| R5 跨容器的 `c4:Using` 必须有 `c4:technology` | 第一级 | `c4ash:CrossContainerUsingTechnologyShape`；组件按它所在的容器计 | `r5-cross-container-no-technology`、`r5-cross-container-component-no-technology` | `r5-same-container-no-technology-ok`、`dual-model-ok` |
| R6 每个 `am4:ApplicationComponent` 至少执行一个 Function 或 Process | 第二级（Warning） | `c4ash:ComponentPerformsBehaviourShape`；可直接执行，也可经一个 Role 执行（§4 偏离 6）；范围见 §4 偏离 3 | `r6-component-without-behaviour-warns`（期望出现 Warning） | `dual-model-ok`（期望无 C4 Warning） |
| R7 每个 `am4:Service` 至少被一个行为实现，并能追溯到 Capability 或 Requirement | 第二级 | `c4ash:ServiceTraceShape`，只检查追溯这一半（§4 偏离 4）；范围见 §4 偏离 3 | `r7-service-without-trace-warns` | `dual-model-ok` |
| R8 每个 `am4:DataObject` 至多一个权威来源（Assignment） | 第二级 | `c4ash:DataObjectOneSourceShape`，作用于全部数据对象 | `r8-dataobject-two-sources-warns` | `dual-model-ok` |

另外三个样例：
- `upstream-containment-endpoints`：确认上游 `c4/shapes` 确实已接入，期望出现上游独有的消息；
- `upstream-structurizr-deployment-endpoints`：确认上游 `c4/structurizr-shapes` 确实已接入；
- `dual-refines-wrong-direction`：确认 refines 只能从 C4 指向 am4。

规则的说明文字都写成中文（`sh:message …@zh`）。样例在 `modules/c4/tests/`，随 `tools/aisep.py test` 和 CI 的 `fixtures` 一起跑。

## 3. 验证

- `$PY tools/aisep.py test --no-pytest`：232/232 通过，其中 c4 的 19 个样例（5 个应通过、14 个应失败）全部通过。PR #106 首轮评审用副本做过对照：逐条停用 AISEP 规则后，对应样例都会变成不通过。
- `$PY tools/aisep.py gate`：PASS，与 main 相同（violations=0，warnings=1，infos=8）。现有模型没有新增 Warning，R8 作用于全部数据对象也没有带来新的告警。
- `tools/vendor_manifest.py check`：PASS。

## 4. 偏离规范之处（规范原文未改）

1. **R1“反之亦然”按“至多一个”实现**：一个 am4 组件至多被一个 C4 软件系统 refines。理由是规范 §3 第一条硬规则说明，多数 am4 组件不会有 C4 描述，如果要求“恰好一个”，所有只在 am4 里建模的组件都会报错。
2. **R4 不另写 shape**：AISEP 硬规则 2（元模型规范 §8.1）规定，作者只写限定关系资源，直连三元组由 `aisep build` 生成；手写直连三元组本来就是 L1 违规。所以“两种形式都有、端点一致”由构建过程保证。这一条与规范 §4 写法规定第 2 条（“同时写直接谓词和限定资源”）不同，以 AISEP 硬规则为准。
3. **R6、R7 只针对被 C4 元素（系统或容器）refines 的 am4 组件，以及这些组件所实现的服务**：本模块只负责双模型这一部分，不给纯 am4 模型增加告警。R8 按规范作用于全部数据对象。
4. **R7 只实现“可追溯”这一半**：服务本身，或实现它的某个行为，realizes 了一个 Capability 或 Requirement。另一半“至少被一个行为实现”没有实现：没有行为实现的服务，找不到通向 C4 元素的路径，因此无法按偏离 3 的范围选中。
5. **与 AISEP 现行规范文字的出入（已全部修订）**：
   - `docs/metamodel-spec.md` 的 §13、§7.2、§7.3 G5 已由 PR #111 修订（加入 §6.8，C4 列为 design 层，G5 写进 `arch:DependsOn`）；
   - 基线版本、§0 中 C4 是例外，以及 `docs/decisions.md` 的 G5 与 ADR-025（C4 双模型），由 PR #114 补上。

6. **规范 §5 与上游冲突，以上游为准**：
   - 规范 §5 写的是 `am4:ApplicationComponent am4:assignedTo am4:Function / am4:Process`。
   - 上游 `archimate4_relationship-tables` 中，组件只对 `am4:Role` 和 `am4:DataObject` 有 `permitsDirectAssignment`；组件 → Function/Process 只有 `permitsAssignment`，也就是只能派生，直接写会得到 L2 的 derived-only 告警。
   - 因此 R6、R7 同时接受直接 Assignment 和经一个 Role 的 Assignment（`am4:assignedTo/am4:assignedTo?`）。正例 `dual-model-ok` 按上游写成“组件 → Role → Function”，并期望没有 derived-only 告警。
   - 这一条应补进核实报告 §8 的不一致表；规范原文未改。

## 4.1 已知局限（后续事项）

- **组件归属没有检查**：组件不属于任何容器、或同时属于两个容器，都不报错；R5 对这类组件也会漏报。规范第 7 节没有要求这一条，上游同样不检查（核实报告 §5）。
- **独立治理的数据库**：规范 §6 允许独立治理的容器 refines 一个 am4 组件。但数据库按 R3 必须 refines 一个 DataObject，而 §7.2 的主锚唯一规则又不允许它再 refines 第二个 am4 节点，所以数据库无法同时对应两边。这是关口 A 方案 (a) 带来的副作用。
- ~~**impact 不沿 C4 关系遍历**~~：已由 `modules/c4/impact.ttl` 补上（方向见规范 §9）。

## 5. 新铸 IRI 清单（一经创建不改，请 Albert 过目）

- **模块**：`https://aisep.example/module/c4`
- **shapes 命名空间** `https://aisep.example/ont/c4/shapes#`（前缀 `c4ash`）下的 9 个：
  - `c4ash:prefixes`：SPARQL 前缀声明
  - `c4ash:SystemRefinesOneComponentShape`
  - `c4ash:ComponentRefinedByOneSystemShape`
  - `c4ash:ContainerInOneSystemShape`
  - `c4ash:DatabaseRefinesDataObjectShape`
  - `c4ash:CrossContainerUsingTechnologyShape`
  - `c4ash:ComponentPerformsBehaviourShape`
  - `c4ash:ServiceTraceShape`
  - `c4ash:DataObjectOneSourceShape`
- **没有**新的类、属性或个体：C4 的词汇全部来自上游 `c4:` 和 `structurizr:`。
- 测试样例里的实例 IRI 都在 `https://aisep.example/model/t/` 下，与其他模块的样例一样只用于测试，不进入任何模型。

## 6. 给自动出图的 C4 类清单

**元素**（rdf:type，可带子类）：

| 类 | 说明 |
| --- | --- |
| `c4:Person` | 人；`c4:ExternalPerson` 是外部人 |
| `c4:SoftwareSystem` | 软件系统；`c4:ExternalSoftwareSystem` 是外部系统 |
| `c4:Container` | 容器；子类有 `c4:Database`、`c4:MobileApp`、`c4:ClientSideWebApp` |
| `c4:Component` | 组件 |
| `structurizr:DeploymentNode` | 部署节点 |
| `structurizr:InfrastructureNode` | 基础设施节点 |

**关系**：模型里写限定资源，构建后另有直连三元组。

| 限定资源类 | 构建出的直连谓词 | 端点 | 用途 |
| --- | --- | --- | --- |
| `c4:ContainerContainment` | `c4:hasContainer` | 系统 → 容器 | 容器图的边界 |
| `c4:ComponentContainment` | `c4:hasComponent` | 容器 → 组件 | 组件图的边界 |
| `c4:Using` | `c4:uses` | C4 元素之间（上游 36 组合法组合） | 连线；连线文字是资源上的 `skos:prefLabel`，协议是 `c4:technology` |
| `structurizr:Deployment` | `structurizr:deployedOn` | 容器 → 部署节点 | 部署图 |
| `arch:HasPart` | `arch:hasPart` | 部署节点 → 部署节点 | 部署节点嵌套，沿用上游转换器的写法 |
| `arch:Refines` | `arch:refines` | C4 元素 → am4 元素 | 跨模型关联，不在 C4 图里画 |

**属性**：`c4:technology`（容器、组件、Using），`structurizr:environment`、`structurizr:instances`（部署节点）。

**视点**：本模块没有加载上游 `c4_viewpoints`。如果出图需要引用 `c4vp:` 视点 IRI，要另行加载该文件，许可证是 CC-BY-4.0。
