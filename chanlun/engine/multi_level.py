# -*- coding: utf-8 -*-
"""多级别联立(简化版): 日线重采样为周线作大级别方向过滤。
数据库仅有日线, 无法做真正的日线+30min区间套; 用重采样周线近似大级别。
"""
from typing import List, Dict
from .czsc_adapter import build_czsc, valid_pivots
from .trend import last_trend, TrendType


def resample_weekly(daily_klines: List[Dict]) -> List[Dict]:
    """日线重采样为周线(周一开盘~周五收盘, 取极值)"""
    from datetime import datetime
    weeks = []
    cur_week = None
    for k in daily_klines:
        dt = k['dt'] if isinstance(k['dt'], str) else str(k['dt'])
        d = datetime.strptime(dt[:10], '%Y-%m-%d')
        iso_week = d.isocalendar()[1]
        iso_year = d.isocalendar()[0]
        key = (iso_year, iso_week)
        if cur_week is None or cur_week['key'] != key:
            if cur_week:
                weeks.append(cur_week)
            cur_week = {'key': key, 'dt': dt, 'open': k['open'], 'high': k['high'],
                        'low': k['low'], 'close': k['close'], 'volume': k.get('volume', 0)}
        else:
            cur_week['high'] = max(cur_week['high'], k['high'])
            cur_week['low'] = min(cur_week['low'], k['low'])
            cur_week['close'] = k['close']
            cur_week['volume'] += k.get('volume', 0)
    if cur_week:
        weeks.append(cur_week)
    for w in weeks:
        del w['key']
    return weeks


def multi_level_ok(symbol: str, daily_klines: List[Dict]) -> Dict:
    """多级别方向过滤: 周线非下跌趋势时允许买入信号。
    返回 {allow: bool, weekly_trend: str, weekly_bi_count: int}
    """
    weekly = resample_weekly(daily_klines)
    if len(weekly) < 20:
        return {'allow': True, 'weekly_trend': 'insufficient', 'weekly_bi_count': 0}
    c = build_czsc(symbol + '_W', weekly)
    zs = valid_pivots(c.bi_list)
    lt = last_trend(zs)
    allow = lt['type'] != TrendType.DOWN
    return {'allow': allow, 'weekly_trend': lt['type'].value, 'weekly_bi_count': len(c.bi_list)}
