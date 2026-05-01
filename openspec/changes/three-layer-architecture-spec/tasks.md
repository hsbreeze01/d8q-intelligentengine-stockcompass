## 1. 统一数据网关实现

- [x] 1.1 创建 `compass/services/data_gateway.py`，定义 DataGateway 类和统一返回格式
- [x] 1.2 实现 `DataAgentFetcher`：通过 HTTP 调用 DataAgent API (localhost:8000) 获取资讯
- [x] 1.3 实现 `SharkFetcher`：通过 HTTP 调用 StockShark API (localhost:5000) 获取行情
- [x] 1.4 实现 `get_stock_profile(code)` 聚合方法，合并双源数据为统一格式
- [x] 1.5 添加服务不可用降级处理（超时/异常时返回空数据+warning日志）

## 2. 实体标识统一

- [x] 2.1 DataAgent 入库逻辑增加 stock_codes 字段提取（正则匹配6位数字）
- [x] 2.2 DataAgent 调用 StockShark `/api/stock/map` 接口补全 entity_names
- [x] 2.3 StockShark 新增 `/api/stock/map` 接口（批量 code→name 映射）
- [x] 2.4 DataAgent 数据库 schema 增加 stock_codes 和 entity_names 列

## 3. LLM 归属规范落地

- [ ] 3.1 审计 StockShark 中的 LLM 调用点，标记待迁移代码
- [ ] 3.2 在 StockCompass 中实现等价的 LLM 分析接口（双LLM：Doubao+DeepSeek）
- [ ] 3.3 配置管理：各层 LLM key 独立配置，Compass 使用 .env 管理双 key
- [ ] 3.4 移除 StockShark 中的 LLM 分析代码（确认 Compass 替代后执行）
