# Tasks: 修复策略扫描线程卡死 + 定时扫描可靠性

## 1. 连接池超时保护

- [ ] **1.1** PooledDB 增加 `timeout=30` 参数 + 健康检查改用 pymysql 短连接
  - 文件: `compass/data/database.py` — `_init_pool` 中 PooledDB 添加 `timeout=30`
  - 文件: `compass/strategy/routes/signals.py` — `_run_scan_background` 健康检查改用 `pymysql.connect()` 直接连接（从 config 读取连接参数），用完立即关闭
  - 文件: `compass/strategy/db.py` — `cleanup_stale_runs` 阈值从 `INTERVAL 30 MINUTE` 改为 `INTERVAL 10 MINUTE`

## 2. APScheduler 定时扫描超时保护

- [ ] **2.1** `_run_scan` 增加内层线程 + 300s 超时机制
  - 文件: `compass/strategy/scheduler.py` — `_run_scan(group_id)` 改为先 `create_run(group_id, trigger_type="cron")` 创建 run 记录，再用内层线程执行 `scanner.scan()`，`join(timeout=300)` 后更新 run 状态
  - 复用 `signals.py::_run_scan_background` 的相同模式（健康检查 + 内层线程 + timeout）

## 3. Pipeline 数据更新后触发策略扫描

- [ ] **3.1** Schedule 回调链增加每日策略扫描步骤
  - 文件: `compass/api/app.py` — 在 `_start_scheduler` 的 `run_analysis_then_recommendation()` 末尾增加策略扫描调用
  - 新增辅助函数 `_trigger_daily_strategy_scan()`: 查询所有 active 策略组，依次调用 `Scanner().scan(group_id, trigger_type="cron", skip_llm=True)`，每个组用 try/except 独立包裹
  - 复用 `compass/strategy/db.list_active_groups()` 查询活跃策略组
