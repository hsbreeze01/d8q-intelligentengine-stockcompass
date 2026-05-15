# Delta Spec: 策略事件结构化分析 LLM 替换

## MODIFIED Requirements

### Requirement: 策略事件结构化分析 SHALL 使用 DeepSeek LLM

系统在对策略组群体事件执行三阶段 LLM 分析时，阶段 1（结构化分析）SHALL 使用 DeepSeek LLM 而非 Doubao LLM。

#### Scenario: 策略事件触发 LLM 结构化分析

- **Given** 一个策略组群体事件被创建或更新
- **When** LLMExtractor 执行三阶段分析的阶段 1（结构化分析）
- **Then** 系统 SHALL 调用 DeepSeek LLM 的 `standard_request` 方法生成结构化分析结果
- **And** 结构化分析 SHALL 返回与当前相同的 JSON schema（event_type, confidence, keywords, possible_drivers, related_themes）
- **And** 阶段 2（关键词搜索）和阶段 3（DeepSeek 深度摘要）行为不变

#### Scenario: DeepSeek 结构化分析超时或失败

- **Given** DeepSeek LLM 服务不可用或响应超时
- **When** LLMExtractor 执行阶段 1 结构化分析
- **Then** 系统 SHALL 捕获异常并记录警告日志
- **And** 结构化分析结果 SHALL 为 None
- **And** 后续阶段 2 和阶段 3 SHALL 继续执行（graceful degradation）

### Requirement: LLMExtractor 不再依赖 DoubaoLLM

LLMExtractor 类 SHALL 移除对 DoubaoLLM 的直接依赖。

#### Scenario: LLMExtractor 初始化无 DoubaoLLM 实例

- **Given** LLMExtractor 类定义
- **When** 检查其构造函数和属性
- **Then** LLMExtractor SHALL 不再持有 DoubaoLLM 实例或 doubao 属性
- **And** LLMExtractor SHALL 仅依赖 DeepSeekLLM 和 DataGateway
