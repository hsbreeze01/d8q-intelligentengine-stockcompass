# Tasks: 数据库资源统一管理与生命周期治理

## Task 1: 创建 Compass stockfetch 统一 DB 基类
- **状态**: todo
- **文件**: `stockfetch/db_base.py`（新增）
- **描述**: 创建 `StockDBBase` 基类，封装连接池（PooledDB）、上下文管理器、参数化查询方法
- **验收**: 基类可独立导入，包含 `_get_conn()`, `_query_one()`, `_query_all()`, `_execute_many()` 方法

## Task 2: 重构 stockfetch/db_bias.py 使用基类
- **状态**: todo
- **文件**: `stockfetch/db_bias.py`
- **描述**: `BIASDaily` 继承 `StockDBBase`，消除 `get_conn()` + 手动 close + SQL 拼接
- **验收**: 所有方法使用参数化查询，无裸 `pymysql.connect()`，无手动 close

## Task 3: 重构 stockfetch/db_ma.py, db_macd.py, db_rsi.py
- **状态**: todo
- **文件**: `stockfetch/db_ma.py`, `stockfetch/db_macd.py`, `stockfetch/db_rsi.py`
- **描述**: 三个指标类继承 `StockDBBase`，模式与 Task 2 一致
- **验收**: 无裸连接，参数化查询

## Task 4: 重构 stockfetch/db_boll.py, db_vr.py, db_wr.py
- **状态**: todo
- **文件**: `stockfetch/db_boll.py`, `stockfetch/db_vr.py`, `stockfetch/db_wr.py`
- **描述**: 三个指标类继承 `StockDBBase`
- **验收**: 无裸连接，参数化查询

## Task 5: 重构 stockfetch/db_asi.py, db_kdj.py
- **状态**: todo
- **文件**: `stockfetch/db_asi.py`, `stockfetch/db_kdj.py`
- **描述**: 两个指标类继承 `StockDBBase`
- **验收**: 无裸连接，参数化查询

## Task 6: 重构 scripts/fetch_valuation.py 连接管理
- **状态**: todo
- **文件**: `scripts/fetch_valuation.py`
- **描述**: 使用 DBClient 连接池替代裸 pymysql.connect，所有连接操作 try/finally 保护
- **验收**: 无裸连接，所有 get_db() 在 try/finally 中 close

## Task 7: 重构 scripts/fetch_financial.py 连接管理
- **状态**: todo
- **文件**: `scripts/fetch_financial.py`
- **描述**: 同 Task 6 模式
- **验收**: 无裸连接，所有 get_db() 在 try/finally 中 close

## Task 8: 修复 DBClient DCL name mangling bug + 添加健康检查
- **状态**: todo
- **文件**: `buy/DBClient.py`
- **描述**: 修复 `self.__pool` name mangling 导致的双重检查锁定失效；添加 `conn.ping(reconnect=True)`；添加 `pool_status()` 类方法
- **验收**: 连接池正确初始化且只初始化一次；断线自动重连；pool_status() 返回可读状态

## Task 9: DataFactory SQLite 生命周期管理
- **状态**: todo
- **文件**: `datafactory/app.py`
- **描述**: 添加 `get_db_ctx()` 上下文管理器，替换 60+ 处 `conn = get_db()` + 手动 close；启用 WAL 模式
- **验收**: 所有 DB 操作在 `with` 语句中，无手动 close

## Task 10: MySQL 参数调优
- **状态**: todo
- **文件**: MySQL my.cnf
- **描述**: `wait_timeout` 从 28800 → 600；`interactive_timeout` 同步调整
- **验收**: `SHOW VARIABLES LIKE 'wait_timeout'` 返回 600
