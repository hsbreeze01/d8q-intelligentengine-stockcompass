# Tasks: replace-doubao-with-deepseek

## Task 1: 替换 LLM 调用
- **file**: `compass/strategy/services/llm_extractor.py`
- **action**: `_run_structured_analysis()` 中 `self.doubao.standard_request(...)` → `self.deepseek.standard_request(...)`
- **verify**: python 直接调用 `_run_structured_analysis()` 返回有效 JSON dict

## Task 2: 重启 compass 并端到端验证扫描
- **action**: 清理旧事件数据，重启 compass，触发扫描
- **verify**:
  1. 扫描在 60s 内完成（不再有 7s Doubao 超时）
  2. `group_event` 表中 `llm_keywords`、`llm_summary` 等字段有内容（非 NULL）
  3. compass.log 无 `Doubao request failed` 或 `Connection error` 错误
