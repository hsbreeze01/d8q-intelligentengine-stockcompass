# Spec: 扫描运行状态查询

## ADDED Requirements

### Requirement: 查询策略组最新运行状态

客户端 SHALL 能通过 API 查询策略组的最新扫描运行状态，用于轮询判断扫描是否完成。

#### Scenario: 查询存在的策略组最新运行记录

- **Given** 策略组 `{group_id}` 存在，且有至少一条 `strategy_group_run` 记录
- **When** 客户端发送 `GET /api/strategy/{group_id}/runs/latest`
- **Then** 系统 SHALL 返回 HTTP 200，包含最新一条运行记录，字段包括 `id`、`status`、`total_stocks`、`matched_stocks`、`duration_seconds`、`started_at`、`finished_at`、`error_message`

#### Scenario: 策略组无运行记录

- **Given** 策略组 `{group_id}` 存在，但没有 `strategy_group_run` 记录
- **When** 客户端发送 `GET /api/strategy/{group_id}/runs/latest`
- **Then** 系统 SHALL 返回 HTTP 200，响应体为 `null`

#### Scenario: 查询运行中的状态

- **Given** 手动扫描已触发，`run_id=42`，后台扫描正在进行
- **When** 客户端发送 `GET /api/strategy/{group_id}/runs/latest`
- **Then** 系统 SHALL 返回 `{"id": 42, "status": "running", "total_stocks": 0, "matched_stocks": 0, ...}`
- **And** 客户端可据此判断扫描尚未完成，继续轮询

### Requirement: Stale running 记录清理

系统 SHALL 在启动时检测并清理超过一定时间的 stale `strategy_group_run` 记录（`status="running"` 但已远超正常扫描耗时），将其标记为 `failed`。

#### Scenario: 启动时清理 stale running 记录

- **Given** `strategy_group_run` 表中存在 `status="running"` 的记录，且 `started_at` 距当前时间超过 30 分钟
- **When** 策略引擎初始化（`init_strategy_engine()`）
- **Then** 系统 SHALL 将这些记录的 `status` 更新为 `"failed"`，`error_message` 设为 `"stale run cleaned on startup"`
