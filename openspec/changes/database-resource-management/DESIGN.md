# Design: 数据库资源统一管理与生命周期治理

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                应用层                              │
├──────────────┬──────────────┬───────────────────┤
│  Compass     │  DataFactory │  Data-Agent       │
│  stockfetch/ │  app.py      │  storage.py       │
│  scripts/    │              │  (aiosqlite ✅)   │
│  pipeline/   │              │                   │
├──────────────┴──────────────┴───────────────────┤
│           统一 DB 访问层                           │
├─────────────────────┬───────────────────────────┤
│  MySQL (DBClient)   │  SQLite (context mgr)     │
│  - 连接池            │  - WAL 模式                │
│  - 健康检查          │  - get_db_ctx()            │
│  - 状态查询          │  - 自动 close              │
├─────────────────────┴───────────────────────────┤
│              数据库实例                            │
├─────────────────────┬───────────────────────────┤
│  MySQL 3306         │  SQLite file               │
│  max_conn=151       │  factory.db / *.db         │
│  wait_timeout=28800 │                            │
└─────────────────────┴───────────────────────────┘
```

## 实施设计

### Phase 1: Compass stockfetch 统一 DB 访问基类

**新文件**: `stockfetch/db_base.py`

```python
"""统一的数据库访问基类 — 连接池 + 上下文管理 + 参数化查询"""
import pymysql
from contextlib import contextmanager
from buy.Config import taskConfig as config
from dbutils.pooled_db import PooledDB

class StockDBBase:
    """stockfetch 模块统一 DB 基类"""
    _pool = None  # 类级别连接池，所有子类共享
    
    @classmethod
    def _get_pool(cls):
        if cls._pool is None:
            cfg = config.getDBconnection()
            cls._pool = PooledDB(
                pymysql,
                mincached=2, maxcached=10, maxconnections=20,
                host=cfg['host'], port=cfg['port'],
                user=cfg['user'], passwd=cfg['password'],
                db=cfg['database'], charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
        return cls._pool
    
    @contextmanager
    def _get_conn(self):
        """上下文管理器 — 自动关闭连接"""
        pool = self._get_pool()
        conn = pool.connection()
        try:
            yield conn
        finally:
            conn.close()
    
    def _query_one(self, sql, params=()):
        """查询单条，返回 dict"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
    
    def _query_all(self, sql, params=()):
        """查询多条，返回 list[dict]"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
    
    def _execute_many(self, sql_params_list):
        """批量执行多条 SQL，自动 commit"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for sql, params in sql_params_list:
                    cur.execute(sql, params)
                conn.commit()
```

**子类改造**（以 db_bias.py 为例）：

```python
# Before:
class BIASDaily(object):
    def get_conn(self):
        conn = pymysql.connect(...)  # 每次新建
        return conn
    
    def db_get_maxdate(self):
        conn = self.get_conn()
        cur = conn.cursor()
        cur.execute("select max(date) from stock_data_daily where stock_code='" + self.code + "';")
        ans = cur.fetchall()
        conn.commit()
        conn.close()  # 异常时泄漏
        return ans[0][0] if ans else None

# After:
from stockfetch.db_base import StockDBBase

class BIASDaily(StockDBBase):
    def __init__(self, code):
        self.code = code
    
    def db_get_maxdate(self):
        result = self._query_one(
            "SELECT MAX(date) AS max_date FROM stock_data_daily WHERE stock_code=%s",
            (self.code,)
        )
        return result['max_date'] if result and result['max_date'] else None
```

### Phase 2: Compass scripts 规范化

**fetch_valuation.py / fetch_financial.py**：
- 替换 `pymysql.connect()` → 使用 DBClient 连接池
- 所有 `conn = get_db()` 包裹在 try/finally
- 批量操作使用同一连接，中间 commit

### Phase 3: DBClient 修复

**DCL Bug 修复**：
```python
# Before (bug: self.__pool → _DBClient__pool via name mangling, 
#         not the same as DBClient.__pool at class level)
if not self.__pool:
    DBClient.lock.acquire()
    if not self.__pool:  # ← 检查的是实例的 _DBClient__pool
        self.__class__.__pool = PooledDB(...)  # ← 设置的是类的 _DBClient__pool
    DBClient.lock.release()

# After:
if DBClient._DBClient__pool is None:
    with DBClient.lock:
        if DBClient._DBClient__pool is None:
            DBClient._DBClient__pool = PooledDB(...)
```

**添加健康检查**：
```python
def __get_conn(self):
    conn = self.__pool.connection()
    # Ping 检测连接存活
    conn.ping(reconnect=True)
    self._cursor = conn.cursor()
```

**添加状态查询**：
```python
@classmethod
def pool_status(cls):
    """返回连接池状态"""
    pool = cls._DBClient__pool
    if pool is None:
        return {"status": "not_initialized"}
    return {
        "status": "active",
        "mincached": pool._mincached,
        "maxconnections": pool._maxconnections,
        "connection_count": cls._connection_count
    }
```

### Phase 4: DataFactory SQLite 生命周期

**新辅助函数**：
```python
@contextmanager
def get_db_ctx():
    """上下文管理器版本的 get_db — 自动 close"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式（只在首次）
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()
```

**逐步替换**：将 `conn = get_db()` → `with get_db_ctx() as conn:`

### Phase 5: MySQL 参数调优

```sql
-- 当前值
wait_timeout = 28800 (8h)  -- 太长，空闲连接占用
interactive_timeout = 28800

-- 建议值
wait_timeout = 600 (10min)  -- 空闲连接 10 分钟回收
interactive_timeout = 600
max_connections = 151  -- 保持，当前峰值 ~10
```

## 文件变更清单

| 文件 | 变更类型 | 描述 |
|------|----------|------|
| stockfetch/db_base.py | 新增 | 统一 DB 访问基类 |
| stockfetch/db_bias.py | 重构 | 继承 StockDBBase |
| stockfetch/db_ma.py | 重构 | 继承 StockDBBase |
| stockfetch/db_macd.py | 重构 | 继承 StockDBBase |
| stockfetch/db_rsi.py | 重构 | 继承 StockDBBase |
| stockfetch/db_boll.py | 重构 | 继承 StockDBBase |
| stockfetch/db_vr.py | 重构 | 继承 StockDBBase |
| stockfetch/db_wr.py | 重构 | 继承 StockDBBase |
| stockfetch/db_asi.py | 重构 | 继承 StockDBBase |
| stockfetch/db_kdj.py | 重构 | 继承 StockDBBase |
| scripts/fetch_valuation.py | 重构 | 使用 DBClient + try/finally |
| scripts/fetch_financial.py | 重构 | 使用 DBClient + try/finally |
| buy/DBClient.py | 修复 | DCL bug + ping + pool_status |
| datafactory/app.py | 重构 | get_db_ctx 上下文管理器 |
| MySQL 配置 | 调优 | wait_timeout → 600s |
