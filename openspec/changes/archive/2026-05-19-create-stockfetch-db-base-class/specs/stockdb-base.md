# Delta Spec: StockDBBase — Unified Database Base Class

## Overview

Introduce `stockfetch/db_base.py` containing a `StockDBBase` class that provides a single, reusable database access foundation for all stockfetch-related modules. This eliminates the need for each module to independently manage PooledDB creation, connection lifecycle, and query execution.

---

## ADDED Requirements

### Requirement: Connection Pool Initialization

The system SHALL provide a `StockDBBase` class that initializes a process-wide `dbutils.pooled_db.PooledDB` connection pool on first instantiation, using DB connection parameters sourced from `buy/Config.py` (`taskConfig.getDBconnection()`).

#### Scenario: First instantiation creates the shared pool

- **Given** no `StockDBBase` instance has been created in the current process
- **When** a `StockDBBase` instance is constructed
- **Then** the system SHALL create a `PooledDB` instance stored as a class-level attribute with the following defaults: `mincached=5`, `maxcached=20`, `maxconnections=100`, `blocking=True`, `charset='utf8mb4'`, `cursorclass=pymysql.cursors.DictCursor`
- **And** the pool SHALL be initialized exactly once (thread-safe double-checked locking)

#### Scenario: Subsequent instantiation reuses existing pool

- **Given** a `StockDBBase` instance has already been created in the current process
- **When** another `StockDBBase` instance is constructed
- **Then** the system SHALL reuse the existing class-level pool without creating a new one

#### Scenario: Custom connection parameters override defaults

- **Given** a caller provides explicit `host`, `port`, `db`, `user`, `passwd` keyword arguments to the constructor
- **When** the pool is first initialized
- **Then** the system SHALL use the provided parameters instead of those from `taskConfig`

---

### Requirement: Context Manager Connection Lifecycle

The `StockDBBase` class SHALL support Python context manager protocol (`with` statement) for automatic connection acquisition and release.

#### Scenario: Entering context acquires a pooled connection

- **Given** a `StockDBBase` instance
- **When** entering a `with` block (`__enter__`)
- **Then** the system SHALL acquire a connection from the pool and create a cursor
- **And** the instance SHALL be returned as the context manager value

#### Scenario: Exiting context without error commits and releases

- **Given** a `StockDBBase` instance inside a `with` block
- **When** the block exits without raising an exception
- **Then** the system SHALL call `commit()` on the connection
- **And** the system SHALL close the cursor and return the connection to the pool

#### Scenario: Exiting context with error rolls back and releases

- **Given** a `StockDBBase` instance inside a `with` block
- **When** the block exits due to an exception
- **Then** the system SHALL call `rollback()` on the connection
- **And** the system SHALL close the cursor and return the connection to the pool
- **And** the exception SHALL propagate to the caller

---

### Requirement: Parameterized Query Methods

The `StockDBBase` class SHALL expose three parameterized query methods that enforce safe SQL execution.

#### Scenario: `_query_one` returns a single row

- **Given** a `StockDBBase` instance with an active connection
- **When** `_query_one(sql, params)` is called with a SELECT statement and tuple parameters
- **Then** the system SHALL execute the parameterized query
- **And** return a tuple of `(row_count: int, row: dict | None)` where `row` is `fetchone()` result

#### Scenario: `_query_all` returns all matching rows

- **Given** a `StockDBBase` instance with an active connection
- **When** `_query_all(sql, params)` is called with a SELECT statement and tuple parameters
- **Then** the system SHALL execute the parameterized query
- **And** return a tuple of `(row_count: int, rows: list[dict])` where `rows` is `fetchall()` result

#### Scenario: `_execute_many` executes a write operation

- **Given** a `StockDBBase` instance with an active connection
- **When** `_execute_many(sql, params)` is called with an INSERT/UPDATE/DELETE statement and parameters
- **Then** the system SHALL execute the parameterized statement
- **And** return a tuple of `(affected_rows: int, last_row_id: int)`

#### Scenario: Query methods require active connection

- **Given** a `StockDBBase` instance without an active connection (not inside a `with` block)
- **When** any of `_query_one`, `_query_all`, `_execute_many` is called
- **Then** the system SHALL raise a `RuntimeError` with a message indicating no active connection

---

### Requirement: Explicit Connection Management (Non-Context-Manager)

The `StockDBBase` class SHALL also support explicit `open()` / `close()` lifecycle for callers that cannot use `with` blocks.

#### Scenario: Explicit open acquires connection

- **Given** a `StockDBBase` instance with no active connection
- **When** `open()` is called
- **Then** the system SHALL acquire a connection from the pool and create a cursor

#### Scenario: Explicit close releases connection

- **Given** a `StockDBBase` instance with an active connection
- **When** `close()` is called
- **Then** the system SHALL close the cursor and return the connection to the pool

#### Scenario: Double close is safe

- **Given** a `StockDBBase` instance whose connection has already been closed
- **When** `close()` is called again
- **Then** the system SHALL not raise an error (no-op)

---

### Requirement: Commit and Rollback

The `StockDBBase` class SHALL expose explicit `commit()` and `rollback()` methods for transaction control.

#### Scenario: Commit persists pending changes

- **Given** a `StockDBBase` instance with an active connection and pending write operations
- **When** `commit()` is called
- **Then** the system SHALL commit the current transaction on the connection

#### Scenario: Rollback discards pending changes

- **Given** a `StockDBBase` instance with an active connection and pending write operations
- **When** `rollback()` is called
- **Then** the system SHALL roll back the current transaction on the connection

---

### Requirement: Module Structure

The `stockfetch` package SHALL be a valid Python package with an `__init__.py` that exports `StockDBBase`.

#### Scenario: Importable from stockfetch package

- **Given** the `stockfetch` package is on the Python path
- **When** a caller writes `from stockfetch.db_base import StockDBBase`
- **Then** the import SHALL succeed without error
