# Delta Spec: Connection Management for fetch_valuation

## MODIFIED Requirements

### Requirement: Database Connection Acquisition

`scripts/fetch_valuation.py` SHALL acquire database connections through the existing `DBClient` connection pool (`buy.DBClient`) instead of creating raw `pymysql.connect()` calls with hardcoded credentials.

#### Scenario: get_db returns pooled connection

- **Given** the script is invoked
- **When** `get_db()` is called
- **Then** it SHALL return a `DBClient()` instance obtained from the `buy.DBClient` module
- **And** no raw `pymysql.connect()` call SHALL exist in the file

#### Scenario: no hardcoded database credentials

- **Given** the source code of `fetch_valuation.py`
- **When** inspected for database connection strings
- **Then** no hardcoded host / user / password / database values SHALL be present
- **And** all connection configuration SHALL be sourced from the existing `buy.Config.taskConfig` YAML pipeline

---

### Requirement: Connection Lifecycle Safety

Every database connection acquired by `fetch_valuation.py` SHALL be released in a `finally` block, guaranteeing closure even when exceptions occur.

#### Scenario: create_table releases connection on success

- **Given** the `create_table()` function is called
- **When** DDL statements complete without error
- **Then** the connection SHALL be closed via `conn.close()` in a `finally` block

#### Scenario: create_table releases connection on exception

- **Given** the `create_table()` function is called
- **When** a DDL statement raises an exception
- **Then** the connection SHALL still be closed via `conn.close()` in a `finally` block

#### Scenario: fetch_market_pe releases connection on exception

- **Given** `fetch_market_pe()` has acquired a connection
- **When** an exception occurs during data insertion
- **Then** the connection SHALL be closed via `finally`
- **And** the exception SHALL be logged

#### Scenario: fetch_market_pb releases connection on exception

- **Given** `fetch_market_pb()` has acquired a connection
- **When** an exception occurs during data insertion
- **Then** the connection SHALL be closed via `finally`
- **And** the exception SHALL be logged

#### Scenario: fetch_individual_batch releases connection on exception

- **Given** `fetch_individual_batch()` has acquired a single connection for the entire batch
- **When** an exception occurs at any point during batch processing
- **Then** the connection SHALL be closed via `finally`
- **And** any partially committed batch data SHALL remain committed (no rollback of already-committed batches)

---

### Requirement: SQL Parameterization

All SQL `execute()` calls in `fetch_valuation.py` SHALL use parameterized queries (`%s` placeholders) and never use Python string formatting (f-string / `.format()`) to compose SQL.

#### Scenario: all execute calls use parameterized queries

- **Given** the source code of `fetch_valuation.py`
- **When** all `cursor.execute()` or `db.execute()` calls are inspected
- **Then** every call SHALL pass values as a parameter tuple
- **And** no SQL string SHALL contain interpolated Python values

> **Note:** The current codebase already uses `%s` parameterized queries. This requirement formalizes the existing behavior as a SHALL constraint to prevent regression.

---

### Requirement: Preserved Public Interface

The refactoring SHALL NOT change the public interface or observable behavior of the script.

#### Scenario: main function entry point unchanged

- **Given** the script is executed as `__main__`
- **When** `main()` runs
- **Then** it SHALL call `create_table()`, `fetch_market_pe()`, and `fetch_market_pb()` in the same order
- **And** the same log messages SHALL be produced for success and error cases

#### Scenario: fetch_individual_batch callable independently

- **Given** `fetch_individual_batch()` is called
- **When** it completes successfully
- **Then** it SHALL insert rows into `stock_valuation_daily` with the same columns and values as before the refactoring
