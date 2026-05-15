# Delta Spec: base.html 样式完善

## MODIFIED Requirements

### Requirement: Compass 风格侧边栏导航

策略组前端 base.html 模板 SHALL 使用 Compass 主应用配色体系：
- 侧边栏背景 `#001529`，文字 `rgba(255,255,255,0.65)`，悬停/激活高亮 `#1890FF`
- 主内容区背景 `#F0F2F5`
- 顶部用户信息栏，显示当前登录用户名

#### Scenario: 普通用户访问策略组页面

```
Given 用户已登录且角色为普通用户
When 用户访问任意策略组页面（/strategy/discover, /strategy/my, /strategy/events/*）
Then 页面左侧显示侧边栏，包含"策略发现"和"我的策略"两个导航项
And 侧边栏背景为 #001529，当前页面导航项高亮为 #1890FF
And 右侧主内容区背景为 #F0F2F5
And 顶部栏显示用户昵称
```

#### Scenario: 管理员用户访问策略组页面

```
Given 用户已登录且角色为管理员
When 用户访问任意策略组页面
Then 侧边栏额外显示"策略管理"导航项（/strategy/admin）
And 其他导航项与普通用户一致
```

### Requirement: ECharts CDN 引入

base.html SHALL 在 `<head>` 中引入 ECharts CDN，供子模板使用。

#### Scenario: 子模板使用 ECharts

```
Given base.html 已加载
When 子模板包含 `<script>` 块调用 echarts.init()
Then ECharts 实例正常创建，无 ReferenceError
```

### Requirement: 全局辅助函数

base.html SHALL 在全局 `<script>` 中提供通用辅助函数：
- `fetchJSON(url, options)` — 封装 fetch + JSON 解析 + 错误处理
- `renderLifecycleBadge(lifecycle)` — 返回 lifecycle 状态标签 HTML

#### Scenario: 子模板调用 fetchJSON

```
Given base.html 已加载
When 子模板调用 fetchJSON('/api/events/1/info')
Then 函数返回 Promise，resolve 为解析后的 JSON 对象
And 若 HTTP 状态非 2xx，reject 并显示错误提示
```
