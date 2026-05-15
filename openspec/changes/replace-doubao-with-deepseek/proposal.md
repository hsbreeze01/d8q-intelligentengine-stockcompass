# Proposal: 用 DeepSeek 替换 Doubao 做策略事件结构化分析

## Summary
Doubao bot endpoint 已关闭（ClosedEndpoint），策略扫描后 LLM 分析阶段 1 每次等待 ~7s 超时后失败。DeepSeek 已验证可用，直接替换。

## Motivation
当前每次扫描 4 个事件 × 7s Doubao 超时 = 28s 浪费。替换后 LLM 分析可以正常工作。

## 修改文件
- `compass/strategy/services/llm_extractor.py` — 将 `_run_structured_analysis()` 中的 `self.doubao` 替换为 `self.deepseek`

## 具体修改

### llm_extractor.py

1. 移除 `DoubaoLLM` import（如不再使用）
2. `_run_structured_analysis()` 方法中：
   - `self.doubao.standard_request(...)` → `self.deepseek.standard_request(...)`
3. `__init__` 中移除 `doubao` 参数（可选，保留也无害）
4. `doubao` property 可保留但不再使用

## 验证
```bash
cd /home/ecs-assist-user/d8q-intelligentengine-stockcompass
venv/bin/python -c "
from compass.strategy.services.llm_extractor import LLMExtractor
ext = LLMExtractor()
result = ext._run_structured_analysis({
    'dimension': 'industry',
    'dimension_value': '半导体',
    'stock_count': 5,
    'stock_codes': ['300750'],
    'stock_names': ['宁德时代']
})
print('result:', result)
"
```

## Target Projects
- d8q-intelligentengine-stockcompass
