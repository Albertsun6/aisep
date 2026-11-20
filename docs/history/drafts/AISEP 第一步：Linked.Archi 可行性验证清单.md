# AISEP 第一步：Linked.Archi 可行性验证清单

目标：用半天到两天，跑通“手写模型 → SHACL 校验 → SPARQL 查询 → Claude Code 读写”的最小闭环，判断 Linked.Archi 能否作为 AISEP 基础设施层的底座。

注：以下命令是按公开资料整理的，仓库内部目录和文件名请以实际拉到的代码为准。

## 0. 先确认许可证

- 打开 gitlab.com/linked-archi/linked-archi-meta
- 查看根目录 LICENSE 文件，或项目页右侧信息栏的许可证标识
- 参考：同作者 GitHub 上的 meta-archimate 仓库为 Apache-2.0
- 判断：Apache / MIT / CC-BY 类可直接用；GPL 类需评估；无许可证则只参考思路、自己重写

## 1. 环境准备（macOS）

```bash
# Python 3.11+
python3 --version

# 建立验证目录和虚拟环境
mkdir -p ~/Desktop/AISEP/spike-linked-archi && cd ~/Desktop/AISEP/spike-linked-archi
python3 -m venv .venv && source .venv/bin/activate

# 核心依赖：RDF 存储/查询 + SHACL 校验
pip install pyoxigraph pyshacl rdflib pyyaml
```

## 2. 拉取仓库

```bash
# 主仓库（GitLab）
git clone https://gitlab.com/linked-archi/linked-archi-meta.git

# 配套查询工具（GitHub）
git clone https://github.com/linked-archi/linked-archi-apm.git

# 旧版 ArchiMate 本体（Apache-2.0，备用参考）
git clone https://github.com/linked-archi/meta-archimate.git
```

拉完后先看：README、core 目录下的 core-onto.ttl 和 core-shapes.ttl、modelingLanguages/archimate 下的文件。

## 3. 手写一个最小模型

用采购业务做例子，写一个 Turtle 文件 sample-model.ttl，包含：

- 3 个元素：业务角色“供应商”、业务对象“报价单”、业务流程“报价审批”
- 2 条关系：供应商 —分配给→ 报价审批；报价审批 —访问→ 报价单
- 1 个视图：包含上述元素和关系

元素和关系的类名、属性名从 core-onto.ttl 和 archimate 本体里抄，不要自己发明。

## 4. SHACL 校验

```bash
pyshacl -s <core-shapes.ttl> -s <archimate-shapes.ttl> \
        -e <core-onto.ttl> -e <archimate-onto.ttl> \
        -f human sample-model.ttl
```

验证点：

- 正确模型应该 Conforms: True
- 故意写一条非法关系（例如业务对象“分配给”业务流程），应该报错，且错误信息能看懂
- 删掉视图里某个节点指向的元素，应该报错

## 5. SPARQL 查询

用 pyoxigraph 写一个十几行的 Python 脚本 query.py：加载本体 + sample-model.ttl，跑三个查询：

1. 列出所有元素及其类型
2. 查“报价单”被哪些元素引用（影响分析雏形）
3. 查某个视图包含哪些元素

如果 linked-archi-apm 里现成的查询脚本能直接用，优先用现成的。

## 6. AI 读写测试（关键）

在 spike 目录下放一个简短的 CLAUDE.md，写明：本体文件在哪、模型文件在哪、校验命令是什么、改完必须跑校验。然后用 Claude Code 做三件事：

1. “给模型加一个元素‘采购经理’，负责报价审批，并通过校验”
2. “报价单如果改结构，会影响哪些元素？”（看它会不会自己写 SPARQL 去查）
3. “把这个模型用中文解释一遍”

观察：它能不能正确用本体里的类型、会不会自动跑校验、出错时能不能自己修。

## 7. 判断标准

通过（选 Linked.Archi 做底座）：

- 许可证允许商用
- 校验能拦住非法关系，报错可读
- SPARQL 查询在百个元素规模下秒级返回
- Claude Code 不需要太多提示就能正确增改模型

不通过（改为参考其结构自建）：

- 许可证有问题
- 本体过于复杂，AI 频繁用错类型
- 工具链在你的 Intel Mac 上装不起来或跑不动

## 8. 产出

- spike 目录本身（可以删，不进正式仓库）
- 一页结论：通过/不通过、遇到的坑、对元模型设计的启发
