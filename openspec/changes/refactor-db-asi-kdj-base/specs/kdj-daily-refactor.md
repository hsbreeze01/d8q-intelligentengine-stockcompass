# Delta Spec: KDJDaily Refactor to StockDBBase

## MODIFIED Requirements

### Requirement: KDJDaily inherits StockDBBase for pooled DB access

The `KDJDaily` class in `stockfetch/db_kdj.py` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of `object`, following the same pattern already established by `BIASDaily`, `RSIDaily`, and other refactored indicator modules.

#### Scenario: Constructor accepts code + optional param + db_kwargs

- **Given** the `KDJDaily` class is imported from `stockfetch.db_kdj`
- **When** a caller constructs `KDJDaily("600036")`
- **Then** the instance SHALL store `self.code = "600036"`, `self.param = "933"` (default), and forward remaining keyword arguments to `super().__init__(**db_kwargs)`
- **And** the class SHALL NOT accept explicit `host`, `port`, `db`, `user`, `passwd` constructor parameters

#### Scenario: Constructor with param="522" selects alternate table

- **Given** the `KDJDaily` class is imported
- **When** a caller constructs `KDJDaily("600036", "522")`
- **Then** `self.param` SHALL be `"522"`
- **And** `insert` and `getData` SHALL target the `indicators_kdj_daily_522` table

#### Scenario: Constructor with custom db kwargs

- **Given** the `KDJDaily` class is imported
- **When** a caller constructs `KDJDaily("600036", **{"host": "10.0.0.1", "port": 3307, "user": "admin", "passwd": "secret", "db": "testdb"})`
- **Then** the keyword arguments SHALL be forwarded to `StockDBBase.__init__`
- **And** no direct `pymysql.connect` call SHALL occur during construction

#### Scenario: db_get_maxdate uses parameterised query

- **Given** a `KDJDaily` instance with `code="600036"`
- **When** `db_get_maxdate()` is called
- **Then** it SHALL execute `SELECT max(date) FROM stock_data_daily WHERE stock_code = %s` with `(self.code,)` as parameters
- **And** it SHALL use `with self:` context manager and `_query_one` helper
- **And** it SHALL NOT use string concatenation to build SQL

#### Scenario: getData returns DataFrame with parameterised query

- **Given** a `KDJDaily` instance with `code="600036"` and default `param="933"`
- **When** `getData()` is called
- **Then** it SHALL return a `pd.DataFrame` of rows from `indicators_kdj_daily` where `stock_code` matches and `record_time <= last_update`
- **And** it SHALL use parameterised `%s` placeholders via `_query_all` helper
- **And** it SHALL fall back to `2000-01-01` when `db_get_maxdate()` returns `None`

#### Scenario: getData with param="522" targets alternate table

- **Given** a `KDJDaily` instance with `code="600036"` and `param="522"`
- **When** `getData()` is called
- **Then** it SHALL query `indicators_kdj_daily_522` table instead of `indicators_kdj_daily`

#### Scenario: insert batch-writes with parameterised REPLACE INTO

- **Given** a `KDJDaily` instance with `code="600036"`
- **When** `insert(KDJ, DATETIME)` is called with funcat KDJ arrays (k, d, j)
- **Then** it SHALL iterate in reverse order over `DATETIME`
- **And** for each valid record (j not NaN), it SHALL execute `REPLACE INTO <table> (stock_code, k, d, j, record_time) VALUES (%s, %s, %s, %s, %s)` with parameterised values
- **And** the target table SHALL be determined by `self.param`: `"522"` → `indicators_kdj_daily_522`, otherwise → `indicators_kdj_daily`
- **And** it SHALL skip records where `j` is NaN
- **And** it SHALL handle `IndexError` silently per existing behavior
- **And** it SHALL use `with self:` context manager so the entire batch commits atomically

#### Scenario: No raw pymysql usage

- **Given** the source code of `KDJDaily`
- **Then** it SHALL NOT contain `pymysql.connect`, `get_conn`, `db_disconnect`, or `db_insertsql` methods
- **And** it SHALL NOT import `pymysql` directly

### Requirement: Backward-compatible public interface

The public interface of `KDJDaily` SHALL remain backward-compatible: `KDJDaily(code)` and `KDJDaily(code, "522")` both construct correctly.

#### Scenario: Existing callers continue to work

- **Given** existing code that calls `KDJDaily(code)` or `KDJDaily(code, "522")` and then `.insert(KDJ(), DATETIME)` or `.getData()`
- **When** the refactored module is used as a drop-in replacement
- **Then** all public methods (`db_get_maxdate`, `getData`, `insert`) SHALL behave identically from the caller's perspective
