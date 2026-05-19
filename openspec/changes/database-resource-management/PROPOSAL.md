# Proposal: 数据库资源统一管理与生命周期治理

## 1. 问题陈述

当前各工程（stockcompass、datafactory、data-agent、infopublisher）在数据库访问上存在严重的资源管理问题：

### 已识别的反模式

#### A. Compass — 连接泄漏 + 无连接复用（MySQL）

**stockfetch/db_*.py（10+ 文件）**：
- 每个方法调用 `get_conn()` 创建新连接，手动 `conn.close()`
- **无 try/finally 保护**：异常时连接泄漏
- 无连接池，每操作创建/销毁 TCP 连接
- SQL 拼接（无参数化）：`"WHERE stock_code=" + "'" + self.code + "'"` — SQL 注入风险

**scripts/fetch_valuation.py / fetch_financial.py**：
- 同样的 `get_db()` → 手动 `conn.close()` 模式
- `fetch_valuation.fetch_market_pe()` 中：异常在 `conn = get_db()` 后发生但未在 finally 中关闭 → 连接泄漏
- `fetch_individual_batch()` 中：批量 5500+ 只股票，但只有最外层 `conn.close()`，中间异常直接泄漏

**scripts/pipeline.py（DBClient 池化）**：
- `DBClient` 使用 `PooledDB` 连接池（mincached=10, maxconnections=100）
- 但每个 pipeline_db 函数都 `mc = _get_db()` + `try/finally: mc.close()` — 模式正确
- **问题**：`DBClient.__pool` 是类变量，但初始化时用了 `self.__pool` 双重检查锁定（DCL），Python name mangling 导致 `self.__pool` 和 `DBClient.__pool` 不是同一属性
- 当前 MySQL 有 **10 个 Sleep 连接**（ID 48-57），Time=58s，来自 pipeline daemon 的 DBClient 池

#### B. DataFactory — SQLite 连接无上下文管理

**app.py**：
- 60+ 处 `conn = get_db()` + 手动 `conn.close()`
- 多处 return 前未 close（如 line 349 `conn.close()` 在 if 分支内）
- `_track_event()` 中 `conn.close()` 在 except 外 → 事件写入异常时连接泄漏
- SQLite 的 WAL 模式未启用，高并发下可能锁定

#### C. Data-Agent — 相对健康

- 使用 `aiosqlite` + `async with` 上下文管理器 — 正确模式
- 但验证脚本（tools/validation/*.py）全部手动 `sqlite3.connect()` + 手动 close

#### D. Infopublisher — 无数据库

- 不使用任何数据库，数据通过 HTTP API 传递 — 无问题

### 核心问题总结

| 问题 | 严重度 | 影响范围 |
|------|--------|----------|
| MySQL 连接泄漏（无 try/finally） | 🔴 高 | compass stockfetch/、scripts/ |
| 无连接池（stockfetch/） | 🟡 中 | compass 10+ db_*.py |
| SQL 注入（字符串拼接） | 🔴 高 | compass db_bias/db_ma/db_kdj 等 |
| DBClient DCL name mangling bug | 🟡 中 | compass pipeline |
| SQLite 连接泄漏 | 🟡 中 | datafactory app.py 60+ 处 |
| fetch_valuation 连接泄漏 | 🔴 高 | compass scripts/fetch_valuation.py |
| MySQL wait_timeout=8h 过长 | 🟡 中 | 全局 |
| 10 个空闲连接常驻 | 🟢 低 | compass pipeline DBClient 池 |

## 2. 目标

1. **消除连接泄漏**：所有 DB 访问使用 try/finally 或上下文管理器
2. **统一连接池**：MySQL 访问统一走 DBClient 连接池，消除裸 pymysql.connect()
3. **参数化查询**：消除 SQL 字符串拼接
4. **健康检测**：应用层 MySQL 可用性 ping + 自动重连
5. **生命周期可视化**：连接池状态纳入 Factory 监控面板

## 3. 期望行为

### Phase 1: Compass stockfetch/ 统一 DB 访问层
- 创建 `stockfetch/db_base.py` — 基类，封装连接池 + try/finally + 参数化
- 所有 db_*.py（bias, ma, macd, rsi, boll, vr, wr, asi, kdj）继承基类
- 废弃 `get_conn()` + 手动 close 模式

### Phase 2: Compass scripts/ 规范化
- fetch_valuation.py / fetch_financial.py 改用 DBClient 连接池
- 添加 try/finally 保护
- 消除 SQL 拼接

### Phase 3: DBClient 修复
- 修复 DCL name mangling bug
- 添加连接健康检查（ping before use）
- 添加连接池状态查询接口

### Phase 4: DataFactory SQLite 生命周期管理
- 改用 `with get_db() as conn:` 模式
- 启用 WAL 模式
- 修复已知的 close 遗漏

### Phase 5: 监控集成
- MySQL 连接池状态 → Factory 监控 API
- SQLite 锁等待统计 → Factory 监控 API

## 4. 涉及工程

| 工程 | 变更范围 |
|------|----------|
| d8q-intelligentengine-stockcompass | stockfetch/db_*.py, scripts/fetch_*.py, buy/DBClient.py |
| d8q-intelligentengine-datafactory | app.py (60+ 处) |
| d8q-data-agent | 验证脚本规范化（低优先级） |
| d8q-intelligentengine-infopublisher | 无变更 |

## 5. 风险评估

- **风险**：重构 stockfetch/db_*.py 可能影响现有指标计算逻辑
- **缓解**：保持接口不变，只改内部实现；逐文件替换 + 功能验证
- **风险**：SQLite WAL 模式可能影响并发行为
- **缓解**：datafactory 是单进程 gunicorn，WAL 只读优化无副作用
