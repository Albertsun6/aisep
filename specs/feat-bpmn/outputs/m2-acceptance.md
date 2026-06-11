# feat-bpmn · M2 验收执行记录(T9)

> refs: ../spec.md(验收 9-12/14/15)
> 执行:2026-06-12,同 m1-acceptance.md 的方式(chrome-devtools-mcp 亲手操作)+ stdlib unittest + headless 烟测。

## 逐条结果

| 验收 | 判据 | 结果 | 证据 |
|---|---|---|---|
| 9 导出契约 | 字段恰为 allowlist/降序并列规则/`<` 全转义/只读/fail-closed | **PASS** | unittest TestExportContract 6 项全绿(tests/test_bpmn_status.py);真仓实跑 `aiforge bpmn-status --emit-pipeline` 产物正常 |
| 10 节点 id 契约 | sdlc-pipeline.bpmn 含映射表全部 6 个 stage id;入库 sdlc-pipeline.js 与 .bpmn 字节一致 | **PASS** | unittest TestPipelineIdContract 2 项绿 |
| 11 状态着色+下钻 | 项目模式渲染六阶段;徽章三态可区分;点节点出详情(gate/decision/时间/feature 全转义) | **PASS** | 浏览器实测:badges=`[gate-spec: approved(绿), gate-trace: approved, 无门禁×3, gate-judge: approved, gate-commit: 暂无数据]`;点 stage-requirements → 详情=`gate-spec → approved / 2026-06-12T01:16:57 / feat-bpmn`(**真实审计数据**,正是本特性 spec 重冻结那次运行);截图 screens/07-project-mode-full-layout.png |
| 12 缺损降级 | 状态文件缺失→管线图仍渲染(备援源)+徽章"暂无数据"+不崩 | **PASS** | headless 探针(T8 commit 前):移走 sdlc-status.js 后四项断言全过(图渲染/暂无数据/降级原因可见/水印在);非 dict/缺字段路径由 `statusData()` 类型检查同路径覆盖 |
| 14 XSS(M2 面) | 徽章/详情只经 DOM 节点+textContent 构造(无 HTML 字符串拼接);静态探针禁 HTML 注入 API | **PASS**(实现侧+静态) | 代码路径(badgeFor/showStageDetail 全 textContent)+ unittest test_no_dynamic_innerhtml;含哨兵的状态数据 fixture 未单独注入实测——徽章文本与详情文本与 M1 验收 13 同一渲染纪律 |
| 15 水印(M2 布局) | 详情面板+XML 面板全开时水印未遮挡 | **PASS** | 同 m1-acceptance.md 第 15 条(一次探针覆盖两个里程碑的最拥挤布局) |

## 备注(如实)
- 徽章里 `gate-commit: 暂无数据` 是**正确行为**:sdlc-status.js 是 T7 时生成的快照,之后的 gate-commit 运行不会自动进快照——重跑 `aiforge bpmn-status` 即刷新(spec"重跑才更新"边界)。
- 验收 14 的"哨兵状态数据"端到端注入(伪造含 payload 的 sdlc-status.js)未实测,依据为同一 textContent 纪律 + 静态探针;T10 异构评审时点名请评审员审这一面。
- 截图证据:screens/07-project-mode-full-layout.png(全开布局)、screens/07b-project-mode-clean.jpeg。
