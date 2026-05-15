# Proposal: 修复策略引擎缺失表导致扫描失败

## Summary
策略扫描执行后报大量错误：`Unknown column 'lifecycle' in 'field list'` 和 `Unknown column 'llm_keywords' in 'field list'`。根因：`signal_snapshot`、`group_event`、`trend_tracking` 三张表未创建。

## Motivation
策略扫描的核心链路不可用。扫描匹配到的股票无法写入 `signal_snapshot`，聚合后无法创建事件（`group_event`），导致整个策略引擎只是空跑。

## Root Cause Analysis
1. `compass/strategy/db.py` 的 `_TABLES` 字典定义了 5 张表的 DDL：`strategy_subscription`, `strategy_group`, `strategy_group_run`, `signal_snapshot`, `group_event`, `trend_tracking`
2. 但 `init_tables()` 在服务启动时只成功创建了 `strategy_group`, `strategy_group_run`, `strategy_subscription` 三张（其他 3 张的 CREATE TABLE 可能被跳过或失败）
3. 扫描器 `scanner.py` 执行 `_aggregate()` 时尝试写入 `group_event` 表，但该表不存在
4. 错误日志中 `Unknown column 'lifecycle'` 实际是整张表不存在时的错误信息

额外问题：扫描后对每个事件调用 Doubao LLM 做结构化分析，但 Doubao 连接失败（`Connection error`），导致每个事件处理耗时 6-7 秒 × 28+ 事件 = 约 3 分钟。

## Expected Behavior
- 扫描匹配的股票写入 `signal_snapshot`
- 聚合事件写入 `group_event`（含 `lifecycle`, `llm_keywords` 等列）
- 趋势跟踪写入 `trend_tracking`
- 手动触发扫描在 30 秒内完成（不含 LLM 分析）

## Scope
- **Compass**: 确保 `init_tables()` 正确创建所有 5 张表
- **Compass**: 如果 Doubao LLM 连接失败，应跳过 LLM 分析而非阻塞

## Target Projects
- d8q-intelligentengine-stockcompass

## 修复方案
1. 在服务器上手动执行缺失 3 张表的 CREATE TABLE
2. 验证 `init_tables()` 的建表逻辑确保新环境也能正确建表
3. 考虑 LLM 分析的超时/降级策略
