## ADR-022 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板，经规划会话转达；修订 ADR-017 R7 与 ADR-019 第 4 款，两者原文不改）
- **决策**：
  1. **负例改认 CI 结果。** 改到负例清单里文件的 PR（清单不变，见 `AGENTS.md`「分支与合并」第 2 条），合并条件由「合并前在本地跑第四轮负例并全绿」改为「本次合并的 PR 头 H 上，CI 的 `negatives` job 结论为 `success`」。协调会话合并前用 `gh api "repos/Albertsun6/aisep/commits/H/check-runs?check_name=negatives&filter=latest" -q '[.check_runs[]|select(.app.slug=="github-actions")|.conclusion]'` 核对：输出必须恰好是 `["success"]`（只取 GitHub Actions 的最新一次运行，恰好一条），并把结论记进合并说明；H 上没有这次运行、还没跑完、多于一条，或结论不是 `success`（含 `cancelled`），就不合并。PR 同时改了 `.github/workflows/**` 时，它的 CI 跑的是 PR 自己的工作流定义，结论不可信，改为在本地跑负例并全绿。CI 不可用时也可以退回本地跑，这只是退路；两种情形都在合并说明里写明用了本地跑。
  2. **`negatives` 不升为所有 PR 的必需检查。** 它在 runner 上实测 304 到 691 秒，其余分片 150 到 290 秒，升为必需会让所有 PR（含纯文档）多等几分钟。以后升不升，仍由 Albert 定。
- **理由**：Albert 原话「如果替代后简化了，就替代」。替代后省掉协调会话每次合并前约 4 分钟的串行本地运行，也不再和本机其他任务抢 CPU；CI 的 `negatives` 与评审并行，不在关键路径上。只对改到负例清单的 PR 核对它，其余 PR 不受影响。
- **后果**：残余风险：PR 事件的 CI 跑在触发时的合并结果上，合并时 `main` 可能已前进，H 上的 `success` 不覆盖新的 `main`。兜底是 push 到 `main` 之后 `negatives` 还会再跑一次：协调会话合并这类 PR 后，在合并后核验里等新的 `main` 头 M 上的 `negatives` 跑完，用同一命令（H 换成 M）取结论写进 PR 评论，不是 `success` 就开 revert PR 并报告 Albert。ADR-017 后果中「R7 仍只靠执行合并的人照做，没有机制强制」仍然成立（核对由协调会话执行，不是分支保护）。`AGENTS.md` 负例条款同步改；协调脚本 `merge_pr.sh` 的 `NEG=1` 一步要改为核对 H 上 `negatives` 的结论（仓库外，由协调会话改）。本地 `tools/aisep.py test` 仍包含负例，开发时自测照旧。
- **补记（Albert 2026-11-27 定，拍板记录第 23 条④）**：合并后对 M 上 `negatives` 的核对改为异步，执行方式如下；第 1 款合并前对 H 上 `negatives` 的核对不变。
  - **不阻塞下一次合并。** 负例清单类 PR 合并后，协调会话不再原地等 M 上 push 触发的 `negatives` 跑完，可以接着合下一个 PR。
  - **批末统一核对。** 协调会话在一批合并结束时（最迟在下一批开始前），用第 1 款的命令（H 换成 M）逐个核对这一批里每个负例清单类合并的 M 上 `negatives`，输出必须恰好是 `["success"]`（还没跑完就等它跑完再判）。结论补记到对应 PR 的评论。合并说明里照旧记 `negatives` 的结论：H 上的结论之外，写「M 上 negatives 待批末核对」。
  - **失败处置。** 任何一个 M 的结论不是 `success`（含 `cancelled`、没有这次运行、多于一条），立刻为该 PR 开 revert PR 并报告 Albert，同时暂停后续负例清单类 PR 的合并，直到修复合入、修复后的 main 头上 `negatives` 为 `success`。
  - **理由**：`negatives` 在 runner 上单次 304 到 691 秒（第 2 款），加上排队，串行等待每次约 9–20 分钟，连续合并多个负例清单类 PR 时这段等待是关键路径上的主要耗时。合并前 H 上的 `negatives` 已经通过，M 上再跑一次只是兜「合并时 main 已前进」的残余（见「后果」），把它移出关键路径、集中在批末核对，换来串行合并提速。
  - **风险**：坏提交在 main 上的暴露窗口从「一次合并」拉长到「一批合并」；期间其他 PR 可能叠加合入，revert 时可能要连带处理冲突，也更难判定是哪一次合并引入的问题（每个 M 各有一次 push 触发的运行，可按 M 逐个定位）。
  - **缓解**：批末核对有明确的最迟时点（下一批开始前）；失败即开 revert PR；同时暂停负例清单类合并，不在已知有问题的 main 上继续叠加同类改动。非负例清单类 PR 不受暂停影响。
  - **参照**：这与合并队列的批量验证思路相近而不相同。GitHub merge queue 与 Bors 都是「先在临时分支上验证一批，通过才合入」，失败时把批拆开定位问题 PR（[GitHub：Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)、[bors-ng](https://github.com/bors-ng/bors-ng)）；本条借用的是「按批验证、失败即定位并处置」，但验证发生在合入之后，处置手段是 revert 加暂停。这样做的前提是 H 上已做过合并前验证，批末核对只兜 main 前进带来的残余，所以没有引入合并队列；是否改用 merge queue 做批量合并另行调研（拍板记录第 24 条）。
