# Delta Spec: Industry Data Completion

## Summary
补全 stock_basic 表的 industry 字段，为群体事件聚合提供行业维度数据。

## ADDED Requirements

### REQ-IDC-001: 批量补全行业分类
系统 SHALL 提供从外部数据源批量补全 stock_basic.industry 字段的能力。

数据源优先级：akshare `stock_board_industry_name_em` 接口 > 本地映射文件。

#### Scenario: 通过 akshare 补全
- **Given** stock_basic 表中 5512 条记录的 industry 字段全部为空
- **When** 运维调用 `POST /api/admin/industry/sync`
- **Then** 系统调用 akshare 获取行业分类映射，更新 stock_basic.industry 字段
- **And** 返回 `updated_count`（成功更新的记录数）

#### Scenario: akshare 接口不可用时的降级
- **Given** akshare 接口超时或返回错误
- **When** 系统尝试获取行业数据
- **Then** 系统 SHALL 尝试从本地映射文件（`data/industry_mapping.json`）读取
- **And** 如果本地文件也不存在，返回错误并提示管理员手动配置

#### Scenario: 增量更新
- **Given** stock_basic 中已有 4000 条记录有 industry 值
- **When** 运维调用 `POST /api/admin/industry/sync`
- **Then** 系统仅更新 industry 为空的 1512 条记录，不覆盖已有值

### REQ-IDC-002: 行业分类查询
系统 SHALL 提供行业分类统计查询。

#### Scenario: 查询行业分布
- **When** 客户端调用 `GET /api/admin/industry/stats`
- **Then** 系统返回各行业的股票数量统计，按数量降序

#### Scenario: 行业补全状态
- **When** 客户端调用 `GET /api/admin/industry/status`
- **Then** 系统返回 `total`（总股票数）、`has_industry`（有行业分类的股票数）、`completion_rate`（完成率百分比）
