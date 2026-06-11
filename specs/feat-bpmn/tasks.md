# feat-bpmn · tasks(decompose)

> refs: plan.md

> blast radius 基线(P5,config.py):单次变更 ≤10 文件 / ≤400 行,超限降人审。
> 有头模式下"人审"= 用户在实现循环里逐任务 review diff——超限任务**诚实标注**,不拆碎规避。
> 每任务 = 一个自洽绿 commit(任务内 TDD:先写测试看红 → 实现转绿;commit 时全绿)。
> src/tests 改动的提交一律带 feature 声明(`AIFORGE_FEATURE=feat-bpmn` 或 `gate-commit --feature feat-bpmn`)。

## M1 — 通用工作台

### T1 vendor 资产落地 + 完整性测试
- 满足:验收 16、验收 1(物料半边);plan 设计点 1。
- 影响:`docs/vendor/bpmn-js@18.18.0/**`(JS+3 组 CSS+bpmn-font+LICENSE+SHA256SUMS)、`tests/test_bpmn_workbench.py`(新:vendor 完整性断言)、`specs/feat-bpmn/plan.md`(回填供应链附录)。
- 验证:`shasum -a 256 -c docs/vendor/bpmn-js@18.18.0/SHA256SUMS`;`PYTHONPATH=src python3 -m unittest tests.test_bpmn_workbench -v`;`PYTHONPATH=src python3 -m aiforge gate-trace specs/feat-bpmn/`(plan 改动后重跑刷新 receipt)。
- **blast radius:超限(第三方资产文件数 >10)→ 按 P5 降人审:请用户过目来源 URL + npm integrity 比对记录 + SHA256SUMS,确认后才 commit。**

### T1b 门禁扫描器 vendor 哈希验证豁免(2026-06-12 修订新增,先于 T1 commit 落地)
- 满足:验收 17;plan 设计点 11。背景:T1 预演发现 minified bundle 触发 judge `eval/exec` 扫描 → CI 永红(不消费本地 ack);用户裁决改扫描器。
- 影响:`src/aiforge/harness.py`(code_only_diff + 两处调用)、`tests/test_judge_vendor_exempt.py`(新,七路径断言)。
- 验证:`PYTHONPATH=src python3 -m unittest tests.test_judge_vendor_exempt -v`;`make test` 全绿;落地后对已 staged 的 vendor 重跑 `gate-judge --staged` 应转 approved。
- blast radius:2 文件,内;**动门禁核心 → T10 异构评审必含本改动**;src 改动带 feature 声明。

### T2 fixtures 入库 + 健全性测试
- 满足:验收 5/13 的前置物料;plan 设计点 3。
- 影响:`specs/feat-bpmn/flows/fixture-order.bpmn`、`specs/feat-bpmn/flows/fixture-xss.bpmn`、`tests/test_bpmn_workbench.py`(扩:ElementTree 断言 pool/lane×2/gateway/边界事件)。
- 验证:`PYTHONPATH=src python3 -m unittest tests.test_bpmn_workbench -v`。
- blast radius:3 文件,内。

### T3 workbench M1 页面 + 零外呼静态探针
- 满足:验收 1(行为)/2/3/4/6/7/8/13/15 的实现侧;plan 设计点 2/4(探针半边)。
- 影响:`docs/bpmn-workbench.html`(新,页内 7 模块:Editor 壳/FileIO/XmlPanel/DirtyGuard/转义/水印保留区/PerfGuard)、`tests/test_bpmn_workbench.py`(扩:零外呼探针——相对路径 allowlist + 无绝对 http(s) 调用)。
- 验证:`PYTHONPATH=src python3 -m unittest tests.test_bpmn_workbench -v`;`open docs/bpmn-workbench.html` 冒烟(建模/保存/联动各一次)。
- **blast radius:2 文件但 HTML 必超 400 行 → 标注人审:diff 由用户在实现循环 review。**

### T4 M1 手动验收执行(记录入库)
- 满足:验收 1/3/4/6/7/8/13/15 的执行与留痕。
- 影响:`specs/feat-bpmn/outputs/m1-acceptance.md`(逐条编号步骤 + pass/fail + 哨兵断言结果)。
- 验证:该记录本身;用户抽查任一条可复现。
- blast radius:1 文件,内。

### T5 AGENTS.md 呈现约定
- 满足:spec"存放与呈现约定";plan 设计点 5。
- 影响:`AGENTS.md`(+1 行:新增流程图默认 BPMN,存放约定)。
- 验证:`git diff` 仅 1 行新增。
- blast radius:1 文件,内。

## M2 — 项目状态接入

### T6 管线 BPMN 图 + 节点 id 契约测试
- 满足:验收 10;plan 设计点 6(.bpmn 半边)。
- 影响:`docs/flows/sdlc-pipeline.bpmn`(6 阶段,id 按 spec 映射表)、`tests/test_bpmn_status.py`(新:解析断言 6 个 stage id 齐)。
- 验证:`PYTHONPATH=src python3 -m unittest tests.test_bpmn_status -v`。
- blast radius:2 文件,内。

### T7 状态导出器 + CLI + 备援源
- 满足:验收 9 + 设计点 6(.js 备援半边)/7/8;依赖 T6。
- 影响:`src/aiforge/bpmn_status.py`(新)、`src/aiforge/cli.py`(+`bpmn-status` 子命令,lazy import)、`tests/test_bpmn_status.py`(扩:allowlist/降序并列/`<` 转义/只读/pipeline.js↔bpmn 一致性)、`.gitignore`(+`docs/flows/sdlc-status.js`)、`docs/flows/sdlc-pipeline.js`(由 `--emit-pipeline` 生成,入库)。
- 验证:`PYTHONPATH=src python3 -m unittest tests.test_bpmn_status -v`;`PYTHONPATH=src python3 -m aiforge bpmn-status` 实跑产出检查;`make test` 全绿;`make arch`(.importlinter 分层不破)。
- blast radius:5 文件,内(src 改动,提交带 feature 声明)。

### T8 workbench 项目模式
- 满足:验收 11/12/14 实现侧 + 15(M2 布局);plan 设计点 9;依赖 T3/T7。
- 影响:`docs/bpmn-workbench.html`(扩:双 script 备援加载/徽章三色/点击下钻/三种缺损降级)。
- 验证:零外呼探针仍绿;`open` 手动冒烟(有状态/无状态两态)。
- blast radius:1 文件(增量行数若超 400 → 同 T3 标注人审)。

### T9 M2 手动验收执行(记录入库)
- 满足:验收 11/12/14/15(M2 布局)的执行与留痕。
- 影响:`specs/feat-bpmn/outputs/m2-acceptance.md`。
- 验证:同 T4。
- blast radius:1 文件,内。

## 收尾(流程任务)

### T10 异构评审 + 落改(契约 05 / 原则⑤)
- 满足:作者模型不得自审自过;评审反例必须加进测试。
- 影响:`specs/feat-bpmn/REVIEW-debate.md`(辩论记录:接受/部分/反驳+理由)+ 评审逼出的代码/测试改动(另计 blast radius)。
- 验证:cursor-agent 对全特性 diff 的 verdict;落改后 `make test` 全绿。

### T11(属阶段 5,列出供导航,不在本阶段执行)
- `PYTHONPATH=src python3 -m aiforge gate-judge --feature feat-bpmn` → `gate-commit --feature feat-bpmn` → `review-3f`。

## 依赖与顺序
T1→T3(页面引 vendor);T2→T3/T4(fixture 供验收);T6→T7(导出器读 .bpmn);T7→T8(备援源+状态);**M1(T1-T5)整体不依赖 M2(T6-T9),M1 完成即可独立交付**;T10 在 M1+M2 代码全落后执行。
