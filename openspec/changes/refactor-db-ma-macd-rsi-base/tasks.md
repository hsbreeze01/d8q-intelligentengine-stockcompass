# Tasks: Refactor db_ma / db_macd / db_rsi to StockDBBase

## Group 1: MA indicator module

- [x] **1.1 Rewrite `stockfetch/db_ma.py`** — Replace `MADaily(object)` with `MADaily(StockDBBase)`. Remove `get_conn`, `db_disconnect`, `db_insertsql`. Rewrite `db_get_maxdate`, `getData`, `insert` to use `with self:` + `_query_one` / `_query_all` / `_execute_many` with parameterized queries. Keep same public interface: constructor `(code, **db_kwargs)`, methods `db_get_maxdate()`, `getData()`, `insert(ma5, ma10, ma20, ma30, ma60, DATETIME)`.

## Group 2: MACD indicator module

- [x] **2.1 Rewrite `stockfetch/db_macd.py`** — Replace `MACDDaily(object)` with `MACDDaily(StockDBBase)`. Remove `get_conn`, `db_disconnect`, `db_insertsql`. Rewrite `db_get_maxdate`, `getData`, `insert` to use `with self:` + parameterized helpers. Keep same public interface: constructor `(code, **db_kwargs)`, methods `db_get_maxdate()`, `getData()`, `insert(MACD, DATETIME)`.

## Group 3: RSI indicator module

- [x] **3.1 Rewrite `stockfetch/db_rsi.py`** — Replace `RSIDaily(object)` with `RSIDaily(StockDBBase)`. Remove `get_conn`, `db_disconnect`, `db_insertsql`. Rewrite `db_get_maxdate`, `getData`, `insert` to use `with self:` + parameterized helpers. Preserve `self.param` table-selection logic (`"61224"` → `indicators_rsi_daily`, `"3612"` → `indicators_rsi_daily_3612`). Keep same public interface: constructor `(code, param="61224", **db_kwargs)`.

## Group 4: Verification

- [x] **4.1 Run ruff lint + existing tests** — Verify all three files pass `ruff check` and existing `pytest` tests. If tests use wildcard imports (`from stockfetch.db_ma import *`), they should still resolve correctly.
