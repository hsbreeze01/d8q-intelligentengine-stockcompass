# Specs: fix-strategy-subscribe-spa

## spec:compass-subscription-auth

### 概述
Compass strategy subscription 路由的认证方式从依赖本地 session 改为支持代理 header/query 参数。

### 修改文件
- `compass/strategy/routes/strategy_subscription.py`

### 修改内容
`_require_login()` 函数改为三级 fallback：
1. `request.headers.get("X-Forwarded-User")` — Factory 代理 header
2. `request.args.get("user_id")` — query 参数
3. `session.get("uid")` — 本地 session（向后兼容）

需要在函数签名上方添加 `from flask import request` import（如果尚未 import）。

### 验证
- `curl -H "X-Forwarded-User: admin" http://localhost:8087/api/strategy/subscription/mine` 应返回 200 + JSON 数组（可能空）
- `curl http://localhost:8087/api/strategy/subscription/mine` 无 header 无 session 应返回 401

### 约束
- 不改动其他 Blueprint 路由（groups, signals, events 等）
- 不改动 db 层
- 保持 `_require_login()` 返回值语义不变（uid 字符串或 None）

---

## spec:factory-spa-fallback

### 概述
DataFactory Flask app 添加 SPA catch-all 路由，解决直接访问 SPA 子路由 404 问题。

### 修改文件
- `app.py`（datafactory 工程）

### 修改内容
在文件末尾（所有 `@app.route` 之后）添加：

```python
@app.route("/<path:path>")
def spa_fallback(path):
    if path.startswith(("api/", "static/")):
        return jsonify({"error": "Not found"}), 404
    return render_template("index.html")
```

确保 `render_template` 已从 flask import。

### 验证
- `curl -s http://localhost:8088/my-strategy` 返回 HTML（index.html 内容）
- `curl -s http://localhost:8088/strategy-discover` 返回 HTML
- `curl -s http://localhost:8088/api/strategy/groups` 仍返回 JSON（不被 catch-all 拦截）

### 约束
- 必须放在所有其他路由之后
- 不能影响 `/api/*` 路由
- 不能影响 `/static/*` 资源
