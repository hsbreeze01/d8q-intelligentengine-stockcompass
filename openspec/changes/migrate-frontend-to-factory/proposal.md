## Why

Compass (8087) 当前是前后端一体的 Flask 应用，既提供 Jinja2 渲染的 HTML 页面，又提供 REST API。DataFactory (8088) 已经作为统一前端入口提供服务（赛道、资讯、个股、管理后台），并通过代理调用 Compass API。这导致前端页面分散在两个服务中，用户需要访问不同端口，体验割裂。将所有前端页面收敛到 DataFactory (8088)，Compass 降级为纯后端 API 服务，实现前后端职责分离。

## What Changes

- **将 Compass 全部 Jinja2 模板和静态文件迁移到 DataFactory**：包括 index.html、dashboard.html、strategy/ 目录下的所有策略组页面（discover、my_strategies、event_detail、admin_list、admin_edit）、login/register、report、policy 等 20+ 模板文件
- **在 DataFactory 中新增 Compass 页面路由**：将原 compass/api/routes/pages.py 和 compass/strategy/routes/strategy_pages.py 的页面路由迁移到 DataFactory，通过 `COMPASS_API` 代理获取数据并渲染模板
- **Compass 移除所有前端路由 Blueprint**：删除 pages_bp 和 strategy_pages_bp 注册，移除 template_folder 和 static_folder 配置，仅保留纯 API 蓝图
- **迁移 Compass 的静态资源**：将 static/ 目录（css/、admin/、images/）迁移到 DataFactory
- **DataFactory 的 strategy 模板中 API 调用路径调整**：原模板通过相对路径调 Compass API，迁移后需确认所有 fetch/XMLHttpRequest 路径正确代理
- **Compass 登录认证对接**：DataFactory 已有独立的 auth 系统（SQLite user 表 + session），需确保 Compass 的 API 认证机制与 DataFactory 的 session 认证兼容

## Capabilities

### New Capabilities
- `frontend-unification`: 将 Compass 的全部前端页面（20+ Jinja2 模板 + 静态资源）迁移到 DataFactory，DataFactory 成为唯一的前端 Web 入口，Compass 退化为纯 API 后端

### Modified Capabilities
- `compass-api-only`: Compass 移除 template/static 配置和页面路由 Blueprint，仅保留 JSON API 端点，新增 CORS 支持以接受来自 DataFactory 的跨域请求

## Impact

- **代码变更**：
  - DataFactory app.py：新增 10+ 页面路由（index、dashboard、strategy/*、report、policy 等）
  - DataFactory templates/：新增 20+ HTML 模板文件
  - DataFactory static/：新增 CSS 和 admin 静态资源
  - Compass compass/api/app.py：移除 pages_bp、strategy_pages_bp 注册，移除 template_folder/static_folder
  - Compass compass/api/routes/pages.py：删除整个文件
  - Compass compass/strategy/routes/strategy_pages.py：删除整个文件
- **API 变更**：Compass 需新增 CORS 头支持，接受 DataFactory 的代理请求
- **依赖**：DataFactory 可能需要新增依赖（如 pandas 用于数据处理，如果页面路由需要）
- **运维**：gunicorn 配置无需变更（端口不变），重启两个服务即可生效
- **用户体验**：用户统一通过 8088 端口访问所有功能，8087 不再直接面向用户
