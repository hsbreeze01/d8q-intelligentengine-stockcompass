# Spec: 数据库连接池监控与生命周期可视化

> Scope: d8q-intelligentengine-stockcompass 内 compass/api/routes/admin.py + compass/data/database.py

## ADDED Requirements

### Requirement: 管理员连接池状态 API

系统 SHALL 提供 REST API 端点，允许管理员实时查看数据库连接池状态。

#### Scenario: 管理员查询连接池健康状态

- **Given** 管理员已通过身份验证且具有管理员权限
- **When** 发送 `GET /api/admin/db/pool-status`
- **Then** 系统 SHALL 返回 JSON 响应，包含：
  - `pool_name`: 连接池标识（如 "compass"、"pipeline"）
  - `active_connections`: 当前活跃连接数
  - `idle_connections`: 当前空闲连接数
  - `max_connections`: 最大连接数配置
  - `last_error`: 最近一次连接错误信息（或 null）
- **And** HTTP 状态码 SHALL 为 200

#### Scenario: 非管理员查询连接池状态被拒绝

- **Given** 当前用户不具有管理员权限
- **When** 发送 `GET /api/admin/db/pool-status`
- **Then** 系统 SHALL 返回 HTTP 403
- **And** 响应体包含错误信息

#### Scenario: 连接池未初始化时返回默认值

- **Given** DBClient 连接池尚未初始化
- **When** 管理员查询连接池状态
- **Then** 系统 SHALL 返回 `initialized: false` 和各字段的零值
- **And** HTTP 状态码 SHALL 为 200

### Requirement: 数据库连接健康度定时检查

系统 SHOULD 定期检查数据库连接可用性，并在检测到异常时记录告警日志。

#### Scenario: 定时检查通过

- **Given** 系统 scheduler 已启动
- **When** 到达健康检查时间点（每 60 秒）
- **Then** 系统 SHALL 对每个已注册的连接池执行 `SELECT 1` 测试查询
- **And** 成功时 SHALL 记录 DEBUG 级别日志

#### Scenario: 健康检查失败时告警

- **Given** 数据库服务不可达或认证失败
- **When** 定时健康检查执行失败
- **Then** 系统 SHALL 记录 WARNING 级别日志，包含错误详情
- **And** 系统 SHALL NOT 因健康检查失败而中断主服务
