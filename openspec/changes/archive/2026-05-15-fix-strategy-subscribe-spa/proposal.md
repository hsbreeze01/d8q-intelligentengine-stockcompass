# Proposal: 修复策略订阅 401 和 SPA 路由 404

## Summary
策略发现页点击订阅返回 401 未授权；直接访问 /my-strategy 等 SPA 路由返回 404。

## Motivation
两个阻断性问题导致策略功能完全不可用：
1. 订阅接口 401：Compass 的 subscription 路由用 `session.get("uid")` 检查登录态，但 DataFactory 的 session 字段是 `username` 不是 `uid`。Factory 代理层传了 `user_id` 参数但 Compass 的 `@require_login` 装饰器在参数解析之前就拦截了。
2. SPA 路由 404：用户直接访问 `http://host:8088/my-strategy` 或刷新页面时，Flask 找不到对应路由返回 404。需要 SPA fallback。

## Expected Behavior
- 策略发现页点击"订阅" → 成功订阅，toast 提示"已订阅"
- 直接访问 `/strategy-discover`、`/my-strategy`、`/strategy-admin` 等 SPA 路由 → 正常渲染对应页面
- 刷新任意 SPA 页面 → 不丢失页面状态

## Root Cause Analysis

### 订阅 401
- Compass `strategy_subscription.py` 的 `_require_login()` 检查 `session.get("uid")`
- DataFactory 的登录存的是 `session["username"]`
- Factory 代理 `/api/strategy/subscribe` 时在 body 中注入了 `user_id`，但 Compass 的 Blueprint 路由先执行 `_require_login()` 检查本地 session
- Compass 和 Factory 不共享 session（不同 Flask app 实例）

**修复方向**：Compass 的 subscription 路由改为从请求参数 `user_id` 读取（代理模式），而非依赖本地 session。或 Factory 代理层在请求头中传递认证信息。

### SPA 路由 404
- Flask 只注册了 `/` 和 API 路由
- 浏览器直接请求 `/my-strategy` 时，Flask 无匹配路由返回 404
- 需要对所有非 API、非 static 的 GET 请求 fallback 到 `index.html`

## Scope
- **Compass**: `compass/strategy/routes/strategy_subscription.py` — 修改认证检查逻辑
- **Factory**: `app.py` — 添加 SPA fallback 路由（catch-all GET → index.html）

## Target Projects
- d8q-intelligentengine-stockcompass（subscription 认证修复）
- d8q-intelligentengine-datafactory（SPA fallback + 代理认证传递）
