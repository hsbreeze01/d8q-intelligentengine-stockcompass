# Design: Refactor db_ma / db_macd / db_rsi to StockDBBase

## Architecture Decision

The three indicator modules (`db_ma.py`, `db_macd.py`, `db_rsi.py`) currently use raw
`pymysql.connect()` per operation, SQL string concatenation, and manual `conn.close()`.
They will be refactored to inherit from `stockfetch.db_base.StockDBBase`, following the
exact pattern established by the already-refactored `db_bias.py`.

### Why StockDBBase inheritance?

- **Connection pooling** — `StockDBBase` uses `dbutils.PooledDB` with a process-wide
  singleton pool. Each `with self:` block acquires and releases a pooled connection,
  eliminating the overhead of creating a new TCP connection per query.
- **Parameterized queries** — `_query_one`, `_query_all`, `_execute_many` accept
  `(sql, params)` tuples, preventing SQL injection via string concatenation.
- **Consistent lifecycle** — `with self:` guarantees commit-on-success /
  rollback-on-error, removing manual `conn.commit()` / `conn.close()` boilerplate.

## Refactoring Pattern (identical for all three files)

### Before (current pattern)
```
class MADaily(object):
    def __init__(self, code, host=..., port=..., ...):
        self.host = host; ...
    def get_conn(self):
        return pymysql.connect(...)
    def db_disconnect(self):
        self.conn.close()
    def db_get_maxdate(self):
        conn = self.get_conn(); cur = conn.cursor()
        cur.execute("... where code='" + self.code + "'")
        conn.commit(); conn.close()
    def getData(self):
        ... SQL string concatenation ...
    def insert(self, ...):
        ... db_insertsql() builds SQL via string concat ...
```

### After (target pattern, matching db_bias.py)
```
class MADaily(StockDBBase):
    def __init__(self, code, **db_kwargs):
        super().__init__(**db_kwargs)
        self.code = code

    def db_get_maxdate(self):
        with self:
            _, row = self._query_one(
                "SELECT max(date) FROM stock_data_daily WHERE stock_code = %s",
                (self.code,))
        return row["max(date)"] if row else None

    def getData(self):
        ... = self.db_get_maxdate()
        with self:
            _, rows = self._query_all(
                "SELECT * FROM indicators_ma_daily WHERE stock_code = %s AND record_time <= %s",
                (self.code, last_update))
        return pd.DataFrame(rows)

    def insert(self, ...):
        with self:
            for index in reversed(range(len(DATETIME))):
                ... skip NaN ...
                self._execute_many(
                    "REPLACE INTO indicators_ma_daily (...) VALUES (%s, ...)",
                    (self.code, ...))
```

## Per-file Differences

| File | Table (getData/insert) | insert signature | Extra state |
|------|----------------------|-----------------|-------------|
| `db_ma.py` | `indicators_ma_daily` | `insert(ma5, ma10, ma20, ma30, ma60, DATETIME)` | — |
| `db_macd.py` | `indicators_macd_daily` | `insert(MACD, DATETIME)` — MACD is tuple of 3 series | — |
| `db_rsi.py` | `indicators_rsi_daily` or `indicators_rsi_daily_3612` | `insert(RSI, DATETIME)` — RSI is tuple of 3 series | `self.param` selects table |

## Data Flow

```
Caller (calc_indicator.py / main_stock.py / main_analysis.py)
  │
  ├─ MADaily(code)
  ├─ MACDDaily(code)
  └─ RSIDaily(code[, param])
       │
       ▼  inherits
  StockDBBase  ──►  PooledDB (process-wide singleton)
                       │
                       ▼
                   pymysql connection (acquired per `with self:` block)
                       │
                       ▼
                   MySQL  (stock_data_daily, indicators_*_daily tables)
```

## Files Modified

| File | Change |
|------|--------|
| `stockfetch/db_ma.py` | Full rewrite: `MADaily(object)` → `MADaily(StockDBBase)`, remove `get_conn`/`db_disconnect`/`db_insertsql`, parameterize all SQL |
| `stockfetch/db_macd.py` | Full rewrite: same pattern |
| `stockfetch/db_rsi.py` | Full rewrite: same pattern, preserve `self.param` table-selection logic |

## Files NOT Modified

- `stockfetch/db_base.py` — stable, already serves `db_bias.py`
- `stockdata/calc_indicator.py` — callers use `MADaily(code)`, `MACDDaily(code)`, `RSIDaily(code)` which remain the same constructor signature (positional `code` still works, `**db_kwargs` defaults to Config-based params)
- `stockdata/main_stock.py` — wildcard import only, no API change
- `stockdata/main_analysis.py` — wildcard import only, no API change
- `stockfetch/main.py` — wildcard import only, no API change
- `tests/test_api.py` — uses same constructor signatures, compatible

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `RSIDaily` has `param` positional arg between `code` and old db args | New signature `RSIDaily(code, param="61224", **db_kwargs)` preserves call sites `RSIDaily(code)` and `RSIDaily(code, "3612")` |
| `getData()` previously read column names from `cur.description` | `_query_all` uses `DictCursor`, so `pd.DataFrame(rows)` auto-gets column names from dict keys |
| Insert loop now calls `_execute_many` per row (not batched) | Same as `db_bias.py` pattern; within a single `with self:` block the connection is held, overhead is minimal |
