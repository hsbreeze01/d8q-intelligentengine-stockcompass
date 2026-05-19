# Spec: 数据库访问统一层（stockfetch & scripts）

> Scope: d8q-intelligentengine-stockcompass 内 stockfetch/ 与 scripts/ 下的所有数据库访问模块

## ADDED Requirements

### Requirement: 统一数据库访问基类

所有 stockfetch/db_*.py 模块 SHALL 通过统一的数据库访问基类获取连接，而非各自调用 `get_conn()` 或 `pymysql.connect()`。

#### Scenario: 基类提供连接池化访问

- **Given** stockfetch 目录下任意 db_*.py 模块需要执行 SQL 查询
- **When** 该模块调用基类提供的查询方法
- **Then** 系统 SHALL 从共享连接池获取连接，而非创建新连接
- **And** 查询完成后连接 SHALL 自动归还连接池

#### Scenario: 基类保证异常时连接归还

- **Given** 一个 db_*.py 模块正在执行 SQL 查询
- **When** 查询过程中抛出任意异常（包括 pymysql.Error、KeyError、ValueError）
- **Then** 连接 SHALL 仍然被归还到连接池或关闭
- **And** 异常 SHALL 正确向上传播，不被吞没

### Requirement: 参数化查询

所有 SQL 查询 MUST 使用参数化占位符（`%s`），禁止通过字符串拼接或 f-string 构造 SQL 语句。

#### Scenario: 查询条件使用参数化

- **Given** 某指标模块需要按 stock_code 查询数据
- **When** 构造 SQL 语句
- **Then** WHERE 子句 SHALL 使用 `WHERE stock_code = %s` 形式
- **And** 参数值 SHALL 通过独立的参数元组传递
- **And** 系统 SHALL NOT 使用 `"WHERE stock_code='" + code + "'"` 等字符串拼接

#### Scenario: 批量操作使用参数化

- **Given** fetch_valuation.py 需要批量插入 5500+ 只股票的估值数据
- **When** 执行 `INSERT` 或 `REPLACE INTO` 操作
- **Then** 每条记录 SHALL 使用 `executemany()` 或参数化的 `execute()`
- **And** SHALL NOT 使用字符串拼接构造 VALUES 子句

### Requirement: 连接生命周期保护

所有数据库访问代码 MUST 使用 `try/finally` 或上下文管理器保证连接释放。

#### Scenario: 单次查询的连接保护

- **Given** stockfetch 中的指标计算函数需要查询数据库
- **When** 函数从基类获取连接并执行查询
- **Then** 无论查询成功或失败，连接 SHALL 在函数返回前被释放

#### Scenario: 批量处理的连接保护

- **Given** fetch_valuation.py 执行批量市场 PE 抓取（5000+ 只股票）
- **When** 中间某只股票数据处理抛出异常
- **Then** 当前连接 SHALL 被正确释放
- **And** 已处理的数据 SHALL 保持提交状态（不回滚整批）

## MODIFIED Requirements

### Requirement: 废弃裸连接获取方式

`get_conn()` 函数（返回原始 pymysql.Connection）MUST NOT 再被 stockfetch/db_*.py 和 scripts/fetch_*.py 调用。

#### Scenario: 旧模式被替代

- **Given** 某个 db_*.py 文件原先使用 `conn = get_conn()` + `conn.close()`
- **When** 该文件被重构后
- **Then** SHALL 使用基类提供的查询方法或上下文管理器
- **And** `get_conn()` 函数 MAY 保留但 SHALL 标记为 `@deprecated`
