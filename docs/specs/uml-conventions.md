# UML 模块的建模约定

适用于 `modules/uml`（规范 §6.3）。本文件只记已拍板的约定；`docs/module-contract.md`、`docs/metamodel-spec.md` 正在别的 PR 里改（#173、#175），合入后可把本节并进去。

## 归属：一律用 `arch:HasPart`
- 类元拥有的属性（`uml:Property`）、操作（`uml:Operation`）、枚举字面量，以及包（`uml:Package`）包含的元素，都写成 `arch:HasPart` 限定关系：`arch:source` 是拥有者，`arch:target` 是被拥有者。
- 不用上游的 `uml:namespace`：它是两个模型成员之间的直连属性，不是限定关系，不在 G7 白名单（`aisep/core.py` 的 `ELEMENT_LINK_OK`）里，gate 会拒绝（硬规则 2「只写限定关系」）。
- 依据：拍板记录第 19 条（Albert，2026-11-27）。类图出图（PR #177，`diagram --uml ClassDiagram`）按这条约定把 `arch:HasPart` 的目标画进类元栏、把包画成框。

## 视点：加载 `uml_viewpoints.ttl`
- uml 模块从 0.4.0 起在 `aisep:loads` 里加载上游 `vendor/meta.linked.archi/ttl/uml_viewpoints.ttl`，14 种 UML 图都是已知的 `arch:Viewpoint`（前缀 `umlvp:`，`https://meta.linked.archi/uml/viewpoints#`）。
- 所以视图写 `arch:viewConformsToViewpoint umlvp:ClassDiagram` 时，L3 不再报「value must be an arch:Viewpoint」的 Warning。夹具：`modules/uml/tests/valid/class-diagram-view.ttl`。

## 示例
```turtle
:Order a uml:Class ; arch:inModel :m ; arch:inView :v ; skos:prefLabel "订单"@zh .
:Order-amount a uml:Property ; arch:inModel :m ; arch:inView :v ; skos:prefLabel "金额"@zh .
:has-order-amount a arch:HasPart ; arch:inModel :m ; arch:source :Order ; arch:target :Order-amount .
:v a arch:Diagram ; arch:inModel :m ; skos:prefLabel "订单类图"@zh ;
    arch:viewConformsToViewpoint umlvp:ClassDiagram .
```
