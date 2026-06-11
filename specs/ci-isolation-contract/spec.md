# ci-isolation-contract — 验证器隔离契约的环境感知测试

status: active
目标:让断言"管线 DONE"的测试在无真隔离后端的环境(如 Linux CI)下,改为断言 C4 fail-closed 的 BLOCKED 契约——使基线 CI 绿,且**不削弱** verifier 的隔离安全。

## 背景与范围

- 背景:`verifier_node` 在 `select_isolated_or_none() is None` 时 fail-closed 为 `BLOCKED`(C4/P4:无验证通过的真隔离绝不执行生成代码)。真隔离后端当前仅 macOS `sandbox-exec`(container 后端被 `prefer_container=False` 排除,标注 experimental)。
- 问题:3 个测试(`test_feature_runs_to_done`、`test_high_risk_triggers_hitl_then_resume`、`test_run_eval_dataset_metrics`)无条件断言 happy 路径(DONE / 3/8),只在 macOS 通过;Linux CI 上 fail-close → BLOCKED → 测试红。此前无远端、CI 从未运行,故隐藏。
- 范围内:这 3 个测试改为**环境感知**——隔离可用则断言原 happy 契约,不可用则断言 fail-closed 契约。
- **不做**:不改 `verifier_node`/`select_sandbox` 的 fail-closed 行为(那是 C4 安全,削弱即违 P4);不在 CI 安装 docker/启用 container 后端(experimental,scope 外)。

## 验收标准(Gherkin)

- Given 运行环境有验证通过的真隔离后端(`select_isolated_or_none()` 非 None)
  When 跑 `test_feature_runs_to_done`
  Then 断言 `status == DONE` 且全链 artifact 齐(原契约不变)。
- Given 运行环境无真隔离后端(`select_isolated_or_none() is None`)
  When 跑同一测试
  Then 断言 `status == BLOCKED` 且 `verification.reason == "no-isolation"`(C4 fail-closed 契约)。
- Given 任一环境
  When 跑 `make test`
  Then 全绿(macOS 与 Linux CI 一致通过)。

## 非功能清单(P6)

- 错误处理:N/A(纯测试断言分支);
- 安全:**核心约束**——不得新增任何"无隔离也放行"的代码路径;测试只观察,不改变 verifier 行为;
- 可观测:无隔离分支在测试名/注释中标明断言的是 fail-closed 契约,避免被误读为"功能缺失";
- 限流/审计:N/A。
