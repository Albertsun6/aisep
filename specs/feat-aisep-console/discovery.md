# feat-aisep-console — 发现与范围(R2)

> refs: intent.md
> 发现地图来源:/survey 调研报告(方案 D「中心本地只读聚合器 + 每仓静态页兜底」)+ specs/_workspace/aisep-console-prototype.html(可点原型 = 发现产物)。范围按 intent 的 appetite(半天到一天、零 server)与"解锁 auction"成功指标圈定。

## in

v1 纳入 — 每项追溯到 intent:

- R1 引导填表单:六字段(problem/users/成功指标/non-goals/appetite)+ track 三档选择器,带行内帮助与示例 — refs: intent#problem(直接解锁 auction R1 认知负荷)
- 表单实时生成 gate-intent 兼容的 intent.md(正确的 `## 节` 结构 + `track:` 行)— refs: intent#成功指标(产物须一次过 gate-intent)
- 复制按钮 + 下载按钮(intent.md 交给会话/落盘)— refs: intent#成功指标(零 server 的交接路径)
- feature-id 输入(表单通用,部署到 auction 默认 auction-mvp)— refs: intent#users(多仓复用)
- Decision Inbox + Portfolio 总览外壳(取自原型,标注"实时数据 v1.1")— refs: intent#problem("哪个项目在哪步"的总览)
- 零构建单文件 HTML,file:// 双击即开 — refs: intent#appetite(不引入 server/依赖)

## out

v1 显式排除(没有显式排除 = 没做范围决策):

- 实时多仓扫描 server + CLI 聚合导出器 → defer v1.1(intent#non-goals;Portfolio 实时数据需要它,但非解锁 auction 必需)
- 前端直写 SSOT 文件(表单直接写 intent.md 到仓)→ defer v1.5(intent#non-goals;需先补写动作审计)
- R2-R5 的填表引导(圈范围/答红卡/定优先级表单)→ defer(intent#non-goals;R1 是认知负荷最重环节,先解决)
- 现成 AI 看板二开(vibe-kanban/Conductor 等)→ out(调研证伪:sunset + SQLite 事实源冲突)
- 云端 / 多人 / 权限 → out(intent#non-goals)
- 桌面壳(Tauri/Electron)→ out(零构建 HTML 已够 v1;file:// 单页不需要)

## 假设(待 R3 澄清或 pilot 验证)

- 假设:R1 表单产出 intent.md 后,auction 会话的 agent 接手写盘 + 跑 gate-intent 是顺畅交接(待 auction 端到端验证)
- 假设:R2-R5 留在聊天的认知负荷可接受(R1 解决后,反应式决策比开放式生成轻 — 待 pilot 观察)
