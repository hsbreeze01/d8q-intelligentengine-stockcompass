# Delta Spec: RSIDaily Refactor to StockDBBase

## MODIFIED Requirements

### Requirement: RSIDaily database access layer

The `RSIDaily` class SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect()` connections.

#### Scenario: Constructor accepts stock code, optional param, and optional db kwargs
- **Given** a stock code string (e.g. `"600036"`) and optional param string (default `"61224"`)
- **When** `RSIDaily(code, param="61224", **db_kwargs)` is constructed
- **Then** the instance SHALL store `self.code` and `self.param`, and call `super().__init__(**db_kwargs)` to initialise the shared connection pool
- **And** the constructor SHALL NOT accept individual `host`, `port`, `db`, `user`, `passwd` keyword arguments

#### Scenario: No raw connection management methods
- **Given** a `RSIDaily` instance
- **Then** the class SHALL NOT expose `get_conn()` or `db_disconnect()` methods
- **And** all database operations SHALL use `with self:` context manager

#### Scenario: db_get_maxdate returns max date with parameterized query
- **Given** a `RSIDaily` instance with code `"600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL execute `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` via `_query_one` with `(self.code,)` params
- **And** return the max date value or `None`

#### Scenario: getData returns DataFrame with parameterized query
- **Given** a `RSIDaily` instance with code `"600036"`
- **When** `getData()` is called
- **Then** it SHALL determine the target table based on `self.param`: if `param == "3612"` use `indicators_rsi_daily_3612`, else use `indicators_rsi_daily`
- **And** execute `SELECT * FROM <table> WHERE stock_code = %s AND record_time <= %s` via `_query_all`
- **And** return a `pd.DataFrame` with column names from the cursor description

#### Scenario: insert batch-writes RSI values with parameterized query
- **Given** a `RSIDaily` instance and funcat RSI tuple (r1, r2, r3) + DATETIME array
- **When** `insert(RSI, DATETIME)` is called
- **Then** it SHALL determine the target table based on `self.param`: if `param == "3612"` use `indicators_rsi_daily_3612`, else use `indicators_rsi_daily`
- **And** iterate in reverse, skip NaN values, and execute `REPLACE INTO <table> (stock_code, rsi_1, rsi_2, rsi_3, record_time) VALUES (%s, %s, %s, %s, %s)` via `_execute_many` with parameterized params
- **And** the `db_insertsql()` method SHALL be removed

## REMOVED Requirements

### Requirement: SQL string concatenation in RSIDaily
- `db_insertsql()` SHALL be removed — replaced by parameterized `_execute_many`
- `get_conn()` SHALL be removed — replaced by `with self:` context manager
- `db_disconnect()` SHALL be removed — connection pool handles lifecycle
