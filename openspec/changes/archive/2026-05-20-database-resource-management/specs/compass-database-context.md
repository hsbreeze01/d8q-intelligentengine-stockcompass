# Spec: Compass Database 上下文管理规范化

> Scope: d8q-intelligentengine-stockcompass 内 compass/data/database.py 及所有使用 Database 类的路由和服务

## MODIFIED Requirements

### Requirement: Database 类作为上下文管理器

`compass.data/database.py` 中的 `Database` 类 MUST 正确实现 `__enter__` / `__exit__` 协议，保证所有代码路径（包括异常）下连接被释放。

#### Scenario: 正常查询完成后连接释放

- **Given** 路由代码使用 `with Database() as db:` 语法
- **When** 代码块正常执行完毕（无异常）
- **Then** 连接 SHALL 被归还到连接池或关闭
- **And** `db` 对象在 `__exit__` 后 SHALL NOT 持有活跃连接

#### Scenario: 查询异常后连接释放

- **Given** 路由代码使用 `with Database() as db:` 语法
- **When** 代码块内 `db.execute()` 或 `db.select_one()` 抛出 pymysql.Error
- **Then** `__exit__` SHALL 捕获异常并释放连接
- **And** 异常 SHALL 继续向上传播（不被吞没）
- **And** 系统 SHALL NOT 出现连接泄漏

#### Scenario: 嵌套 Database 上下文不互相干扰

- **Given** 一个路由方法内嵌套使用两个 `with Database() as db:` 块
- **When** 内层块执行完毕
- **Then** 外层块的连接 SHALL 保持活跃
- **And** 内层块的连接 SHALL 被释放

## ADDED Requirements

### Requirement: Database 查询方法参数化保证

Database 类提供的所有查询方法（`execute`、`select_one`、`select_many`）SHALL 强制要求参数化查询。

#### Scenario: 无参数调用被安全处理

- **Given** 调用 `db.select_one("SELECT COUNT(*) FROM user")`
- **When** SQL 语句无参数占位符
- **Then** 系统 SHALL 正确执行该查询
- **And** 参数参数默认为空元组

#### Scenario: 带参数调用正确传递

- **Given** 调用 `db.select_one("SELECT * FROM user WHERE id = %s", (uid,))`
- **When** 参数元组包含用户输入
- **Then** pymysql SHALL 使用参数化方式执行
- **And** 系统 SHALL NOT 对参数值做字符串拼接

### Requirement: Database 支持自动重连

当 Database 检测到连接已断开时，SHALL 自动重建连接并重试当前操作。

#### Scenario: 长时间空闲后连接断开

- **Given** 一个 Database 实例的连接因 `wait_timeout` 被服务端关闭
- **When** 调用 `db.select_one()` 或 `db.execute()`
- **Then** 系统 SHALL 检测到连接错误
- **And** SHALL 自动重建连接并重新执行该查询
- **And** 调用方 SHALL NOT 感知到重连过程
