# 契约 09 · 数据与安全契约(原则级)

> 本契约写原则与接口,不写复杂实现;实现随对应里程碑落地。1/2 由测试钉死;3~6 为**治理契约(流程执行,非机器钉死)**,违约在复盘登记。

1. **schema_version**:所有持久化 JSON(receipt、成本台账、角色输出)带整数 `schema_version`;**消费者必须忽略未知字段**(新增兼容字段不升版);语义变化才升版并在本文件登记迁移说明;消费者遇到高于自己认识的版本 → 退出码 3 + 可读诊断,不猜。(版本粒度:v1 用整数 + 未知字段忽略已够;需要时再细化。)
2. **hash 规范化**:`sha256` 对文件**原始字节**计算(读 `rb`,不做换行/编码/BOM 规范化);路径记**相对 repo root 的 POSIX 形式**;**不跟随 symlink**(gate 输入是 symlink → 3);目录不 hash;文件缺失走对应 gate 语义(如缺 spec = 1);大小写以文件系统实际为准。
3. **secret/PII redaction**:receipt、成本台账、ADR、PR 描述中不得出现 secret(API key/token/密码)——**secret 一律不存指纹**(含截断指纹),留痕只记"种类 + 定位提示"(如 "ANTHROPIC_API_KEY,见本机 env");身份信息只允许最小字段集 `{user, uid, hostname}`(契约 07 审计用),不记邮箱/电话等。`.env*` 已在 deny 与 gitignore。
4. **CI token 最小权限**:gates.yml 用默认 `GITHUB_TOKEN` 且显式声明最小 permissions(`contents: read` 起步),不用 PAT;任何提权在 workflow 文件内显式声明并注释理由。
5. **CODEOWNERS 责任边界**:受保护路径(契约 02)的 owner = 人类账号(repo 所有者);owner 变更本身也是受保护变更。(**2026-06-13 起 CODEOWNERS 为标注性**,契约 01 修订;本条责任归属语义不变。)
6. **break-glass 紧急放行**:仅 repo admin 可临时解除 branch protection 或强制合并;事后 **24 小时内**补一条 ADR(谁/何时/为何/影响面),且下一个 PR 必须全量重跑门禁。无 ADR 的 break-glass = 违约,复盘处理。

## 钉死方式

- 1:版本不识别 → 3 + 诊断(M1 测试);未知字段忽略(M1 测试);
- 2:hash 复算一致性 + symlink 拒绝(M1 测试);
- 3~6:流程契约,约定 + 复盘留痕执行(CODEOWNERS 强制与必须人审已撤销——契约 01 修订 2026-06-13)。
