# feat-aisep-console — 规格(R5)

status: active

> refs: discovery.md (in/out 范围) · intent.md (problem/成功指标/non-goals/appetite)

目标:交付 AISEP Console v1 —— 单文件零构建 HTML,核心是 **R1 引导填表单**(把"聊天里记六问"变成"结构化表单填六字段"),产出一次性通过 `gate-intent` 的 `intent.md`,解锁 auction pilot 被阻塞的 R1;附 Decision Inbox + Portfolio 总览外壳。

## 背景

需求来源:`/survey` 调研报告(方案 D 中心本地只读聚合器)+ 可点原型(specs/_workspace/aisep-console-prototype.html)+ auction pilot-log 高严重度摩擦。范围按 R2 discovery 的 in/out 表冻结:v1 = 客户端表单 + 总览外壳;server 实时数据 = v1.1;前端直写 = v1.5。设计纪律:人决策(填什么)在表单,机器裁决(gate)不变,前端只生成产物文本、不写 SSOT。

## 范围

### 实现项(本特性改动覆盖)
1. 单文件 HTML `docs/console/aisep-console.html`(零构建,无 server,无新运行时依赖)。
2. R1 Intake 表单:feature-id 输入 + 六字段(problem/users/成功指标/non-goals/appetite)+ track 三档选择器,每项带行内帮助与示例。
3. 实时生成区:按表单内容生成 `intent.md` 文本,结构与 `gate-intent` 校验判据精确一致(`## problem` / `## users` / `## 成功指标` / `## non-goals` / `## appetite` 各非空 + `track: <fast|standard|epic>` 行)。
4. 复制按钮(写剪贴板)+ 下载按钮(导出 intent.md 文件)。
5. Decision Inbox + Portfolio 总览外壳(取自原型),顶部显式标注"实时数据 = v1.1,当前为演示/快照"。
6. 部署物:同一 HTML 复制到 auction 仓 + auction 的 START-HERE 引导 + `specs/auction-mvp/` scaffold(使换会话可直接开始)。

### 显式 out-of-scope(R2 discovery out 表)
| 不做项 | 去向 |
|---|---|
| 实时多仓扫描 server + CLI 聚合导出器 | v1.1 |
| 前端直写 SSOT 文件 | v1.5(需写动作审计) |
| R2-R5 填表引导 | defer |
| 现成 AI 看板二开 | out(调研证伪) |
| 云端/多人/权限/桌面壳 | out |

## 验收标准(Gherkin)

### A. R1 表单产物的门禁兼容性(核心,可执行验证)

1. **表单产物一次过 gate-intent**
   - Given 用户在 R1 Intake 表单填入 feature-id 与六字段(均非空)、选 track=standard
   - When 把生成区输出的文本保存为 `specs/<feature-id>/intent.md` 并跑 `python -m aiforge gate-intent --feature <feature-id>`
   - Then 退出码 = 0(`gate-intent: approved`),receipt 落盘 —— 即表单产物结构与 gate 判据精确一致。

2. **空字段产物被 gate 拒(诚实:表单不假装通过)**
   - Given 用户漏填 non-goals(留空)
   - When 表单仍生成文本并保存为 intent.md 后跑 gate-intent
   - Then 退出码 = 1(诊断点名缺/空 non-goals)——表单生成区**同时**在客户端给出"必填项未填"提示(不阻止生成,但醒目标注),与 gate 判定一致不误导。

3. **track 三档都被接受**
   - Given 用户分别选 track=fast / standard / epic
   - When 各自产物存为 intent.md 跑 gate-intent
   - Then 三者退出码均 = 0(track 合法值)。

### B. 表单交互与引导

4. **六字段 + 帮助文本齐全**
   - Given 打开 aisep-console.html 的 R1 Intake
   - Then 可见 feature-id 输入 + problem/users/成功指标/non-goals/appetite 五个文本区 + track 选择器,每项有一句行内帮助与一个示例占位;无需用户预先知道"必填哪六项"。

5. **复制与下载可用**
   - Given 表单已填
   - When 点"复制" / "下载 intent.md"
   - Then 复制写入剪贴板(失败时降级提示手动选中)、下载导出名为 `intent.md` 的文件,内容 = 生成区文本。

### C. 总览外壳与零构建

6. **总览外壳标注非实时**
   - Given 打开 Inbox / Portfolio 标签
   - Then 顶部有醒目徽章注明"实时数据 = v1.1,当前为演示快照";不误导用户以为已接真实多仓数据。

7. **file:// 双击即开**
   - Given 直接双击 aisep-console.html(file:// 协议)
   - Then 表单与外壳正常渲染、生成/复制/下载可用,无需启动任何 server(v1 不依赖 fetch 跨仓)。

### D. 部署可用性(解锁 auction)

8. **auction 换会话可直接开始**
   - Given 部署后打开 auction 仓的 START-HERE 与控制台
   - When 用户填 R1 表单(feature-id=auction-mvp)生成 intent.md、由会话写盘并跑 gate-intent
   - Then 退出码 = 0,auction-mvp 的 R1 完成、可推进 R2——用户全程未在聊天里逐问回答六项。

## 非功能清单(P6)

- **错误处理**:表单为纯客户端,无后端错误面;剪贴板 API 不可用 → 降级为提示手动复制(不静默失败)。要求。
- **安全**:无 server、无网络请求、无外部 CDN 依赖(自包含,离线可用);不读 / 不写任何仓文件(v1 只生成文本交给用户/会话);不执行用户输入。要求。
- **可观测/审计**:v1 前端不产生 receipt(它不跑 gate);真正的审计锚仍是 gate-intent 写的 receipt(由会话/CLI 跑)。诚实标注:前端是"产物草稿生成器",非门禁。要求。
- **可访问性/认知负荷**:六字段一屏可见 + 行内帮助 + 示例,直接服务"降低认知负荷"成功指标。要求。
- **性能**:单文件静态页,无性能面。N/A。
- **兼容/向后**:不改任何现有 src/gate/契约;纯新增 docs 资产 + 部署物。要求。

## 追溯

> refs: discovery.md

- P1 规格先于代码:v1 范围由 R1-R4 产物(intent/discovery)冻结后才写本 spec 与实现。
- P2 可追溯:in 表每项 refs intent;本 spec refs discovery;部署到 auction 的产物同源。
- P6 非功能一等公民:错误降级/离线安全/认知负荷逐项列"要求"或"N/A"。
- 契约 06/08:v1 不引入 src 改动(docs-only),不需 feature 声明即可提交;若 v1.1 加 CLI 导出器则那时按 src 改动走 feature 声明。
- 诚实(P10):前端不写 receipt、不裁决;总览外壳标注非实时;表单不假装产物通过 gate(空字段如实提示 + gate 仍会拒)。
