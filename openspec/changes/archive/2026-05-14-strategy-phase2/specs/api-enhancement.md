# Delta Spec: 事件关闭 API 增强

## MODIFIED Requirements

### REQ-API-001: 事件关闭端点记录操作者

`POST /api/events/<id>/close` 端点 SHALL 在关闭事件时记录操作者信息和关闭时间。

#### Scenario: 管理员关闭事件并记录操作者

- **Given** 一个群体事件存在且 `lifecycle` 为 `'suggest_close'` 或 `'tracking'`
- **When** 管理员调用 `POST /api/events/<id>/close`
- **Then** 系统 SHALL 更新 `lifecycle='closed'`，设置 `closed_at` 为当前时间，设置 `closed_by` 为当前登录用户 ID
- **And** 返回 200 和更新后的事件数据

#### Scenario: 关闭已关闭的事件

- **Given** 一个群体事件的 `lifecycle` 已为 `'closed'`
- **When** 调用 `POST /api/events/<id>/close`
- **Then** 系统 SHALL 返回 400 错误，提示事件已关闭

#### Scenario: 关闭不存在的事件

- **Given** 指定 ID 的群体事件不存在
- **When** 调用 `POST /api/events/<id>/close`
- **Then** 系统 SHALL 返回 404 错误

---

## ADDED Requirements

### REQ-API-002: 事件趋势跟踪数据查询

系统 SHALL 提供查询群体事件趋势跟踪历史数据的 API 端点。

#### Scenario: 查询事件趋势跟踪记录

- **Given** 一个群体事件存在
- **When** 调用 `GET /api/events/<id>/trend`
- **Then** 系统 SHALL 返回该事件所有 `trend_tracking` 记录，按日期升序排列
- **And** 每条记录包含 date、指标均值、new_stocks、lost_stocks、news_count

#### Scenario: 查询不存在事件的趋势

- **Given** 指定 ID 的群体事件不存在
- **When** 调用 `GET /api/events/<id>/trend`
- **Then** 系统 SHALL 返回 404 错误
