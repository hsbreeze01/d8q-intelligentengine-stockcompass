# Delta Spec: MADaily Refactor to StockDBBase

## MODIFIED Requirements

### Requirement: MADaily database access layer

The `MADaily` class SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect()` connections.

#### Scenario: Constructor accepts stock code and optional db kwargs
- **Given** a stock code string (e.g. `"600036"`)
- **When** `MADaily(code, **db_kwargs)` is constructed
- **Then** the instance SHALL store `self.code` and call `super().__init__(**db_kwargs)` to initialise the shared connection pool
- **And** the constructor SHALL NOT accept individual `host`, `port`, `db`, `user`, `passwd` keyword arguments

#### Scenario: No raw connection management methods
- **Given** a `MADaily` instance
- **Then** the class SHALL NOT expose `get_conn()` or `db_disconnect()` methods
- **And** all database operations SHALL use `with self:` context manager

#### Scenario: db_get_maxdate returns max date with parameterized query
- **Given** a `MADaily` instance with code `"600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL execute `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` via `_query_one` with `(self.code,)` params
- **And** return the max date value or `None`

#### Scenario: getData returns DataFrame with parameterized query
- **Given** a `MADaily` instance with code `"600036"`
- **When** `getData()` is called
- **Then** it SHALL execute `SELECT * FROM indicators_ma_daily WHERE stock_code = %s AND record_time <= %s` via `_query_all`
- **And** return a `pd.DataFrame` with column names from the cursor description

#### Scenario: insert batch-writes MA values with parameterized query
- **Given** a `MADaily` instance and funcat MA series arrays + DATETIME array
- **When** `insert(ma5, ma10, ma20, ma30, ma60, DATETIME)` is called
- **Then** it SHALL iterate in reverse, skip NaN / > 9999 values, and execute `REPLACE INTO indicators_ma_daily (stock_code, ma5, ma10, ma20, ma30, ma60, record_time) VALUES (%s, %s, %s, %s, %s, %s, %s)` via `_execute_many` with parameterized params
- **And** the `db_insertsql()` method SHALL be removed

## REMOVED Requirements

### Requirement: SQL string concatenation in MADaily
- `db_insertsql()` SHALL be removed — replaced by parameterized `_execute_many`
- `get_conn()` SHALL be removed — replaced by `with self:` context manager
- `db_disconnect()` SHALL be removed — connection pool handles lifecycle
