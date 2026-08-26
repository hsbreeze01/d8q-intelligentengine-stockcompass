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


# B3-8: 周线数据最少周数。不足时无法可靠判定大级别方向。
MIN_WEEKLY_BARS = 20


def multi_level_ok(symbol: str, daily_klines: List[Dict]) -> Dict:
    """多级别方向过滤(方向化)。

    B3-8 修正两点:
    1. 数据不足时旧实现返回 allow=True(fail-open), 等于静默放行;
       改为 fail-closed(allow=False), 由调用方决定是否放宽。
    2. 旧实现只有一个 allow(仅过滤周线下跌趋势), 对卖出信号无意义。
       改为同时返回 allow_buy / allow_sell:
         买入: 周线为下跌趋势时不允许
         卖出: 周线为上涨趋势时不允许
    返回 {allow, allow_buy, allow_sell, weekly_trend, weekly_bi_count, sufficient}
    """
    weekly = resample_weekly(daily_klines)
    if len(weekly) < MIN_WEEKLY_BARS:
        return {'allow': False, 'allow_buy': False, 'allow_sell': False,
                'weekly_trend': 'insufficient', 'weekly_bi_count': 0, 'sufficient': False}
    c = build_czsc(symbol + '_W', weekly)
    zs = valid_pivots(c.bi_list)
    lt = last_trend(zs)
    allow_buy = lt['type'] != TrendType.DOWN
    allow_sell = lt['type'] != TrendType.UP
    return {'allow': allow_buy,            # 兼容旧字段(买入语义)
            'allow_buy': allow_buy,
            'allow_sell': allow_sell,
            'weekly_trend': lt['type'].value,
            'weekly_bi_count': len(c.bi_list),
            'sufficient': True}
