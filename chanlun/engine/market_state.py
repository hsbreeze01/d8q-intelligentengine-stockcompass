# -*- coding: utf-8 -*-
"""大盘状态判断(v2): 三档判定 — 看多/中性/看空。

逻辑:
- 上涨趋势 + 在ZG上方 → 看多（强势）
- 上涨趋势 + 中枢内（ZD~ZG之间）→ 中性偏多（回踩中枢，正常）
- 上涨趋势 + 跌破ZD → 看空（趋势可能结束）
- 盘整 + 在ZG上方 → 中性偏多
- 盘整 + 中枢内 → 中性
- 盘整 + 跌破ZD → 中性偏空
- 下跌趋势 + 在ZD下方 → 看空（强空）
- 下跌趋势 + 中枢内 → 中性偏空
- 下跌趋势 + 突破ZG → 中性偏多（可能反转）
"""
import pymysql
from .czsc_adapter import build_czsc, valid_pivots
from .trend import last_trend, TrendType

DB_CONFIG = {'host': '127.0.0.1', 'port': 3306, 'user': 'root',
             'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'}

# 大盘态度枚举
BULLISH = 'bullish'          # 看多，适合做多
NEUTRAL_BULL = 'neutral_bull'  # 中性偏多，谨慎做多
NEUTRAL = 'neutral'          # 中性，观望为主
NEUTRAL_BEAR = 'neutral_bear'  # 中性偏空，轻仓或观望
BEARISH = 'bearish'          # 看空，不做多

# 态度对应的中文和建议
ATTITUDE_MAP = {
    BULLISH: {'label': '看多', 'suggestion': '适合做多，标准仓位', 'score': 25},
    NEUTRAL_BULL: {'label': '中性偏多', 'suggestion': '可做多，控制仓位', 'score': 18},
    NEUTRAL: {'label': '中性', 'suggestion': '观望为主，精选标的', 'score': 12},
    NEUTRAL_BEAR: {'label': '中性偏空', 'suggestion': '轻仓或观望', 'score': 6},
    BEARISH: {'label': '看空', 'suggestion': '不做多，等待企稳', 'score': 0},
}


def get_market_state(index_code='000001', limit=250) -> dict:
    """返回大盘状态 {attitude, bullish, trend_type, position, last_close, zg, zd, ...}"""
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        cur = conn.cursor()
        cur.execute('SELECT date dt,open,high,low,close,volume FROM index_daily WHERE stock_code=%s ORDER BY date DESC LIMIT %s', (index_code, limit))
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return {'attitude': NEUTRAL, 'bullish': False, 'trend_type': 'unknown',
                'above_zg': False, 'below_zd': False}
    rows.reverse()
    kl = [{'dt': str(r['dt']), 'open': float(r['open']), 'high': float(r['high']),
           'low': float(r['low']), 'close': float(r['close']), 'volume': float(r.get('volume', 0))} for r in rows]
    c = build_czsc(index_code, kl)
    zs = valid_pivots(c.bi_list)
    lt = last_trend(zs)
    last_close = kl[-1]['close']

    # 位置判定
    zg = zs[-1].zg if zs else None
    zd = zs[-1].zd if zs else None
    above_zg = last_close > zg if zg else False
    below_zd = last_close < zd if zd else False
    in_pivot = not above_zg and not below_zd

    # 三档态度判定
    trend = lt['type']
    if trend == TrendType.UP:
        if above_zg:
            attitude = BULLISH
        elif in_pivot:
            attitude = NEUTRAL_BULL  # 关键修复：上涨趋势回踩中枢 = 中性偏多
        else:
            attitude = BEARISH  # 跌破ZD，趋势可能结束
    elif trend == TrendType.DOWN:
        if below_zd:
            attitude = BEARISH
        elif in_pivot:
            attitude = NEUTRAL_BEAR
        else:
            attitude = NEUTRAL_BULL  # 下跌趋势但突破ZG，可能反转
    else:  # CONSOLIDATION
        if above_zg:
            attitude = NEUTRAL_BULL
        elif below_zd:
            attitude = NEUTRAL_BEAR
        else:
            attitude = NEUTRAL

    info = ATTITUDE_MAP[attitude]
    # 兼容旧接口: bullish 仍保留，但语义调整为允许做多
    allow_long = attitude in (BULLISH, NEUTRAL_BULL)

    return {
        'attitude': attitude,
        'bullish': allow_long,
        'trend_type': trend.value,
        'above_zg': above_zg,
        'below_zd': below_zd,
        'in_pivot': in_pivot,
        'last_close': last_close,
        'zg': round(zg, 2) if zg else None,
        'zd': round(zd, 2) if zd else None,
        'label': info['label'],
        'suggestion': info['suggestion'],
        'env_score': info['score'],
    }
