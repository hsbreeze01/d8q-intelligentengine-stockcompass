# Design: Refactor fetch_valuation.py Connection Management

## Context

`scripts/fetch_valuation.py` is a standalone data-ingestion script that fetches market-wide and individual stock valuation data from akshare and persists it to MySQL. It currently creates raw `pymysql.connect()` connections with **hardcoded credentials** and lacks guaranteed connection cleanup (`finally` blocks).

The project already provides two connection-pool utilities:
1. **`buy.DBClient`** — DBUtils-based pool, reads config from `buy/Config.py` (YAML pipeline)
2. **`compass.data.database.Database`** — DBUtils-based pool with context-manager (`with` statement), reads config from `compass.config`

Both ultimately wrap `dbutils.pooled_db.PooledDB` + `pymysql`. Since `fetch_valuation.py` lives under `scripts/` (not `compass/`) and the proposal explicitly targets `buy.DBClient`, we adopt `DBClient` as the connection provider.

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Connection provider | `buy.DBClient` | Per proposal; avoids importing compass config into a standalone script; YAML config already available |
| Lifecycle pattern | `try/finally` | Explicit and readable; `DBClient` lacks context-manager (`__enter__`/`__exit__`) support |
| Transaction control | Explicit `conn.commit()` calls | Matches existing batch-commit pattern in `fetch_individual_batch()`; `DBClient.execute()` does NOT auto-commit |
| SQL style | `%s` parameterized queries | Already in use; no change needed |
| Logging | Keep existing `logging` module setup | No change; consistency with rest of script |

## Data Flow

```
main()
  ├── create_table()        → DBClient() → DDL × 2 → commit → close
  ├── fetch_market_pe()     → akshare API → DBClient() → INSERT rows → commit → close
  ├── fetch_market_pb()     → akshare API → DBClient() → INSERT rows → commit → close
  └── (fetch_individual_batch) → akshare API → DBClient() → INSERT batches → commit per batch → close
```

Every function follows the same pattern:

```
conn = DBClient()
try:
    # ... database operations ...
    conn.commit()
finally:
    conn.close()
```

## File Changes

| File | Action | Description |
|---|---|---|
| `scripts/fetch_valuation.py` | **MODIFY** | Replace `get_db()` body, add `try/finally` to all 4 functions, remove hardcoded credentials, add `from buy.DBClient import DBClient` import |

No other files need modification. The `buy/DBClient.py` and `buy/Config.py` modules are consumed as-is.

## Key Implementation Details

### 1. `get_db()` replacement

The function body changes from:
```python
def get_db():
    return pymysql.connect(host='localhost', user='root', password='password', database='stock_analysis_system')
```
To:
```python
from buy.DBClient import DBClient

def get_db():
    return DBClient()
```

This delegates connection configuration to `buy/Config.py` → YAML files, eliminating hardcoded credentials.

### 2. `create_table()` — try/finally

```python
def create_table():
    conn = get_db()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS ...""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ...""")
        conn.commit()
    finally:
        conn.close()
```

Note: `DBClient.execute()` returns `(count, lastrowid)`. DDL statements work fine through it.

### 3. `fetch_market_pe()` / `fetch_market_pb()` — try/finally around conn

The connection acquisition moves inside a `try` block with `finally: conn.close()`. The outer `try/except` for akshare errors is preserved but restructured so that DB connection lifecycle is separate:

```python
def fetch_market_pe():
    try:
        import akshare as ak
        df = ak.stock_market_pe_lg()
        ...
        conn = get_db()
        try:
            for idx, row in df.iterrows():
                conn.execute("INSERT IGNORE INTO ...", (...))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(...)
```

### 4. `fetch_individual_batch()` — single connection, try/finally

Keeps the existing single-connection-for-entire-batch pattern, wrapped in `try/finally`:

```python
def fetch_individual_batch():
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()  # with retry
        ...
        conn = get_db()
        try:
            for batch in batches:
                for row in batch:
                    conn.execute("INSERT IGNORE INTO ...", (...))
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(...)
```

### 5. Cursor consideration

`DBClient` returns `DictCursor` results. The `fetch_valuation.py` script only uses `execute()` for INSERT/DDL (no `fetchone`/`fetchall`), so the cursor class change has no behavioral impact.
