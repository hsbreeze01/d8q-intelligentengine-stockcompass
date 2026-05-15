## Why

compass-data-pipeline 作为独立服务部署在远程服务器上（d8q-datapipeline），负责 K线数据采集、技术指标计算、分析结果存储。但 StockShark 已具备 `crawl_stock_daily_trade`、`crawl_today_trade_data`、`crawl_incremental_basic_info` 等完整的数据采集能力。

当前问题：
1. **功能重叠**：pipeline_fetcher 和 StockShark 的 crawler 都做 K线采集，数据源不同（新浪 vs 东财），维护两套代码
2. **资源浪费**：服务器多跑一个 Python 进程 + systemd service，内存占用 ~130MB
3. **数据孤岛**：pipeline 写 `stock_data_daily` / `indicators_daily` / `stock_analysis`，StockShark 写 `stock_daily_trade` 等表，同类数据分散在不同表中

系统资源有限，遵循"无需必要，不增实体"原则，应该将 pipeline 能力融合到 StockShark。

## What Changes

将 compass-data-pipeline 的三个核心能力迁移到 StockShark：
1. **K线采集**（新浪数据源 `stock_zh_a_daily`）→ StockShark crawler 增加 Sina 降级
2. **技术指标计算**（TA-Lib）→ StockShark 增加 indicator 模块
3. **综合分析**（buy_advice_v2 逻辑）→ 复用 compass 现有分析能力，由 StockShark 调度

融合后：
- d8q-datapipeline 服务退役
- StockShark 增加 daemon 模式（APScheduler 定时增量采集 + 指标计算）
- compass 通过 StockShark API 获取数据

## 并行评估：daemon vs 融合

**结论：可以并行，但需要分阶段。**

| 阶段 | 内容 | 与 daemon 关系 |
|---|---|---|
| Phase A | 启动 daemon 模式（用现有 pipeline 代码跑日常增量） | daemon 正常运行 |
| Phase B | StockShark 增加新浪数据源 + indicator 模块 | daemon 继续运行 |
| Phase C | 切换：StockShark daemon 接管，pipeline daemon 停止 | 切换瞬间 |

**Phase A 先行**：init 完成后立即启动 pipeline daemon，保证每日增量数据不断档。
**Phase B/C 融合**：StockShark 代码改造完成后，一次性切换，pipeline 退役。

## Capabilities

### New Capabilities
- `sina-kline-source`: StockShark 支持 Sina 数据源（东财不可用时的降级）
- `talib-indicators`: StockShark 内置 TA-Lib 技术指标计算
- `stockshark-daemon`: StockShark daemon 模式（定时增量采集+指标计算）

### Modified Capabilities
- `stockshark-crawler`: 增加写入 `stock_data_daily` + `indicators_daily` 的能力
- `compass-data-access`: compass 通过 StockShark API 而非直连 DB

### Retired Capabilities
- `d8q-datapipeline`: 独立服务退役，systemd service 移除

## Impact

- **修改仓库**: d8q-intelligentengine-stockshark（增加模块）、d8q-intelligentengine-stockcompass（改为调用 StockShark API）
- **服务器变更**: d8q-datapipeline 退役，d8q-stockshark 增加 daemon 调度
- **数据库变更**: 无新表，继续使用 `stock_data_daily` / `indicators_daily` / `stock_analysis`
- **不改动**: compass 的分析逻辑（buy_advice_v2 等）、前端

## Service Specification

- **d8q-stockshark** 增加定时任务调度（APScheduler 或集成到现有 Flask 服务）
- **d8q-datapipeline** 退役
- **d8q-compass** 数据获取路径从直连 DB 改为 StockShark API（可选，低优先级）
