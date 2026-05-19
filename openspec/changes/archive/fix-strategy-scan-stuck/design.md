# Design: 修复策略扫描线程卡死 + 定时扫描可靠性

## 架构决策

### AD1: PooledDB 增加 timeout 参数
**决策**: 在 `PooledDB(blocking=True)` 基础上增加 `timeout=30` 参数。

**理由**: 当前 `blocking=True` 无超时，当连接池耗尽时（100 连接全部占用或 stale），新请求 `connection()` 会无限等待。这是 daemon thread 卡死的主要根因——`_load_latest_indicators()` 内的 `Database()` 调用永远拿不到连接。添加 `timeout=30` 后，30 秒内拿不到连接就抛异常，由上层 catch 处理。

**风险**: 正常情况下不会触发（连接池容量 100），只在极端场景下生效。

### AD2: 健康检查使用独立短连接
**决策**: `_run_scan_background` 的 `SELECT 1` 健康检查改用 `pymysql.connect()` 直接连接，不经过 PooledDB。

**理由**: 如果连接池已耗尽，用同一个连接池做健康检查本身也会阻塞。用独立短连接可以在连接池不可用时快速失败，避免健康检查也成为阻塞点。健康检查连接用完立即关闭，不占用池。

### AD3: APScheduler `_run_scan` 复用超时模式
**决策**: `compass/strategy/scheduler.py` 的 `_run_scan()` 使用与 `_run_scan_background` 相同的内层线程 + `join(timeout=300)` 模式。

**理由**: APScheduler 默认使用线程池执行任务，如果 `_run_scan()` 直接在 APScheduler 线程中执行扫描且卡住，会占用 APScheduler 的工作线程，最终耗尽线程池导致所有定时任务失效。使用内层线程 + timeout 可以确保 APScheduler 线程始终能返回。

### AD4: Pipeline 集成策略扫描
**决策**: 在 `compass/api/app.py` 的 `_start_scheduler` 中，将策略扫描嵌入 `DailyAnalysisTask` 完成后的回调链中。

**理由**: 避免引入新的独立进程/定时器，复用已有的 schedule 线程。扫描在数据更新后的同一轮循环中执行，确保数据新鲜度。

**替代方案（否决）**: 在 APScheduler 中单独注册 17:00 的扫描任务。问题：与 DailyAnalysisTask 完成时间不挂钩，可能扫描到旧数据。

## 数据流

```
手动触发:
  POST /api/strategy/<id>/scan
    → trigger_scan() 创建 run 记录
    → 启动 daemon thread _run_scan_background
      → pymysql.connect() 短连接 SELECT 1（健康检查）
      → 内层 worker thread:
          → Scanner().scan() → Database() → __pool.connection(timeout=30)
            → _load_latest_indicators() → indicators_daily
            → _match() 条件匹配
            → insert_signal_snapshots()
            → Aggregator.aggregate()
      → worker.join(timeout=300)
      → 更新 run 状态

定时触发（APScheduler cron）:
  _run_scan(group_id)
    → 内层 worker thread: Scanner().scan(trigger_type="cron")
    → join(timeout=300)
    → 更新 run 状态

Pipeline 触发（schedule 线程）:
  DailyAnalysisTask.run()
    → 数据采集完成
  DailyRecommendationTask.run()
    → 推荐计算完成
  → _trigger_daily_strategy_scan()
    → list_active_groups()
    → 依次 Scanner().scan(group_id, trigger_type="cron", skip_llm=True)
```

## 修改文件列表

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `compass/data/database.py` | 修改 | PooledDB 增加 `timeout=30` |
| `compass/strategy/routes/signals.py` | 修改 | 健康检查改用 pymysql 短连接 |
| `compass/strategy/scheduler.py` | 修改 | `_run_scan` 增加内层线程超时保护 |
| `compass/api/app.py` | 修改 | schedule 回调链增加策略扫描步骤 |
| `compass/strategy/db.py` | 修改 | `cleanup_stale_runs` 阈值从 30 分钟改为 10 分钟 |
