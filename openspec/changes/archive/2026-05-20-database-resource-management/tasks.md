# Tasks: 数据库资源统一管理与生命周期治理

## 1. DBClient 连接池修复与增强

- [ ] **修复 DBClient DCL name mangling bug + 添加 ping 健康检查 + 添加 get_pool_status() 方法**
  - 修复 `buy/DBClient.py` 中 `self.__pool` / `DBClient.__pool` name mangling 不一致问题，改用单下划线 `_pool` 或模块级变量
  - 在连接交给调用方前执行 `connection.ping(reconnect=True)`
  - 新增 `get_pool_status()` 方法返回 `{active, idle, max, last_error, initialized}`
  - 保持现有 `execute/select_one/select_many` 接口不变
  - scope: `buy/DBClient.py`

## 2. stockfetch 数据库访问基类

- [ ] **创建 stockfetch/db_base.py 统一数据库访问基类**
  - 封装从 DBClient 连接池获取连接的逻辑
  - 提供 `query_one(sql, params)` / `query_many(sql, params)` / `execute(sql, params)` 方法
  - 所有方法内部使用 `try/finally` 保证连接释放
  - 强制参数化查询（params 必须是 tuple/list）
  - scope: `stockfetch/db_base.py`（新建）

- [ ] **重构 stockfetch/db_*.py 全部指标模块继承基类（bias/ma/macd/rsi/boll/vr/wr/asi/kdj）**
  - 逐文件将 db_*.py 改为继承 `DbBase`
  - 移除 `get_conn()` 裸连接调用和手动 `conn.close()`
  - 将 SQL 字符串拼接改为 `%s` 参数化占位符
  - 保持对外接口不变（如 `get_bias_data(code, date)` 等函数签名）
  - scope: `stockfetch/db_bias.py`, `db_ma.py`, `db_macd.py`, `db_rsi.py`, `db_boll.py`, `db_vr.py`, `db_wr.py`, `db_asi.py`, `db_kdj.py`

## 3. scripts/ 批量脚本规范化

- [ ] **重构 scripts/fetch_valuation.py 和 fetch_financial.py 使用 DBClient 连接池 + 参数化查询**
  - 替换裸 `pymysql.connect()` 为 `DBClient` 连接池
  - 所有 SQL 使用参数化 `%s` 占位符，消除字符串拼接
  - 批量操作（5500+ 只股票）添加 try/finally 保护，确保单条失败不泄漏连接
  - scope: `scripts/fetch_valuation.py`, `scripts/fetch_financial.py`

## 4. Compass Database 类增强

- [ ] **为 compass/data/database.py 添加自动重连和池状态查询**
  - `__enter__` 中获取连接后执行 `connection.ping(reconnect=True)`
  - `select_one/select_many/execute` 方法添加一次重试逻辑：捕获 `OperationalError` 后重建连接并重试
  - 新增 `get_pool_status()` 类方法，返回连接池健康信息
  - scope: `compass/data/database.py`

## 5. 监控与管理接口

- [ ] **添加 /api/admin/db/pool-status 管理员端点**
  - 在 `compass/api/routes/admin.py` 新增 `GET /api/admin/db/pool-status`
  - 复用 `_is_admin()` 权限校验
  - 聚合 DBClient 和 Database 两个连接池的状态信息
  - 返回 JSON：`{pools: [{name, active, idle, max, initialized, last_error}]}`
  - scope: `compass/api/routes/admin.py`

- [ ] **添加数据库连接健康定时检查任务（可选，低优先级）**
  - 在 `compass/scheduler/tasks.py` 新增每 60 秒执行一次的 `SELECT 1` 健康检查
  - 检查失败时记录 WARNING 日志，不中断主服务
  - scope: `compass/scheduler/tasks.py`
