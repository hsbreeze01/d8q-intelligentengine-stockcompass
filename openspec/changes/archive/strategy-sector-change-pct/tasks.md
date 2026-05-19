# Tasks: 策略组事件板块涨跌幅计算

## Tasks
- [ ] T1: ALTER TABLE group_event ADD COLUMN sector_change_pct FLOAT DEFAULT NULL COMMENT '板块平均涨跌幅'
- [ ] T2: 在 db.py 新增函数 `calc_sector_change_pct(matched_stocks, date)` — 从 stock_data_daily 查询并计算平均值
- [ ] T3: 修改 aggregator.py — insert_group_event 和 update_group_event 时调用 calc_sector_change_pct 并写入
- [ ] T4: 修改 trend_tracker.py — _track_event 时重新计算 sector_change_pct 并 update
- [ ] T5: 编写回填脚本 — 对所有 lifecycle='tracking' 的事件用 window_start 日期补算 sector_change_pct
