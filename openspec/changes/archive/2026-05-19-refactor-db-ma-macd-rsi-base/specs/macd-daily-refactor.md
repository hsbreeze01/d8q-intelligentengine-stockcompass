# Delta Spec: MACDDaily Refactor to StockDBBase

## MODIFIED Requirements

### Requirement: MACDDaily database access layer

The `MACDDaily` class SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect()` connections.

#### Scenario: Constructor accepts stock code and optional db kwargs
- **Given** a stock code string (e.g. `"600036"`)
- **When** `MACDDaily(code, **db_kwargs)` is constructed
- **Then** the instance SHALL store `self.code` and call `super().__init__(**db_kwargs)` to initialise the shared connection pool
- **And** the constructor SHALL NOT accept individual `host`, `port`, `db`, `user`, `passwd` keyword arguments

#### Scenario: No raw connection management methods
- **Given** a `MACDDaily` instance
- **Then** the class SHALL NOT expose `get_conn()` or `db_disconnect()` methods
- **And** all database operations SHALL use `with self:` context manager

#### Scenario: db_get_maxdate returns max date with parameterized query
- **Given** a `MACDDaily` instance with code `"600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL execute `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` via `_query_one` with `(self.code,)` params
- **And** return the max date value or `None`

#### Scenario: getData returns DataFrame with parameterized query
- **Given** a `MACDDaily` instance with code `"600036"`
- **When** `getData()` is called
- **Then** it SHALL execute `SELECT * FROM indicators_macd_daily WHERE stock_code = %s AND record_time <= %s` via `_query_all`
- **And** return a `pd.DataFrame` with column names from the cursor description

#### Scenario: insert batch-writes MACD values with parameterized query
- **Given** a `MACDDaily` instance and funcat MACD tuple (macd, diff, dea) + DATETIME array
- **When** `insert(MACD, DATETIME)` is called
- **Then** it SHALL iterate in reverse, skip NaN values, and execute `REPLACE INTO indicators_macd_daily (stock_code, macd, diff, dea, record_time) VALUES (%s, %s, %s, %s, %s)` via `_execute_many` with parameterized params
- **And** the `db_insertsql()` method SHALL be removed

## REMOVED Requirements

### Requirement: SQL string concatenation in MACDDaily
- `db_insertsql()` SHALL be removed — replaced by parameterized `_execute_many`
- `get_conn()` SHALL be removed — replaced by `with self:` context manager
- `db_disconnect()` SHALL be removed — connection pool handles lifecycle
