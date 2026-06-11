# feat-launcher-outputs · 异构评审辩论记录(T4,契约 05 / 原则⑤)

> 评审者:cursor-agent(自报 GPT-5.5),2026-06-12;对象:全特性 diff(899 行)+ 冻结 spec/plan + 验收记录。
> verdict:**approve-with-fixes**(1 Med,已落改并补反例测试)。

## 判断矩阵

| # | 评审发现 | 裁决 | 落点 |
|---|---|---|---|
| Med:`gates` **父目录**软链可串读——`specs/feat-a/gates -> ../feat-b/gates` 被 resolve().is_relative_to(specs_root) 放行,feat-a 展示 feat-b 的 receipt,破坏 receipt↔feature 绑定 | **接受**(真洞) | 读 gates 前加 `gdir.is_symlink()` 守卫(与 outputs 同款,我 outputs 查了父目录软链却漏了 gates);反例进测试 test_gates_parent_symlink_blocked(攻击者特性软链借受害者 receipt → 断言 gates 为空) | launcher_data.py;tests |

## 评审确认无问题的面(steelman 摘录)
- `_safe_in_specs` 对"中间目录软链指向 specs 外"挡住了(resolve 落 specs 外 → is_relative_to false);评审未能仅靠 diff 构造出读 `../../.ssh` 的路径。TOCTOU 理论存在但需本机并发写权,非外部 PR 静态 diff 可稳定利用。
- `renderGate` 的 split 重组即使 id 写成 `</code><img>` 也只进 textContent/文本节点,只影响显示分段不执行;全页确无五类注入 API。
- 数据不入库取舍合理:消除"提交任意 JS 载荷"入库攻击面;留下的本地草稿固化是本地可见、默认不扩散,spec 已诚实写明。
- spec/plan/验收记录三者一致,验收 9 的字段面与实现路径对得上。

## 复盘(作者自记)
- 教训:**防护要对称**。outputs 我查了父目录软链(`odir.is_symlink()`),gates 却只查到文件级——同一类防护在并列代码路径上漏了一处,正是异构评审擅长抓的"不对称疏漏"。修复后两条路径守卫一致。
- 与 feat-bpmn 的 symlink 教训连起来看:软链穿越是这套"读 specs 全文"导出器的系统性风险面,父目录/文件/中间段都要覆盖——已沉淀进测试矩阵。
