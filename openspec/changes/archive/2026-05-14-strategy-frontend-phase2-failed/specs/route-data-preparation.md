# Delta Spec: 路由数据准备增强

## MODIFIED Requirements

### Requirement: 事件详情页模板数据传递

strategy_pages.py 中的事件详情路由 SHALL 将完整的 LLM 分析数据和 lifecycle 状态传递给模板，避免前端额外请求已知的摘要信息。

#### Scenario: 事件详情路由传递 LLM 摘要数据

```
Given 事件 ID=42 存在，且有 llm_summary, llm_confidence, llm_keywords 等字段
When 服务端渲染 /strategy/events/42 页面
Then 模板上下文包含 event 对象，其中包含：
  - event.lifecycle
  - event.llm_summary
  - event.llm_confidence
  - event.news_confirmed
  - event.news_confirm_score
  - event.buy_star
  - event.dimension_value
  - event.strategy_name
And 模板可直接使用这些值渲染顶部摘要栏，无需 JS 额外请求
```

### Requirement: 策略发现页传递用户角色

strategy_pages.py 中的策略发现和我的策略路由 SHALL 将 `is_admin` 标志传递给模板，用于控制管理员专属 UI 元素的显示。

#### Scenario: 模板接收 is_admin 标志

```
Given 用户为管理员
When 服务端渲染策略发现页
Then 模板上下文包含 is_admin=True
And 模板可据此决定是否显示管理员专属导航
```
