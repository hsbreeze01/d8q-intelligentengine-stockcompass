# Design: 用 DeepSeek 替换 Doubao 做策略事件结构化分析

## 背景与动机

Doubao bot endpoint 已关闭（ClosedEndpoint），导致策略扫描后 LLM 分析阶段 1 每次等待 ~7s 超时后失败。
每次扫描 4 个事件 × 7s 超时 = 28s 浪费。DeepSeek 已验证可用，直接替换。

## 架构决策

### 决策 1：用 DeepSeek 替换 Doubao 用于结构化分析

**理由：** DeepSeek 同样支持 JSON 结构化输出，且已通过阶段 3 验证可用。Doubao endpoint 已关闭，无法恢复。

**影响范围：** 仅影响 `compass/strategy/services/llm_extractor.py`。`compass/services/llm_analysis.py`（股票分析服务）仍使用 Doubao + DeepSeek 双 LLM 模式，本次不修改。

### 决策 2：移除 LLMExtractor 中 DoubaoLLM 依赖

**理由：** LLMExtractor 的 doubao 属性仅用于阶段 1 结构化分析，替换后不再需要。移除死代码可减少维护负担。

**注意：** `compass/llm/doubao.py` 文件保留，因为 `compass/services/llm_analysis.py` 仍在使用 DoubaoLLM。

## 数据流

```
事件触发 → LLMExtractor.analyze_event()
  ├── 阶段 1: DeepSeek → 结构化 JSON (event_type, keywords, ...)
  ├── 阶段 2: DataGateway → 关键词搜索确认
  └── 阶段 3: DeepSeek → 深度摘要 markdown
```

替换前后变化：
- **Before:** 阶段 1 Doubao, 阶段 3 DeepSeek（两个不同 LLM）
- **After:** 阶段 1 DeepSeek, 阶段 3 DeepSeek（同一个 LLM）

## 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `compass/strategy/services/llm_extractor.py` | MODIFY | 移除 DoubaoLLM 导入/属性，阶段 1 改用 DeepSeek |

### 不修改的文件

- `compass/llm/doubao.py` — 保留，`llm_analysis.py` 仍在使用
- `compass/llm/deepseek.py` — 无需修改
- `compass/llm/__init__.py` — 无需修改
- `compass/services/llm_analysis.py` — 股票分析服务，不在本次范围

## 具体修改点

### `compass/strategy/services/llm_extractor.py`

1. **Import 行：** 移除 `DoubaoLLM` 导入
   - `from compass.llm import DoubaoLLM, DeepSeekLLM` → `from compass.llm import DeepSeekLLM`

2. **`__init__` 方法：** 移除 `doubao` 参数和 `self._doubao` 属性

3. **`doubao` property：** 移除整个 property

4. **`_run_structured_analysis` 方法：**
   - `self.doubao.standard_request(...)` → `self.deepseek.standard_request(...)`
   - 错误日志中的 "Doubao" → "DeepSeek"

## 风险评估

- **低风险：** DeepSeek 的 `standard_request` 接口与 Doubao 一致（都继承自 `base.py`），调用方式无变化。
- **输出质量：** DeepSeek 结构化 JSON 输出质量与 Doubao 相当，prompt 无需调整。
