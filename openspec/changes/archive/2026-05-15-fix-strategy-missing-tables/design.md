# Design: 修复策略引擎缺失表 + LLM 超时降级

## 问题根因

### 1. 缺失表 — `init_tables()` 失败即中断

`compass/strategy/db.py` 的 `init_tables()` 遍历 `_TABLES` 字典执行 DDL，但遇到异常直接 `raise`，导致后续表不会创建。

当前代码：
```python
def init_tables():
    with Database() as db:
        for name, ddl in _TABLES.items():
            try:
                db.execute(ddl)
                db.commit()
            except Exception as exc:
                logger.error("建表失败 %s: %s", name, exc)
                raise  # ← 这里中断了后续建表
```

推测：`signal_snapshot`（第 4 张）创建失败后，`group_event`（第 5 张）和 `trend_tracking`（第 6 张）未被创建。后续扫描写入 `signal_snapshot` 或更新 `group_event` 时报 `Unknown column` 错误。

### 2. LLM 分析阻塞 — Doubao 连接失败无超时

`compass/strategy/services/aggregator.py` 的 `_trigger_llm_analysis()` 同步调用 `LLMExtractor().analyze_event()`，其中 Doubao 连接失败时每次耗时 6-7 秒。28 个事件 × 6.5s ≈ 3 分钟，远超扫描应有的 30 秒。

`DoubaoLLM.standard_request()` 已有 try/except 返回 `None`，但网络层超时由 volcengine SDK 的默认配置控制，没有显式上限。

## 修复方案

### 方案 1: init_tables 韧性化（核心）

**文件**: `compass/strategy/db.py`

**改动**: 移除 `raise`，改为 `continue`。每张表独立 try/except + commit。

```python
def init_tables():
    with Database() as db:
        for name, ddl in _TABLES.items():
            try:
                db.execute(ddl)
                db.commit()
                logger.info("表 %s 已就绪", name)
            except Exception as exc:
                logger.error("建表失败 %s: %s", name, exc)
                # 不再 raise，继续创建后续表
```

**效果**: 即使某张表失败，后续表仍会被创建。重启服务后 `init_tables()` 再次运行，因使用 `IF NOT EXISTS`，已存在的表会被跳过，失败的表有机会重试。

### 方案 2: 聚合器 LLM 分析加超时

**文件**: `compass/strategy/services/aggregator.py`

**改动**: 为 `_trigger_llm_analysis` 添加超时保护。使用 `concurrent.futures.ThreadPoolExecutor` + `timeout` 参数。

```python
import concurrent.futures

_LLM_TIMEOUT = 15  # 单事件 LLM 分析超时上限（秒）

def _trigger_llm_analysis(self, event_id: int):
    from compass.strategy.services.llm_extractor import LLMExtractor
    extractor = LLMExtractor()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extractor.analyze_event, event_id)
        try:
            future.result(timeout=_LLM_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.warning("LLM 分析超时 event=%d (>%ds), 跳过", event_id, _LLM_TIMEOUT)
        except Exception as exc:
            logger.warning("LLM 分析失败 event=%d: %s", event_id, exc)
```

**效果**: 单事件 LLM 分析超过 15 秒自动放弃，不阻塞聚合主流程。

### 方案 3: init_strategy_engine 不中断应用启动

**文件**: `compass/strategy/app.py`

当前代码已经对 `init_tables()` 和 `start_scheduler()` 分别 try/except，不需要改动。但需确认 `init_tables()` 内部不再 `raise`（方案 1 已处理）。

## 数据流（修复后）

```
[服务启动]
  └─ create_app()
       └─ _start_scheduler()
            └─ init_strategy_engine()
                 ├─ init_tables()          ← 创建全部 6 张表（韧性化）
                 │    ├─ strategy_subscription  ✓
                 │    ├─ strategy_group          ✓
                 │    ├─ strategy_group_run       ✓
                 │    ├─ signal_snapshot           ✓ (若失败，继续)
                 │    ├─ group_event                ✓ (若失败，继续)
                 │    └─ trend_tracking              ✓
                 └─ start_scheduler()     ← 启动 APScheduler

[手动扫描]
  └─ Scanner.scan()
       ├─ 读取 indicators_daily + stock_analysis
       ├─ 条件匹配 → 写入 signal_snapshot      ← 表已存在
       ├─ Aggregator.aggregate()
       │    ├─ 按维度聚合 → 写入 group_event     ← 表已存在
       │    └─ _trigger_llm_analysis()           ← 超时保护
       │         └─ LLMExtractor (15s timeout)
       └─ 返回扫描结果
```

## 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `compass/strategy/db.py` | MODIFY | `init_tables()` 移除 raise，改为 continue |
| `compass/strategy/services/aggregator.py` | MODIFY | `_trigger_llm_analysis()` 添加超时保护 |

## 验证步骤

1. 在服务器上重启服务 → `systemctl restart d8q-stockshark`（或对应 compass 服务）
2. 观察日志：6 张表全部 `已就绪`
3. 手动触发扫描 → 验证 `signal_snapshot`、`group_event` 有数据写入
4. 观察日志：LLM 分析超时或成功均有合理日志，无长时间阻塞
