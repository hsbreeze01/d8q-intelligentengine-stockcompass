# Design: Refactor ASIDaily & KDJDaily to StockDBBase

## Architecture Decision

**Decision**: Refactor the two remaining legacy indicator DB classes (`ASIDaily`, `KDJDaily`) to inherit from `StockDBBase`, completing the migration that was already applied to `BIASDaily`, `RSIDaily`, `MACDDaily`, `BOLLDaily`, `VRDaily`, `WRDaily`, and `MADaily`.

**Rationale**: The project has an established pattern where all `db_*.py` indicator modules inherit from `StockDBBase`. Only `db_asi.py` and `db_kdj.py` still use the legacy pattern (raw `pymysql.connect`, manual connection management, string-concatenated SQL). Completing this migration:

1. **Security**: Eliminates SQL injection vectors from string-concatenated queries
2. **Resource management**: Replaces per-call `pymysql.connect`/`close` with a shared PooledDB connection pool
3. **Consistency**: All 9 indicator modules share the same base class and coding pattern
4. **Testability**: `StockDBBase` subclasses can be unit-tested with a mock pool (see `tests/test_db_bias.py`)

## Data Flow

No data flow changes. The public interface (`db_get_maxdate`, `getData`, `insert`) and table schemas remain identical.

### Before (legacy pattern)

```
Constructor → stores host/port/db/user/passwd
get_conn() → pymysql.connect(...)
db_get_maxdate() → get_conn() → cur.execute("..."+code+"...") → conn.close()
getData() → get_conn() → cur.execute("..."+code+"..."+date+"...") → conn.close()
insert() → get_conn() → for: cur.execute(db_insertsql(...)) → conn.close()
```

### After (StockDBBase pattern)

```
Constructor → super().__init__(**db_kwargs)  # pool initialised once
db_get_maxdate() → with self: _query_one(sql, params) → auto commit/release
getData() → with self: _query_all(sql, params) → auto commit/release
insert() → with self: for: _execute_many(sql, params) → auto commit/release
```

## Files to Modify

| File | Change |
|---|---|
| `stockfetch/db_asi.py` | Full rewrite: inherit StockDBBase, remove raw pymysql, parameterised queries |
| `stockfetch/db_kdj.py` | Full rewrite: inherit StockDBBase, remove raw pymysql, parameterised queries, param-based table selection |

## Files to Add

| File | Purpose |
|---|---|
| `tests/test_db_asi.py` | Unit tests for ASIDaily (construction, db_get_maxdate, getData, insert, no-raw-pymysql) |
| `tests/test_db_kdj.py` | Unit tests for KDJDaily (construction, param routing, db_get_maxdate, getData, insert, no-raw-pymysql) |

## Files NOT Modified

- `stockdata/calc_indicator.py` — calls `ASIDaily(code)` and `KDJDaily(code)` / `KDJDaily(code, "522")`, which remain backward-compatible
- `stockdata/main_stock.py`, `stockdata/main_analysis.py` — wildcard imports (`from stockfetch.db_asi import *`), no change needed
- `stockfetch/main.py` — wildcard imports, no change needed
- `tests/test_api.py` — integration test file, uses `ASIDaily(code)` / `KDJDaily(code)` constructors unchanged

## Implementation Notes

### ASIDaily specifics

- The `ASI()` function from funcat returns 2 arrays: `ASI[0]` = asi values, `ASI[1]` = asi_t values
- NaN guard: skip when `asi` or `asi_t` is NaN, or when value > 999999 or < -999999 (existing behavior)
- Table: `indicators_asi_daily` with columns `(stock_code, asi, asi_t, record_time)`

### KDJDaily specifics

- The `KDJ()` function returns 3 arrays: `KDJ[0]` = k, `KDJ[1]` = d, `KDJ[2]` = j
- NaN guard: skip when `j` is NaN only (existing behavior — only checks j)
- `self.param` determines target table:
  - `"522"` → `indicators_kdj_daily_522`
  - otherwise (default `"933"`) → `indicators_kdj_daily`
- Follow `RSIDaily._table_name()` pattern for clean table routing
- Table columns: `(stock_code, k, d, j, record_time)`

### Test pattern

Follow `tests/test_db_bias.py` as the canonical test template:
- Mock PooledDB via `unittest.mock.patch`
- `_FakeValue` class to mimic funcat's Value wrapper
- Test groups: Construction → db_get_maxdate → getData → insert → NoRawConnection
- For KDJDaily, add param-based table routing tests
