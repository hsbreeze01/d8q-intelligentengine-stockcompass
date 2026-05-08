# Design: dic_stock 同步脚本

## 架构决策

### 1. 数据源选择：akshare THS/Sina

**决策**：使用 `akshare.stock_info_a_code_name()` 获取股票列表 + `akshare.stock_zh_a_spot()` 获取实时行情。

**理由**：
- 项目已依赖 `akshare>=1.15`，无需引入新依赖
- `stock_zh_a_spot()` 使用 Sina 数据源，proposal 确认可用且约 15s 完成
- 避免使用 EM push2 相关接口（已知问题）
- 旧方案使用 tushare 已完全注释掉，不走回头路

### 2. 同步策略：全量替换

**决策**：每次同步全量获取所有 A 股数据，UPSERT 到 `dic_stock` 表。

**理由**：
- A 股总数约 5200 条，全量同步一次约 15-20 秒，性能可接受
- UPSERT（`ON DUPLICATE KEY UPDATE`）保证幂等性，重复执行安全
- 增量同步需要跟踪上次同步时间，复杂度高，当前无必要

### 3. 批量写入

**决策**：每 500 条一批执行 `INSERT ... ON DUPLICATE KEY UPDATE`。

**理由**：
- 避免单次 SQL 过大导致 MySQL `max_allowed_packet` 限制
- 500 条/批 × 11 批 ≈ 5200 条，合理平衡批次数量和单批大小
- 遵循项目现有 `Database` 上下文管理器模式

### 4. API 端点异步执行

**决策**：`POST /api/sync/dic-stock` 使用后台线程执行同步，立即返回 202。

**理由**：
- 同步耗时 15-20 秒，HTTP 请求不应阻塞
- 使用 `threading.Thread` 而非 celery/任务队列，与项目现有调度器模式一致
- 用模块级锁防止并发重复同步

## 数据流

```
                    ┌──────────────────────┐
                    │   CLI / API 触发      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  stock_info_a_code_name()  │ ── 股票列表 (code, name)
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  stock_zh_a_spot()    │ ── 实时行情 (~5200行 DataFrame)
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  字段映射 & 类型转换    │ ── 标准化记录列表
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  批量 UPSERT (500/批)  │ ── MySQL dic_stock 表
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  摘要报告 (log + return)│
                    └──────────────────────┘
```

## 需要新增的文件

| 文件 | 说明 |
|---|---|
| `compass/sync/__init__.py` | 包初始化，空文件 |
| `compass/sync/dic_stock_sync.py` | 核心同步逻辑：获取、映射、批量 UPSERT |
| `compass/api/routes/sync.py` | 同步触发 API 端点 Blueprint |

## 需要修改的文件

| 文件 | 变更 |
|---|---|
| `compass/api/app.py` | 注册 `sync` Blueprint |

## 复用的现有组件

| 组件 | 来源 | 用途 |
|---|---|---|
| `Database` | `compass/data/database.py` | MySQL 连接与查询执行 |
| `_is_admin()` | `compass/api/routes/admin.py` 模式 | 管理员权限校验 |
| `logger` | `compass/utils/logger.py` | 统一日志 |

## 关键实现细节

### 数据库交互

使用项目现有的 `Database` 上下文管理器：

```python
from compass.data.database import Database

with Database() as db:
    db.execute(sql, params)
```

### UPSERT SQL 模板

```sql
INSERT INTO dic_stock (code, stock_name, latest_price, ...)
VALUES (%s, %s, %s, ...)
ON DUPLICATE KEY UPDATE
  stock_name = VALUES(stock_name),
  latest_price = VALUES(latest_price),
  ...
```

### 行情字段名映射

`stock_zh_a_spot()` 返回的 DataFrame 列名（Sina 数据源，中文列名）：

| akshare 列名 | dic_stock 列名 |
|---|---|
| 代码 | code |
| 名称 | stock_name |
| 最新价 | latest_price |
| 涨跌幅 | change_percentage |
| 涨跌额 | change_amount |
| 成交量 | volume |
| 成交额 | turnover |
| 振幅 | amplitude |
| 最高 | highest |
| 最低 | lowest |
| 今开 | open_today |
| 昨收 | close_yesterday |
| 换手率 | turnover_rate |
| 市盈率-动态 | pe_ratio_dynamic |
| 市净率 | pb_ratio |
| 总市值 | total_market_value |
| 流通市值 | circulating_market_value |

> 注：实际列名以 akshare 版本为准，脚本中需做防御性处理，缺失列自动映射为 NULL。

### 并发控制

```python
import threading
_sync_lock = threading.Lock()
_sync_running = False
```

API 端点检查 `_sync_running` 标志，防止并发同步。
