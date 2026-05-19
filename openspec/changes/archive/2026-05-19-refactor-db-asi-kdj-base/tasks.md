# Tasks: Refactor ASIDaily & KDJDaily to StockDBBase

## 1. Refactor ASIDaily module

- [x] Rewrite `stockfetch/db_asi.py` — ASIDaily inherits StockDBBase, parameterised queries, pooled connections
  - Change base class from `object` to `StockDBBase`
  - Constructor: `def __init__(self, code, **db_kwargs)` → `super().__init__(**db_kwargs)` + `self.code = code`
  - Remove: `get_conn`, `db_disconnect`, `db_insertsql` methods; remove `pymysql` import
  - Rewrite `db_get_maxdate`: use `with self:` + `_query_one` with `%s` placeholder
  - Rewrite `getData`: use `with self:` + `_query_all` with `%s` placeholder
  - Rewrite `insert`: use `with self:` + `_execute_many` with parameterised `REPLACE INTO`
  - Keep NaN/out-of-range guard logic: skip if asi or asi_t is NaN or |value| > 999999

## 2. Refactor KDJDaily module

- [x] Rewrite `stockfetch/db_kdj.py` — KDJDaily inherits StockDBBase, parameterised queries, pooled connections, param-based table routing
  - Change base class from `object` to `StockDBBase`
  - Constructor: `def __init__(self, code, param="933", **db_kwargs)` → `super().__init__(**db_kwargs)` + `self.code = code` + `self.param = param`
  - Remove: `get_conn`, `db_disconnect`, `db_insertsql` methods; remove `pymysql` import
  - Add `_table_name()` helper: returns `indicators_kdj_daily_522` if param=="522", else `indicators_kdj_daily`
  - Rewrite `db_get_maxdate`: use `with self:` + `_query_one` with `%s` placeholder
  - Rewrite `getData`: use `with self:` + `_query_all` + `_table_name()` with `%s` placeholder
  - Rewrite `insert`: use `with self:` + `_execute_many` + `_table_name()` with parameterised `REPLACE INTO`
  - Keep NaN guard: skip if j is NaN (only checks j, per original behavior)

## 3. Add unit tests for ASIDaily

- [x] Create `tests/test_db_asi.py` — full unit test suite following `test_db_bias.py` pattern
  - Mock PooledDB, `_FakeValue` helper, pool reset fixture
  - Test: construction (code only, explicit db_kwargs, inherits StockDBBase)
  - Test: db_get_maxdate (returns date, returns None, uses parameterised query)
  - Test: getData (returns DataFrame, fallback date, parameterised query)
  - Test: insert (valid records, skips NaN, skips out-of-range ±999999, parameterised REPLACE INTO)
  - Test: no raw pymysql (source inspection: no `pymysql.connect`, no `get_conn`, no `db_disconnect`, no `db_insertsql`)

## 4. Add unit tests for KDJDaily

- [x] Create `tests/test_db_kdj.py` — full unit test suite with param routing coverage
  - Mock PooledDB, `_FakeValue` helper, pool reset fixture
  - Test: construction (code only, with param="522", explicit db_kwargs, inherits StockDBBase)
  - Test: `_table_name()` routing (default → `indicators_kdj_daily`, param="522" → `indicators_kdj_daily_522`)
  - Test: db_get_maxdate (returns date, returns None, uses parameterised query)
  - Test: getData (returns DataFrame for default table, returns DataFrame for 522 table, fallback date, parameterised query)
  - Test: insert (valid records, skips NaN on j, targets correct table per param, parameterised REPLACE INTO)
  - Test: no raw pymysql (source inspection)

## 5. Verify all tests pass

- [x] Run `pytest tests/` and `ruff check stockfetch/db_asi.py stockfetch/db_kdj.py` — zero failures, zero lint errors
