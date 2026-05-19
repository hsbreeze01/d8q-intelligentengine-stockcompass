# Design: Refactor BOLL / VR / WR to inherit StockDBBase

## Architecture Decision

Follow the exact same refactoring pattern already proven in `db_rsi.py`, `db_bias.py`, `db_ma.py`, and `db_macd.py`:

1. **Replace raw `pymysql.connect` with `StockDBBase` inheritance** — eliminates per-call connection creation, uses the process-wide `PooledDB` connection pool.
2. **Use `with self:` context manager** for all DB operations — guarantees commit/rollback and connection release.
3. **Replace string-concatenated SQL with parameterised queries** via `_query_one`, `_query_all`, `_execute_many` — eliminates SQL injection risk.
4. **Remove `get_conn()`, `db_disconnect()`, `db_insertsql()`** — these helpers are superseded by `StockDBBase` methods.

## Data Flow (unchanged)

```
Caller (calc_indicator / test_api)
  → BOLLDaily(code) / VRDaily(code) / WRDaily(code)
    → db_get_maxdate()        # SELECT max(date) FROM stock_data_daily
    → getData()               # SELECT * FROM indicators_*_daily WHERE ... <= maxdate
    → insert(INDICATOR, DATETIME)  # REPLACE INTO indicators_*_daily ...
```

The data flow is identical; only the DB access mechanism changes.

## Files to Modify

| File | Change |
|---|---|
| `stockfetch/db_boll.py` | Full rewrite — inherit `StockDBBase`, remove raw pymysql |
| `stockfetch/db_vr.py` | Full rewrite — inherit `StockDBBase`, remove raw pymysql |
| `stockfetch/db_wr.py` | Full rewrite — inherit `StockDBBase`, remove raw pymysql |

No changes needed to callers (`stockdata/calc_indicator.py`, `tests/test_api.py`) since the public interface (`db_get_maxdate`, `getData`, `insert`) is preserved.

## Detailed Design Per Module

### stockfetch/db_boll.py — BOLLDaily

- Inherit `StockDBBase`
- Constructor: `def __init__(self, code, **db_kwargs)` → `super().__init__(**db_kwargs)`
- `db_get_maxdate()`: `with self:` + `_query_one("SELECT max(date) FROM stock_data_daily WHERE stock_code = %s", (self.code,))`
- `getData()`: `with self:` + `_query_all("SELECT * FROM indicators_boll_daily WHERE stock_code = %s AND record_time <= %s", (self.code, last_update))`
- `insert(BOLL, DATETIME)`: `with self:` + loop + `_execute_many("REPLACE INTO indicators_boll_daily (stock_code, upper_v, mid_v, lower_v, record_time) VALUES (%s, %s, %s, %s, %s)", (...))`
- Remove: `get_conn()`, `db_disconnect()`, `db_insertsql()`

### stockfetch/db_vr.py — VRDaily

- Same structural pattern as BOLLDaily
- Table: `indicators_vr_daily`
- Columns: `stock_code, vr_1, a_v, b_v, record_time`
- Preserve the hard-coded `av=100, bv=200` default values in `insert()`
- Remove: `get_conn()`, `db_disconnect()`, `db_insertsql()`

### stockfetch/db_wr.py — WRDaily

- Same structural pattern as BOLLDaily
- Table: `indicators_wr_daily`
- Columns: `stock_code, wr_1, wr_2, record_time`
- `WR` is a 2-element array: `WR[0]` → `wr_1`, `WR[1]` → `wr_2`
- Remove: `get_conn()`, `db_disconnect()`, `db_insertsql()`

## Reference Implementation

See `stockfetch/db_bias.py` (simplest, 80 lines) for the canonical pattern to follow.
