# 成本台账(契约 09/10;STEP 0 v2 §4-M4 双口径)

> 每跑完一轮管线(或一个里程碑)追加一行。**schema_version: 1**——字段语义变化须升版并记迁移说明。
> 口径纪律:`requested_model`(请求什么)/`reported_model`(对方报什么)/`observed_source`(报告来源:
> api_response / tool_self_report / unobservable);**secret 不入账;不可观测就如实记,不编造**(契约 10)。
> `billing_regime` = 计费制度标签(如 `subscription-pre-2026-06-15`、`subscription-post-split`、`api-direct`),
> 标签不同的行**不可直接比较**(口径隔离,这正是该字段存在的原因)。

| date | scope | requested_model | reported_model | observed_source | effort | billing_regime | subscription_cost(/cost 口径) | hypothetical_api_cost | tokens(in/out) | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-11 | 自举试运行#1:toy-csv-export 全管线(requirements→gate-commit)+ STEP 0 D0~M4 落地,单一有头会话 | claude-fable-5 | claude-fable-5 | tool_self_report(会话 env 自报;API 响应字段会话内不可观测) | xhigh | subscription-pre-split | 未观测——**待用户在本会话跑 /cost 后补填** | 未观测(同左,/cost 有假想 API 口径) | 未观测(参考点:方案修订阶段 Workflow 子代理计 727k output tokens,不含主会话) | 有头会话含人机来回与评审,按上界口径使用(v1 §5 已知偏差);异构 cursor-agent 3 次调用走其自身订阅,不入本账 |
