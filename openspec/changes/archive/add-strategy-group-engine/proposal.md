# Proposal: Strategy Group Engine — Phase 1 Backend Core

## Summary
实现策略组引擎的核心后端：策略组管理 CRUD、信号扫描器、群体事件聚合器、行业数据补全。这是策略组引擎的第一阶段实现。

## Motivation
Compass 已有完整的指标计算（8 类技术指标 + buy_advice_v2 综合决策引擎）和 5500+ 只股票的日线数据。但缺少从个股信号到群体事件的自动化检测能力。投资经理需要手动逐只翻看股票分析，无法自动发现行业级别的共振信号。

策略组引擎解决的核心问题：当多只同行业股票同时出现底部反转信号时，自动检测、聚合、并通过 LLM 分析确认。

## Expected Behavior

### 1. 策略组管理 CRUD
- 创建策略组：选择指标（KDJ/RSI/MACD/BOLL/MA/Volume 等）+ 配置触发条件 + 组合逻辑（AND/OR/SCORING）+ 聚合规则（维度/阈值/时间窗口）+ 扫描频率
- 编辑策略组：修改任何配置项
- 删除策略组：软删除（状态改为 archived）
- 启停策略组：active / paused 切换
- 列表查询：按状态/创建时间筛选

### 2. 信号扫描引擎
- 按 strategy_group.indicators + signal_logic 扫描全市场股票
- 从 indicators_daily + stock_data_daily 读取最新数据
- 匹配每个策略组的条件表达式
- 生成 signal_snapshot 记录（触发时刻的指标快照 + buy_star 评分）
- 支持定时扫描（APScheduler）和手动触发

### 3. 群体事件聚合器
- 按 strategy_group.aggregation.dimension（industry/concept/theme）分组
- 在时间窗口内检测同维度 ≥ min_stocks 只股票触发 = 群体事件
- 新信号匹配已有事件（同 target + 时间窗口内）→ 追加股票
- 不匹配 → 创建新 group_event
- 计算 avg_buy_star、stock_count 等聚合指标

### 4. 行业数据补全
- stock_basic.industry 当前全部为空（0/5512）
- 群体事件聚合的 industry 维度依赖此字段
- 需要从可用数据源（akshare 或其他）补全行业分类

### 5. API 层
- FastAPI 服务 :8090
- 策略组 CRUD: POST/PUT/DELETE/GET /api/strategy/*
- 信号查询: GET /api/signals/*
- 事件查询: GET /api/events/*
- 扫描触发: POST /api/strategy/{id}/scan
- SSE 推送: GET /api/signals/stream

### 6. 数据库表
- strategy_group：策略组配置（JSON 字段存储指标/逻辑/聚合规则）
- signal_snapshot：信号快照（触发时刻的指标值 + buy_star）
- group_event：群体事件（聚合结果 + LLM 分析结果字段预留）
- strategy_group_run：扫描执行记录

## Technical Constraints
- 数据库: MySQL stock_analysis_system, root/password, localhost:3306
- Python 3.12, 复用现有 venv
- 复用现有模块: calc_indicator.py, main_analysis.py (buy_advice_v2), dic_stock
- 不修改现有表结构，只新增 4 张表
- FastAPI 独立服务（:8090），不改动现有 Compass Flask（:8087）
- 行业数据优先通过 akshare stock_board_industry_name_em（如果被封则用本地映射文件）
- 信号扫描应复用已有的 indicators_daily 数据，不重复计算指标
- buy_star 直接复用 stock_analysis 表中的 buy 字段

## Scope
- IN SCOPE: 4 张新表 + CRUD API + 信号扫描器 + 聚合器 + 行业补全 + APScheduler 定时扫描
- OUT OF SCOPE: LLM 特征提取（Phase 2）、前端站点、趋势跟踪（已砍）、采集密度（已砍）
