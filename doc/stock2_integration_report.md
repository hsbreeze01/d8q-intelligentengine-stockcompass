# stock2 工程整合报告

> 生成日期：2026-04-29 | 目标：为跨工程整合提供技术参考

---

## 一、工程概览

**stock2** 是一个面向中国 A 股市场的 Python 量化分析决策系统，集成数据采集、技术指标计算、多策略分析、LLM 智能分析、Web 展示和桌面 K 线图。

| 维度 | 详情 |
|---|---|
| 语言 | Python 3 |
| Web 框架 | Flask + Jinja2 + Blueprint |
| 数据库 | MySQL (pymysql + DBUtils 连接池) |
| 核心数据源 | akshare (东方财富)、新浪财经、腾讯财经 |
| 指标计算 | TA-Lib + 自定义 funcat DSL |
| AI 引擎 | Doubao (火山引擎) + DeepSeek |
| 调度 | schedule (cron 风格) |
| 桌面端 | PyQtGraph / PyQt5 |

---

## 二、模块架构

```
stock2/
├── stockdata/          ← 🔴 核心 Web 应用 — 系统中枢
│   ├── main.py              Flask 入口 + 蓝注册 + 定时线程
│   ├── page.py              Web 页面蓝图 (推荐/自选/分析)
│   ├── simulation_page.py   模拟交易蓝图
│   ├── stats_api.py         统计 API
│   ├── DailyStockCheckTaskV2.py  ★ 每日核心定时任务
│   ├── calc_indicator.py    技术指标计算 (funcat + TA-Lib)
│   ├── main_analysis.py     ★ 策略编排 + 综合买卖决策
│   ├── stock.py             StockData 类 (akshare 封装)
│   ├── llm.py               LLM 抽象 + Doubao/DeepSeek 实现
│   ├── stock_task.py        个股异步任务
│   ├── security_middleware.py 安全中间件 (限流/蜜罐)
│   └── templates/static/    前端资源
│
├── buy/                ← 🟠 交易/持仓管理
│   ├── Config.py             YAML 多环境配置加载
│   ├── DBClient.py           MySQL 连接池封装
│   ├── task/                 任务定义 (Base/Daily/Current)
│   ├── cache/DicStockFactory.py  股票字典缓存
│   └── bean/StockToday.py   数据对象
│
├── stockfetch/         ← 🟡 数据采集层 (历史数据拉取与存储)
│   ├── main.py              全量拉取编排
│   ├── dic_stock.py         股票字典管理
│   ├── stock_data_daily.py  日线数据入库
│   └── db_kdj/macd/rsi/...  各指标数据库存储模块
│
├── funcat/             ← 🟢 量化分析库
│   ├── api.py               DSL — S(), T(), O, H, L, C, V...
│   ├── indicators.py        KDJ/MACD/RSI/BOLL/ASI/VR...
│   ├── func.py              核心函数 (CrossOver, HHV, LLV...)
│   ├── context.py           执行上下文
│   └── data/db_backend.py   MySQL 数据后端 (生产)
│
├── src/                ← 🔵 桌面应用 + 策略分析库
│   ├── index.py             PyQtGraph K线桌面应用
│   └── analysis/
│       ├── IndicatorAnalysis.py   分析基类
│       ├── kdj/macd/rsi/ma/volume/trade.py  各指标策略
│       └── StrategyAggregation.py  ★ 多策略聚合
│
├── Ashare/             ← 🟣 A股行情双核心库
├── doc/                ← SQL 建表 + 指标文档
├── test/ + tests/      ← 测试代码
└── notebooks/          ← Jupyter Notebook
```

---

## 三、技术指标体系

### 3.1 指标计算引擎

两层指标计算：

| 层 | 引擎 | 指标数 | 说明 |
|---|---|---|---|
| 自定义 DSL | `funcat/indicators.py` | 15 | KDJ/DMI/MACD/RSI/BOLL/WR/BIAS/ASI/VR/ARBR/DPO/TRIX |
| C 库 | TA-Lib (`calc_indicator.py`) | 5 | MACD/KDJ/BOLL/RSI/MA（与 funcat 并行计算） |

### 3.2 策略分析矩阵

每个指标对应一个 `Analysis` 子类，统一流程：**SQL取数据 → 线性回归趋势预测 → 强弱判定 → 金叉死叉 → 策略信号 → 回写DB**

| 分析类 | 分析方法 | 策略变体数 |
|---|---|---|
| **KDJAnalysis** | J值加速度 + 成交量放大 + K>D + K>阈值 + 金叉 | 4 (`kdj_14/15/14_522/15_522`) |
| **RSIAnalysis** | 量比 + RSI斜率加速 + RSI1>RSI2 + 70~90区间 + 金叉 | 2 (`rsi_0_4/0_5`) |
| **MACDAnalysis** | 线性趋势斜率 + 零轴强弱 | 1 |
| **MAAnalysis** | MA5/10/20 线性趋势斜率 | 辅助（不独立交易） |
| **TradeAnalysis** | 60日高低点背离 + MA支撑/压力 + BOLL + 量价背离 + 十字星 | 14+ 信号维度 |

### 3.3 统一趋势预测模式

所有分析类共用 sklearn `LinearRegression` 对最近 N 天做线性拟合：

```python
X = np.array(range(len(values))).reshape(-1, 1)
y = np.array(values).reshape(-1, 1)
slope = LinearRegression().fit(X, y).coef_[0][0]
# slope > 0 → 向上趋势, slope < 0 → 向下趋势
```

---

## 四、多策略融合决策引擎

### 4.1 策略聚合 (`StrategyAggregation`)

将 14 个策略变体结果按日期汇聚到 `stat_strategy_aggregation` 表，标记 win/lose。

### 4.2 综合决策 (`buy_advice_v2`) — 五层递进分析

```
Layer 1: 趋势分析
  ├─ MA5 slope > 0.01 (1%防震荡) + RSI slope > -0.01 + MACD slope > 0
  └─ → 3/3 向好=buy, MA5向下=sell, 其余=hold

Layer 2: 强弱分析
  ├─ RSI>80 or MACD>1    → 超买=sell
  ├─ RSI>50 & MACD>-0.2  → 多方强=buy
  ├─ RSI<20 & MACD<-1    → 超卖=hold(等转折)
  └─ RSI<50 & MACD<-0.2  → 空方强=sell

Layer 3: 金叉死叉
  ├─ RSI/KDJ 低位金叉 → buy
  └─ RSI/KDJ 高位死叉 → sell

Layer 4: 综合买入评分 (buy_star 位运算)
  ├─ MA5 支撑连续天数  → N × 10^(N+3) 分
  ├─ MA20 支撑          → +2000万 分
  ├─ KDJ 底部/金叉       → +10/+1 分
  └─ BOLL 站上 mid      → +3亿 分 (最强信号)

Layer 5: 风险否决
  ├─ 十字星 + 上升通道      → cancel (buy_star=-1)
  ├─ BOLL 上轨卖出信号      → cancel
  ├─ 量价背离               → cancel
  ├─ 新高背离 + 十字星       → sell
  └─ MA5/10/20 间距<1%     → 震荡区间警告
```

---

## 五、外部数据依赖全景

### 5.1 数据源矩阵

| 分类 | 数据源 | 获取方式 | 对应表/用途 |
|---|---|---|---|
| **日线行情** | 东方财富 (akshare) | `ak.stock_zh_a_hist()` | → `stock_data_daily` |
| | 东方财富 (备) | `ak.stock_zh_a_daily()` | → `stock_data_daily` |
| | 新浪财经 (备) | `money.finance.sina.com.cn/.../getKLineData` | Ashare 备用 |
| | 腾讯财经 (备) | `web.ifzq.gtimg.cn/.../fqkline/get` | Ashare 备用 |
| **实时快照** | 东方财富 | `ak.stock_zh_a_spot_em()` | → `dic_stock` (全量初始化) |
| | 新浪财经 | `hq.sinajs.cn/list=` | 实时报价 |
| **行业分类** | 东方财富 | `ak.stock_individual_info_em()` | → `dic_stock.industry` |
| **概念板块** | **新浪 HTML 抓取** | `BeautifulSoup` 解析 `finance.sina.com.cn/realstock/company/{code}/nc.shtml` | → `stock_concept` |
| **盘口** | 东方财富 | `ak.stock_bid_ask_em()` | 实时行情 |
| **新闻** | 东方财富 | `ak.stock_news_em()` | 个股新闻 |
| **机构调研** | 东方财富 | `ak.stock_jgdy_tj_em()` | 机构调研统计 |
| **高管持股** | 东方财富 | `ak.stock_ggcg_em()` | 高管增减持 |
| **大股东** | 东方财富 | `ak.stock_gsrl_gsdt_em()` | 大股东增减持 |
| **市场情绪** | 东方财富 | `ak.stock_comment_detail_scrd_*()` | 用户关注/交易意愿/筹码成本 |
| **资金流向** | 东方财富 (直连HTTP) | `push2his.eastmoney.com/api/qt/stock/fflow/daykline/get` | 个股资金流 |
| **操盘必读** | 东方财富 (直连HTTP) | `emweb.securities.eastmoney.com/PC_HSF10/OperationsRequired/PageAjax` | 主要指标+板块+股东+龙虎榜 |
| **LLM 分析** | 火山引擎 Doubao | `https://ark.cn-beijing.volces.com/api/v3` | 公众号分析文章 |
| | DeepSeek | `https://api.deepseek.com` | 分析文章(备) |
| **微信登录** | 微信开放平台 | `https://api.weixin.qq.com/sns/jscode2session` | 小程序登录 |
| **持久化** | MySQL (本地) | pymysql + DBUtils 连接池 | 全部持久化数据 |

### 5.2 每日数据流

```
17:00 定时触发
  │
  ├─ [1] ak.stock_zh_a_spot_em()           → dic_stock (全市场股票快照, ~5000条)
  ├─ [2] ak.stock_zh_a_hist() × N          → stock_data_daily (每只股票增量日线)
  ├─ [3] ak.stock_individual_info_em() × N → dic_stock.industry (行业分类)
  ├─ [4] 新浪 HTML 抓取 × N                → stock_concept (概念板块)
  ├─ [5] funcat + TA-Lib                   → indicators_daily (KDJ/MACD/RSI/BOLL...)
  ├─ [6] src/analysis/*                    → 策略信号生成 + 聚合
  ├─ [7] buy_advice_v2()                   → stock_analysis (综合买卖建议)
  └─ [8] LLM (Doubao/DeepSeek)            → 公众号分析文章
```

---

## 六、数据库核心表

| 表名 | 行数级 | 核心字段 | 读写模式 |
|---|---|---|---|
| `dic_stock` | ~5000 | code, name, industry, latest_price, 市值, update_time | 每日全量刷新 |
| `stock_data_daily` | ~5000×N天 | date, code, OHLCV, 涨跌幅, 换手率 | 增量追加 |
| `indicators_daily` | ~5000×N天 | code, date, MACD/KDJ/RSI/BOLL/MA... | 每日全量计算 |
| `stock_analysis` | ~5000/天 | code, date, analysis_data(JSON), buy_advice(JSON), buy, sell | 每日新增 |
| `stock_analysis_stat` | 按日聚合 | date, type, category_name, count | 每日聚合 |
| `stock_concept` | 多对多 | stock_code, concept_name | 增量更新 |
| `user_stock` | 按用户 | user_id, stock_code | 用户操作 |
| `user` + `login_log` | — | 用户认证 | 低频写入 |
| `stat_strategy` | 历史全量 | code, strategy, buy_date, win, lose | 分析结果回写 |
| `stat_strategy_aggregation` | 按日聚合 | 14个策略字段 + win/lose | 策略聚合 |

---

## 七、整合要点

### 7.1 可复用模块

| 模块 | 复用价值 | 整合方式 |
|---|---|---|
| `funcat/` | ⭐⭐⭐⭐⭐ 完整的量化DSL | 可直接作为 lib 引入，依赖 MySQL 后端 |
| `src/analysis/` | ⭐⭐⭐⭐ 多策略分析框架 | 抽象 Analysis 基类可扩展新策略 |
| `buy_advice_v2()` | ⭐⭐⭐⭐⭐ 五层决策引擎 | 核心决策函数，输入 JSON → 输出 buy/sell + 评分 |
| `buy/DBClient.py` | ⭐⭐⭐ MySQL 连接池 | 通用 DB 工具，可直接复用 |
| `stockdata/llm.py` | ⭐⭐⭐ LLM 抽象层 | ABC 基类设计良好，可扩展新模型 |
| `stockdata/stock.py` | ⭐⭐ akshare 封装 | 数据获取适配器，可按接口替换 |

### 7.2 已知风险

| 风险 | 等级 | 说明 |
|---|---|---|
| SQL 注入 | 🔴 高 | 大量字符串拼接 SQL (`"\'"+code+"\'"`) |
| API Key 硬编码 | 🔴 高 | `llm.py` 中 Doubao/DeepSeek 密钥明文 |
| 概念板块抓取脆弱 | 🔴 高 | BeautifulSoup 解析新浪 HTML，页面改版即失效 |
| 日线拉取串行 | 🟡 中 | 5000只股票逐只请求，耗时数小时 |
| 无降级机制 | 🟡 中 | akshare 限频后仅重试，无备选数据源切换 |
| 策略硬编码阈值 | 🟡 中 | K=79, K522=64, 1.01止盈 — 无超参优化 |
| 重复指标计算 | 🟡 中 | funcat 和 TA-Lib 各自计算相同指标 |

### 7.3 改进路线图

```
P0 (立即)
├─ 概念板块抓取 → akshare stock_board_concept_cons_em()
├─ API Key → 环境变量
└─ SQL 拼接 → 参数化查询 (DBClient 已支持 param 参数)

P1 (近期)
├─ 日线拉取 → ThreadPoolExecutor 并发
├─ 数据源降级: akshare → tushare → baostock
└─ 统一数据获取层，消除 stockfetch/stockdata 重复代码

P2 (中期)
├─ 引入 backtrader 回测框架替代手工统计
├─ optuna 超参搜索替代硬编码阈值
├─ SQLAlchemy ORM 消除 SQL 注入
└─ FinGPT 等金融专用 LLM 替代通用模型

P3 (长期)
├─ 投资组合优化 (PyPortfolioOpt)
├─ 实时流处理 (Celery + Redis)
└─ ML 信号分类 (XGBoost/LightGBM) 替代线性回归
```

---

## 八、对外接口清单

### 8.1 Flask API 端点

| 路由 | 方法 | 认证 | 说明 |
|---|---|---|---|
| `/` | GET | Session | 股票列表首页 |
| `/login` | POST/GET | 公开 | 用户登录 |
| `/login2` | POST | 公开 | 微信小程序登录 |
| `/register` | POST/GET | 公开 | 用户注册 |
| `/logout` | GET | Session | 登出 |
| `/favorite/add` | POST/GET | Session | 添加自选 |
| `/favorite/delete` | POST | Session | 删除自选 |
| `/favorite/list` | GET | Session | 自选列表 |
| `/recommended/<date>` | GET | 公开 | 推荐股票(按日期) |
| `/recommended2/<date>` | GET | 公开 | 推荐股票V2 |
| `/llm/` | POST | Session | LLM 股票分析对话 |
| `/tracking/` | GET | Session | 股票追踪 |
| `/security/status` | GET | Admin | 安全状态 |
| `/security/dashboard` | GET | Admin | 安全面板 |

### 8.2 外部依赖版本 (requirements.txt)

```
Flask, requests, numpy, openai, akshare, pyyaml,
dbutils, pymysql, cached_property, schedule,
scikit-learn, markdown
```

### 8.3 未列入但实际使用的依赖

```
TA-Lib, pandas, BeautifulSoup4, lxml, flask-compress,
pyqtgraph, qtpy, matplotlib, volcenginesdkarkruntime
```

---

## 九、联系方式

本报告基于 stock2 工程源码静态分析生成，覆盖全部模块、指标、数据源和决策逻辑。如需特定模块的深度分析或整合方案设计，请进一步沟通。
