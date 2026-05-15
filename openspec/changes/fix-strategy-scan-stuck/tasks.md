# Tasks: fix-strategy-scan-stuck

## Task 1: 清理卡死的扫描记录 + DB 连接池 ping 检测
- **file**: `compass/data/database.py`
- **action**:
  1. 在 `PooledDB()` 初始化参数中添加 `ping=1`（连接从池中取出时检查有效性，如果失效则自动重建）
  2. 执行 SQL 清理卡死的 run：`UPDATE strategy_group_run SET status='failed', error_message='手动清理-卡死线程' WHERE status='running' AND started_at < NOW() - INTERVAL 10 MINUTE;`
- **verify**: `SELECT * FROM strategy_group_run WHERE status='running';` 应返回空

## Task 2: 后台扫描线程增加超时保护
- **file**: `compass/strategy/routes/signals.py`
- **action**:
  1. 重写 `_run_scan_background(group_id, run_id)`：
     - 启动前先用 `Database()` 做 `SELECT 1` 验证连接可用，失败直接标记 run 为 failed
     - 使用内层 thread + `join(timeout=300)` 实现超时控制（因为 daemon thread 中 signal.SIGALRM 不可用）
     - 超时后标记 run 为 failed，error_message="扫描超时（300s）"
  2. 确保所有异常路径都调用 `db_helpers.update_run(status="failed", ...)`
- **verify**: 代码中不存在未捕获异常导致 run 永远卡在 running 的路径

## Task 3: 添加定时扫描
- **file**: `scripts/pipeline.py`
- **action**:
  1. 在 daily update 函数（或 daemon 模式的 scheduled job）末尾，数据采集完成后，添加策略扫描触发逻辑：
     - `from compass.strategy import db as strategy_db` → `list_active_groups()`
     - 对每个 active 策略组调用 `Scanner().scan(group_id, trigger_type="cron", skip_llm=True)`
     - 每个 group 的扫描 try/except 包裹，单个失败不影响后续
  2. 添加日志：`logger.info("策略组 %d 定时扫描完成, matched=%d", group_id, result.get("matched_count", 0))`
- **verify**: 重启 compass 后，pipeline daemon 会在 16:30 触发 daily update + 策略扫描

## Task 4: 端到端验证
- **action**:
  1. 重启 compass：`systemctl restart d8q-compass`
  2. 手动触发扫描：`curl -X POST http://localhost:8087/api/strategy/1/scan`
  3. 验证返回 202 + run_id
  4. 等待 60s，检查 `SELECT * FROM strategy_group_run ORDER BY id DESC LIMIT 3;` → 最新 run status=completed
  5. 检查 `SELECT COUNT(*) FROM signal_snapshot WHERE run_id = <最新run_id>;` → 有数据
  6. 检查 `SELECT * FROM group_event ORDER BY id DESC LIMIT 3;` → 有聚合结果
- **verify**: 扫描正常完成，不再卡在 running
