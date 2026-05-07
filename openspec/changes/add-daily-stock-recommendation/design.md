# Design: 每日推荐股票 API

## 架构决策

### 1. 分层架构，复用现有模式

遵循项目已有的 `compass/api/routes/*` → `compass/services/*` → `compass/data/database.py` 三层架构：

- **Route 层**：新增 `compass/api/routes/recommendation.py`，Flask Blueprint 处理 HTTP 请求
- **Service 层**：新增 `compass/services/recommendation.py`，封装推荐计算逻辑
- **Data 层**：复用 `compass/data/database.py` 的连接池读写新表

**理由**：项目所有功能模块都遵循此模式（analysis、market_data、subscription 等），保持一致性。

### 2. 评分引擎设计：纯 Python 函数式

推荐评分引擎不依赖 LLM，用纯 Python 实现确定性计算。四个维度独立计算后加权求和。

**理由**：
- 已有 `stock_analysis.buy_advice` JSON 存储了技术指标买卖信号（buy/sell 计数）
- 已有 `stock_data_daily` 存储了完整的日线行情（MA、成交量等）
- 已有 `dic_stock` 存储了基本面数据（PE、PB、市值等）
- 确定性计算比 LLM 生成评分更可测试、更可复现

### 3. 推荐理由生成：规则模板 + 可选 LLM

先用规则模板拼接推荐理由和风险提示（无需 LLM 调用，性能好），后续可扩展为 LLM 生成。

**理由**：
- 推荐计算在调度任务中批量执行，涉及全市场 5000+ 股票
- 对每只股票调用 LLM 成本高、耗时长
- 规则模板可满足需求且覆盖 REQ-REC-003

### 4. 数据库表设计

新增 `daily_recommendation` 表，存储每日推荐结果：

```sql
CREATE TABLE daily_recommendation (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code      CHAR(10)       NOT NULL,
    stock_name      VARCHAR(32)    NOT NULL,
    recommendation_date DATE       NOT NULL,
    total_score     DECIMAL(5,2)   NOT NULL COMMENT '综合评分 0-100',
    technical_score DECIMAL(5,2)   NOT NULL COMMENT '技术指标评分',
    trend_score     DECIMAL(5,2)   NOT NULL COMMENT '趋势动量评分',
    fundamental_score DECIMAL(5,2) NOT NULL COMMENT '基本面评分',
    volume_score    DECIMAL(5,2)   NOT NULL COMMENT '量价配合评分',
    rank            INT            NOT NULL COMMENT '当日排名',
    reason          TEXT           NOT NULL COMMENT '推荐理由',
    risk_warning    TEXT           NOT NULL COMMENT '风险提示',
    generated_at    DATETIME       NOT NULL,
    UNIQUE KEY uk_stock_date (stock_code, recommendation_date),
    KEY idx_date_score (recommendation_date, total_score DESC)
);
```

### 5. 调度集成

在 `compass/scheduler/tasks.py` 中新增 `DailyRecommendationTask`，在 `DailyAnalysisTask.run()` 完成后调用。

**理由**：现有的调度模式是 `DailyAnalysisTask` 更新全市场数据，推荐计算依赖数据更新完成后的状态。

## 数据流

```
[调度器] DailyAnalysisTask 完成
    ↓
[调度器] DailyRecommendationTask.run()
    ↓
[Service] RecommendationService.generate_daily()
    ├── 1. 从 dic_stock 读取全市场股票列表，应用排除规则（ST、低流动性、涨跌停）
    ├── 2. 对候选股票逐只评分：
    │   ├── 从 stock_analysis 读取 buy_advice JSON → technical_score
    │   ├── 从 stock_data_daily 读取近 20 日数据 → trend_score
    │   ├── 从 dic_stock 读取 PE/PB/市值 → fundamental_score
    │   └── 从 stock_data_daily 读取近 10 日量价 → volume_score
    ├── 3. 加权求和 → total_score
    ├── 4. 按分数排序取 Top N
    ├── 5. 生成推荐理由和风险提示（规则模板）
    └── 6. 批量写入 daily_recommendation 表

[API] GET /api/recommendation/daily
    ↓
[Service] RecommendationService.get_daily(date, limit, offset)
    ↓
[Database] SELECT from daily_recommendation WHERE recommendation_date = ?
```

## 需要新增/修改的文件

### 新增文件

| 文件 | 说明 |
|------|------|
| `compass/api/routes/recommendation.py` | 推荐路由 Blueprint |
| `compass/services/recommendation.py` | 推荐评分引擎 + 查询服务 |
| `scripts/create_daily_recommendation_table.py` | 建表脚本 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `compass/api/app.py` | 注册 recommendation Blueprint |
| `compass/scheduler/tasks.py` | 新增 DailyRecommendationTask，在 DailyAnalysisTask 后触发 |
| `prompts/prompts.yml` | （可选）预留 LLM 推荐理由生成的 prompt 模板 |
