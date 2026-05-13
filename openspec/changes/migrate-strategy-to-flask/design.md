# Design: 策略组引擎 FastAPI → Flask Blueprint 迁移

## 架构决策

### 1. Blueprint 分组策略

保持与现有 FastAPI 路由相同的 URL prefix 分组，创建 4 个独立 Blueprint：

| Blueprint 名 | url_prefix | 源文件 | 端点数 |
|---|---|---|---|
| `strategy_groups` | `/api/strategy` | `routes/strategy_groups.py` | 6 |
| `strategy_signals` | `/api` | `routes/signals.py` | 3 |
| `strategy_events` | `/api` | `routes/events.py` | 3 |
| `strategy_industry_sync` | `/api` | `routes/industry_sync.py` | 4 |

> **理由**: `strategy_groups` 使用独立 prefix `/api/strategy`，因为其端点路径为 `/groups`、`/groups/<id>` 等，需要 `/api/strategy/groups` 才能避免与其他 Blueprint 冲突。其余三个 Blueprint 的端点路径已经带有独特前缀（`/strategy/<id>/scan`、`/signals/`、`/events/`、`/admin/industry/`），共享 `/api` prefix 不会冲突。

### 2. 路径参数转换

FastAPI 的 `{param}` 风格转为 Flask 的 `<int:param>` 或 `<param>` 风格：
- `{group_id}` → `<int:group_id>`
- `{event_id}` → `<int:event_id>`

### 3. 请求体解析

FastAPI 的 Pydantic 自动解析转为手动解析：
```python
data = request.json or {}
body = StrategyGroupCreate(**data)  # 保留 Pydantic 校验
```

### 4. 后台任务

`fastapi.BackgroundTasks` → `threading.Thread(target=fn, daemon=True).start()`

### 5. SSE 流

`sse_starlette.EventSourceResponse` → Flask `Response(stream_with_context(gen()), content_type="text/event-stream")`

SSE 生成器从 `async def` 改为普通 `def`（同步），使用 `time.sleep(30)` 替代 `asyncio.sleep(30)`。Flask 的 SSE 格式需要手动添加 `data: ` 前缀和 `\n\n` 后缀。

### 6. 错误处理

`HTTPException(status_code=X, detail="...")` → `return jsonify({"error": "..."}), X`

### 7. 生命周期初始化

原 FastAPI `lifespan` 中的 `init_tables()` + `start_scheduler()` 移到 Flask `_start_scheduler()` 流程中（或 `create_app()` 末尾），保持与 Compass 现有启动模式一致。

## 数据流

```
Client Request
    │
    ▼
Compass Flask App (create_app)
    │
    ├─ /api/strategy/*  → strategy_groups Blueprint
    ├─ /api/strategy/*/scan → strategy_signals Blueprint  
    ├─ /api/signals/*  → strategy_signals Blueprint
    ├─ /api/events/*   → strategy_events Blueprint
    └─ /api/admin/industry/* → strategy_industry_sync Blueprint
                                │
                                ▼
                    compass.strategy.db (数据库操作)
                    compass.strategy.services/* (业务逻辑)
                    compass.strategy.models (Pydantic 校验)
```

## 需要修改的文件

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `compass/strategy/routes/strategy_groups.py` | **重写** | APIRouter → Blueprint，6 个端点 |
| `compass/strategy/routes/signals.py` | **重写** | APIRouter → Blueprint，3 个端点，含 SSE |
| `compass/strategy/routes/events.py` | **重写** | APIRouter → Blueprint，3 个端点 |
| `compass/strategy/routes/industry_sync.py` | **重写** | APIRouter → Blueprint，4 个端点，BackgroundTasks → threading |
| `compass/strategy/app.py` | **重写** | 移除 FastAPI create_app，改为提供 `register_blueprints(app)` 函数 + 初始化逻辑 |
| `compass/api/app.py` | **修改** | 在 `_register_blueprints()` 中导入并注册 4 个 strategy Blueprint |

## 不修改的文件

- `compass/strategy/__init__.py` — 无需改动
- `compass/strategy/db.py` — 纯 DB 操作
- `compass/strategy/models.py` — Pydantic 模型保留用于请求校验
- `compass/strategy/scheduler.py` — APScheduler 无框架依赖
- `compass/strategy/services/*.py` — 纯业务逻辑

## 关键转换模板

### strategy_groups.py 端点转换示例

**Before (FastAPI):**
```python
from fastapi import APIRouter, HTTPException
router = APIRouter()

@router.post("/groups", status_code=201)
def create_group(body: StrategyGroupCreate):
    ...
    raise HTTPException(status_code=404, detail="策略组不存在")
```

**After (Flask):**
```python
from flask import Blueprint, request, jsonify
bp = Blueprint("strategy_groups", __name__, url_prefix="/api/strategy")

@bp.route("/groups", methods=["POST"])
def create_group():
    data = request.json or {}
    body = StrategyGroupCreate(**data)
    ...
    return jsonify({"error": "策略组不存在"}), 404
    return jsonify(_to_response(group)), 201
```

### signals.py SSE 转换示例

**Before (FastAPI):**
```python
from sse_starlette.sse import EventSourceResponse
@router.get("/signals/stream")
async def signal_stream():
    async def event_generator():
        while True:
            yield {"event": "ping", "data": json.dumps({"ts": "heartbeat"})}
            await asyncio.sleep(30)
    return EventSourceResponse(event_generator())
```

**After (Flask):**
```python
from flask import Response, stream_with_context
import time

@bp.route("/signals/stream")
def signal_stream():
    def event_generator():
        while True:
            yield f"event: ping\ndata: {json.dumps({'ts': 'heartbeat'})}\n\n"
            time.sleep(30)
    return Response(stream_with_context(event_generator()), content_type="text/event-stream")
```

### industry_sync.py BackgroundTasks 转换示例

**Before (FastAPI):**
```python
from fastapi import BackgroundTasks
@router.post("/admin/industry/sync", status_code=202)
def trigger_industry_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_industry_data)
    return {"message": "同步任务已启动"}
```

**After (Flask):**
```python
import threading
@bp.route("/admin/industry/sync", methods=["POST"])
def trigger_industry_sync():
    thread = threading.Thread(target=sync_industry_data, daemon=True)
    thread.start()
    return jsonify({"message": "同步任务已启动"}), 202
```
