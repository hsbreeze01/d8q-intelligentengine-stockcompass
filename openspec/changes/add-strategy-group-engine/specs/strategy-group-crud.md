# Delta Spec: Strategy Group CRUD

## Summary
策略组的创建、编辑、删除、启停和查询功能。

## ADDED Requirements

### REQ-SG-001: 创建策略组
系统 SHALL 提供 API 端点 `POST /api/strategy/groups` 用于创建策略组。

创建时 MUST 包含以下字段：
- `name`: 策略组名称（非空字符串）
- `indicators`: 指标列表（如 `["KDJ", "RSI", "MACD"]`），不可为空
- `signal_logic`: 组合逻辑，取值限定为 `AND` / `OR` / `SCORING`
- `conditions`: 触发条件数组，每个条件包含 `indicator`、`operator`、`value`
- `aggregation`: 聚合规则对象，包含 `dimension`（industry/concept/theme）、`min_stocks`（≥1）、`time_window_minutes`（≥1）
- `scan_cron`: 扫描频率 cron 表达式

系统 SHALL 为新策略组生成唯一 ID，设置状态为 `active`，记录 `created_at` 时间戳。

#### Scenario: 成功创建策略组
- **Given** 请求体包含合法的 name、indicators、signal_logic、conditions、aggregation、scan_cron
- **When** 客户端调用 `POST /api/strategy/groups`
- **Then** 系统返回 201，body 包含 `id`、`name`、`status: "active"`、`created_at`

#### Scenario: 缺少必填字段
- **Given** 请求体缺少 `name` 字段
- **When** 客户端调用 `POST /api/strategy/groups`
- **Then** 系统返回 400，body 包含 `error` 描述缺少字段名

#### Scenario: signal_logic 值非法
- **Given** 请求体 `signal_logic` 为 `"XOR"`
- **When** 客户端调用 `POST /api/strategy/groups`
- **Then** 系统返回 400，body 包含 `error` 描述合法取值范围

### REQ-SG-002: 编辑策略组
系统 SHALL 提供 `PUT /api/strategy/groups/{id}` 端点用于修改策略组的任何配置项。

#### Scenario: 成功更新策略组
- **Given** 存在 ID 为 42 的策略组
- **When** 客户端调用 `PUT /api/strategy/groups/42` 并传入 `{"name": "新名称"}`
- **Then** 系统返回 200，策略组 name 已更新

#### Scenario: 策略组不存在
- **Given** 不存在 ID 为 999 的策略组
- **When** 客户端调用 `PUT /api/strategy/groups/999`
- **Then** 系统返回 404

### REQ-SG-003: 删除策略组（软删除）
系统 SHALL 提供 `DELETE /api/strategy/groups/{id}` 端点，执行软删除——将状态改为 `archived`，而非物理删除。

#### Scenario: 成功软删除
- **Given** 存在 ID 为 42 且状态为 active 的策略组
- **When** 客户端调用 `DELETE /api/strategy/groups/42`
- **Then** 系统返回 200，该策略组状态变为 `archived`

#### Scenario: 已归档的策略组再次删除
- **Given** 存在 ID 为 42 且状态为 archived 的策略组
- **When** 客户端调用 `DELETE /api/strategy/groups/42`
- **Then** 系统返回 200，策略组保持 archived 状态不变

### REQ-SG-004: 启停策略组
系统 SHALL 提供 `PATCH /api/strategy/groups/{id}/status` 端点用于在 `active` 和 `paused` 之间切换状态。

#### Scenario: 暂停策略组
- **Given** 存在 ID 为 42 且状态为 active 的策略组
- **When** 客户端调用 `PATCH /api/strategy/groups/42/status` 并传入 `{"status": "paused"}`
- **Then** 系统返回 200，策略组状态变为 `paused`，定时扫描停止触发该策略组

#### Scenario: 恢复策略组
- **Given** 存在 ID 为 42 且状态为 paused 的策略组
- **When** 客户端调用 `PATCH /api/strategy/groups/42/status` 并传入 `{"status": "active"}`
- **Then** 系统返回 200，策略组状态变为 `active`

#### Scenario: 非法状态值
- **Given** 请求体 `{"status": "running"}`
- **When** 客户端调用 `PATCH /api/strategy/groups/42/status`
- **Then** 系统返回 400，描述合法取值为 active/paused

### REQ-SG-005: 查询策略组列表
系统 SHALL 提供 `GET /api/strategy/groups` 端点，支持按状态筛选和按创建时间排序。

#### Scenario: 查询所有策略组
- **Given** 数据库中有 3 个策略组（2 active, 1 archived）
- **When** 客户端调用 `GET /api/strategy/groups`
- **Then** 系统返回 200，body 包含所有 3 个策略组（含 archived），按 created_at 降序

#### Scenario: 按状态筛选
- **When** 客户端调用 `GET /api/strategy/groups?status=active`
- **Then** 系统返回 200，body 仅包含状态为 active 的策略组

#### Scenario: 获取单个策略组详情
- **When** 客户端调用 `GET /api/strategy/groups/42`
- **Then** 系统返回 200，body 包含该策略组的完整配置（含 indicators、conditions、aggregation 的 JSON 字段）
