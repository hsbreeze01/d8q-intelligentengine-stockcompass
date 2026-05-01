## ADDED Requirements

### Requirement: LLM 三层归属规范
明确各层 LLM 使用边界，避免重复调用和职责混乱。

#### Scenario: DataAgent LLM 使用范围
- **WHEN** DataAgent 处理采集到的原始资讯
- **THEN** 仅允许使用 LLM 进行资讯清洗（摘要生成、情感分析、实体识别），不做投资分析

#### Scenario: StockShark LLM 移除
- **WHEN** StockCompass 实现了等价的 LLM 分析能力
- **THEN** StockShark 中的 LLM 调用代码应被移除，仅保留纯数据服务

#### Scenario: StockCompass 终端唯一 LLM
- **WHEN** 需要对股票进行综合分析（技术面+消息面+资金面）
- **THEN** 必须且仅由 StockCompass 的双 LLM（Doubao+DeepSeek）执行，其他层不做分析

#### Scenario: LLM Key 管理
- **WHEN** 各层需要调用 LLM API
- **THEN** DataAgent 使用独立 DeepSeek key 用于清洗，Compass 使用 Doubao+DeepSeek 双 key 用于分析
