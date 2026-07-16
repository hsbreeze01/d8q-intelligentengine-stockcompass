# -*- coding: utf-8 -*-
"""大盘状态判断: 对上证指数跑czsc引擎，输出趋势/中枢位置，替换环境分硬编码。"""
import pymysql
from .czsc_adapter import build_czsc, valid_pivots
from .trend import last_trend, TrendType

DB_CONFIG = {'host': '127.0.0.1', 'port': 3306, 'user': 'root',
             'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'}

def get_market_state(index_code='000001', limit=250) -> dict:
    """返回大盘状态 {bullish, trend_type, above_zg, last_close, zg, zd}"""
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        cur = conn.cursor()
        cur.execute('SELECT date dt,open,high,low,close,volume FROM index_daily WHERE stock_code=%s ORDER BY date DESC LIMIT %s', (index_code, limit))
        rows = cur.fetchall()
        if not rows:
            cur.execute('SELECT date dt,open,high,low,close,volume FROM index_daily WHERE stock_code=%s ORDER BY date DESC LIMIT %s', (index_code, limit))
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return {'bullish': False, 'trend_type': 'unknown', 'above_zg': False}
    rows.reverse()
    kl = [{'dt': str(r['dt']), 'open': float(r['open']), 'high': float(r['high']),
           'low': float(r['low']), 'close': float(r['close']), 'volume': float(r.get('volume', 0))} for r in rows]
    c = build_czsc(index_code, kl)
    zs = valid_pivots(c.bi_list)
    lt = last_trend(zs)
    last_close = kl[-1]['close']
    above_zg = last_close > zs[-1].zg if zs else False
    bullish = lt['type'] != TrendType.DOWN and above_zg
    return {
        'bullish': bullish,
        'trend_type': lt['type'].value,
        'above_zg': above_zg,
        'last_close': last_close,
        'zg': round(zs[-1].zg, 2) if zs else None,
        'zd': round(zs[-1].zd, 2) if zs else None,
    }
