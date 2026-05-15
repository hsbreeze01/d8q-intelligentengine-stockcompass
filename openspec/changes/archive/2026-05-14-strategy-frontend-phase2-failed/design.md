# Design: 策略组前端 Phase 2

## 架构决策

### 1. 前端技术栈
- **Jinja2 模板 + 原生 JS + ECharts** — 与 Compass 主应用保持一致，不引入前端框架
- 样式内联 `<style>` 块 — 不引入独立 CSS 文件，保持模板自包含
- 所有动态数据通过 `fetch()` + async/await 获取
- Markdown 渲染使用 marked.js CDN（用于 llm_summary 渲染）

### 2. 数据加载策略
- **服务端渲染（SSR）**：页面初始加载时，路由传递基础数据（event 对象、is_admin、subscriptions）
- **客户端懒加载（CSR）**：Tab 数据（micro/macro/info/trend）通过 JS 按需 fetch，缓存到模块级变量
- 顶部摘要栏使用 SSR 数据，无需额外 API 调用

### 3. 配色体系
遵循 Compass 主应用：
| 用途 | 色值 |
|------|------|
| 侧边栏背景 | `#001529` |
| 侧边栏文字 | `rgba(255,255,255,0.65)` |
| 侧边栏高亮 | `#1890FF` |
| 主内容区背景 | `#F0F2F5` |
| 卡片背景 | `#FFFFFF` |
| 成功/跟踪 | `#52C41A` |
| 警告/建议关闭 | `#FAAD14` |
| 错误/关闭 | `#FF4D4F` |
| 文字主色 | `rgba(0,0,0,0.85)` |
| 文字次色 | `rgba(0,0,0,0.45)` |

## 数据流

### 策略发现页
```
用户访问 /strategy/discover
  → route handler 渲染模板（is_admin, user_name）
  → JS: fetch GET /api/strategy/groups → 卡片网格
  → JS: fetch GET /api/strategy/subscriptions → 标记已订阅状态
  → 用户点击订阅 → JS: POST /api/strategy/subscribe → 更新按钮状态
```

### 事件详情页
```
用户访问 /strategy/events/{id}
  → route handler: 查询 event + strategy_group → SSR 渲染摘要栏
  → JS: 默认加载微观 Tab → fetch GET /api/events/{id}/micro
  → 用户切换 Tab → 懒加载对应 API → 缓存数据
  → 信息 Tab: fetch GET /api/events/{id}/info + GET /api/events/{id}/trend
```

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `compass/templates/strategy/base.html` | MODIFIED | 完整重写：Compass 风格侧边栏 + 用户栏 + ECharts CDN + 全局辅助函数 |
| `compass/templates/strategy/discover.html` | MODIFIED | 策略卡片网格 + 订阅交互 JS |
| `compass/templates/strategy/my_strategies.html` | MODIFIED | 策略组概览卡片 + 事件卡片 lifecycle 标签 + 点击导航 |
| `compass/templates/strategy/event_detail.html` | MODIFIED | 三维度 Tab + LLM 分析展示 + ECharts 图表 + 关闭按钮 |
| `compass/templates/strategy/admin_list.html` | MODIFIED | Compass 风格表格 + 操作按钮 |
| `compass/templates/strategy/admin_edit.html` | MODIFIED | Compass 风格表单 |
| `compass/strategy/routes/strategy_pages.py` | MODIFIED | 增强模板上下文数据（is_admin, event 完整字段） |

## 关键实现模式

### 全局辅助函数（base.html）
```javascript
async function fetchJSON(url, options = {}) {
  const resp = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

function renderLifecycleBadge(lifecycle) {
  const map = {
    tracking: {color: '#52C41A', text: '跟踪中'},
    suggest_close: {color: '#FAAD14', text: '建议关闭'},
    closed: {color: '#999', text: '已关闭'}
  };
  const cfg = map[lifecycle] || {color: '#999', text: lifecycle};
  return `<span style="background:${cfg.color}22;color:${cfg.color};padding:2px 8px;border-radius:4px;font-size:12px">${cfg.text}</span>`;
}
```

### Tab 懒加载模式（event_detail.html）
```javascript
const tabCache = {micro: null, macro: null, info: null};
async function switchTab(tab) {
  if (tabCache[tab] === null) {
    tabCache[tab] = await fetchJSON(`/api/events/${eventId}/${tab}`);
  }
  renderTab(tab, tabCache[tab]);
}
```

### Markdown 渲染
```html
<!-- 使用 marked.js CDN -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<div id="llm-summary"></div>
<script>
document.getElementById('llm-summary').innerHTML = marked.parse(summaryText);
</script>
```

## 前端任务说明

⚠️ **所有模板文件修改均为前端任务（scope: frontend）**，需要人工完成 UI 渲染。
唯一的后端任务是 `strategy_pages.py` 路由数据传递增强。
