# 契约 02 · 基线与受保护路径

- **基线**:tag `archive/pre-harness` → **commit `0c1c620`**(immutable SHA 为准,tag 仅是别名;远端建立后将其设为 protected/annotated tag)。
- **基线验收**:在**记录环境**(Python 3.11+,`requirements-dev.txt` 锁定的 ruff/import-linter 版本)下 `make test` + `make arch` 必须绿;环境漂移导致的红不构成基线失效,按 infra 处理。
- **就地实施**:STEP 0 在本 repo 实施(ADR-013),不存在第二个本地 repo;"新项目门面" = push 本 repo 到新建 GitHub 远端。
- **生效语义**:本契约包自评审落改之时起在**约定层**生效(变更须走下述流程);**远端强制**自 M4 配置清单(契约 01)生效起。两者不混淆(契约 01 硬规则 2)。
- **受保护路径**(M4 起 CODEOWNERS 强制;**2026-06-13 起降为标注性**,契约 01 修订):`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`。
- **契约变更流程**:PR(required check 为机器强制)+ CI 复验 + 对被改契约重跑异构评审(cursor-agent **或** codex,满足契约 05 的异构定义;皆不可用 → 人审替代并留痕"异构缺席");评审记录入 PR 描述或 `REVIEW-*.md`。**强制人审已撤销**(契约 01 修订 2026-06-13),人审改为自愿;异构评审与评审留痕是**契约流程要求**(非 GitHub 强制,违约靠复盘),要求**不变**。
- **feature ↔ 代码映射 = 声明制**:提交含 `src/`、`tests/` 改动时必须声明所属 feature(`--feature <id>` 或 env `AIFORGE_FEATURE`),声明的 id 须有合法 receipt 链(契约 06);无声明 → `gate-commit` 退出码 1。纯文档/配置改动不要求。
- **specs/<id>/spec.md 冻结语义**:过 `gate-spec` 后冻结,改动按契约变更流程走(见契约 08)。
