# Tasks: 策略组 Phase 2 — LLM 编排 + 趋势跟踪 + 生命周期管理

## 1. 数据层增强

- [ ] **1.1 增强 compass/strategy/db.py — trend_tracking CRUD + lifecycle 更新 + group_event LLM 字段更新**
  - 新增 `insert_trend_tracking(event_id, track_date, stock_count, new_stocks, lost_stocks, avg_rsi, avg_macd_dif, avg_volume_ratio, avg_score, news_count)` 
  - 新增 `get_latest_trend_tracking(event_id)` — 获取事件最近一条跟踪记录
  - 新增 `get_trend_tracking_history(event_id)` — 获取全部历史
  - 新增 `update_event_lifecycle(event_id, lifecycle, suggest_close_reason=None, closed_by=None)` — 统一生命周期更新
  - 新增 `update_event_llm_result(event_id, llm_keywords, llm_summary, llm_confidence, llm_drivers, llm_related_themes, news_confirmed, news_confirm_score, news_matched)` — LLM 结果批量写入
  - 新增 `append_event_news_matched(event_id, new_items)` — 追加资讯（JSON merge）

## 2. DataGateway 资讯搜索增强

- [ ] **2.1 DataAgentFetcher 新增 search_news_by_keywords 方法**
  - 在 `compass/services/data_gateway.py` 的 `DataAgentFetcher` 中新增 `search_news_by_keywords(keywords: list, limit=20) -> list[dict]`
  - 遍历所有 tracks 的 news，对 title+content 做关键词匹配
  - 返回 `[{title, source, date, relevance, matched_keyword}, ...]`
  - 空关键词返回空列表；DataAgent 不可用记录 warning 返回空列表

## 3. LLM 特征提取器

- [ ] **3.1 创建 compass/strategy/services/llm_extractor.py — LLM 三阶段分析编排**
  - `LLMExtractor` 类，依赖 `DataGateway`、`DoubaoLLM`、`DeepSeekLLM`（lazy init，复用现有客户端）
  - `analyze_event(event_id)` 主入口：
    - Step 1: 读取事件上下文（调用 db 层获取触发股票、指标、行业信息）
    - Step 2: Doubao 结构化分析 — 组装 prompt，解析 JSON 输出
    - Step 3: 关键词搜索 — 调用 `DataGateway.search_news_by_keywords(keywords)`
    - Step 4: DeepSeek 深度摘要 — 组装 prompt（结构化 + 搜索结果）
    - Step 5: 持久化 — 调用 `db.update_event_llm_result()`
  - 每阶段独立 try/atch，失败记录 warning 不阻塞
  - Prompt 模板硬编码在类中（与 `DualLLMAnalysisService` 模式一致）

## 4. 趋势跟踪器

- [ ] **4.1 创建 compass/strategy/services/trend_tracker.py — 趋势跟踪 + 信号衰减 + 资讯关联**
  - `TrendTracker` 类，依赖 `DataGateway`、`db` 层
  - `track_all()` 主入口：
    - 查询所有 `lifecycle='tracking'` 的事件
    - 对每个事件调用 `_track_event(event)`
  - `_track_event(event)`：
    - 查询当日触发股票列表 + 指标数据
    - 与前一日对比（`db.get_latest_trend_tracking`）计算 new_stocks / lost_stocks
    - 聚合指标均值（RSI / MACD DIF / 量比 / 综合评分）
    - 资讯关联：用 event.llm_keywords + llm_related_themes 搜索近 24h 资讯，追加 news_matched
    - 写入 `trend_tracking` 记录
    - 衰减判定：连续 2 日 avg_score < 0.5 → 更新 lifecycle='suggest_close'

## 5. 集成触发

- [ ] **5.1 修改 aggregator.py — 事件创建后触发 LLM 分析**
  - 在 `aggregator.py` 创建 `group_event` 成功后，调用 `LLMExtractor().analyze_event(event_id)`
  - 用 try/except 包裹，LLM 失败不影响事件创建主流程
  - 设置 `lifecycle='tracking'` 为默认值

- [ ] **5.2 修改调度入口 — 每日触发趋势跟踪**
  - 在 scheduler（或调度入口）的每日任务中添加 `TrendTracker().track_all()` 调用
  - 在扫描任务（scanner/aggregator）之后执行

## 6. API 端点增强

- [ ] **6.1 增强 compass/strategy/routes/events.py — close 端点 + trend 查询端点**
  - 修改 `POST /api/events/<id>/close`：验证 lifecycle 状态，记录 `closed_at=NOW()`、`closed_by=current_user_id`，已关闭返回 400
  - 新增 `GET /api/events/<id>/trend`：返回该事件全部 `trend_tracking` 记录，按日期升序

## 7. 测试

- [ ] **7.1 编写单元测试 — LLM 特征提取器 + 趋势跟踪器核心逻辑（mock LLM 和 DataAgent）**
  - `tests/test_llm_extractor.py`：mock DoubaoLLM / DeepSeekLLM / DataGateway，验证三阶段顺序执行、部分失败 graceful degradation、结果持久化调用
  - `tests/test_trend_tracker.py`：mock db 层和 DataGateway，验证跟踪记录写入、衰减判定逻辑、资讯关联追加
  - `tests/test_data_gateway_keywords.py`：验证 `search_news_by_keywords` 空关键词、服务不可用、正常匹配场景
  - 运行 `pytest + ruff check` 确保全部通过
