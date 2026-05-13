# Proposal: 策略组引擎 FastAPI → Flask Blueprint 迁移

## 背景
策略组引擎（compass/strategy/）当前使用 FastAPI 独立运行于 :8090 端口。按照"无需必要，不增实体"原则，应将其融入现有 Compass Flask 应用，避免维护两套 Web 框架。

## 目标
将 compass/strategy/ 的 4 个路由文件从 FastAPI APIRouter 迁移为 Flask Blueprint，注册到 Compass Flask 主应用中。

## 变更范围
**需要修改的文件（仅 5 个）：**
1. `compass/strategy/routes/strategy_groups.py` — APIRouter → Blueprint (6 endpoints)
2. `compass/strategy/routes/signals.py` — APIRouter → Blueprint (3 endpoints, 含 SSE)
3. `compass/strategy/routes/events.py` — APIRouter → Blueprint (3 endpoints)
4. `compass/strategy/routes/industry_sync.py` — APIRouter → Blueprint (4 endpoints)
5. `compass/strategy/app.py` — 移除 FastAPI 应用创建，改为 Blueprint 注册函数
6. `compass/api/app.py` — 在 `_register_blueprints()` 中注册 strategy blueprints

**不需要修改的文件：**
- `compass/strategy/db.py` — 纯 DB 操作，无框架依赖
- `compass/strategy/models.py` — Pydantic 模型，保留用于请求校验
- `compass/strategy/services/*.py` — 纯业务逻辑
- `compass/strategy/scheduler.py` — APScheduler，无框架依赖

## 迁移模式参考
Compass 现有 Blueprint 模式（参考 `compass/api/routes/analysis.py`）：
```python
from flask import Blueprint, request, jsonify
bp = Blueprint("name", __name__)

@bp.route("/path", methods=["GET"])
def handler():
    data = request.json or {}
    return jsonify(result)
    # 错误: return jsonify({"error": "..."}), 404
```

## 关键转换点
| FastAPI | Flask |
|---------|-------|
| `APIRouter()` | `Blueprint("name", __name__, url_prefix="/api/xxx")` |
| `@router.post("/path")` | `@bp.route("/path", methods=["POST"])` |
| `body: PydanticModel` | `data = request.json or {}; body = PydanticModel(**data)` |
| `{group_id}` 路径参数 | `<int:group_id>` |
| `HTTPException(404, detail=...)` | `return jsonify({"error": "..."}), 404` |
| `EventSourceResponse(gen)` | `Response(stream_with_context(gen), content_type="text/event-stream")` |
| `BackgroundTasks.add_task(fn)` | `threading.Thread(target=fn, daemon=True).start()` |
| `return dict` | `return jsonify(dict)` |
| `return obj, status_code` | `return jsonify(obj), status_code` |

## 成功标准
- 所有 16 个策略组端点作为 Flask 路由工作
- `from compass.api.app import create_app; app = create_app()` 包含所有策略组路由
- 无 FastAPI 残余 import（不再依赖 fastapi/sse-starlette）
- compass/strategy/db.py, services/*.py, models.py, scheduler.py 零改动
