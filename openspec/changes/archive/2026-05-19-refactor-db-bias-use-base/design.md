# Design: Refactor BIASDaily to inherit StockDBBase

## Overview

Refactor `stockfetch/db_bias.py` so that `BIASDaily` extends
`stockfetch.db_base.StockDBBase`, eliminating raw `pymysql.connect()` calls,
manual `conn.close()`, and SQL string concatenation. This is the first `db_*`
module to adopt the new base class; it establishes the pattern for subsequent
refactors of `db_kdj`, `db_ma`, etc.

## Architecture Decisions

| Decision | Rationale |
|---|---|
| Inherit `StockDBBase` | Reuse process-wide `PooledDB` connection pool, context manager, and query helpers (`_query_one`, `_query_all`, `_execute_many`). |
| Keep constructor signature compatible | Callers use `BIASDaily(code)` and `BIASDaily(code, **db_kwargs)`. The new constructor calls `super().__init__(**db_kwargs)` and stores `self.code`. |
| Use `with self:` blocks | Guarantees commit-on-success / rollback-on-error and automatic connection release. |
| Parameterised queries (`%s`) | Eliminates SQL injection risk from string concatenation. |
| Remove `get_conn`, `db_disconnect`, `db_insertsql` | These are replaced by base-class helpers; keeping them would create dead code. |
| Handle `DictCursor` in `getData` | `StockDBBase` pool uses `pymysql.cursors.DictCursor`. `pd.DataFrame(rows)` works directly since each row is a `dict`. No need to extract column names from `cursor.description`. |

## Data Flow

### db_get_maxdate()

```
BIASDaily.db_get_maxdate()
  → with self:
      _query_one("SELECT max(date) FROM stock_data_daily WHERE stock_code = %s", (self.code,))
      → return row["max(date)"] or None
```

### getData()

```
BIASDaily.getData()
  → lastUpdateDate = self.db_get_maxdate()  # may return None → fallback "2000-01-01"
  → with self:
      _query_all("SELECT * FROM indicators_bias_daily WHERE stock_code = %s AND record_time <= %s", (self.code, lastUpdateDate))
      → return pd.DataFrame(rows)
```

**Note on date handling**: `db_get_maxdate()` returns a `datetime.date` or
`None`. When `None`, we use `datetime.date(2000, 1, 1)` as fallback. The
parameterised query handles both `datetime.date` and `str` transparently via
pymysql's type conversion.

### insert()

```
BIASDaily.insert(BIAS, DATETIME)
  → b1, b2, b3 = BIAS[0], BIAS[1], BIAS[2]
  → with self:
      for index in reversed(range(len(DATETIME))):
          validate (skip NaN, skip > 9999)
          _execute_many(
              "REPLACE INTO indicators_bias_daily (stock_code, bias_1, bias_2, bias_3, record_time) VALUES (%s, %s, %s, %s, %s)",
              (self.code, b1_val, b2_val, b3_val, record_time_str)
          )
      # auto-commit on __exit__
```

**Validation**: BIAS uses the same NaN check as KDJ but adds a `> 9999`
guard on all three values. This behaviour is preserved.

## Files to Modify

| File | Action |
|---|---|
| `stockfetch/db_bias.py` | **Rewrite** — inherit `StockDBBase`, remove raw pymysql, add parameterised queries. |

## Files to Add

| File | Action |
|---|---|
| `tests/test_db_bias.py` | **New** — unit tests for refactored `BIASDaily` using mock pool (same pattern as `tests/test_stockdb_base.py`). |

## Files Not Changed

| File | Reason |
|---|---|
| `stockdata/calc_indicator.py` | Uses `from stockfetch.db_bias import *` — public interface unchanged. |
| `stockdata/main_analysis.py` | Same wildcard import — unaffected. |
| `tests/test_api.py` | Same wildcard import — unaffected. |
| `stockdata/main_stock.py` | Same wildcard import — unaffected. |
| `stockfetch/db_base.py` | Base class is stable; no changes needed. |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `DictCursor` changes `getData()` DataFrame column ordering | Test asserts column names are present; `pd.DataFrame` from dicts preserves keys. |
| `db_get_maxdate()` returns `None` vs date in tuple access | Use dict key `row["max(date)"]` with a fallback, tested explicitly. |
| Other `db_*` modules not yet refactored import `*` from `db_bias` | Wildcard import only pulls `BIASDaily` class name — no conflict. |
