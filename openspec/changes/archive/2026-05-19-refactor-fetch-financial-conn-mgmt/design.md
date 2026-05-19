# Design: Refactor fetch_financial.py Connection Management

## Architecture Decision

Replace raw `pymysql.connect()` with the existing `DBClient` connection pool from
`buy/DBClient.py`.

**Why DBClient instead of compass.data.Database?**

| Factor | `buy.DBClient` | `compass.data.Database` |
|--------|---------------|------------------------|
| Config source | `buy/config/config_*.yaml` | `compass.config` (env vars) |
| Used by `buy/` module | ✅ Same package | ❌ Cross-module dependency |
| Connection pool | DBUtils PooledDB | DBUtils PooledDB |
| Context manager | No (manual close) | Yes (`__enter__`/`__exit__`) |
| Module location | `buy.DBClient` | `compass.data.database` |

`scripts/fetch_financial.py` already imports from `buy/` path space and the
YAML config has the same DB credentials. Using `DBClient` avoids pulling the
entire `compass` config layer into a standalone script.

## Data Flow (Unchanged)

```
main()
  ├── conn = DBClient()          ← was pymysql.connect()
  │     SELECT code FROM stock_basic
  ├── conn.close()               ← in finally block
  │
  └── for each stock:
        └── fetch_one_stock(code)
              ├── akshare → store_profit(code, df)
              │     conn = DBClient()
              │     INSERT IGNORE INTO stock_financial …
              │     conn.commit()
              │     conn.close()   ← in finally block
              │
              ├── akshare → store_balance(code, df)
              │     conn = DBClient()
              │     UPDATE / INSERT IGNORE stock_financial …
              │     conn.commit()
              │     conn.close()   ← in finally block
              │
              └── akshare → cash flow (log only, no DB)
```

## Key Design Decisions

1. **`get_db()` returns `DBClient()`** — Single-line function retained for
   indirection; consumers don't change their call pattern.

2. **`try/finally` on every `conn = get_db()`** — Guarantees `conn.close()` is
   called even when exceptions occur inside the loop body. The `DBClient.close()`
   method returns the connection to the pool (does not destroy it).

3. **`conn.execute()` replaces `cursor.execute()` + `conn.commit()`** —
   `DBClient.execute()` already wraps `cursor.execute()` and returns
   `(count, lastrowid)`. We call `conn.commit()` separately to match the
   original transactional behavior (batch commit after all rows).

4. **`conn.select_many()` replaces raw cursor SELECT** — In `main()`, the
   `SELECT code FROM stock_basic` query uses `conn.select_many()` which returns
   `List[dict]`. We extract codes via list comprehension.

5. **Parameterized queries** — Already partially in place (`%s` in INSERT/UPDATE).
   The `SELECT code FROM stock_basic` has no user input, but we keep it as a
   parameterized call for consistency.

## Files Modified

| File | Change |
|------|--------|
| `scripts/fetch_financial.py` | Replace `pymysql.connect()` with `DBClient`, add `try/finally`, remove `pymysql` import |

## Files Unchanged

- `buy/DBClient.py` — Already provides all needed functionality
- `buy/Config.py` — Already loads YAML config with DB credentials
- `buy/config/config_*.yaml` — Credentials already match
