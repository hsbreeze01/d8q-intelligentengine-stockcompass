## Phase 1 — StockShark 增加数据能力（与 pipeline daemon 并行）

- [ ] 1.1 StockShark crawler 增加新浪 K线数据源：在 `fetch_stock_daily_trade` 中增加 `stock_zh_a_daily` 支持，参考 `compass/scripts/pipeline_fetcher.py` 的列名映射逻辑
- [ ] 1.2 新建 `stockshark/indicators/` 模块：自包含 TA-Lib 计算（SMA/EMA/MACD/RSI/KDJ/BOLL/ATR），写入 `indicators_daily` 表，参考 `compass/scripts/pipeline_db.py` 的 `calc_and_save_indicators()`
- [ ] 1.3 验证：单股端到端测试，确认 StockShark 能独立完成 K线采集 + 指标计算，数据写入 `stock_data_daily` + `indicators_daily`

## Phase 2 — StockShark daemon 模式

- [ ] 2.1 StockShark Flask app 集成 APScheduler：每日定时增量采集 + 指标计算（参考 pipeline.py 的 daemon 模式，每日 16:30 触发）
- [ ] 2.2 验证：daemon 单日增量正常运行，数据与 pipeline daemon 产出一致

## Phase 3 — 切换（analysis 全量完成后）

- [ ] 3.1 确认 pipeline analysis 全量完成：`SELECT COUNT(DISTINCT stock_code) FROM stock_analysis` 接近 5200
- [ ] 3.2 停止 pipeline daemon：`systemctl stop d8q-datapipeline`
- [ ] 3.3 启动 StockShark daemon：验证接管后每日数据正常
- [ ] 3.4 移除 d8q-datapipeline：`systemctl disable d8q-datapipeline && rm /etc/systemd/system/d8q-datapipeline.service`
- [ ] 3.5 数据一致性验证：对比切换前后每日数据行数
