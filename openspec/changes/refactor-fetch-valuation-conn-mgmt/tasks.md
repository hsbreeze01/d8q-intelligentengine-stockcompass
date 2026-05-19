# Tasks: Refactor fetch_valuation.py Connection Management

## Group 1: Connection Pool Migration & Lifecycle Safety

- [x] **1.1** Replace `get_db()` with `DBClient` pool and add `try/finally` to all functions
  - Remove `import pymysql` and hardcoded `get_db()` body
  - Add `from buy.DBClient import DBClient`; `get_db()` returns `DBClient()`
  - Wrap `create_table()`, `fetch_market_pe()`, `fetch_market_pb()`, `fetch_individual_batch()` in `try/finally: conn.close()`
  - Replace raw `cursor.execute()` calls with `conn.execute()` (DBClient API)
  - Ensure all `conn.commit()` calls remain in place
  - Verify no string-formatting in SQL (already parameterized — confirm)

## Group 2: Verification

- [x] **2.1** Run static analysis on the refactored file
  - `ruff check scripts/fetch_valuation.py` passes with no errors
  - `python -c "import ast; ast.parse(open('scripts/fetch_valuation.py').read())"` succeeds (syntax valid)
  - Grep confirms no `pymysql.connect` remaining in the file
  - Grep confirms all `conn = get_db()` are followed by `try:` blocks with `finally: conn.close()`
