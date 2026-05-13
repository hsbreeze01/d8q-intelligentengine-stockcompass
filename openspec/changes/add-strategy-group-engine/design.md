# Design: Strategy Group Engine — Phase 1 Backend Core

## Architecture Overview

策略组引擎是一个独立的 FastAPI 服务（端口 8090），与现有 Compass Flask 服务（端口 8087）并行运行。它复用 Compass 的数据库访问层（`compass.data.database.Database`）和现有数据表（indicators_daily、stock_data_daily、stock_analysis、stock_basic），新增 4 张表存储策略配置和扫描结果。

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Strategy Engine (:8090)                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ CRUD     │  │ Scanner  │  │ Aggregator            │  │
│  │ Routes   │  │ Engine   │  │ (post-scan hook)      │  │
│  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘  │
│       │              │                    │              │
│  ┌────▼──────────────▼────────────────────▼───────────┐  │
│  │              Database Layer                         │  │
│  │  (compass.data.database.Database)                  │  │
│  └────────────────────┬───────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │           APScheduler (scan_cron)                   │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │  MySQL              │
              │  stock_analysis_    │
              │  system             │
              │                    │
              │  [existing tables]  │
              │  - stock_analysis   │
              │  - indicators_daily │
              │  - stock_data_daily │
              │  - stock_basic      │
              │  - dic_stock        │
              │                    │
              │  [new tables]       │
              │  - strategy_group   │
              │  - signal_snapshot  │
              │  - group_event      │
              │  - strategy_group_  │
              │    run              │
              └────────────────────┘
```

## Key Design Decisions

### D1: FastAPI 独立服务而非 Flask Blueprint
**理由**: 策略组引擎有独立的扫描调度需求（APScheduler），且未来可能需要高频 SSE 推送。FastAPI 原生支持 async 和 SSE，不干扰现有 Compass Flask 服务的稳定性。

**约束**: 复用 `compass.data.database.Database` 模块，不重复实现数据库连接管理。通过 `sys.path` 引入 compass 包。

### D2: 信号扫描复用已有计算结果
**理由**: indicators_daily 已有每日计算好的技术指标值（KDJ、RSI、MACD、BOLL、MA、Volume 等），stock_analysis 已有 buy 字段（buy_star）。扫描引擎只做条件匹配，不重新计算指标，保证扫描速度。

**实现**: 每次扫描从 indicators_daily 读取最新一天的所有股票数据，在内存中做条件过滤。5512 只股票 × ~30 个指标字段，内存占用可控。

### D3: 聚合器作为扫描后置钩子
**理由**: 聚合器不需要独立调度，而是在每次扫描完成后自动执行。扫描 → 生成 signal_snapshot → 触发聚合检测。这样聚合始终基于最新信号，逻辑简单。

### D4: JSON 字段存储策略配置
**理由**: conditions、aggregation 等配置结构灵活多变，用 JSON 字段存储比拆成多张关联表更简单。MySQL 8.0 支持 JSON 类型和函数查询，但本阶段只在应用层解析 JSON，不依赖 MySQL JSON 函数。

### D5: 行业数据通过 akshare 同步
**理由**: stock_basic.industry 当前全部为空。akshare 的 `stock_board_industry_name_em` 接口可获取东方财富行业分类。提供本地 JSON 文件作为降级方案。只需运行一次同步，后续新股票可通过定时任务补全。

## Data Flow

### 扫描流程
```
1. APScheduler / 手动触发 → Scanner.scan(strategy_group_id)
2. 从 DB 加载策略组配置
3. 从 indicators_daily 读取最新日期所有股票数据（单次批量查询）
4. 从 stock_analysis 读取最新 buy 值（关联 buy_star）
5. 遍历每只股票，按 conditions + signal_logic 匹配
6. 匹配成功 → 写入 signal_snapshot
7. 创建 strategy_group_run 记录（统计信息）
8. 触发 Aggregator.aggregate(strategy_group_id, run_id)
9. Aggregator 按 dimension 分组 → 检测群体事件 → 写入/更新 group_event
```

### 群体事件聚合流程
```
1. 获取本次扫描的所有 signal_snapshot（按 run_id）
2. 关联 stock_basic 获取 industry/concept/theme
3. 按 dimension 分组统计
4. 对每组：检查是否已有 open 状态的同 dimension + dimension_value 事件
   - 有且在时间窗口内 → 追加股票，更新聚合指标
   - 无 → 如果 stock_count ≥ min_stocks → 创建新 group_event
5. 检查所有 open 事件，关闭超出时间窗口的
```

## Database Schema — New Tables

### strategy_group
```sql
CREATE TABLE strategy_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    indicators JSON NOT NULL COMMENT '["KDJ", "RSI", "MACD"]',
    signal_logic ENUM('AND', 'OR', 'SCORING') NOT NULL DEFAULT 'AND',
    conditions JSON NOT NULL COMMENT '[{"indicator":"KDJ_K","operator":">","value":80}]',
    scoring_threshold INT DEFAULT NULL COMMENT 'SCORING 模式的达标阈值',
    aggregation JSON NOT NULL COMMENT '{"dimension":"industry","min_stocks":3,"time_window_minutes":60}',
    scan_cron VARCHAR(100) DEFAULT NULL COMMENT 'cron 表达式',
    status ENUM('active', 'paused', 'archived') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### strategy_group_run
```sql
CREATE TABLE strategy_group_run (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    trigger_type ENUM('cron', 'manual') NOT NULL DEFAULT 'manual',
    total_stocks INT DEFAULT 0,
    matched_stocks INT DEFAULT 0,
    status ENUM('running', 'completed', 'failed') NOT NULL DEFAULT 'running',
    error_message TEXT DEFAULT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME DEFAULT NULL,
    duration_seconds FLOAT DEFAULT NULL,
    FOREIGN KEY (strategy_group_id) REFERENCES strategy_group(id),
    INDEX idx_sg_status (strategy_group_id, status),
    INDEX idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### signal_snapshot
```sql
CREATE TABLE signal_snapshot (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_id INT NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100) DEFAULT NULL,
    indicator_snapshot JSON NOT NULL COMMENT '触发时刻的指标值',
    buy_star INT DEFAULT NULL COMMENT 'stock_analysis.buy 字段',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_group_id) REFERENCES strategy_group(id),
    FOREIGN KEY (run_id) REFERENCES strategy_group_run(id),
    INDEX idx_sg_created (strategy_group_id, created_at DESC),
    INDEX idx_stock (stock_code, created_at DESC),
    INDEX idx_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### group_event
```sql
CREATE TABLE group_event (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_id INT DEFAULT NULL COMMENT '首次创建时的扫描 run_id',
    dimension VARCHAR(50) NOT NULL COMMENT 'industry/concept/theme',
    dimension_value VARCHAR(100) NOT NULL COMMENT '半导体/新能源等',
    stock_count INT NOT NULL DEFAULT 0,
    avg_buy_star FLOAT DEFAULT NULL,
    max_buy_star INT DEFAULT NULL,
    matched_stocks JSON NOT NULL COMMENT '[{"code":"000001","name":"平安","buy_star":4}]',
    status ENUM('open', 'closed', 'analyzed') NOT NULL DEFAULT 'open',
    window_start DATETIME NOT NULL COMMENT '时间窗口起始',
    window_end DATETIME NOT NULL COMMENT '时间窗口结束',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_group_id) REFERENCES strategy_group(id),
    INDEX idx_dim (dimension, dimension_value),
    INDEX idx_status (status, created_at DESC),
    INDEX idx_sg (strategy_group_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## File Structure

```
compass/
├── strategy/                          # 新模块
│   ├── __init__.py
│   ├── app.py                         # FastAPI 应用创建 + 生命周期
│   ├── models.py                      # Pydantic 模型（请求/响应 schema）
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── strategy_groups.py         # 策略组 CRUD 路由
│   │   ├── signals.py                 # 信号查询 + SSE 路由
│   │   └── events.py                  # 群体事件查询路由
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scanner.py                 # 信号扫描引擎
│   │   ├── aggregator.py              # 群体事件聚合器
│   │   └── industry_sync.py           # 行业数据同步
│   ├── scheduler.py                   # APScheduler 封装
│   └── db.py                          # 数据库建表 + 辅助查询
├── data/
│   └── industry_mapping.json          # 行业分类降级数据（可选）
├── scripts/
│   └── run_strategy_engine.py         # 启动脚本
└── tests/
    └── test_strategy/
        ├── test_crud.py
        ├── test_scanner.py
        ├── test_aggregator.py
        └── test_industry_sync.py
```

## Dependencies

新增依赖（需添加到 pyproject.toml）：
- `fastapi>=0.111` — Web 框架
- `uvicorn>=0.30` — ASGI 服务器
- `apscheduler>=3.10` — 定时任务调度
- `sse-starlette>=2.0` — SSE 推送支持
- `pydantic>=2.0` — 请求/响应模型（FastAPI 内置）

现有依赖复用：
- `pymysql` / `dbutils` — 数据库连接
- `akshare` — 行业分类数据

## Service Management

服务通过 systemd 管理，服务名 `d8q-strategy`：
```ini
[Unit]
Description=StockCompass Strategy Engine
After=network.target mysql.service

[Service]
ExecStart=/path/to/venv/bin/python -m uvicorn compass.strategy.app:app --host 0.0.0.0 --port 8090
Restart=always
```

重启命令：`systemctl restart d8q-strategy`
