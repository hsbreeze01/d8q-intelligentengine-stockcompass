# Design: 修复策略订阅 401 和 SPA 路由 404

## Architecture Decision

### 问题 1：订阅 401

**根因**：Factory 通过 `_strategy_proxy` 代理策略 API 到 Compass，并在 header `X-Forwarded-User` 中传递 `session["username"]`。同时 Factory 也在 request body/query 中注入 `user_id` 字段。但 Compass 的 `strategy_subscription.py` 的 `_require_login()` 检查的是 `session.get("uid")`，这完全忽略了 header 和 query 参数。Compass 没有用户登录流程（前端在 Factory），所以 Compass session 永远没有 uid。

**修复方案**：Compass 的 subscription 路由改为从 `request.headers.get("X-Forwarded-User")` 或 `request.args.get("user_id")` 读取用户身份。修改 `_require_login()` 函数：

```python
def _require_login():
    """从代理 header 或 query 参数读取用户身份"""
    return (
        request.headers.get("X-Forwarded-User")
        or request.args.get("user_id")
        or session.get("uid")
    )
```

这样既支持 Factory 代理模式（header 传递），也支持 query 参数传递，还保留了原始 session 方式。

### 问题 2：SPA 路由 404

**根因**：Flask 只有 `@app.route("/")` 渲染 `index.html`，以及 `/api/*` 路由。浏览器直接请求 `/my-strategy`、`/strategy-discover` 等 SPA 路由时，Flask 返回 404。

**修复方案**：在 `app.py` 末尾添加 catch-all 路由，所有非 `/api/*`、非 `/static/*` 的 GET 请求都 fallback 到 `index.html`：

```python
@app.route("/<path:path>")
def spa_fallback(path):
    """SPA 路由 fallback — 所有非 API 路由返回 index.html"""
    if path.startswith("api/") or path.startswith("static/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("index.html")
```

注意：此路由必须放在所有其他路由之后，确保 API 路由优先匹配。

## Files Changed

| File | Project | Change |
|------|---------|--------|
| `compass/strategy/routes/strategy_subscription.py` | stockcompass | `_require_login()` 改为读 header/args/session 三级 fallback |
| `app.py` | datafactory | 末尾添加 SPA catch-all 路由 |

## Risks
- SPA catch-all 可能吞掉合法的 404（如拼写错误路径）— 可接受，SPA 前端会显示正确内容
- `_require_login()` 修改后 Compass 直连 subscription 也可以用 query 参数 — 向后兼容
