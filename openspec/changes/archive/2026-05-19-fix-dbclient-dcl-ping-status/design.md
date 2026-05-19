# Design: DBClient DCL / Ping / Pool Status

## Problem

`buy/DBClient.py` has three issues:

1. **DCL name-mangling bug**: `self.__pool` triggers Python name mangling → `self._DBClient__pool`. The DCL checks `if not self.__pool` then acquires the lock and checks again. While Python's attribute lookup will fall back to the class-level `DBClient.__pool`, the semantics are fragile and confusing. The assignment `self.__class__.__pool = PooledDB(...)` writes to the class attribute, but the reads go through instance lookup — a subtle bug risk.

2. **No stale-connection protection**: After MySQL's `wait_timeout` expires, pooled connections die. The next use raises `OperationalError: (2006, "MySQL server has gone away")`. The file header even documents this exact error but doesn't fix it.

3. **No pool observability**: There is no way to check whether the pool has been initialized or how many connections are outstanding without reaching into private attributes.

## Approach

All three fixes are confined to `buy/DBClient.py`. No other files are affected.

### 1. DCL fix

Replace all `self.__pool` references with `DBClient._DBClient__pool` (the mangled class-level name). This makes reads and writes unambiguous:

```python
# Before (fragile)
if not self.__pool:
    with DBClient.lock:
        if not self.__pool:
            self.__class__.__pool = PooledDB(...)

# After (explicit)
if DBClient._DBClient__pool is None:
    with DBClient.lock:
        if DBClient._DBClient__pool is None:
            DBClient._DBClient__pool = PooledDB(...)
```

Also replace `self.__pool` in `__get_conn()` with `DBClient._DBClient__pool`.

The `with` context-manager form replaces the manual `acquire`/`release` for cleaner exception safety.

### 2. Ping on connect

After acquiring a connection from the pool in `__get_conn()`, call `conn.ping(reconnect=True)`:

```python
def __get_conn(self):
    self._conn = DBClient._DBClient__pool.connection()
    self._conn.ping(reconnect=True)
    self._cursor = self._conn.cursor()
```

`ping(reconnect=True)` is a no-op on live connections and auto-reconnects dead ones. PyMySQL supports this natively.

### 3. pool_status classmethod

```python
@classmethod
def pool_status(cls):
    return {
        "status": "active" if cls._DBClient__pool is not None else "not_initialized",
        "connection_count": cls._connection_count,
    }
```

This is purely additive — no existing method is changed.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `buy/DBClient.py` | **MODIFY** | Fix DCL, add ping, add pool_status() |

No other files need changes. The public interface is preserved.

## Data Flow

```
DBClient.__init__()
  → DCL check (DBClient._DBClient__pool is None)
    → with DBClient.lock
      → create PooledDB if needed
  → __get_conn()
    → pool.connection()
    → conn.ping(reconnect=True)   ← NEW
    → cursor = conn.cursor()

DBClient.pool_status()            ← NEW
  → read cls._DBClient__pool
  → read cls._connection_count
  → return {"status": ..., "connection_count": ...}
```

## Risk Assessment

- **Low risk**: Changes are confined to a single file with no API changes.
- **Backward compatible**: All public method signatures unchanged.
- **Test**: Manual verification via `DBClient.pool_status()` before and after construction.
