# Tasks: 策略组前端 Phase 2

## 1. 后端路由数据准备

- [x] **1.1 增强 strategy_pages.py 路由上下文数据** — 为所有策略组页面路由传递 `is_admin` 标志；为事件详情路由查询完整 event 记录（含 llm_summary, llm_confidence, llm_keywords, llm_drivers, llm_related_themes, news_confirmed, news_confirm_score, lifecycle, buy_star, dimension_value）并传递给模板；确保 admin 检测逻辑复用现有 session + DB 查询模式
  - scope: backend
  - files: `compass/strategy/routes/strategy_pages.py`

## 2. 基础模板和样式（scope: frontend — 需人工完成）

- [x] **2.1 重写 base.html 完整布局和全局辅助** — Compass 风格侧边栏（#001529 背景，三导航项按角色显示）、顶部用户信息栏、主内容区 #F0F2F5 背景；引入 ECharts CDN + marked.js CDN；全局 `<script>` 定义 `fetchJSON()` 和 `renderLifecycleBadge()` 辅助函数；子模板通过 `{% block content %}` 注入内容
  - scope: frontend
  - files: `compass/templates/strategy/base.html`

## 3. 策略发现页（scope: frontend — 需人工完成）

- [x] **3.1 实现 discover.html 策略卡片网格和订阅交互** — 卡片网格布局（每行最多 3 张），展示策略名称/描述/维度/指标/状态标签/活跃事件数；页面加载时 fetch `/api/strategy/groups` + `/api/strategy/subscriptions` 初始化卡片和订阅状态；订阅按钮点击调用 POST/DELETE `/api/strategy/subscribe` 并更新按钮状态
  - scope: frontend
  - files: `compass/templates/strategy/discover.html`

## 4. 我的策略页（scope: frontend — 需人工完成）

- [x] **4.1 实现 my_strategies.html 策略组概览和事件卡片** — 策略组概览卡片（名称、活跃事件数、最新时间）；展开显示事件卡片列表，每张卡片展示维度值/股票数/buy_star/日期 + lifecycle 状态标签（tracking=绿/suggest_close=黄/closed=灰）；卡片可点击跳转到 `/strategy/events/{id}`
  - scope: frontend
  - files: `compass/templates/strategy/my_strategies.html`

## 5. 事件详情页（scope: frontend — 需人工完成）

- [x] **5.1 实现事件详情页顶部摘要栏和三维度 Tab 框架** — SSR 渲染摘要栏（策略组名+维度值、股票数、buy_star、持续天数、lifecycle 标签、LLM 置信度进度条、消息面确认图标）；管理员关闭按钮（仅 admin + suggest_close/closed 时显示，调用 POST `/api/events/{id}/close`）；三个 Tab（微观/宏观/信息）互斥切换 + 懒加载缓存机制
  - scope: frontend
  - files: `compass/templates/strategy/event_detail.html`

- [x] **5.2 实现微观数据 Tab（个股表格 + ECharts 散点图）** — fetch `/api/events/{id}/micro`，展示触发个股表格（代码/名称/buy_star/指标快照，按 buy_star 降序）+ ECharts 散点图（x=buy_star, y=RSI）
  - scope: frontend
  - files: `compass/templates/strategy/event_detail.html`

- [x] **5.3 实现宏观数据 Tab（板块聚合 + ECharts 饼图）** — fetch `/api/events/{id}/macro`，展示板块维度聚合列表 + ECharts 饼图（各板块股票数占比）
  - scope: frontend
  - files: `compass/templates/strategy/event_detail.html`

- [x] **5.4 实现信息关联 Tab（LLM 分析 + 资讯 + 趋势折线图）** — fetch `/api/events/{id}/info`，展示 llm_summary（marked.js Markdown 渲染）、llm_keywords 标签云、llm_drivers 列表、llm_related_themes 标签、news_confirm_score 进度条 + 匹配资讯数、关联资讯列表（标题/来源/时间）；fetch `/api/events/{id}/trend`，ECharts 折线图展示 avg_score 随时间变化；无数据时显示"暂无 LLM 分析结果"占位
  - scope: frontend
  - files: `compass/templates/strategy/event_detail.html`

## 6. 管理员页面样式（scope: frontend — 需人工完成）

- [x] **6.1 完善 admin_list.html 表格样式和操作交互** — Compass 风格表格（斑马纹、悬停高亮）；操作按钮（编辑=蓝、暂停/恢复=黄/绿、删除=红）；"新建策略组"按钮跳转 `/strategy/admin/new`
  - scope: frontend
  - files: `compass/templates/strategy/admin_list.html`

- [x] **6.2 完善 admin_edit.html 表单样式** — Compass 风格表单（统一圆角输入框、#1890FF 提交按钮）；支持创建和编辑两种模式（通过模板变量区分）；表单验证 + 提交交互（POST/PUT 对应接口）
  - scope: frontend
  - files: `compass/templates/strategy/admin_edit.html`
