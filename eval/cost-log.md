# 成本台账(契约 09/10;STEP 0 v2 §4-M4 双口径)

> 每跑完一轮管线(或一个里程碑)追加一行。**schema_version: 1**——字段语义变化须升版并记迁移说明。
> 口径纪律:`requested_model`(请求什么)/`reported_model`(对方报什么)/`observed_source`(报告来源:
> api_response / tool_self_report / unobservable);**secret 不入账;不可观测就如实记,不编造**(契约 10)。
> `billing_regime` = 计费制度标签(如 `subscription-pre-2026-06-15`、`subscription-post-split`、`api-direct`),
> 标签不同的行**不可直接比较**(口径隔离,这正是该字段存在的原因)。

| date | scope | requested_model | reported_model | observed_source | effort | billing_regime | subscription_cost(/cost 口径) | hypothetical_api_cost | tokens(in/out) | notes |
|---|---|---|---|---|---|---|---|---|---|---|
