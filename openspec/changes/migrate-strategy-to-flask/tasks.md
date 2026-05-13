# Tasks: 策略组引擎 FastAPI → Flask Blueprint 迁移

## 1. 路由文件迁移（FastAPI → Flask Blueprint）

- [ ] 1.1 迁移 `compass/strategy/routes/strategy_groups.py` — APIRouter → Blueprint，转换 6 个端点（create/update/delete/toggle_status/list/get），Pydantic 手动解析，HTTPException → jsonify + status code，保留 `_to_response`/`_fmt` 辅助函数
- [ ] 1.2 迁移 `compass/strategy/routes/signals.py` — APIRouter → Blueprint，转换 3 个端点（trigger_scan/query_signals/signal_stream），SSE 改用 Flask Response + stream_with_context + time.sleep，Query 参数改用 `request.args.get()`
- [ ] 1.3 迁移 `compass/strategy/routes/events.py` — APIRouter → Blueprint，转换 3 个端点（query_events/get_event/close_event），路径参数 `{event_id}` → `<int:event_id>`，Query 参数改用 `request.args.get()`
- [ ] 1.4 迁移 `compass/strategy/routes/industry_sync.py` — APIRouter → Blueprint，转换 4 个端点（trigger_sync/sync_status/industry_stats/industry_status），BackgroundTasks → threading.Thread

## 2. 应用入口与注册

- [ ] 2.1 重写 `compass/strategy/app.py` — 移除 FastAPI create_app/生命周期/lifespan，改为提供 `register_blueprints(app)` 函数（注册 4 个 Blueprint）+ `init_strategy_engine()` 函数（建表 + 启动调度器）
- [ ] 2.2 修改 `compass/api/app.py` — 在 `_register_blueprints()` 中导入并注册 `compass.strategy.app.register_blueprints`，在 `_start_scheduler()` 中调用 `compass.strategy.app.init_strategy_engine()`

## 3. 验证与清理

- [ ] 3.1 清理 FastAPI 残余 import — 确认所有 strategy/routes/*.py 文件无 `from fastapi` / `from sse_starlette` 导入，运行 ruff 检查
- [ ] 3.2 端到端验证 — `from compass.api.app import create_app; app = create_app()` 成功创建，`app.url_map` 包含所有 16 个策略组路由规则
