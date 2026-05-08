## Context

D8Q 生态包含 5 个服务（DataAgent:8000, StockShark:5000, DataFactory:8088, InfoPublisher:8089, StockCompass:待部署），均运行在 47.99.57.152。当前 StockShark 同时承担数据获取和 LLM 分析，DataAgent 和 StockShark 存在重复爬虫逻辑，StockCompass 缺少统一数据接入层。

## Goals / Non-Goals

**Goals:**
- 建立三层职责边界：DataAgent（采集+清洗）→ StockShark（结构化存储）→ Compass（分析+终端）
- 实现 `compass/services/data_gateway.py` 统一网关
- 定义实体标识统一规范（stock_codes + entity_names）
- 明确 LLM 归属：DataAgent 仅清洗，Compass 独占终端分析

**Non-Goals:**
- 不迁移 StockShark 现有存储（MySQL/MongoDB 保持不变）
- 不改变 DataFactory/InfoPublisher 的现有架构
- 不实现微信小程序功能（属于后续 Phase）

## Decisions

1. **统一网关模式**：Compass 通过 `data_gateway.py` 的 `DataAgentFetcher` 和 `SharkFetcher` 访问数据，不直接操作底层 DB
2. **HTTP API 通信**：三层之间通过 HTTP REST API 通信（同机 localhost），不引入消息队列
3. **实体标识方案**：以 `stock_code`（6位数字）为主键关联，DataAgent 入库时通过正则+StockShark 映射表补全
4. **LLM 渐进迁移**：StockShark 的 LLM 分析不立即删除，先在 Compass 实现替代后再移除
5. **存储透明**：Compass 不关心底层是 SQLite/MySQL/MongoDB，网关统一返回 dict 格式

## Risks / Trade-offs

- **同机单点风险**：所有服务在同一台 ECS，宕机影响全部。缓解：健康检查自动恢复（已有）
- **HTTP 调用延迟**：同机 localhost 调用延迟可忽略（<1ms），可接受
- **实体识别准确率**：正则提取股票代码可能遗漏，后续可用 LLM 增强。当前 P0 先用正则
- **渐进迁移期间重复**：StockShark LLM 和 Compass LLM 短期并存，需人工确认后再移除
