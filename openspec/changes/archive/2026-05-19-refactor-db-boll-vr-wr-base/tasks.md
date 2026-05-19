# Tasks: Refactor BOLL / VR / WR to StockDBBase

## 1. Refactor indicator modules

- [x] **1.1 Refactor `stockfetch/db_boll.py` — BOLLDaily to inherit StockDBBase**
  - Rewrite class to inherit `StockDBBase`
  - Constructor: `__init__(self, code, **db_kwargs)` → `super().__init__(**db_kwargs)`
  - `db_get_maxdate()`: `with self:` + `_query_one` with `%s` param
  - `getData()`: `with self:` + `_query_all` with `%s` params
  - `insert(BOLL, DATETIME)`: `with self:` + loop + `_execute_many` with parameterised REPLACE
  - Remove `get_conn()`, `db_disconnect()`, `db_insertsql()`
  - Follow `stockfetch/db_bias.py` pattern exactly

- [x] **1.2 Refactor `stockfetch/db_vr.py` — VRDaily to inherit StockDBBase**
  - Same structural pattern as 1.1
  - Table: `indicators_vr_daily`, columns: `stock_code, vr_1, a_v, b_v, record_time`
  - Preserve `av=100, bv=200` hard-coded defaults in `insert()`
  - Remove `get_conn()`, `db_disconnect()`, `db_insertsql()`

- [x] **1.3 Refactor `stockfetch/db_wr.py` — WRDaily to inherit StockDBBase**
  - Same structural pattern as 1.1
  - Table: `indicators_wr_daily`, columns: `stock_code, wr_1, wr_2, record_time`
  - `WR[0]` → `wr_1`, `WR[1]` → `wr_2`, skip NaN for both
  - Remove `get_conn()`, `db_disconnect()`, `db_insertsql()`

## 2. Verify

- [x] **2.1 Run lint and import sanity check**
  - `ruff check stockfetch/db_boll.py stockfetch/db_vr.py stockfetch/db_wr.py`
  - Verify `python -c "from stockfetch.db_boll import BOLLDaily; from stockfetch.db_vr import VRDaily; from stockfetch.db_wr import WRDaily"` succeeds
