# Delta Spec: 我的策略页增强

## MODIFIED Requirements

### Requirement: 订阅策略组概览卡片

my_strategies.html SHALL 展示用户已订阅的策略组卡片，每个卡片包含：
- 策略组名称
- 活跃事件数
- 最新事件触发时间
- 点击卡片展开该策略组下的事件列表

#### Scenario: 加载我的策略页

```
Given 用户已订阅 2 个策略组
When 用户访问 /strategy/my
Then 页面调用 GET /api/strategy/subscriptions 获取订阅列表
And 调用 GET /api/events?subscribed=true 获取关联事件
And 展示 2 张策略组概览卡片，每张显示活跃事件数和最新事件时间
```

### Requirement: 事件卡片 lifecycle 状态标签

每个事件卡片 SHALL 展示 lifecycle 状态标签：
- `tracking` → 绿色标签 "跟踪中"
- `suggest_close` → 黄色标签 "建议关闭"（带警告图标）
- `closed` → 灰色标签 "已关闭"

#### Scenario: 显示不同 lifecycle 状态的事件

```
Given 策略组 A 下有 3 个事件，lifecycle 分别为 tracking、suggest_close、closed
When 用户展开策略组 A 的事件列表
Then tracking 事件显示绿色"跟踪中"标签
And suggest_close 事件显示黄色"建议关闭"标签
And closed 事件显示灰色"已关闭"标签
```

### Requirement: 事件卡片点击导航

事件卡片 SHALL 可点击，导航到对应事件详情页。

#### Scenario: 点击事件卡片

```
Given 事件列表已展示
When 用户点击某事件卡片
Then 页面跳转到 /strategy/events/{event_id}
```

### Requirement: 事件卡片基础信息

每个事件卡片 SHALL 展示：
- 维度值（如行业名称或概念名称）
- 触发股票数量
- buy_star 确认度
- 触发日期

#### Scenario: 事件卡片信息展示

```
Given 存在一个事件：维度值="半导体", 触发股票=8, buy_star=0.75, 触发日期=2025-01-15
When 该事件卡片渲染完成
Then 卡片显示"半导体 | 8只股票 | 确认度 0.75 | 2025-01-15"
```
