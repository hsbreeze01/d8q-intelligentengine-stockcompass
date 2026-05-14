# 策略组前端 Phase 1 — 角色分流 UI 实施

## 背景

策略组引擎后端已完成（commit 8476d84），包含 CRUD API、信号扫描器、群体事件聚合器。
现在需要实施前端页面，让用户可以浏览/订阅策略并查看事件详情。

## 设计文档

- 交互设计稿 HTML: `docs/Strategy_Group_UX_Wireframe.html` (v3.1)
- UX 设计文档: `docs/Strategy_Group_UX_Design.md` (v2.0)
- 产品需求: `docs/Strategy_Group_Product_Requirements.md` (v1.4)

## 核心要求

### 角色模型
- **Admin/Editor**: 看到侧边栏"策略管理"tab，可创建/编辑/启停策略组
- **User**: 看到"策略发现"和"我的策略"两个 tab
- 角色判断基于 session 中的用户角色字段

### 用户页面（3个页面 + 1个子页面）

1. **策略发现页** `/strategy/discover/`
   - 展示所有 status=active 的策略组卡片
   - 已订阅策略显示"已订阅"标签和"查看我的策略"入口
   - 未订阅策略显示"订阅此策略"按钮
   - 顶部统计：可订阅策略数、已订阅数、活跃事件数

2. **我的策略页** `/strategy/my/`
   - 展示当前用户已订阅的策略组
   - 每个策略组下方展示该策略的活跃事件卡片
   - 无活跃事件显示空状态
   - 可取消订阅
   - **点击事件卡片 → 进入事件详情页**

3. **事件详情页** `/strategy/events/<id>/`
   - 顶部：事件摘要（触发股票数、确认度、持续天数、板块涨跌）
   - **Tab 切换三个维度**:
     - 🔬 微观数据: 触发个股的指标快照卡片（KDJ/RSI/量比/MACD/涨跌幅/buy_star）
     - 📊 宏观数据: 行业趋势指标聚合 ECharts 图 + 板块走势图 + 每日跟踪统计表
     - 🔗 信息关联: LLM 分析摘要 + 驱动因素 + 关联主题 + 资讯流（按相关性排序）
   - 生命周期管理（底部，管理员可操作"确认关闭"）

### 管理员页面（复用后端已有API）

4. **策略管理页** `/strategy/admin/groups/`
   - 策略组列表（含编辑/启停/删除操作）
   - 点击策略组 → 详情页

5. **策略组配置页** `/strategy/admin/groups/<id>/edit`
   - 创建/编辑策略组表单

### 技术约束

- **技术栈**: Jinja2 + ECharts + vanilla JS（fetch API）
- **风格**: 复用现有 Compass 侧边栏风格（#001529 深色 + #F0F2F5 内容区 + #1890FF 强调色）
- **路由**: 作为 Flask Blueprint 注册到现有 Compass app
- **DB**: 复用 `compass/data/database.py` 的 Database 连接池
- **订阅表**: 需创建 `strategy_subscription` 表
- **侧边栏**: 不同角色显示不同导航项，不分组

### 数据模型

需新增 `strategy_subscription` 表：
```sql
CREATE TABLE IF NOT EXISTS strategy_subscription (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    strategy_group_id INT NOT NULL,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_strategy (user_id, strategy_group_id)
);
```

### 文件结构

```
compass/strategy/
├── routes/
│   ├── strategy_groups.py  (已有，API)
│   ├── strategy_pages.py   (新增，页面路由)
│   └── strategy_subscription.py (新增，订阅API)
├── templates/strategy/
│   ├── base.html            (布局模板：侧边栏+顶部栏)
│   ├── discover.html        (策略发现)
│   ├── my_strategies.html   (我的策略)
│   ├── event_detail.html    (事件详情)
│   ├── admin_list.html      (策略管理)
│   └── admin_edit.html      (策略配置)
└── static/strategy/
    └── strategy.css         (策略组样式)
```

## 验收标准

1. 用户角色登录后看到"策略发现"和"我的策略"两个侧边栏入口
2. 管理员角色登录后看到"策略管理"侧边栏入口
3. 策略发现页可订阅/取消订阅策略组
4. 我的策略页展示已订阅策略及活跃事件
5. 点击事件卡片可进入事件详情页，三个 Tab 可正常切换
6. 事件详情微观 Tab 展示个股指标快照
7. 事件详情宏观 Tab 展示 ECharts 趋势图
8. 事件详情信息关联 Tab 展示 LLM 分析和资讯流
9. 管理员可创建/编辑/启停策略组
10. 所有页面风格与现有 Compass 一致
