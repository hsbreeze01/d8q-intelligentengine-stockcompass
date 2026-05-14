# Design: 策略组 Phase 2 — LLM 编排 + 趋势跟踪 + 生命周期管理

## 架构决策

### 1. LLM 编排采用顺序流水线模式

**决策**：LLM 分析链路（Doubao → 关键词搜索 → DeepSeek）在单个服务类中按顺序执行，不用消息队列或异步任务。

**理由**：
- 项目现有模式是同步调用（见 `DualLLMAnalysisService`）
- 群体事件创建频率低（每日数十条），不需要异步队列
- 三阶段有严格依赖关系（搜索依赖 Doubao 关键词，DeepSeek 依赖前两阶段结果）
- 减少基础设施复杂度

### 2. LLM 失败采用 graceful degradation 策略

**决策**：每个 LLM 阶段独立 try/catch，失败不阻塞后续阶段。

**理由**：
- 与现有 `DataGateway._http_get` 的容错模式一致
- 部分结果仍有价值（Doubao 成功但 DeepSeek 失败 → 至少有关键词和确认度）

### 3. 趋势跟踪集成在现有调度器中

**决策**：在 `compass/strategy/services/trend_tracker.py` 实现跟踪逻辑，由 scheduler 每日调度。

**理由**：
- 与现有 aggregator/scanner 调度模式一致
- 独立服务类便于测试和维护

### 4. 资讯搜索增强在 DataGateway 层实现

**决策**：`DataAgentFetcher.search_news_by_keywords()` 封装在 DataGateway 中，而非 llm_extractor 直接调用。

**理由**：
- 趋势跟踪器也需要关键词搜索（资讯持续关联）
- 保持单一数据源访问模式

## 数据流

### 群体事件创建 → LLM 分析

```
aggregator.py
  │ 创建 group_event (lifecycle='tracking')
  └→ llm_extractor.analyze_event(event_id)
       │ 1. 读取 event 上下文（触发股票、指标、行业）
       │ 2. 调用 DoubaoLLM → structured JSON
       │ 3. 用 keywords 调用 DataGateway.search_news_by_keywords()
       │ 4. 调用 DeepSeekLLM → summary
       └→ 更新 group_event 的 llm_* / news_* 字段
```

### 每日趋势跟踪

```
scheduler (每日)
  └→ trend_tracker.track_all()
       │ 查询 lifecycle='tracking' 的 events
       │ 对每个 event:
       │   ├─ 查询当日触发股票 + 指标
       │   ├─ 与前一日对比 → new_stocks / lost_stocks
       │   ├─ 聚合指标均值 → trend_tracking 记录
       │   ├─ 资讯关联 → news_count
       │   └─ 衰减判定 → 可能更新 lifecycle='suggest_close'
```

### 事件关闭

```
POST /api/events/<id>/close
  │ 验证 lifecycle != 'closed'
  │ 更新 lifecycle='closed', closed_at=NOW(), closed_by=current_user_id
  └→ 返回更新后的事件
```

## 需要新增的文件

| 文件 | 职责 |
|------|------|
| `compass/strategy/services/llm_extractor.py` | LLM 三阶段分析编排：Doubao 结构化 → 关键词搜索 → DeepSeek 摘要 |
| `compass/strategy/services/trend_tracker.py` | 每日趋势跟踪：指标聚合、信号衰减判定、资讯关联 |

## 需要修改的文件

| 文件 | 变更内容 |
|------|----------|
| `compass/services/data_gateway.py` | `DataAgentFetcher` 新增 `search_news_by_keywords()` 方法 |
| `compass/strategy/services/aggregator.py` | 事件创建后调用 `llm_extractor.analyze_event()` |
| `compass/strategy/db.py` | 新增 trend_tracking CRUD、lifecycle 更新、group_event 字段更新函数 |
| `compass/strategy/routes/events.py` | 增强 close 端点（记录 closed_by + closed_at），新增 trend 查询端点 |
| `compass/strategy/scheduler.py`（如存在）或调度入口 | 每日调用 `trend_tracker.track_all()` |

## 数据库交互说明

### group_event 更新字段
- `llm_keywords` — JSON array，Doubao 提取的关键词
- `llm_summary` — TEXT，DeepSeek 生成的摘要
- `llm_confidence` — FLOAT，Doubao 置信度
- `llm_drivers` — JSON array，驱动因素
- `llm_related_themes` — JSON array，关联主题
- `news_confirmed` — BOOLEAN，消息面是否确认
- `news_confirm_score` — FLOAT，确认度评分 0-1
- `news_matched` — JSON array，匹配资讯列表
- `lifecycle` — ENUM('tracking', 'suggest_close', 'closed')
- `suggest_close_reason` — TEXT，衰减原因
- `closed_at` — DATETIME，关闭时间
- `closed_by` — INT，关闭者 user.id

### trend_tracking 写入字段
- `group_event_id` — INT，关联事件
- `track_date` — DATE，跟踪日期
- `stock_count` — INT，触发股票数
- `new_stocks` — JSON array，新增股票
- `lost_stocks` — JSON array，消失股票
- `avg_rsi` / `avg_macd_dif` / `avg_volume_ratio` / `avg_score` — FLOAT，指标均值
- `news_count` — INT，当日关联资讯数

## 错误处理策略

| 组件 | 错误场景 | 处理方式 |
|------|----------|----------|
| DoubaoLLM | 超时/服务不可用 | 记录 warning，structured=null |
| DeepSeekLLM | 超时/服务不可用 | 记录 warning，summary=null |
| DataAgent | 搜索失败 | 记录 warning，news_matched=[] |
| 趋势跟踪 | 指标数据缺失 | 跳过该事件，记录 warning |
| DB 写入 | 字段更新失败 | 记录 error，不影响其他事件 |

## 前端任务说明

前端 UI 展示（事件详情页的 LLM 摘要、趋势图表、资讯列表渲染、生命周期状态展示）属于 `scope: frontend` 任务，不在本 design 范围内由 zsiga 执行。后端 API 已提供完整数据接口供前端消费。
