# StockShark LLM 调用点审计报告

> 审计日期: 2025-01-01  
> 审计范围: StockShark (localhost:5000) 中涉及 LLM 的 API 端点  
> 目的: 识别待迁移至 StockCompass 的 LLM 分析能力

## 1. StockShark LLM 调用点清单

### 1.1 `/api/analysis/stock/comprehensive` — 综合股票分析

- **调用方**: `compass/api/routes/analysis.py` → `llm_analyze()`
- **调用方式**: POST, `{"stock_code": "...", "scope": "all"}`
- **返回内容**: 包含 `score`、技术分析、趋势判断等综合分析结果
- **LLM 推测**: **高概率使用 LLM** — 该端点返回的分析文本（comprehensive analysis）需要综合多维度数据生成自然语言结论
- **迁移优先级**: **P0 — 核心分析能力**
- **Compass 替代方案**: 已部分替代 — `llm_analyze()` 获取 Shark 数据后用 Compass 自有 DeepSeekLLM 生成文章，但 Shark 端仍可能做了一次 LLM 分析

### 1.2 `/api/stock/analyze` — 股票行情分析

- **调用方**: `compass/services/data_gateway.py` → `SharkFetcher.get_quote()`
- **调用方式**: POST, `{"symbol": stock_code}`
- **返回内容**: 包含 `success` 标志和 `data` 字段的行情分析数据
- **LLM 推测**: **中概率** — 如果返回的数据包含文本分析（而非纯数值指标），则使用了 LLM
- **迁移优先级**: **P1 — 数据获取**
- **Compass 替代方案**: `DataGateway.get_stock_profile()` 已实现聚合，但底层仍依赖此端点

### 1.3 `/api/stock/map` — 股票代码映射

- **调用方**: `compass/services/data_gateway.py` → `SharkFetcher.get_stock_map()`
- **调用方式**: GET, `?codes=600519,000001`
- **返回内容**: `{code: name}` 映射字典
- **LLM 推测**: **不使用 LLM** — 纯数据库查询
- **迁移优先级**: 无需迁移

### 1.4 `/api/stock/by-keyword` — 关键词搜索

- **调用方**: `compass/services/data_gateway.py` → `SharkFetcher.search_by_keyword()`
- **调用方式**: GET, `?keyword=...`
- **返回内容**: 匹配的股票列表
- **LLM 推测**: **不使用 LLM** — 纯搜索/匹配
- **迁移优先级**: 无需迁移

## 2. Compass 现有 LLM 使用情况

### 2.1 DeepSeekLLM (`compass/llm/deepseek.py`)

| 调用位置 | 用途 | 状态 |
|---------|------|------|
| `compass/api/routes/analysis.py` → `llm_analyze()` | 生成股票分析文章 | ✅ 已在用 |
| `compass/api/routes/report.py` → `generate_report()` | 生成周报 | ✅ 已在用 |
| `compass/llm/deepseek.py` → `stock_message()` | 股票消息分析模板 | ⚠️ 已定义但未在路由中使用 |

### 2.2 DoubaoLLM (`compass/llm/doubao.py`)

| 调用位置 | 用途 | 状态 |
|---------|------|------|
| `compass/llm/doubao.py` → `stock_message()` | 股票消息分析模板 | ⚠️ 已定义但未在路由中使用 |

> **注意**: DoubaoLLM 已实现但尚未在任何 API 路由中被调用。Task 3.2 需要激活双 LLM 协同能力。

### 2.3 DataAgent LLM 委托

| 调用位置 | 用途 | 合规性 |
|---------|------|--------|
| `compass/api/routes/policy.py` → `classify_policy()` | 政策分类（委托 DataAgent） | ✅ 合规 — DataAgent 仅做清洗 |

## 3. 迁移计划

### Phase 1: Task 3.2 — 实现等价 LLM 分析接口

需要实现的接口：
1. **综合分析接口** — 替代 `/api/analysis/stock/comprehensive`
   - 输入: stock_code, scope
   - 处理: 从 Shark 获取纯数值行情数据 → Compass 双 LLM（Doubao 结构化分析 + DeepSeek 深度文章）
   - 输出: 包含 score + 分析文章的统一格式

2. **双 LLM 协同模式**
   - DoubaoLLM: 快速结构化分析（技术面评分、趋势判断、买卖信号）
   - DeepSeekLLM: 深度文章生成（公众号风格分析文章）

### Phase 2: Task 3.3 — 配置管理

- Compass `.env` 中管理 `DOUBAO_API_KEY` + `DEEPSEEK_API_KEY`（已实现）
- 确保各层 key 独立

### Phase 3: Task 3.4 — 移除 StockShark LLM

- 确认 Compass 完全替代后，标记 StockShark 中可安全移除的 LLM 代码
- 需要修改的 StockShark 文件（待确认）:
  - 综合分析接口中的 LLM 调用逻辑
  - 相关 prompt 配置

## 4. 风险与注意事项

1. **数据依赖**: Compass 的 LLM 分析依赖 Shark 返回的数值数据。如果 Shark 的 `/api/analysis/stock/comprehensive` 同时做数据获取和 LLM 分析，迁移时需要确保纯数据获取部分保留
2. **向后兼容**: 迁移期间 Shark 端点应保持可用，Compass 新接口并行运行
3. **LLM Key 隔离**: Compass 的 Doubao/DeepSeek key 与 DataAgent 的清洗 key 必须独立
