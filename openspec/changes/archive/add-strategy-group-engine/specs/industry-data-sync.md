# Spec: Industry Data Sync

## ADDED Requirements

### REQ-IS-001: Bulk Industry Population

系统 SHALL 通过 akshare `stock_board_industry_name_em` + `stock_board_industry_cons_em` 补全 `stock_basic.industry` 字段。同步过程：
1. 获取所有行业板块列表
2. 对每个行业板块获取成分股
3. 将行业名称写入 `stock_basic.industry`

#### Scenario: Populate industry for all stocks
- **Given** stock_basic 有 5512 只股票，industry 全部为 NULL
- **When** 系统执行行业数据同步
- **Then** stock_basic.industry 字段被填充为对应的东方财富行业分类名称（如 "银行"、"证券" 等）

#### Scenario: Handle akshare rate limiting gracefully
- **Given** akshare 连续调用可能被限速
- **When** 系统在循环调用 `stock_board_industry_cons_em` 时遇到连接错误
- **Then** 系统 SHALL 等待 2 秒后重试，最多重试 3 次；若仍失败则跳过该行业并记录日志

---

### REQ-IS-002: Industry Sync Idempotency

行业同步 SHALL 支持幂等重复执行：每次执行时全量覆盖 industry 字段（以 akshare 数据为准）。

#### Scenario: Re-run sync updates stale data
- **Given** stock_basic 中部分股票的 industry 已有旧值
- **When** 系统再次执行行业数据同步
- **Then** 所有股票的 industry 字段以最新 akshare 数据为准更新

---

### REQ-IS-003: Sync API Endpoint

系统 SHALL 提供 API 端点手动触发行业数据同步。

#### Scenario: Trigger industry sync via API
- **Given** 管理员需要更新行业数据
- **When** 用户 POST /api/strategy/industry/sync
- **Then** 系统启动同步任务，返回 202 和任务状态（同步在后台执行）

#### Scenario: Query sync status
- **Given** 行业同步正在执行
- **When** 用户 GET /api/strategy/industry/sync/status
- **Then** 系统返回同步进度（已处理行业数/总行业数、已更新股票数、当前状态）
