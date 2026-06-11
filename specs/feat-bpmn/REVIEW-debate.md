# feat-bpmn · 异构评审辩论记录(T10,契约 05 / 原则⑤)

> 评审者:cursor-agent(自报 GPT-5.5),2026-06-12;对象:全特性 diff(main...worktree-feat-bpmn,
> 剔除 vendored minified bundle 本体)+ 冻结 spec/plan + 验收记录。
> 评审 verdict:**approve-with-fixes**。以下逐条裁决,反例一律进测试。

## 判断矩阵

| # | 评审发现 | 裁决 | 落点 |
|---|---|---|---|
| High:恶意 vendor JS + 配套新 SHA256SUMS 在同一 diff 内自洽,扫描器豁免被绕过(SUMS 自证不证来源) | 问题**接受**(真洞);修法**部分接受** | **问题真实**:豁免的信任根是 SUMS,而 SUMS 与文件可在同一 PR 里一起伪造。**但评审建议的修法(SUMS 在 diff 中变更 → 豁免失效)会让豁免成为死代码**:任何合法 vendor 变更都必须同步改 SUMS(否则哈希不符),于是豁免永不生效,vendor 永远 needs_human,而 CI 不消费 ack(契约 07)→ 回到"CI 永红"原点,特性自毁。**替代机器修法**:CI 新增 `vendor-provenance` 步(scripts/verify_vendor_provenance.py)——vendor 变更时对 npm registry 重验:先验官方 tarball sha512 integrity,再要求每个 vendored 文件 sha256 ∈ 官方 tarball 文件集。registry 是 PR 作者无法伪造的外部信任根,合法更新自动绿、伪造内容必红、网络不可达 fail-closed。已对真实 vendor 实跑通过([OK] bpmn-js@18.18.0)。 | gates.yml +1 步;scripts/verify_vendor_provenance.py;spec 验收 17 修订 |
| Med:豁免读磁盘而非 staged blob——staged 篡改 + 磁盘洗白可骗过本地 gate | **接受** | `_vendor_content()`:内容源优先 git index(将被提交的版本),**index 与磁盘分叉即拒**;反例进测试(⑩ test_staged_disk_divergence_not_exempt,真 git repo 构造分叉) | harness.py;tests ⑩ |
| Med:vendor 路径未规范化,`..` 组件可参与解析 | **接受** | `_clean_vendor_rel()`:拒绝绝对路径与 `.`/`..`/空段,diff 路径与 SUMS 条目两侧都过;反例进测试(⑨ test_path_traversal_not_exempt) | harness.py;tests ⑨ |
| Low:plan"不动 harness/gates/quality;门禁链零改动"与实际改动自相矛盾(红线句已改,边界节漏改) | **接受** | 边界节改为如实陈述:门禁链改动仅限设计点 11 + CI provenance 步 | plan.md |
| 建议:验收 14 哨兵状态数据补端到端浏览器探针 | **接受** | 伪造含 payload 的 `AIFORGE_STATUS`(四字段全塞)→ 项目模式徽章+详情实测:`__pwned` undefined、零注入节点、字面呈现;顺带二证验收 12 备援源 | m2-acceptance.md 更新 |

## 评审确认无问题的面(steelman 摘录)
vendor 锁版本 + SHA256SUMS 复核把供应链面显式化;工作台动态 DOM 全走 textContent/value 无 HTML 注入 API;句柄替换 fail-closed;`<`→`\u003c` 全量转义足以挡 `</script>`/`<!--`(JSON 自身处理引号/反斜杠);bpmn_status 只读与 fail-closed 主路径成立;验收记录诚实自报缺口。

## 复盘(作者自记)
- 自报的缺口(验收 14 未实测)被评审点名——"自己挑明"不等于"可以不做",评审价值在于把它从备注变成行动。
- High 的教训:给门禁开任何豁免,信任根必须在 **PR 作者控制之外**(外部 registry / 已落地历史 / 人),仅靠 PR 内部自洽性 = 可伪造。
