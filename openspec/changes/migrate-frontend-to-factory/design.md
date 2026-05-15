## Context

当前系统有两个 Flask Web 服务运行在同一台服务器 (47.99.57.152) 上：
- **Compass (8087)**：前后端一体，提供 20+ Jinja2 模板页面 + REST API（行情、分析、策略组引擎等）
- **DataFactory (8088)**：统一前端入口，已有赛道/资讯/个股/管理后台等页面，通过 HTTP 代理调用 Compass API

DataFactory 的 app.py 中已有 `COMPASS_API = "http://localhost:8087"` 常量和 `compass_request()` 代理函数，大量 Compass API 已被代理。但 Compass 仍然直接对外暴露前端页面，导致：
1. 用户需要知道两个端口的存在
2. 策略组相关的新页面分散在 Compass 中
3. 认证体系不统一（Compass 用 MySQL user 表，DataFactory 用 SQLite user 表 + session）

## Goals / Non-Goals

**Goals:**
- DataFactory (8088) 成为唯一面向用户的 Web 入口，所有页面统一在此服务
- Compass (8087) 降级为纯 API 后端，不再渲染任何 HTML
- 保持所有现有功能和 URL 路径不变（用户无感知迁移）
- 认证统一走 DataFactory 的 auth 系统

**Non-Goals:**
- 不重写前端页面（Jinja2 模板原样迁移）
- 不改变 Compass API 的接口契约（URL、请求/响应格式不变）
- 不引入新的前端框架（不用 React/Vue/Next.js）
- 不改变数据库结构
- 不处理 Compass 内部调度器、pipeline 等后端逻辑

## Decisions

### D1: 模板迁移策略 — 物理复制到 DataFactory

**选择**：将 Compass 的 templates/ 目录整体复制到 DataFactory 的 templates/compass/ 子目录下。

**理由**：
- DataFactory 已有自己的模板（index.html、login.html 等），与 Compass 的模板文件名有冲突（如 index.html、login.html、report.html）
- 放在 templates/compass/ 子目录下，Flask 的 render_template 路径为 `compass/index.html`，无冲突
- 静态资源同理，放到 static/compass/ 子目录

**替代方案**：
- A. 软链接：运维简单但部署不透明，git 不跟踪 → 否决
- B. 修改所有模板文件名：如 compass_index.html → 工作量大且丑陋 → 否决
- C. Flask Blueprint 的 template_folder 参数：可以隔离，但需要每个 Blueprint 配置 → 可选但增加复杂度

### D2: 页面路由策略 — DataFactory 新增 Blueprint

**选择**：在 DataFactory 中新建 `compass_pages` Blueprint，URL 前缀为 `/`（无前缀），逐一迁移 Compass 的页面路由。

**理由**：
- DataFactory 已有根路由 `/`（render_template index.html），需要与 Compass 的 `/` 协调
- Compass 的 `/` 是股票列表页，DataFactory 的 `/` 是主入口 → 需要合并或选择其一
- 采用策略：DataFactory 的根路由保持不变（已作为主入口），Compass 的原页面路由挂载到对应路径

**具体路由映射**：
| Compass 原路由 | DataFactory 新路由 | 处理方式 |
|---|---|---|
| `/` (股票列表) | `/compass/` | 新路由，render_template("compass/index.html") |
| `/dashboard` | `/compass/dashboard` | 新路由 |
| `/strategy/discover/` | `/strategy/discover/` | 新路由 |
| `/strategy/my/` | `/strategy/my/` | 新路由 |
| `/strategy/events/<id>/` | `/strategy/events/<id>/` | 新路由 |
| `/strategy/admin/groups/` | `/strategy/admin/groups/` | 新路由 |
| `/strategy/admin/groups/<id>/edit` | `/strategy/admin/groups/<id>/edit` | 新路由 |
| `/login` | 已有 DataFactory `/login` | 复用 DataFactory 现有登录 |
| `/register` | `/register` | 复用或新建 |
| `/recommended/<date>` | `/compass/recommended/<date>` | 新路由 |
| `/report` | 已有 DataFactory `/report` | 合并到 DataFactory |
| `/policy` | `/compass/policy` | 新路由 |

### D3: 数据获取策略 — 通过 Compass API 代理

**选择**：页面路由中的数据获取不再直连 MySQL，而是通过 `compass_request()` 代理调用 Compass 的 API 端点。

**理由**：
- DataFactory 的 app.py 已有完善的 `compass_request()` 函数
- 原页面路由中有大量直连 Database() 的逻辑（如 pages.py 中的 `_get_dic_stock()`），这些不应迁移到 DataFactory
- Compass 已有对应的 JSON API（如 index 路由支持 `?format=json`），直接复用

**变更点**：
- 原 Compass pages.py 中 `_get_dic_stock()` 直连 MySQL → DataFactory 调用 `GET /?format=json` API
- 原 strategy_pages.py 中 `db.list_strategy_groups_with_subscription()` → DataFactory 调用 `GET /api/strategy/groups/` API
- 所有 db.xxx() 调用替换为 compass_request() API 调用

### D4: 认证策略 — DataFactory session 透传

**选择**：DataFactory 页面路由使用 DataFactory 的 session 认证，API 调用时通过 header 或参数传递用户身份给 Compass。

**理由**：
- DataFactory 已有完整的 auth 系统（auth.py），login 页面、session 管理都已实现
- Compass 原有的 login/register 页面将被废弃
- DataFactory 的 `compass_request()` 已支持在代理请求时传递认证信息

### D5: 静态资源处理

**选择**：将 Compass 的 static/ 目录复制到 DataFactory 的 static/compass/ 下，模板中的引用路径使用 Flask 的 url_for('static', filename='compass/...')。

**理由**：避免文件名冲突（DataFactory 已有 static/ 目录），路径隔离清晰。

### D6: Compass API CORS 配置

**选择**：由于 DataFactory 通过服务端代理（`compass_request()`）调用 Compass API，而非前端直接跨域调用，因此 Compass 无需配置 CORS。

**理由**：所有 API 调用都通过 DataFactory 服务端代理，浏览器只与 DataFactory (8088) 通信，不存在跨域问题。

## Risks / Trade-offs

- **[模板中硬编码路径]** → 迁移后模板中的 `url_for()` 引用可能指向错误 Blueprint。缓解：逐个模板检查路径，使用 Flask Blueprint 的 url_for 正确引用。
- **[认证不兼容]** → Compass 的 session 认证和 DataFactory 不同，迁移后页面访问 Compass API 时可能 401。缓解：确保 compass_request() 传递必要的认证 header；对于 API-only 的 Compass，可以配置白名单或 token 认证。
- **[策略组模板中 fetch API 路径]** → 策略组页面的 JS 代码可能硬编码了 `/api/strategy/...` 路径，迁移后需确保这些请求也走 DataFactory 代理。缓解：检查所有模板中的 fetch/XMLHttpRequest 调用，确保路径在 DataFactory 有对应代理路由。
- **[双份模板维护]** → 模板物理复制后，两份代码需同步维护。缓解：迁移完成后删除 Compass 侧的模板，只保留 DataFactory 一份。

## Migration Plan

1. **Phase 1: 复制资源** — 将 Compass 的 templates/ 和 static/ 复制到 DataFactory 的对应子目录
2. **Phase 2: 添加路由** — 在 DataFactory 中新建 Blueprint，逐一添加页面路由
3. **Phase 3: 适配数据获取** — 将模板中的数据获取从直连 DB 改为 API 代理调用
4. **Phase 4: 清理 Compass** — 移除 Compass 的前端路由和模板配置
5. **Phase 5: 重启验证** — 重启两个 gunicorn 服务，验证所有页面和 API 正常工作
6. **Rollback** — 如果出问题，恢复 Compass 的前端路由即可（git revert）

## Open Questions

- DataFactory 的 `/report` 路由是否已涵盖 Compass `/report` 的功能？需要检查模板内容对比。
- Compass 的 favorites、simulation、security 等 Blueprint 中是否有页面路由需要一并迁移？还是纯 API？
