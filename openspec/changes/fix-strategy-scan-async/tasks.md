# Tasks: 策略扫描异步化 + LLM 分析解耦

## 组 1: 扫描运行状态查询（后端）

- [x] **1.1** 在 `compass/strategy/db.py` 新增 `get_latest_run(group_id)` 函数和 `cleanup_stale_runs()` 函数
  - `get_latest_run(group_id)`: 查询 `strategy_group_run WHERE strategy_group_id = %s ORDER BY started_at DESC LIMIT 1`，返回 dict 或 None
  - `cleanup_stale_runs()`: 将 `status='running' AND started_at < NOW() - INTERVAL 30 MINUTE` 的记录更新为 `status='failed', error_message='stale run cleaned on startup'`

- [x] **1.2** 在 `compass/strategy/routes/signals.py` 新增 `GET /api/strategy/<group_id>/runs/latest` 路由
  - 调用 `db_helpers.get_latest_run(group_id)` 查询最新运行记录
  - 策略组不存在返回 404，无运行记录返回 200 + null

- [x] **1.3** 在 `compass/strategy/app.py` 的 `init_strategy_engine()` 中调用 `cleanup_stale_runs()`
  - 在 `init_tables()` 和 `start_scheduler()` 之后调用
  - 异常仅 log warning，不影响引擎启动

## 组 2: 测试补充

- [x] **2.1** 补充 `tests/test_strategy/test_async_scan.py` 测试用例
  - `TestRunStatusQuery`: 测试 `GET /strategy/{id}/runs/latest` 返回最新运行记录、策略组不存在返回 404、无运行记录返回 null
  - `TestStaleRunCleanup`: 测试 `cleanup_stale_runs()` 将超时 running 记录标记为 failed、不影响已完成的记录
  - 共约 4-5 个测试方法，覆盖正常路径和边界情况
