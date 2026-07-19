# -*- coding: utf-8 -*-
"""
概念生命周期追踪
计算热度趋势(1d/3d/7d变化率)和异动检测
异动类型: emerging(新兴)/warming(升温)/exploding(爆发)/sustained(持续)/cooling(退潮)
"""
import pymysql
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from storage import DB_CONFIG, get_connection


def compute_heat_trends(trend_date: Optional[date] = None) -> Dict[str, any]:
    """
    计算热度趋势并写入t_heat_trend表
    基于t_hot_event中的数据做聚合分析
    """
    if trend_date is None:
        trend_date = date.today()

    stats = {'inserted': 0, 'topics_analyzed': 0}

    with get_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 获取今日各topic的热度聚合(按source+title分组)
            cursor.execute("""
                SELECT source, title AS topic,
                       SUM(hot_score) AS heat_score,
                       COUNT(*) AS mention_count
                FROM t_hot_event
                WHERE event_date = %s AND is_finance_related = 1
                GROUP BY source, title
                HAVING heat_score > 0 OR mention_count > 1
            """, (trend_date,))
            today_topics = cursor.fetchall()

            if not today_topics:
                print(f"[lifecycle] {trend_date} 无金融相关热点数据")
                return stats

            stats['topics_analyzed'] = len(today_topics)

            for topic_row in today_topics:
                source = topic_row['source']
                topic = topic_row['topic']
                heat_score = float(topic_row['heat_score'])

                # 计算历史热度
                heat_1d = _get_heat_change(cursor, source, topic, trend_date, 1, heat_score)
                heat_3d = _get_heat_change(cursor, source, topic, trend_date, 3, heat_score)
                heat_7d = _get_heat_change(cursor, source, topic, trend_date, 7, heat_score)
                heat_ma5 = _get_heat_ma(cursor, source, topic, trend_date, 5)

                # 异动检测
                is_anomaly, anomaly_type = _detect_anomaly(
                    cursor, source, topic, trend_date,
                    heat_score, heat_1d, heat_ma5
                )

                # 获取相关概念
                related = _get_related_concepts(cursor, topic, trend_date)

                # 写入t_heat_trend
                cursor.execute("""
                    INSERT INTO t_heat_trend
                        (trend_date, topic, source, heat_score, heat_1d_change, heat_3d_change,
                         heat_7d_change, heat_ma5, is_anomaly, anomaly_type, related_concepts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        heat_score = VALUES(heat_score),
                        heat_1d_change = VALUES(heat_1d_change),
                        heat_3d_change = VALUES(heat_3d_change),
                        heat_7d_change = VALUES(heat_7d_change),
                        heat_ma5 = VALUES(heat_ma5),
                        is_anomaly = VALUES(is_anomaly),
                        anomaly_type = VALUES(anomaly_type),
                        related_concepts = VALUES(related_concepts)
                """, (
                    trend_date,
                    topic[:200],
                    source[:20],
                    heat_score,
                    heat_1d,
                    heat_3d,
                    heat_7d,
                    heat_ma5,
                    1 if is_anomaly else 0,
                    anomaly_type[:20] if anomaly_type else None,
                    related[:500] if related else None,
                ))
                stats['inserted'] += 1

    return stats


def _get_heat_change(cursor, source: str, topic: str, ref_date: date,
                     days_back: int, current_score: float) -> Optional[float]:
    """计算N日变化率 (%)"""
    past_date = ref_date - timedelta(days=days_back)
    cursor.execute("""
        SELECT SUM(hot_score) AS heat
        FROM t_hot_event
        WHERE source = %s AND title = %s AND event_date = %s
    """, (source, topic, past_date))
    row = cursor.fetchone()
    past_heat = float(row['heat']) if row and row['heat'] else 0

    if past_heat == 0:
        return 100.0 if current_score > 0 else 0.0
    return round((current_score - past_heat) / past_heat * 100, 2)


def _get_heat_ma(cursor, source: str, topic: str, ref_date: date, window: int) -> Optional[float]:
    """计算MA均值"""
    start_date = ref_date - timedelta(days=window - 1)
    cursor.execute("""
        SELECT AVG(daily_heat) AS ma FROM (
            SELECT event_date, SUM(hot_score) AS daily_heat
            FROM t_hot_event
            WHERE source = %s AND title = %s AND event_date BETWEEN %s AND %s
            GROUP BY event_date
        ) sub
    """, (source, topic, start_date, ref_date))
    row = cursor.fetchone()
    return round(float(row['ma']), 2) if row and row['ma'] else None


def _detect_anomaly(cursor, source: str, topic: str, ref_date: date,
                    heat_score: float, heat_1d: Optional[float],
                    heat_ma5: Optional[float]) -> Tuple[bool, Optional[str]]:
    """
    异动检测
    - emerging: 首次出现(过去7天无记录)
    - warming: 连续3日上升
    - exploding: 今日热度 > 3倍MA5
    - sustained: 连续>5天在MA5上方
    - cooling: 连续3日下降
    """
    # 检查是否首次出现
    past_start = ref_date - timedelta(days=7)
    cursor.execute("""
        SELECT COUNT(DISTINCT event_date) AS days
        FROM t_hot_event
        WHERE source = %s AND title = %s AND event_date >= %s AND event_date < %s
    """, (source, topic, past_start, ref_date))
    row = cursor.fetchone()
    past_days = row['days'] if row else 0

    if past_days == 0:
        return True, 'emerging'

    # 爆发检测: > 3倍MA5
    if heat_ma5 and heat_ma5 > 0 and heat_score > 3 * heat_ma5:
        return True, 'exploding'

    # 获取近5天每日热度
    daily_heats = _get_daily_heats(cursor, source, topic, ref_date, 5)

    # 连续3日上升(升温)
    if len(daily_heats) >= 3:
        recent_3 = daily_heats[-3:]
        if all(recent_3[i] < recent_3[i + 1] for i in range(len(recent_3) - 1)):
            return True, 'warming'

    # 连续3日下降(退潮)
    if len(daily_heats) >= 3:
        recent_3 = daily_heats[-3:]
        if all(recent_3[i] > recent_3[i + 1] for i in range(len(recent_3) - 1)):
            return True, 'cooling'

    # 持续: >5天在MA5上方
    if heat_ma5 and len(daily_heats) >= 5:
        above_count = sum(1 for h in daily_heats if h > heat_ma5)
        if above_count >= 5:
            return True, 'sustained'

    return False, None


def _get_daily_heats(cursor, source: str, topic: str, ref_date: date,
                     days: int) -> List[float]:
    """获取近N天每日热度列表"""
    start_date = ref_date - timedelta(days=days - 1)
    cursor.execute("""
        SELECT event_date, SUM(hot_score) AS daily_heat
        FROM t_hot_event
        WHERE source = %s AND title = %s AND event_date BETWEEN %s AND %s
        GROUP BY event_date
        ORDER BY event_date ASC
    """, (source, topic, start_date, ref_date))
    return [float(r['daily_heat']) for r in cursor.fetchall()]


def _get_related_concepts(cursor, topic: str, ref_date: date) -> Optional[str]:
    """获取同日相关概念(同标题出现在概念板块中的)"""
    cursor.execute("""
        SELECT title, MAX(hot_score) AS max_score FROM t_hot_event
        WHERE event_date = %s AND source = 'eastmoney_concept'
          AND title != %s
          AND is_finance_related = 1
        GROUP BY title ORDER BY max_score DESC
        LIMIT 5
    """, (ref_date, topic))
    rows = cursor.fetchall()
    if rows:
        return ','.join(r['title'] for r in rows)
    return None


if __name__ == '__main__':
    print("[lifecycle] 开始计算今日热度趋势...")
    stats = compute_heat_trends()
    print(f"[lifecycle] 完成: 分析 {stats['topics_analyzed']} 个话题, 写入 {stats['inserted']} 条趋势记录")
