## ADR-029 · 2026-11-27

- **状态**：已采纳（Albert 2026-11-27 定：模块属性必须声明定义域；vendor 定义域暂不强制）。承接 issue #67 与 PR #153。
- **决策**：
  1. **模块属性必须声明定义域。** `modules/**` 声明的每个 `owl:ObjectProperty`、`owl:DatatypeProperty`、`rdf:Property` 至少有一条写在模块文件里的 `rdfs:domain`，取值是 IRI 或 `owl:unionOf` 的 IRI 列表；`owl:AnnotationProperty` 是元模型注解，不在此列。这是模块合约，由 pytest `aisep-mcp/tests/test_module_property_domains.py` 检查（CI 必需检查 `pytest`）。L1 定义域检查（PR #153）对 `owl:unionOf` 定义域按「主语是其中任一类」判定。
  2. **`vendor/` 上游本体声明的 `rdfs:domain` 暂不强制。** L1 只读模块文件里的定义域；上游属性被借用到别的类型上，`gate` 照旧不拦。
- **理由**：PR #153 只强制已声明的定义域，没声明定义域的模块属性仍可借用到任意元素上，等于留了一个口子；补齐定义域并把「必须声明」做成常驻检查，口子才算堵上。vendor 暂不强制，是因为上游的写法与 RDFS 语义不完全一致：`ad:appliedInOption` 声明了三个 `rdfs:domain`（ReferenceArchitecture、Pattern、Tactic），按 RDFS 是交集，上游大概率想要并集；ArchiMate 4 的关系谓词用的是不蕴含的 `arch:domainIncludes`。强制之前要先定口径，又不能改上游文件（硬规则 6）。实测当前仓库模型没有违反 vendor 定义域的写法。
- **后果**：
  - 本次补齐的定义域：DDD 关系类的直连谓词取关系类定义写明的源端（`ddd:upstreamOf`、`supplierOf`、`partnerOf`、`sharesKernelWith`、`owns`、`implements` → `ddd:BoundedContext`；`ddd:contains`、`hasRoot` → `ddd:Aggregate`；`ddd:triggers` → `owl:unionOf(ddd:DomainService ddd:Policy)`），DDD 升 0.2.1；ext-actions 新增类 `aisep:ActionBinding` 作参数绑定节点的定义域（`aisep:argument`、`constant`、`fromParameter`、`fromStep`、`modelOf`、`attributePredicate`），并作 `aisep:binding` 的值域，`catalog.ttl` 里的绑定节点仍不写类型，已有动作的定义摘要不变，ext-actions 升 0.2.0。声明这个类会让它在 L1 成为合法类型，所以 EA10 的绑定形状同时以 `aisep:ActionBinding` 为目标：类型写成它的节点必须是 `aisep:binding` 的宾语，否则 L3 报 EA10（负例 `ea10-action-binding-type-on-model-element.ttl`）；未铸新 IRI。
  - 直连谓词的定义域只在源文件里读到，而源文件里写直连三元组本身就是 L1 违规；限定关系的 `arch:source` 目前不按直连谓词的定义域核对（ext-code 的 EC5、ext-verification 的 EV2 已有同类核对，DDD 没有）。
  - 重新考虑 vendor 定义域的触发条件：模型里出现借用上游属性造成的实际问题，或升级上游（规范 §11）时上游改了定义域的写法。
