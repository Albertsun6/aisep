# feat-req-5step — requirements 阶段升级为 R1-R5 渐进细化

status: active
目标:把管线 requirements 阶段从"一步出 spec"升级为 R1-R5 五步渐进细化(AI 当放大器、人当范围决策者),并以两个新 gate(`gate-intent`/`gate-scope`)+ 升级版 `gate-spec` 把"人主导意图/范围决策"与"NEEDS CLARIFICATION 清零 + trace 链"变成机器可校验的硬门禁,防 AI 臆想需求。

## 背景

需求来源:`需求工程化细化全流程-完整报告.md`(57 源、经异构终审 Refine 收敛,§推荐 + §待验证风险)。报告结论:把 requirements 拆成 5 步渐进细化,杂交四个最优面——人写意图层(R1)、AI 放大的发现/范围切片(R2)、覆盖式澄清与硬 gate(R3)、追溯纪律(R5);并按变更规模分档(size-adaptive)。报告判据:范围决策(R2)与价值判断(R1/R4)是 LLM 实证最弱、臆想后果最重的环节,必须人主导;覆盖式澄清(R3)是已验证的防臆想机制;每步产物落盘 + 门禁与现有 receipt 链同构,是增量而非重构。

R1-R5 产物与人审点(编排为 sdlc-requirements skill 的建议层,本特性只实现门禁与机器校验):

| 步 | 产物 | 谁主导 | 本特性的机器强制 |
|---|---|---|---|
| R0 萃取 | `intent.md` 头部 source 出处 | AI 萃取要点/分歧/未决,人改定 | 无独立 gate(并入 gate-intent 必填节) |
| R1 意图简报 | `intent.md`(≤1 页) | 人主写,AI 只问不答 | **gate-intent**:必填节非空 + track 合法 |
| R2 发现与范围 | `discovery.md`(表格化) | AI 放大,人执刀圈范围 | **gate-scope**:in 项 refs intent + out 表非空 |
| R3 覆盖式澄清 | `clarifications.md`(append-only Q&A) | AI 提问,人作答 | gate-spec:spec 不得残留 `[NEEDS CLARIFICATION` |
| R4 优先级切片 | `scope.md`(首版切片) | 人决策,AI 算分 | 无独立 gate(建议层) |
| R5 spec 起草冻结 | `spec.md` | analyst 升级,在 R1-R4 约束下起草 | gate-spec:结构校验 + 清零 + trace 链 |

调研报告的待验证风险已并入本特性设计:页数预算(防审阅税)写入非功能项;门禁的"可追溯"校验沿用 gate-trace 的 `> refs:` 约定;"借机制不借实现"——5 步自实现于本管线门禁,不引入外部模板。

## 范围

### 实现项(本特性 src/tests 改动覆盖)
1. 新增 CLI 子命令 `gate-intent`:校验 `specs/<id>/intent.md`,写 receipt(gate 名 `gate-intent`)。
2. 新增 CLI 子命令 `gate-scope`:校验 `specs/<id>/discovery.md`,写 receipt(gate 名 `gate-scope`)。
3. `gate-spec` 升级:新增 NEEDS CLARIFICATION 清零检查(总是跑);新增 trace 链校验(仅当 intent.md 存在才跑)。
4. receipt 链扩展:`gate-commit` 对存在 intent.md 的 feature 要求链上含 gate-intent receipt;无 intent.md 的旧 feature 不受影响(向后兼容)。
5. `sdlc-requirements` skill 文档改造为 R1-R5 编排(建议层文案)。
6. to-be BPMN 流程图入库 `docs/flows/`(项目级约定)。

### 契约对齐(冻结约束,不在本特性内重定义)
- 退出码:`gate-intent`/`gate-scope`/`gate-spec` 均走契约 03 受控路径,只产生 0(approved)/1(rejected)/3(infra_error);三者**均无 needs_human(2)**。
- receipt:路径 `specs/<id>/gates/<gate-name>.json`、schema v1、字段与 hash 语义沿用契约 06,新 gate 仅扩展 `gate` 枚举值,不改 schema 结构。
- trace 语法:沿用 gate-trace 既有 `_REFS_RE`(行匹配 `> refs: <up>`),不新造引用语法。
- 验收结构校验:沿用 gate-spec 既有 `_spec_has_acceptance`(Gherkin/EARS/User Story+验收标记,≥40 字符),本特性不改其判据。

### 显式 out-of-scope(不做)

| 不做项 | 理由 |
|---|---|
| LLM 提问/萃取/算分逻辑本身(R0 萃取、R3 提问、R4 RICE 算分) | 那是 skill/agent 层(契约 04 无模型通道);本特性只做"产物落盘后的机器校验" |
| 任何 UI / 网页 / 启动台改动 | 本特性纯 CLI + 文档 |
| 改 CI 强制层语义 / receipt schema 结构 / 退出码契约 | 契约 02/03/06 冻结;本特性仅新增 gate 枚举值与校验逻辑 |
| 给新 gate 引入 needs_human(2) 态 | 三个 gate 是结构校验,无人审分支 |
| 对存量 spec 做迁移 / 让 CI 因旧 spec 变红 | 向后兼容渐进启用(见验收 11/12) |
| epic 子 feature 的"回流本流程"自动化 | 建议层流程,不做机器强制(gate-scope 只校验 in/out 表结构与 refs) |
| clarifications.md 的独立 gate | R3 清零并入 gate-spec,不单设 gate |
| scope.md(R4)的独立 gate | R4 是人决策建议层,不设机器门禁 |

## 验收标准(Gherkin)

> 载体:全部为 **[unittest]**(stdlib 可执行,临时 repo fixture)。受控退出码语义见契约 03;receipt 落盘语义见契约 06。

### A. gate-intent

1. **gate-intent 过(approved)**
   - Given 临时 repo 的 `specs/feat-x/intent.md` 含非空的必填节 problem / users / 成功指标 / non-goals / appetite,且头部 `track: standard`
   - When 跑 `python -m aiforge gate-intent --feature feat-x`(或对 intent.md 路径)
   - Then 退出码 = 0、stdout 含 `gate-intent: approved`,且 `specs/feat-x/gates/gate-intent.json` 落盘:`gate` = `gate-intent`、`feature_id` = `feat-x`、`exit_code` = 0、`decision` = `approved`、`inputs[0].path` = `specs/feat-x/intent.md` 且 `sha256` 对 intent.md 原始字节相符、`schema_version` = 1。

2. **gate-intent 拒(rejected)——必填节缺失或空**
   - Given `intent.md` 缺少 non-goals 节(或该节为空白)、其余必填节齐全、`track: standard`
   - When 跑 `gate-intent`
   - Then 退出码 = 1、stdout 含 `gate-intent: rejected` 且诊断点名缺失节;仍写 receipt:`decision` = `rejected`、`exit_code` = 1。

3. **gate-intent 拒——track 非法**
   - Given `intent.md` 必填节齐全但头部 `track: turbo`(不属于 {fast, standard, epic})
   - When 跑 `gate-intent`
   - Then 退出码 = 1、诊断点名 track 非法值与允许集合;receipt `decision` = `rejected`。

4. **gate-intent infra(infra_error)**
   - Given `intent.md` 不存在,或存在但内容无法按预期解析(例:必填节标题结构损坏到无法定位)
   - When 跑 `gate-intent`
   - Then 退出码 = 3、stderr 含可读诊断(出错环节 + 建议动作),不裸 traceback;不静默落 0。

### B. gate-scope

5. **gate-scope 过(approved)**
   - Given `specs/feat-x/discovery.md` 含一张 in 表与一张非空 out 表,且每个 in 项均带 `> refs: intent.md`(或 `intent#<条目>`)指向 intent 条目,intent.md 存在
   - When 跑 `python -m aiforge gate-scope --feature feat-x`
   - Then 退出码 = 0、stdout 含 `gate-scope: approved`,`specs/feat-x/gates/gate-scope.json` 落盘:`gate` = `gate-scope`、`inputs[0].path` = `specs/feat-x/discovery.md` 且 hash 相符、`decision` = `approved`。

6. **gate-scope 拒——in 项缺 refs**
   - Given `discovery.md` 的 in 表某项未声明 `> refs:` 到 intent(范围决策未挂回意图)
   - When 跑 `gate-scope`
   - Then 退出码 = 1、诊断点名未追溯的 in 项;receipt `decision` = `rejected`。

7. **gate-scope 拒——out 表为空**
   - Given `discovery.md` 的 out 表缺失或为空(没有显式排除 = 没做范围决策)
   - When 跑 `gate-scope`
   - Then 退出码 = 1、诊断点名 out 表为空;receipt `decision` = `rejected`。

8. **gate-scope infra**
   - Given `discovery.md` 不存在或无法解析出 in/out 两表结构
   - When 跑 `gate-scope`
   - Then 退出码 = 3、stderr 含可读诊断;不落 0。

### C. gate-spec 升级

9. **NEEDS CLARIFICATION 清零检查(总是跑)**
   - Given 任一 `spec.md`(无论是否存在 intent.md)正文残留字面 `[NEEDS CLARIFICATION` 标记
   - When 跑 `python -m aiforge gate-spec specs/feat-x/spec.md`
   - Then 退出码 = 1、诊断点名残留标记;
   - And Given 同一 spec 删除该标记后重跑,Then 该检查不再触发(其余既有结构校验照常)。

10. **trace 链校验(仅当 intent.md 存在)**
    - Given `specs/feat-x/intent.md` 存在,且 `spec.md` 通过既有结构校验但**缺** `> refs:` 到 scope/intent 条目的 trace 行
    - When 跑 `gate-spec`
    - Then 退出码 = 1、诊断点名 trace 链断裂(沿用 gate-trace 的 `> refs:` 约定);
    - And Given 同 feature 的 `spec.md` 补齐合法 `> refs:` 行后重跑,Then trace 检查通过。

### D. 三档 track 行为

11. **fast track 短路径**
    - Given `intent.md` 头部 `track: fast`、必填节齐全,且该 feature **无** scope.md / clarifications.md / discovery.md
    - When 依次跑 `gate-intent` 与 `gate-spec`
    - Then `gate-intent` = 0(必跑);`gate-spec` **不要求** scope/clarifications/discovery 存在,仅跑结构校验 + NEEDS CLARIFICATION 清零(+ 若 intent.md 存在则 trace 链);fast track 在 receipt/产物链中可被识别(intent.md 留有 `track: fast`)。

12. **standard track 全 5 步**
    - Given `track: standard`,intent.md + discovery.md(in/out 表 + refs)+ 无残留 clarification 标记的 spec.md(带 trace 行)俱全
    - When 依次跑 `gate-intent`、`gate-scope`、`gate-spec`
    - Then 三者均 = 0,各自落 receipt。

13. **epic track 范围结构**
    - Given `track: epic` 的 `intent.md`(program vision),其 `discovery.md` 的 in/out 表结构合法且 in 项 refs 到 intent
    - When 跑 `gate-intent` 与 `gate-scope`
    - Then 二者均 = 0;gate-scope **只**校验 in/out 表结构与 refs(不校验"子 feature 是否已切片回流"——那是建议层);epic 的子 feature 回流不被机器强制。

### E. receipt 链扩展与向后兼容

14. **gate-commit 要求 gate-intent 在链上(有 intent.md)**
    - Given staged 含 `src/` 改动并声明 `--feature feat-x`,`specs/feat-x/intent.md` 存在,但链上**缺** gate-intent receipt(只有 gate-spec)
    - When 跑 `gate-commit --feature feat-x`
    - Then 退出码 = 1、诊断点名缺 gate-intent receipt(沿用契约 06 "上游 receipt 齐全"语义)。

15. **向后兼容——无 intent.md 的旧 feature 不受影响**
    - Given staged 含 `src/` 改动声明 `--feature feat-legacy`,该 feature **无** intent.md(存量特性),链上有合法 gate-spec receipt
    - When 跑 `gate-commit --feature feat-legacy`
    - Then 不因缺 gate-intent receipt 而拒(该项检查不触发);gate-commit 结论由既有规则裁定。

16. **向后兼容——存量 spec 不被新检查变红**
    - Given 存量 `spec.md` 无 `[NEEDS CLARIFICATION` 标记、其 feature 无 intent.md
    - When CI/本地跑 `gate-spec`(或 `--check`)
    - Then NEEDS CLARIFICATION 清零检查天然过(无标记)、trace 链校验不触发(无 intent.md);结论与升级前一致,不因本特性变红。

## 非功能清单(P6)

- **错误处理**:三个新增/升级 gate 在受控路径内任何未预期异常 → 退出码 3 并向 stderr 打印可读诊断(出错环节 + 建议动作),不裸 traceback、不静默落 0(契约 03 fail-closed)。文件缺失/不可解析 → 3;结构校验未过(必填节空/track 非法/refs 缺/out 空/残留标记/trace 断)→ 1。要求。
- **安全**:gate 只读 intent.md/discovery.md/spec.md,不执行其内容、不调模型(契约 04)、零网络。读路径沿用既有 `_read_no_symlink` 防软链穿越(不经软链读到 repo 外)。feature_id 沿用契约 06 的 `^[a-z0-9_][a-z0-9._-]{0,99}$` 校验防路径穿越。要求。
- **可观测/审计**:每次 gate 运行由真实命令写出 receipt(契约 06,gate 名/feature_id/exit_code/inputs/hash/created_at),作为"未跳阶段"的机器证据;stdout 打印 `<gate>: <decision> (exit N)`;拒绝时点名具体失败项(哪个必填节/哪个 in 项/哪条标记)。本地 receipt 是反馈层,权威消费在 CI(契约 06)。要求。
- **限流/并发**:N/A——CLI 单次同步执行、无后台任务、无外部调用,无限流面。
- **页数预算(防 markdown 审阅税,调研待验证风险④)**:intent.md ≤ 1 页、scope.md ≤ 1 页、discovery.md 表格化呈现。**本预算为建议层约束(写入 skill 文案与本 spec),本特性不做机器强制超页拒绝**(避免误伤;诚实标注:页数硬门禁未实现)。要求(建议层)。
- **性能**:N/A——单文件解析、毫秒级;无性能指标要求。
- **合规/向后兼容**:渐进启用——trace 链校验仅 intent.md 存在才跑、NEEDS CLARIFICATION 清零对无标记 spec 天然过、gate-commit 的 gate-intent 要求仅对有 intent.md 的 feature 生效;CI 不因存量 spec 变红(验收 15/16)。要求。

## 追溯

> refs: 需求工程化细化全流程-完整报告.md (§推荐 R1-R5 + §待验证风险)

- P1 规格先于代码:本特性把 R1-R5 的"意图/范围/澄清/trace"四道人审点变成冻结前的机器门禁,强化"代码服务于规格"。
- P2 可追溯:gate-scope 强制 in 项 refs intent、gate-spec 强制 spec trace 回 scope/intent,沿用 gate-trace 的 `> refs:` 链,把 spec→scope→intent 接入既有追溯链路。
- P6 非功能一等公民:错误处理/安全/审计/页数预算逐项列为"要求"或"N/A+理由",不靠 agent 自觉。
- 契约 03:三 gate 退出码 0/1/3,无 needs_human;契约 06:receipt 扩展仅加 gate 枚举值,schema 不变;契约 02:不改 CI 强制层语义,向后兼容渐进启用。
- 契约 08:analyst 升级仍守双宿主(file-in/file-out,JSON 落 outputs/),定序逻辑不进 prompt。
