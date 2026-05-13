# Delta Spec: Group Event Aggregator

## Summary
群体事件聚合器：在时间窗口内检测同维度多只股票的共振信号，自动聚合为群体事件。

## ADDED Requirements

### REQ-GE-001: 群体事件自动检测
系统 SHALL 在每次信号扫描完成后自动执行聚合检测。

聚合 MUST 按 strategy_group 的 `aggregation.dimension`（industry/concept/theme）对 signal_snapshot 分组。

当同一 dimension + 同一 dimension_value（如行业="半导体"）在 `time_window_minutes` 内匹配股票数 ≥ `min_stocks` 时，SHALL 创建或追加 `group_event` 记录。

#### Scenario: 新建群体事件
- **Given** 策略组 1 配置 aggregation.dimension=industry, min_stocks=3, time_window_minutes=60
- **And** 本次扫描在"半导体"行业匹配了 5 只股票
- **When** 聚合器检测到 5 ≥ 3
- **Then** 系统创建新 group_event，dimension_value="半导体"，stock_count=5

#### Scenario: 追加到已有事件
- **Given** 已有 group_event（策略组 1, dimension_value="半导体", stock_count=3, 创建于 30 分钟前）
- **And** 策略组 1 的 time_window_minutes=60
- **And** 本次扫描新增 2 只"半导体"股票信号
- **When** 聚合器检测到时间窗口内已有事件
- **Then** 系统将 2 只新股票追加到该事件，stock_count 更新为 5

#### Scenario: 匹配数不足
- **Given** 策略组 1 配置 min_stocks=3
- **And** 本次扫描在"银行"行业仅匹配了 2 只股票
- **When** 聚合器检测
- **Then** 不创建 group_event

#### Scenario: 超出时间窗口
- **Given** 已有 group_event（策略组 1, dimension_value="半导体", 创建于 120 分钟前）
- **And** 策略组 1 的 time_window_minutes=60
- **When** 新信号到达
- **Then** 系统不追加到旧事件，而是评估是否创建新事件

### REQ-GE-002: 聚合指标计算
每个 group_event MUST 计算并存储以下聚合指标：
- `stock_count`: 匹配股票数
- `avg_buy_star`: 所有匹配股票 buy_star 的平均值
- `max_buy_star`: 最高 buy_star
- `matched_stocks`: 匹配股票列表 JSON（code + name + buy_star）

#### Scenario: 聚合指标正确计算
- **Given** 5 只半导体股票匹配，buy_star 分别为 3, 4, 5, 2, 4
- **When** 创建 group_event
- **Then** stock_count=5, avg_buy_star=3.6, max_buy_star=5

### REQ-GE-003: 群体事件查询 API
系统 SHALL 提供事件查询端点。

#### Scenario: 查询最新群体事件
- **When** 客户端调用 `GET /api/events?limit=20`
- **Then** 系统返回最近 20 条 group_event，按 created_at 降序，包含聚合指标和股票列表

#### Scenario: 按策略组筛选事件
- **When** 客户端调用 `GET /api/events?strategy_group_id=1`
- **Then** 系统仅返回策略组 1 的事件

#### Scenario: 按维度值筛选
- **When** 客户端调用 `GET /api/events?dimension_value=半导体`
- **Then** 系统仅返回 dimension_value 为"半导体"的事件

#### Scenario: 查询事件详情
- **When** 客户端调用 `GET /api/events/{id}`
- **Then** 系统返回完整事件信息，含 matched_stocks 列表和关联的 signal_snapshot IDs

### REQ-GE-004: 事件状态管理
group_event SHALL 支持以下状态：`open`（仍在时间窗口内可追加）、`closed`（超出时间窗口或手动关闭）、`analyzed`（LLM 分析完成，Phase 2 预留）。

#### Scenario: 超出时间窗口自动关闭
- **Given** group_event 创建于 60 分钟前，time_window_minutes=60
- **When** 定时检查器运行
- **Then** 事件状态从 open 变为 closed

#### Scenario: 手动关闭事件
- **When** 客户端调用 `PATCH /api/events/{id}/close`
- **Then** 事件状态变为 closed，不再接受新信号追加
