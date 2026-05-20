# Design: 数据库资源统一管理与生命周期治理

## 架构决策

### ADR-1: MySQL 连接池统一使用 DBClient（PooledDB）

**决策**：所有 MySQL 访问统一走 `buy/DBClient.py` 的 `PooledDB` 连接池，消除裸 `pymysql.connect()` 调用。

**理由**：
- DBClient 已封装 `PooledDB`（mincached=10, maxconnections=100），是项目现有的标准池化方案
- compass/data/database.py 的 `Database` 类已有 `with Database() as db:` 上下文管理模式
- 新增统一不需引入新依赖，复用现有 `dbutils.PooledDB`
- stockfetch/db_*.py 的裸连接模式是历史遗留，统一到池化方案改动最小

**替代方案否决**：
- SQLAlchemy Session — 引入新 ORM 依赖，与现有裸 SQL 风格冲突
- 每个模块自行连接池 — 碎片化管理，无法监控全局

### ADR-2: stockfetch 模块改造策略 — 基类继承 + 接口不变

**决策**：创建 `stockfetch/db_base.py` 基类，封装连接获取/释放/参数化，db_*.py 继承基类，保持对外接口不变。

**理由**：
- stockfetch/db_*.py 有 10+ 个文件（bias, ma, macd, rsi, boll, vr, wr, asi, kdj），逐一重写成本高
- 基类继承模式可一次性解决连接泄漏 + SQL 注入 + 无连接池三个问题
- 对外接口不变（如 `get_bias_data(code, date)`），不影响下游调用方

### ADR-3: Database 类增强 — 自动重连 + 健康检查

**决策**：在 `compass/data/database.py` 的 `Database` 类中添加 `connection.ping(reconnect=True)` 和重试逻辑。

**理由**：
- MySQL `wait_timeout` 默认 8 小时，长空闲后连接失效
- `pymysql.Connection.ping(reconnect=True)` 是官方推荐的连接活性检测方式
- 一次 ping 的性能开销可忽略（< 1ms）

### ADR-4: 监控接口复用现有 admin 路由

**决策**：连接池状态查询挂在 `/api/admin/db/pool-status`，复用现有 admin 权限校验 `_is_admin()`。

**理由**：
- admin 路由已有权限校验和日志基础设施
- 不需要新增 Blueprint 或中间件

## 数据流

### 连接获取流程（改造后）

```
调用方代码
  │
  ▼
with Database() as db:          # compass 模块
  └─ Database.__enter__()
       └─ DBClient 连接池.connection()
            └─ PooledDB 连接池 → 获取或创建连接
                 └─ connection.ping(reconnect=True)  ← 新增：健康检查
  
  db.select_one(sql, params)    # 参数化查询
  db.execute(sql, params)

  Database.__exit__()           # 自动归还连接
```

### stockfetch 调用流程（改造后）

```
指标模块 (db_bias.py 等)
  │
  ▼
class DbBias(DbBase):           # 新增：继承基类
  def get_data(code, date):
    return self.query_one(sql, params)   # 基类方法，自动管理连接
  
  DbBase.query_one()
    └─ with self._get_connection() as conn:
         └─ conn → 从 DBClient 池获取
              └─ 执行查询 → 返回结果
              └─ finally: 归还连接
```

### 监控数据流

```
GET /api/admin/db/pool-status
  │
  ▼
admin._is_admin() 鉴权
  │
  ▼
DBClient.get_pool_status()      # 新增方法
  └─ 返回 {active, idle, max, last_error}
  │
  ▼
Database.get_pool_status()      # 新增方法
  └─ 返回 {active, idle, max, initialized}
  │
  ▼
合并响应 → JSON 200
```

## 需要新增/修改的文件

### 新增文件

| 文件 | 说明 |
|------|------|
| `stockfetch/db_base.py` | 数据库访问基类，封装连接池获取、参数化查询、try/finally 保护 |

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `buy/DBClient.py` | 修复 DCL name mangling bug；新增 `get_pool_status()` 方法；获取连接时添加 `ping(reconnect=True)` |
| `compass/data/database.py` | `__enter__` 中添加 `ping` 健康检查；添加重试逻辑（最多 1 次）；新增 `get_pool_status()` 类方法 |
| `compass/api/routes/admin.py` | 新增 `GET /api/admin/db/pool-status` 端点 |
| `stockfetch/db_bias.py` | 继承 `DbBase`，移除裸连接代码，改用基类查询方法 |
| `stockfetch/db_ma.py` | 同上 |
| `stockfetch/db_macd.py` | 同上 |
| `stockfetch/db_rsi.py` | 同上 |
| `stockfetch/db_boll.py` | 同上 |
| `stockfetch/db_vr.py` | 同上 |
| `stockfetch/db_wr.py` | 同上 |
| `stockfetch/db_asi.py` | 同上 |
| `stockfetch/db_kdj.py` | 同上 |
| `scripts/fetch_valuation.py` | 改用 DBClient 连接池 + try/finally 保护 + 参数化查询 |
| `scripts/fetch_financial.py` | 同上 |
| `compass/scheduler/tasks.py` | 新增定时连接池健康检查任务（可选） |

### 不修改的文件

| 文件 | 原因 |
|------|------|
| `compass/api/routes/*.py`（非 admin） | 已使用 `with Database() as db:` 模式，无需改动 |
| `compass/services/*.py` | 通过 Database 类访问数据库，间接受益于底层增强 |
| `buy/Config.py` | 数据库配置不变 |

## 兼容性说明

- **接口兼容**：所有改动保持对外接口不变。stockfetch 的 `get_*_data()` 函数签名不变；Database 的 `select_one/select_many/execute` 签名不变。
- **行为变化**：连接不再泄漏（正面变化）；查询因使用连接池而复用连接（性能提升）。
- **配置不变**：MySQL 连接参数（host/port/user/password/database）保持从 `buy/Config.py` 读取。

## 跨工程说明

本 change 仅覆盖 **d8q-intelligentengine-stockcompass** 工程。以下工程的改动需在各自项目中另行处理：

- **d8q-intelligentengine-datafactory**：app.py 的 60+ 处 SQLite 连接泄漏（不在本项目范围内）
- **d8q-data-agent**：验证脚本规范化（低优先级，不在本项目范围内）
