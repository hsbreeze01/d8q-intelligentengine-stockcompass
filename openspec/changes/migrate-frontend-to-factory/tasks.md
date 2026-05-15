## 1. 资源迁移（模板 + 静态文件）

- [x] 1.1 在 DataFactory 项目中创建 templates/compass/ 和 static/compass/ 目录
- [x] 1.2 复制 Compass 的所有模板文件到 DataFactory 的 templates/compass/ 下（包括 strategy/ 子目录）
- [x] 1.3 复制 Compass 的 static/ 目录内容到 DataFactory 的 static/compass/ 下（css/、admin/、images/）
- [x] 1.4 修改迁移后的模板文件中所有 static 资源引用路径，从 `/static/xxx` 改为 `/static/compass/xxx`（或使用 url_for 配合 Blueprint 静态目录）

## 2. DataFactory 页面路由实现

- [x] 2.1 在 DataFactory 中创建 compass_pages Blueprint（如 compass_pages.py），配置 template_folder 指向 templates/compass/
- [x] 2.2 实现 `/compass/` 路由（股票列表页）：通过 compass_request("GET", "/?format=json") 获取数据，render_template("index.html")
- [x] 2.3 实现 `/compass/dashboard` 路由：render_template("dashboard.html")
- [x] 2.4 实现 `/compass/recommended/<date>` 路由：通过 compass_request 获取推荐数据，render_template("recommended_stocks.html")
- [x] 2.5 实现 `/compass/report` 路由：render_template("report.html")
- [x] 2.6 实现 `/compass/policy` 路由：render_template("policy.html")
- [x] 2.7 实现 `/strategy/discover/` 路由：通过 compass_request("GET", "/api/strategy/groups/?public=1") 获取策略列表 + subscriptions，render_template("strategy/discover.html")
- [x] 2.8 实现 `/strategy/my/` 路由：通过 compass_request 获取用户订阅和事件数据，render_template("strategy/my_strategies.html")
- [x] 2.9 实现 `/strategy/events/<int:event_id>/` 路由：通过 compass_request 获取事件详情，render_template("strategy/event_detail.html")
- [x] 2.10 实现 `/strategy/admin/groups/` 路由（需 admin 权限检查）：通过 compass_request 获取策略组列表，render_template("strategy/admin_list.html")
- [x] 2.11 实现 `/strategy/admin/groups/new` 路由：render_template("strategy/admin_edit.html")
- [x] 2.12 实现 `/strategy/admin/groups/<int:group_id>/edit` 路由：通过 compass_request 获取策略组详情，render_template("strategy/admin_edit.html")
- [x] 2.13 在 DataFactory app.py 中注册 compass_pages Blueprint

## 3. 认证对接

- [x] 3.1 确保 compass_pages Blueprint 中所有需要认证的路由使用 DataFactory 的 session 认证（check session["username"]）
- [x] 3.2 策略组 admin 路由增加 admin 角色检查（check session.get("role") == "admin"）
- [x] 3.3 确保 compass_request() 代理调用时传递用户身份信息（如 X-User header）给 Compass API
- [x] 3.4 验证 DataFactory login 页面登录后，compass 页面路由能正确获取用户身份

## 4. 模板 API 路径适配

- [x] 4.1 检查所有迁移模板中的 fetch/XMLHttpRequest 调用路径，确保 `/api/strategy/*`、`/api/events/*` 等路径在 DataFactory 有对应代理路由
- [x] 4.2 确认 DataFactory 已有的 API 代理路由覆盖了策略组页面需要的所有 API 端点（如 /api/strategy/groups/、/api/strategy/events/、/api/strategy/subscriptions/ 等）
- [x] 4.3 对于缺失的 API 代理路由，在 DataFactory app.py 中补充 compass_request 代理

## 5. Compass 前端路由清理

- [x] 5.1 在 compass/api/app.py 中移除 pages_bp 的注册（`from compass.api.routes.pages import bp as pages_bp` 和 `app.register_blueprint(pages_bp)`）
- [x] 5.2 在 compass/strategy/app.py 中移除 pages_bp 的注册（strategy_pages Blueprint）
- [x] 5.3 在 compass/api/app.py 的 create_app() 中移除 template_folder 和 static_folder 参数
- [x] 5.4 删除 compass/api/routes/pages.py 文件
- [x] 5.5 删除 compass/strategy/routes/strategy_pages.py 文件
- [x] 5.6 （可选）清理 compass/templates/ 和 compass/static/ 目录（迁移完成后可删除或保留作参考）

## 6. 重启与验证

- [x] 6.1 重启 DataFactory gunicorn 服务（`systemctl restart d8q-factory` 或 kill + 重启）
- [x] 6.2 重启 Compass gunicorn 服务
- [x] 6.3 验证 DataFactory (8088) 上所有 compass 页面路由返回 200 且内容正确
- [x] 6.4 验证 Compass (8087) 不再返回任何 HTML 页面（/, /dashboard 等返回 404）
- [x] 6.5 验证 Compass (8087) 的所有 API 端点仍然正常工作
- [x] 6.6 验证策略组发现→订阅→事件详情→admin 管理完整流程在 DataFactory (8088) 上正常运作
