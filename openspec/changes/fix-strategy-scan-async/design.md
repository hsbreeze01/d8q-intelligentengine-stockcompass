# Design: 策略扫描异步化 + LLM 分析解耦

## 架构决策

### 1. 扫描触发：HTTP 请求 → 后台线程（已实现）

`signals.py` 的 `trigger_scan()` 已改为创建 `strategy_group_run` 记录后启动 `threading.Thread(daemon=True)` 执行 `_run_scan_background()`。HTTP 响应在 202 返回，后台线程独立运行扫描+聚合。

**理由**：Flask + gunicorn sync worker 架构下，`threading.Thread` 是最简单可行的异步方案。不引入 Celery/Redis 等额外依赖，降低运维复杂度。

### 2. LLM 分析：fire-and-forget（已实现）

`aggregator.py` 的 `_trigger_llm_analysis()` 已改为启动独立 daemon 线程，不等待结果。LLM 分析失败仅 log warning，不影响聚合结果。

**理由**：LLM 分析耗时 15-30s/event，同步执行 4 个事件需 60-120s。fire-and-forget 模式让聚合主流程秒级完成，LLM 结果异步写入 DB。

### 3. 定时扫描保持 APScheduler 线程内执行（无需改动）

`APScheduler` 的 `BackgroundScheduler` 已在独立线程池中执行 cron 任务，不阻塞 Flask 请求线程。`_run_scan()` 调用 `scanner.scan(group_id, trigger_type="cron")`，不传 `skip_llm`（默认 False），聚合器会为每个新事件触发 fire-and-forget LLM 分析。

**现状**：定时扫描不需要额外异步化，APScheduler 已经在后台线程运行。

### 4. 新增：扫描运行状态查询端点

新增 `GET /api/strategy/<group_id>/runs/latest` 端点，供前端轮询扫描状态。

**实现**：
- `compass/strategy/db.py` 新增 `get_latest_run(group_id)` — 查询 `strategy_group_run WHERE strategy_group_id = %s ORDER BY started_at DESC LIMIT 1`
- `compass/strategy/routes/signals.py` 新增路由 `get_latest_run()`

### 5. 新增：Stale running 记录清理

策略引擎初始化时清理 stale running 记录。

**实现**：
- `compass/strategy/db.py` 新增 `cleanup_stale_runs()` — 将 `status='running' AND started_at < NOW() - INTERVAL 30 MINUTE` 的记录更新为 `failed`
- `compass/strategy/app.py` 的 `init_strategy_engine()` 调用 `cleanup_stale_runs()`

## 数据流

### 手动扫描流程（改造后）
```
Client → POST /api/strategy/{id}/scan
  → trigger_scan() [Flask 请求线程]
    → create_run() → run_id=42, status='running'
    → threading.Thread(_run_scan_background, daemon=True)
    → return 202 {run_id: 42, status: "running"}  ← 立即返回

  [后台线程]
  → _run_scan_background(1, 42)
    → Scanner.scan(1, run_id=42, skip_llm=True)
      → _load_latest_indicators()  ← 27s
      → _match()  ← 内存操作
      → insert_signal_snapshots()
      → Aggregator.aggregate(1, 42, skip_llm=True)  ← 不触发 LLM
    → update_run(42, status='completed', ...)

Client → GET /api/strategy/{id}/runs/latest  ← 轮询
  → return {id: 42, status: "completed", ...}
```

### 定时扫描流程（无变化）
```
APScheduler → _run_scan(group_id) [APScheduler 线程]
  → Scanner.scan(group_id, trigger_type="cron")
    → create_run() → run_id
    → _load_latest_indicators()
    → _match()
    → insert_signal_snapshots()
    → Aggregator.aggregate(group_id, run_id, skip_llm=False)
      → 创建群体事件
      → _trigger_llm_analysis(event_id)  ← fire-and-forget
        → threading.Thread(_llm_analyze_sync, daemon=True)
          → LLMExtractor.analyze_event(event_id)  ← 30-60s
          → update_event_llm_result(...)
```

## 需要新增/修改的文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `compass/strategy/db.py` | MODIFIED | 新增 `get_latest_run()` 和 `cleanup_stale_runs()` |
| `compass/strategy/routes/signals.py` | MODIFIED | 新增 `GET /strategy/<id>/runs/latest` 路由 |
| `compass/strategy/app.py` | MODIFIED | `init_strategy_engine()` 调用 `cleanup_stale_runs()` |
| `tests/test_strategy/test_async_scan.py` | MODIFIED | 补充 run status 查询和 stale cleanup 测试 |

**不需要修改的文件**（已实现）：
- `compass/strategy/services/scanner.py` — `run_id` 和 `skip_llm` 参数已支持
- `compass/strategy/services/aggregator.py` — fire-and-forget LLM 已实现
- `compass/strategy/scheduler.py` — APScheduler 后台线程执行，无需改动
