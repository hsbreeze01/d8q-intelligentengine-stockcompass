# 策略系统技术参考文档

> 版本：1.0
> 更新日期：2026-05-29
> 涉及服务：Compass（47.99.57.152:8087）+ StockShark（49.234.48.221:5000）
> 共享数据库：MySQL 47.99.57.152:3306/stock_analysis_system

---

## 一、系统架构

```
Compass (47:8087)
  ├── 策略引擎
  │   ├── Scanner — 信号扫描（从 indicators_daily 条件匹配）
  │   ├── Aggregator — 群体事件聚合（按行业/概念维度）
  │   └── Scheduler — 定时调度（APScheduler cron）
  ├── LLM 分析器
  │   ├── LLMExtractor — 三阶段分析（DeepSeek）
  │   └── TrendTracker — 趋势跟踪 + 衰减判定
  └── DB Layer (compass/strategy/db.py)
      ├── strategy_group — 策略组配置
      ├── strategy_group_run — 扫描运行记录
      ├── signal_snapshot — 信号快照
      ├── group_event — 群体事件
      ├── strategy_subscription — 用户订阅
      └── trend_tracking — 趋势跟踪记录

StockShark (49:5000)
  ├── 指标计算 (calc_indicator.py / TA-Lib)
  ├── 评分引擎 (data_processor.py)
  └── K线采集 + Daemon 调度

共享 MySQL (47.99.57.152:3306)
  ├── indicators_daily (3.1M行, 5200股, 578天)
  ├── stock_data_daily (K线行情)
  ├── stock_analysis (分析结果, 276K行)
  ├── stock_basic (基本信息 + 行业分类)
  └── index_daily (5大A股指数日K线)
```

### 服务分工

| 职责 | 服务 | 说明 |
|------|------|------|
| 指标计算（MACD/KDJ/RSI/BOLL/MA） | StockShark | TA-Lib，每日 15:35 K线 + 15:50 指标 |
| 投资评分 + 风险评级 | StockShark | `data_processor.py` 4因子评分 |
| 策略组 CRUD | Compass | 创建/编辑/启停/删除策略组 |
| 信号扫描 | Compass | `Scanner` 从 indicators_daily 条件匹配 |
| 群体事件聚合 | Compass | `Aggregator` 按行业/概念维度聚合 |
| 定时调度 | Compass | APScheduler cron + 每日趋势跟踪 |
| LLM 分析 | Compass | DeepSeek 三阶段分析 |
| 趋势跟踪 + 衰减判定 | Compass | `TrendTracker` 每日跟踪，连续2日低分衰减 |
| 用户订阅 | Compass | 订阅/取消订阅，策略发现 |

---

## 二、数据模型

### 2.1 strategy_group（策略组）

```sql
CREATE TABLE strategy_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    indicators JSON NOT NULL COMMENT '指标列表',
    signal_logic ENUM('AND', 'OR', 'SCORING') NOT NULL DEFAULT 'AND',
    conditions JSON NOT NULL COMMENT '触发条件数组',
    scoring_threshold INT DEFAULT NULL COMMENT 'SCORING 模式达标阈值',
    aggregation JSON NOT NULL COMMENT '聚合规则',
    scan_cron VARCHAR(100) DEFAULT NULL COMMENT 'cron 表达式',
    status ENUM('active', 'paused', 'archived') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### conditions 字段结构

```json
[
  {"indicator": "rsi_6", "operator": "<", "value": 30},
  {"indicator": "kdj_k", "operator": "<", "value": 20}
]
```

**支持的运算符**：

| 运算符 | 含义 | 说明 |
|--------|------|------|
| `>` | 大于 | RSI > 70 |
| `<` | 小于 | RSI < 30 |
| `>=` | 大于等于 | MA5 >= MA20 |
| `<=` | 小于等于 | KDJ <= 20 |
| `==` | 等于 | 浮点精度 1e-9 |
| `cross_above` | 上穿 | 简化实现：当前值 > 阈值 |
| `cross_below` | 下穿 | 简化实现：当前值 < 阈值 |

#### signal_logic 三种模式

| 模式 | 逻辑 | 适用场景 |
|------|------|----------|
| `AND` | 所有条件同时满足 | 严格入场（底部共振） |
| `OR` | 任一条件满足 | 宽松入场 |
| `SCORING` | 满足条件数 >= scoring_threshold | 综合评分入场 |

#### aggregation 字段结构

```json
{
  "dimension": "industry",
  "min_stocks": 3,
  "time_window_minutes": 60
}
```

| 字段 | 说明 |
|------|------|
| `dimension` | 聚合维度：`industry`（行业）/ `concept`（概念）/ `theme`（主题） |
| `min_stocks` | 同维度最少触发股票数，低于此数不产生事件 |
| `time_window_minutes` | 时间窗口（分钟），窗口内可追加到已有事件 |

#### 当前已配置的策略

---

##### 策略一：底部共振（ID=1）

**策略思路**：当 KDJ 的 K 值和 RSI(6) 同时处于极度超卖区（均低于 15），说明多指标在底部形成共振，可能出现反弹机会。

| 配置项 | 值 |
|--------|-----|
| 名称 | 底部共振测试 |
| 信号逻辑 | `SCORING`（满足条件数 >= 2） |
| 调度 | `0 16 * * *`（每日 16:00） |
| 状态 | active |
| 关联指标 | `kdj_k`, `rsi_6`, `volume_ratio` |

**入场条件**：

| # | 指标 | 运算符 | 阈值 | 说明 |
|---|------|--------|------|------|
| 1 | `kdj_k` | `<` | 15 | KDJ K 线极度超卖 |
| 2 | `rsi_6` | `<` | 15 | RSI(6) 极度超卖 |

SCORING 阈值 = 2，即两个条件**必须同时满足**（等效 AND）。

**聚合规则**：

| 配置 | 值 | 说明 |
|------|-----|------|
| 维度 | `industry`（行业） | 按行业聚合 |
| 最少股票数 | 3 | 同行业至少 3 只触发才产生事件 |
| 时间窗口 | 4320 分钟（3 天） | 3 天内同行业可追加到同一事件 |

**运行统计**（截至 2026-05-29）：
- 累计运行：22 次已完成
- 累计匹配：18,132 只次
- 平均耗时：24.8 秒/次

**典型触发场景**：
- 大盘急跌后，某行业多只股票同时进入 RSI < 15 + KDJ K < 15 的极度超卖状态
- 系统按行业聚合，若 >= 3 只同行业股票触发，生成群体事件
- 触发 LLM 分析（DeepSeek 结构化分析 + 资讯确认 + 摘要生成）
- 进入趋势跟踪，每日 16:00 持续跟踪信号衰减

---

##### 策略二：放量突破（ID=2）

**策略思路**：量比大于 2（成交量突然放大至平均的 2 倍以上）且 KDJ K 线为正值并出现上穿信号，捕捉放量上攻的突破行情。

| 配置项 | 值 |
|--------|-----|
| 名称 | 放量突破策略 |
| 信号逻辑 | `AND`（所有条件同时满足） |
| 调度 | `0 16 * * *`（每日 16:00） |
| 状态 | active |
| 关联指标 | `volume_ratio`, `kdj_k` |

**入场条件**：

| # | 指标 | 运算符 | 阈值 | 说明 |
|---|------|--------|------|------|
| 1 | `volume_ratio` | `>` | 2.0 | 量比 > 2，成交量放大 |
| 2 | `kdj_k` | `>` | 0.0 | KDJ K 线为正（排除极端超卖） |
| 3 | `kdj_k` | `cross_above` | 0.0 | KDJ K 线上穿 0 轴 |

三个条件必须同时满足。

**聚合规则**：

| 配置 | 值 | 说明 |
|------|-----|------|
| 维度 | `concept`（概念） | 按概念板块聚合 |
| 最少股票数 | 3 | 同概念至少 3 只触发才产生事件 |
| 时间窗口 | 7200 分钟（5 天） | 5 天内同概念可追加到同一事件 |

**运行统计**（截至 2026-05-29）：
- 累计运行：20 次已完成
- 累计匹配：0 只次（当前条件较严格，暂无匹配）
- 平均耗时：26.4 秒/次

**匹配分析**：
放量突破策略目前匹配为 0，可能原因：
1. `volume_ratio` 数据在 `indicators_daily` 中可能未正确填充
2. 三个条件 AND 逻辑较严格，尤其是 `cross_above` 为简化实现（仅判断当前值 > 0）
3. 需确认 `indicators_daily` 中 `volume_ratio` 字段是否有有效数据

---

### 2.2 strategy_group_run（扫描运行记录）

```sql
CREATE TABLE strategy_group_run (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    trigger_type ENUM('cron', 'manual') NOT NULL DEFAULT 'manual',
    total_stocks INT DEFAULT 0,
    matched_stocks INT DEFAULT 0,
    status ENUM('running', 'completed', 'failed') NOT NULL DEFAULT 'running',
    error_message TEXT DEFAULT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME DEFAULT NULL,
    duration_seconds FLOAT DEFAULT NULL
);
```

### 2.3 signal_snapshot（信号快照）

```sql
CREATE TABLE signal_snapshot (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_id INT NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100) DEFAULT NULL,
    indicator_snapshot JSON NOT NULL COMMENT '触发时刻的指标值',
    buy_star INT DEFAULT NULL COMMENT 'stock_analysis.buy 字段',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

`indicator_snapshot` 记录触发时刻该股票的所有指标值，用于回溯分析。

### 2.4 group_event（群体事件）

```sql
CREATE TABLE group_event (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_id INT DEFAULT NULL,
    dimension VARCHAR(50) NOT NULL COMMENT 'industry/concept/theme',
    dimension_value VARCHAR(100) NOT NULL COMMENT '维度值',
    stock_count INT NOT NULL DEFAULT 0,
    avg_buy_star FLOAT DEFAULT NULL,
    max_buy_star INT DEFAULT NULL,
    matched_stocks JSON NOT NULL COMMENT '匹配股票列表',
    status ENUM('open', 'closed', 'analyzed') NOT NULL DEFAULT 'open',
    lifecycle ENUM('tracking', 'suggest_close', 'closed') DEFAULT 'tracking',
    -- LLM 分析结果
    llm_keywords JSON DEFAULT NULL,
    llm_summary TEXT DEFAULT NULL,
    llm_confidence FLOAT DEFAULT NULL,
    llm_drivers JSON DEFAULT NULL,
    llm_related_themes JSON DEFAULT NULL,
    -- 消息面确认
    news_confirmed BOOLEAN DEFAULT NULL,
    news_confirm_score FLOAT DEFAULT NULL,
    news_matched JSON DEFAULT NULL,
    -- 生命周期
    suggest_close_reason TEXT DEFAULT NULL,
    closed_at DATETIME DEFAULT NULL,
    window_start DATETIME NOT NULL,
    window_end DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### 事件生命周期

```
创建 (status=open, lifecycle=tracking)
  |
  v
LLM 三阶段分析 (lifecycle=tracking)
  |
  v
每日趋势跟踪
  +-- 信号持续 -> lifecycle=tracking (继续跟踪)
  +-- 连续2日评分 < 0.5 -> lifecycle=suggest_close (建议关闭)
       |
       v
人工/自动关闭 -> lifecycle=closed, status=closed
```

### 2.5 strategy_subscription（策略订阅）

```sql
CREATE TABLE strategy_subscription (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    strategy_group_id INT NOT NULL,
    subscribed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_strategy (user_id, strategy_group_id)
);
```

用户身份识别优先级：`X-Forwarded-User` > `?user_id=` > `session.uid`。

### 2.6 trend_tracking（趋势跟踪记录）

```sql
CREATE TABLE trend_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_event_id INT NOT NULL,
    track_date DATE NOT NULL,
    stock_count INT NOT NULL DEFAULT 0,
    new_stocks JSON DEFAULT NULL,
    lost_stocks JSON DEFAULT NULL,
    avg_rsi FLOAT DEFAULT NULL,
    avg_macd_dif FLOAT DEFAULT NULL,
    avg_volume_ratio FLOAT DEFAULT NULL,
    avg_score FLOAT DEFAULT NULL,
    news_count INT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_event_date (group_event_id, track_date)
);
```

---

## 三、策略扫描引擎

### 3.1 Scanner — 信号扫描

**文件**：`compass/strategy/services/scanner.py`

**流程**：

1. 加载策略组 (conditions + signal_logic + scoring_threshold)
2. 创建运行记录 (strategy_group_run)
3. 批量读取 `indicators_daily` 最新一天数据 + `stock_analysis.buy` 值
4. 逐股票匹配条件：
   - AND: 所有条件同时满足
   - OR: 任一条件满足
   - SCORING: 满足数 >= threshold
5. 写入 `signal_snapshot`
6. 更新运行记录 (matched_stocks / total_stocks / duration)
7. 触发 `Aggregator` 聚合

**条件匹配核心逻辑**：

```python
def _eval_condition(self, indicator_values, condition):
    current = indicator_values.get(condition["indicator"])
    threshold = condition["value"]
    operator = condition["operator"]

    if operator == ">":   return current > threshold
    if operator == "<":   return current < threshold
    if operator == ">=":  return current >= threshold
    if operator == "<=":  return current <= threshold
    if operator == "==":  return abs(current - threshold) < 1e-9
    if operator == "cross_above": return current > threshold  # 简化实现
    if operator == "cross_below": return current < threshold  # 简化实现
```

**数据源**：
- 指标值：`indicators_daily` 表（最新一天全量数据）
- buy_star：`stock_analysis.buy` 字段

### 3.2 Aggregator — 群体事件聚合

**文件**：`compass/strategy/services/aggregator.py`

**流程**：

1. 获取策略组聚合规则 (dimension / min_stocks / time_window_minutes)
2. 获取本次扫描的 signal_snapshot
3. 加载股票的维度映射 (stock_basic.industry/concept/theme)
4. 按维度值分组
5. 每组处理：
   - 股票数 < min_stocks → 跳过
   - 查找同维度 open 事件：
     - 窗口内 → 追加到已有事件（合并 matched_stocks）
     - 窗口外 → 创建新事件
   - 计算聚合指标 (avg_buy_star / max_buy_star / sector_change_pct)
   - 设置 lifecycle=tracking
   - 异步触发 LLM 分析 (fire-and-forget 线程)
6. 关闭超时事件

**sector_change_pct 计算**：查询 `stock_data_daily` 中匹配股票当日 `change_percentage` 的均值。

### 3.3 Scheduler — 定时调度

**文件**：`compass/strategy/scheduler.py`

**机制**：APScheduler `BackgroundScheduler`

**注册的任务**：

| 任务 | 触发条件 | 说明 |
|------|----------|------|
| 策略扫描 | 每个策略组的 `scan_cron` | `_run_scan(group_id)` |
| 趋势跟踪 | `0 16 * * mon-fri` | `_run_trend_tracking()` |

**调度器管理**：
- `start_scheduler()` — 启动
- `shutdown_scheduler()` — 优雅关闭
- `reload_scheduler()` — 策略组变更后重新加载

---

## 四、LLM 分析引擎

### 4.1 LLMExtractor — 三阶段分析

**文件**：`compass/strategy/services/llm_extractor.py`

**阶段 1 — DeepSeek 结构化分析**：

- Prompt 要求输出 JSON 格式：`{event_type, confidence, keywords, possible_drivers, related_themes}`
- 输入：事件上下文（维度、股票列表、指标数据）
- 输出：事件类型（板块联动/概念爆发/资金异动）、置信度、关键词、驱动因素

**阶段 2 — 关键词搜索确认**：

- 用阶段 1 提取的 `keywords` 搜索近 24h 资讯
- 计算确认度评分：`score = min(1.0, matched_count / keyword_count)`
- 确认阈值：`score >= 0.3` 则 `news_confirmed = True`

**阶段 3 — DeepSeek 深度摘要**：

- 输入：事件数据 + 结构化分析 + 资讯匹配结果
- 输出：Markdown 格式摘要（事件概述 + 驱动因素 + 消息面 + 关注要点）

**Graceful Degradation**：每个阶段独立 try/except，失败不阻塞后续阶段。

### 4.2 TrendTracker — 趋势跟踪 + 衰减判定

**文件**：`compass/strategy/services/trend_tracker.py`

**每日跟踪内容**：

| 指标 | 数据源 | 说明 |
|------|--------|------|
| stock_count | 事件 matched_stocks | 当前触发股票数 |
| new_stocks / lost_stocks | 前一日对比 | 新增/消失的股票 |
| avg_rsi | signal_snapshot | RSI 均值 |
| avg_macd_dif | signal_snapshot | MACD DIF 均值 |
| avg_volume_ratio | signal_snapshot | 量比均值 |
| avg_score | buy_star 归一化 (÷10) | 综合评分均值 |
| news_count | 资讯搜索 | 关联资讯数量 |

**衰减判定规则**：

```
DECAY_SCORE_THRESHOLD = 0.5
DECAY_CONSECUTIVE_DAYS = 2

连续 2 日 avg_score < 0.5 -> lifecycle = suggest_close
```

---

## 五、API 接口

### 策略组管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategy/groups` | POST | 创建策略组 |
| `/api/strategy/groups` | GET | 列表（可选 `?status=active`） |
| `/api/strategy/groups/<id>` | GET | 详情 |
| `/api/strategy/groups/<id>` | PUT | 更新 |
| `/api/strategy/groups/<id>` | DELETE | 软删除（status=archived） |
| `/api/strategy/groups/<id>/status` | PATCH | 启停（active/paused） |

### 策略订阅

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategy/subscription` | POST | 订阅（需登录） |
| `/api/strategy/subscription/<id>` | DELETE | 取消订阅 |
| `/api/strategy/subscription/mine` | GET | 我的订阅列表 |

---

## 六、核心数据流

```
策略组配置 (strategy_group)
      |
      v
Scheduler 定时触发 / 手动触发
      |
      v
Scanner._load_latest_indicators()  <- indicators_daily (最新日)
Scanner._load_buy_values()         <- stock_analysis.buy
      |
      v
条件匹配 (_match + _eval_condition)
      |
      v
signal_snapshot (写入)
      |
      v
Aggregator.aggregate()
  +-- 维度分组 (stock_basic.industry)
  +-- 事件合并/创建 (group_event)
  +-- 异步 LLM 分析 (LLMExtractor)
       +-- 阶段1: DeepSeek 结构化
       +-- 阶段2: 关键词资讯确认
       +-- 阶段3: DeepSeek 摘要
      |
      v
TrendTracker.track_all() (每日 16:00)
  +-- 指标聚合 (avg_rsi / avg_macd / avg_volume_ratio / avg_score)
  +-- 资讯关联
  +-- 衰减判定 -> suggest_close
```
