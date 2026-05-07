# Delta Spec: 每日推荐股票 API

## ADDED Requirements

### REQ-REC-001: 每日推荐列表 API

系统 SHALL 提供 `GET /api/recommendation/daily` 端点，返回当日推荐股票列表。

#### Scenario: 正常获取推荐列表

- **Given** 系统已完成当日数据更新（调度任务执行完毕）
- **When** 客户端发送 `GET /api/recommendation/daily`
- **Then** 响应状态码为 200，body 包含 `recommendations` 数组，每条记录包含 `stock_code`、`stock_name`、`score`、`rank`、`reason`、`risk_warning`、`recommendation_date` 字段
- **And** 列表按 `score` 降序排列，默认最多返回 20 条

#### Scenario: 无当日推荐数据时返回空列表

- **Given** 当日尚未执行推荐计算
- **When** 客户端发送 `GET /api/recommendation/daily`
- **Then** 响应状态码为 200，`recommendations` 为空数组，`generated_at` 为 null

#### Scenario: 支持分页和数量限制

- **Given** 当日已有推荐数据
- **When** 客户端发送 `GET /api/recommendation/daily?limit=10&offset=0`
- **Then** 返回最多 10 条记录，从排名最高的开始
- **And** 响应包含 `total` 字段表示总推荐数量

---

### REQ-REC-002: 推荐评分引擎

系统 SHALL 基于多维指标计算综合推荐评分（0-100 分）。

评分维度与权重：

| 维度 | 权重 | 数据来源 |
|------|------|----------|
| 技术指标信号 | 40% | stock_analysis 表的 buy_advice JSON |
| 趋势动量 | 25% | stock_data_daily 近期涨跌幅、MA 排列 |
| 基本面质量 | 20% | dic_stock 的 PE、PB、市值、换手率 |
| 量价配合 | 15% | 成交量变化率、换手率异动 |

#### Scenario: 技术指标维度评分

- **Given** stock_analysis 表中存在某股票当日 buy_advice 数据
- **When** 评分引擎计算技术指标分数
- **Then** buy 信号数量越多，得分越高；sell 信号数量越多，得分越低
- **And** 分数归一化到 0-100 区间

#### Scenario: 趋势动量维度评分

- **Given** stock_data_daily 表中存在某股票近 20 日行情数据
- **When** 评分引擎计算趋势动量分数
- **Then** MA5 > MA10 > MA20 > MA30 多头排列时得高分
- **And** 近 5 日涨跌幅为正且在合理范围（非暴涨）时加分

#### Scenario: 基本面质量维度评分

- **Given** dic_stock 表中存在某股票的最新基本面数据
- **When** 评分引擎计算基本面分数
- **Then** PE 在 10-30 区间加分，PB 在 1-3 区间加分
- **And** 排除 ST 股票、PE 为负的股票

#### Scenario: 量价配合维度评分

- **Given** stock_data_daily 表中存在某股票近 10 日成交量和价格数据
- **When** 评分引擎计算量价配合分数
- **Then** 价格上涨且成交量放大时得高分
- **And** 价格下跌且成交量萎缩时得中等分数

---

### REQ-REC-003: 推荐理由与风险提示生成

系统 SHALL 为每只推荐股票生成推荐理由文本和风险提示文本。

#### Scenario: 生成推荐理由

- **Given** 评分引擎已完成某股票的各维度评分
- **When** 系统生成推荐理由
- **Then** 推荐理由 SHALL 包含：得分最高的维度名称、关键指标数值、主要买入信号名称
- **And** 推荐理由为中文自然语言文本，不超过 200 字

#### Scenario: 生成风险提示

- **Given** 评分引擎已完成某股票的各维度评分
- **When** 系统生成风险提示
- **Then** 风险提示 SHALL 包含：得分最低维度的风险描述、是否为高风险标的（如 ST、涨跌幅超 5%）
- **And** 风险提示为中文自然语言文本，不超过 200 字

---

### REQ-REC-004: 定时计算调度

系统 SHALL 在每日数据更新完成后自动触发推荐计算。

#### Scenario: 调度触发

- **Given** 调度器配置了推荐计算任务
- **When** DailyAnalysisTask 执行完毕后
- **Then** 推荐计算任务 SHALL 自动启动
- **And** 计算结果写入 `daily_recommendation` 数据库表

#### Scenario: 手动触发

- **Given** 管理员已登录
- **When** 发送 `POST /api/recommendation/generate`
- **Then** 系统立即执行推荐计算
- **And** 返回本次生成的推荐数量和耗时

---

### REQ-REC-005: 推荐历史查询

系统 SHALL 提供历史推荐查询能力。

#### Scenario: 按日期查询历史推荐

- **Given** 数据库中存在历史推荐记录
- **When** 客户端发送 `GET /api/recommendation/daily?date=2025-01-20`
- **Then** 返回指定日期的推荐列表，结构与当日推荐一致

#### Scenario: 推荐效果回溯

- **Given** 历史推荐记录存在且对应日期之后有行情数据
- **When** 客户端发送 `GET /api/recommendation/performance?date=2025-01-20`
- **Then** 每条推荐记录包含 `actual_change_1d`（次日涨跌幅）、`actual_change_5d`（5日涨跌幅）字段
- **And** 响应包含整体统计信息：平均涨跌幅、胜率（上涨占比）

---

### REQ-REC-006: 排除规则

推荐引擎 SHALL 排除不符合条件的股票。

#### Scenario: 排除 ST 股票

- **Given** dic_stock 中某股票名称包含 "ST"
- **When** 推荐引擎筛选候选股票
- **Then** 该股票 SHALL 被排除

#### Scenario: 排除流动性不足的股票

- **Given** 某股票当日成交额低于 5000 万或换手率低于 0.5%
- **When** 推荐引擎筛选候选股票
- **Then** 该股票 SHALL 被排除

#### Scenario: 排除涨跌幅异常的股票

- **Given** 某股票当日涨跌幅超过 9.5% 或低于 -9.5%
- **When** 推荐引擎筛选候选股票
- **Then** 该股票 SHALL 被排除
