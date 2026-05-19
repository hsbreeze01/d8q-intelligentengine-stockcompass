# Delta Spec: DBClient DCL / Ping / Pool Status

## MODIFIED Requirements

### Requirement: DBClient connection pool initialization MUST use correct double-checked locking

The `DBClient` class SHALL use the mangled attribute name `DBClient._DBClient__pool` consistently in all DCL checks, instead of relying on `self.__pool` which may resolve differently depending on context. The outer check, inner check, and assignment SHALL all reference `DBClient._DBClient__pool` explicitly.

#### Scenario: Pool initialized once under concurrent construction

- **Given** `DBClient._DBClient__pool` is `None`
- **When** multiple threads create `DBClient()` instances simultaneously
- **Then** exactly one `PooledDB` instance SHALL be created
- **And** all `DBClient` instances SHALL share the same pool

#### Scenario: Pool already initialized skips creation

- **Given** `DBClient._DBClient__pool` is already a `PooledDB` instance
- **When** a new `DBClient()` is constructed
- **Then** no new `PooledDB` SHALL be created
- **And** the existing pool SHALL be reused

---

### Requirement: DBClient SHALL auto-reconnect stale MySQL connections

The `__get_conn()` method SHALL call `conn.ping(reconnect=True)` on the connection obtained from the pool before returning it. This ensures that stale or timed-out connections are transparently reconnected without raising `OperationalError: (2006, "MySQL server has gone away")`.

#### Scenario: Stale connection is transparently reconnected

- **Given** a connection in the pool has been idle beyond MySQL's `wait_timeout`
- **When** `DBClient()` is constructed and `__get_conn()` acquires that connection
- **Then** `ping(reconnect=True)` SHALL be called on the connection
- **And** the connection SHALL be alive before any SQL is executed

#### Scenario: Live connection remains usable after ping

- **Given** a connection in the pool is still alive
- **When** `__get_conn()` calls `ping(reconnect=True)`
- **Then** the connection SHALL remain open and usable
- **And** no error SHALL be raised

---

## ADDED Requirements

### Requirement: DBClient SHALL expose pool status via classmethod

A new classmethod `pool_status()` SHALL return a `dict` describing the current state of the connection pool.

The returned dict SHALL contain:
- `"status"`: `"active"` when the pool is initialized, `"not_initialized"` otherwise
- `"connection_count"`: the current value of `_connection_count` (int)

#### Scenario: Pool is initialized

- **Given** `DBClient._DBClient__pool` is a `PooledDB` instance
- **And** `_connection_count` is `3`
- **When** `DBClient.pool_status()` is called
- **Then** it SHALL return `{"status": "active", "connection_count": 3}`

#### Scenario: Pool is not yet initialized

- **Given** `DBClient._DBClient__pool` is `None`
- **And** `_connection_count` is `0`
- **When** `DBClient.pool_status()` is called
- **Then** it SHALL return `{"status": "not_initialized", "connection_count": 0}`

---

### Requirement: DBClient public interface SHALL remain unchanged

The following public methods SHALL continue to exist with the same signatures and return types: `select_one`, `select_many`, `select_many_cols`, `execute`, `commit`, `rollback`, `close`, `get_connection_count`.

#### Scenario: Existing callers continue to work

- **Given** any existing code that uses `DBClient` via `with Database() as db:` or direct instantiation
- **When** the code calls `select_one`, `select_many`, `select_many_cols`, `execute`, `commit`, `rollback`, or `close`
- **Then** the behavior and return types SHALL be identical to before the change
