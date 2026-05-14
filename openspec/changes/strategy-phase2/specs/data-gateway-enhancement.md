# Delta Spec: DataGateway 资讯搜索增强

## ADDED Requirements

### REQ-DG-001: 关键词列表搜索资讯

`DataAgentFetcher` SHALL 支持按关键词列表搜索资讯，返回匹配的资讯列表和相关性信息。

#### Scenario: 多关键词搜索返回匹配资讯

- **Given** DataAgent 服务正常运行（localhost:8000）
- **When** 调用 `search_news_by_keywords(keywords=["半导体", "AI芯片"], limit=20)`
- **Then** 系统 SHALL 遍历所有 track 的 news，对每条 news 的 title + content 做关键词匹配
- **And** 返回按相关度排序的资讯列表，每条包含 `title`、`source`、`date`、`relevance`（匹配度评分）、`matched_keyword`（命中的关键词）

#### Scenario: 空关键词列表

- **Given** 调用 `search_news_by_keywords(keywords=[])`
- **When** 执行搜索
- **Then** 系统 SHALL 返回空列表，不发起任何 HTTP 请求

#### Scenario: DataAgent 服务不可用

- **Given** DataAgent 服务无响应或返回错误
- **When** 执行关键词搜索
- **Then** 系统 SHALL 记录 warning 日志并返回空列表，不抛出异常
