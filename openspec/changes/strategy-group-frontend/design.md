# Design: 策略组前端 Phase 1

## 架构决策

### 1. 页面路由作为独立 Blueprint

**决策**: 新增 `strategy_pages` Blueprint 和 `strategy_subscription` Blueprint，注册到现有 Compass Flask app。

**理由**: 现有后端 API（strategy_groups, signals, events, industry_sync）已独立为 Blueprint。页面路由和订阅 API 是新增关注点，独立 Blueprint 保持职责分离，避免修改已有的 API 路由文件。

### 2. 订阅数据存储

**决策**: 新增 `strategy_subscription` 表，使用 MySQL 唯一索引防重。

**理由**: 订阅关系是用户与策略组的 N:M 关系，需要独立存储。唯一索引在数据库层面保证幂等性，比应用层检查更可靠。

### 3. 事件详情数据组装

**决策**: 新增 `/api/events/<id>/micro`、`/api/events/<id>/macro`、`/api/events/<id>/info` 三个数据端点，在路由层组装数据。

**理由**: 前端三个 Tab 需要不同维度的数据。独立端点允许懒加载（切换 Tab 时才请求数据），减少首屏负载。数据组装在路由层而非新增 service 层，因为这些是简单的多表联查，不值得抽象为独立服务。

### 4. 宏观数据来源

**决策**: 宏观数据通过查询 `signal_snapshot` 表按日期聚合获取历史趋势，板块走势从 `stock_data_daily` 聚合同行业股票计算。

**理由**: 数据库已有 indicators_daily、signal_snapshot、stock_data_daily 表，无需引入外部数据源。行业聚合通过 stock_basic.industry 分组实现。

### 5. 信息关联数据来源

**决策**: 信息关联 Tab 通过 DataGateway 获取资讯，LLM 分析通过现有 DualLLMAnalysisService 或简单摘要生成。

**理由**: 复用现有 DataGateway 和 LLM 服务，避免重复实现。LLM 分析可异步触发，首次访问时可能为空，后续补充。

### 6. 模板继承策略

**决策**: 新增 `compass/templates/strategy/base.html` 作为策略组布局模板，继承 Compass 主布局风格（#001529 侧边栏 + #F0F2F5 内容区 + #1890FF 强调色）。

**理由**: 策略组页面是独立功能区，需要自定义侧边栏（角色分流），不适合直接复用主 index.html 布局。但视觉风格必须与 Compass 一致。

### 7. 前端技术栈

**决策**: Jinja2 服务端渲染 + ECharts（宏观数据图表）+ vanilla JS（fetch API 调接口）。

**理由**: 与项目现有技术栈一致，不引入新框架依赖。

## 数据流

### 策略发现页
```
用户 → GET /strategy/discover/
     → strategy_pages.discover()
     → db: 查询 strategy_group WHERE status='active'
     → db: 查询 strategy_subscription WHERE user_id=X
     → db: 查询 group_event WHERE status='open' 统计活跃事件数
     → 渲染 discover.html（服务端注入订阅状态）
```

### 订阅操作
```
用户点击"订阅" → JS fetch POST /api/strategy/subscription
               → strategy_subscription.subscribe()
               → db: INSERT strategy_subscription
               → JS 刷新卡片状态
```

### 事件详情页
```
用户 → GET /strategy/events/<id>/
     → strategy_pages.event_detail()
     → db: 查询 group_event WHERE id=X（含 matched_stocks JSON）
     → db: 查询 strategy_group WHERE id=X（策略组名称）
     → 渲染 event_detail.html（首屏服务端渲染摘要）

用户切Tab → JS fetch GET /api/events/<id>/micro|macro|info
          → 对应路由组装数据
          → JS 渲染 Tab 内容（ECharts / 卡片 / 资讯列表）
```

### 管理员页面
```
管理员 → GET /strategy/admin/groups/
       → strategy_pages.admin_list()
       → db: 查询所有 strategy_group（含 archived）
       → db: 统计每组 subscriber_count
       → 渲染 admin_list.html

管理员编辑 → GET /strategy/admin/groups/<id>/edit
           → strategy_pages.admin_edit()
           → db: 查询 strategy_group WHERE id=X
           → 渲染 admin_edit.html（表单预填充）

管理员保存 → JS fetch PUT /api/strategy/groups/<id>（复用已有 API）
```

## 需要新增/修改的文件

### 新增文件

| 文件 | 职责 |
|------|------|
| `compass/strategy/routes/strategy_pages.py` | 页面路由 Blueprint（discover, my, event_detail, admin_list, admin_edit） |
| `compass/strategy/routes/strategy_subscription.py` | 订阅 API Blueprint（subscribe, unsubscribe, mine, status） |
| `compass/templates/strategy/base.html` | 策略组布局模板（侧边栏 + 顶部栏 + 内容区） |
| `compass/templates/strategy/discover.html` | 策略发现页 |
| `compass/templates/strategy/my_strategies.html` | 我的策略页 |
| `compass/templates/strategy/event_detail.html` | 事件详情页（含三个 Tab） |
| `compass/templates/strategy/admin_list.html` | 管理员策略列表页 |
| `compass/templates/strategy/admin_edit.html` | 管理员策略编辑/创建页 |
| `compass/static/strategy/strategy.css` | 策略组页面统一样式 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `compass/strategy/db.py` | 新增 subscription 相关 DDL 和 CRUD 函数；新增事件微观数据查询、宏观数据聚合查询 |
| `compass/strategy/app.py` | 注册 2 个新 Blueprint（strategy_pages, strategy_subscription） |
| `compass/strategy/routes/events.py` | 新增 3 个数据端点（/micro, /macro, /info） |
