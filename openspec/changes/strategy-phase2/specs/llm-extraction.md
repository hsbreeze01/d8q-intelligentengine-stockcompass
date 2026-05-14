# Delta Spec: LLM 特征提取与消息面确认

## ADDED Requirements

### REQ-LLM-001: 群体事件自动触发 LLM 分析

当一个新的群体事件（`group_event`）被聚合器创建后，系统 SHALL 自动启动三阶段 LLM 分析链路：Doubao 结构化分析 → 关键词搜索确认 → DeepSeek 深度摘要。

#### Scenario: 新群体事件创建后自动触发分析

- **Given** 聚合器检测到群体信号并创建了一条 `group_event` 记录
- **When** 该记录成功写入数据库
- **Then** 系统 SHALL 异步启动 LLM 分析流程，不阻塞聚合器主流程

#### Scenario: LLM 分析链路三阶段执行顺序

- **Given** 一个 `group_event` 已创建并触发 LLM 分析
- **When** 分析流程启动
- **Then** 系统 SHALL 按顺序执行：① Doubao 结构化分析 → ② 关键词搜索确认 → ③ DeepSeek 深度摘要

---

### REQ-LLM-002: Doubao 结构化分析

系统 SHALL 使用 DoubaoLLM 对群体事件上下文进行结构化分析，提取事件类型、置信度、关键词、驱动因素和关联主题。

#### Scenario: 结构化分析正常完成

- **Given** 群体事件的上下文数据（触发股票列表 + 指标快照 + 行业信息 + 价格走势）已组装
- **When** 调用 DoubaoLLM 进行结构化分析
- **Then** 系统 SHALL 输出包含以下字段的 JSON：`event_type`、`confidence`（0-1）、`keywords`（关键词列表）、`possible_drivers`（驱动因素列表）、`related_themes`（关联主题列表）

#### Scenario: DoubaoLLM 调用失败

- **Given** DoubaoLLM 服务不可用或返回错误
- **When** 结构化分析阶段执行
- **Then** 系统 SHALL 记录 warning 日志，不阻塞后续阶段，`structured` 字段标记为 `null`

---

### REQ-LLM-003: 关键词搜索确认

系统 SHALL 使用 Doubao 提取的关键词通过 DataGateway 搜索资讯库，计算消息面确认度评分。

#### Scenario: 关键词匹配资讯并计算确认度

- **Given** Doubao 结构化分析输出了 `keywords` 列表
- **When** 系统使用关键词搜索 DataAgent 资讯库
- **Then** 系统 SHALL 返回匹配资讯列表（`news_matched`）和确认度评分（`news_confirm_score`，0-1）

#### Scenario: 关键词为空时跳过搜索

- **Given** Doubao 结构化分析未输出有效关键词
- **When** 进入关键词搜索阶段
- **Then** 系统 SHALL 跳过搜索，`news_matched` 为空列表，`news_confirm_score` 为 0

---

### REQ-LLM-004: DeepSeek 深度摘要生成

系统 SHALL 使用 DeepSeekLLM 基于结构化分析和资讯搜索结果生成可读的事件分析摘要。

#### Scenario: 摘要生成正常完成

- **Given** 结构化分析和关键词搜索结果已就绪
- **When** 调用 DeepSeekLLM 生成摘要
- **Then** 系统 SHALL 输出 `llm_summary` 字符串，包含对群体事件的综合分析

#### Scenario: DeepSeekLLM 调用失败

- **Given** DeepSeekLLM 服务不可用或返回错误
- **When** 摘要生成阶段执行
- **Then** 系统 SHALL 记录 warning 日志，`llm_summary` 标记为 `null`，不影响已完成的阶段结果

---

### REQ-LLM-005: LLM 分析结果持久化

系统 SHALL 将 LLM 分析的所有结果写入 `group_event` 表的对应字段。

#### Scenario: 分析结果写入数据库

- **Given** 三阶段分析链路执行完成（无论各阶段是否成功）
- **When** 结果准备就绪
- **Then** 系统 SHALL 更新 `group_event` 记录的以下字段：`llm_keywords`、`llm_summary`、`llm_confidence`、`llm_drivers`、`llm_related_themes`、`news_confirmed`、`news_confirm_score`、`news_matched`

#### Scenario: 部分阶段失败时的持久化

- **Given** 分析链路中某阶段失败（如 Doubao 超时）
- **When** 将已有结果写入数据库
- **Then** 系统 SHALL 仅更新成功阶段的字段，失败阶段对应字段保持 `null`
