# -*- coding: utf-8 -*-
"""
数据写入MySQL
表: t_hot_event, t_concept_board_daily, t_collect_log
"""
import json
import pymysql
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from contextlib import contextmanager


DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'password',
    'database': 'stock_analysis_system',
    'charset': 'utf8mb4',
    'autocommit': False,
}


@contextmanager
def get_connection():
    """获取数据库连接"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_hot_events(items: List[Dict[str, Any]]) -> int:
    """
    写入t_hot_event表
    返回实际插入行数
    """
    if not items:
        return 0

    sql = """
    INSERT INTO t_hot_event
        (event_date, event_time, source, title, hot_score, rank_pos, url, category, is_finance_related, tags, extra)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        hot_score = VALUES(hot_score),
        extra = VALUES(extra)
    """

    now = datetime.now()
    today = now.date()
    rows = []

    for item in items:
        extra = item.get('extra', {})
        rank_pos = extra.get('rank', None)
        rows.append((
            today,
            now,
            item.get('source', '')[:20],
            item.get('title', '')[:500],
            int(item.get('hot_score', 0)),
            rank_pos,
            item.get('url', '')[:500],
            item.get('category', 'general')[:50],
            1 if item.get('is_finance_related') else 0,
            item.get('tags', '')[:200],
            json.dumps(extra, ensure_ascii=False)[:2000] if extra else None,
        ))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)
            affected = cursor.rowcount
    return affected


def save_concept_boards(items: List[Dict[str, Any]]) -> int:
    """
    写入t_concept_board_daily表
    仅处理source为eastmoney_concept的数据
    """
    concept_items = [i for i in items if i.get('source') == 'eastmoney_concept']
    if not concept_items:
        return 0

    sql = """
    INSERT INTO t_concept_board_daily
        (trade_date, board_code, board_name, change_pct, net_inflow, turnover, up_count, down_count, lead_stock, rank_by_change, rank_by_flow)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        change_pct = VALUES(change_pct),
        net_inflow = VALUES(net_inflow),
        up_count = VALUES(up_count),
        down_count = VALUES(down_count)
    """

    today = date.today()
    rows = []

    # 按涨幅排名
    sorted_by_change = sorted(concept_items, key=lambda x: x.get('extra', {}).get('change_pct', 0), reverse=True)
    # 按净流入排名
    sorted_by_flow = sorted(concept_items, key=lambda x: x.get('extra', {}).get('net_inflow', 0), reverse=True)
    flow_rank_map = {item.get('extra', {}).get('board_code', ''): idx + 1 for idx, item in enumerate(sorted_by_flow)}

    for idx, item in enumerate(sorted_by_change, 1):
        extra = item.get('extra', {})
        board_code = extra.get('board_code', '')
        rows.append((
            today,
            board_code[:20],
            item.get('title', '')[:50],
            extra.get('change_pct'),
            extra.get('net_inflow'),
            None,  # turnover - 当前API不提供
            extra.get('up_count'),
            extra.get('down_count'),
            None,  # lead_stock - 需要单独接口
            idx,
            flow_rank_map.get(board_code, None),
        ))

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)
            affected = cursor.rowcount
    return affected


def save_collect_log(source: str, status: str, items_count: int,
                     error_msg: Optional[str] = None,
                     duration_ms: Optional[int] = None) -> None:
    """写入t_collect_log表"""
    sql = """
    INSERT INTO t_collect_log (collect_time, source, status, items_count, error_msg, duration_ms)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (
                datetime.now(),
                source[:20],
                status[:10],
                items_count,
                (error_msg[:500] if error_msg else None),
                duration_ms,
            ))


if __name__ == '__main__':
    # 测试连接
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM t_hot_event")
            count = cursor.fetchone()[0]
            print(f"t_hot_event 现有 {count} 条记录")
            cursor.execute("SELECT COUNT(*) FROM t_concept_board_daily")
            count = cursor.fetchone()[0]
            print(f"t_concept_board_daily 现有 {count} 条记录")
            cursor.execute("SELECT COUNT(*) FROM t_collect_log")
            count = cursor.fetchone()[0]
            print(f"t_collect_log 现有 {count} 条记录")
