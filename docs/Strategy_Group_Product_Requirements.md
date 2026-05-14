# Compass 策略组引擎 — 产品需求与设计规划

> 文档版本: v1.4 | 日期: 2026-05-14 | 状态: 需求规划
> v1.4: 角色分流（Admin/Editor 策略管理 vs User 发现/订阅/跟踪）+ 事件详情三维度（微观/宏观/信息关联）+ 订阅机制
> v1.3: 策略层级升级（2层结构）+ 趋势跟踪纳入核心闭环 + 日级别为主 + 资讯持续关联 + 生命周期管理 + 事件跟踪页
> v1.2: 移除 F6 趋势阶段跟踪 + F7 动态采集密度（内部沟通后决定暂不实现）
> v1.1: 新增 §11 数据支撑评估（服务器实地调研）
> 前置文档: [高端用户需求规划](./d8q-premium-user-requirements.md) | [交互设计稿](./d8q-interaction-design.md)
> 项目仓库: root@47.99.57.152:/home/ecs-assist-user/d8q-intelligentengine-stockcompass

---

## 目录

1. [产品愿景](#1-产品愿景)
2. [核心概念](#2-核心概念)
3. [用例故事](#3-用例故事)
4. [功能需求](#4-功能需求)
5. [数据模型设计](#5-数据模型设计)
6. [计算流程设计](#6-计算流程设计)
7. [架构方案](#7-架构方案)
8. [现有能力盘点](#8-现有能力盘点)
9. [实施路径](#9-实施路径)
10. [术语表](#10-术语表)
11. [数据支撑评估](#11-数据支撑评估)

---

## 1. 产品愿景

### 1.1 一句话描述

**从个股指标信号出发，通过群体性事件检测、LLM 智能特征提取与消息面确认，实现对行业/主题趋势的日级别捕捉、持续跟踪与生命周期管理。**

### 1.2 核心价值主张

| 维度 | 现状（手动） | 目标（自动化） |
|------|------------|--------------|
| **信号发现** | 投资经理逐只翻看个股分析 | 系统自动扫描全市场，日级别推送群体信号 |
| **关联分析** | 人脑关联"这几只半导体同时翻转了" | 系统自动聚合行业/主题共振事件 |
| **消息确认** | 手动搜索新闻验证判断 | LLM 提取特征词 → 持续关联维度资讯采集 |
| **趋势跟踪** | 凭经验判断"这波行情到什么阶段了" | 确立趋势后每日统计跟踪，指标线聚合 |

### 1.3 目标用户

- **Admin/Editor（内部业务人士）** — 设计策略、配置参数、管理启停、管理生命周期。当前限管理员或 editor 用户，暂不开放给外部用户
- **普通用户** — 浏览策略、订阅策略、查看已订阅策略的事件、查看微观/宏观/信息关联
- **一级市场投资经理** — 跟踪赛道热度，发现一二级联动机会
- **二级市场分析师** — 捕捉行业轮动信号，发现板块共振
- **投后管理人员** — 监控 portfolio 公司所在行业的事件驱动

---

## 2. 核心概念

### 2.1 概念关系图

```
┌────────────┐      选择      ┌────────────┐      组合      ┌────────────┐
│  技术指标   │ ─────────────→ │  策略组     │ ─────────────→ │  信号快照   │
│  KDJ/RSI/  │               │  用户自定义  │               │  单只股票的  │
│  BOLL/MA…  │               │  指标组合    │               │  触发记录    │
└────────────┘               └────────────┘               └──────┬─────┘
                                                                   │ 聚合
                                                                   ▼
                                                           ┌────────────┐
                                                           │  群体事件   │
                                                           │  同行业/主题 │
                                                           │  多股共振    │
                                                           └──────┬─────┘
                                                                  │ LLM 分析
                                                                  ▼
┌────────────┐      确认      ┌────────────┐      提取      ┌────────────┐
│  消息面     │ ←──────────── │  特征关键词  │ ←──────────── │  LLM 特征   │
│  政策/新闻  │               │  LLM 抽取   │               │  提取器      │
│  研报      │               │             │               │             │
└────────────┘               └────────────┘               └────────────┘
```

### 2.2 核心概念定义

| 概念 | 定义 | 示例 |
|------|------|------|
| **技术指标** | Compass 已实现的 8 类指标（KDJ/MACD/RSI/BOLL/MA/ASI/BIAS/VR）+ 综合决策引擎 `buy_advice_v2()` | KDJ 金叉、RSI<30 超卖、BOLL 破下轨 |
| **策略** | 单个指标因子的逻辑组合，配置触发条件和权重，是策略组的组成单元 | "RSI超卖反弹"：RSI<30 AND 量比>1.5 |
| **策略组** | 用户从多个策略中选择组合，配置信号规则（买入/卖出阈值）、聚合规则、扫描频率，形成可复用的信号检测规则集 | "底部共振策略组"：RSI超卖(1.0) + MACD金叉(1.2) + 量价突破(0.8)，≥3个同时命中 |
| **信号快照** | 单只股票在某个时刻触发了某个策略组的条件，记录当时的指标值和评分 | "2026-05-12 600036 触发底部反转策略，buy_star=53000" |
| **群体事件** | 在有效时间窗口内，同一行业/主题的多只股票同时触发信号，形成群体性共振 | "半导体行业 3 日内 8 只股票同时触发底部反转信号" |
| **维度主题** | 由群体事件确立的行业/主题趋势方向，关联持续采集的资讯信息，形成趋势分析和跟踪 | "半导体底部反转"主题，关联AI芯片、国产芯片、先进制程等维度 |
| **特征关键词** | LLM 从群体事件中提取的描述性关键词，用于后续搜索消息面确认 | "半导体国产替代"、"先进封装产能扩张"、"AI芯片需求激增" |
| **消息面确认** | 使用特征关键词搜索 DataAgent 的资讯库，确认消息面是否支持信号方向 | 搜索到"国家大基金三期注资半导体"——政策面利好确认 |
| **事件跟踪** | 群体事件确立后的持续跟踪过程：每日统计触发股票变化、指标趋势聚合、关联资讯采集，直至信号衰减后关闭 | 半导体事件连续跟踪5天，15→13→10只股票变化 |

---

## 3. 用例故事

### 用例 1：创建策略组

**主角**：张明，一级市场投资经理，关注半导体赛道

**故事**：

张明最近发现，当多只半导体股票同时出现 KDJ 低位金叉 + RSI 超卖 + 放量的组合信号时，往往预示着整个半导体板块即将反弹。过去他靠逐只翻看股票来判断，效率很低。

现在他打开 Compass 策略组配置页面：

1. **创建策略**：他先从指标库中创建几个策略单元
   - "RSI 超卖反弹"：RSI_6 < 30，权重 1.0
   - "MACD 金叉"：DIF > DEA，权重 1.2
   - "成交量异动"：量比 > 1.5，权重 0.8

2. **组合策略组**：将以上 3 个策略加入"底部共振策略组"
   - 买入阈值：≥ 3 个策略同时命中
   - 冷却期：同一股票 5 个交易日内不重复信号

3. **配置聚合规则**：同一行业 3 日内 ≥ 3 只股票触发 = 群体事件

4. **扫描频率**：日级别（每个交易日收盘后）

5. **命名保存**："底部共振策略 v1"

系统验证策略语法，保存到数据库，状态为"已激活"。

**验收标准**：
- 策略组保存后可在列表页看到
- 条件编辑器支持 AND/OR/SCORING 三种组合模式
- 可随时启停策略组
- 可查看策略组的历史触发统计

---

### 用例 2：盘中信号捕捉与群体事件聚合

**主角**：系统自动执行（基于张明的策略组，日级别扫描）

**故事**：

5 月 12 日收盘后，策略引擎执行日级别扫描：

1. **信号扫描**：引擎从 `indicators_daily` + `stock_data_daily` 读取最新数据，按"底部共振策略 v1"的条件逐只匹配。发现 12 只股票同时满足条件。

2. **行业聚合**：按 `dic_stock.industry` 分组，发现其中 5 只属于"半导体"行业，触发时间均在近 3 日内。满足"同行业 ≥ 3 只"的聚合规则。

3. **创建群体事件**：
   ```
   事件ID: evt_20260512_001
   类型: industry_reversal（行业底部反转）
   目标: 半导体
   触发股票: ["002049", "300666", "688981", "603501", "300316"]
   平均星级: 42,000
   ```

4. **推送通知**：张明收到 Compass App 推送——"🚨 半导体板块底部共振信号（5只股票触发）"

**验收标准**：
- 扫描周期可配置（daily 默认，支持手动触发）
- 聚合时间窗口可配置（1d/3d/5d）
- 聚合维度可选（行业/概念/主题/自选股集合）
- 信号产生后当日内推送通知

---

### 用例 3：LLM 特征提取与消息面确认

**主角**：系统自动执行 → 张明查看确认结果及持续资讯关联

**故事**：

群体事件 `evt_20260512_001` 创建后，系统自动启动 LLM 分析链路：

1. **数据准备**：系统将 5 只触发股票的近期指标数据、价格走势、行业信息打包成分析上下文。

2. **Doubao 结构化分析**（快速）：
   - 输入：5 只半导体股票的指标快照 + 近 5 日行情
   - 输出 JSON：
     ```json
     {
       "event_type": "industry_bottom_reversal",
       "confidence": 0.78,
       "keywords": ["半导体", "先进封装", "国产替代", "AI芯片"],
       "possible_drivers": ["大基金三期注资预期", "AI算力需求拉动"],
       "related_themes": ["人工智能", "国产芯片", "先进制程"]
     }
     ```

3. **关键词搜索确认**：系统用提取的关键词搜索 DataAgent 资讯库：
   - "大基金三期" → 找到 3 条相关新闻（4/28 财联社报道）
   - "AI芯片需求" → 找到 7 条相关新闻（多源）
   - "先进封装" → 找到 2 条研报提及
   - 政策面：搜索到"工信部集成电路产业推进会"相关报道

4. **DeepSeek 深度分析**（生成可读摘要）：
   > "半导体板块出现底部共振信号。5只个股（紫光国微、江丰电子、中芯国际、韦尔股份、晶盛机电）在近3日内同步触发KDJ低位金叉+RSI超卖+放量组合。消息面确认：大基金三期注资预期升温、AI算力需求持续拉动芯片出货量。建议重点关注先进封装和AI芯片方向。"

5. **张明查看**：他打开事件跟踪页面，看到：
   - 信号概览（5只股票的指标快照卡片）
   - LLM 分析摘要（DeepSeek 生成）
   - 消息面确认度（3/3 关键词有新闻支撑，标记为 ✅ 已确认）
   - 关联行业/主题列表
   - **关联资讯流**（持续采集，每日按关键词匹配追加相关资讯，按相关性排序）

6. **持续资讯关联**：事件确立后，系统每日用关键词 + 维度主题搜索 DataAgent 新增资讯：
   - 05-13 新增：AI芯片出货量Q2环比+40%（相关性 0.78）
   - 05-14 新增：大基金三期注资预期升温（相关性 0.85）
   - 资讯持续累积直到事件关闭

**验收标准**：
- LLM 分析在群体事件创建后 60 秒内完成
- 关键词搜索覆盖 DataAgent 全部资讯源
- 消息面确认结果可视化（确认度评分、相关新闻列表）
- 确认后事件状态自动推进到"跟踪中"
- **持续资讯关联**：事件跟踪期间每日自动按关键词匹配新增资讯，在事件跟踪页展示

---

### 用例 4：从群体事件到关联股票集合的扩展

**主角**：张明，基于确认的群体事件扩展关注范围

**故事**：

半导体底部共振事件确认后，张明想了解还有哪些相关股票值得关注：

1. **关联股票发现**：系统基于触发股票的 `stock_concept`（概念板块）和 `industry`（行业），自动扩展关联股票集合：
   - 触发股票共同关联的概念：AI芯片（12只）、先进封装（8只）、国产替代（15只）
   - 合并去重后得到 28 只关联股票

2. **关联股票评分**：系统对 28 只关联股票运行同一策略组：
   - 12 只也满足部分条件（2/3 指标触发）
   - 5 只完全满足条件但不在原始聚合范围内（不同细分行业）

3. **行业/主题趋势映射**：系统将群体事件与 Compass 已有的赛道系统（tracks）关联：
   - "半导体" → 映射到 "芯片/半导体" 赛道
   - 自动将该赛道的趋势热度提升
   - 在赛道 Dashboard 上标记"🚀 信号确认"

4. **张明操作**：
   - 一键将关联股票加入自选股
   - 事件自动进入"跟踪中"状态，系统每日统计跟踪
   - 当系统判定信号衰减（连续2日均值评分低于0.5），标记为"建议关闭"
   - 张明在事件跟踪页看到建议后，点击"确认关闭"结束跟踪
   - 关闭后资讯采集停止，已采集数据保留可查

**验收标准**：
- 自动扩展关联股票集合（基于行业/概念/主题）
- 关联股票有评分排序（完全匹配 > 部分匹配 > 概念关联）
- 可一键加入自选股
- 与赛道系统联动（热度提升）
- 支持设定跟踪提醒

---

### 用例 5：策略组回测与效果评估

**主角**：张明，验证策略组的有效性

**故事**：

张明创建策略组后想先看历史表现：

1. **选择回测参数**：
   - 策略组："底部共振策略 v1"
   - 时间范围：2025-01-01 ~ 2026-05-12
   - 聚合维度：行业，阈值 ≥ 3 只
   - 对比基准：沪深300

2. **回测结果**：
   ```
   历史触发次数: 47 次群体事件
   平均持续天数: 6.3 天
   平均板块涨幅: +8.7%
   胜率: 72.3%（34/47 次确认后上涨）
   最大涨幅: +23.1%（2025-09 新能源汽车）
   最大回撤: -4.2%（2025-11 地产，假信号）
   确认后5日胜率: 78.4%
   加速期平均涨幅: +5.6%
   顶部预警准确率: 65.2%（15/23 次成功预警）
   ```

3. **张明调整**：基于回测结果，他决定：
   - 将聚合阈值从 3 只提高到 4 只（提高信号质量）
   - 添加 MACD 辅助确认条件（降低假信号）
   - 重新回测验证改善效果

**验收标准**：
- 支持任意时间范围回测
- 输出关键统计指标（胜率/平均涨幅/持续天数）
- 支持与基准指数对比
- 可基于回测结果调整策略参数并重新回测
- 回测结果可导出为报告

---

### 用例 6：日常监控仪表盘

**主角**：张明，每日打开系统查看全局状态

**故事**：

张明早上 8:30 打开 Compass 策略组仪表盘，一眼看到：

1. **信号概览卡片**（顶部）：
   - 当前活跃群体事件：3 个
   - 今日新信号：12 个
   - 待确认事件：1 个
   - 进入顶部预警：0 个

   2. **群体事件列表**（中部）：
    | 行业 | 触发股票 | 确认度 | 信号时间 | 最新变化 |
    |------|---------|--------|---------|---------|
    | 半导体 | 15只 | ✅✅✅ | 5/12 | +3.2% |
    | 新能源 | 5只 | ✅✅ | 5/12 | +1.1% |
    | 医药 | 4只 | ✅ | 5/13 | -0.3% |

3. **行业热力图**（右侧）：
   - X轴：行业，Y轴：策略组
   - 颜色深度：触发信号密度
   - 点击下钻到具体事件

   4. **信号时间线**（底部）：
    - 半导体事件的完整信号时间线
    - 每个节点标注关键数据（涨跌幅/新增信号/消息面）

   5. **LLM 早报**（左下角）：
    > "今日重点关注：半导体板块群体信号确认，新能源获政策确认。医药板块出现底部信号，等待消息面验证。"

**验收标准**：
- 页面加载 < 3 秒
- 信号数据自动刷新（SSE 推送，无需手动刷新）
- 支持按行业/阶段/日期筛选
- 热力图可点击下钻
- LLM 早报每日 8:00 自动生成

---

## 4. 功能需求

### 4.1 功能清单

| # | 功能 | 优先级 | 描述 | 角色 |
|---|------|--------|------|------|
| F1 | 策略组管理 | P0 | 创建/编辑/删除/启停策略组，2层结构（策略→策略组），配置指标选择和触发条件 | Admin |
| F2 | 信号扫描引擎 | P0 | 按策略组规则批量扫描全市场股票，日级别扫描，生成信号快照 | 系统 |
| F3 | 群体事件聚合 | P0 | 按行业/主题/概念分组，检测群体性共振事件 | 系统 |
| F4 | LLM 特征提取 | P0 | Doubao 结构化分析 + DeepSeek 深度摘要，提取关键词 | 系统 |
| F5 | 消息面确认 | P0 | 用关键词搜索 DataAgent 资讯，量化确认度 | 系统 |
| F6 | 趋势跟踪（日级别） | P0 | 确立趋势后每日统计跟踪：触发股票变化、指标趋势聚合、综合评分演进 | 系统 |
| F7 | 资讯持续关联 | P0 | 事件跟踪期间每日按关键词+维度主题匹配新增资讯，在事件跟踪页展示 | 系统 |
| F8 | 关联股票扩展 | P1 | 基于行业/概念自动扩展关联股票集合 | 系统 |
| F9 | 策略组回测 | P1 | 历史数据回放，统计策略组有效性 | Admin |
| F10 | 策略发现与订阅 | P0 | 用户浏览公开策略组，一键订阅/取消订阅 | User |
| F11 | 我的策略 | P0 | 用户查看已订阅策略列表，展示策略下的事件入口 | User |
| F12 | 事件详情（微观） | P0 | 展示触发个股的指标快照（KDJ/RSI/量比/MACD/涨跌幅/buy_star） | User |
| F13 | 事件详情（宏观） | P0 | 展示板块/行业趋势聚合图 + 每日跟踪统计表 | User |
| F14 | 事件详情（信息关联） | P0 | LLM 分析摘要 + 关键词 + 驱动因素 + 持续采集的资讯流 | User |
| F15 | 事件推送通知 | P1 | 新事件/建议关闭等推送 | User |
| F16 | 事件复盘报告 | P2 | 事件结束后自动生成复盘分析 | Admin |
| F17 | 生命周期管理 | P0 | 自动跟踪→自动建议关闭→管理员确认关闭，资讯采集跟随生命周期 | Admin |

### 4.2 非功能需求

| 维度 | 要求 |
|------|------|
| **信号延迟** | 从收盘数据入库到信号检测完成 < 60 秒 |
| **扫描吞吐** | 全市场（~5500只股票）单次日级别扫描 < 30 秒 |
| **LLM 响应** | 特征提取 + 消息面搜索全链路 < 90 秒 |
| **前端实时性** | 信号推送 SSE 延迟 < 5 秒 |
| **并发** | 支持 10 个策略组同时运行 |
| **数据保留** | 信号快照保留 90 天，群体事件永久保留 |
| **可用性** | 99.5%（允许盘中偶发短时中断） |

---

## 5. 数据模型设计

### 5.1 ER 关系

```
strategy_group 1──N signal_snapshot N──1 group_event
                     │                      │
                     │                      └──N group_event_keyword
                     │
                     └──1 dic_stock (stock_code)
```

### 5.2 表结构

#### 5.2.1 strategy_group（策略组）

```sql
CREATE TABLE strategy_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '策略组名称',
    description TEXT COMMENT '策略描述',
    
    -- 指标配置
    indicators JSON NOT NULL COMMENT '选择的指标及触发条件',
    -- 示例: {
    --   "kdj": {"params": [9,3,3], "conditions": ["cross_golden", "k<30"]},
    --   "rsi": {"params": [6,12,24], "conditions": ["rsi_6<30"]},
    --   "volume": {"conditions": ["volume_ratio>1.5"]}
    -- }
    
    -- 信号逻辑
    signal_logic JSON NOT NULL COMMENT '信号触发逻辑',
    -- 示例: {
    --   "type": "AND",           -- AND / OR / SCORING
    --   "min_signals": 3,        -- SCORING 模式下最少命中指标数
    --   "scoring_weights": {}    -- SCORING 模式下各指标权重
    -- }
    
    -- 聚合规则
    aggregation JSON NOT NULL COMMENT '群体事件聚合规则',
    -- 示例: {
    --   "dimension": "industry",  -- industry / concept / theme / custom
    --   "min_stocks": 3,          -- 最少共振股票数
    --   "time_window_days": 3     -- 时间窗口（天）
    -- }
    
    -- 扫描配置
    scan_frequency ENUM('1min','5min','15min','daily') DEFAULT 'daily',
    
    -- 状态
    status ENUM('active','paused','archived') DEFAULT 'active',
    
    -- 统计
    total_signals INT DEFAULT 0 COMMENT '历史触发总次数',
    total_events INT DEFAULT 0 COMMENT '历史群体事件数',
    last_scan_at DATETIME COMMENT '最后扫描时间',
    
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_scan (scan_frequency, status)
) ENGINE=InnoDB COMMENT='策略组配置';
```

#### 5.2.2 signal_snapshot（信号快照）

```sql
CREATE TABLE signal_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    signal_time DATETIME NOT NULL COMMENT '信号触发时间',
    
    -- 信号分类
    signal_type VARCHAR(50) COMMENT 'reversal/breakout/golden_cross/oversold',
    
    -- 触发时的指标快照
    indicator_values JSON NOT NULL COMMENT '触发时刻各指标的具体值',
    -- 示例: {
    --   "kdj_k": 25.3, "kdj_d": 22.1, "kdj_j": 31.7,
    --   "rsi_6": 28.5, "rsi_12": 35.2,
    --   "volume_ratio": 2.1, "close": 45.6, "change_pct": 3.2
    -- }
    
    -- 综合评分
    buy_star INT COMMENT 'buy_advice_v2 的星级评分',
    buy_count INT COMMENT '买入信号数',
    sell_count INT COMMENT '卖出信号数',
    
    -- 股票归属
    industry VARCHAR(50) COMMENT '行业',
    concept VARCHAR(200) COMMENT '概念板块（逗号分隔）',
    
    -- 群体事件关联（后续聚合时填入）
    group_event_id BIGINT COMMENT '关联的群体事件ID',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_strategy_time (strategy_group_id, signal_time),
    INDEX idx_stock (stock_code, signal_time),
    INDEX idx_industry (industry, signal_time),
    INDEX idx_event (group_event_id)
) ENGINE=InnoDB COMMENT='信号快照';
```

#### 5.2.3 group_event（群体事件）

```sql
CREATE TABLE group_event (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    
    -- 事件标识
    event_date DATETIME NOT NULL COMMENT '事件创建时间',
    event_type VARCHAR(50) NOT NULL COMMENT 'industry_reversal/theme_breakout/concept_surge',
    
    -- 聚合目标
    target_type ENUM('industry','concept','theme','custom') NOT NULL,
    target_name VARCHAR(100) NOT NULL COMMENT '行业/主题/概念名称',
    
    -- 群体数据
    stock_count INT NOT NULL COMMENT '共振股票数量',
    stock_codes JSON NOT NULL COMMENT '触发股票代码列表',
    avg_buy_star FLOAT COMMENT '平均星级评分',
    
    -- LLM 分析结果
    llm_keywords JSON COMMENT 'LLM 提取的特征关键词',
    -- 示例: ["半导体国产替代", "先进封装", "AI芯片需求"]
    llm_summary TEXT COMMENT 'LLM 生成的事件摘要',
    llm_confidence FLOAT COMMENT 'LLM 置信度 0-1',
    llm_drivers JSON COMMENT 'LLM 推断的可能驱动因素',
    llm_related_themes JSON COMMENT 'LLM 推断的关联主题',
    
    -- 消息面确认
    news_confirmed TINYINT DEFAULT 0 COMMENT '消息面是否确认 (0/1)',
    news_confirm_score FLOAT COMMENT '消息面确认度 0-1',
    news_matched JSON COMMENT '匹配到的新闻列表',
    -- 示例: [{"title": "...", "source": "财联社", "date": "2026-05-12", "relevance": 0.85}]
    policy_signals JSON COMMENT '关联的政策信号',
    
    -- 趋势跟踪（v1.3 恢复实现）
    lifecycle ENUM('tracking','suggest_close','closed') DEFAULT 'tracking' COMMENT '生命周期状态',
    suggest_close_reason TEXT COMMENT '系统建议关闭的原因',
    closed_at DATETIME COMMENT '管理员确认关闭时间',
    closed_by VARCHAR(50) COMMENT '确认关闭的管理员',

    -- 统计
    duration_days INT COMMENT '持续天数（事件结束时填入）',
    total_change_pct FLOAT COMMENT '板块累计涨跌幅（结束时）',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_date (event_date),
    INDEX idx_target (target_type, target_name),
    -- INDEX idx_stage (stage),  -- 暂不实现
    INDEX idx_strategy (strategy_group_id)
) ENGINE=InnoDB COMMENT='群体事件';
```

#### 5.2.4 trend_tracking（趋势跟踪记录）

> v1.3 恢复实现。记录群体事件的每日跟踪数据。

```sql
CREATE TABLE trend_tracking (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    group_event_id BIGINT NOT NULL,

    -- 跟踪日期
    track_date DATE NOT NULL COMMENT '跟踪日期',

    -- 触发股票变化
    stock_count INT NOT NULL COMMENT '当日触发股票数',
    stocks_added INT DEFAULT 0 COMMENT '新增触发股票数',
    stocks_removed INT DEFAULT 0 COMMENT '消失触发股票数',

    -- 指标聚合（触发股票均值）
    avg_rsi FLOAT COMMENT 'RSI均值',
    avg_macd_dif FLOAT COMMENT 'MACD DIF均值',
    avg_volume_ratio FLOAT COMMENT '量比均值',
    avg_score FLOAT COMMENT '综合评分均值',

    -- 板块变化
    sector_change_pct FLOAT COMMENT '板块当日涨跌幅',

    -- 资讯关联
    news_count INT DEFAULT 0 COMMENT '当日关联资讯数',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_event_date (group_event_id, track_date),
    UNIQUE KEY uk_event_date (group_event_id, track_date)
) ENGINE=InnoDB COMMENT='事件趋势跟踪记录';
```

#### 5.2.5 strategy_subscription（策略订阅）

> v1.4 新增。记录用户对策略组的订阅关系。

```sql
CREATE TABLE strategy_subscription (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    strategy_group_id INT NOT NULL COMMENT '策略组ID',
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_user_strategy (user_id, strategy_group_id),
    INDEX idx_user (user_id),
    INDEX idx_strategy (strategy_group_id)
) ENGINE=InnoDB COMMENT='策略组订阅记录';
```

#### 5.2.6 strategy_group_run（扫描执行记录）

```sql
CREATE TABLE strategy_group_run (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_time DATETIME NOT NULL,
    run_type ENUM('scheduled','manual') DEFAULT 'scheduled',
    
    -- 执行统计
    stocks_scanned INT COMMENT '扫描股票数',
    signals_found INT COMMENT '发现信号数',
    events_created INT COMMENT '新建群体事件数',
    events_updated INT COMMENT '更新群体事件数',
    
    -- 执行状态
    status ENUM('running','completed','failed') DEFAULT 'running',
    error_message TEXT,
    elapsed_seconds FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_strategy_time (strategy_group_id, run_time)
) ENGINE=InnoDB COMMENT='策略组扫描执行记录';
```

---

## 6. 计算流程设计

### 6.1 主流程：信号扫描 → 事件跟踪

```
┌──────────────────────────────────────────────────────────────────┐
│                      定时触发 / 手动触发                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: 信号扫描                                                │
│                                                                  │
│  输入: strategy_group.indicators + signal_logic                  │
│  数据: indicators_daily + stock_data_daily + dic_stock           │
│  处理: 逐只股票匹配条件 → 生成 signal_snapshot                   │
│  复用: calc_indicator.py 的指标计算 + buy_advice_v2() 的评分      │
│  输出: signal_snapshot 记录                                      │
│  耗时: ~5500只 * 条件匹配 ≈ 10-30秒                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 2: 群体事件聚合                                            │
│                                                                  │
│  输入: 新增 signal_snapshot + strategy_group.aggregation         │
│  处理: 按 dimension(industry/concept/theme) 分组                 │
│        时间窗口内 ≥ min_stocks 只 = 群体事件                     │
│  逻辑:                                                           │
│    - 新信号 → 匹配已有事件（同 target + 时间窗口内）→ 追加股票    │
│    - 不匹配 → 创建新事件                                         │
│  输出: 新建或更新的 group_event 记录                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 3: LLM 特征提取（仅新事件或阶段变更时触发）                 │
│                                                                  │
│  3a. Doubao 结构化分析:                                          │
│      输入: 事件上下文（股票列表 + 指标快照 + 行业信息）            │
│      输出: event_type, confidence, keywords, drivers, themes     │
│      耗时: ~10秒                                                 │
│                                                                  │
│  3b. 关键词搜索确认:                                             │
│      输入: llm_keywords                                          │
│      处理: 调用 DataAgent API 按关键词搜索资讯                    │
│      输出: news_matched, news_confirm_score                      │
│      耗时: ~5秒                                                  │
│                                                                  │
│  3c. DeepSeek 深度摘要:                                          │
│      输入: 结构化分析 + 搜索结果                                  │
│      输出: llm_summary（可读的事件分析）                          │
│      耗时: ~15秒                                                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 4: 趋势跟踪（每日，仅 tracking 状态事件）                    │
│                                                                  │
│  输入: 所有 lifecycle='tracking' 的 group_event                   │
│  处理:                                                           │
│    4a. 统计当日触发股票变化（新增/消失）                             │
│    4b. 聚合触发股票的指标均值（RSI/MACD/量比/评分）                  │
│    4c. 写入 trend_tracking 记录                                   │
│    4d. 判定信号衰减：连续2日均值评分 < 0.5 → 标记 suggest_close     │
│  输出: trend_tracking 记录 + lifecycle 状态变更                    │
│  触发: 每日扫描后自动执行                                          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 5: 资讯持续关联（每日，仅 tracking 状态事件）                 │
│                                                                  │
│  输入: group_event.llm_keywords + 维度主题                        │
│  处理: 用关键词搜索 DataAgent 近 24h 新增资讯                      │
│  输出: 关联资讯追加到 news_matched，更新 news_count                │
│  触发: Step 4 完成后自动执行                                      │
│  生命周期: tracking=持续采集, suggest_close=仍采集, closed=停止     │
└──────────────────────────────────────────────────────────────────┘
```

> **注意**：v1.3 恢复了趋势跟踪（Step 4）和资讯持续关联（Step 5），计算流程从 Step 3 延伸到 Step 5。

### 6.2 指标条件表达式语法

策略组的 `indicators.conditions` 使用简易表达式语言：

```
# 比较运算
kdj_k < 30          # K 值小于 30
rsi_6 > 70          # RSI6 大于 70
volume_ratio > 1.5  # 量比大于 1.5

# 穿越检测
cross_golden(kdj_k, kdj_d)   # K 上穿 D（金叉）
cross_dead(kdj_k, kdj_d)     # K 下穿 D（死叉）

# 范围
between(rsi_6, 20, 40)       # RSI6 在 20-40 之间

# 趋势
slope(kdj_k, 5) > 0          # K 值 5 日斜率向上

# 组合
all(kdj_j < 10, 5)           # J 值连续 5 天低于 10（底部）
```

---

## 7. 架构方案

### 7.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          前端层                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Compass Web (Flask + Jinja2 + ECharts)                     ││
│  │  :8087                                                      ││
│  │  现有功能 + 策略组 Blueprint（列表/配置/回测/运行/事件跟踪）   ││
│  │  侧边栏导航风格：#001529 深色 + #F0F2F5 内容区 + #1890FF    ││
│  └───────────────────────────┬─────────────────────────────────┘│
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          API 层                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Compass Flask :8087                                        ││
│  │  /api/market/*     — 现有行情路由                            ││
│  │  /api/analysis/*   — 现有分析路由                            ││
│  │  /api/strategy/*   — 策略组 CRUD + 信号扫描                  ││
│  │  /api/events/*     — 群体事件 + 事件跟踪                     ││
│  │  /api/tracking/*   — 趋势跟踪 + 资讯关联                     ││
│  └───────────────────────────┬─────────────────────────────────┘│
│                               │                                 │
└───────────────────────────────┼─────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          计算层                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Strategy Engine（Compass 内 Python 模块）                   ││
│  │                                                             ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         ││
│  │  │ 信号扫描器   │  │ 策略组引擎   │  │ 群体事件    │         ││
│  │  │ SignalScanner│  │ Strategy    │  │ 聚合器      │         ││
│  │  │ 复用现有指标  │  │ Engine      │  │ EventAggre- │         ││
│  │  │ 计算+匹配   │  │ 条件解析+   │  │ gator       │         ││
│  │  └─────────────┘  │ 聚合触发    │  └─────────────┘         ││
│  │                   └─────────────┘                           ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         ││
│  │  │ LLM 特征    │  │ 趋势跟踪器  │  │ 资讯关联器  │         ││
│  │  │ 提取器      │  │ Trend       │  │ News        │         ││
│  │  │ LLMFeature  │  │ Tracker     │  │ Associator  │         ││
│  │  │ Extractor   │  │ 每日统计+   │  │ 持续关联+   │         ││
│  │  └─────────────┘  │ 衰减判定    │  │ 生命周期    │         ││
│  │                   └─────────────┘  └─────────────┘         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Compass MySQL    │  │ DataAgent    │  │ StockShark        │ │
│  │ :3306            │  │ :8000        │  │ :5000             │ │
│  │ 策略组新表+      │  │ 资讯搜索+    │  │ 行情数据+         │ │
│  │ 现有表(只读)     │  │ 资讯搜索     │  │ 股票搜索          │ │
│  └──────────────────┘  └──────────────┘  └───────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ 调度器 APScheduler（集成在 Flask 内）                         ││
│  │ 策略组日级别扫描 + 趋势跟踪 + 资讯关联                        ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 为什么融入 Compass Flask（v1.3 更新）

| 维度 | 独立 FastAPI（v1.0 方案） | 融入 Compass Flask（v1.3 方案） | 决策 |
|------|--------------------------|-------------------------------|------|
| **技术栈** | 新增 FastAPI + 独立部署 | 复用现有 Flask + Blueprint | ✅ 融入 |
| **资源** | 额外占用 1 个端口 + 1 个进程 | 共享现有 :8087 | ✅ 融入 |
| **前端** | Next.js（需 Node.js 运行时） | Jinja2 + ECharts（零依赖） | ✅ 融入 |
| **数据源** | MySQL 直连 | 复用 Database() 连接池 | 共享 |
| **LLM 能力** | DoubaoLLM + DeepSeekLLM | 复用同一 LLM 模块 | 共享 |
| **指标计算** | calc_indicator + buy_advice_v2 | 复用同一计算模块 | 共享 |
| **运维** | 需额外服务管理 | 零额外运维 | ✅ 融入 |

### 7.3 与现有系统的关系

```
共享层（复用，不改动）:
├── MySQL 数据库（stock_analysis_system）
├── 指标计算模块（stockdata/calc_indicator.py）
├── 综合决策引擎（stockdata/main_analysis.py → buy_advice_v2）
├── LLM 模块（compass/llm/）
├── DataGateway（compass/services/data_gateway.py）
├── DB 连接池（compass/data/database.py → DBUtils PooledDB）
└── DataAgent / StockShark 外部服务

新增层（融入 Compass Flask Blueprint）:
├── strategy_group 等 5 张新表 + trend_tracking 表
├── Strategy Engine Python 模块（信号扫描/聚合/LLM编排/趋势跟踪/资讯关联）
├── Flask Blueprint: strategy_bp（/api/strategy/*, /api/events/*, /api/tracking/*）
├── Jinja2 模板: 策略组列表/配置/详情/回测/运行/事件跟踪 6 个页面
└── 前端: ECharts 图表 + 侧边栏导航（匹配 d8q-interaction-design.md）

不动层:
├── Compass Flask 现有路由 — 不变
├── stockdata 页面（:5001）— 不变
└── 所有现有 HTML 模板 — 不变
```

---

## 8. 现有能力盘点

### 8.1 可直接复用

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| 8 类技术指标计算 | `stockdata/calc_indicator.py` + `stockfetch/` | 直接调用 `calcIndicatorAndSaveToDB()` |
| 综合买卖决策 | `stockdata/main_analysis.py` → `buy_advice_v2()` | 直接调用，获取 buy_star 评分 |
| KDJ 趋势/强弱/金叉/头底分析 | `src/analysis/kdj.py` | 复用 `predict_linear_trend()` 等方法 |
| RSI/MACD/BOLL/MA 分析 | `src/analysis/rsi.py` 等 | 复用各类分析方法 |
| 交易分析（背离/支撑压力） | `src/analysis/trade.py` | 复用 `predict_trade()` |
| 指标数据库 | `indicators_daily` 表（24 个字段） | 信号扫描直接查询 |
| 行业/概念分类 | `dic_stock.industry` + `stock_concept` | 群体聚合直接使用 |
| LLM 分析 | `compass/llm/doubao.py` + `deepseek.py` | 复用已有 LLM 客户端 |
| 数据网关 | `compass/services/data_gateway.py` | 资讯搜索复用 |
| DataAgent 资讯 | `http://localhost:8000` | 消息面搜索直接调用 |
| StockShark 行情 | `http://localhost:5000` | 行情数据直接调用 |
| 推送通知 | `compass/api/routes/notify.py` | 邮件推送已实现 |

### 8.2 需要新建

| 能力 | 说明 | 优先级 |
|------|------|--------|
| 策略组条件解析引擎 | 解析 indicators JSON + signal_logic，生成 SQL 或内存过滤条件 | P0 |
| 信号扫描调度器 | 日级别扫描 + 手动触发 | P0 |
| 群体事件聚合器 | 按维度分组 + 时间窗口 + 阈值判断 | P0 |
| LLM 编排器 | 串联 Doubao 结构化 → 关键词搜索 → DeepSeek 摘要 | P0 |
| 趋势跟踪器 | 每日统计触发股票变化 + 指标聚合 + 衰减判定 | P0 |
| 资讯关联器 | 每日按关键词+主题匹配新增资讯 + 生命周期跟随 | P0 |
| 关联股票扩展器 | 基于行业/概念自动扩展 | P1 |
| 策略组回测引擎 | 历史数据回放 | P1 |
| Flask Blueprint | 策略组 API 路由 + 6 个页面模板 | P0 |

### 8.3 当前数据状态

⚠️ **关键前提**：所有计算管线依赖基础数据，当前数据库中以下表为空：

| 表 | 记录数 | 说明 |
|----|--------|------|
| `dic_stock` | 0 | 股票基础列表 |
| `stock_data_daily` | 0 | 日线行情 |
| `indicators_daily` | 0 | 技术指标 |
| `stock_analysis` | 0 | 综合分析 |

**Phase 0 必须先恢复数据填充管线**，通过 `DailyStockCheckTaskV2.action()` 重新拉取。

---

## 9. 实施路径

### 9.1 分阶段计划

| 阶段 | 内容 | 工作量 | 前置依赖 | 交付物 |
|------|------|--------|---------|--------|
| **Phase 0** | 数据恢复 + 管线验证 | 1 天 | akshare 可用 | dic_stock + stock_data_daily + indicators_daily 有数据 |
| **Phase 1** | 策略组后端核心 | 3 天 | Phase 0 | 5 张新表 + 信号扫描器 + 聚合器 + API |
| **Phase 2** | LLM 编排 + 消息面确认 | 2 天 | Phase 1 | LLM 特征提取链路 + 搜索确认 |
| **Phase 3** | 前端页面（融入 Flask） | 5 天 | Phase 1 可并行 | Jinja2 + ECharts 6 个页面 |
| **Phase 4** | 趋势跟踪 + 资讯关联 + 生命周期 | 2 天 | Phase 1-2 | TrendTracker + NewsAssociator + 生命周期管理 |
| **Phase 5** | 端到端联调 + 优化 | 2 天 | Phase 1-4 | 完整可用系统 |
| **Phase 6** | 回测 + 复盘报告 | 2 天 | Phase 2 | 策略组回测 + 事件复盘 |

**总计约 17 个工作日**。Phase 1-2（后端）与 Phase 3（前端）可并行。

> **v1.3 变更**：恢复趋势跟踪和资讯持续关联（Phase 4），前端融入 Flask（不独立部署），新增生命周期管理。

### 9.2 Phase 1 详细拆解

| 任务 | 说明 | 产出来 |
|------|------|--------|
| 1.1 建表 | 创建 strategy_group / signal_snapshot / group_event / strategy_group_run / trend_tracking | SQL 脚本 |
| 1.2 策略组 CRUD API | 创建/编辑/删除/启停/列表 | FastAPI 路由 |
| 1.3 条件解析引擎 | 解析 indicators JSON → 内存过滤函数 | StrategyConditionParser 类 |
| 1.4 信号扫描器 | 查询 indicators_daily + 匹配条件 → signal_snapshot | SignalScanner 类 |
| 1.5 群体事件聚合器 | 按 dimension 分组 + 时间窗口 + 阈值 → group_event | EventAggregator 类 |
| 1.6 调度集成 | APScheduler 注册定时扫描任务 | 调度配置 |

### 9.3 Phase 4 前端页面清单

| 页面 | 功能 | 优先级 |
|------|------|--------|
| 策略组列表 | 全局概览 + 策略组卡片列表 | P0 |
| 策略组配置 | 创建/编辑策略组，2层结构（策略→策略组）| P0 |
| 策略组详情 | 信号快照 + 策略构成 + 活跃事件入口 | P0 |
| 回测页面 | 策略组历史回测 + 效果统计 | P2 |
| 运行管理 | 调度配置 + 运行历史 | P0 |
| 事件跟踪页 | 指标趋势聚合 + 关联资讯流 + 每日跟踪统计 + LLM分析 + 生命周期管理 | P0 |

---

## 10. 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 策略 | Strategy | 单个指标因子的逻辑组合，是策略组的组成单元 |
| 策略组 | Strategy Group | 用户自定义的策略组合 + 触发条件 + 聚合规则 |
| 信号快照 | Signal Snapshot | 单只股票触发策略条件时的指标记录 |
| 群体事件 | Group Event | 同一维度（行业/主题）内多只股票共振触发 |
| 维度主题 | Dimension Theme | 由群体事件确立的趋势方向，关联持续资讯采集 |
| 特征关键词 | Feature Keywords | LLM 从事件中提取的描述性关键词 |
| 消息面确认 | News Confirmation | 用关键词搜索资讯库验证信号方向 |
| 事件跟踪 | Event Tracking | 群体事件确立后的持续跟踪过程 |
| 生命周期 | Lifecycle | 事件状态：跟踪中 → 建议关闭 → 已关闭 |
| buy_star | Buy Star | buy_advice_v2() 输出的星级评分，综合多维度买卖信号 |
| 指标条件表达式 | Indicator Condition Expression | 策略组中描述指标触发条件的 DSL |

---

---

## 11. 数据支撑评估

> 基于对远端服务器 47.99.57.152 的实地调研（2026-05-13）

### 11.1 数据需求 vs 现状全景

策略组引擎的完整运行依赖 **6 大数据层**，逐层盘点如下：

| 数据层 | 需要什么 | 现有表 | 数据量 | 状态 | 差距 |
|--------|---------|--------|--------|------|------|
| **① 股票基础信息** | 代码/名称/**行业**/概念/市场 | `stock_basic` | 5,512 只 | ⚠️ 半空 | industry 全部为空 |
| **② 日线行情** | 开高低收量/换手率/涨跌幅 | `stock_data_daily` | **0** | ❌ 空 | 完全无数据 |
| **③ 技术指标** | KDJ/MACD/RSI/BOLL/MA/ASI 等 | `indicators_daily` | **0** | ❌ 空 | 完全无数据 |
| **④ 综合分析** | buy_star/buy/sell/买卖建议 | `stock_analysis` | **0** | ❌ 空 | 完全无数据 |
| **⑤ 资讯数据** | 新闻/政策/研报（关键词可搜索） | DataAgent SQLite | 738 条 | ✅ 有数据 | 可用但规模小 |
| **⑥ 赛道数据** | tracks/keywords/heat | DataAgent | 5 条赛道 | ✅ 有数据 | 可用 |

### 11.2 各层详细状态

#### ① 股票基础信息 — ⚠️ 半空

```
stock_basic: 5,512 只股票（代码+名称有）
             industry: 0% 覆盖（全部为空）
             market/list_date/total_share/float_share: 全部为空

dic_stock: 0 条（表结构完整但无数据，含 industry/pe/pb/market_cap 等 24 字段）
stock_concept: 0 条（无概念板块关联数据）
stock_theme: 0 条（无主题关联数据）
```

**差距**：群体事件聚合的维度之一是"行业"。stock_basic 的 industry 全空，dic_stock 无数据，无法按行业聚合。

**修复方案**：
- `stock_basic.industry` 可通过 `akshare.stock_info_a_code_name()` + 其他来源补充（东方财富接口被封，需找替代）
- `dic_stock` 需要通过 `akshare.stock_zh_a_spot_em()` 填充（当前该接口被封）

#### ② 日线行情 — ❌ 空表

```
stock_data_daily: 0 条
表结构完整: stock_code, date, open, close, high, low, volume, turnover, 
            amplitude, change_percentage, change_amount, turnover_rate
```

**差距**：这是所有计算的基础。无此数据，指标无法计算，信号无法检测。

**数据获取渠道**：
- `akshare.stock_zh_a_hist()`（东方财富）→ ❌ **当前被封**（RemoteDisconnected）
- `akshare.stock_zh_a_daily()`（新浪）→ ✅ **可用**（实测 600036 成功获取 5 天数据）
- `stock_task.py` 的 `get_kline_daily()` 已支持 api=0（新浪）和 api=1（东财）两种数据源

**修复方案**：将 `DailyStockCheckTaskV2` 的数据获取从东财切换到新浪接口即可。

#### ③ 技术指标 — ❌ 空表

```
indicators_daily: 0 条
表结构完整: 24 字段（macd_dif/dea/macd, kdj_k/d/j, boll_up/mid/low, 
            rsi_6/12/24, ma5/10/20/30/60, volume_ratio, amplitude 等）
```

**差距**：指标计算依赖 `stock_data_daily`。无行情数据 → 无法计算指标。

**计算管线状态**：
- `calc_indicator.py` + TA-Lib → ✅ 代码就绪
- `stock_task.updateIndicatorV2()` → ✅ 代码就绪
- 只要有 `stock_data_daily` 数据，指标可立即计算

#### ④ 综合分析 — ❌ 空表

```
stock_analysis: 0 条
表结构: stock_code, analysis_data(JSON), buy_advice(JSON), record_time, buy, sell
```

**差距**：`buy_advice_v2()` 依赖 `indicators_daily` + `stock_data_daily`。两者都为空。

**计算管线状态**：
- `main_analysis.buy_advice_v2()` → ✅ 代码就绪（10 维度综合决策）
- `stock_task.updateTradeAnalysis()` → ✅ 代码就绪
- 有指标数据后可立即运行

#### ⑤ 资讯数据 — ✅ 可用

```
DataAgent SQLite: 738 条新闻
  - 人工智能: 394 条
  - 具身智能: 182 条
  - 新材料: 59 条
  - 量子计算: 39 条
  - 核电: 37 条
  - 碳纤维: 22 条
时间范围: 2026-02-09 ~ 2026-05-13（持续采集中）
数据源: 财联社(cailianshe), 每经(nbd), 36氪(36kr)
```

**状态**：DataAgent 每日自动采集，数据持续增长。可用于消息面确认。
**不足**：ai_summary 字段全部为 null（LLM 摘要未启用）；news_type 只有 telegraph（快讯）。

#### ⑥ 赛道数据 — ✅ 可用

```
tracks: 5 条赛道（人工智能/具身智能/新材料/量子计算/核电）
keywords: 每个赛道有关键词配置
执行记录: 200+ 条，最近持续运行
```

**状态**：赛道系统运行正常，可作为群体事件的"主题"维度。

### 11.3 akshare 接口可用性（服务器实测）

| 接口 | 数据源 | 状态 | 说明 |
|------|--------|------|------|
| `stock_market_pe_lg` | 乐估 | ✅ 可用 | 342 rows，市场 PE |
| `stock_market_pb_lg` | 乐估 | ✅ 可用 | 5183 rows，个股 PB |
| `stock_info_a_code_name` | 多源 | ✅ 可用 | 5515 只股票列表 |
| `stock_zh_a_daily` | 新浪 | ✅ 可用 | 个股日线K线 |
| `stock_financial_abstract` | 新浪 | ✅ 可用 | 财务摘要 |
| `stock_zh_a_spot_em` | 东财 | ❌ 被封 | RemoteDisconnected |
| `stock_zh_a_hist` | 东财 | ❌ 被封 | RemoteDisconnected |
| `stock_individual_info_em` | 东财 | ❌ 被封 | RemoteDisconnected |
| `stock_board_industry_name_em` | 东财 | ❌ 被封 | 行业板块数据不可用 |

**关键发现**：东方财富系列接口（`_em` 后缀）全部被封。新浪/乐估接口可用。

### 11.4 数据恢复路径（Phase 0 详细方案）

策略组引擎的数据依赖链：

```
股票列表 ──→ 日线行情 ──→ 技术指标 ──→ 综合分析 ──→ 策略组信号
  ①            ②            ③            ④            ⑤
```

#### Step 1: 恢复股票列表（①）

| 数据项 | 来源 | 接口 | 操作 |
|--------|------|------|------|
| 代码+名称 | akshare | `stock_info_a_code_name()` ✅ | 补充 `stock_basic` 缺失字段 |
| 行业分类 | 待定 | 东财被封，需替代方案 | 见下方方案 |
| 实时行情快照 | akshare | `stock_zh_a_spot_em()` ❌ | 需替代方案 |

**行业分类替代方案**（按可行性排序）：

| 方案 | 数据源 | 可行性 | 工作量 |
|------|--------|--------|--------|
| A. 爬取东方财富行业分类 | 东财网页 | ⚠️ 可能被封 | 1 天 |
| B. 使用 `stock_zh_a_daily` + 手动映射 | 新浪 | ✅ 可行但粗糙 | 0.5 天 |
| C. 本地维护行业映射表 | 人工 | ✅ 可行 | 2 天（5000+只） |
| D. 使用第三方 API（Tushare/Wind） | 付费 | ✅ 稳定 | 需要账号 |

**推荐**：先用方案 C 建立核心股票（沪深300成分）的行业映射，后续再完善。

#### Step 2: 恢复日线行情（②）

| 数据项 | 来源 | 接口 | 操作 |
|--------|------|------|------|
| 日K线 | akshare（新浪） | `stock_zh_a_daily()` ✅ | 修改 `stock_task.get_kline_daily(api=0)` |
| 换手率 | akshare（新浪） | 同上 | 已含在返回数据中 |

**修改点**：`DailyStockCheckTaskV2` 默认使用 `api=1`（东财），需改为 `api=0`（新浪）。

**预估时间**：5500 只 × 每只 3 秒 ≈ 4.5 小时（首次全量）。增量更新约 30 分钟。

#### Step 3: 计算技术指标（③）

前置条件：Step 2 完成。

**管线**：`stock_task.updateIndicatorV2()` → `calc_indicator.py` → `indicators_daily` 表

已支持的 8 类指标全部使用 TA-Lib 计算，无需外部 API 调用。

**预估时间**：5500 只 × 每只 1 秒 ≈ 1.5 小时。

#### Step 4: 运行综合分析（④）

前置条件：Step 3 完成。

**管线**：`stock_task.updateTradeAnalysis()` → `buy_advice_v2()` → `stock_analysis` 表

纯内存计算 + DB 写入，无需外部 API。

**预估时间**：5500 只 × 每只 0.5 秒 ≈ 45 分钟。

#### Step 5: 恢复定时任务

当前 cron 只有 `fetch_valuation.py`（每天 3:00）。需要恢复：

| 任务 | 频率 | 说明 |
|------|------|------|
| `DailyStockCheckTaskV2` | 每天 17:00 | 更新行情 → 计算指标 → 综合分析 |
| `DailyRecommendationTask` | 每天 18:00 | 生成每日推荐 |
| `fetch_valuation.py` | 每天 3:00 | ✅ 已在运行 |

### 11.5 数据恢复优先级与策略组的关系

```
                    策略组引擎可启动的最低数据要求
                    
┌─────────────────────────────────────────────────────┐
│  最低要求（MVP）                                      │
│                                                      │
│  ① stock_basic: 5512 只 + industry（至少覆盖 300 只） │
│  ② stock_data_daily: 最近 60 天行情                   │
│  ③ indicators_daily: 最近 60 天指标                   │
│  ④ stock_analysis: 最近 30 天分析结果                 │
│  ⑤ DataAgent 资讯: ✅ 已满足                          │
│                                                      │
│  满足以上 → 策略组引擎可运行日级别扫描                 │
│  盘中实时扫描需额外：实时行情推送（可后续接入）         │
└─────────────────────────────────────────────────────┘
```

### 11.6 数据恢复成本估算

| Step | 任务 | 预估时间 | 风险 |
|------|------|---------|------|
| 1 | 修改数据获取接口（东财→新浪） | 2 小时 | 低 |
| 2 | 补充行业分类（核心 300 只） | 4 小时 | 中（东财被封需替代方案） |
| 3 | 首次全量数据拉取（5500 只） | 4.5 小时（自动） | 低（新浪接口稳定） |
| 4 | 技术指标计算（5500 只） | 1.5 小时（自动） | 低（TA-Lib 本地计算） |
| 5 | 综合分析（5500 只） | 45 分钟（自动） | 低 |
| 6 | 配置 cron 定时任务 | 30 分钟 | 低 |
| **总计** | **人工 6.5 小时 + 自动 6.75 小时** | **约 2 个工作日** | |

### 11.7 长期数据需求（Phase 2+）

策略组引擎在 MVP 之外还有以下数据增强需求：

| 数据 | 来源 | 用途 | 优先级 |
|------|------|------|--------|
| 实时行情推送 | 东财/Tushare Pro | 盘中信号捕捉 | P1 |
| 融资融券数据 | akshare | 量价信号增强 | P1 |
| 北向资金流向 | akshare | 资金面确认 | P1 |
| 研报数据 | akshare/爬虫 | 消息面确认增强 | P2 |
| 公司公告 | 巨潮资讯 | 事件驱动信号 | P2 |
| 概念板块关联 | 东财（被封）/替代 | 关联股票扩展 | P1 |

---

*§11 基于服务器实地调研完成。核心结论：代码管线全部就绪，但基础数据（行情+指标+分析）全部为空。恢复路径明确——将数据源从东财切换到新浪，约 2 个工作日可完成数据恢复。*
