# Proposal: Sync dic_stock from akshare THS/Sina sources

## Summary
Create a data sync script that populates the `dic_stock` table with A-share stock basic info and real-time quotes, using working THS/Sina akshare APIs. This unblocks the compass recommendation engine.

## Motivation
The `dic_stock` table in MySQL `stock_analysis_system` has 0 rows. The recommendation engine (`compass/services/recommendation.py`) queries `dic_stock` to get stock candidates for scoring. Without data, `POST /api/recommendation/generate` returns empty results and the factory recommend page shows "暂无推荐数据".

The old sync mechanism (`stockfetch/stock_data_daily.py`) is entirely commented out and used tushare (also problematic).

## Expected Behavior

### 1. New script: `compass/sync/dic_stock_sync.py`
- Fetch all A-share stock list via `akshare.stock_info_a_code_name()` (works, not EM push2)
- Fetch real-time quotes via `akshare.stock_zh_a_spot()` (Sina source, ~15s, cached)
- For each stock, map to `dic_stock` columns and UPSERT into MySQL
- Column mapping:
  - `code` ← code
  - `stock_name` ← name
  - `latest_price` ← 最新价
  - `change_percentage` ← 涨跌幅
  - `change_amount` ← 涨跌额
  - `volume` ← 成交量
  - `turnover` ← 成交额
  - `amplitude` ← 振幅
  - `highest` ← 最高
  - `lowest` ← 最低
  - `open_today` ← 今开
  - `close_yesterday` ← 昨收
  - `turnover_rate` ← 换手率
  - `pe_ratio_dynamic` ← 市盈率-动态 (if available from Sina)
  - `pb_ratio` ← 市净率 (if available from Sina)
  - `total_market_value` ← 总市值 (if available)
  - `circulating_market_value` ← 流通市值 (if available)
  - `status` ← 0 (active)
  - `industry` ← empty for now (separate enrichment)

### 2. Rate limiting and caching
- Use `stockshark.data.fetcher.DataFetcher` pattern or simple in-memory cache with 30min TTL
- Rate limit: max 1 call per second to any API source
- UPSERT in batches of 500 rows to avoid MySQL timeout

### 3. CLI command
- Script is runnable standalone: `python -m compass.sync.dic_stock_sync`
- Also callable as module function for potential cron scheduling
- Progress logging: "Syncing batch 1/N (500 stocks)..."
- Summary on completion: "Synced 5200 stocks in 18.5s"

### 4. API endpoint (optional)
- `POST /api/sync/dic-stock` — trigger sync (admin only)
- Returns sync summary JSON

## Out of Scope
- Historical data sync (stock_data_daily table) — separate effort
- Industry/concept enrichment — separate effort
- Technical indicator data (buy/sell signals for stock_analysis) — separate effort
- Full automation (cron job) — manual for now

## Files to Modify
1. `compass/sync/__init__.py` — NEW: package init
2. `compass/sync/dic_stock_sync.py` — NEW: sync script
3. `compass/api/routes/sync.py` — NEW: sync API endpoint (optional)

## Constraints
- MySQL: `stock_analysis_system` on localhost:3306, user=root, password=password
- `dic_stock` table schema: see `DESCRIBE dic_stock` output (28 columns)
- `stock_info_a_code_name()` returns ~5200 stocks (code + name only)
- `stock_zh_a_spot()` (Sina) returns ~5200 stocks with full quote data (~15s)
- akshare v1.18.59 on server
