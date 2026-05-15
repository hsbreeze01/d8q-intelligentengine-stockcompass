# Tasks: fix-strategy-subscribe-spa

## Task 1: 修复 Compass subscription 认证
- **spec**: compass-subscription-auth
- **project**: d8q-intelligentengine-stockcompass
- **file**: `compass/strategy/routes/strategy_subscription.py`
- **action**: 修改 `_require_login()` 函数，添加 `request` import，改为从 `X-Forwarded-User` header / `user_id` query 参数 / `session["uid"]` 三级 fallback
- **verify**: `curl -H "X-Forwarded-User: admin" http://localhost:8087/api/strategy/subscription/mine` 返回 200

## Task 2: 添加 Factory SPA catch-all 路由
- **spec**: factory-spa-fallback
- **project**: d8q-intelligentengine-datafactory
- **file**: `app.py`
- **action**: 在文件末尾（所有 `@app.route` 之后）添加 SPA fallback 路由，排除 `api/` 和 `static/` 前缀
- **verify**: `curl -s http://localhost:8088/my-strategy | head -5` 返回 HTML

## Task 3: 重启服务并端到端验证
- **action**: `systemctl restart d8q-compass && systemctl restart d8q-factory`
- **verify**:
  1. `curl -s -H "X-Forwarded-User: admin" http://localhost:8087/api/strategy/subscription/mine` → 200
  2. `curl -s http://localhost:8088/my-strategy | head -3` → HTML
  3. `curl -s http://localhost:8088/strategy-discover | head -3` → HTML
  4. `curl -s http://localhost:8088/api/strategy/subscriptions/` → JSON（非 404）
