# 契约 01 · 权威层级(=ADR-014)

| 层 | 机制 | 性质 | 谁能绕过 |
|---|---|---|---|
| **强制层(唯一)** | GitHub CI(gates.yml)+ branch protection + CODEOWNERS(按下方配置清单开启) | 对 AI 和人同等生效 | 仅 repo admin 经 break-glass(契约 09)显式改保护规则 |
| 反馈层 | 本地 pre-commit(`.githooks/` + `core.hooksPath`) | 快速反馈,**明文承认可旁路**(`--no-verify`、改 hooksPath) | 任何人/任何会话 |
| 会话护栏 | `settings.json` `permissions.deny` / 权限模式 | 会话内摩擦,防呆不防恶 | 改 settings、换无防护会话 |
| 建议层 | CLAUDE.md / constitution.md / skills 文案 | 模型可无视 | 模型自身 |

## 强制层机器可验证配置清单(M4 建远端时逐项核对)

当前生效配置(2026-06-13 修订后;原 M4 清单以删除线留痕,供历史追溯):

1. `Require status checks to pass` + required check 名 = **`gates`**(gates.yml 的 job 名,钉死不改)——**机器强制仅剩此项**(连带效应:未过检查的提交无法直推 main,合并路径事实上只有 PR);
2. ~~`Require a pull request before merging` + `Require review from Code Owners`~~ **已撤销(2026-06-13 修订,见下)**——不再强制人类 approval 与 Code Owners 审;
3. ~~`Do not allow bypassing the above settings`(含 administrators)~~ **实际配置 `enforce_admins=false`**(单人开发裁决,ADR-014):admin 对红 CI 的合并即 break-glass,须按契约 09 第 6 条 24h 内补 ADR,无 ADR = 违约;
4. `Require branches to be up to date before merging`(`strict=true`,2026-06-13 实测仍开启)。

人审 / 异构评审 / ADR 等均为**契约流程要求**(违约靠复盘登记),不再由 GitHub review 规则机器强制。

## 硬规则

1. **会话内的一切编排——Workflow、Agent 工具、长程会话、本地 git hooks / 会话 hooks——永远不是强制**。任何 ADR/文档不得以会话内构件作为权威或强制层的论据。理由:会话内约束是"被约束方自己执行的约束",定义落在模型可写路径。(注:GitHub 侧 webhook/App check 属远端强制链,不在此限。)
2. "已强制"三个字只允许指向按上述清单配置生效后的强制层。远端 + 配置清单生效之前,本 repo 不存在任何强制,只有反馈与建议。
3. 受 CODEOWNERS 保护的路径:`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`。

## 钉死方式

- M4 验收 = 配置清单逐项核对 + 三个攻击探针 PR 全被拦(无 feature 声明的 src 提交 → required check `gates` 红;同 PR 改空 gates.yml → Code Owners 审查拦;改已冻结 spec → `gates` 的 receipt 校验红 + Code Owners 拦);**2026-06-13 修订后**:两处"Code Owners 拦"失效,仅 `gates` 类拦截仍有效(如实标注,不假装拦截仍存在);
- 本契约文字本身受 CODEOWNERS 保护——**2026-06-13 修订后降为标注性**(见下)。

## 修订 2026-06-13:撤销强制人审(用户裁决)

- **撤销配置清单第 2 项**(PR approval + Code Owners review)。理由:单人仓中"自己 approve 自己驱动的产出"是虚假控制感(《需求工程化细化全流程》调研同款结论);main 非生产环境;变更可回退(P5)。
- **已知且接受的敞口**:治理面(`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`)的改动可由 agent 发 PR、CI 绿后自合,**无人审窄门**——**包括修改 `gates.yml`/门禁实现本身把 required check 改弱:只要改后的 CI 仍绿即可进 main**,发现与纠正依赖审计与回退,不依赖事前拦截。"CI 守卫 job(治理路径命中则要求 approval)"方案经评估被用户否决(单人仓多余)。补偿控制:P8 全量审计(receipt/审计流水/git 历史)+ 可回退。
- **重新评估触发条件**(满足任一必须重审本修订):仓库进入多人协作;main 接生产/部署链;harness 分发给 ≥2 个消费仓(同 PROPOSAL-harness-distribution 升级条件)。
- 硬规则第 3 条的 CODEOWNERS 路径清单**保留为标注性**(声明哪些路径属治理面),不再有机器强制效力;`.github/CODEOWNERS` 文件保留不删(多人化时一键恢复强制)。
