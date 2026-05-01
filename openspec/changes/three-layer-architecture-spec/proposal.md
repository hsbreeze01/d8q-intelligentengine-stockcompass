## Why

D8Q 智能引擎生态当前存在三个项目职责边界模糊、LLM 调用重复、数据获取逻辑分散的问题。需要建立明确的三层架构规范，确保 DataAgent（数据层）、StockShark（业务层）、StockCompass（分析层）各司其职，消除重复代码并为后续扩展奠定基础。

## What Changes

- 建立 DataAgent 作为统一非结构化资讯采集底座，LLM 仅限资讯清洗（摘要/情感/实体识别）
- 明确 StockShark 为金融结构化数据中枢，后续移除其 LLM 分析职责
- 确立 StockCompass 为终端唯一 LLM 层（Doubao+DeepSeek），实现统一数据网关消费双源数据
- 统一实体标识：所有入库资讯带 `stock_codes` + `entity_names`
- 新增 `compass/services/data_gateway.py` 统一网关，屏蔽底层存储差异

## Capabilities

### New Capabilities
- `data-gateway`: StockCompass 统一数据网关，定义 DataAgentFetcher 和 SharkFetcher 接入规范
- `entity-unification`: 跨项目实体标识统一方案（stock_codes + entity_names）
- `llm-ownership`: 三层 LLM 归属规范，明确各层 LLM 使用边界

### Modified Capabilities

## Impact

- `compass/services/` 目录：新增 data_gateway.py 及 fetcher 实现
- DataAgent 入库逻辑：需增加 stock_codes/entity_names 字段
- StockShark：后续需移除 LLM 分析代码，保留纯数据服务
- API 契约：定义 DataAgent/StockShark 对外统一查询接口格式
