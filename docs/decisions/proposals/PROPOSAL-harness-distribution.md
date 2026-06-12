# PROPOSAL — AISEP harness 多项目分发模型(上线形态)

- 状态:**方向已裁决、分阶段实施**(用户 2026-06-13 提出"正式上线后每个项目单独复制一份 harness?还是什么方式")
- 关联:deploy-setup skill(现状路径)、契约 01(权威分层)、P9(选型可替换)

## 结论:按权威层拆分发方式,pilot 期先 vendored

harness 三种成分的权威等级不同,分发方式不同:

| 成分 | 权威层 | pilot 期(1 个消费仓) | 上线形态(≥2 消费仓) |
|---|---|---|---|
| CI 门禁(.github/workflows/gates.yml) | 强制层 | vendored 快照 | **reusable workflow**:业务仓一行 `uses: <org>/aisep/.github/workflows/gates.yml@v1`,锁 tag,中心升级 |
| 引擎(src/aiforge,gate CLI) | 反馈层 | vendored 快照 | **pip 包** `aiforge==x.y`(核心纯标准库,发包零负担;receipt 已有 aiforge_version 可追溯) |
| 流程资产(.claude/ skills+agents、specs/contracts、constitution.md) | 建议层 | vendored 快照 | **模板 + update 重放**(copier 类),允许各项目本地化裁剪 |

## pilot 期纪律(现在生效)

1. 业务仓 harness 用 deploy-setup 从 AISEP main 拷快照;
2. 部署记录写进业务仓(`docs/HARNESS-VERSION.md`:来源 repo + commit + 日期)——哪个版本的管线跑出哪些摩擦,可追溯;
3. 升级 = AISEP 改进合 main 后重新同步快照,更新部署记录。

## 升级触发条件(满足任一即立 feature 实施上线形态)

- 消费仓 ≥ 2 个;
- 同一摩擦修复需要向业务仓手动同步**第二次**(说明同步成本已真实发生);
- 业务仓团队成员 > 1 人(强制层不能再依赖"自己拷贝自己")。

## 被否的选项(留痕防重辩)

- **git submodule**:体验差、心智成本高,团队协作易出错;
- **全 monorepo**(业务和 harness 同仓):业务代码与方法论仓互相污染,git 历史混杂(2026-06-13 已按此理由选择业务独立仓);
- **一步到位发包**:pilot 期只有一个消费仓,是给不存在的规模做基建(② Simplicity First)。
