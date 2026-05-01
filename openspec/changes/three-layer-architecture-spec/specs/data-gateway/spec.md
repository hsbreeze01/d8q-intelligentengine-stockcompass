## ADDED Requirements

### Requirement: 统一数据网关接口
StockCompass 通过 `compass/services/data_gateway.py` 统一访问 DataAgent 和 StockShark 数据，不直接操作底层存储。

#### Scenario: 查询非结构化资讯
- **WHEN** Compass 调用 `DataAgentFetcher.get_news_by_code(stock_code)`
- **THEN** 返回该股票相关的资讯列表，包含 title/content/sentiment/publish_time

#### Scenario: 查询结构化行情
- **WHEN** Compass 调用 `SharkFetcher.get_quote(stock_code)`
- **THEN** 返回该股票的最新行情数据，包含 open/close/high/low/volume

#### Scenario: 统一格式输出
- **WHEN** Compass 调用 `DataGateway.get_stock_profile(stock_code)`
- **THEN** 返回统一格式 dict 包含 quote + news + entity_name，屏蔽底层存储差异

#### Scenario: 服务不可用降级
- **WHEN** DataAgent 或 StockShark 服务不可达
- **THEN** 返回空数据并记录 warning 日志，不抛出异常
