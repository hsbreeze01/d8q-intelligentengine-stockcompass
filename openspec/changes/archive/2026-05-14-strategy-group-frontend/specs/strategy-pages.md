# Delta Spec: 策略组页面路由与角色分流

## ADDED Requirements

### Requirement: 策略发现页

系统 SHALL 提供策略发现页面路由 `/strategy/discover/`，展示所有可订阅的策略组。

#### Scenario: 访问策略发现页

- Given 用户已登录
- When 用户访问 GET /strategy/discover/
- Then 系统 SHALL 渲染 discover.html 模板
- And 页面顶部展示统计信息：可订阅策略数、已订阅数、活跃事件数
- And 页面展示所有 status=active 的策略组卡片
- And 每张卡片显示策略名称、指标列表、信号逻辑、条件摘要
- And 已订阅策略的卡片显示"已订阅"标签
- And 未订阅策略的卡片显示"订阅此策略"按钮

#### Scenario: 未登录访问

- Given 用户未登录
- When 用户访问 GET /strategy/discover/
- Then 系统 SHALL 重定向到登录页

---

### Requirement: 我的策略页

系统 SHALL 提供"我的策略"页面路由 `/strategy/my/`，展示用户已订阅的策略及活跃事件。

#### Scenario: 有订阅和活跃事件

- Given 用户已订阅策略组 id=10，该策略组有 2 个 status=open 的事件
- When 用户访问 GET /strategy/my/
- Then 系统 SHALL 渲染 my_strategies.html 模板
- And 展示策略组 id=10 的卡片
- And 策略组卡片下方展示 2 个活跃事件卡片
- And 每个事件卡片显示：维度值、触发股票数、平均 buy_star、创建时间
- And 每个事件卡片可点击跳转到事件详情页

#### Scenario: 无订阅

- Given 用户未订阅任何策略组
- When 用户访问 GET /strategy/my/
- Then 系统 SHALL 显示空状态提示"暂无订阅的策略，去策略发现页浏览"

#### Scenario: 有订阅但无活跃事件

- Given 用户已订阅策略组 id=10，该策略组无 open 状态事件
- When 用户访问 GET /strategy/my/
- Then 系统 SHALL 在策略组卡片下方显示"暂无活跃事件"

---

### Requirement: 事件详情页

系统 SHALL 提供事件详情页路由 `/strategy/events/<event_id>/`，支持三个维度 Tab 切换。

#### Scenario: 访问事件详情页

- Given 存在事件 id=5
- When 用户访问 GET /strategy/events/5/
- Then 系统 SHALL 渲染 event_detail.html 模板
- And 顶部展示事件摘要：策略组名称、维度值、触发股票数、确认度(avg_buy_star)、持续天数、板块涨跌
- And 页面包含三个 Tab：微观数据、宏观数据、信息关联

#### Scenario: 微观数据 Tab

- Given 事件 id=5 包含 8 只触发股票
- When 用户切换到"微观数据"Tab
- Then 系统 SHALL 展示 8 只个股的指标快照卡片
- And 每张卡片显示：股票代码、股票名称、buy_star、涨跌幅
- And 卡片展示触发时刻的指标值（如 KDJ/RSI/量比/MACD 等）

#### Scenario: 宏观数据 Tab

- Given 事件 id=5 的维度为 industry，维度值为"电子"
- When 用户切换到"宏观数据"Tab
- Then 系统 SHALL 展示行业趋势指标聚合 ECharts 图表
- And 展示板块走势图
- And 展示每日跟踪统计表（日期、触发股票数、avg_buy_star 变化）

#### Scenario: 信息关联 Tab

- Given 事件 id=5 的维度值为"电子"
- When 用户切换到"信息关联"Tab
- Then 系统 SHALL 展示 LLM 分析摘要（如有）
- And 展示驱动因素列表
- And 展示关联主题标签
- And 展示相关资讯流（按相关性排序）

#### Scenario: 事件不存在

- Given 事件 id=999 不存在
- When 用户访问 GET /strategy/events/999/
- Then 系统 SHALL 返回 404 页面

#### Scenario: 管理员关闭事件

- Given 管理员已登录，事件 id=5 的 status 为 open
- When 管理员点击"确认关闭"按钮
- Then 系统 SHALL 调用 PATCH /api/events/5/close
- And 事件状态变为 closed
- And 页面刷新后关闭按钮消失

---

### Requirement: 事件详情数据 API

系统 SHALL 提供事件详情的微观数据和宏观数据 API 端点。

#### Scenario: 获取微观数据

- Given 事件 id=5 存在
- When 前端发起 GET /api/events/5/micro 请求
- Then 系统 SHALL 返回事件下所有触发个股的指标快照
- And 包含从 signal_snapshot 获取的 indicator_snapshot 详细数据
- And 包含从 stock_analysis 获取的 buy 值

#### Scenario: 获取宏观数据

- Given 事件 id=5 存在，维度为 industry，维度值为"电子"
- When 前端发起 GET /api/events/5/macro 请求
- Then 系统 SHALL 返回该行业的趋势指标聚合数据
- And 包含最近 N 日该行业所有股票的指标分布统计
- And 包含板块走势数据（日期、涨跌幅）

#### Scenario: 获取信息关联数据

- Given 事件 id=5 存在，matched_stocks 包含 ["000001", "000002"]
- When 前端发起 GET /api/events/5/info 请求
- Then 系统 SHALL 返回相关资讯流（通过 DataGateway 获取）
- And 返回触发股票的行业/概念关联
- And 返回 LLM 分析摘要（如已有）

---

### Requirement: 管理员策略管理页

系统 SHALL 提供策略管理页面，管理员可创建/编辑/启停策略组。

#### Scenario: 访问策略管理列表

- Given 管理员已登录
- When 访问 GET /strategy/admin/groups/
- Then 系统 SHALL 渲染 admin_list.html 模板
- And 展示所有策略组列表（含 archived 状态）
- And 每行显示：名称、状态、指标、扫描频率、订阅人数
- And 提供编辑、启停、删除操作按钮
- And 提供创建新策略组按钮

#### Scenario: 非管理员访问

- Given 用户 is_admin 不为 1
- When 用户访问 /strategy/admin/groups/
- Then 系统 SHALL 重定向到登录页或返回 403

#### Scenario: 访问策略组编辑页

- Given 管理员已登录，策略组 id=10 存在
- When 访问 GET /strategy/admin/groups/10/edit
- Then 系统 SHALL 渲染 admin_edit.html 模板
- And 表单预填充策略组的现有配置（名称、指标、条件、聚合规则、cron）
- And 提供"保存"和"取消"按钮

#### Scenario: 创建新策略组

- Given 管理员已登录
- When 访问 GET /strategy/admin/groups/new
- Then 系统 SHALL 渲染 admin_edit.html 模板（空白表单）
- And 提交时调用 POST /api/strategy/groups

---

### Requirement: 角色分流侧边栏

系统 SHALL 根据用户角色在侧边栏显示不同的策略组导航项。

#### Scenario: 普通用户侧边栏

- Given 用户已登录，is_admin 不为 1
- When 用户访问任何策略组页面
- Then 侧边栏 SHALL 显示"策略发现"和"我的策略"两个导航项
- And 不显示"策略管理"导航项

#### Scenario: 管理员侧边栏

- Given 用户已登录，is_admin 为 1
- When 用户访问任何策略组页面
- Then 侧边栏 SHALL 显示"策略发现"、"我的策略"和"策略管理"三个导航项
- And 导航项不分组，与其他 Compass 导航项平级展示
