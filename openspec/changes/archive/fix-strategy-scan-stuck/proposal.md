# Proposal: 修复策略扫描线程卡死 + 添加定时扫描

## Summary
策略扫描在后台 daemon thread 中执行时，`_run_scan_background()` 卡在 running 状态无法完成（run_id=7 自 5月15日 20:08 至今仍为 running，total_stocks=0, matched_stocks=0）。同时，当前缺少策略组的定时扫描机制——cron 中没有策略扫描任务，需要新增。

## Motivation

### 问题 1：后台扫描线程卡死
- `strategy_group_run` 表 run_id=7 卡在 `status=running`，started_at=2026-05-15 20:08:57
- total_stocks=0, matched_stocks=0 → 扫描线程在初始化阶段就卡住了
- DB 连接池当前 27 个连接（其中 10 个 Sleep 136s），连接池配置 maxconnections=100，理论上够用
- **根因假设**：`_run_scan_background()` 在 gunicorn fork 后的 daemon thread 中执行，`Database()` 类的连接池 `__pool` 是类变量，gunicorn fork 后子进程继承父进程的连接池状态（含已失效的 MySQL 连接），导致新线程拿到的连接可能是 stale 的

### 问题 2：缺少定时扫描
- crontab 中无策略扫描任务
- pipeline daemon 的 APScheduler 只做数据采集（16:30 触发），不含策略扫描
- `strategy_group.scan_cron` 字段存在但从未被消费

## Expected Behavior
1. 手动触发扫描 → 后台线程正常完成 → `strategy_group_run` status 变为 completed/failed
2. 16:30 数据采集完成后，自动触发所有 active 策略组的扫描
3. DB 连接在 daemon thread 中正确获取和释放

## Root Cause Analysis

### 调用链
```
POST /api/strategy/1/scan  (gunicorn worker)
  → trigger_scan()
    → db_helpers.create_run()  → Database() → __pool.connection() ✅ (在 worker 主线程中)
    → threading.Thread(target=_run_scan_background, daemon=True).start()
    
  _run_scan_background (daemon thread):
    → Scanner()
      → scanner.scan(group_id, run_id=7)
        → _load_latest_indicators()
          → Database() → __pool.connection()  ← 可能卡在这里
            → PooledDB(maxconnections=100, blocking=True)
              → 如果连接池满了或连接失效 → blocking=True 会无限等待
```

### 可能的根因
1. **gunicorn fork 后连接池状态问题**：`Database.__pool` 是类变量，gunicorn preload 时在 master 进程创建连接池，fork 后 worker 继承。daemon thread 在 worker 进程中运行，可能拿到 stale 连接
2. **`_load_latest_indicators()` 查询锁等待**：4851 行的 SELECT 可能在等待表锁
3. **Scanner.__init__ 中的 DB 初始化**：`Scanner` 构造函数没做 DB 操作，但 `scanner.scan()` 调用了 `_load_latest_indicators()` → `Database()` → 连接池初始化

### 佐证
- run_id=7 的 total_stocks=0, matched_stocks=0 → 卡在 `_load_latest_indicators()` 之前或之中
- DB 连接池 10 个 Sleep 连接都 Sleep 136s → 可能是被 daemon thread 打开但未被正确使用/释放

## Scope
- **Compass**: `compass/strategy/routes/signals.py` — 后台扫描线程增加超时保护和连接验证
- **Compass**: `compass/strategy/services/scanner.py` — 扫描方法增加连接健康检查
- **Compass**: `compass/data/database.py` — 连接池增加 stale 连接检测
- **Compass**: `scripts/pipeline.py` — 在 daily update 完成后触发策略扫描

## Target Projects
- d8q-intelligentengine-stockcompass

## Design

### 修复 1：后台扫描线程超时保护

**signals.py `_run_scan_background()`**：
- 增加 overall timeout（300s），超时后标记 run 为 failed
- 在 thread 启动前验证 DB 连接可用（先做一次 `SELECT 1`）
- 如果 DB 连接不可用，直接标记 failed 并 return

```python
def _run_scan_background(group_id: int, run_id: int):
    """后台线程：执行扫描 + 聚合，更新 run 状态"""
    import datetime
    from compass.strategy.services.scanner import Scanner

    # 1. 先验证 DB 连接可用
    try:
        from compass.data.database import Database
        with Database() as db:
            db.select_one("SELECT 1 AS health_check")
    except Exception as exc:
        logger.error("后台扫描 DB 连接验证失败 run=%d: %s", run_id, exc)
        db_helpers.update_run(run_id, status="failed", error_message=f"DB连接失败: {exc}",
                              finished_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return

    # 2. 执行扫描（带超时）
    import signal
    def _timeout_handler(signum, frame):
        raise TimeoutError("扫描超时（300s）")
    
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(300)  # 5分钟超时
        
        scanner = Scanner()
        result = scanner.scan(group_id, run_id=run_id, skip_llm=True)
        
        signal.alarm(0)  # 取消超时
        
        db_helpers.update_run(run_id, status="completed", ...)
    except TimeoutError as exc:
        signal.alarm(0)
        db_helpers.update_run(run_id, status="failed", error_message=str(exc), ...)
    except Exception as exc:
        signal.alarm(0)
        logger.error("后台扫描失败 group=%d run=%d: %s", group_id, run_id, exc, exc_info=True)
        try:
            db_helpers.update_run(run_id, status="failed", error_message=str(exc), ...)
        except Exception:
            logger.error("更新 run 失败状态也失败 run=%d", run_id, exc_info=True)
```

**注意**：`signal.SIGALRM` 只能在主线程使用。daemon thread 不是主线程，所以 SIGALRM 不可用。替代方案：用 `threading.Timer` 或在 `_load_latest_indicators` 中增加查询超时。

**替代方案（推荐）**：使用 `threading.Event` + 超时机制：
```python
def _run_scan_background(group_id: int, run_id: int):
    import datetime
    from compass.strategy.services.scanner import Scanner

    result_container = {}
    
    def _do_scan():
        try:
            scanner = Scanner()
            result_container["result"] = scanner.scan(group_id, run_id=run_id, skip_llm=True)
        except Exception as exc:
            result_container["error"] = exc

    scan_thread = threading.Thread(target=_do_scan, daemon=True)
    scan_thread.start()
    scan_thread.join(timeout=300)  # 5分钟超时

    if scan_thread.is_alive():
        # 扫描超时
        db_helpers.update_run(run_id, status="failed", error_message="扫描超时（300s）", ...)
    elif "error" in result_container:
        db_helpers.update_run(run_id, status="failed", error_message=str(result_container["error"]), ...)
    else:
        result = result_container.get("result", {})
        db_helpers.update_run(run_id, status="completed", ...)
```

### 修复 2：Database 连接池 stale 检测

**database.py**：在 `PooledDB` 初始化时增加 `ping` 参数：
```python
self.__class__.__pool = PooledDB(
    pymysql,
    ...,
    ping=1,  # 1 = check when connection is fetched from pool
)
```

### 修复 3：定时扫描

**scripts/pipeline.py**：在 daily update 完成后，触发策略扫描：
```python
# 在 daily_update() 函数末尾添加：
def _trigger_strategy_scan():
    """在 daily update 完成后触发所有 active 策略组扫描"""
    from compass.strategy import db as strategy_db
    groups = strategy_db.list_active_groups()
    for group in groups:
        try:
            from compass.strategy.services.scanner import Scanner
            scanner = Scanner()
            scanner.scan(group["id"], trigger_type="cron", skip_llm=True)
            logger.info("策略组 %d 定时扫描完成", group["id"])
        except Exception as exc:
            logger.error("策略组 %d 定时扫描失败: %s", group["id"], exc)
```

## 验证
1. 先清理卡住的 run_id=7：`UPDATE strategy_group_run SET status='failed', error_message='手动清理-卡死' WHERE id=7;`
2. 手动触发扫描 → 202 立即返回 → 60s 内 `strategy_group_run` status 变为 completed
3. 检查 group_event 表有新聚合结果
4. 检查 pipeline daily update 日志，确认策略扫描被触发
