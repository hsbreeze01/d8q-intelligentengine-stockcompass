# Tasks: Refactor BIASDaily to inherit StockDBBase

## 1. Rewrite stockfetch/db_bias.py

- [x] **1.1** Rewrite `BIASDaily` to inherit `StockDBBase` with parameterised queries
  - Change class declaration to `class BIASDaily(StockDBBase):`
  - Rewrite `__init__(self, code, **db_kwargs)` to call `super().__init__(**db_kwargs)` and store `self.code`
  - Rewrite `db_get_maxdate()` to use `_query_one` with `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` inside `with self:`
  - Rewrite `getData()` to use `_query_all` with parameterised `SELECT * FROM indicators_bias_daily WHERE stock_code = %s AND record_time <= %s` inside `with self:`, return `pd.DataFrame(rows)`
  - Rewrite `insert(BIAS, DATETIME)` to iterate arrays, validate (skip NaN, skip > 9999), and use `_execute_many` with parameterised `REPLACE INTO` inside `with self:`
  - Remove `get_conn()`, `db_disconnect()`, `db_insertsql()`
  - Remove `import pymysql` and `from buy.Config import taskConfig as config` (no longer needed)

## 2. Add unit tests

- [x] **2.1** Create `tests/test_db_bias.py` — unit tests for refactored `BIASDaily`
  - Test construction with code-only and with explicit db kwargs
  - Test `db_get_maxdate()` returns date or None (mock `_query_one`)
  - Test `getData()` returns DataFrame with correct data (mock `_query_all`)
  - Test `insert()` skips NaN and > 9999 values, writes valid rows (mock `_execute_many`)
  - Follow mock-pool pattern from `tests/test_stockdb_base.py`

## 3. Verify

- [x] **3.1** Run lint and tests
  - `ruff check stockfetch/db_bias.py tests/test_db_bias.py`
  - `pytest tests/test_db_bias.py -v`
  - `pytest tests/test_stockdb_base.py -v` (regression)
