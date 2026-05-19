# Spec: BIASDaily Refactor — Inherit StockDBBase

## MODIFIED Requirements

### Requirement: BIASDaily class construction

`BIASDaily` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of
`object`. The constructor SHALL accept a mandatory `code` parameter and forward
optional database keyword arguments (`host`, `port`, `db`, `user`, `passwd`) to
the `StockDBBase.__init__` via `**db_kwargs`.

#### Scenario: Construct with code only (default config)

- **Given** the application config provides default DB connection parameters
- **When** `BIASDaily("600036")` is called
- **Then** the instance SHALL use the shared connection pool initialised from
  `buy/Config.py` defaults

#### Scenario: Construct with explicit DB kwargs

- **Given** a user wants to override connection parameters
- **When** `BIASDaily("600036", host="10.0.0.1", port=3307, user="admin",
  passwd="secret", db="testdb")` is called
- **Then** the instance SHALL forward those parameters to `StockDBBase` and
  the pool SHALL be initialised with the custom parameters

---

### Requirement: db_get_maxdate — parameterised query

`db_get_maxdate()` SHALL query `stock_data_daily` using a parameterised
`SELECT max(date) … WHERE stock_code = %s` statement via `_query_one`. It
MUST NOT build SQL through string concatenation.

#### Scenario: Stock has historical data

- **Given** `stock_data_daily` contains rows for stock code `"600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL return the maximum `date` value as a `datetime.date` (or
  `None` if no rows exist)

#### Scenario: Stock has no data

- **Given** `stock_data_daily` has no rows for the given stock code
- **When** `db_get_maxdate()` is called
- **Then** it SHALL return `None`

---

### Requirement: getData — parameterised query with context manager

`getData()` SHALL query `indicators_bias_daily` using a parameterised `SELECT`
via `_query_all` inside a `with self:` block. It MUST NOT open/close raw
`pymysql` connections. The returned `DataFrame` SHALL use column names derived
from the cursor description (compatible with `DictCursor`).

#### Scenario: Data exists up to a known date

- **Given** `db_get_maxdate()` returns a valid date for the stock
- **When** `getData()` is called
- **Then** it SHALL return a `pd.DataFrame` with all rows from
  `indicators_bias_daily` where `stock_code` matches and `record_time <=
  max_date`

#### Scenario: No prior data (fallback to 2000-01-01)

- **Given** `db_get_maxdate()` returns `None`
- **When** `getData()` is called
- **Then** it SHALL fall back to `"2000-01-01"` as the upper-bound date and
  return a DataFrame (possibly empty)

---

### Requirement: insert — parameterised batch write with context manager

`insert(BIAS, DATETIME)` SHALL iterate over the indicator arrays, validate each
value (skip NaN and values > 9999), and write each valid row using
`_execute_many` with a parameterised `REPLACE INTO` statement inside a
`with self:` block. It MUST NOT build SQL through string concatenation or call
`db_insertsql`.

#### Scenario: Insert valid BIAS records

- **Given** BIAS arrays `[b1, b2, b3]` and `DATETIME` array of matching length
- **When** `insert(BIAS, DATETIME)` is called
- **Then** each valid record (non-NaN, all values ≤ 9999) SHALL be written to
  `indicators_bias_daily` via parameterised `REPLACE INTO`
- **And** the context manager SHALL auto-commit on success

#### Scenario: Skip invalid records

- **Given** some BIAS values are NaN or exceed 9999
- **When** `insert(BIAS, DATETIME)` is called
- **Then** invalid records SHALL be silently skipped without raising

---

## REMOVED Requirements

### Requirement: Raw pymysql connection management

The `get_conn()` and `db_disconnect()` methods SHALL be removed. All database
access SHALL go through `StockDBBase` connection pool and context manager.

#### Scenario: No raw pymysql.connect in BIASDaily

- **Given** the refactored `BIASDaily` source code
- **When** searched for `pymysql.connect`
- **Then** zero occurrences SHALL be found

### Requirement: SQL string concatenation

The `db_insertsql()` method and any inline SQL concatenation SHALL be removed.
All SQL SHALL use parameterised queries (`%s` placeholders).

#### Scenario: No SQL concatenation in BIASDaily

- **Given** the refactored `BIASDaily` source code
- **When** searched for `"\\'" +` or string-concatenated SQL patterns
- **Then** zero occurrences SHALL be found
