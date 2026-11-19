# metamodel-prototype 使用说明

## 是什么
AISEP 元模型（规范 v0.4）的可执行原型，包含 8 个模块：ArchiMate 4.0 枢纽、BPMN、UML、DDD、验证、代码追溯、治理、核心规则；一个跨记法的采购例子；以及校验、构建、查询、影响分析的命令行 `tools/aisep.py`。它是第一期 MCP Server（ADR-008）的语义基准。

## 怎么用
```bash
cd ~/Desktop/AISEP/metamodel-prototype
PY=~/Desktop/AISEP/spike-linked-archi/.venv/bin/python   # 需要 Python 3.12+
$PY tools/aisep.py gate models/procurement/*.ttl         # 唯一的提交/CI 入口：L0–L4 一次跑完
$PY tools/aisep.py check models/procurement/*.ttl        # 开发时的快速反馈（约 0.1 秒）
$PY tools/aisep.py impact procurement:quotation --mode depends   # 或 --mode ripple
$PY tools/aisep.py query 'SELECT ...'                    # 在构建后的图上查询
$PY tools/aisep.py test                                  # 全部模块和验收测试（约 2–3 分钟）
```
写模型的规则见 `CONTRACT.md` 的 Authoring profile 一节：只写限定关系、一个元素一个类型、不手填 approvalState、谓词闭世界等。

## 怎么撤
原型自成一体，不改任何全局配置；删掉整个 `metamodel-prototype/` 目录即可。它依赖的 Python 环境在 `spike-linked-archi/.venv`，可以一起删。

## 配置在哪
- 模块：`modules/<名>/metamodel.ttl`（清单）、`onto.ttl`、`shapes.ttl`、`align.ttl`、`impact.ttl`、`tests/`
- 上游本体（只读，按 SHA256 锁定）：`vendor/meta.linked.archi/`
- 接口约定：`CONTRACT.md`；设计依据：`../AISEP 第二步：元模型规范（草案）.md`
<!-- 过程记录：v0.1→v0.3 共 5 轮实现/审计，测试从 84 → 109 → 128 → 139 → 148；GPT-5.3 经 cursor-agent 做了 2 次异构评审。v0.4（ADR-013）加 aisep:AgentActivity / aisep:activity，测试 148 → 174；经一轮 GPT 异构评审后补主语限制、空白节点活动、EG24 混合时区，测试 174 → 179。细节见规范附录 B。 -->
