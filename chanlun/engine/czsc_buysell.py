# -*- coding: utf-8 -*-
"""三类买卖点(czsc路线): 基于笔+中枢+走势+背驰。"""
from typing import List, Dict
from ..czsc_core import BI, ZS, Direction
from .trend import classify_trends, TrendType, last_trend
from .czsc_divergence import last_divergence

def detect_buy1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一买: 下跌背驰(趋势一买 + 盘整一买)"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Down:
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Down:
        return signals
    if div['kind'] == 'trend':
        reason = 'trend_bottom_divergence'
    elif div['kind'] == 'consolidation':
        # 盘整一买: 要求中枢内笔数>=5(盘整够充分)
        if not zs_list or len(zs_list[-1].bis) < 5:
            return signals
        reason = 'consolidation_bottom_divergence'
    else:
        return signals
    signals.append({'type': 'buy1', 'price': last_bi.low, 'dt': str(last_bi.edt),
                    'stop_loss': round(last_bi.low * 0.95, 2),
                    'reason': reason, 'ratio': div['ratio']})
    return signals

def detect_buy2(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """二买: 一买后第一次回调不破前低（加严版）
    增加条件:
    1. 回调幅度不超过上涨段的50%（防止深度回调伪二买）
    2. 回调低点必须在最近中枢ZG附近或上方（中枢关联）
    """
    signals = []
    if len(bis) < 5:
        return signals
    b1, b2, b3 = bis[-3], bis[-2], bis[-1]
    if b1.direction != Direction.Down or b2.direction != Direction.Up or b3.direction != Direction.Down:
        return signals
    if b3.low > b1.low and b2.high > b1.high:
        lt = last_trend(zs_list)
        if lt['type'] == TrendType.DOWN:
            return signals
        # P0-2a: 回调幅度限制 - 回调不超过上涨段(b2)的30%
        up_range = b2.high - b1.low
        pullback = b2.high - b3.low
        if up_range > 0 and pullback / up_range > 0.50:
            return signals
        # P0-2b: 中枢关联校验 - 回调低点不应远离最近中枢ZG（信号价不超ZG的50%以上）
        if zs_list:
            last_zg = zs_list[-1].zg
            if b3.low > last_zg * 1.5:
                return signals
        signals.append({'type': 'buy2', 'price': b3.low, 'dt': str(b3.edt),
                        'stop_loss': round(b3.low * 0.95, 2),
                        'reason': 'pullback_not_break_low'})
    return signals

def detect_buy3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三买: 离开线段中枢后回踩不破ZG（日线级别）

    宁可不出信号，也不出低质量三买。
    必须有线段中枢才产生三买，否则返回空。
    """
    from .segment_adapter import bis_to_segments, segment_pivots
    signals = []
    # 必须有线段中枢
    segs = bis_to_segments(bis)
    seg_zs = segment_pivots(segs)
    if not seg_zs:
        return signals
    last_seg = seg_zs[-1]
    seg_zg = last_seg['zg']
    seg_zd = last_seg['zd']
    # 寻找突破线段ZG后回踩不破的模式
    if len(bis) < 3:
        return signals
    for i in range(len(bis)-2, max(len(bis)-6, 0), -1):
        up_bi = bis[i]
        if up_bi.direction != Direction.Up or up_bi.high <= seg_zg:
            continue
        if i+1 < len(bis) and bis[i+1].direction == Direction.Down:
            pullback = bis[i+1]
            if pullback.low > seg_zg:
                price = closes[-1] if closes else pullback.low
                signals.append({'type': 'buy3', 'price': price, 'dt': str(pullback.edt),
                                'stop_loss': round(seg_zg * 0.97, 2),
                                'zg': seg_zg, 'zd': seg_zd,
                                'reason': 'segment_breakout_pullback_above_zg'})
                break
    return signals

def detect_sell1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一卖: 上涨背驰(趋势一卖 + 盘整一卖)"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Up:
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Up:
        return signals
    if div['kind'] == 'trend':
        reason = 'trend_top_divergence'
    elif div['kind'] == 'consolidation':
        if not zs_list or len(zs_list[-1].bis) < 5:
            return signals
        reason = 'consolidation_top_divergence'
    else:
        return signals
    signals.append({'type': 'sell1', 'price': last_bi.high, 'dt': str(last_bi.edt),
                    'stop_loss': round(last_bi.high * 1.05, 2),
                    'reason': reason, 'ratio': div['ratio']})
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
                            'stop_loss': round(b3.high * 1.05, 2),
                            'reason': 'rebound_not_break_high'})
    return signals

def detect_sell3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三卖: 跌破中枢ZD后回抽不过ZD"""
    signals = []
    if not zs_list:
        return signals
    last_zs = zs_list[-1]
    after_bis = [b for b in bis if b.sdt >= last_zs.edt]
    if len(after_bis) < 2:
        return signals
    down_bi = after_bis[0]
    if down_bi.direction != Direction.Down or down_bi.low >= last_zs.zd:
        return signals
    rebound = after_bis[1] if len(after_bis) >= 2 else None
    if rebound is None or rebound.direction != Direction.Up:
        return signals
    if rebound.high < last_zs.zd:
        price = closes[-1] if closes else rebound.high
        signals.append({'type': 'sell3', 'price': price, 'dt': str(rebound.edt),
                        'stop_loss': round(price * 1.05, 2),
                        'zg': last_zs.zg, 'zd': last_zs.zd,
                        'rebound_high': rebound.high,
                        'reason': 'breakdown_rebound_below_zd'})
    return signals

def detect_all_buys(bis, zs_list, closes):
    return detect_buy1(bis, zs_list, closes) + detect_buy2(bis, zs_list, closes) + detect_buy3(bis, zs_list, closes)

def detect_all_sells(bis, zs_list, closes):
    return detect_sell1(bis, zs_list, closes) + detect_sell2(bis, zs_list, closes) + detect_sell3(bis, zs_list, closes)
