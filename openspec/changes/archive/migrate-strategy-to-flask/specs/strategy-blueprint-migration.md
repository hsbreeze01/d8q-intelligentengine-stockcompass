# Delta Spec: 策略组引擎 FastAPI → Flask Blueprint 迁移

## MODIFIED Requirements

### Requirement: 策略组引擎 Web 层框架

策略组引擎的 HTTP 接口 SHALL 从独立 FastAPI 服务迁移为 Compass Flask 应用的 Blueprint 模块。

#### Scenario: Flask 应用启动时包含策略组路由

- **Given** Compass Flask 应用通过 `create_app()` 创建
- **When** 应用初始化完成
- **Then** 应用 SHALL 注册以下 4 个 Blueprint：
  - `strategy_groups`（prefix `/api/strategy`）
  - `strategy_signals`（prefix `/api`）
  - `strategy_events`（prefix `/api`）
  - `strategy_industry_sync`（prefix `/api`）
- **And** 所有 16 个策略组端点 SHALL 可通过 Flask 路由访问

#### Scenario: 策略组 CRUD 端点保持相同 URL 和行为

- **Given** 策略组引擎已迁移到 Flask
- **When** 客户端请求以下端点
  - `POST /api/strategy/groups` — 创建策略组（返回 201）
  - `PUT /api/strategy/groups/<id>` — 更新策略组
  - `DELETE /api/strategy/groups/<id>` — 软删除策略组
  - `PATCH /api/strategy/groups/<id>/status` — 切换启停状态
  - `GET /api/strategy/groups` — 列表查询（可选 `?status=` 过滤）
  - `GET /api/strategy/groups/<id>` — 获取详情
- **Then** 每个 endpoint SHALL 返回与原 FastAPI 版本相同的 JSON 结构和 HTTP 状态码

#### Scenario: 信号扫描与查询端点保持相同 URL 和行为

- **Given** 策略组引擎已迁移到 Flask
- **When** 客户端请求以下端点
  - `POST /api/strategy/<group_id>/scan` — 手动触发扫描
  - `GET /api/signals` — 查询信号列表（支持 `strategy_group_id`, `stock_code`, `limit`, `offset` 参数）
  - `GET /api/signals/stream` — SSE 实时信号推送
- **Then** 每个 endpoint SHALL 返回与原 FastAPI 版本相同的 JSON 结构和 HTTP 状态码

#### Scenario: 群体事件端点保持相同 URL 和行为

- **Given** 策略组引擎已迁移到 Flask
- **When** 客户端请求以下端点
  - `GET /api/events` — 查询事件列表（支持 `strategy_group_id`, `dimension_value`, `status`, `limit`, `offset` 参数）
  - `GET /api/events/<id>` — 获取事件详情
  - `PATCH /api/events/<id>/close` — 手动关闭事件
- **Then** 每个 endpoint SHALL 返回与原 FastAPI 版本相同的 JSON 结构和 HTTP 状态码

#### Scenario: 行业数据同步端点保持相同 URL 和行为

- **Given** 策略组引擎已迁移到 Flask
- **When** 客户端请求以下端点
  - `POST /api/admin/industry/sync` — 触发后台同步（返回 202）
  - `GET /api/admin/industry/sync/status` — 查询同步进度
  - `GET /api/admin/industry/stats` — 行业分布统计
  - `GET /api/admin/industry/status` — 行业补全状态
- **Then** 每个 endpoint SHALL 返回与原 FastAPI 版本相同的 JSON 结构和 HTTP 状态码

### Requirement: 无 FastAPI 残余依赖

迁移完成后，项目 SHALL 不再在路由层导入 `fastapi` 或 `sse_starlette`。

#### Scenario: 路由文件无 FastAPI import

- **Given** 迁移已完成
- **When** 检查 `compass/strategy/routes/` 目录下所有 `.py` 文件
- **Then** 不 SHALL 包含 `from fastapi` 或 `from sse_starlette` 的 import 语句

### Requirement: 非路由文件零改动

迁移 SHALL NOT 修改 `compass/strategy/` 下非路由相关的文件。

#### Scenario: 数据层和服务层文件不变

- **Given** 迁移已完成
- **When** 比对以下文件的 git diff
  - `compass/strategy/db.py`
  - `compass/strategy/models.py`
  - `compass/strategy/scheduler.py`
  - `compass/strategy/services/*.py`
  - `compass/strategy/__init__.py`
- **Then** 这些文件 SHALL 无变更

## ADDED Requirements

### Requirement: 策略组生命周期初始化集成到 Compass 应用

策略组引擎的启动时初始化（建表 + 调度器启动）SHALL 集成到 Compass Flask 应用的启动流程中。

#### Scenario: Flask 应用启动时初始化策略组引擎

- **Given** Compass Flask 应用通过 `create_app()` 创建
- **When** 应用初始化完成
- **Then** 系统 SHALL 自动执行 `compass.strategy.db.init_tables()` 进行建表
- **And** 系统 SHALL 自动执行 `compass.strategy.scheduler.start_scheduler()` 启动定时调度

### Requirement: 后台任务使用 threading 替代 FastAPI BackgroundTasks

行业同步路由中的后台任务执行 SHALL 使用 `threading.Thread` 替代 FastAPI 的 `BackgroundTasks`。

#### Scenario: 行业同步后台执行

- **Given** 客户端发送 `POST /api/admin/industry/sync`
- **When** 同步未在运行中
- **Then** 系统 SHALL 在后台线程中执行 `sync_industry_data()`
- **And** 立即返回 202 状态码和启动确认消息

### Requirement: SSE 端点使用 Flask 流式响应

信号推送 SSE 端点 SHALL 使用 Flask 的 `Response` + `stream_with_context` 替代 `sse_starlette.EventSourceResponse`。

#### Scenario: SSE 信号流推送

- **Given** 客户端连接 `GET /api/signals/stream`
- **When** 连接建立
- **Then** 系统 SHALL 返回 `Content-Type: text/event-stream` 的流式响应
- **And** 每 30 秒发送心跳 `{"event": "ping", "data": "{\"ts\": \"heartbeat\"}"}`
