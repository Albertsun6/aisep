# 契约 09 · 数据与安全契约(原则级)

> 本契约写原则与接口,不写复杂实现;实现随对应里程碑落地。

1. **schema_version**:所有持久化 JSON(receipt、成本台账、角色输出)必须带 `schema_version` 整数字段;消费方遇到高于自己认识的版本 → 按契约 03 报 3(infra_error),不猜。版本演进 = 新增字段向后兼容则不升版,语义变化必须升版并在本文件登记迁移说明。
2. **hash 规范化**:`sha256` 一律对文件**原始字节**计算(读 `rb`,不做换行/编码/BOM 规范化);hash 对象是文件而非字符串拼接。理由:规则唯一且无歧义,跨平台可复算。
3. **secret/PII redaction**:receipt、成本台账、ADR、PR 描述中**不得出现** secret(API key/token/密码)与个人敏感信息;留痕需要引用时记"已脱敏 + 指纹前 8 位"。`.env*` 已在 deny 与 gitignore。
4. **CI token 最小权限**:gates.yml 的 `GITHUB_TOKEN` 用默认最小 permissions(`contents: read` 起步,按需显式加),不用 PAT;任何提权在 workflow 文件内显式声明并注释理由。
5. **CODEOWNERS 责任边界**:受保护路径(契约 02)的 owner = 人类账号(repo 所有者);owner 变更本身也是受保护变更。
6. **break-glass 紧急放行**:仅 repo admin 可临时解除 branch protection 或强制合并;事后 **24 小时内**补一条 ADR(谁/何时/为何/影响面),且下一个 PR 必须全量重跑门禁。无 ADR 的 break-glass = 违约,复盘处理。

## 钉死方式

- 1/2 随 M1 测试钉死(版本不识别 → 3;hash 复算一致);
- 3~6 为流程契约,由 CODEOWNERS + 人审执行,违约在复盘中登记。
