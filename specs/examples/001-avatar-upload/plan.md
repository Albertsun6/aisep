# Plan: 用户头像上传

- 关联 Spec: F001（AC1/AC2/AC3）

## 1. 技术方案概述
新增 `POST /api/users/{id}/avatar`：鉴权 → 校验 → 存储（对象存储抽象）→ 返回 URL。

## 2. 模块边界与数据流

```mermaid
flowchart LR
  Client --> API["AvatarController"]
  API --> Validator["FileValidator (大小/类型/魔数)"]
  Validator --> Store["BlobStore 抽象"]
  Store --> Audit["AuditTrail"]
```

## 3. 接口契约
- `upload_avatar(user_id, file) -> {url}`；错误码 400/401/429/503。

## 4. 数据与迁移
- 用户表新增 `avatar_url` 字段（可空），非破坏性，低风险。

## 5. 满足验收标准映射
- AC1 → Store.put + 返回 URL
- AC2 → FileValidator 拒绝并返回 400
- AC3 → Store 异常 → 503 + 告警

## 6. 非功能需求落地
- 安全: Validator 校验魔数；Controller 鉴权。
- 可观测: 计数/耗时指标。
- 限流: 网关层每用户 10/min。
- 审计: 写 AuditTrail。

## 7. 测试策略
- 单元: Validator 边界（大小/类型/魔数）。
- 集成: 上传成功路径 + 存储不可用路径。
