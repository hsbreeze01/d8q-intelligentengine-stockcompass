# Tasks: DBClient DCL / Ping / Pool Status

## Group 1: DBClient core fixes

- [x] **1.1 Fix DCL name-mangling and lock usage in `__init__` and `__get_conn`**
  Replace all `self.__pool` references with explicit `DBClient._DBClient__pool` (the mangled class-level attribute name). Use `with DBClient.lock:` context-manager instead of manual `acquire`/`release`. Apply `is None` checks instead of truthiness checks for clarity. File: `buy/DBClient.py`.

- [x] **1.2 Add `conn.ping(reconnect=True)` in `__get_conn()`**
  After acquiring a connection from the pool and before creating the cursor, call `self._conn.ping(reconnect=True)` to auto-reconnect stale MySQL connections. File: `buy/DBClient.py`.

- [x] **1.3 Add `pool_status()` classmethod**
  Add a new classmethod that returns `{"status": "active"|"not_initialized", "connection_count": int}`. File: `buy/DBClient.py`.

## Group 2: Verification

- [x] **2.1 Run diagnostics and import smoke test**
  Run `ruff check buy/DBClient.py` and a quick Python import test to verify the module loads without errors.
