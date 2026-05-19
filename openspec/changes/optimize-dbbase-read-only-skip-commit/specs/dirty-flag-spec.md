# Spec: Read-Only Context Skip Commit

## MODIFIED Requirements

### Requirement: StockDBBase context manager SHALL skip commit on read-only usage

The `__exit__` method of `StockDBBase` currently commits on every clean exit,
even when only `SELECT` queries were executed. This wastes a round-trip to the
database server for pure read operations such as `db_get_maxdate()` and
`getData()`.

#### Scenario: Read-only `with` block exits without committing

- **Given** a `StockDBBase` instance used inside a `with` block
- **And** only `_query_one` and/or `_query_all` are called (no writes)
- **When** the `with` block exits without exception
- **Then** `commit()` SHALL NOT be invoked
- **And** the connection SHALL still be released normally

#### Scenario: Write operation triggers commit on clean exit

- **Given** a `StockDBBase` instance used inside a `with` block
- **And** `_execute_many` is called at least once
- **When** the `with` block exits without exception
- **Then** `commit()` SHALL be invoked exactly once
- **And** the internal dirty flag SHALL be reset to `False`

#### Scenario: Exception during write triggers rollback as before

- **Given** a `StockDBBase` instance used inside a `with` block
- **When** an exception is raised (regardless of read or write usage)
- **Then** `rollback()` SHALL be invoked
- **And** the dirty flag SHALL be reset to `False`

### Requirement: StockDBBase SHALL track write state via an internal flag

A private boolean attribute `_dirty` SHALL be introduced to track whether any
write operation has been performed during the current connection lifetime.

- `_dirty` MUST be `False` after `__init__` and after each `_release_conn`.
- `_dirty` MUST be set to `True` inside `_execute_many` after the cursor
  executes the SQL statement.
- `_dirty` MUST NOT be modified by `_query_one` or `_query_all`.
