# Delta Spec: Connection Management

## MODIFIED Requirements

### Requirement: Database Connection via Connection Pool

`scripts/fetch_financial.py` SHALL acquire all database connections through the
existing `DBClient` connection pool (`buy.DBClient`) instead of creating raw
`pymysql.connect()` instances.

#### Scenario: Replace raw pymysql.connect with DBClient pool

- **Given** `scripts/fetch_financial.py` is executed
- **When** any function needs a database connection
- **Then** it SHALL obtain the connection via `DBClient()` from `buy.DBClient`
- **And** it SHALL NOT import or call `pymysql.connect` directly
- **And** database credentials SHALL be read from the existing YAML config
  (`buy/config/config_*.yaml`) through `DBClient`'s `taskConfig`

---

### Requirement: Guaranteed Connection Release

Every database connection acquired by `scripts/fetch_financial.py` MUST be
released back to the pool regardless of success or failure.

#### Scenario: Connection released on success

- **Given** `store_profit` or `store_balance` completes without error
- **When** all rows have been inserted/updated and committed
- **Then** the connection SHALL be closed (`conn.close()`)

#### Scenario: Connection released on exception

- **Given** an exception occurs after `conn = DBClient()` but before
  `conn.close()`
- **When** the exception propagates
- **Then** the `finally` block SHALL still call `conn.close()`
- **And** no connection SHALL remain checked out from the pool

#### Scenario: main() query connection lifecycle

- **Given** `main()` queries `stock_basic` for the stock list
- **When** the query completes (success or failure)
- **Then** the connection SHALL be released via `try/finally`

---

### Requirement: Parameterized Queries

All SQL statements executed by `scripts/fetch_financial.py` SHALL use `%s`
parameterized queries.

#### Scenario: No string interpolation in SQL

- **Given** any SQL INSERT, UPDATE, or SELECT in `fetch_financial.py`
- **When** variable values are passed
- **Then** they SHALL be passed as separate parameters using `%s` placeholders
- **And** no f-string or string concatenation SHALL be used to build SQL values
