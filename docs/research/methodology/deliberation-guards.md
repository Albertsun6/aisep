> **来源**:老库 AISEP/.metap/engines/deliberation.yaml(quality_guards / record_template)。本文为方法论短笔记,**只抽取反模式守护**,不搬整个辩论引擎(契约 01)。

# 辩论/异构评审的反模式守护(deliberation guards)

老库 MetaP 辩论引擎沉淀的三条守护,可作为本项目 `/debate-review`、`/survey`、异构评审(原则⑤)的方法论补充:

1. **虚假共识检测 → 强制 devil's advocate**:多角色辩论若过快收敛到"一致同意",强制指派一个唱反调角色重新质疑——共识太顺往往是盲区共享(呼应原则⑤"同一模型盲区系统性")。
2. **`[unsubstantiated]` 标注**:任何"普遍认为/共识是"式无源结论必须标注未证实,或关联到具体来源(呼应老库 §15 来源诚实原则)。
3. **立场锁定校验**:博弈中每个角色坚守其立场约束,不可被其他角色同化(否则 N 个角色退化成 1 个声音)——异构评审里 cursor/Claude 必须各自独立,不互相找补。

## 辩论记录结构(可复用)
共识点(结论+支撑+confidence)/ 分歧点(争议点+各方观点+各方 confidence)/ 行动建议 / 元认知洞察。本项目的 `REVIEW-debate.md` 判断矩阵即此结构的落地。
