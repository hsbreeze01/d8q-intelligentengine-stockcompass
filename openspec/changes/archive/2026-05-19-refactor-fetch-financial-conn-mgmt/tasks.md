# Tasks: Refactor fetch_financial.py Connection Management

## 1. Connection Pool Migration

- [x] **1.1 Replace get_db() and imports to use DBClient pool**
  - Remove `import pymysql` from `scripts/fetch_financial.py`
  - Change `get_db()` to return `DBClient()` instance from `buy.DBClient`
  - Ensure `sys.path` setup allows importing `buy.DBClient`
  - Scope: `scripts/fetch_financial.py` lines 1–17

## 2. Connection Lifecycle Safety

- [x] **2.1 Add try/finally to store_profit, store_balance, and main()**
  - Wrap `store_profit`: `conn = get_db()` in `try/finally: conn.close()`
  - Wrap `store_balance`: same pattern
  - Wrap `main()` stock list query: `conn = get_db()` in `try/finally: conn.close()`
  - Adapt `main()` SELECT to use `conn.select_many()` (returns `List[dict]`), extract codes
  - Adapt `store_profit`/`store_balance` INSERT/UPDATE to use `conn.execute()` (returns `(count, id)`) + `conn.commit()`
  - Scope: `scripts/fetch_financial.py` — `store_profit`, `store_balance`, `main()`

## 3. Verification

- [x] **3.1 Verify syntax and lint**
  - Run `ruff check scripts/fetch_financial.py` — must pass with no errors
  - Run `python -c "import scripts.fetch_financial"` or equivalent import check
  - Confirm `pymysql.connect` does not appear in the file
