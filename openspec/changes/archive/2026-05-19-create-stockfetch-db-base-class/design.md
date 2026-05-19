# Design: StockDBBase — Unified Database Base Class

## Architecture Decision

Create `stockfetch/db_base.py` as a new greenfield module. The design closely follows the proven pattern from `compass/data/database.py` (class-level pool, context manager, `__enter__`/`__exit__`) while adding explicit `open()`/`close()` for backward compatibility with legacy callers that use manual lifecycle management (like `buy/task/*.py`).

### Why a new module instead of extending `compass/data/database.py`?

1. **Separation of concern** — `compass/data/database.py` is tightly coupled to `compass.config.get_config()` (Flask env-based configuration). The `stockfetch` subsystem uses `buy/Config.py` (YAML-based configuration).
2. **Dependency direction** — `stockfetch/` is intended to be a low-level data access layer. It should not depend on the Flask-based compass config system.
3. **Gradual migration** — A new base class allows `funcat/data/db_backend.py` and `buy/task/*.py` to be incrementally refactored without touching the working compass module.

## Class Design

```
StockDBBase
├── __init__(pool_params=None, **db_kwargs)   # lazy pool init
├── __enter__() -> self                        # acquire conn
├── __exit__(exc_type, exc_val, exc_tb)        # commit/rollback + release
├── open()                                     # explicit acquire
├── close()                                    # explicit release
├── _get_conn()                                # internal: acquire from pool
├── _query_one(sql, params=()) -> (int, dict|None)
├── _query_all(sql, params=()) -> (int, list[dict])
├── _execute_many(sql, params=()) -> (int, int)
├── commit()
├── rollback()
└── Class-level:
    __pool: PooledDB | None
    _lock: threading.Lock
```

### Connection Configuration Flow

```
Constructor call
  │
  ├─ Has **db_kwargs overrides? ──→ Use provided host/port/user/etc.
  │
  └─ No overrides? ──→ Read from buy/Config.py taskConfig.getDBconnection()
       │
       └─ Returns dict: {host, port, user, password, database}
```

### Pool Initialization (Thread-Safe Double-Checked Locking)

```
__init__()
  │
  ├─ cls.__pool is not None? ──→ Skip (pool exists)
  │
  └─ cls.__pool is None?
       │
       ├─ Acquire cls._lock
       ├─ cls.__pool is still None? ──→ Create PooledDB(...)
       └─ Release cls._lock
```

### Connection Lifecycle (Context Manager)

```
with StockDBBase() as db:
    db._query_all("SELECT ...")
    db._execute_many("INSERT ...")
    # on normal exit: commit() + close()
    # on exception: rollback() + close() + re-raise
```

### Connection Lifecycle (Explicit)

```
db = StockDBBase()
db.open()
try:
    db._execute_many("INSERT ...")
    db.commit()
except:
    db.rollback()
finally:
    db.close()
```

## Files to Create

| File | Purpose |
|------|---------|
| `stockfetch/__init__.py` | Package init, exports `StockDBBase` |
| `stockfetch/db_base.py` | `StockDBBase` class with pool, context manager, query methods |

## Files NOT Modified (This Change)

This change is purely additive. No existing files are modified. Future changes will refactor consumers to use `StockDBBase`:

- `funcat/data/db_backend.py` — will be refactored to extend `StockDBBase` instead of raw `pymysql.connect()`
- `buy/task/*.py` — will be refactored to use `StockDBBase` context manager instead of manual `DBClient()` + `close()`
- `buy/DBClient.py` — will eventually be deprecated in favor of `StockDBBase`

## Dependencies

- `pymysql` — MySQL driver (already in requirements)
- `dbutils.pooled_db.PooledDB` — connection pooling (already in requirements)
- `buy/Config.py` — YAML-based config with `taskConfig` singleton (existing, read-only dependency)
- `threading` — for pool init locking (stdlib)

## Test Strategy

Unit tests in `tests/test_stockdb_base.py` will:
1. Mock `PooledDB` to verify pool is created once
2. Verify context manager `__enter__`/`__exit__` calls commit/close on success
3. Verify context manager calls rollback/close on exception
4. Verify `_query_one`, `_query_all`, `_execute_many` delegate to cursor correctly
5. Verify `RuntimeError` when calling query methods without active connection
6. Verify double `close()` is safe (no-op)
