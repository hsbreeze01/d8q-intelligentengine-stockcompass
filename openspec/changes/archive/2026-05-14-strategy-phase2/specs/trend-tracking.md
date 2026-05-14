# Delta Spec: 趋势跟踪与生命周期管理

## ADDED Requirements

### REQ-TRK-001: 每日趋势跟踪执行

系统 SHALL 在每日调度任务中，对所有 `lifecycle='tracking'` 的群体事件执行趋势跟踪。

#### Scenario: 每日扫描 tracking 事件

- **Given** 调度器触发每日扫描任务
- **When** 系统查询所有 `lifecycle='tracking'` 的 `group_event`
- **Then** 系统 SHALL 对每个事件执行趋势跟踪，写入一条 `trend_tracking` 记录

#### Scenario: 无 tracking 事件时安全跳过

- **Given** 数据库中不存在 `lifecycle='tracking'` 的群体事件
- **When** 趋势跟踪任务执行
- **Then** 系统 SHALL 正常结束，不产生错误

---

### REQ-TRK-002: 触发股票变化检测

趋势跟踪 SHALL 记录当日触发股票列表与前一日的差异。

#### Scenario: 检测新增和消失的触发股票

- **Given** 一个 tracking 事件有前一日的 `trend_tracking` 记录
- **When** 执行当日趋势跟踪
- **Then** 系统 SHALL 计算新增触发股票（`new_stocks`）和消失触发股票（`lost_stocks`），写入当日记录

#### Scenario: 首次跟踪无历史记录

- **Given** 一个 tracking 事件没有前一日 `trend_tracking` 记录
- **When** 执行首次趋势跟踪
- **Then** 系统 SHALL 将所有触发股票记录为当前快照，`new_stocks` 为全部，`lost_stocks` 为空

---

### REQ-TRK-003: 指标聚合计算

趋势跟踪 SHALL 对当日触发股票的量化指标进行聚合计算。

#### Scenario: 聚合触发股票指标均值

- **Given** 当日触发股票列表已确定
- **When** 执行指标聚合
- **Then** 系统 SHALL 计算 RSI、MACD DIF、量比、综合评分的均值，写入 `trend_tracking` 记录的对应字段

---

### REQ-TRK-004: 信号衰减判定

系统 SHALL 基于趋势跟踪指标判定信号是否衰减，自动更新生命周期状态。

#### Scenario: 连续 2 日评分低于阈值触发衰减

- **Given** 一个 tracking 事件最近 2 个交易日的 `trend_tracking` 记录的均值评分均 < 0.5
- **When** 趋势跟踪器执行衰减判定
- **Then** 系统 SHALL 将该事件的 `lifecycle` 更新为 `'suggest_close'`，并记录 `suggest_close_reason` 为信号衰减描述

#### Scenario: 评分未达衰减条件

- **Given** 一个 tracking 事件的近期评分未连续低于阈值
- **When** 趋势跟踪器执行衰减判定
- **Then** 系统 SHALL 保持 `lifecycle='tracking'` 不变

---

### REQ-TRK-005: 资讯持续关联

趋势跟踪 SHALL 每日对 tracking 事件搜索新增资讯并追加到事件记录。

#### Scenario: 用关键词搜索近 24h 资讯

- **Given** 一个 tracking 事件的 `llm_keywords` 和 `llm_related_themes` 不为空
- **When** 执行每日趋势跟踪
- **Then** 系统 SHALL 使用这些关键词搜索 DataAgent 近 24h 新增资讯，追加到 `group_event.news_matched`，更新 `trend_tracking.news_count`

#### Scenario: 关键词为空时跳过资讯关联

- **Given** 一个 tracking 事件的 `llm_keywords` 和 `llm_related_themes` 均为空
- **When** 执行资讯关联
- **Then** 系统 SHALL 跳过资讯搜索，`news_count` 记录为 0

---

### REQ-TRK-006: 生命周期状态转换

系统 SHALL 管理群体事件的完整生命周期，确保状态转换符合规则。

#### Scenario: 事件创建时设置 tracking

- **Given** 聚合器创建新的群体事件
- **When** 写入 `group_event` 记录
- **Then** 系统 SHALL 设置 `lifecycle='tracking'`

#### Scenario: 信号衰减自动标记 suggest_close

- **Given** 趋势跟踪器检测到信号衰减（REQ-TRK-004）
- **When** 自动更新生命周期
- **Then** 系统 SHALL 将 `lifecycle` 更新为 `'suggest_close'`，记录 `suggest_close_reason`

#### Scenario: 管理员确认关闭

- **Given** 一个事件的 `lifecycle` 为 `'suggest_close'` 或 `'tracking'`
- **When** 管理员调用关闭 API
- **Then** 系统 SHALL 将 `lifecycle` 更新为 `'closed'`，记录 `closed_at`（当前时间）和 `closed_by`（操作者 ID）

#### Scenario: 已关闭事件不再跟踪和资讯采集

- **Given** 一个事件的 `lifecycle='closed'`
- **When** 每日趋势跟踪任务执行
- **Then** 系统 SHALL 跳过该事件，不执行任何跟踪或资讯采集操作

#### Scenario: 已关闭事件的数据保留

- **Given** 一个事件已被关闭
- **When** 查询该事件详情
- **Then** 系统 SHALL 返回该事件的所有历史数据，包括 trend_tracking 记录和 news_matched
