# AISEP 仓库使用说明

> 最近更新：2026-11-20 建仓（第三步），由 `metamodel-prototype/` 迁入。

## 是什么
AISEP 正式仓库：元模型模块、校验 CLI、示例模型、方法论文档与 ADM 阶段模板。

## 怎么用
```bash
cd ~/Desktop/AISEP/aisep
PY=~/Desktop/AISEP/spike-linked-archi/.venv/bin/python   # Python 3.12+
git config core.hooksPath .githooks                     # 提交前自动跑 gate
$PY tools/aisep.py gate                                 # 校验全部模型，PASS 才能提交
$PY tools/aisep.py test                                 # 元模型全量测试（约 2.5 分钟）
```
做某个 ADM 阶段：打开 `docs/adm/<阶段>/prompt.md` 贴给编码代理，交付物按同目录 `template.md`。

## 怎么撤
删掉 `~/Desktop/AISEP/aisep/` 即可；外层原文件（草案、`metamodel-prototype/`）未改动。关闭钩子：`git config --unset core.hooksPath`。

## 配置在哪
- 钩子：`.githooks/pre-commit`（解释器可用环境变量 `AISEP_PY` 覆盖）
- 依赖版本：`requirements.txt`
- 代理规则：`AGENTS.md`（`CLAUDE.md` 只引用它）

<!-- 迁移记录：原型原样复制（排除 build/、__pycache__），CONTRACT.md → docs/module-contract.md，原型 USAGE.md → docs/history/prototype-USAGE.md；
     docs/ 下的原则/总纲/规范/decisions 为外层文件的副本，自建仓起以仓库内版本为准。IRI 根仍为占位符 https://aisep.example/（用户 2026-11-20 决定暂留）。 -->
