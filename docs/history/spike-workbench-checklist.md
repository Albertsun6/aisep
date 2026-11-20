# spike-workbench-checklist.md

目标：用半天到一天，验证 Orchestrator.inc（agent-orchestrator）能否作为 AISEP 工作台的骨架，并回答核心问题：插件机制能否添加全新的界面面板。与 Linked.Archi 验证（spike-checklist.md）并行，互不依赖。

背景和选型理由见 workbench-reference.md。

注：以下步骤按公开资料整理，仓库内部结构和文档地址以实际为准。

## 0. 确认许可证与活跃度

- 仓库：github.com/OrchestratorInc/agent-orchestrator
- 已知：Apache-2.0，14.6k 星，4,120 次提交
- 确认：最近一次 release 日期、最近 30 天提交数、issue 响应情况

## 1. 安装试用

```bash
# 从 Releases 下载 macOS 桌面版安装（Intel 版本）
# 或源码构建：
cd ~/Desktop/AISEP
git clone https://github.com/OrchestratorInc/agent-orchestrator.git
cd agent-orchestrator
# 按 README / CONTRIBUTING.md 的构建说明执行（Go 后端 + Node 前端）
```

验证点：Intel Mac 上能否正常启动；配置 Claude Code 作为 worker 是否顺利。

## 2. 走一遍完整流程

用一个小任务（例如：在 AISEP 仓库里加一个 README 段落）走完：

1. 向主代理下达任务
2. 观察它如何拆分、启动 worker、建 worktree 和分支
3. 看板上的状态流转：Working → Needs you → In review → Ready to merge
4. 在"Needs you"处做一次批准和一次驳回，看驳回后 worker 如何继续
5. 在结构化聊天里问 worker"为什么这么改"

记录：关口页面现在长什么样、展示了哪些信息、跟 AISEP 要的关口页面（AI 摘要 + 模型差异图 + 校验结果 + 批准/驳回/修改）差多远。

## 3. 核心问题：插件能否加界面面板

阅读：

- docs.orchestrator.inc/plugins 全部页面
- 仓库内 DESIGN.md、AGENTS.md、CONTEXT.md
- packages/ 和 contracts/ 目录，找插件接口定义
- frontend/src/renderer 目录，看现有面板是怎么注册的

要回答：

- 插件能注册新的顶级页面或侧边栏入口吗？
- 插件能在现有页面（如 PR 评审页）里插入自定义区块吗？
- 插件能访问外部数据源（如本地 MCP Server）吗？
- 如果以上都不能：fork 后在前端加一个面板要改哪些文件？估计工作量。

## 4. 小规模改造实验（可选，视第 3 节结论而定）

用 Claude Code 在 fork 上加一个最简面板：侧边栏加一个"Architecture"入口，点进去显示一段写死的文字。观察：

- 改了几个文件
- 构建和热重载是否顺畅
- Claude Code 能否凭仓库自带的 AGENTS.md / CLAUDE.md 自己搞定，不需要太多提示

## 5. 判断标准

通过（选为工作台骨架）：

- Intel Mac 上跑得起来，Claude Code 作为 worker 正常工作
- 关口流程（批准 / 驳回 / 聊天）符合预期
- 插件能加界面面板，或 fork 改前端的工作量可接受（一个面板一天内）

不通过（换候选或自建轻量工作台）：

- Intel Mac 跑不动或极不稳定
- 前端结构封闭，加面板要动大量核心文件
- 关口模型与 AISEP 的人工把关需求有根本冲突

## 6. 产出

- spike-workbench-result.md：通过/不通过、插件 vs fork 的结论、关口页面现状截图描述、遇到的坑
- 若做了第 4 节：fork 仓库地址和改动的文件清单
