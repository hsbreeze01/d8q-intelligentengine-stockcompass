# Proposal: 补全 stock_basic.industry 字段

## 背景
策略组引擎的聚合器（Aggregator）按行业维度对信号进行分组聚合。但当前 stock_basic 表的 industry 字段全部为空（0/5512），导致聚合器无法按行业工作。

## 目标
1. 从 akshare 获取 A 股行业分类数据
2. 批量更新 stock_basic.industry 字段
3. 提供行业数据同步 API（已有 industry_sync 服务，需验证可用性）
4. 验证聚合器的行业维度功能

## 现有代码
- `compass/strategy/services/industry_sync.py` — IndustrySync 类，已有 sync() 方法
- `compass/strategy/routes/industry_sync.py` — 已有 Flask Blueprint 路由
- stock_basic 表已有 industry 列（VARCHAR(50)），只需填充数据

## 变更范围
- 可能需要修复 industry_sync.py 中的 akshare 接口调用（接口可能已变化）
- 验证同步 API 能正确更新 stock_basic.industry
- 确保 Aggregator 能正确使用 industry 字段

## 成功标准
- stock_basic.industry 非空率 > 90%
- 行业数据同步 API 可正常调用
- 聚合器能按行业维度分组信号
