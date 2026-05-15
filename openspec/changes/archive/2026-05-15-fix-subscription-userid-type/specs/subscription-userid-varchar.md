# Delta Spec: 策略订阅 user_id 类型兼容字符串用户名

## MODIFIED Requirements

### Requirement: strategy_subscription.user_id 列类型

`strategy_subscription` 表的 `user_id` 列 SHALL 使用 `VARCHAR(100)` 类型，
以同时兼容整型用户 ID 和字符串用户名（如 Factory 代理通过 `X-Forwarded-User` 传递的 `"admin"`）。

#### Scenario: 通过字符串用户名订阅策略组

- **Given** 用户已通过 Factory 代理认证
- **And** `X-Forwarded-User` header 值为 `"admin"`
- **When** 用户点击订阅策略组 ID=1
- **Then** 系统 SHALL 成功创建订阅记录，`user_id` 存储为 `"admin"`
- **And** 响应状态码为 201

#### Scenario: 通过字符串用户名取消订阅

- **Given** 用户已订阅策略组，`user_id = "admin"`
- **When** 用户取消订阅同一策略组
- **Then** 系统 SHALL 成功删除订阅记录
- **And** 响应状态码为 200

#### Scenario: 通过字符串用户名查询订阅列表

- **Given** 用户已订阅多个策略组，`user_id = "admin"`
- **When** 用户查询自己的订阅列表
- **Then** 系统 SHALL 返回该用户的所有订阅记录
- **And** 响应状态码为 200

#### Scenario: 策略组列表附带字符串用户名的订阅状态

- **Given** 用户 `user_id = "admin"` 已订阅策略组 ID=1
- **When** 请求策略组列表（含订阅状态）
- **Then** 策略组 ID=1 的 `subscribed` 字段 SHALL 为 `true`
- **And** 策略组 ID=2（未订阅）的 `subscribed` 字段 SHALL 为 `false`

#### Scenario: 唯一约束兼容字符串 user_id

- **Given** 用户 `"admin"` 已订阅策略组 ID=1
- **When** 用户再次尝试订阅策略组 ID=1
- **Then** 系统 SHALL 返回 409 错误，提示"已订阅该策略"
- **And** 数据库中 SHALL 只有一条 `(user_id="admin", strategy_group_id=1)` 记录

### Requirement: 现有整型 user_id 数据迁移

系统 SHALL 在 DDL 变更后自动迁移已有的整型 `user_id` 数据，
确保 `(1, strategy_group_id)` 等现有记录不受影响。

#### Scenario: 已有整型订阅记录在新 DDL 下仍可查询

- **Given** 变更前存在 `user_id = 1`（INT）的订阅记录
- **When** 执行 ALTER TABLE 将 `user_id` 改为 VARCHAR(100)
- **Then** 该记录 SHALL 自动转为 `user_id = "1"`（VARCHAR）
- **And** 通过 `user_id = 1` 或 `user_id = "1"` 查询 SHALL 均能命中该记录
