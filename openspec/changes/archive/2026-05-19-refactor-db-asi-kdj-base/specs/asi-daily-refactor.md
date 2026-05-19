# Delta Spec: ASIDaily Refactor to StockDBBase

## MODIFIED Requirements

### Requirement: ASIDaily inherits StockDBBase for pooled DB access

The `ASIDaily` class in `stockfetch/db_asi.py` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of `object`, following the same pattern already established by `BIASDaily`, `RSIDaily`, `MACDDaily`, and other refactored indicator modules.

#### Scenario: Constructor accepts code + optional db_kwargs

- **Given** the `ASIDaily` class is imported from `stockfetch.db_asi`
- **When** a caller constructs `ASIDaily("600036")`
- **Then** the instance SHALL store `self.code = "600036"` and forward all remaining keyword arguments to `super().__init__(**db_kwargs)`
- **And** the class SHALL NOT accept explicit `host`, `port`, `db`, `user`, `passwd` constructor parameters

#### Scenario: Constructor with custom db kwargs

- **Given** the `ASIDaily` class is imported
- **When** a caller constructs `ASIDaily("600036", host="10.0.0.1", port=3307, user="admin", passwd="secret", db="testdb")`
- **Then** the keyword arguments SHALL be forwarded to `StockDBBase.__init__`
- **And** no direct `pymysql.connect` call SHALL occur during construction

#### Scenario: db_get_maxdate uses parameterised query

- **Given** an `ASIDaily` instance with `code="600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL execute `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` with `(self.code,)` as parameters
- **And** it SHALL use `with self:` context manager and `_query_one` helper
- **And** it SHALL NOT use string concatenation to build SQL

#### Scenario: getData returns DataFrame with parameterised query

- **Given** an `ASIDaily` instance with `code="600036"`
- **When** `getData()` is called
- **Then** it SHALL return a `pd.DataFrame` of rows from `indicators_asi_daily` where `stock_code` matches and `record_time <= last_update`
- **And** it SHALL use parameterised `%s` placeholders via `_query_all` helper
- **And** it SHALL fall back to `2000-01-01` when `db_get_maxdate()` returns `None`

#### Scenario: insert batch-writes with parameterised REPLACE INTO

- **Given** an `ASIDaily` instance with `code="600036"`
- **When** `insert(ASI, DATETIME)` is called with funcat arrays
- **Then** it SHALL iterate in reverse order over `DATETIME`
- **And** for each valid record (not NaN, value within ±999999), it SHALL execute `REPLACE INTO indicators_asi_daily (stock_code, asi, asi_t, record_time) VALUES (%s, %s, %s, %s)` with parameterised values
- **And** it SHALL skip records where `asi` or `asi_t` is NaN or outside ±999999
- **And** it SHALL handle `IndexError` silently per existing behavior
- **And** it SHALL use `with self:` context manager so the entire batch commits atomically

#### Scenario: No raw pymysql usage

- **Given** the source code of `ASIDaily`
- **Then** it SHALL NOT contain `pymysql.connect`, `get_conn`, `db_disconnect`, or `db_insertsql` methods
- **And** it SHALL NOT import `pymysql` directly

### Requirement: Backward-compatible public interface

The public interface of `ASIDaily` SHALL remain backward-compatible: `ASIDaily(code)` constructs correctly without any additional arguments.

#### Scenario: Existing callers continue to work

- **Given** existing code that calls `ASIDaily(code)` and then `.insert(ASI(), DATETIME)` or `.getData()`
- **When** the refactored module is used as a drop-in replacement
- **Then** all public methods (`db_get_maxdate`, `getData`, `insert`) SHALL behave identically from the caller's perspective
