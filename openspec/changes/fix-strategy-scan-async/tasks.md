# Tasks: fix-strategy-scan-async

## Task 1: 扫描路由异步化
- **file**: `compass/strategy/routes/signals.py`
- **action**:
  1. `trigger_scan()` 改为先 `db.create_run()` 创建 running 记录，然后 `threading.Thread(daemon=True)` 启动后台扫描，立即返回 `202 {"run_id": N, "status": "running"}`
  2. 新增 `_run_scan_background(group_id, run_id)` 函数，在后台线程中执行 `Scanner().scan(group_id, run_id=run_id)`
- **verify**: `curl -X POST http://localhost:8087/api/strategy/1/scan` 返回 202

## Task 2: Scanner 支持复用 run_id
- **file**: `compass/strategy/services/scanner.py`
- **action**: `scan()` 方法新增 `run_id=None` 参数。如果传入 run_id 则复用（不重复 create_run），否则自行创建
- **verify**: 传入已有 run_id 时不再创建新记录

## Task 3: LLM 分析 fire-and-forget
- **file**: `compass/strategy/services/aggregator.py`
- **action**:
  1. 删除 `concurrent.futures` 导入和 `_LLM_TIMEOUT` 常量
  2. `_trigger_llm_analysis()` 改为 `threading.Thread(daemon=True).start()`，fire-and-forget 不等待
  3. LLM 分析在独立线程中执行 try/except 包裹，失败只 log warning
- **verify**: 聚合器对 4 个事件触发 LLM 后立即返回（不等 LLM 完成）

## Task 4: Factory proxy scan timeout 调整
- **file**: `app.py`（datafactory）
- **action**: `proxy_strategy_scan()` 路由中，对 scan 请求 proxy timeout 从默认 30s 改为 10s（因为现在 scan API 立即返回 202）
- **verify**: 扫描期间 factory API 正常响应

## Task 5: 端到端验证
- **action**: 重启 compass + factory
- **verify**:
  1. `curl -X POST http://localhost:8087/api/strategy/1/scan` → 202 立即返回
  2. 扫描期间 `curl http://localhost:8087/api/strategy/groups` → 200
  3. 等待 60s 后 DB 中 `strategy_group_run` status 变为 completed
  4. DB 中 `group_event` 有 LLM 分析结果
