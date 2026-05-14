# Proposal: 策略组前端 Phase 2 — LLM 分析展示 + 趋势跟踪 + 生命周期管理

## 背景
后端 Phase 2 已完成 (commit ea6cfde)，新增：
- LLM 三阶段分析（Doubao→关键词搜索→DeepSeek 摘要）
- 趋势跟踪 + 信号衰减判定
- 事件关闭（记录 closed_by）
- 资讯关联增强

前端 Phase 1 已完成 (commit 142bdb2)，当前模板结构：
- `base.html` — 侧边栏导航（策略管理/策略发现/我的策略）
- `discover.html` — 策略发现页（骨架）
- `my_strategies.html` — 我的策略页（事件卡片列表）
- `event_detail.html` — 事件详情页（三维度 Tab：微观/宏观/信息）
- `admin_list.html` / `admin_edit.html` — 管理员页面

当前前端是**骨架状态**，需要：
1. 完善样式（匹配 Compass 主应用风格：#001529 侧边栏 + #F0F2F5 背景 + #1890FF 强调色）
2. 对接 Phase 2 后端新增的 API
3. 展示 LLM 分析结果、趋势跟踪、生命周期状态

## 需求清单

### 1. base.html 样式完善
- Compass 风格侧边栏：#001529 背景，#FFFFFF 文字，#1890FF 高亮
- 主内容区 #F0F2F5 背景
- 顶部用户信息栏
- ECharts CDN 引入

### 2. 策略发现页 (discover.html) 完善
- 策略卡片网格布局：名称、指标、状态标签（active/paused）
- 订阅/取消订阅按钮（POST `/api/strategy/subscribe`, DELETE `/api/strategy/subscribe`）
- 活跃事件统计展示

### 3. 我的策略页 (my_strategies.html) 增强
- 每个订阅策略组卡片展示：活跃事件数、最新事件时间
- 事件卡片增强：展示 lifecycle 状态标签（tracking/suggest_close/closed）
- suggest_close 状态黄色警告标签
- 事件卡片点击进入事件详情

### 4. 事件详情页 (event_detail.html) 重大增强
这是核心页面，需要完整实现三维度 Tab：

#### 顶部事件摘要
- 策略组名称 + 事件维度值
- 触发股票数、确认度（buy_star）、持续天数
- **lifecycle 状态标签**（tracking=绿色、suggest_close=黄色、closed=灰色）
- **LLM 置信度**（confidence 0-1 进度条）
- **消息面确认**（news_confirmed 图标：✓/✗）
- **关闭按钮**（仅 admin + lifecycle=suggest_close/closed 时显示）

#### 微观数据 Tab
- 调用 GET `/api/events/{id}/micro`
- 触发个股表格：股票代码、名称、buy_star、指标快照
- ECharts 散点图：buy_star vs RSI

#### 宏观数据 Tab
- 调用 GET `/api/events/{id}/macro`
- 板块维度聚合展示
- ECharts 饼图：板块分布

#### 信息关联 Tab（Phase 2 核心）
- 调用 GET `/api/events/{id}/info`
- **LLM 分析摘要**：`llm_summary`（markdown 渲染）
- **关键词标签云**：`llm_keywords`
- **驱动因素**：`llm_drivers` 列表
- **关联主题**：`llm_related_themes` 标签
- **消息面确认度**：`news_confirm_score` 进度条 + 匹配资讯数
- **关联资讯列表**：`news` 列表（标题 + 来源 + 时间）
- **趋势跟踪图表**：调用 GET `/api/events/{id}/trend`，ECharts 折线图展示 avg_score 随时间变化

### 5. 管理员页面样式完善
- `admin_list.html`：策略组表格 + 订阅人数 + 状态操作
- `admin_edit.html`：策略组创建/编辑表单

## 技术约束
- Jinja2 模板 + 原生 JS + ECharts（不用 React/Vue）
- 样式内联或 `<style>` 块（暂不引入独立 CSS 文件）
- 所有 API 调用用 `fetch()` + async/await
- 复用 Compass 主应用配色：#001529, #F0F2F5, #1890FF, #52C41A, #FAAD14
- 侧边栏基于角色显示不同 tab（admin 多一个"策略管理" tab）

## 文件清单
| 文件 | 操作 | 说明 |
|------|------|------|
| `compass/templates/strategy/base.html` | MODIFIED | 完整样式+侧边栏+用户栏 |
| `compass/templates/strategy/discover.html` | MODIFIED | 策略卡片网格+订阅功能 |
| `compass/templates/strategy/my_strategies.html` | MODIFIED | 事件卡片增强+lifecycle标签 |
| `compass/templates/strategy/event_detail.html` | MODIFIED | 三维度Tab+LLM分析+趋势图表+关闭按钮 |
| `compass/templates/strategy/admin_list.html` | MODIFIED | 表格样式+操作按钮 |
| `compass/templates/strategy/admin_edit.html` | MODIFIED | 表单样式 |
| `compass/strategy/routes/strategy_pages.py` | MODIFIED | 传递 lifecycle/llm 数据到模板 |

## 验收标准
1. 所有 6 个模板渲染无报错
2. 事件详情页三维度 Tab 正确切换，数据正确展示
3. LLM 摘要、关键词、驱动因素、资讯列表可见
4. 趋势跟踪折线图（ECharts）正确渲染
5. lifecycle 状态标签正确显示（tracking/suggest_close/closed）
6. 关闭按钮仅 admin 可见，调用 POST `/api/events/{id}/close`
7. 策略发现页订阅/取消功能可用
8. 配色与 Compass 主应用一致
