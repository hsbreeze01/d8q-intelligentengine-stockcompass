# Spec: LLM 分析解耦

## MODIFIED Requirements

### Requirement: LLM 分析与聚合流程解耦

聚合器执行聚合检测时，LLM 分析 SHALL 以 fire-and-forget 模式异步执行，不阻塞聚合主流程。LLM 分析失败 SHALL 不影响聚合结果写入。

#### Scenario: 手动扫描跳过 LLM 同步等待

- **Given** 手动扫描触发，`skip_llm=True` 传入聚合器
- **When** `Aggregator.aggregate()` 执行聚合检测
- **Then** 聚合器 SHALL 不启动 LLM 分析线程
- **And** 聚合器 SHALL 正常创建/更新群体事件记录

#### Scenario: 定时扫描触发 LLM 异步分析

- **Given** 定时扫描（cron）触发，`skip_llm=False` 传入聚合器
- **When** `Aggregator.aggregate()` 创建新群体事件
- **Then** 聚合器 SHALL 启动 daemon 线程执行 LLM 分析（fire-and-forget）
- **And** 聚合器 SHALL 不等待 LLM 分析完成即返回
- **And** LLM 分析结果 SHALL 异步写入 `group_event` 记录

#### Scenario: LLM 分析失败容错

- **Given** LLM 分析线程启动
- **When** `LLMExtractor.analyze_event()` 抛出异常（如 API 超时、网络错误）
- **Then** 系统 SHALL 仅记录 warning 级别日志
- **And** 群体事件记录 SHALL 保持原有聚合结果不变（不标记失败）
- **And** 不影响后续事件的 LLM 分析

### Requirement: 定时扫描也使用 skip_llm 参数

定时扫描（APScheduler 触发）SHALL 在 APScheduler 后台线程中执行扫描，扫描内部调用聚合器时 SHALL 传入 `skip_llm=False` 以触发异步 LLM 分析。

#### Scenario: 定时扫描正常执行

- **Given** APScheduler 按策略组的 `scan_cron` 触发定时扫描
- **When** `_run_scan(group_id)` 被调度器调用
- **Then** `Scanner.scan()` SHALL 在 APScheduler 后台线程中执行
- **And** 聚合器 SHALL 接收 `skip_llm=False`，为每个新事件触发异步 LLM 分析
- **And** 定时扫描 SHALL 不阻塞 Flask 请求处理线程
