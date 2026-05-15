"""策略组引擎 — 数据库建表 + 辅助查询"""
import json
import logging
from typing import List, Optional

from compass.data.database import Database

logger = logging.getLogger("compass.strategy.db")

# ---------------------------------------------------------------------------
# DDL — 4 张新表
# ---------------------------------------------------------------------------
_TABLES = {
    "strategy_subscription": """
CREATE TABLE IF NOT EXISTS strategy_subscription (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    strategy_group_id INT NOT NULL,
    subscribed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_strategy (user_id, strategy_group_id),
    INDEX idx_user (user_id),
    INDEX idx_group (strategy_group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "strategy_group": """
CREATE TABLE IF NOT EXISTS strategy_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    indicators JSON NOT NULL COMMENT '指标列表',
    signal_logic ENUM('AND', 'OR', 'SCORING') NOT NULL DEFAULT 'AND',
    conditions JSON NOT NULL COMMENT '触发条件数组',
    scoring_threshold INT DEFAULT NULL COMMENT 'SCORING 模式达标阈值',
    aggregation JSON NOT NULL COMMENT '聚合规则',
    scan_cron VARCHAR(100) DEFAULT NULL COMMENT 'cron 表达式',
    status ENUM('active', 'paused', 'archived') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "strategy_group_run": """
CREATE TABLE IF NOT EXISTS strategy_group_run (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "signal_snapshot": """
CREATE TABLE IF NOT EXISTS signal_snapshot (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "group_event": """
CREATE TABLE IF NOT EXISTS group_event (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_group_id INT NOT NULL,
    run_id INT DEFAULT NULL COMMENT '首次创建时的扫描 run_id',
    dimension VARCHAR(50) NOT NULL COMMENT 'industry/concept/theme',
    dimension_value VARCHAR(100) NOT NULL COMMENT '维度值',
    stock_count INT NOT NULL DEFAULT 0,
    avg_buy_star FLOAT DEFAULT NULL,
    max_buy_star INT DEFAULT NULL,
    matched_stocks JSON NOT NULL COMMENT '匹配股票列表',
    status ENUM('open', 'closed', 'analyzed') NOT NULL DEFAULT 'open',
    lifecycle ENUM('tracking', 'suggest_close', 'closed') DEFAULT 'tracking',
    llm_keywords JSON DEFAULT NULL COMMENT 'Doubao 提取的关键词',
    llm_summary TEXT DEFAULT NULL COMMENT 'DeepSeek 生成的摘要',
    llm_confidence FLOAT DEFAULT NULL COMMENT 'Doubao 置信度',
    llm_drivers JSON DEFAULT NULL COMMENT '驱动因素',
    llm_related_themes JSON DEFAULT NULL COMMENT '关联主题',
    news_confirmed BOOLEAN DEFAULT NULL COMMENT '消息面是否确认',
    news_confirm_score FLOAT DEFAULT NULL COMMENT '确认度评分 0-1',
    news_matched JSON DEFAULT NULL COMMENT '匹配资讯列表',
    suggest_close_reason TEXT DEFAULT NULL COMMENT '衰减原因',
    closed_at DATETIME DEFAULT NULL COMMENT '关闭时间',
    closed_by INT DEFAULT NULL COMMENT '关闭者 user.id',
    window_start DATETIME NOT NULL COMMENT '时间窗口起始',
    window_end DATETIME NOT NULL COMMENT '时间窗口结束',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_group_id) REFERENCES strategy_group(id),
    INDEX idx_dim (dimension, dimension_value),
    INDEX idx_status (status, created_at DESC),
    INDEX idx_lifecycle (lifecycle, created_at DESC),
    INDEX idx_sg (strategy_group_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "trend_tracking": """
CREATE TABLE IF NOT EXISTS trend_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_event_id INT NOT NULL,
    track_date DATE NOT NULL COMMENT '跟踪日期',
    stock_count INT NOT NULL DEFAULT 0 COMMENT '触发股票数',
    new_stocks JSON DEFAULT NULL COMMENT '新增股票列表',
    lost_stocks JSON DEFAULT NULL COMMENT '消失股票列表',
    avg_rsi FLOAT DEFAULT NULL COMMENT 'RSI 均值',
    avg_macd_dif FLOAT DEFAULT NULL COMMENT 'MACD DIF 均值',
    avg_volume_ratio FLOAT DEFAULT NULL COMMENT '量比均值',
    avg_score FLOAT DEFAULT NULL COMMENT '综合评分均值',
    news_count INT NOT NULL DEFAULT 0 COMMENT '当日关联资讯数',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_event_id) REFERENCES group_event(id),
    INDEX idx_event_date (group_event_id, track_date),
    UNIQUE KEY uk_event_date (group_event_id, track_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}


def init_tables():
    """创建策略组引擎所需的表（IF NOT EXISTS）+ 迁移"""
    with Database() as db:
        for name, ddl in _TABLES.items():
            try:
                db.execute(ddl)
                db.commit()
                logger.info("表 %s 已就绪", name)
            except Exception as exc:
                logger.error("建表失败 %s: %s", name, exc)
                # 不再 raise，继续创建后续表

        # 迁移：strategy_subscription.user_id INT → VARCHAR(100)
        try:
            _, col = db.select_one(
                "SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'strategy_subscription' "
                "AND COLUMN_NAME = 'user_id'"
            )
            if col and col["DATA_TYPE"] in ("int", "int unsigned", "bigint"):
                db.execute(
                    "ALTER TABLE strategy_subscription "
                    "MODIFY COLUMN user_id VARCHAR(100) NOT NULL"
                )
                db.commit()
                logger.info("strategy_subscription.user_id 已迁移为 VARCHAR(100)")
        except Exception as exc:
            logger.warning("strategy_subscription.user_id 迁移检查跳过: %s", exc)


# ---------------------------------------------------------------------------
# Strategy Group — 辅助查询
# ---------------------------------------------------------------------------

def insert_strategy_group(
    name: str,
    indicators: list,
    signal_logic: str,
    conditions: list,
    aggregation: dict,
    scan_cron: Optional[str] = None,
    scoring_threshold: Optional[int] = None,
) -> int:
    """插入新策略组，返回 id"""
    with Database() as db:
        db.execute(
            """INSERT INTO strategy_group
               (name, indicators, signal_logic, conditions, scoring_threshold,
                aggregation, scan_cron)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                name,
                json.dumps(indicators, ensure_ascii=False),
                signal_logic,
                json.dumps(conditions, ensure_ascii=False),
                scoring_threshold,
                json.dumps(aggregation, ensure_ascii=False),
                scan_cron,
            ),
        )
        _, last_id = db.execute("SELECT LAST_INSERT_ID()")
        db.commit()
        # fetch the inserted row to get the id
        db.execute("SELECT id FROM strategy_group ORDER BY id DESC LIMIT 1")
        row = db.select_one("SELECT id FROM strategy_group ORDER BY id DESC LIMIT 1")
        return row[1]["id"] if row[1] else last_id


def update_strategy_group(group_id: int, **fields) -> bool:
    """更新策略组字段，返回是否成功"""
    allowed = {
        "name", "indicators", "signal_logic", "conditions",
        "scoring_threshold", "aggregation", "scan_cron", "status",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return False
    vals.append(group_id)
    with Database() as db:
        db.execute(
            f"UPDATE strategy_group SET {', '.join(sets)} WHERE id = %s",
            tuple(vals),
        )
        return True


def soft_delete_strategy_group(group_id: int) -> bool:
    """软删除 — 状态设为 archived"""
    with Database() as db:
        db.execute(
            "UPDATE strategy_group SET status = 'archived' WHERE id = %s",
            (group_id,),
        )
        return True


def update_strategy_group_status(group_id: int, status: str) -> bool:
    """切换策略组状态 (active / paused)"""
    with Database() as db:
        db.execute(
            "UPDATE strategy_group SET status = %s WHERE id = %s",
            (status, group_id),
        )
        return True


def get_strategy_group(group_id: int) -> Optional[dict]:
    """获取单个策略组"""
    with Database() as db:
        _, row = db.select_one(
            "SELECT * FROM strategy_group WHERE id = %s",
            (group_id,),
        )
        return _parse_group(row) if row else None


def list_strategy_groups(
    status: Optional[str] = None,
) -> List[dict]:
    """列出策略组，可选按状态筛选"""
    with Database() as db:
        if status:
            _, rows = db.select_many(
                "SELECT * FROM strategy_group WHERE status = %s ORDER BY created_at DESC",
                (status,),
            )
        else:
            _, rows = db.select_many(
                "SELECT * FROM strategy_group ORDER BY created_at DESC",
            )
        return [_parse_group(r) for r in rows]


def list_active_groups() -> List[dict]:
    """获取所有 active 状态的策略组"""
    return list_strategy_groups(status="active")


def _parse_group(row: dict) -> dict:
    """解析 JSON 字段"""
    if row is None:
        return None
    for key in ("indicators", "conditions", "aggregation"):
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


# ---------------------------------------------------------------------------
# Strategy Group Run — 辅助查询
# ---------------------------------------------------------------------------

def create_run(group_id: int, trigger_type: str = "manual") -> int:
    """创建扫描运行记录，返回 run_id"""
    with Database() as db:
        db.execute(
            """INSERT INTO strategy_group_run
               (strategy_group_id, trigger_type, status)
               VALUES (%s, %s, 'running')""",
            (group_id, trigger_type),
        )
        _, row = db.select_one("SELECT LAST_INSERT_ID() as id")
        return row["id"]


def update_run(run_id: int, **fields) -> bool:
    """更新运行记录"""
    allowed = {
        "total_stocks", "matched_stocks", "status",
        "error_message", "finished_at", "duration_seconds",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return False
    vals.append(run_id)
    with Database() as db:
        db.execute(
            f"UPDATE strategy_group_run SET {', '.join(sets)} WHERE id = %s",
            tuple(vals),
        )
        return True


def get_run(run_id: int) -> Optional[dict]:
    """获取运行记录"""
    with Database() as db:
        _, row = db.select_one(
            "SELECT * FROM strategy_group_run WHERE id = %s",
            (run_id,),
        )
        return row


def get_latest_run(group_id: int) -> Optional[dict]:
    """获取策略组最新一条运行记录"""
    with Database() as db:
        _, row = db.select_one(
            """SELECT * FROM strategy_group_run
               WHERE strategy_group_id = %s
               ORDER BY started_at DESC LIMIT 1""",
            (group_id,),
        )
        return row


def cleanup_stale_runs() -> int:
    """清理超过 30 分钟仍在 running 的记录，标记为 failed。
    返回清理数量。
    """
    try:
        with Database() as db:
            db.execute(
                """UPDATE strategy_group_run
                   SET status = 'failed',
                       error_message = 'stale run cleaned on startup'
                   WHERE status = 'running'
                     AND started_at < NOW() - INTERVAL 30 MINUTE"""
            )
            # 返回受影响行数 — db.execute 返回 (affected, last_id)
            result = db.select_one(
                "SELECT ROW_COUNT() as cnt"
            )
            cnt = result[1]["cnt"] if result[1] else 0
            if cnt:
                logger.info("清理 stale running 记录 %d 条", cnt)
            return cnt
    except Exception as exc:
        logger.warning("清理 stale running 记录失败: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Signal Snapshot — 辅助查询
# ---------------------------------------------------------------------------

def insert_signal_snapshots(snapshots: list) -> int:
    """批量插入信号快照"""
    if not snapshots:
        return 0
    with Database() as db:
        for s in snapshots:
            db.execute(
                """INSERT INTO signal_snapshot
                   (strategy_group_id, run_id, stock_code, stock_name,
                    indicator_snapshot, buy_star)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    s["strategy_group_id"],
                    s["run_id"],
                    s["stock_code"],
                    s.get("stock_name"),
                    json.dumps(s.get("indicator_snapshot", {}), ensure_ascii=False),
                    s.get("buy_star"),
                ),
            )
        return len(snapshots)


def query_signals(
    strategy_group_id: Optional[int] = None,
    stock_code: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """查询信号列表，返回 {items, total}"""
    conditions = []
    params = []
    if strategy_group_id is not None:
        conditions.append("strategy_group_id = %s")
        params.append(strategy_group_id)
    if stock_code:
        conditions.append("stock_code = %s")
        params.append(stock_code)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with Database() as db:
        _, row = db.select_one(
            f"SELECT COUNT(*) as total FROM signal_snapshot {where}",
            tuple(params),
        )
        total = row["total"] if row else 0

        _, rows = db.select_many(
            f"SELECT * FROM signal_snapshot {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [limit, offset]),
        )
        for r in rows:
            for key in ("indicator_snapshot",):
                val = r.get(key)
                if isinstance(val, str):
                    try:
                        r[key] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return {"items": rows, "total": total}


# ---------------------------------------------------------------------------
# Group Event — 辅助查询
# ---------------------------------------------------------------------------


def calc_sector_change_pct(matched_stocks: list, date_str: str):
    codes = []
    for s in (matched_stocks or []):
        if isinstance(s, dict):
            c = s.get("code", "")
        elif isinstance(s, str):
            c = s
        else:
            continue
        if c:
            codes.append(c)
    if not codes or not date_str:
        return None
    date = str(date_str)[:10]
    ph = ",".join(["%s"] * len(codes))
    with Database() as db:
        _, rows = db.select_many(
            "SELECT change_percentage FROM stock_data_daily "
            "WHERE stock_code IN (" + ph + ") AND date = %s "
            "AND change_percentage IS NOT NULL",
            (*codes, date),
        )
    if not rows:
        return None
    vals = [float(r["change_percentage"]) for r in rows]
    return round(sum(vals) / len(vals), 4)


def insert_group_event(event: dict) -> int:
    """插入群体事件，返回 id"""
    with Database() as db:
        db.execute(
            """INSERT INTO group_event
               (strategy_group_id, run_id, dimension, dimension_value,
                stock_count, avg_buy_star, max_buy_star, matched_stocks,
                status, window_start, window_end, sector_change_pct)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event["strategy_group_id"],
                event.get("run_id"),
                event["dimension"],
                event["dimension_value"],
                event["stock_count"],
                event.get("avg_buy_star"),
                event.get("max_buy_star"),
                json.dumps(event.get("matched_stocks", []), ensure_ascii=False),
                event.get("status", "open"),
                event["window_start"],
                event["window_end"],
                event.get("sector_change_pct"),
            ),
        )
        _, row = db.select_one("SELECT LAST_INSERT_ID() as id")
        return row["id"]


def update_group_event(event_id: int, **fields) -> bool:
    """更新群体事件"""
    allowed = {
        "stock_count", "avg_buy_star", "max_buy_star",
        "matched_stocks", "status", "run_id", "sector_change_pct",
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return False
    vals.append(event_id)
    with Database() as db:
        db.execute(
            f"UPDATE group_event SET {', '.join(sets)} WHERE id = %s",
            tuple(vals),
        )
        return True


def get_group_event(event_id: int) -> Optional[dict]:
    """获取单个群体事件"""
    with Database() as db:
        _, row = db.select_one(
            "SELECT * FROM group_event WHERE id = %s",
            (event_id,),
        )
        return _parse_event(row) if row else None


def query_group_events(
    strategy_group_id: Optional[int] = None,
    dimension_value: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """查询群体事件列表"""
    conditions = []
    params = []
    if strategy_group_id is not None:
        conditions.append("strategy_group_id = %s")
        params.append(strategy_group_id)
    if dimension_value:
        conditions.append("dimension_value = %s")
        params.append(dimension_value)
    if status:
        conditions.append("status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with Database() as db:
        _, row = db.select_one(
            f"SELECT COUNT(*) as total FROM group_event {where}",
            tuple(params),
        )
        total = row["total"] if row else 0

        _, rows = db.select_many(
            f"SELECT * FROM group_event {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [limit, offset]),
        )
        return {"items": [_parse_event(r) for r in rows], "total": total}


def find_open_event(
    strategy_group_id: int,
    dimension: str,
    dimension_value: str,
) -> Optional[dict]:
    """查找同策略组 + 同维度的 open 事件"""
    with Database() as db:
        _, row = db.select_one(
            """SELECT * FROM group_event
               WHERE strategy_group_id = %s
                 AND dimension = %s
                 AND dimension_value = %s
                 AND status = 'open'
               ORDER BY created_at DESC LIMIT 1""",
            (strategy_group_id, dimension, dimension_value),
        )
        return _parse_event(row) if row else None


def close_expired_events() -> int:
    """关闭所有超出时间窗口的 open 事件，返回关闭数量"""
    with Database() as db:
        # 获取所有 open 事件
        _, rows = db.select_many(
            "SELECT * FROM group_event WHERE status = 'open'"
        )
        closed = 0
        now_str = None
        import datetime
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        for evt in rows:
            window_end = evt.get("window_end")
            if window_end and str(window_end) < now_str:
                db.execute(
                    "UPDATE group_event SET status = 'closed' WHERE id = %s",
                    (evt["id"],),
                )
                closed += 1
        return closed


def _parse_event(row: dict) -> dict:
    """解析事件 JSON 字段"""
    if row is None:
        return None
    for key in ("matched_stocks", "llm_keywords", "llm_drivers",
                "llm_related_themes", "news_matched"):
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


# ---------------------------------------------------------------------------
# Strategy Subscription — CRUD
# ---------------------------------------------------------------------------

def insert_subscription(user_id, strategy_group_id: int) -> Optional[dict]:
    """订阅策略组。成功返回订阅记录，已存在返回 None。"""
    import pymysql
    with Database() as db:
        try:
            db.execute(
                """INSERT INTO strategy_subscription (user_id, strategy_group_id)
                   VALUES (%s, %s)""",
                (user_id, strategy_group_id),
            )
        except pymysql.IntegrityError:
            return None
        _, row = db.select_one(
            "SELECT * FROM strategy_subscription WHERE user_id = %s AND strategy_group_id = %s",
            (user_id, strategy_group_id),
        )
        return row


def delete_subscription(user_id, strategy_group_id: int) -> bool:
    """取消订阅，返回是否实际删除了记录"""
    with Database() as db:
        count, _ = db.execute(
            "DELETE FROM strategy_subscription WHERE user_id = %s AND strategy_group_id = %s",
            (user_id, strategy_group_id),
        )
        return count > 0


def get_subscription(user_id, strategy_group_id: int) -> Optional[dict]:
    """查询单个订阅记录"""
    with Database() as db:
        _, row = db.select_one(
            "SELECT * FROM strategy_subscription WHERE user_id = %s AND strategy_group_id = %s",
            (user_id, strategy_group_id),
        )
        return row


def list_user_subscriptions(user_id) -> List[dict]:
    """查询用户的所有订阅，附带策略组详情"""
    with Database() as db:
        _, rows = db.select_many(
            """SELECT s.*, sg.name, sg.indicators, sg.signal_logic, sg.conditions,
                      sg.aggregation, sg.scan_cron, sg.status as group_status
               FROM strategy_subscription s
               JOIN strategy_group sg ON s.strategy_group_id = sg.id
               WHERE s.user_id = %s
               ORDER BY s.subscribed_at DESC""",
            (user_id,),
        )
        for r in rows:
            for key in ("indicators", "conditions", "aggregation"):
                val = r.get(key)
                if isinstance(val, str):
                    try:
                        r[key] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return rows


def count_subscribers(strategy_group_id: int) -> int:
    """统计策略组的订阅人数"""
    with Database() as db:
        _, row = db.select_one(
            "SELECT COUNT(*) as cnt FROM strategy_subscription WHERE strategy_group_id = %s",
            (strategy_group_id,),
        )
        return row["cnt"] if row else 0


def list_strategy_groups_with_subscription(
    user_id,
    status: Optional[str] = None,
) -> List[dict]:
    """列出策略组并附带当前用户的订阅状态和订阅人数"""
    with Database() as db:
        if status:
            _, rows = db.select_many(
                "SELECT * FROM strategy_group WHERE status = %s ORDER BY created_at DESC",
                (status,),
            )
        else:
            _, rows = db.select_many(
                "SELECT * FROM strategy_group ORDER BY created_at DESC",
            )

        result = []
        for r in rows:
            g = _parse_group(r)
            gid = g["id"]
            # 订阅状态
            _, sub = db.select_one(
                "SELECT * FROM strategy_subscription WHERE user_id = %s AND strategy_group_id = %s",
                (user_id, gid),
            )
            g["subscribed"] = sub is not None
            g["subscribed_at"] = str(sub["subscribed_at"]) if sub else None
            # 订阅人数
            _, cnt_row = db.select_one(
                "SELECT COUNT(*) as cnt FROM strategy_subscription WHERE strategy_group_id = %s",
                (gid,),
            )
            g["subscriber_count"] = cnt_row["cnt"] if cnt_row else 0
            result.append(g)
        return result


# ---------------------------------------------------------------------------
# Event Detail — 微观/宏观/信息 数据查询
# ---------------------------------------------------------------------------

def get_event_micro_data(event_id: int) -> Optional[dict]:
    """获取事件微观数据：触发个股的指标快照 + buy 值"""
    event = get_group_event(event_id)
    if not event:
        return None

    strategy_group_id = event["strategy_group_id"]
    matched_stocks = event.get("matched_stocks", [])
    stock_codes = [s if isinstance(s, str) else s.get("code", "") for s in matched_stocks]

    if not stock_codes:
        return {"event_id": event_id, "stocks": []}

    with Database() as db:
        # 从 signal_snapshot 获取最近一批指标快照
        placeholders = ",".join(["%s"] * len(stock_codes))
        _, rows = db.select_many(
            f"""SELECT DISTINCT ss.stock_code, ss.stock_name, ss.indicator_snapshot,
                       ss.buy_star, ss.created_at
               FROM signal_snapshot ss
               WHERE ss.strategy_group_id = %s
                 AND ss.stock_code IN ({placeholders})
               ORDER BY ss.created_at DESC""",
            tuple([strategy_group_id] + stock_codes),
        )
        # 去重：每只股票只保留最新一条
        seen = set()
        stocks = []
        for r in rows:
            snap = r.get("indicator_snapshot")
            if isinstance(snap, str):
                try:
                    snap = json.loads(snap)
                except (json.JSONDecodeError, TypeError):
                    snap = {}
            if r["stock_code"] not in seen:
                seen.add(r["stock_code"])
                stocks.append({
                    "stock_code": r["stock_code"],
                    "stock_name": r.get("stock_name"),
                    "buy_star": r.get("buy_star"),
                    "indicator_snapshot": snap,
                    "created_at": str(r.get("created_at", "")),
                })

    return {"event_id": event_id, "stocks": stocks}


def get_event_macro_data(event_id: int) -> Optional[dict]:
    """获取事件宏观数据：行业趋势聚合 + 板块涨跌"""
    event = get_group_event(event_id)
    if not event:
        return None

    strategy_group_id = event["strategy_group_id"]
    dimension = event.get("dimension", "")
    dimension_value = event.get("dimension_value", "")

    result = {
        "event_id": event_id,
        "dimension": dimension,
        "dimension_value": dimension_value,
        "daily_stats": [],
        "sector_trend": [],
    }

    with Database() as db:
        # 1. 按日统计触发股票数和 avg_buy_star 变化
        try:
            _, daily_rows = db.select_many(
                """SELECT DATE(created_at) as stat_date,
                          COUNT(DISTINCT stock_code) as stock_count,
                          AVG(buy_star) as avg_buy_star
                   FROM signal_snapshot
                   WHERE strategy_group_id = %s
                   GROUP BY DATE(created_at)
                   ORDER BY stat_date DESC
                   LIMIT 30""",
                (strategy_group_id,),
            )
            result["daily_stats"] = [
                {
                    "date": str(r["stat_date"]),
                    "stock_count": r["stock_count"],
                    "avg_buy_star": round(float(r["avg_buy_star"]), 2) if r["avg_buy_star"] else None,
                }
                for r in daily_rows
            ]
        except Exception as exc:
            logger.warning("宏观数据-日统计查询失败: %s", exc)

        # 2. 板块走势（从 stock_data_daily 聚合同行业股票涨跌幅）
        try:
            _, trend_rows = db.select_many(
                """SELECT trade_date,
                          COUNT(*) as stock_count,
                          AVG(change_pct) as avg_change_pct
                   FROM stock_data_daily
                   WHERE stock_code IN (
                       SELECT stock_code FROM signal_snapshot
                       WHERE strategy_group_id = %s
                   )
                   GROUP BY trade_date
                   ORDER BY trade_date DESC
                   LIMIT 30""",
                (strategy_group_id,),
            )
            result["sector_trend"] = [
                {
                    "date": str(r["trade_date"]),
                    "stock_count": r["stock_count"],
                    "avg_change_pct": round(float(r["avg_change_pct"]), 4) if r["avg_change_pct"] else 0,
                }
                for r in trend_rows
            ]
        except Exception as exc:
            logger.warning("宏观数据-板块走势查询失败: %s", exc)

    return result


def get_event_info_data(event_id: int) -> Optional[dict]:
    """获取事件信息关联数据：matched_stocks 列表用于资讯查询"""
    event = get_group_event(event_id)
    if not event:
        return None

    matched_stocks = event.get("matched_stocks", [])
    stock_codes = [s if isinstance(s, str) else s.get("code", "") for s in matched_stocks]

    return {
        "event_id": event_id,
        "dimension": event.get("dimension", ""),
        "dimension_value": event.get("dimension_value", ""),
        "matched_stocks": stock_codes,
        "stock_count": event.get("stock_count", 0),
    }


# ---------------------------------------------------------------------------
# Trend Tracking — CRUD
# ---------------------------------------------------------------------------

def insert_trend_tracking(
    event_id: int,
    track_date: str,
    stock_count: int,
    new_stocks: list,
    lost_stocks: list,
    avg_rsi: Optional[float] = None,
    avg_macd_dif: Optional[float] = None,
    avg_volume_ratio: Optional[float] = None,
    avg_score: Optional[float] = None,
    news_count: int = 0,
) -> int:
    """插入趋势跟踪记录，返回 id"""
    with Database() as db:
        db.execute(
            """INSERT INTO trend_tracking
               (group_event_id, track_date, stock_count, new_stocks, lost_stocks,
                avg_rsi, avg_macd_dif, avg_volume_ratio, avg_score, news_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event_id,
                track_date,
                stock_count,
                json.dumps(new_stocks, ensure_ascii=False),
                json.dumps(lost_stocks, ensure_ascii=False),
                avg_rsi,
                avg_macd_dif,
                avg_volume_ratio,
                avg_score,
                news_count,
            ),
        )
        _, row = db.select_one("SELECT LAST_INSERT_ID() as id")
        return row["id"]


def get_latest_trend_tracking(event_id: int) -> Optional[dict]:
    """获取事件最近一条跟踪记录"""
    with Database() as db:
        _, row = db.select_one(
            """SELECT * FROM trend_tracking
               WHERE group_event_id = %s
               ORDER BY track_date DESC LIMIT 1""",
            (event_id,),
        )
        return _parse_trend(row) if row else None


def get_trend_tracking_history(event_id: int) -> List[dict]:
    """获取事件全部历史跟踪记录，按日期升序"""
    with Database() as db:
        _, rows = db.select_many(
            """SELECT * FROM trend_tracking
               WHERE group_event_id = %s
               ORDER BY track_date ASC""",
            (event_id,),
        )
        return [_parse_trend(r) for r in rows]


def _parse_trend(row: dict) -> dict:
    """解析跟踪记录 JSON 字段"""
    if row is None:
        return None
    for key in ("new_stocks", "lost_stocks"):
        val = row.get(key)
        if isinstance(val, str):
            try:
                row[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


# ---------------------------------------------------------------------------
# Lifecycle Management
# ---------------------------------------------------------------------------

def update_event_lifecycle(
    event_id: int,
    lifecycle: str,
    suggest_close_reason: Optional[str] = None,
    closed_by: Optional[int] = None,
) -> bool:
    """统一生命周期更新

    Parameters
    ----------
    lifecycle : str
        'tracking' / 'suggest_close' / 'closed'
    suggest_close_reason : str, optional
        衰减原因描述
    closed_by : int, optional
        关闭者 user.id
    """
    sets = ["lifecycle = %s"]
    vals = [lifecycle]

    if lifecycle == "suggest_close" and suggest_close_reason is not None:
        sets.append("suggest_close_reason = %s")
        vals.append(suggest_close_reason)

    if lifecycle == "closed":
        import datetime
        sets.append("closed_at = %s")
        vals.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if closed_by is not None:
            sets.append("closed_by = %s")
            vals.append(closed_by)
        # Also update status for backward compatibility
        sets.append("status = %s")
        vals.append("closed")

    vals.append(event_id)
    with Database() as db:
        db.execute(
            f"UPDATE group_event SET {', '.join(sets)} WHERE id = %s",
            tuple(vals),
        )
        return True


def update_event_llm_result(
    event_id: int,
    llm_keywords: Optional[list] = None,
    llm_summary: Optional[str] = None,
    llm_confidence: Optional[float] = None,
    llm_drivers: Optional[list] = None,
    llm_related_themes: Optional[list] = None,
    news_confirmed: Optional[bool] = None,
    news_confirm_score: Optional[float] = None,
    news_matched: Optional[list] = None,
) -> bool:
    """LLM 分析结果批量写入 group_event"""
    fields = {
        "llm_keywords": llm_keywords,
        "llm_summary": llm_summary,
        "llm_confidence": llm_confidence,
        "llm_drivers": llm_drivers,
        "llm_related_themes": llm_related_themes,
        "news_confirmed": news_confirmed,
        "news_confirm_score": news_confirm_score,
        "news_matched": news_matched,
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return False
    vals.append(event_id)
    with Database() as db:
        db.execute(
            f"UPDATE group_event SET {', '.join(sets)} WHERE id = %s",
            tuple(vals),
        )
        return True


def append_event_news_matched(event_id: int, new_items: list) -> bool:
    """追加资讯到 group_event.news_matched（JSON merge）"""
    event = get_group_event(event_id)
    if not event:
        return False
    existing = event.get("news_matched") or []
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            existing = []
    merged = existing + new_items
    with Database() as db:
        db.execute(
            "UPDATE group_event SET news_matched = %s WHERE id = %s",
            (json.dumps(merged, ensure_ascii=False), event_id),
        )
        return True


def list_tracking_events() -> List[dict]:
    """查询所有 lifecycle='tracking' 的群体事件"""
    with Database() as db:
        _, rows = db.select_many(
            """SELECT * FROM group_event
               WHERE lifecycle = 'tracking'
               ORDER BY created_at DESC"""
        )
        return [_parse_event(r) for r in rows]


def get_recent_trend_trackings(event_id: int, days: int = 2) -> List[dict]:
    """获取事件最近 N 个交易日的跟踪记录"""
    with Database() as db:
        _, rows = db.select_many(
            """SELECT * FROM trend_tracking
               WHERE group_event_id = %s
               ORDER BY track_date DESC
               LIMIT %s""",
            (event_id, days),
        )
        return [_parse_trend(r) for r in rows]
