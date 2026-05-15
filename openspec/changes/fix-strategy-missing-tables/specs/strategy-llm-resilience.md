# Delta Spec: LLM 分析超时降级

## ADDED Requirements

### Requirement: 聚合器触发 LLM 分析必须带超时保护

聚合器 `Aggregator._trigger_llm_analysis()` 对每个群体事件调用 LLM 三阶段分析时，SHALL 设置总超时上限。当 LLM 服务不可用或超时时，SHALL 跳过该事件的分析并记录 WARNING 日志，MUST NOT 阻塞聚合主流程。

#### Scenario: Doubao 连接失败时 LLM 分析被跳过

- **Given** 一个群体事件刚被创建
- **And** Doubao LLM 服务不可用（Connection error）
- **When** 聚合器对该事件触发 LLM 分析
- **Then** 分析请求 SHALL 在 10 秒内超时或捕获异常
- **And** 该事件 SHALL 被跳过，记录 WARNING 日志
- **And** 聚合主流程 MUST 继续处理后续事件

#### Scenario: LLM 分析总耗时不超限

- **Given** 聚合器创建了 28 个群体事件
- **And** Doubao 服务正常但每次调用耗时 2 秒
- **When** 聚合器依次触发 LLM 分析
- **Then** 每个事件的 LLM 分析 SHALL 在 15 秒内完成或超时
- **And** 总 LLM 分析耗时应低于 28 × 15 = 420 秒

### Requirement: LLM 分析结果持久化不依赖成功

当 LLM 分析被跳过（超时或连接失败）时，群体事件 MUST 仍然保留 `status='open'` 和 `lifecycle='tracking'`，不含 `llm_summary` 和 `llm_keywords`。后续趋势跟踪 SHALL 能正常处理无 LLM 分析的事件。

#### Scenario: 无 LLM 分析的事件仍可被趋势跟踪处理

- **Given** 事件 E 的 `llm_summary` 和 `llm_keywords` 为 NULL
- **When** 趋势跟踪器执行 `track_all()`
- **Then** 事件 E SHALL 被正常跟踪
- **And** `_associate_news()` SHALL 跳过资讯搜索（无关键词）并返回 0
