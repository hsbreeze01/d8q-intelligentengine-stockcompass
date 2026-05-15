# Tasks: 用 DeepSeek 替换 Doubao 做策略事件结构化分析

## 1. LLMExtractor 替换实现

- [x] 1.1 修改 `compass/strategy/services/llm_extractor.py`：移除 DoubaoLLM 导入、`__init__` 中 doubao 参数、doubao property，将 `_run_structured_analysis` 中的 `self.doubao` 调用替换为 `self.deepseek`，更新相关日志文本

## 2. 验证

- [x] 2.1 运行 ruff check 确认无 lint 错误，运行 pytest 确认无回归
