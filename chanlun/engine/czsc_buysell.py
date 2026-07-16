# -*- coding: utf-8 -*-
"""三类买卖点(czsc路线): 基于笔+中枢+走势+背驰。"""
from typing import List, Dict
from ..czsc_core import BI, ZS, Direction
from .trend import classify_trends, TrendType, last_trend
from .czsc_divergence import last_divergence

def detect_buy1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一买: 下跌趋势末端底背驰"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Down or div['kind'] != 'trend':
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Down:
        return signals
    signals.append({'type': 'buy1', 'price': last_bi.low, 'dt': str(last_bi.edt),
                    'stop_loss': round(max(last_bi.low * 0.95, last_bi.low * 0.90), 2),
                    'reason': 'trend_bottom_divergence', 'ratio': div['ratio']})
    return signals

def detect_buy2(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """二买: 一买后第一次回调不破前低"""
    signals = []
    if len(bis) < 5:
        return signals
    b1, b2, b3 = bis[-3], bis[-2], bis[-1]
    if b1.direction != Direction.Down or b2.direction != Direction.Up or b3.direction != Direction.Down:
        return signals
    if b3.low > b1.low and b2.high > b1.high:
        lt = last_trend(zs_list)
        if lt['type'] != TrendType.DOWN:
            signals.append({'type': 'buy2', 'price': b3.low, 'dt': str(b3.edt),
                            'stop_loss': round(max(b1.low * 0.97, b3.low * 0.90), 2),
                            'reason': 'pullback_not_break_low'})
    return signals

def detect_buy3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三买: 离开中枢后回踩不破ZG"""
    signals = []
    if not zs_list:
        return signals
    last_zs = zs_list[-1]
    after_bis = [b for b in bis if b.sdt >= last_zs.edt]
    if len(after_bis) < 3:
        return signals
    up_bi = after_bis[0]
    if up_bi.direction != Direction.Up or up_bi.high <= last_zs.zg:
        return signals
    pullback = after_bis[1]
    if pullback.direction != Direction.Down:
        return signals
    if pullback.low > last_zs.zg:
        price = closes[-1] if closes else pullback.low
        signals.append({'type': 'buy3', 'price': price, 'dt': str(pullback.edt),
                        'stop_loss': round(max(last_zs.zg * 0.97, price * 0.90), 2),
                        'zg': last_zs.zg, 'zd': last_zs.zd,
                        'reason': 'breakout_pullback_above_zg'})
    return signals

def detect_sell1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一卖: 上涨趋势末端顶背驰"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Up or div['kind'] != 'trend':
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Up:
        return signals
    signals.append({'type': 'sell1', 'price': last_bi.high, 'dt': str(last_bi.edt),
                    'stop_loss': round(last_bi.high * 1.05, 2),
                    'reason': 'trend_top_divergence', 'ratio': div['ratio']})
    return signals

def detect_sell2(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """二卖: 一卖后第一次反弹不破前高"""
    signals = []
    if len(bis) < 5:
        return signals
    b1, b2, b3 = bis[-3], bis[-2], bis[-1]
    if b1.direction != Direction.Up or b2.direction != Direction.Down or b3.direction != Direction.Up:
        return signals
    if b3.high < b1.high and b2.low < b1.low:
        lt = last_trend(zs_list)
        if lt['type'] != TrendType.UP:
            signals.append({'type': 'sell2', 'price': b3.high, 'dt': str(b3.edt),
                            'stop_loss': round(b1.high * 1.03, 2),
                            'reason': 'rebound_not_break_high'})
    return signals

def detect_sell3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三卖: 跌破中枢ZD后回抽不过ZD"""
    signals = []
    if not zs_list:
        return signals
    last_zs = zs_list[-1]
    after_bis = [b for b in bis if b.sdt >= last_zs.edt]
    if len(after_bis) < 3:
        return signals
    down_bi = after_bis[0]
    if down_bi.direction != Direction.Down or down_bi.low >= last_zs.zd:
        return signals
    rebound = after_bis[1]
    if rebound.direction != Direction.Up:
        return signals
    if rebound.high < last_zs.zd:
        price = closes[-1] if closes else rebound.high
        signals.append({'type': 'sell3', 'price': price, 'dt': str(rebound.edt),
                        'stop_loss': round(last_zs.zd * 1.03, 2),
                        'zg': last_zs.zg, 'zd': last_zs.zd,
                        'rebound_high': rebound.high,
                        'reason': 'breakdown_rebound_below_zd'})
    return signals

def detect_all_buys(bis, zs_list, closes):
    return detect_buy1(bis, zs_list, closes) + detect_buy2(bis, zs_list, closes) + detect_buy3(bis, zs_list, closes)

def detect_all_sells(bis, zs_list, closes):
    return detect_sell1(bis, zs_list, closes) + detect_sell2(bis, zs_list, closes) + detect_sell3(bis, zs_list, closes)
