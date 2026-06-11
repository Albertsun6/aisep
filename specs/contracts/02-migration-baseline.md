# 契约 02 · 基线与受保护路径

- **基线**:tag `archive/pre-harness`(D0,main 合并 `chore/health-improvements` 后)。基线验收命令 = `make test` + `make arch`,任何时点回到基线两者必须绿。
- **就地实施**:STEP 0 在本 repo 实施(ADR-013),不存在第二个本地 repo;"新项目门面" = push 本 repo 到新建 GitHub 远端。
- **受保护路径**(M4 起由 CODEOWNERS 强制,之前为约定):`.github/`、`specs/contracts/`、`constitution.md`、`.githooks/`。
- **契约变更流程**:PR + 人审 + 对被改契约重跑异构(cursor-agent)评审;评审记录入 PR 描述或 ADR。
- **specs/<id>/spec.md 冻结语义**:过 `gate-spec` 后冻结,改动按上述变更流程走(见契约 08)。
