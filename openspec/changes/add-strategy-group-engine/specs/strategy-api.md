# Spec: Strategy Engine REST API

## ADDED Requirements

### REQ-API-001: FastAPI Independent Service

系统 SHALL 提供 FastAPI 独立服务运行在 :8090 端口，与现有 Flask 应用（:5001）独立运行，共享同一 MySQL 数据库。

#### Scenario: Service health check
- **Given** 策略引擎服务已启动
- **When** 请求 GET http://localhost:8090/health
- **Then** 返回 200 和 `{"status": "ok", "service": "strategy-engine"}`

---

### REQ-API-002: Strategy Group CRUD Endpoints

系统 SHALL 提供以下策略组管理端点：

| Method | Path | Behavior |
|--------|------|----------|
| POST | /api/strategy/group | 创建策略组 (REQ-SG-001) |
| PUT | /api/strategy/group/{id} | 更新策略组 (REQ-SG-002) |
| DELETE | /api/strategy/group/{id} | 软删除策略组 (REQ-SG-003) |
| POST | /api/strategy/group/{id}/toggle | 切换启停 (REQ-SG-004) |
| GET | /api/strategy/groups | 列表查询 (REQ-SG-005) |
| GET | /api/strategy/group/{id} | 获取单个详情 |

#### Scenario: Full CRUD lifecycle
- **Given** 策略引擎服务已启动
- **When** 用户依次执行 POST → GET → PUT → toggle → DELETE → GET（已归档）
- **Then** 每步操作返回正确状态码和预期数据

---

### REQ-API-003: Signal and Event Query Endpoints

| Method | Path | Behavior |
|--------|------|----------|
| GET | /api/signals | 查询信号列表 (REQ-SS-006) |
| GET | /api/events | 查询群体事件列表 (REQ-GE-005) |
| GET | /api/events/{id} | 获取事件详情 |

Query Parameters for `/api/signals`:
- `group_id` (optional): 按策略组筛选
- `date` (optional): 按日期筛选 (YYYY-MM-DD)
- `min_buy_star` (optional): buy_star 下限
- `limit` (default 50, max 200)
- `offset` (default 0)

Query Parameters for `/api/events`:
- `group_id` (optional)
- `dimension` (optional): industry/concept/theme
- `status` (optional): active/resolved
- `limit` (default 20, max 100)
- `offset` (default 0)

#### Scenario: Paginated signal query
- **Given** 策略组 1 在 2025-01-15 产生了 80 条信号
- **When** GET /api/signals?group_id=1&date=2025-01-15&limit=20&offset=0
- **Then** 返回前 20 条信号（按 buy_star 降序），包含 total=80 分页元数据

---

### REQ-API-004: Scan Trigger Endpoint

| Method | Path | Behavior |
|--------|------|----------|
| POST | /api/strategy/group/{id}/scan | 手动触发扫描 (REQ-SS-004) |

#### Scenario: Manual scan returns immediate summary
- **Given** 策略组 id=5 存在
- **When** POST /api/strategy/group/5/scan
- **Then** 返回 200 和 `{"scan_run_id": <int>, "signals_found": <int>, "events_created": <int>, "duration_seconds": <float>}`

---

### REQ-API-005: SSE Signal Stream

系统 SHALL 提供 SSE 端点实时推送新信号。

| Method | Path | Behavior |
|--------|------|----------|
| GET | /api/signals/stream | SSE 实时信号流 |

#### Scenario: Client receives new signals via SSE
- **Given** 客户端已连接到 /api/signals/stream
- **When** 扫描器发现新信号
- **Then** 系统 SHALL 通过 SSE 推送 `event: signal`，data 为 JSON 格式的信号快照

---

### REQ-API-006: Industry Sync Endpoints

| Method | Path | Behavior |
|--------|------|----------|
| POST | /api/strategy/industry/sync | 触发同步 (REQ-IS-003) |
| GET | /api/strategy/industry/sync/status | 查询同步进度 |
