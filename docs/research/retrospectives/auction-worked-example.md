# auction 案例复盘 + gate-log(worked example)

> **来源**:老库 AISEP/projects/auction/。retrospective 展示"量化学习曲线(7→2→1 迭代收敛)+ L0/L1/L2 知识分层";gate-log 是"一条完整 receipt 链长什么样"的具象化(呼应契约 06)。

## retrospective.yaml

```yaml
# S8 制品：复盘报告
# 项目：线上拍卖系统 (auction)
# 生成时间：2026-03-16T07:30:00+08:00

retrospective:
  project_id: "auction"
  project_name: "线上拍卖系统"
  timestamp: "2026-03-16T07:30:00+08:00"

  # ══════════════════════════════════════════════════════════════
  # Step 1: 项目度量
  # ══════════════════════════════════════════════════════════════
  metrics:
    timeline:
      start: "2026-03-15T21:37:00+08:00"  # S0 Gate（首次）
      end: "2026-03-16T07:30:00+08:00"    # S8 复盘
      elapsed_hours: ~10
      active_sessions: 2  # 跨 2 个对话窗口
    scope:
      total_slices: 3
      total_stories: 14
      must_stories: 9
      should_stories: 4
      wont_stories: 1
    deliverables:
      modules: 3  # auction_lot, auction_session, auction_bidding
      total_files: 36
      total_lines: ~2418
      models: 7  # lot, lot.image, lot.category, session, session.lot, bidding.round, bid
      adrs: 2    # 实时竞价推送 + 并发锁定
    quality:
      total_tests: 74
      test_failures: 0
      test_errors: 0
      gate_passes: 10  # S0(×2) + S1 + S2 + S3 + S4/S5/S6(×3 slices) + S7
      gate_failures: 0
      gate_rollbacks: 1  # S0→S1 rollback 为体验改进版 flow
      bugs_found_in_dev: 3  # TransactionCase 可靠性 + One2many 缓存 + groups 菜单
      bugs_found_in_prod: 0
      slice_iteration_stats:
        slice_1: { tests: 33, iterations: 7 }
        slice_2: { tests: 20, iterations: 2 }
        slice_3: { tests: 21, iterations: 1 }  # zero-fix 首次通过
    gates_detail:
      - { stage: "S0 (首次)", result: "pass", notes: "经 /deepdive 增强 problem+risks" }
      - { stage: "S0 (rollback)", result: "rollback", notes: "回退以体验改进版 S0 flow" }
      - { stage: "S0 (第二次)", result: "pass", notes: "改进版 S0 验证通过" }
      - { stage: "S1", result: "pass", notes: "3 BC · 3 Aggregate · 17 术语 · 4 E2E 流程" }
      - { stage: "S2", result: "pass", notes: "14 Stories (Must 9/Should 4/Won't 1)" }
      - { stage: "S3", result: "pass", notes: "7 Model · 2 Groups · 2 ADR · 7 铁律" }
      - { stage: "S4 Slice-1", result: "pass", notes: "3 Model · 9 View · 8 初始分类" }
      - { stage: "S5+S6 Slice-1", result: "pass", notes: "33 tests / 7 轮迭代" }
      - { stage: "S4 Slice-2", result: "pass", notes: "2 Model · 4 View" }
      - { stage: "S5+S6 Slice-2", result: "pass", notes: "20 tests / 2 轮迭代" }
      - { stage: "S4 Slice-3", result: "pass", notes: "2 Model · FOR UPDATE + Bus" }
      - { stage: "S5+S6 Slice-3", result: "pass", notes: "21 tests / 一次通过" }
      - { stage: "S7", result: "pass", notes: "Docker Compose + Nginx + prepare.sh" }

  # ══════════════════════════════════════════════════════════════
  # Step 2a: 踩坑记录
  # ══════════════════════════════════════════════════════════════
  pitfalls:
    encountered:
      - id: "PIT-AUC-001"
        description: "TransactionCase 中 SQL 约束 + Python 约束交互导致测试不可靠"
        discovered_at: "Slice-1 S6（7 轮迭代主因）"
        fix_cost: "中（需要理解 Odoo 测试事务回滚机制）"
        root_cause: |
          SQL 约束在 DB 层触发 IntegrityError，TransactionCase 的 savepoint
          被破坏后，同一测试方法内后续 ORM 操作均失败。
        fix: "将期望 SQL 约束的测试用 with self.assertRaises(IntegrityError) 包裹，或拆分为独立测试方法"
        already_in_knowledge_base: false
        should_promote: "L1 — 通用 Odoo 测试陷阱"
        proposed_pitfall_id: "P2-05"

      - id: "PIT-AUC-002"
        description: "One2many 缓存刷新：create 后 count 不更新"
        discovered_at: "Slice-2 S6（2 轮迭代主因）"
        fix_cost: "低（1 处代码修改）"
        root_cause: |
          Odoo ORM 缓存机制导致在同一事务中 create One2many 子记录后，
          父记录的 One2many 字段未自动刷新，compute 字段仍为旧值。
        fix: "在 create 后调用 parent.invalidate_recordset() 强制刷新缓存"
        already_in_knowledge_base: false
        should_promote: "L1 — 常见 ORM 缓存问题"
        proposed_pitfall_id: "P2-06"

      - id: "PIT-AUC-003"
        description: "菜单不可见：admin 用户未自动加入自定义安全组"
        discovered_at: "S7 部署验证"
        fix_cost: "低（1 处 XML 修改）"
        root_cause: |
          Odoo 的 groups 可见性要求用户必须属于该组。admin 虽是超级用户
          但不等于自动属于所有自定义组。group_auction_manager 需通过
          implied_ids 链到 base.group_user 才能让 admin 自动获取。
        fix: "在 group 定义中通过 implied_ids 链正确设置继承关系"
        already_in_knowledge_base: false
        should_promote: "L1 — Odoo 安全组常见误解"
        proposed_pitfall_id: "P2-07"

    assessment: |
      共 3 个开发阶段踩坑，均已即时修复。
      与 proj-001 不同，本项目无 P1 级（致命）踩坑，说明 pitfalls.md 知识库发挥了预防作用。
      但发现了 3 个 P2 级新陷阱，应沉淀到 L1 框架知识库。
      特别值得注意的是：Slice-1 的 7 轮测试迭代成本较高，
      而到了 Slice-3 实现了零修复一次通过 —— 团队学习曲线效果显著。

  # ══════════════════════════════════════════════════════════════
  # Step 2b: 模式识别
  # ══════════════════════════════════════════════════════════════
  patterns:
    - name: "FOR UPDATE 行级锁保护并发写入"
      frequency: 1  # auction_bidding.place_bid
      description: |
        在 ORM 事务内嵌入裸 SQL SELECT FOR UPDATE，实现行级排他锁。
        解决了 ORM 层无法提供的并发写入一致性问题。
      promoted_to: null
      action: "保留 L2。如下个项目有类似并发场景（如库存扣减），提升为 L1 Skill"
      note: "已在 ADR-002 和 constitution.md 中记录此例外"

    - name: "Bus._sendone 实时推送模式"
      frequency: 1  # auction_bidding.place_bid
      description: |
        利用 Odoo 内置 Bus 模块的 _sendone 方法实现服务端到客户端的
        实时消息推送，配合 Nginx WebSocket proxy 实现低延迟通知。
      promoted_to: null
      action: "保留 L2。如下个项目需要实时推送（如消息通知），提升为 L1 Skill"

    - name: "三路判定状态机（sold/conditional/unsold）"
      frequency: 1  # auction_bidding._check_hammer
      description: |
        基于底价和有条件成交阈值的三路分支判定逻辑。
        判定函数纯逻辑（无副作用），易于测试。
      promoted_to: null
      action: "保留 L2。属于业务领域特有模式"

    - name: "Immutable Record 模式（ORM write/unlink 覆写）"
      frequency: 1  # auction.bid
      description: |
        通过覆写 write() 和 unlink() 方法禁止修改/删除已创建的记录，
        但允许 compute 字段更新（通过 ALLOWED_FIELDS 白名单）。
      promoted_to: null
      action: "保留 L2。如下个项目有审计日志/交易记录等需求，考虑提升为 L1"

    - name: "模块间依赖拓扑排序 + 分层 Slice"
      frequency: 1  # auction_lot → auction_session → auction_bidding
      description: |
        3 个模块严格按依赖顺序在 3 个 Slice 中实现。
        每个 Slice 交付一个完整的 Bounded Context，
        后续 Slice 依赖前驱 Slice 已通过测试。
      promoted_to: "L1"
      action: "验证了 proj-001 已识别的 Vertical Slice 架构模式（learn-008）"

    - name: "SQL 约束 + Python 约束 职责分离"
      frequency: 3  # lot(2 SQL) + session(2 SQL) + bidding(1 SQL)
      description: |
        数值范围、字段关系约束用 SQL_constraints（数据库层强保障），
        跨记录/跨表/复杂逻辑约束用 @api.constrains（Python 层灵活处理）。
      promoted_to: "L1"
      action: "与 proj-001 的 Compute+Constraint 模式互补，强化了 best-practices.md"

  # ══════════════════════════════════════════════════════════════
  # Step 2c: 决策回顾
  # ══════════════════════════════════════════════════════════════
  decisions:
    - adr: "ADR-001 实时竞价推送方案"
      decision: "Odoo Bus (Long Polling)"
      status: "validated"
      evidence: |
        Bus._sendone 成功集成到 place_bid 方法中。
        Nginx WebSocket proxy 配置完成。
        21 个竞价引擎测试全部通过（含 Bus 推送测试）。
      caveat: "未经真实高并发压测验证延迟表现"

    - adr: "ADR-002 并发竞价一致性策略"
      decision: "PostgreSQL SELECT ... FOR UPDATE"
      status: "validated"
      evidence: |
        place_bid 方法中 FOR UPDATE 行级锁成功实现。
        并发场景在单元测试中验证通过。
        锁粒度精确到单个 bidding.round 行。
      caveat: "未经真实多进程并发压测，生产环境需监控锁等待时间"

    - adr_implicit: "新建模块策略（vs 继承标准模块）"
      decision: "3 个全新模块，不继承标准 Odoo 模型"
      status: "validated"
      evidence: |
        拍卖业务与标准 sale/purchase 流程差异大，新建模块避免了
        不必要的耦合。7 个 Model 全部为新建，无继承冲突。
      recommendation: "记录为 ADR-003"

  # ══════════════════════════════════════════════════════════════
  # Step 3: 知识分层沉淀
  # ══════════════════════════════════════════════════════════════
  knowledge_layering:
    L2_project:
      - "PIT-AUC-001/002/003 已记录在本报告"
      - "deploy/ 目录的 Docker Compose + Nginx + prepare.sh 配置"
      - "2 个 ADR 验证为有效"

    L1_framework:
      - item: "P2-05 TransactionCase SQL约束测试可靠性"
        status: "待新增到 pitfalls.md"
      - item: "P2-06 One2many 缓存刷新"
        status: "待新增到 pitfalls.md"
      - item: "P2-07 自定义安全组与 admin 可见性"
        status: "待新增到 pitfalls.md"
      - item: "SQL+Python 约束职责分离"
        status: "验证了 best-practices.md 现有指导"
      - item: "Vertical Slice 按依赖拓扑排序"
        status: "验证了 learn-008，validation_count +1"

    L0_universal:
      - item: "S8 复盘进化 Workflow"
        status: "第 2 次执行 — 验证流程稳定"
      - item: "学习曲线效应可量化"
        status: "Slice-1(7轮) → Slice-2(2轮) → Slice-3(1轮) 提供了度量基准"

  # ══════════════════════════════════════════════════════════════
  # Step 4: 认知笔记
  # ══════════════════════════════════════════════════════════════
  knowledge_entries:
    - id: "learn-013"
      topic: "FOR UPDATE 行级锁在 ORM 中的应用"
      one_liner: "在 Odoo ORM 事务内嵌入裸 SQL SELECT FOR UPDATE 实现并发写入保护"
      analogy: "像银行柜台取号 — 同一个号只能被一个人办理，其他人必须排队"
      key_insights:
        - "FOR UPDATE 锁定的是行而非表，锁粒度精确"
        - "锁定后必须 invalidate_recordset() 刷新 ORM 缓存"
        - "事务结束时锁自动释放，无需手动管理"
        - "这是裸 SQL 例外场景之一，需在 ADR 中明确记录"
      tags: [odoo, postgresql, concurrency, locking]

    - id: "learn-014"
      topic: "Immutable Record 设计模式"
      one_liner: "通过覆写 ORM 的 write/unlink 方法，实现创建后不可修改/删除的业务记录"
      analogy: "像刻在石板上的铭文 — 一旦写下就不能擦除，只能追加新石板"
      key_insights:
        - "白名单机制允许 compute 字段更新（系统行为 vs 用户行为的分离）"
        - "适用于审计日志、交易记录、出价记录等法规要求不可篡改的场景"
        - "覆写 write() 时必须调用 super()（通过白名单过滤 vals）"
      tags: [odoo, design-pattern, data-integrity, audit]

    - id: "learn-015"
      topic: "Odoo Bus 实时推送机制"
      one_liner: "Odoo 内置的消息总线，通过 Long Polling 实现服务端到浏览器的实时通知"
      analogy: "像广播电台 — 服务器是播音员，浏览器调到对应频道就能收到消息"
      key_insights:
        - "bus._sendone(channel, type, message) 是核心 API"
        - "Channel 用 Model._name + record_id 实现精确推送"
        - "需要 Nginx 的 WebSocket proxy_pass 到 Odoo 8072 端口"
        - "Long Polling 延迟 1-2s，够用但不适合超高频场景"
      tags: [odoo, bus, realtime, websocket, long-polling]

  # ══════════════════════════════════════════════════════════════
  # Step 5: 系统自进化
  # ══════════════════════════════════════════════════════════════
  system_evolutions:
    - type: "pitfall"
      description: "新增 P2-05/P2-06/P2-07 到 Odoo 17 pitfalls.md"
      impact: "L1 — 所有 Odoo 17 项目受益"

    - type: "knowledge"
      description: "learn-008 Vertical Slice 架构 validation_count +1（第 2 个项目验证）"
      impact: "L1 — 方法论成熟度提升"

    - type: "metric"
      description: "首次量化学习曲线效应（7→2→1 迭代收敛），可作为项目估算参考"
      impact: "L0 — 跨项目估算改进"

    - type: "gate"
      description: "S7 Gate 浏览器验收已执行（菜单可见 + 表单展示），与 proj-001 建议一致"
      recommendation: "确认将浏览器验收纳入 S6/S7 Gate 标准检查项"

    - type: "workflow"
      description: "S8 Workflow 第 2 次执行，流程稳定，无需修改"
      impact: "无变更"

    - type: "tidy"
      description: "/tidy 检查项无遗漏"
      impact: "无变更"

  # ══════════════════════════════════════════════════════════════
  # 对比 proj-001
  # ══════════════════════════════════════════════════════════════
  comparison_with_proj001:
    improvement_areas:
      - aspect: "P1 级踩坑"
        proj001: "1 个（P1-05 stock.move 字段重命名）"
        auction: "0 个 — pitfalls.md 预防效果显现"
      - aspect: "测试迭代收敛"
        proj001: "无明确收敛数据"
        auction: "7→2→1 轮，学习曲线可量化"
      - aspect: "一次通过率"
        proj001: "无 Slice 实现一次通过"
        auction: "Slice-3 实现 zero-fix 一次通过"
      - aspect: "ADR 质量"
        proj001: "2 个隐式 ADR"
        auction: "2 个显式 ADR + 独立 markdown 文件"
    stable_areas:
      - "Vertical Slice 拓扑排序策略 — 两个项目均验证有效"
      - "pitfalls.md 自检清单 — 有效防止已知问题复现"
      - "/tidy + gate-log 全生命周期追溯 — 流程稳定"

  # ══════════════════════════════════════════════════════════════
  # 下一步行动
  # ══════════════════════════════════════════════════════════════
  next_actions:
    - "新增 P2-05/P2-06/P2-07 到 pitfalls.md"
    - "更新 knowledge index.yaml（learn-013/014/015 + learn-008 validation++）"
    - "前端竞价页面：WebSocket 连接 Bus 实时出价 UI（_next_session 已规划）"
    - "生产部署验证：docker compose up 并验证三模块集成"
    - "如 FOR UPDATE / Immutable Record 模式在下个项目再次出现 → 提升为 L1 Skill"
    - "如 Bus 推送模式在下个项目再次出现 → 提升为 L1 Skill + 创建 ADR-003 模板"

```

## gate-log.yaml(receipt 链范例)

```yaml
# Gate 审批日志
gates:
  - stage: s0
    timestamp: "2026-03-15T21:37:00+08:00"
    result: passed
    gate_checklist:
      completeness:
        name_non_empty: true
        description_non_empty: true
        target_modules_gte_1: true  # 3 个核心域模块
        constraints_at_least_1: true  # team_size 已填
      reasonableness:
        module_count_lte_15: true  # 3 个
        constraints_reasonable: true
        tech_stack_matches_skills: true  # odoo17 ✓
      traceability:
        existing_system_confirmed: true  # 确认为空
      user_confirmation: true
    notes: "经 /deepdive 验证后增强了 problem + known_risks 字段。S0 workflow 同步改进（prop-010/011/012）。"

  - stage: s0
    action: rollback
    timestamp: "2026-03-15T22:00:00+08:00"
    from_stage: s1-domain
    reason: "体验改进后的 S0 flow（含痛点追问 + KPI + risk 引导）"

  - stage: s0
    action: passed
    timestamp: "2026-03-15T22:11:00+08:00"
    notes: "改进版 S0 flow 第二次通过。验证了 Step 1 痛点追问、KPI 引导、Step 3 风险追问的体验流畅性。"

  - stage: s1
    action: passed
    timestamp: "2026-03-15T22:21:00+08:00"
    artifacts_produced:
      - "artifacts/global/domain-model.yaml"
      - "glossary.yaml"
    notes: "3 BC · 3 Aggregate · 17 术语 · 4 端到端流程。关键规则：无底价拍卖、底价隐藏、有条件成交、拍品不可同时多场。"

  - stage: s2
    action: passed
    timestamp: "2026-03-15T22:40:00+08:00"
    artifacts_produced:
      - "artifacts/global/functional.yaml"
      - "artifacts/global/slice-plan.yaml"
    notes: "14 Stories (Must 9/Should 4/Won't 1, Must=64%)。3 Slices 按拓扑序。US-08 经 /deepdive 降为 Should。CRUD 矩阵完整。"

  - stage: s3
    action: passed
    timestamp: "2026-03-15T22:58:00+08:00"
    artifacts_produced:
      - "artifacts/global/architecture.yaml"
      - "adr/001-realtime-bidding.md"
      - "adr/002-concurrency-locking.md"
    notes: "3 模块(auction_lot/auction_session/auction_bidding) · 7 Model 字段级设计 · 2 Groups + ACL 矩阵 · 2 Record Rules · Docker 部署 · 2 ADR · 7 条项目铁律。Gate 14 项全部通过。"

  - stage: s4
    slice_id: slice-1
    action: passed
    timestamp: "2026-03-15T23:53:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-1/design.yaml"
    notes: "3 Model (lot/image/category) · 14+4+4 字段 · 5 约束方法 · 3 业务动作 · 9 View(form/tree/search/kanban) · 3 级菜单 · 9 ACL + 1 Record Rule · 8 初始分类 · Pitfall 9/9 通过。同步沉淀分片策略规则到模板和工作流。"

  - stage: s5
    slice_id: slice-1
    action: passed
    timestamp: "2026-03-16T00:11:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-1/code/auction_lot/"
    file_count: 12
    total_lines: 672
    notes: "auction_lot 模块完整生成。3 Model Python + 3 View XML + Security(ACL+Groups+Rule) + Data(8分类) + Manifest。自检 5/5 通过。"

  - stage: s6
    slice_id: slice-1
    action: passed
    timestamp: "2026-03-16T00:27:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-1/code/auction_lot/tests/test_auction_lot.py"
    test_stats:
      total: 33
      passed: 33
      failed: 0
      errors: 0
      iterations: 7
    notes: "Odoo 17 Docker 安装验证通过。33 tests / 0 failures / 0 errors。测试覆盖：CRUD(8) + 业务规则(8) + 计算字段(1) + 状态流转(4) + 搜索(3) + 安全(5) + 约束(2)。7 轮迭代修复了 TransactionCase 中 SQL/Python 约束交互的测试可靠性问题。"

  - stage: s4
    slice_id: slice-2
    action: passed
    timestamp: "2026-03-16T00:33:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-2/design.yaml"
    notes: "Slice-2 拍卖会编排设计。2 Model(session 12字段+4动作+2SQL约束 / session_lot 4字段+1Python约束) + 4 View(form/tree/search/kanban) + 6 ACL + 1 RecordRule。复用 auction_lot 顶级菜单。Pitfall checklist 7/7。"

  - stage: s5
    slice_id: slice-2
    action: passed
    timestamp: "2026-03-16T06:55:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-2/code/auction_session/"
    metrics:
      files: 11
      lines: 766
    notes: "auction_session 模块生成。11 文件 / 766 行。Models(2) + Views(2) + Security(2) + Tests(2) + Init(2) + Manifest(1)。S5 自检通过：import 链完整、manifest data 安全优先、comodel_name 拼写正确。"

  - stage: s6
    slice_id: slice-2
    action: passed
    timestamp: "2026-03-16T07:00:00+08:00"
    metrics:
      tests: 20
      failures: 0
      errors: 0
      iterations: 2
    notes: "Odoo 17 Docker 安装验证通过。20 tests / 0 failures / 0 errors。2 轮迭代修复 1 个 One2many 缓存刷新问题（invalidate_recordset）。覆盖：CRUD(3) + 约束(4) + 编排(3) + 状态流转(6) + 搜索(1) + 唯一性(2) + 默认值(1)。"

  - stage: s4
    slice_id: slice-3
    action: passed
    timestamp: "2026-03-16T07:03:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-3/design.yaml"
    notes: "Slice-3 竞价引擎设计。2 Model(bidding.round 12字段+4方法 / bid 6字段+immutable)。核心：place_bid FOR UPDATE 行级锁 + bus._sendone 实时推送 + _check_hammer 三路判定。Pitfall checklist 8/8。"

  - stage: s5
    slice_id: slice-3
    action: passed
    timestamp: "2026-03-16T07:20:00+08:00"
    artifacts_produced:
      - "artifacts/slices/slice-3/code/auction_bidding/"
    metrics:
      files: 10
      lines: 852
    notes: "auction_bidding 模块生成。10 文件 / 852 行。Models(2) + Views(2) + Security(1) + Tests(2) + Init(2) + Manifest(1)。核心：place_bid FOR UPDATE + Bus + 三路判定。bid immutable write/unlink 覆写。"

  - stage: s6
    slice_id: slice-3
    action: passed
    timestamp: "2026-03-16T07:21:00+08:00"
    metrics:
      tests: 21
      failures: 0
      errors: 0
      iterations: 1
    notes: "Odoo 17 Docker 安装验证通过。21 tests / 0 failures / 0 errors。一次通过（zero iteration fix）。覆盖：CRUD(2) + 出价(4) + 落槌判定(5) + 有条件成交(3) + immutable(2) + 计算(2) + SQL约束(1) + 搜索(1) + 默认值(1)。"

  - stage: s7
    action: passed
    timestamp: "2026-03-16T07:22:00+08:00"
    artifacts_produced:
      - "deploy/docker-compose.yml"
      - "deploy/.env.example"
      - "deploy/nginx/default.conf"
      - "deploy/prepare.sh"
    notes: "Docker Compose 生产配置。Odoo 17(4 workers) + PostgreSQL 15(healthcheck) + Nginx(WebSocket proxy for Bus)。prepare.sh 自动复制 3 Slice 模块。"

  - stage: s8
    action: passed
    timestamp: "2026-03-16T07:30:00+08:00"
    artifacts_produced:
      - "artifacts/global/retrospective.yaml"
    notes: |
      S8 复盘进化完成。6 步全部执行：
      度量(10h/74tests) + 踩坑(3个P2新增到pitfalls.md) + 模式(6个候选) +
      决策回顾(2 ADR validated) + 认知笔记(learn-013/014/015) +
      系统进化(pitfalls.md/index.yaml 已更新)。
      跨项目对比：P1 踩坑从 1→0，测试迭代 7→2→1 收敛。
    gate_checklist:
      metrics_collected: true
      pitfalls_documented: true
      patterns_evaluated_gte_3: true  # 6 个模式
      knowledge_entries_shown: true
      retrospective_generated: true
      backlog_updated: false  # 本项目无 backlog.md

```
