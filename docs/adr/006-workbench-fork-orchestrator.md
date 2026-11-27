## ADR-006 · 2026-11-19

- **状态**：已采纳（2026-11-19，经 spike-workbench 验证后转正）
- **决策**：工作台以 Orchestrator.inc 为骨架，以私有镜像方式 fork；架构面板放在独立目录，以 fork 改前端的方式加入（不走插件，spike 证实插件机制不能加界面面板）。
- **理由**：Apache-2.0，近 30 天 900+ 次提交；关口审批、看板、多代理调度与需求直接对应；优先源头项目。spike 实测加一个面板改 16 个前端文件，约 20 分钟。详见 spike-workbench-result.md。
- **后果**：立即 fork，锁定 stable v0.15.3；AISEP 改动集中在独立目录，与上游接触面最小化；升级为显式动作，由 AI 辅助完成适配。GitHub 的 fork 只能公开，故采用私有镜像并保留 upstream remote。
