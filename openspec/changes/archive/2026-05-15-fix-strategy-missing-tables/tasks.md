# Tasks: 修复策略引擎缺失表 + LLM 超时降级

## 1. 建表韧性修复

- [x] **1.1 修改 `init_tables()` 移除 raise，允许单表失败不中断**
  - 文件: `compass/strategy/db.py`
  - 将 `except` 块中的 `raise` 改为 `continue`，确保 6 张表都能尝试创建
  - 同时确保每次 DDL 执行后立即 `commit()`，避免失败事务影响后续

## 2. LLM 分析超时保护

- [x] **2.1 为聚合器 `_trigger_llm_analysis` 添加超时保护**
  - 文件: `compass/strategy/services/aggregator.py`
  - 使用 `concurrent.futures.ThreadPoolExecutor` + `timeout=15` 包装 LLM 调用
  - 捕获 `TimeoutError` 和 `Exception`，记录 WARNING 日志并跳过
  - 添加 `import concurrent.futures` 到文件顶部

## 3. 部署验证

- [x] **3.1 重启服务并验证建表成功**
  - 执行 `systemctl restart d8q-stockshark`（或 compass 对应服务）
  - 检查日志确认 6 张策略表全部 `已就绪`
  - 手动触发一次扫描，验证 `signal_snapshot` 和 `group_event` 有数据写入
