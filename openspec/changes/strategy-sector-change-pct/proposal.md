# Proposal: 策略组事件板块涨跌幅计算

## Summary
为 group_event 表新增 `sector_change_pct` 字段，在事件创建和每日趋势跟踪时自动计算触发股票的平均涨跌幅，填充到前端展示。

## Motivation
线框图设计中，事件卡片和事件详情页都展示板块累计涨跌幅（如 +3.2%），但当前 `group_event` 表没有此字段，API 返回 null，前端只能显示 `-`。

## 数据源分析
- `stock_data_daily` 表有 `change_percentage` 字段，数据完整（每日更新）
- `indicators_daily.change_pct` 全是 NULL（不可用）
- `group_event.matched_stocks` 包含触发股票代码列表
- `group_event.window_start` 是事件起始日期

## 计算逻辑
```
sector_change_pct = AVG(matched_stocks[].code → stock_data_daily WHERE date=window_start 的 change_percentage)
```

## Expected Behavior
1. **建表变更**：`ALTER TABLE group_event ADD COLUMN sector_change_pct FLOAT DEFAULT NULL`
2. **事件创建时**（aggregator.py）：`insert_group_event` 时计算并写入 `sector_change_pct`
3. **每日趋势跟踪时**（trend_tracker.py）：`track_all` 时用最新日期重新计算并更新 `sector_change_pct`
4. **历史数据回填**：对已有 62 个 tracking 事件一次性补算

## 文件变更
- `compass/strategy/db.py` — DDL + update_group_event 支持 sector_change_pct
- `compass/strategy/services/aggregator.py` — 创建事件时计算
- `compass/strategy/services/trend_tracker.py` — 每日跟踪时更新
- 数据库 ALTER TABLE

## Constraints
- 计算逻辑用 `stock_data_daily.change_percentage`，不用 `indicators_daily.change_pct`（全是 NULL）
- 取事件 `window_start` 当天的 change_percentage
- 如果当天数据不存在，sector_change_pct 保持 NULL
