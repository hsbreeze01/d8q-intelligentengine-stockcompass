# Delta Spec: 策略引擎表初始化韧性

## ADDED Requirements

### Requirement: init_tables 必须创建全部 6 张策略表且不中断

策略引擎启动时 `init_tables()` SHALL 遍历 `_TABLES` 字典中的所有表执行 `CREATE TABLE IF NOT EXISTS`。当某张表创建失败时，SHALL 记录错误日志但继续创建后续表，MUST NOT 因单张表失败而中断整个初始化流程。

#### Scenario: signal_snapshot 创建失败不阻塞后续建表

- **Given** 数据库中 `strategy_group` 和 `strategy_group_run` 已存在
- **And** `signal_snapshot` 的 DDL 因临时错误失败
- **When** `init_tables()` 执行
- **Then** `signal_snapshot` 的失败 SHALL 被记录为 ERROR 日志
- **And** `group_event` 和 `trend_tracking` MUST 仍然被创建
- **And** `init_tables()` MUST 正常返回（不抛出异常）

#### Scenario: 所有表已存在时 init_tables 正常完成

- **Given** 6 张策略表已全部存在
- **When** `init_tables()` 执行
- **Then** 所有 `CREATE TABLE IF NOT EXISTS` 均跳过
- **And** 函数正常返回，无 ERROR 日志

### Requirement: 策略引擎初始化失败不阻塞应用启动

`init_strategy_engine()` 在 `init_tables()` 失败时 SHALL 记录错误但继续尝试启动调度器。应用启动 MUST NOT 因策略引擎建表失败而中断。

#### Scenario: init_tables 全部失败后调度器仍启动

- **Given** 数据库连接正常但 DDL 全部失败（如权限不足）
- **When** `init_strategy_engine()` 执行
- **Then** `init_tables()` 的错误 SHALL 被记录
- **And** 调度器 `start_scheduler()` MUST 仍然被调用
