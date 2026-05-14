# Tasks: 策略组前端 Phase 1

## 1. 后端 — 数据层

- [ ] **1.1** 添加 strategy_subscription 表 DDL 和订阅 CRUD 函数
  - 在 `compass/strategy/db.py` 中新增 `_TABLES["strategy_subscription"]` DDL
  - 新增函数：`insert_subscription(user_id, strategy_group_id)`, `delete_subscription(user_id, strategy_group_id)`, `list_user_subscriptions(user_id)`, `get_subscription(user_id, strategy_group_id)`, `count_subscribers(strategy_group_id)`, `list_strategy_groups_with_subscription(user_id, status=None)`
  - 包含唯一约束防重逻辑（INSERT IGNORE 或捕获 IntegrityError 返回 409）

- [ ] **1.2** 添加事件详情数据查询函数（微观/宏观/信息）
  - 在 `compass/strategy/db.py` 中新增：
    - `get_event_micro_data(event_id)` — 从 signal_snapshot 获取触发个股指标快照 + 从 stock_analysis 获取 buy 值
    - `get_event_macro_data(event_id)` — 聚合同行业股票在 signal_snapshot 中的历史趋势（按日分组统计 stock_count, avg_buy_star）+ 从 stock_data_daily 聚合板块涨跌
    - `get_event_info_data(event_id)` — 获取 matched_stocks 列表用于资讯查询

## 2. 后端 — API 路由

- [ ] **2.1** 添加订阅 API Blueprint
  - 新建 `compass/strategy/routes/strategy_subscription.py`
  - Blueprint url_prefix: `/api/strategy`
  - 端点：
    - `POST /subscription` — 订阅（需登录，检查策略组存在且 active）
    - `DELETE /subscription/<int:group_id>` — 取消订阅
    - `GET /subscription/mine` — 查询当前用户订阅列表
  - 所有端点需检查 session["uid"]，未登录返回 401
  - 注册到 `compass/strategy/app.py`

- [ ] **2.2** 添加事件详情数据端点
  - 修改 `compass/strategy/routes/events.py`，新增 3 个端点：
    - `GET /events/<int:event_id>/micro` — 返回微观数据 JSON
    - `GET /events/<int:event_id>/macro` — 返回宏观数据 JSON（含趋势数据和板块走势）
    - `GET /events/<int:event_id>/info` — 返回信息关联数据 JSON（调用 DataGateway 获取资讯 + 返回 matched_stocks 关联信息）

## 3. 后端 — 页面路由

- [ ] **3.1** 添加策略组页面路由 Blueprint
  - 新建 `compass/strategy/routes/strategy_pages.py`
  - Blueprint name: `strategy_pages`, 无 url_prefix
  - 端点：
    - `GET /strategy/discover/` — 策略发现页（服务端查询 active 策略组 + 用户订阅状态 + 活跃事件数统计）
    - `GET /strategy/my/` — 我的策略页（查询用户订阅 + 每个订阅策略的 open 事件）
    - `GET /strategy/events/<int:event_id>/` — 事件详情页（查询事件基本信息渲染首屏）
    - `GET /strategy/admin/groups/` — 管理员策略列表页（需 admin 权限检查）
    - `GET /strategy/admin/groups/<int:group_id>/edit` — 管理员编辑页（需 admin 权限检查）
    - `GET /strategy/admin/groups/new` — 管理员创建页（需 admin 权限检查）
  - 所有端点需检查登录状态，未登录重定向到 /login
  - admin 端点复用 `_is_admin()` 模式检查 `user.is_admin == 1`
  - 注册到 `compass/strategy/app.py` 的 `register_blueprints`

## 4. 后端 — Blueprint 注册

- [ ] **4.1** 注册新 Blueprint 到 strategy app
  - 修改 `compass/strategy/app.py`：
    - import 并注册 `strategy_subscription` bp
    - import 并注册 `strategy_pages` bp

## 5. 前端 — 页面模板和样式（scope: frontend，需人工完成）

- [ ] **5.1** 创建策略组基础布局模板 `compass/templates/strategy/base.html`
  - 复用 Compass 侧边栏风格（#001529 深色 + #F0F2F5 内容区 + #1890FF 强调色）
  - 侧边栏根据 `is_admin` 变量动态显示"策略发现"、"我的策略"、"策略管理"
  - 顶部栏显示用户名和返回主页入口
  - 包含 ECharts CDN 引用和 strategy.css 引用

- [ ] **5.2** 创建策略发现页 `compass/templates/strategy/discover.html`
  - 继承 base.html
  - 顶部统计栏：可订阅策略数、已订阅数、活跃事件数
  - 策略组卡片网格：名称、指标标签、条件摘要、订阅状态/按钮
  - JS 逻辑：点击"订阅"调用 POST /api/strategy/subscription，点击"取消订阅"调用 DELETE

- [ ] **5.3** 创建我的策略页 `compass/templates/strategy/my_strategies.html`
  - 继承 base.html
  - 每个已订阅策略组为一个折叠区域
  - 展开后显示该策略的活跃事件卡片列表
  - 事件卡片可点击跳转到 /strategy/events/<id>/
  - 空状态和无活跃状态提示
  - 取消订阅按钮

- [ ] **5.4** 创建事件详情页 `compass/templates/strategy/event_detail.html`
  - 继承 base.html
  - 顶部事件摘要区域
  - 三个 Tab 切换：微观数据 / 宏观数据 / 信息关联
  - 微观数据：个股指标快照卡片网格（JS fetch /api/events/<id>/micro）
  - 宏观数据：ECharts 行业趋势图 + 板块走势图 + 统计表（JS fetch /api/events/<id>/macro）
  - 信息关联：LLM 分析区 + 驱动因素 + 资讯流列表（JS fetch /api/events/<id>/info）
  - 管理员可见"确认关闭"按钮（调用 PATCH /api/events/<id>/close）

- [ ] **5.5** 创建管理员策略列表页 `compass/templates/strategy/admin_list.html`
  - 继承 base.html
  - 策略组表格：名称、状态、指标、cron、订阅人数、操作按钮
  - 操作：编辑（跳转编辑页）、启停（调用 PATCH /api/strategy/groups/<id>/status）、删除（调用 DELETE /api/strategy/groups/<id>）
  - "创建新策略组"按钮

- [ ] **5.6** 创建管理员策略编辑页 `compass/templates/strategy/admin_edit.html`
  - 继承 base.html
  - 表单字段：名称、指标列表（多选或逗号分隔）、信号逻辑（AND/OR/SCORING下拉）、条件列表（动态添加/删除）、聚合规则（维度/最小股票数/时间窗口）、cron 表达式、SCORING 阈值
  - 提交调用 POST/PUT /api/strategy/groups

- [ ] **5.7** 创建策略组统一样式 `compass/static/strategy/strategy.css`
  - 卡片样式、Tab 样式、表格样式、按钮样式
  - 响应式布局
  - 与 Compass 现有风格一致的配色方案
