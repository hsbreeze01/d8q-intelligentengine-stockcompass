# Proposal: 策略扫描异步化 + LLM 分析解耦

## Summary
策略扫描（scanner → aggregator → LLM 分析）在 gunicorn 同步 worker 中全量执行，耗时 3-5 分钟，阻塞 worker 导致所有 API 返回 502。需将扫描改为异步执行，LLM 分析从主流程解耦。

## Motivation
当前问题链：
1. **gunicorn 502**：2 workers，扫描占 1 个 worker 3-5 分钟，期间 API 全部 502
2. **LLM 阻塞**：聚合器对每个事件同步调用 DeepSeek（15s 超时 × 4 事件 = 60s），超时保护在 gunicorn preload 下不生效
3. **worker 被 kill**：gunicorn `--timeout 300`，扫描+聚合+LLM 总耗时超 300s → worker 被 gunicorn master 杀掉 → systemd 重启
4. **功能缺陷**：`_trigger_llm_analysis` 中 `ThreadPoolExecutor` 15s 超时在 gunicorn 下无效，因为线程和 worker 共享命运

## Expected Behavior
1. 触发扫描 → API 立即返回（run_id + status="running"）→ 前端可轮询进度
2. 扫描在后台线程中执行（scanner → aggregator → 写入 DB）
3. LLM 分析独立于扫描，不阻塞聚合和扫描完成
4. 扫描期间其他 API 正常响应（不被 502）

## Root Cause Analysis

### 调用链
```
POST /api/strategy/1/scan
  → trigger_scan()  [gunicorn worker 线程]
    → Scanner.scan()
      → _load_latest_indicators() (27s, 4800 rows)
      → _match() (1850 matched)
      → insert_signal_snapshots()
      → Aggregator.aggregate()
        → 对每组信号聚合
        → insert_group_event()
        → _trigger_llm_analysis() × 4 事件
          → LLMExtractor.analyze_event()
            → DeepSeek 结构化分析 (~15s/event)
            → 关键词搜索
            → DeepSeek 摘要生成 (~15s/event)
    → return result  [总耗时 ~180s]
```

### 为什么 ThreadPoolExecutor 超时无效
gunicorn 使用 sync worker，所有请求在主线程处理。`ThreadPoolExecutor` 创建的子线程与 worker 共享进程，gunicorn master 监控的是 worker 进程而非线程。当 worker 进程超过 `--timeout 300s` 时被杀，所有线程一起死。线程内的 `future.result(timeout=15)` 只控制线程内等待，但 DeepSeek API 调用本身在 openai 库中用了 socket 级别超时（60s），ThreadPoolExecutor 的 timeout 无法中断正在进行的 socket 读取。

## Scope
- **Compass**: `compass/strategy/routes/signals.py` — 扫描路由改为异步
- **Compass**: `compass/strategy/services/aggregator.py` — LLM 分析从聚合流程中完全剥离
- **Compass**: `compass/strategy/services/scanner.py` — scan() 改为可选异步
- **Factory**: `app.py` — proxy scan 路由增加 timeout 处理

## Target Projects
- d8q-intelligentengine-stockcompass（主要修改）
- d8q-intelligentengine-datafactory（proxy timeout 调整）

## Design

### 核心改动：扫描异步化

**signals.py `trigger_scan()`**：
```python
@bp.route("/strategy/<int:group_id>/scan", methods=["POST"])
def trigger_scan(group_id):
    # 创建 run 记录（status=running）
    run_id = db.create_run(group_id, trigger_type="manual")
    
    # 启动后台线程执行扫描
    import threading
    thread = threading.Thread(
        target=_run_scan_background,
        args=(group_id, run_id),
        daemon=True,
    )
    thread.start()
    
    return jsonify({"run_id": run_id, "status": "running"}), 202

def _run_scan_background(group_id, run_id):
    """后台线程中执行扫描+聚合（不含 LLM）"""
    try:
        scanner = Scanner()
        result = scanner.scan(group_id, run_id=run_id, skip_llm=True)
        db.update_run(run_id, status="completed", ...)
    except Exception as exc:
        db.update_run(run_id, status="failed", error_message=str(exc))
        logger.error("后台扫描失败 run_id=%d: %s", run_id, exc)
```

**aggregator.py `_trigger_llm_analysis()`**：
改为 fire-and-forget：创建独立线程调用 LLM，不等待结果，不阻塞聚合。
```python
def _trigger_llm_analysis(self, event_id):
    import threading
    thread = threading.Thread(
        target=self._llm_analyze_sync,
        args=(event_id,),
        daemon=True,
    )
    thread.start()

def _llm_analyze_sync(self, event_id):
    try:
        extractor = LLMExtractor()
        extractor.analyze_event(event_id)
    except Exception as exc:
        logger.warning("LLM 分析失败 event=%d: %s", event_id, exc)
```

**scanner.py `scan()`**：
新增 `run_id` 参数（复用已创建的 run）和 `skip_llm` 参数。
```python
def scan(self, strategy_group_id, trigger_type="manual", run_id=None, skip_llm=False):
    if run_id is None:
        run_id = db_helpers.create_run(strategy_group_id, trigger_type=trigger_type)
    # ... 扫描逻辑不变 ...
    # 聚合器调用时传 skip_llm
    agg = Aggregator()
    events_created = agg.aggregate(strategy_group_id, run_id, skip_llm=skip_llm)
```

**Factory proxy timeout**：
`_strategy_proxy` 对 scan 请求增加 timeout 到 10s（只需等待 run 创建，不等待扫描完成）。

### 前端配合
`loadStrategyAdmin` 中的手动扫描按钮改为：触发 → 显示"扫描中" → 轮询 `/api/strategy/groups/{id}/runs/latest` → 完成后刷新。这可以作为后续优化，当前先确保 API 不 502。

## 验证
1. `curl -X POST http://localhost:8087/api/strategy/1/scan` → 202 + `{"run_id": N, "status": "running"}` 立即返回
2. 扫描期间 `curl http://localhost:8087/api/strategy/groups` → 200（正常响应）
3. `strategy_group_run` 表最终 status 变为 completed
4. `group_event` 表有 LLM 分析结果（可能延迟 30-60s）
