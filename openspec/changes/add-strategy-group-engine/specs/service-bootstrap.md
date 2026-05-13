# Delta Spec: FastAPI Service Bootstrap

## Summary
策略组引擎作为独立 FastAPI 服务运行在 :8090，不修改现有 Compass Flask 服务。

## ADDED Requirements

### REQ-FAS-001: 服务启动与健康检查
系统 SHALL 作为独立 FastAPI 服务运行，监听端口 8090。

#### Scenario: 服务健康检查
- **When** 客户端调用 `GET /health`
- **Then** 系统返回 `{"status": "ok", "service": "strategy-engine"}`，HTTP 200

#### Scenario: 服务启动自动恢复定时任务
- **Given** 数据库中有 3 个 active 策略组，各自有 scan_cron 配置
- **When** FastAPI 服务启动
- **Then** 系统从数据库加载所有 active 策略组，注册对应的 APScheduler 定时任务

#### Scenario: 服务关闭时清理
- **When** 服务收到关闭信号
- **Then** 系统优雅关闭：等待当前扫描完成、关闭数据库连接、停止调度器

### REQ-FAS-002: 数据库连接复用
系统 MUST 复用现有 `compass.data.database.Database` 模块进行数据库操作，保持与 Compass 主服务一致的连接池管理。

#### Scenario: 数据库操作正常
- **Given** MySQL stock_analysis_system 可用
- **When** 服务执行任意数据库查询
- **Then** 使用 `with Database() as db:` 模式，自动管理连接

### REQ-FAS-003: 错误处理
系统 SHALL 对所有 API 端点提供统一的错误响应格式。

#### Scenario: 数据库错误
- **Given** MySQL 连接失败
- **When** 客户端调用任意 API
- **Then** 系统返回 500，body 为 `{"error": "Internal server error"}`，日志记录完整错误信息

#### Scenario: 请求参数格式错误
- **Given** 请求体 JSON 解析失败
- **When** 客户端调用 POST 端点
- **Then** 系统返回 400，body 包含 `{"error": "Invalid JSON"}`

### REQ-FAS-004: 日志规范
系统 SHALL 使用标准 logging 模块，日志命名遵循 `compass.strategy.{module}` 模式。

#### Scenario: 扫描日志
- **Given** 扫描引擎开始执行
- **When** 策略组 1 扫描完成
- **Then** 系统记录 INFO 日志：`[strategy.scanner] strategy_group_id=1 matched=23 total=5512 duration=3.2s`
