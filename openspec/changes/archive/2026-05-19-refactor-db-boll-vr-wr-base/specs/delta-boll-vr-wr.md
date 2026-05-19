# Delta Spec: Refactor BOLL / VR / WR indicator modules to StockDBBase

## MODIFIED Requirements

### Requirement: BOLLDaily database access layer

The `BOLLDaily` class in `stockfetch/db_boll.py` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect` calls.

#### Scenario: Constructor accepts code and optional db_kwargs

- **Given** a stock code string (e.g. `"600036"`)
- **When** `BOLLDaily(code)` is constructed
- **Then** the instance SHALL store `self.code` and forward `**db_kwargs` to `StockDBBase.__init__`
- **And** no individual `host` / `port` / `db` / `user` / `password` attributes SHALL be stored on the instance

#### Scenario: db_get_maxdate uses parameterised query via context manager

- **Given** a `BOLLDaily` instance with a valid stock code
- **When** `db_get_maxdate()` is called
- **Then** it SHALL use `with self:` context manager and `self._query_one(...)` with a `%s` parameter placeholder
- **And** it SHALL return the same result type as before (date or `None`)

#### Scenario: getData returns DataFrame via pooled query

- **Given** a `BOLLDaily` instance
- **When** `getData()` is called
- **Then** it SHALL use `with self:` and `self._query_all(...)` with parameterised query
- **And** the returned `pd.DataFrame` SHALL contain the same columns and rows as before

#### Scenario: insert writes BOLL values via parameterised REPLACE

- **Given** `BOLL` and `DATETIME` arrays from funcat
- **When** `insert(BOLL, DATETIME)` is called
- **Then** it SHALL iterate the arrays in reverse, skip `NaN` values
- **And** use `with self:` context manager with `self._execute_many(...)` using a parameterised `REPLACE INTO indicators_boll_daily (stock_code, upper_v, mid_v, lower_v, record_time) VALUES (%s, %s, %s, %s, %s)`
- **And** commit SHALL be handled automatically by the context manager on exit

---

### Requirement: VRDaily database access layer

The `VRDaily` class in `stockfetch/db_vr.py` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect` calls.

#### Scenario: Constructor accepts code and optional db_kwargs

- **Given** a stock code string
- **When** `VRDaily(code)` is constructed
- **Then** the instance SHALL store `self.code` and forward `**db_kwargs` to `StockDBBase.__init__`
- **And** no individual `host` / `port` / `db` / `user` / `password` attributes SHALL be stored on the instance

#### Scenario: db_get_maxdate uses parameterised query via context manager

- **Given** a `VRDaily` instance with a valid stock code
- **When** `db_get_maxdate()` is called
- **Then** it SHALL use `with self:` and `self._query_one(...)` with a `%s` parameter placeholder
- **And** it SHALL return the same result type as before

#### Scenario: getData returns DataFrame via pooled query

- **Given** a `VRDaily` instance
- **When** `getData()` is called
- **Then** it SHALL use `with self:` and `self._query_all(...)` with parameterised query against `indicators_vr_daily`
- **And** the returned `pd.DataFrame` SHALL contain the same columns and rows as before

#### Scenario: insert writes VR values via parameterised REPLACE

- **Given** `VR` and `DATETIME` arrays from funcat
- **When** `insert(VR, DATETIME)` is called
- **Then** it SHALL iterate in reverse, skip `NaN`
- **And** use `with self:` with `self._execute_many(...)` using a parameterised `REPLACE INTO indicators_vr_daily (stock_code, vr_1, a_v, b_v, record_time) VALUES (%s, %s, %s, %s, %s)`
- **And** the hard-coded `av=100`, `bv=200` values SHALL be preserved as-is

---

### Requirement: WRDaily database access layer

The `WRDaily` class in `stockfetch/db_wr.py` SHALL inherit from `stockfetch.db_base.StockDBBase` instead of constructing raw `pymysql.connect` calls.

#### Scenario: Constructor accepts code and optional db_kwargs

- **Given** a stock code string
- **When** `WRDaily(code)` is constructed
- **Then** the instance SHALL store `self.code` and forward `**db_kwargs` to `StockDBBase.__init__`
- **And** no individual `host` / `port` / `db` / `user` / `password` attributes SHALL be stored on the instance

#### Scenario: db_get_maxdate uses parameterised query via context manager

- **Given** a `WRDaily` instance with a valid stock code
- **When** `db_get_maxdate()` is called
- **Then** it SHALL use `with self:` and `self._query_one(...)` with a `%s` parameter placeholder
- **And** it SHALL return the same result type as before

#### Scenario: getData returns DataFrame via pooled query

- **Given** a `WRDaily` instance
- **When** `getData()` is called
- **Then** it SHALL use `with self:` and `self._query_all(...)` with parameterised query against `indicators_wr_daily`
- **And** the returned `pd.DataFrame` SHALL contain the same columns and rows as before

#### Scenario: insert writes WR values via parameterised REPLACE

- **Given** `WR` and `DATETIME` arrays from funcat
- **When** `insert(WR, DATETIME)` is called
- **Then** it SHALL iterate in reverse, skip `NaN` for both `wr_1` and `wr_2`
- **And** use `with self:` with `self._execute_many(...)` using a parameterised `REPLACE INTO indicators_wr_daily (stock_code, wr_1, wr_2, record_time) VALUES (%s, %s, %s, %s)`
- **And** commit SHALL be handled by the context manager on exit

---

## Compatibility Requirements

### Requirement: Public interface backward compatibility

#### Scenario: Existing callers construct with code-only argument

- **Given** any call site that creates `BOLLDaily("600036")`, `VRDaily("600036")`, or `WRDaily("600036")`
- **When** the refactored module is imported
- **Then** the constructor SHALL accept a positional `code` argument without requiring any `db_kwargs`
- **And** database connection parameters SHALL be resolved automatically via `StockDBBase._resolve_db_params({})` (falls back to `buy/Config.py`)

#### Scenario: Existing callers use db_get_maxdate / getData / insert

- **Given** a refactored `BOLLDaily`, `VRDaily`, or `WRDaily` instance
- **When** `db_get_maxdate()`, `getData()`, or `insert(...)` is called
- **Then** the method signatures and return types SHALL be identical to the pre-refactor versions
