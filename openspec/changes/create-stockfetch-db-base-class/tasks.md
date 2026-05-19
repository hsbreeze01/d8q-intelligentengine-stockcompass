# Tasks: Create StockDBBase

## 1. Package & Base Class Implementation

- [x] **1.1 Create `stockfetch/` package with `StockDBBase` class**
  - Create `stockfetch/__init__.py` exporting `StockDBBase`
  - Create `stockfetch/db_base.py` with the full class: class-level `PooledDB` pool (thread-safe double-checked locking), `__init__` reading from `buy/Config.py` taskConfig, context manager (`__enter__`/`__exit__`), explicit `open()`/`close()`, `_get_conn()`, `_query_one()`, `_query_all()`, `_execute_many()`, `commit()`, `rollback()`
  - Files: `stockfetch/__init__.py`, `stockfetch/db_base.py`

## 2. Tests

- [x] **2.1 Create unit tests for `StockDBBase`**
  - Mock `PooledDB` and verify: single pool creation, context manager commit/rollback paths, query method delegation, `RuntimeError` without active connection, double `close()` safety, custom db kwargs override
  - File: `tests/test_stockdb_base.py`

## 3. Validation

- [x] **3.1 Run linter and tests**
  - `ruff check stockfetch/` passes
  - `pytest tests/test_stockdb_base.py` passes
