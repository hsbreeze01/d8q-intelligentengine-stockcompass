# Spec: DBClient 连接池修复与增强

> Scope: d8q-intelligentengine-stockcompass 内 buy/DBClient.py

## MODIFIED Requirements

### Requirement: DBClient 连接池初始化线程安全

DBClient 的连接池初始化 MUST 使用正确的类属性引用，消除 Python name mangling 导致的双重检查锁定（DCL）bug。

#### Scenario: 多线程并发获取首个连接

- **Given** 多个线程同时首次调用 `DBClient()` 实例化
- **When** 并发触发连接池初始化
- **Then** SHALL 只创建一个 `PooledDB` 实例
- **And** 所有线程 SHALL 共享同一连接池
- **And** SHALL NOT 因为 name mangling 导致 `DBClient.__pool` 和实例的 `self.__pool` 指向不同对象

#### Scenario: 单线程正常获取连接

- **Given** 连接池已初始化
- **When** 调用 `DBClient()._get_conn()` 获取连接
- **Then** SHALL 从现有池中返回空闲连接
- **And** 连接 SHALL 处于可用状态

### Requirement: 连接健康检查

DBClient 连接池 MUST 在将连接交给调用方之前验证连接的可用性。

#### Scenario: 空闲连接因超时断开时自动重连

- **Given** 连接池中有一个空闲连接，其服务端已因 `wait_timeout` 关闭
- **When** 调用方从池中获取该连接
- **Then** 系统 SHALL 检测到连接不可用
- **And** SHALL 丢弃该连接并创建新连接返回
- **And** 调用方 SHALL NOT 收到 "MySQL server has gone away" 异常

#### Scenario: 网络瞬断后自动恢复

- **Given** 应用与 MySQL 之间的网络发生短暂中断后恢复
- **When** 下一次从连接池获取连接
- **Then** 系统 SHALL 执行 `connection.ping(reconnect=True)` 或等效检查
- **And** 如果连接已断开，SHALL 自动重建

## ADDED Requirements

### Requirement: 连接池状态查询接口

DBClient SHALL 提供查询当前连接池状态的方法，供监控和调试使用。

#### Scenario: 查询连接池健康状态

- **Given** DBClient 连接池已初始化并运行
- **When** 调用连接池状态查询方法
- **Then** SHALL 返回至少以下信息：
  - 当前活跃连接数
  - 当前空闲连接数
  - 最大连接数配置
  - 最近一次错误信息（如有）

#### Scenario: 连接池未初始化时查询状态

- **Given** DBClient 尚未初始化连接池
- **When** 调用连接池状态查询方法
- **Then** SHALL 返回表示"未初始化"的状态信息
- **And** SHALL NOT 抛出异常
