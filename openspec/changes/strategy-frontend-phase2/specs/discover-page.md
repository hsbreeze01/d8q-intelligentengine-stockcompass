# Delta Spec: 策略发现页完善

## MODIFIED Requirements

### Requirement: 策略卡片网格布局

discover.html SHALL 以响应式卡片网格展示所有策略组，每张卡片包含：
- 策略组名称（strategy_name）
- 策略描述（description）
- 维度名称 + 指标名称
- 状态标签（active=绿色，paused=灰色）
- 当前活跃事件数
- 订阅/取消订阅按钮

#### Scenario: 加载策略发现页

```
Given 用户访问 /strategy/discover
When 页面加载完成
Then 页面调用 GET /api/strategy/groups 获取策略组列表
And 以卡片网格（每行最多3张）展示所有策略组
And 每张卡片显示策略名称、描述、维度、指标名、状态标签、活跃事件数
```

#### Scenario: 订阅策略组

```
Given 策略发现页已加载，用户未订阅某策略组
When 用户点击该策略卡片上的"订阅"按钮
Then 页面发送 POST /api/strategy/subscribe（body: {strategy_id}）
And 按钮变为"已订阅"状态（蓝色实心）
And 页面提示"订阅成功"
```

#### Scenario: 取消订阅策略组

```
Given 策略发现页已加载，用户已订阅某策略组
When 用户点击该策略卡片上的"已订阅"按钮
Then 页面发送 DELETE /api/strategy/subscribe（body: {strategy_id}）
And 按钮恢复为"订阅"状态（蓝色空心）
And 页面提示"已取消订阅"
```

### Requirement: 策略卡片订阅状态初始化

页面加载时 SHALL 通过 GET /api/strategy/subscriptions 获取当前用户的订阅列表，将已订阅策略组的按钮标记为"已订阅"状态。

#### Scenario: 已订阅策略组显示已订阅状态

```
Given 用户已订阅策略组 A
When 策略发现页加载完成
Then 策略组 A 的卡片上按钮显示为"已订阅"（蓝色实心）
And 其他未订阅策略组的按钮显示为"订阅"（蓝色空心）
```
