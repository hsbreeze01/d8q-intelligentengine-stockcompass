# Delta Spec: 策略组订阅

## ADDED Requirements

### Requirement: 策略组订阅数据持久化

系统 SHALL 创建 `strategy_subscription` 表，存储用户与策略组的订阅关系。

#### Scenario: 首次启动自动建表

- Given 系统启动时 strategy_subscription 表不存在
- When 策略组引擎初始化执行
- Then 系统 SHALL 自动创建 strategy_subscription 表，包含字段：id, user_id, strategy_group_id, subscribed_at
- And 表 SHALL 具有 uk_user_strategy 唯一约束（user_id + strategy_group_id），防止重复订阅

---

### Requirement: 用户订阅策略组

已登录用户 SHALL 能订阅状态为 active 的策略组。

#### Scenario: 成功订阅

- Given 用户已登录（session 中存在 uid）
- And 存在一个 status=active 的策略组（id=10）
- And 用户尚未订阅该策略组
- When 用户发起 POST /api/strategy/subscription 请求（body: {strategy_group_id: 10}）
- Then 系统 SHALL 在 strategy_subscription 表插入一条记录
- And 返回 201 状态码及订阅信息 {id, user_id, strategy_group_id, subscribed_at}

#### Scenario: 重复订阅

- Given 用户已订阅策略组 id=10
- When 用户再次发起订阅请求（strategy_group_id: 10）
- Then 系统 SHALL 返回 409 状态码及错误信息 "已订阅该策略"

#### Scenario: 订阅不存在的策略组

- Given 策略组 id=999 不存在
- When 用户发起订阅请求（strategy_group_id: 999）
- Then 系统 SHALL 返回 404 状态码及错误信息 "策略组不存在"

#### Scenario: 订阅非 active 策略组

- Given 策略组 id=10 的 status 为 paused
- When 用户发起订阅请求（strategy_group_id: 10）
- Then 系统 SHALL 返回 400 状态码及错误信息 "该策略组不可订阅"

#### Scenario: 未登录用户订阅

- Given 用户未登录（session 中无 uid）
- When 用户发起订阅请求
- Then 系统 SHALL 返回 401 状态码

---

### Requirement: 用户取消订阅策略组

已登录用户 SHALL 能取消已订阅的策略组。

#### Scenario: 成功取消订阅

- Given 用户已订阅策略组 id=10
- When 用户发起 DELETE /api/strategy/subscription/<strategy_group_id> 请求
- Then 系统 SHALL 删除 strategy_subscription 中的对应记录
- And 返回 200 状态码及消息 "已取消订阅"

#### Scenario: 取消未订阅的策略组

- Given 用户未订阅策略组 id=10
- When 用户发起取消订阅请求
- Then 系统 SHALL 返回 404 状态码及错误信息 "未订阅该策略"

---

### Requirement: 查询用户订阅列表

已登录用户 SHALL 能查询自己订阅的所有策略组。

#### Scenario: 查询订阅列表

- Given 用户已订阅策略组 id=10 和 id=20
- When 用户发起 GET /api/strategy/subscription/mine 请求
- Then 系统 SHALL 返回 200 状态码及订阅列表
- And 列表每项包含策略组详情（id, name, indicators, signal_logic, status）及订阅时间

#### Scenario: 无订阅

- Given 用户未订阅任何策略组
- When 用户查询订阅列表
- Then 系统 SHALL 返回 200 状态码及空列表 []

---

### Requirement: 查询策略组的订阅状态

系统 SHALL 支持在策略组列表中嵌入当前用户的订阅状态。

#### Scenario: 策略发现页带订阅标记

- Given 用户已订阅策略组 id=10，未订阅 id=20
- When 用户发起 GET /api/strategy/groups?with_subscription=true 请求
- Then 系统 SHALL 返回策略组列表
- And 策略组 id=10 的响应中包含 subscribed: true
- And 策略组 id=20 的响应中包含 subscribed: false
- And 策略组 id=10 的响应中包含 subscribed_at 时间戳

---

### Requirement: 查询策略组订阅统计

系统 SHALL 支持查询策略组的订阅人数。

#### Scenario: 管理员查看订阅统计

- Given 策略组 id=10 有 5 名订阅者
- When 管理员查询策略组列表
- Then 系统 SHALL 在策略组信息中返回 subscriber_count: 5
