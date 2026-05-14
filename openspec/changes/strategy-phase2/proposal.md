# 策略组 Phase 2+4 — LLM 编排 + 消息面确认 + 趋势跟踪 + 资讯关联 + 生命周期管理

## 背景

策略组前端 Phase 1 已完成（commit 142bdb2），包含页面路由、订阅系统、事件详情页。
现有基础设施：
- `compass/llm/doubao.py` — DoubaoLLM（结构化分析）
- `compass/llm/deepseek.py` — DeepSeekLLM（深度文章）
- `compass/services/llm_analysis.py` — DualLLMAnalysisService（个股双LLM分析）
- `compass/services/data_gateway.py` — DataAgent（资讯搜索）+ StockShark（行情）
- `compass/strategy/routes/events.py` — 事件 CRUD + micro/macro/info API 端点
- `compass/strategy/db.py` — 策略组数据层

群体事件聚合器（`compass/strategy/services/aggregator.py`）在检测到群体事件后创建 `group_event` 记录，但**目前不会自动触发 LLM 分析**。

## 核心需求

### 1. LLM 特征提取器（`compass/strategy/services/llm_extractor.py`）

当群体事件创建后，自动启动 LLM 分析链路：

**Step 1: Doubao 结构化分析**
- 输入：事件上下文（触发股票列表 + 指标快照 + 行业信息 + 价格走势）
- 输出 JSON：
```json
{
  "event_type": "industry_bottom_reversal",
  "confidence": 0.78,
  "keywords": ["半导体国产替代", "先进封装", "AI芯片需求"],
  "possible_drivers": ["大基金三期注资预期", "AI算力需求拉动"],
  "related_themes": ["人工智能", "国产芯片", "先进制程"]
}
```

**Step 2: 关键词搜索确认**
- 用 `keywords` 通过 `DataGateway` 搜索 DataAgent 资讯库
- 对每个关键词计算匹配数和最高相关度
- 输出：`news_matched`（新闻列表+相关度）、`news_confirm_score`（0-1 确认度）

**Step 3: DeepSeek 深度摘要**
- 输入：结构化分析 + 搜索结果
- 输出：`llm_summary`（可读的事件分析摘要）

将以上结果写入 `group_event` 表的 `llm_keywords`, `llm_summary`, `llm_confidence`, `llm_drivers`, `llm_related_themes`, `news_confirmed`, `news_confirm_score`, `news_matched` 字段。

### 2. 消息面确认器（集成在 llm_extractor 中）

- `DataAgentFetcher.get_news_by_subject()` 已有，但需要增强
- 新增 `search_by_keywords(keywords: list) -> list[dict]` — 遍历所有 track 的 news，按关键词匹配
- 计算确认度：`matched_keywords / total_keywords * avg_relevance`

### 3. 趋势跟踪器（`compass/strategy/services/trend_tracker.py`）

每日对 `lifecycle='tracking'` 的事件执行：
- 查询当日触发股票变化（新增/消失）
- 聚合触发股票的指标均值（RSI/MACD DIF/量比/综合评分）
- 写入 `trend_tracking` 记录
- 判定信号衰减：连续 2 日均值评分 < 0.5 → 更新 lifecycle='suggest_close'

### 4. 资讯持续关联器（集成在 trend_tracker 中）

每日对 tracking 事件执行：
- 用 `group_event.llm_keywords` + `llm_related_themes` 搜索 DataAgent 近 24h 新增资讯
- 追加到 `group_event.news_matched`
- 更新 `trend_tracking.news_count`

### 5. 生命周期管理

- 创建群体事件时：`lifecycle='tracking'`（自动）
- 趋势跟踪器判定衰减：`lifecycle='suggest_close'`（自动）+ 记录 `suggest_close_reason`
- 管理员确认关闭：`lifecycle='closed'`，记录 `closed_at` + `closed_by`
- closed 后资讯采集停止，已采集数据保留

### 6. 集成触发

- **aggregator.py** 创建新 group_event 后，自动调用 `llm_extractor.analyze_event(event_id)`
- **scheduler.py** 每日扫描后，自动调用 `trend_tracker.track_all()`
- 新增 API：`POST /api/events/<id>/close` — 管理员确认关闭（已存在但需增强：记录 closed_by）

### 7. 增强 DataGateway 资讯搜索

在 `compass/services/data_gateway.py` 的 `DataAgentFetcher` 中新增：
- `search_news_by_keywords(keywords, limit=20)` — 按关键词列表搜索资讯
- 遍历所有 tracks，对每条 news 的 title+content 做关键词匹配
- 返回 `[{title, source, date, relevance, matched_keyword}, ...]`

## 技术约束

- 复用现有 DoubaoLLM 和 DeepSeekLLM 客户端
- LLM prompt 模板硬编码在服务类中
- DataGateway 搜索通过 HTTP 调用 localhost:8000
- trend_tracking 表已存在（建表 SQL 在 PRD 中）
- 错误处理：LLM 调用失败不阻塞主流程，仅记录 warning
- 依赖行业数据（stock_basic.industry/concept）做聚合，当前数据采集中，可延后验证聚合功能

## 文件结构

```
compass/strategy/services/
├── aggregator.py          (已有，需修改：事件创建后触发 LLM)
├── scanner.py             (已有)
├── llm_extractor.py       (新增：LLM 编排 + 消息面确认)
└── trend_tracker.py       (新增：趋势跟踪 + 资讯关联 + 生命周期)

compass/services/
├── data_gateway.py        (已有，需增强：关键词搜索)
└── ...

compass/strategy/routes/
├── events.py              (已有，需增强：close 端点记录 closed_by)
└── ...

compass/strategy/db.py     (已有，需增强：trend_tracking CRUD + lifecycle 更新)
```

## 验收标准

1. 群体事件创建后自动触发 LLM 分析（Doubao→关键词搜索→DeepSeek）
2. LLM 结果写入 group_event 的 llm_* 和 news_* 字段
3. 关键词搜索返回匹配资讯列表和确认度评分
4. 趋势跟踪器每日对 tracking 事件写入 trend_tracking 记录
5. 信号衰减自动标记 suggest_close
6. 资讯持续关联每日追加到 news_matched
7. 管理员确认关闭记录 closed_by
8. LLM/网络错误不阻塞主流程
9. 单元测试覆盖核心逻辑（可 mock LLM 和 DataAgent）

## 待数据采集完成后验证的内容

- 群体事件聚合（依赖 stock_basic.industry 数据）
- 端到端联调（从信号扫描到 LLM 分析到前端展示）
- 趋势跟踪的真实数据验证
