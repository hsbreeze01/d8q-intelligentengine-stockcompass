## Context

当前远程服务器上的数据服务分布：

| 服务 | 端口 | 职责 | 状态 |
|---|---|---|---|
| d8q-stockshark | :5000 | 股票分析、搜索、供应链分析 | 运行中 |
| d8q-datapipeline | APScheduler | K线采集、指标计算、分析 | daemon 运行中(16:30)，analysis 后台跑 |
| d8q-compass | :8087 | 前端展示、buy_advice 分析 | 运行中 |

**Pipeline 数据完成状态（05-13 12:30）：**
- `stock_data_daily`：5200 股票，289 万行 ✅ 完成
- `indicators_daily`：5200 股票，288 万行 ✅ 完成
- `stock_analysis`：3 股票完成，全量还在后台跑（预估 30+h）🔄

StockShark 已有的数据能力（`stockshark/data/crawler.py`）：
- `StockDataCrawler.crawl_stock_daily_trade()` — 单股 K线采集（东财源）
- `StockDataCrawler.crawl_today_trade_data()` — 全量今日数据
- `StockDataCrawler.crawl_incremental_basic_info()` — 增量股票信息
- `AkShareData` — akshare 数据封装层（带缓存 fetcher）

Pipeline 已有的能力（需迁移，`compass/scripts/`）：
- `pipeline_fetcher.fetch_kline_daily()` — 新浪数据源（akshare stock_zh_a_daily）
- `pipeline_db.calc_and_save_indicators()` — TA-Lib 指标（SMA/EMA/MACD/RSI/KDJ/BOLL/ATR）
- `pipeline_db.analyze_and_save()` — 综合分析（buy_advice_v2）
- `pipeline.py` daemon 模式（APScheduler，每日 16:30 增量）

关键依赖/陷阱：
- `dicStock` 全局变量：`from buy.cache import *` 会触发 `DicStockFactory()` 查 `dic_stock` 表（为空），导致 import 崩溃
- StockShark 的 crawler 不依赖 `dicStock`，可以安全复用
- 新浪接口 `stock_zh_a_daily` 可用，东财 `stock_zh_a_hist` 封禁

## Goals / Non-Goals

**Goals:**
- Phase 1：StockShark 增加新浪数据源 + TA-Lib 指标计算模块（与 pipeline daemon 并行）
- Phase 2：StockShark 增加 daemon 调度模式（集成到 Flask）
- Phase 3：全量 analysis 完成后，pipeline 下线，StockShark 接管

**Non-Goals:**
- 不改 compass 的数据获取路径（继续直连 DB）
- 不合并数据库表
- 不重构 StockShark 整体架构

## Decisions

### D1: 数据源 — 新浪优先

**选择**: StockShark 使用 `stock_zh_a_daily`（新浪），东财作为降级
**理由**: 东财接口持续不稳定（已确认封禁），新浪接口可用且稳定

### D2: 指标计算 — 独立模块

**选择**: 新建 `stockshark/indicators/` 模块，自包含 TA-Lib 计算
**理由**: 不 import compass 的 `stock_task.py`（会触发 dicStock 崩溃）
**参考**: `compass/scripts/pipeline_db.py` 中的 `calc_and_save_indicators()` 实现

### D3: Daemon — 集成到 StockShark Flask

**选择**: 在 StockShark Flask app 中增加 APScheduler 后台调度
**理由**: 不新增进程，复用现有 service

### D4: pipeline 下线时机

**选择**: analysis 全量完成 + StockShark daemon 验证通过后，再下线 pipeline
**理由**: 数据完整性优先，宁可多跑一段时间也不丢数据

### D5: 不做 analysis 融合

**选择**: analysis（buy_advice_v2）留在 compass，不迁移到 StockShark
**理由**: analysis 依赖 compass 的 funcat/buy 模块，import 链复杂且有 dicStock 陷阱。StockShark 只负责数据采集+指标计算，analysis 由 compass 调用

## Risks / Trade-offs

- **[风险] StockShark import 链** → crawler 模块安全，但集成新模块时需验证 import 路径
- **[风险] 切换期间数据重复** → Phase 3 切换时确保 pipeline 完全停止后再启动 StockShark daemon
- **[取舍] analysis 不融合** → compass 仍需依赖 pipeline 数据表，但 StockShark daemon 写同一张表，无影响
