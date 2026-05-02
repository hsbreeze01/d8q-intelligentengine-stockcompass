# D8Q 智能引擎架构规范

> 最后更新: 2026-05-02
> 状态: 已确认

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────┐
│  Factory (聚合生产层)                                     │
│  面向用户的统一入口。不做具体计算，聚合各服务能力输出给用户。     │
│  端口: 8088                                              │
└──────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │
           ▼              ▼              ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Compass         │  │  Compass         │  │  Agent           │
│  (计算分析中枢)   │──│  (计算分析中枢)   │  │  (数据采集层)     │
│                  │  │                  │  │                  │
│  技术/策略/回测   │  │  LLM分析/周报    │  │  爬虫/AI增强      │
│  选股/用户体系    │  │  政策/通知       │  │  政策分类/摘要    │
│  端口: 8087      │  │                  │  │  端口: 8000      │
└────────┬─────────┘  └──────────────────┘  └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Shark           │
│  (数据底座)       │
│                  │
│  行情/研报/公告   │
│  搜索/供应链      │
│  数据入库/爬取    │
│  端口: 5000      │
└──────────────────┘

┌──────────────────┐
│  Publisher       │
│  (内容推送层)     │
│  公众号/小红书    │
│  端口: 8089      │
└──────────────────┘
```

## 2. 各工程定位与边界

### 2.1 Factory — 聚合生产层

| 属性 | 说明 |
|---|---|
| **定位** | 面向用户的统一入口，聚合各服务能力 |
| **原则** | **不做具体计算**，只做编排和呈现 |
| **端口** | 8088 (Gunicorn) |
| **分支** | premium |

**职责:**
- 用户界面渲染（前端页面）
- API 代理（转发到 Compass/Agent/Shark）
- 内容生产编排（调用各服务组合输出）
- 用户认证与权限管理
- LLM 内容创作（小红书风格资讯速递/研究报告）

**不做:**
- ❌ 股票计算/分析（调 Compass）
- ❌ 新闻爬取/分类（调 Agent）
- ❌ 行情数据获取（调 Shark）

---

### 2.2 Compass — 股票金融计算分析中枢

| 属性 | 说明 |
|---|---|
| **定位** | 所有股票/金融相关计算和分析的权威服务 |
| **原则** | 管计算不管数据，调 Shark 获取原始数据 |
| **端口** | 8087 (Gunicorn) |
| **分支** | main |

**职责:**
- 技术指标计算（MA/MACD/RSI/KDJ/BOLL/VR/WR/ASI 等）
- 选股推荐（DailyStockCheckTask）
- 交易策略分析（buy_advice）
- 回测框架
- 模拟交易
- LLM 分析文章生成（调 Shark 拿数据 + 自有 LLM）
- 政策分析（调 Agent 做分类，自己做影响分析）
- 周报生成（调 Agent 拿资讯 + 调 Shark 拿研报 + LLM 生成）
- 赛道热度分析
- 用户体系（登录/注册/收藏/订阅/管理后台）
- 邮件推送通知

**不做:**
- ❌ 行情数据爬取（调 Shark）
- ❌ 研报/公告原始获取（调 Shark）
- ❌ 新闻爬取（调 Agent）

**依赖:**
- **Shark**: 行情数据、研报、公告、搜索、code↔name映射
- **Agent**: 新闻资讯、政策分类、摘要

---

### 2.3 Agent — 数据采集层

| 属性 | 说明 |
|---|---|
| **定位** | 所有外部数据的采集和智能化处理 |
| **原则** | 管采集和处理，是新闻/资讯数据的唯一权威来源 |
| **端口** | 8000 (Uvicorn) |
| **分支** | premium |

**职责:**
- 多源新闻爬取（财联社、36氪、微博、小红书、每日经济等）
- LLM 增强处理（内容提取、完整性分析、摘要生成、质量评估）
- 政策/监管类资讯分类（唯一权威）
- NER 实体提取（股票代码、公司名称）
- 赛道热度聚合
- 定时任务调度

**不做:**
- ❌ 股票行情/计算（调 Shark 或 Compass）
- ❌ 前端界面（Factory 负责）

---

### 2.4 Shark — 数据底座

| 属性 | 说明 |
|---|---|
| **定位** | 股票金融原始数据的唯一权威来源 |
| **原则** | 管数据不管计算，只提供原始数据和简单查询 |
| **端口** | 5000 (Gunicorn) |
| **分支** | premium |

**职责:**
- 行情数据获取与入库（AkShare: 实时/历史/估值/财务）
- 全量/增量股票数据爬取与存储
- 研报聚合（洞见研报 + 慧博投研 + 巨潮公告，三源并行）
- 研报搜索
- 公告获取
- 股票搜索（行业/概念/主题/关键词）
- code ↔ name 批量映射
- 供应链分析与图谱
- 定时数据更新调度

**不做:**
- ❌ 技术指标计算（Compass 负责）
- ❌ 交易策略/选股（Compass 负责）
- ❌ LLM 分析（逐步迁移到 Compass）
- ❌ 用户体系/前端页面

---

### 2.5 Publisher — 内容推送层

| 属性 | 说明 |
|---|---|
| **定位** | 将生产好的内容推送到各平台 |
| **原则** | 只负责推送，不生产不计算 |
| **端口** | 8089 (Gunicorn) |

**职责:**
- 公众号内容发布
- 小红书内容发布
- 其他平台分发

---

## 3. 依赖规则（强制）

```
依赖方向: 上层 → 下层（禁止反向依赖）

Factory  →  Compass, Agent, Shark, Publisher
Compass  →  Shark, Agent
Agent    →  Shark (仅限股票代码映射等轻量查询)
Shark    →  无（最底层，不依赖其他服务）
Publisher→  Factory (获取待发布内容)

禁止:
  ❌ Compass → Factory （计算中枢不依赖聚合层）
  ❌ Shark → Compass  （数据层不依赖计算层）
  ❌ Shark → Agent    （数据层不依赖采集层）
  ❌ Agent → Compass  （采集层不依赖计算层）
  ❌ Agent → Factory  （采集层不依赖聚合层）
```

## 4. LLM 使用归属

| LLM 场景 | 归属工程 | 调用方式 |
|---|---|---|
| 新闻内容提取/补全 | Agent | 直接调用 DeepSeek |
| 新闻完整性分析 | Agent | 直接调用 DeepSeek |
| 新闻摘要生成 | Agent | 直接调用 DeepSeek |
| 新闻质量评估 | Agent | 直接调用 DeepSeek |
| 政策/监管分类 | **Agent** | 直接调用 DeepSeek。Compass/Factory 调 Agent API |
| 股票综合分析文章 | **Compass** | 调 Shark 拿数据，自有 LLM 生成分析文章 |
| 周报生成 | **Compass** | 调 Agent+Shark 拿数据，自有 LLM 生成周报 |
| 政策影响分析 | **Compass** | 调 Agent 做分类，自有 LLM 做影响分析 |
| 小红书资讯速递 | Factory | 直接调用 DeepSeek |
| 小红书研究报告 | Factory | 调 Shark 拿研报数据，自有 LLM 生成 |
| 公告 AI 解读 | Factory | 直接调用 DeepSeek |
| 赛道热度摘要 | Factory | 直接调用 DeepSeek |

**LLM 统一配置:**
- 模型: DeepSeek (`deepseek-chat` / `deepseek-reasoner`)
- 所有工程均已配置 retry (2次指数退避)
- 所有工程均已配置 timeout (60s)

## 5. P1 消除功能重复计划

| # | 重复场景 | 当前状态 | 目标状态 | 改动工程 |
|---|---|---|---|---|
| 1 | 政策分类 | Factory + Compass 各一套 | Agent 统一提供，Factory/Compass 调 Agent API | Agent(补API), Compass(改调Agent), Factory(改调Agent) |
| 2 | 摘要生成 | Agent + Factory 各一套 | Agent 统一提供，Factory 调 Agent API | Agent(补API), Factory(改调Agent) |
| 3 | LLM股票分析 | Shark `llm_analyzer` + Compass `stock_message` | Compass 调 Shark 拿数据+自有LLM。Shark `llm_analyzer` 的 `_gather_data()` 保留为数据接口，LLM 分析逻辑逐步迁移到 Compass | Compass(改调Shark拿数据), Shark(数据接口化) |
| 4 | 周报生成 | Factory + Compass 各一套 | Compass 统一提供，Factory 调 Compass API | Compass(补API), Factory(改调Compass) |
| 5 | 技术指标计算 | Shark `DataProcessor` + Compass `stockdata/` | Compass 统一，Shark 只提供原始行情数据 | Compass(自有), Shark(确认只提供raw data) |

## 6. 共享资源

### 数据库
| 数据库 | 用途 | 使用者 |
|---|---|---|
| MySQL `stock_analysis_system` | 股票基础数据、行情、研报、公告 | Shark(写入), Compass(读取) |
| SQLite `financial_news.db` | 新闻资讯数据 | Agent(写入), Factory(读取) |
| SQLite `task_store.db` | 定时任务 | Agent |
| MongoDB `stock_analysis_system` | 评估缓存 | Shark |
| MySQL `stock` (旧版) | Compass 旧模块 | Compass (逐步废弃) |

### API Key
| 服务 | Key | 使用者 |
|---|---|---|
| DeepSeek | `sk-858d...1a8f` | Agent, Shark, Compass, Factory |
| 慧博投研 | 账号: 18516519320 | Shark |
| 微信小程序 | appid: wx2c30afda72db1ad8 | Compass |

## 7. 服务管理

```bash
# 统一启停脚本
/home/ecs-assist-user/d8q-services.sh {start|stop|restart|status} [agent|factory|shark|publisher]

# Compass 单独管理（gunicorn）
pkill -f "gunicorn.*compass"  # 停止
# 启动见 start_compass.sh
```

### 日志位置
| 服务 | 日志 |
|---|---|
| Factory | `/var/log/d8q/factory.log`, `/var/log/d8q/factory-access.log` |
| Agent | `/home/ecs-assist-user/logs/agent/uvicorn.log` |
| Shark | `/var/log/d8q/shark.log`, `/var/log/d8q/shark-access.log` |
| Compass | `/var/log/d8q/compass.log`, `/var/log/d8q/compass-access.log` |
| Publisher | `/home/ecs-assist-user/logs/publisher/app.log` |
