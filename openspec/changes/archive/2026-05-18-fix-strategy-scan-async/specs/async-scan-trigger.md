# Spec: 策略扫描异步触发

## ADDED Requirements

### Requirement: 手动扫描异步触发

手动触发策略组扫描时，系统 SHALL 立即返回 HTTP 202 状态码，包含 `run_id` 和 `status="running"`。扫描过程在后台线程中执行，不阻塞 HTTP 请求线程。

#### Scenario: 正常触发手动扫描

- **Given** 策略组 `{group_id}` 存在且 `status="active"`
- **When** 客户端发送 `POST /api/strategy/{group_id}/scan`
- **Then** 系统 SHALL 在 3 秒内返回 HTTP 202，响应体包含 `{"run_id": <int>, "status": "running"}`
- **And** 系统 SHALL 在后台线程中执行扫描（scanner → aggregator → DB 写入）
- **And** 后台线程中 `Scanner.scan()` SHALL 传入 `run_id=<已创建的 run_id>` 和 `skip_llm=True`

#### Scenario: 策略组不存在

- **Given** 策略组 `{group_id}` 不存在
- **When** 客户端发送 `POST /api/strategy/{group_id}/scan`
- **Then** 系统 SHALL 返回 HTTP 400，响应体包含 `{"error": "策略组 {group_id} 不存在"}`

#### Scenario: 策略组非 active 状态

- **Given** 策略组 `{group_id}` 存在但 `status` 不为 `"active"`
- **When** 客户端发送 `POST /api/strategy/{group_id}/scan`
- **Then** 系统 SHALL 返回 HTTP 400，响应体包含错误信息说明策略组未处于 active 状态

### Requirement: 扫描期间 API 不阻塞

手动扫描执行期间，所有其他 API 端点 SHALL 正常响应，不出现 502 或超时。

#### Scenario: 扫描进行中查询策略组列表

- **Given** 策略组 1 的手动扫描正在后台执行
- **When** 客户端发送 `GET /api/strategy/groups`
- **Then** 系统 SHALL 返回 HTTP 200，包含策略组列表

#### Scenario: 扫描进行中查询信号

- **Given** 策略组 1 的手动扫描正在后台执行
- **When** 客户端发送 `GET /api/signals?strategy_group_id=1`
- **Then** 系统 SHALL 返回 HTTP 200，包含信号列表（可能是之前扫描的结果）

### Requirement: 后台扫描完成/失败状态持久化

后台线程执行扫描后，SHALL 更新 `strategy_group_run` 记录的状态。

#### Scenario: 扫描成功完成

- **Given** 后台扫描线程成功完成扫描
- **When** `Scanner.scan()` 正常返回结果
- **Then** 系统 SHALL 更新 `strategy_group_run` 记录：`status="completed"`，并填写 `total_stocks`、`matched_stocks`、`duration_seconds`、`finished_at`

#### Scenario: 扫描过程中异常

- **Given** 后台扫描线程执行过程中抛出异常
- **When** `Scanner.scan()` 抛出 `RuntimeError`
- **Then** 系统 SHALL 更新 `strategy_group_run` 记录：`status="failed"`，`error_message` 包含异常信息
- **And** 系统 SHALL 记录 error 级别日志
- **And** 更新失败状态的操作本身如果也失败，SHALL 仅记录日志，不抛出异常
