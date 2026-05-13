# Delta Spec: Signal Scanner Engine

## Summary
信号扫描引擎：根据策略组配置扫描全市场股票，生成信号快照记录。

## ADDED Requirements

### REQ-SS-001: 信号扫描执行
系统 SHALL 提供信号扫描功能，遍历所有 `active` 状态的策略组，对每只股票匹配其触发条件。

扫描 MUST 从 `indicators_daily` 和 `stock_data_daily` 读取最新一日的指标数据，不重复计算指标。

扫描 MUST 复用 `stock_analysis` 表中的 `buy` 字段作为 buy_star 评分，不重新计算。

#### Scenario: 手动触发单个策略组扫描
- **Given** 存在 ID 为 1 的 active 策略组，配置了 KDJ 金叉条件
- **And** 数据库中 indicators_daily 有最新数据
- **When** 客户端调用 `POST /api/strategy/1/scan`
- **Then** 系统执行扫描，返回 200，body 包含 `matched_count`（匹配股票数）和 `run_id`

#### Scenario: 扫描非 active 策略组
- **Given** 存在 ID 为 2 的 paused 策略组
- **When** 客户端调用 `POST /api/strategy/2/scan`
- **Then** 系统返回 400，描述该策略组未处于 active 状态

#### Scenario: 定时批量扫描
- **Given** 系统中有 3 个 active 策略组，各自有不同的 scan_cron
- **When** APScheduler 根据 cron 表达式触发
- **Then** 系统依次执行每个策略组的扫描，各自生成独立的 signal_snapshot 记录

### REQ-SS-002: 条件匹配逻辑
系统 SHALL 支持三种信号组合逻辑：

- **AND**: 所有条件同时满足才算匹配
- **OR**: 任一条件满足即匹配
- **SCORING**: 每个条件匹配得一分，总分 ≥ 阈值（配置在 conditions 中）即匹配

每个条件 MUST 包含 `indicator`（指标名）、`operator`（比较运算符：`>`、`<`、`>=`、`<=`、`==`、`cross_above`、`cross_below`）、`value`（阈值）。

#### Scenario: AND 逻辑 — 全部条件满足
- **Given** 策略组配置 signal_logic=AND，conditions 为 `[KDJ_K > 80, RSI < 30]`
- **And** 某股票当日 KDJ_K=85, RSI=25
- **When** 扫描引擎评估该股票
- **Then** 该股票标记为匹配，生成 signal_snapshot

#### Scenario: AND 逻辑 — 部分条件不满足
- **Given** 策略组配置 signal_logic=AND，conditions 为 `[KDJ_K > 80, RSI < 30]`
- **And** 某股票当日 KDJ_K=85, RSI=45
- **When** 扫描引擎评估该股票
- **Then** 该股票不匹配，不生成 signal_snapshot

#### Scenario: SCORING 逻辑 — 达标
- **Given** 策略组配置 signal_logic=SCORING，scoring_threshold=2
- **And** conditions 包含 3 个条件，某股票满足其中 2 个
- **When** 扫描引擎评估该股票
- **Then** 该股票标记为匹配（2 ≥ 2）

### REQ-SS-003: 信号快照记录
每次匹配成功 MUST 在 `signal_snapshot` 表中生成一条记录，包含：
- `strategy_group_id`: 关联策略组
- `stock_code`: 股票代码
- `stock_name`: 股票名称
- `indicator_snapshot`: 触发时刻的指标值 JSON
- `buy_star`: 从 stock_analysis.buy 字段获取
- `run_id`: 关联本次扫描执行记录

#### Scenario: 快照包含完整指标值
- **Given** 策略组配置了 KDJ 指标，某股票 KDJ_K=85.3, KDJ_D=78.1, KDJ_J=99.7
- **When** 扫描匹配成功
- **Then** signal_snapshot 的 indicator_snapshot 字段包含 `{"KDJ_K": 85.3, "KDJ_D": 78.1, "KDJ_J": 99.7}`

### REQ-SS-004: 扫描执行记录
每次扫描 MUST 在 `strategy_group_run` 表中生成一条记录，记录开始时间、结束时间、扫描股票数、匹配数、状态。

#### Scenario: 扫描成功完成
- **Given** 策略组 1 扫描 5512 只股票，其中 23 只匹配
- **When** 扫描完成
- **Then** strategy_group_run 记录 `total_stocks=5512, matched_stocks=23, status="completed"`

#### Scenario: 扫描异常中断
- **Given** 扫描过程中数据库连接断开
- **When** 扫描未能完成
- **Then** strategy_group_run 记录 `status="failed"`，并记录 error_message

### REQ-SS-005: 信号查询 API
系统 SHALL 提供信号查询端点。

#### Scenario: 按策略组查询最新信号
- **When** 客户端调用 `GET /api/signals?strategy_group_id=1&limit=50`
- **Then** 系统返回该策略组最近 50 条 signal_snapshot，按 created_at 降序

#### Scenario: 按股票代码查询信号历史
- **When** 客户端调用 `GET /api/signals?stock_code=000001`
- **Then** 系统返回该股票的所有信号快照历史

#### Scenario: SSE 实时信号推送
- **When** 客户端连接 `GET /api/signals/stream`
- **Then** 系统建立 SSE 连接，每次新信号生成时推送事件
