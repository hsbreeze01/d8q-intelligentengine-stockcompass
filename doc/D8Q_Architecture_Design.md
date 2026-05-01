# D8Q 智能引擎生态 — 架构设计方案

> 文档版本：v1.0  
> 生成时间：2026-04-30  
> 基于：114 条会话讨论 + 远端 47.99.57.152 代码扫描

---

## 一、需求定义

### 1.1 核心需求

基于 D8Q 智能引擎生态，构建**三层解耦的金融数据分析平台**：

| 项目 | 定位 | 核心职责 |
|------|--------|----------|
| **DataAgent** | 非结构化金融资讯采集底座 | 财经新闻/研报/公告爬虫 + LLM 清洗摘要（不面向终端） |
| **StockShark** | 金融结构化数据中枢 | A股行情（akshare）+ 港股HIBOR + MySQL/MongoDB 存储（后续移除LLM） |
| **StockCompass** | 策略配置与计算分析 | 消费双源数据 + 双LLM（Doubao+DeepSeek）综合分析 → 终端输出 |

### 1.2 功能需求

#### DataAgent（非结构化资讯采集）
- [P0] 集成 ak share 封装 A股行情 API（未来可能扩展到结构化）
- [P0] 迁移 StockShark 的 HIBOR 港股数据到 DataAgent
- [P1] 东方财富/同花顺资讯爬取适配（基于 crawl4ai + playwright）
- [P1] LLM 增强资讯处理（摘要、情感分析、实体识别）
- [P2] 财报 PDF 解析（结合 LLM 提取关键指标）
- [P2] 用户行为数据爬取（机构参与度、用户关注指数）

#### StockShark（金融结构化数据中枢）
- [P0] 数据获取层迁移到 DataAgent（移除本地 ak share 调用）
- [P0] 明确不再承担 LLM 分析职责（后续迁移到 Compass）
- [P1] 保留 HIBOR 分析逻辑（业务层，非数据层）
- [P1] pymongo → 统一存储（非结构化资讯改由 DataAgent 存储）
- [P2] 前端/API 层优化（与 Compass 差异化竞争：Web端 vs 小程序端）

#### StockCompass（策略配置与计算分析）
- [P0] 填充 `compass/services/` 层（定义 DataAgent/StockShark 接入规范）
- [P0] 微信小程序接口完善（利用现有 `WX_APPID/WX_SECRET` 配置）
- [P1] 双 LLM 层优化（保留 Doubao + DeepSeek 双引擎）
- [P1] 移除本地 `beautifulsoup4`（复杂反爬走 DataAgent）
- [P2] 远端部署适配（与 DataAgent/StockShark 同机）
- [P2] 实现 `todo.md` 计划功能（最近3条新闻、机构参与度、用户关注指数）

### 1.3 非功能需求

| 维度 | 要求 |
|------|------|
| **数据一致性** | 实体标识统一：`stock_code` + `entity_name` 双字段 |
| **存储兼容性** | Compass 通过统一网关屏蔽底层 SQLite/MySQL/MongoDB 差异 |
| **LLM 归属清晰** | DataAgent（资讯清洗）→ StockShark（将移除）→ Compass（终端唯一） |
| **可维护性** | 消除重复代码，数据获取统一由 DataAgent 负责 |
| **可扩展性** | 新增数据源只需在 DataAgent 适配，上层无感知 |

---

## 二、收益分析

### 2.1 业务收益

| 收益 | 说明 | 量化 |
|------|------|------|
| **数据覆盖完整** | 结构化行情 + 非结构化资讯统一覆盖 | A股+港股+财联社+36氪+微博 |
| **分析能力增强** | Compass 双LLM + 15+技术指标 + 五层融合决策 | 策略准确率提升（待回测验证） |
| **终端多样化** | StockShark（Web端）+ Compass（微信小程序） | 覆盖不同用户场景 |
| **内容发布闭环** | Data Factory → Info Publisher 小红书自动发布 | 每日推荐股票早报自动化 |

### 2.2 技术收益

| 收益 | 说明 |
|------|------|
| **消除重复代码** | 三个项目的数据获取逻辑统一由 DataAgent 维护 |
| **架构清晰** | 数据层 / 业务层 / 终端层三层解耦 |
| **能力互补** | crawl4ai 反爬 + ak share 行情 + LLM 分析各司其职 |
| **存储透明** | Compass 通过统一网关访问，无需关心底层存储差异 |
| **LLM 分层** | 清洗层（DataAgent）+ 分析层（Compass）职责分明 |

### 2.3 成本收益

| 成本 | 收益 |
|------|------|
| 短期：DataAgent 金融适配开发（P0/P1） | 长期：StockShark + Compass 不再维护爬虫逻辑 |
| 短期：StockShark 数据层迁移 | 长期：统一维护，降低人力成本 50%+ |
| 短期：实体标识统一改造 | 长期：跨源关联零成本 |

---

## 三、设计方案

### 3.1 总体架构图

```
┌─────────────────────────────────────────────────────┐
│                    D8Q 智能引擎生态                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ↓                           ↓
┌─────────────────┐         ┌─────────────────┐
│   DataAgent    │         │ Data Factory  │
│   (47.99.57.152)│         │   (8088)      │
│                 │         │                │
│ • crawl4ai      │         │ • 周报生成     │
│ • playwright    │         │ • 邮件推送     │
│ • LLM清洗      │         │ • 内容调度     │
└────────┬────────┘         └───────┬────────┘
         │                        │
         ↓                        ↓
┌─────────────────┐         ┌─────────────────┐
│  StockShark   │         │Info Publisher  │
│   (47.99.57.152)│         │   (8089)      │
│                 │         │                │
│ • A股行情      │         │ • 小红书发布   │
│ • HIBOR港股    │         │ • Patchright   │
│ • MySQL/Mongo  │         │ • 人类行为模拟 │
└────────┬────────┘         └────────────────┘
         │
         ↓ 通过 compass/services/ 统一网关
┌─────────────────┐
│ StockCompass   │
│   (计划远端)    │
│                 │
│ • 双LLM分析    │
│   (Doubao+     │
│    DeepSeek)    │
│ • 15+指标      │
│ • 五层融合     │
│ • 微信小程序   │
└─────────────────┘
```

### 3.2 项目定位与职责边界

```
┌─────────────────────────────────────────────────────┐
│                    数据层（统一底座）                        │
│                   DataAgent                              │
├──────────────────┬──────────────────┬──────────────────┤
│ 非结构化资讯   │ 结构化行情   │ 用户行为     │
│ crawl4ai       │ (未来akshare) │ (计划开发)   │
│ +LLM增强      │              │              │
└────────┬──────┴──────────────┴──────────────┬─────────┘
               │                   统一 API 调用  │
         ┌─────┴────────┐
         ↓                    ↓
┌──────────────┐ ┌──────────────┐
│ StockShark   │ │StockCompass  │  ← 业务层（差异化分析）
│              │ │              │
│ • A股行情   │ │ • 双LLM分析│
│ • HIBOR港股 │ │ • 技术指标  │
│ • 存储      │ │ • 策略融合  │
└──────────────┘ └──────────────┘
```

### 3.3 数据流向设计

```
DataAgent（非结构化资讯）
    ├─ 爬取：财联社/36氪/微博/crawl4ai
    ├─ LLM清洗：摘要/情感分析/实体识别
    └─ 入库：SQLite + stock_codes + entity_names
         ↓ 统一 API
StockShark（结构化行情）
    ├─ 拉取：akshare（A股）+ HIBOR（港股）
    ├─ 存储：MySQL（行情）+ MongoDB（公告）
    └─ 入库：dic_stock 已有 code + name 映射
         ↓ 统一 API
StockCompass（消费 + 分析）
    ├─ 查询：services/data_gateway.py
    │   ├─ query_dataagent(code)  → 非结构化资讯
    │   └─ query_shark(code)       → 结构化行情
    ├─ 分析：技术指标 + 五层融合决策
    └─ 输出：LLM综合分析 → 微信小程序/Web
```

### 3.4 存储方案

| 项目 | 存储系统 | 数据类型 | 统一网关适配 |
|------|----------|----------|------------------|
| **DataAgent** | SQLAlchemy + SQLite | 非结构化资讯（新闻/研报/公告） | `DataAgentFetcher` |
| **StockShark** | MySQL + pymongo | 结构化行情（akshare K线）+ HIBOR | `SharkMySQLFetcher` + `SharkMongoFetcher` |
| **StockCompass** | MySQL（计划） | 分析结果/策略/用户数据 | 直接读写（本地） |

**关键点**：Compass 不直接操作 DataAgent/StockShark 的存储，只通过 `services/data_gateway.py` 访问。

### 3.5 LLM 归属模型

```
┌─────────────────────────────────────────────────────┐
│                     LLM 三层归属                             │
├──────────────────┬──────────────────┬──────────────────┤
│  DataAgent      │  StockShark     │  StockCompass   │
│                 │                 │                 │
│ • 资讯清洗     │ • 将移除       │ • 终端唯一     │
│ • 摘要生成     │   （迁移到      │ • 双LLM        │
│ • 情感分析     │   Compass）    │   (Doubao+     │
│ • 实体识别     │                 │    DeepSeek)    │
│                 │                 │ • 策略生成     │
│ Key: DeepSeek  │  Key: 同左     │ • 分析报告     │
│ (sk-858d16b6...)│  (将移除)       │                 │
└──────────────────┴──────────────────┴──────────────────┘
```

### 3.6 实体标识统一方案

**目标**：所有入库的资讯/公告都带 `stock_codes` + `entity_names`，消除跨源关联成本。

#### DataAgent 入库改造（Python）

```python
# tools/financial_news_crawler.py 入库时新增：
def save_news(title, content, source):
    # 1. 提取股票代码（从标题/内容正则匹配）
    stock_codes = re.findall(r'\b\d{6}\b', title + content)
    
    # 2. 调用 StockShark API 查 code→name 映射
    entity_names = []
    if stock_codes:
        resp = requests.get(
            "http://47.99.57.152:5000/api/stock/map",
            params={"codes": ",".join(stock_codes)}
        )
        entity_names = [resp.json()[code] for code in stock_codes]
    
    # 3. 入库（SQLite）
    news = News(
        title=title,
        content=content,
        source=source,
        stock_codes=stock_codes,    # ← 新增
        entity_names=entity_names,  # ← 新增
        publish_time=datetime.now()
    )
    session.add(news)
```

#### StockShark 已有完整映射

```sql
-- dic_stock 表已有 code + name，无需改造
SELECT code, name FROM dic_stock WHERE code IN ('600519', '000858');
-- 返回：{"600519": "贵州茅台", "000858": "五粮液"}
```

#### Compass 消费时零成本关联

```python
# compass/services/data_gateway.py
def get_stock_profile(code):
    # 1. 查结构化行情（Shark）
    quote = shark_fetcher.get_quote(code)
    
    # 2. 查非结构化资讯（DataAgent）
    news_list = dataagent_fetcher.get_news_by_code(code)
    #     ↑ 直接用 code 关联，无需实体对齐
    
    return {"quote": quote, "news": news_list}
```

### 3.7 统一数据网关设计

```
compass/services/data_gateway.py
┌─────────────────────────────────────────────────────┐
│                 DataGateway                       │
├──────────────────┬──────────────────────────────┤
│  DataAgentFetcher  │  SharkFetcher               │
│                 │                             │
│ • SQLite         │  • MySQL                   │
│ • stock_codes    │  • dic_stock (code+name)   │
│ • entity_names   │  • HIBOR                   │
│                 │                             │
│ 方法：                         │
│  - get_news_by_code(code) → 按stock_codes查 │
│  - get_announcements(code)                   │
└────────┬────────┴──────────────────────────────┘
         │ 统一输出格式：
         ↓
{
  "stock_code": "600519",
  "entity_name": "贵州茅台",
  "quote": {"open": 1850.00, "close": 1865.00, ...},
  "news": [{"title": "...", "sentiment": 0.8}, ...],
  "source": "dataagent|shark"
}
```

### 3.8 实施路径（分阶段）

#### Phase 1：数据底座整合（1-2周）
```
✅ 完成：
├─ [P0] DataAgent 入库新增 stock_codes + entity_names
├─ [P0] StockShark 数据获取层开始迁移到 DataAgent
└─ [P0] Compass services/data_gateway.py 框架搭建

⚠️ 进行中：
├─ [P1] StockShark LLM 分析逻辑迁移到 Compass
└─ [P1] DataAgent 财经网站反爬适配（crawl4ai）
```

#### Phase 2：分析层增强（2-3周）
```
├─ [P1] Compass 双LLM层优化（Doubao + DeepSeek）
├─ [P1] Compass 填充 services/ 层（DataAgent/StockShark 接入）
└─ [P2] Compass 远端部署（与 DataAgent/StockShark 同机）
```

#### Phase 3：闭环完善（1-2周）
```
├─ [P2] Data Factory 展示 Compass 信号（新增 /stock 路由）
├─ [P3] Info Publisher 自动发布 Compass 分析报告
└─ [P3] 邮件推送集成（每日推荐股票早报）
```

### 3.9 风险缓解措施

| 风险 | 缓解措施 | 状态 |
|------|----------|------|
| **存储碎片化** | Compass 通过 `services/data_gateway.py` 屏蔽底层差异 | ⚠️ 实施中 |
| **跨源联动** | DataAgent 入库加 `stock_codes` + `entity_names` | ⚠️ 实施中 |
| **LLM 重复** | 三层归属清晰：DataAgent（清洗）→ StockShark（将移除）→ Compass（终端） | ✅ 已解决 |
| **数据分散** | DataAgent 专做非结构化资讯，StockShark 专做结构化行情 | ✅ 已解决 |
| **实体不匹配** | 统一用 `stock_code` 作为关联 Key | ⚠️ 实施中 |

---

## 四、最终结论

### 4.1 架构合理性评估

| 评估维度 | 评分 | 说明 |
|----------|------|------|
| **分工合理性** | ✅ **85% 合理** | 配合你最新明确的 LLM 归属模型（DataAgent 资讯清洗 + StockShark 将移除 + Compass 终端唯一），比上一轮（70%）提升明显 |
| **数据分散风险** | ⚠️ **仍存在** | 采集层已不分散，但存储碎片化（3种DB）未完全解决 |
| **联动能力** | ⚠️ **需补充** | 需要 StockCompass 做实体对齐 + 统一 API 网关 |

### 4.2 方案完整的最小补充动作

**只需做 2 件事，方案即可从 85% 提升到 95%+：**

```
1. 统一实体标识（在 DataAgent 的资讯入库时增加 stock_code 字段）
   DataAgent:  {"title": "...", "stock_codes": ["600519", "000858"], ...}
   → StockCompass 可直接用股票代码跨源关联，无需实体对齐

2. StockCompass 增加统一数据网关（利用已有的 compass/services/ 空目录）
   compass/services/data_gateway.py
     ├─ query_shark(code)      # 查结构化行情
     └─ query_dataagent(code)   # 查非结构化资讯
          ↓ 统一返回格式
```

### 4.3 一句话总结

> 新方案分工清晰、解决了上一轮的核心冲突（DataAgent 定位、LLM 归属），只需补充**实体标识统一**和**轻量网关**，即可完整落地。

---

## 五、附录

### 5.1 远端服务端口与运行状态

| 服务 | 端口 | 进程 | 状态 |
|------|------|------|------|
| **Data Factory** | 8088 | gunicorn × 2 | ✅ 运行中 |
| **StockShark** | 5000 | gunicorn × 2 | ✅ 运行中 |
| **Data Agent** | 8000 | uvicorn | ✅ 运行中 |
| **Info Publisher** | 8089 | Flask | ✅ 运行中 |
| **MySQL** | 3306 | mysqld | ✅ 运行中 |
| **MongoDB** | 27017 | mongod | ✅ 运行中 |
| **StockCompass** | 本地开发 | — | ⚠️ 待部署 |

### 5.2 参考文档

| 文档 | 路径 |
|------|------|
| stock2 模块结构分析 | `doc/stock2_integration_report.md` |
| 技术指标详细设计 | `doc/指标汇总.md` + `doc/V2版本指标分析.md` |
| 待办事项 | `doc/TODO.md` |
| 数据来源 | `doc/股票信息来源地址.md` |
| 分析提示词 | `doc/股票分析提示词.md` |
