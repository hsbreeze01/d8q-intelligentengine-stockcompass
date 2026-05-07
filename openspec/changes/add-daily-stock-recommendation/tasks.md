# Tasks: 每日推荐股票 API

## 1. 数据库准备

- [x] 1.1 创建建表脚本 `scripts/create_daily_recommendation_table.py`，包含 `daily_recommendation` 表 DDL 和 `DROP IF EXISTS` 保护，用 `compass/data/database.py` 的 Database 类执行
  - 文件: `scripts/create_daily_recommendation_table.py`

## 2. 推荐评分引擎

- [x] 2.1 实现 `compass/services/recommendation.py` 中的 `RecommendationService` 类框架，包含 `generate_daily()` 和 `get_daily(date, limit, offset)` 方法签名，以及排除规则函数 `_filter_eligible()`
  - 文件: `compass/services/recommendation.py`

- [x] 2.2 实现技术指标评分 `_calc_technical_score()`：从 `stock_analysis` 读取 `buy_advice` JSON，统计 buy/sell 信号数量，归一化到 0-100
  - 文件: `compass/services/recommendation.py`

- [x] 2.3 实现趋势动量评分 `_calc_trend_score()`：从 `stock_data_daily` 读取近 20 日数据，计算 MA 排列状态和近期涨跌幅，归一化到 0-100
  - 文件: `compass/services/recommendation.py`

- [x] 2.4 实现基本面评分 `_calc_fundamental_score()`：从 `dic_stock` 读取 PE、PB、市值、换手率，按区间打分并归一化到 0-100
  - 文件: `compass/services/recommendation.py`

- [x] 2.5 实现量价配合评分 `_calc_volume_score()`：从 `stock_data_daily` 读取近 10 日量价数据，计算量价关系，归一化到 0-100
  - 文件: `compass/services/recommendation.py`

- [x] 2.6 实现推荐理由与风险提示生成 `_generate_reason()` 和 `_generate_risk_warning()`：基于各维度分数的规则模板拼接文本
  - 文件: `compass/services/recommendation.py`

- [x] 2.7 实现 `generate_daily()` 主流程：串联筛选→评分→排序→生成理由→批量写入 `daily_recommendation` 表，返回生成数量和耗时
  - 文件: `compass/services/recommendation.py`

## 3. API 路由

- [x] 3.1 创建 `compass/api/routes/recommendation.py`，定义 Blueprint 和三个端点：`GET /api/recommendation/daily`（含 date/limit/offset 参数）、`POST /api/recommendation/generate`（手动触发）、`GET /api/recommendation/performance`（历史效果回溯）
  - 文件: `compass/api/routes/recommendation.py`

- [x] 3.2 在 `compass/api/app.py` 的 `_register_blueprints()` 中注册 recommendation Blueprint
  - 文件: `compass/api/app.py`

## 4. 调度集成

- [ ] 4.1 在 `compass/scheduler/tasks.py` 中新增 `DailyRecommendationTask` 类，在 `_start_scheduler()` 中配置为 `DailyAnalysisTask` 之后执行
  - 文件: `compass/scheduler/tasks.py`

## 5. 测试

- [ ] 5.1 编写 `tests/test_recommendation_service.py`，覆盖排除规则、四个维度评分函数、理由生成的单元测试，使用 mock Database
  - 文件: `tests/test_recommendation_service.py`

- [ ] 5.2 编写 `tests/test_recommendation_api.py`，覆盖三个 API 端点的集成测试（使用 Flask test client）
  - 文件: `tests/test_recommendation_api.py`
