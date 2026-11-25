# 上游升级差异报告：Linked.Archi 2026-11-19 快照 → 2026-11-25 线上版

- 依据：关口 A 第 4 项的决定（[核实报告 §9.3](c4-archimate4-verification.md)，Albert 2026-11-25 选择“整体升级到线上版”），以及元模型规范 §11 的升级流程：抓取 → 差异报告 → 全部模块回归 → 人工批准（批准记录，关口为“架构决策”）。
- 对应规范：[c4-archimate4-dual-model.md](c4-archimate4-dual-model.md) 第 9 节第 3 步。

## 1. 抓取

- 范围：`vendor/meta.linked.archi/urls.txt` 中的全部 245 个 URL，请求头为 `Accept: text/turtle`。URL 清单没有改动，`REMOVED.txt` 也没有改动。
- 结果：245 个请求都返回 `200 text/turtle`，全部用 pyoxigraph 解析通过。`FETCHED_AT` 改为 `2026-11-25T14:19:07Z`；`fetch.log` 与 `SHA256SUMS` 重新生成，文件顺序与原来相同。
- `vendor/MANIFEST.json` 用 `tools/vendor_manifest.py generate` 重新生成，之后 `check` 结果为 `problems=0`。
- 许可证：33 个有变化的文件中，没有一个的 `cc:license` 或 `dcterms:license` 声明发生变化；MANIFEST 里也没有缺许可证的上游文件。
- 上游目录新增了一项资产 `https://meta.linked.archi/core-notation`。它不在 URL 清单里，本次没有引入，因为当前加载的任何文件都没有 import 它。

## 2. 有变化的文件（33 个，其余 212 个字节完全相同）

**AISEP 实际加载、本次有变化的 4 个文件**

| 文件 | 版本 | 变化 | 加载方 |
| --- | --- | --- | --- |
| `core.ttl` | 0.6.0 → **0.7.0** | 新增 `arch:DependsOn`、`arch:dependsOn`、`arch:dependencyOf`、`arch:qualifiedDependsOn`（DD-40、DD-44） | 全部 7 个模块 |
| `archimate4_onto.ttl` | 4.0 → 4.0（内容变化，版本号没变） | `am4:serves` 设为 `arch:dependencyOf` 的子属性；十几处 `arch:domainIncludes`/`rangeIncludes arch:Element` 收窄为 am4 的四个抽象类 | am4、ddd、ext-code、ext-governance、ext-verification |
| `arch-decision.ttl` | 0.0.9 → 0.0.10 | `ad:dependsOn` 增加父属性 `arch:dependsOn` | ext-governance |
| `uml_onto.ttl` | 0.3.0 → 0.4.0 | `uml:dependsOn` 等依赖属性对齐 `arch:dependsOn`（DD-44） | uml |

没有变化、仍被加载的文件：`archimate4_shapes`、`archimate4_viewpoints`、`archimate4_relationship-tables`（RT_FILE）、`core-shapes`、`bpmn_*`、`uml_shapes`、`arch-decision-shapes`、`iso25010`。

**C4 相关（目前没有被加载，留给第 4 步使用）**：`c4_onto`（0.3.0，`c4:uses` 的定义域收窄到 C4 自己的四类元素，并新增 scopeNote，说明 C4 与其他语言之间要用 core 的关系类型）、`c4_shapes`（0.2.0，新增 36 组合法的 `Using` 组合，以及按元素类型划分的直接谓词 shape）、`c4_structurizr`、`c4_structurizr-shapes`。

**其余变化，AISEP 不加载**：`arch-decision` 以外的 archimate3 系列（`archimate3_onto`、`archimate3_onto_3.0`、`archimate3_derivation`）、`archimate4_derivation`、backstage 系列 6 个、basic 系列 3 个、`bpmn-lite_onto`、`catalog`、`core-deliverable-templates`、`core-questions`、`core-vis`、`core-vis-shapes`（CC-BY-SA，仍然不加载）、`examples_*` 3 个、`leanix_onto`、`togaf_onto`、`togaf9_onto`。

## 3. 回归结果

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| vendor 清单 | `$PY tools/vendor_manifest.py check` | PASS，problems=0 |
| gate | `$PY tools/aisep.py gate` | PASS：19 个文件，violations=0，warnings=1，infos=8，与升级前相同（warning 是 procurement 里已有的派生捷径） |
| 全部模块测试 | `$PY tools/aisep.py test` | PASS：940/940，见第 5 节 |

## 4. C4 环境可用性（用上游自带的示例数据跑一遍）

做法与上游 Structurizr 转换器的 `validate` 一致：shapes 用 `c4_shapes`、`c4_structurizr-shapes`、`core-shapes`，本体用 `core`、`c4_onto`、`c4_structurizr` 做 RDFS 子类推理；校验器是 pyshacl 0.40.2，打开 `inference=rdfs`。

| 数据 | 来源 | 结果 |
| --- | --- | --- |
| Order Management 的 C4 模型 | [practice 页 §8](https://meta.linked.archi/docs/practice/archimate-application-layer-vs-c4-containers/#c4-model-what-it-looks-like-to-technical-teams) 原文，只补了 `@prefix` 行 | conforms=True |
| 转换器输出示例的 semantic 图 | [Structurizr 转换器文档 Output example](https://converters-c2cddb.gitlab.io/converters/structurizr/#output-example)，`…` 换成 example.org IRI | conforms=True |
| 反例：4 处故意写错 | 自写探针 | conforms=False，4 条 Violation 一一对应：人不能包含容器；标签没有语言标签；ContainerContainment 端点类型错误；Deployment 起点不是容器 |

反例 4 处全部被拦下，说明这些 shapes 确实在生效，不是空跑通过。探针脚本和数据只放在会话临时目录，没有提交到仓库；第 4 步写 AISEP 规则时会配正式的测试样例。

## 5. 全部模块测试

`$PY tools/aisep.py test`（含 `aisep-mcp/tests` 与合并检查负例）：`SUMMARY test total=940 passed=940 failed=0 seconds=2865.6`，退出码 0。日志里出现的 `ValueError`、`Parser error` 都来自预期失败的负例 fixture，对应用例本身是 PASS。

## 6. 还差的人工步骤

按元模型规范 §11，这次升级还需要一条人工批准记录（关口为“架构决策”），只能由 Albert 本人做出。本 PR 改到了 `vendor/**` 和根目录的 `NOTICE`，合并前还需要独立评审。
