# Delta Spec: 事件详情页三维度展示

## MODIFIED Requirements

### Requirement: 顶部事件摘要栏

event_detail.html SHALL 在页面顶部展示事件摘要信息：
- 策略组名称 + 事件维度值
- 触发股票数、buy_star 确认度、持续天数
- lifecycle 状态标签（tracking=绿色、suggest_close=黄色、closed=灰色）
- LLM 置信度进度条（confidence 0→1）
- 消息面确认图标（news_confirmed=true 显示 ✓绿色，false 显示 ✗灰色）

#### Scenario: 事件摘要栏展示 tracking 状态事件

```
Given 事件 ID=42，策略组="行业动量"，维度值="半导体"，lifecycle="tracking"
And 触发股票数=8，buy_star=0.75，持续天数=3，confidence=0.82，news_confirmed=true
When 用户访问 /strategy/events/42
Then 顶部摘要栏显示"行业动量 > 半导体"
And 显示"8只股票 | 确认度 0.75 | 持续3天"
And lifecycle 标签为绿色"跟踪中"
And LLM 置信度进度条填充至 82%
And 消息面确认显示绿色 ✓
```

### Requirement: 管理员关闭事件按钮

当用户为管理员且事件 lifecycle 为 `suggest_close` 或 `closed` 时，摘要栏 SHALL 显示"关闭事件"按钮。点击后调用 `POST /api/events/{id}/close`。

#### Scenario: 管理员关闭 suggest_close 事件

```
Given 用户为管理员，事件 ID=42 lifecycle="suggest_close"
When 用户点击"关闭事件"按钮
Then 页面发送 POST /api/events/42/close
And 成功后 lifecycle 标签变为灰色"已关闭"
And 关闭按钮消失或变为禁用状态
```

#### Scenario: 普通用户不显示关闭按钮

```
Given 用户为普通用户
When 用户访问事件详情页
Then 无论事件 lifecycle 状态如何，均不显示"关闭事件"按钮
```

### Requirement: 微观数据 Tab

事件详情页 SHALL 提供"微观"Tab，展示：
- 触发个股表格（股票代码、名称、buy_star、指标快照）
- ECharts 散点图（x=buy_star, y=RSI 或类似指标）

#### Scenario: 切换到微观数据 Tab

```
Given 用户已进入事件详情页
When 用户点击"微观"Tab
Then 页面调用 GET /api/events/{id}/micro 获取微观数据
And 展示触发个股表格，按 buy_star 降序排列
And 渲染 ECharts 散点图，每只股票一个点
```

### Requirement: 宏观数据 Tab

事件详情页 SHALL 提供"宏观"Tab，展示：
- 板块维度聚合数据
- ECharts 饼图展示板块分布

#### Scenario: 切换到宏观数据 Tab

```
Given 用户已进入事件详情页
When 用户点击"宏观"Tab
Then 页面调用 GET /api/events/{id}/macro 获取宏观数据
And 展示板块聚合列表
And 渲染 ECharts 饼图展示各板块股票数量占比
```

### Requirement: 信息关联 Tab（Phase 2 核心）

事件详情页 SHALL 提供"信息"Tab，展示完整的 LLM 分析和资讯关联：
- LLM 分析摘要（llm_summary，Markdown 渲染）
- 关键词标签云（llm_keywords）
- 驱动因素列表（llm_drivers）
- 关联主题标签（llm_related_themes）
- 消息面确认度进度条（news_confirm_score）+ 匹配资讯数
- 关联资讯列表（标题 + 来源 + 时间）

#### Scenario: 切换到信息关联 Tab

```
Given 用户已进入事件详情页，事件有 LLM 分析结果
When 用户点击"信息"Tab
Then 页面调用 GET /api/events/{id}/info 获取信息关联数据
And 以 Markdown 渲染 llm_summary
And 以标签形式展示 llm_keywords
And 以列表展示 llm_drivers
And 以标签形式展示 llm_related_themes
And 以进度条展示 news_confirm_score 并标注匹配资讯数
And 展示关联资讯列表（标题可点击）
```

#### Scenario: 事件无 LLM 分析结果

```
Given 事件无 LLM 分析结果（llm_summary 为空）
When 用户查看信息 Tab
Then 显示"暂无 LLM 分析结果"提示
And 关键词、驱动因素、主题区域均显示"暂无数据"
```

### Requirement: 趋势跟踪折线图

信息关联 Tab SHALL 展示趋势跟踪 ECharts 折线图，调用 `GET /api/events/{id}/trend` 获取数据，x 轴为日期，y 轴为 avg_score。

#### Scenario: 渲染趋势跟踪图表

```
Given 事件有多日趋势数据
When 用户查看信息 Tab
Then 页面调用 GET /api/events/{id}/trend
And 渲染 ECharts 折线图，x 轴为日期，y 轴为 avg_score
And 图表标题为"趋势跟踪"
```

### Requirement: Tab 切换状态管理

三个 Tab（微观/宏观/信息）SHALL 互斥切换，切换时仅加载当前 Tab 数据，不重复加载已加载的 Tab。

#### Scenario: Tab 数据懒加载

```
Given 用户首次进入事件详情页
When 默认展示"微观"Tab
Then 仅调用 GET /api/events/{id}/micro 加载数据
And 不调用 /macro 和 /info 接口

When 用户切换到"宏观"Tab
Then 调用 GET /api/events/{id}/macro
And 微观数据保留在 DOM 中

When 用户再次切回"微观"Tab
Then 不重新调用 /micro 接口，直接显示缓存数据
```
