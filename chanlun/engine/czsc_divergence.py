# -*- coding: utf-8 -*-
"""背驰判定(czsc路线): 趋势前提+同级别推动段+创新极值+MACD面积比+DIF衰减。"""
from typing import List, Dict, Optional
from ..czsc_core import BI, ZS, Direction
from .trend import classify_trends, TrendType

def _macd_area(bis: List[BI], all_closes: List[float]) -> float:
    if not bis:
        return 0.0
    start_id = bis[0].raw_bars[0].id
    end_id = bis[-1].raw_bars[-1].id
    seg = all_closes[start_id:end_id+1]
    if len(seg) < 26:
        return abs(sum(seg)) / max(len(seg), 1)
    import numpy as np
    s = np.array(seg, dtype=float)
    ema12 = s.copy(); ema26 = s.copy()
    for i in range(1, len(s)):
        ema12[i] = ema12[i-1]*10/13 + s[i]*2/13
        ema26[i] = ema26[i-1]*24/27 + s[i]*2/27
    dif = ema12 - ema26
    return float(np.sum(np.abs(dif)))

def last_divergence(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> Dict:
    """判定最后一段是否背驰。返回 dict(is_divergence, kind, direction, ratio, ...)"""
    result = {'is_divergence': False, 'kind': 'none', 'direction': None,
              'ratio': 0.0, 'price_new_extreme': False, 'dif_weaken': False}
    if len(zs_list) < 1 or len(bis) < 5:
        return result

    trends = classify_trends(zs_list)
    if not trends:
        return result
    lt = trends[-1]
    is_trend = lt['type'] in (TrendType.UP, TrendType.DOWN)
    direction = Direction.Up if lt['type'] == TrendType.UP else Direction.Down

    if is_trend and len(lt['pivots']) >= 2:
        result['kind'] = 'trend'
        last_zs = lt['pivots'][-1]
        prev_zs = lt['pivots'][-2]
        a_bis = [b for b in bis if b.edt <= prev_zs.sdt and b.direction == direction][-3:] if direction == Direction.Up else [b for b in bis if b.edt <= prev_zs.sdt and b.direction == direction][-3:]
        c_bis = [b for b in bis if b.sdt >= last_zs.edt and b.direction == direction]
        if not a_bis or not c_bis:
            return result
        if direction == Direction.Up:
            a_ext = max(b.high for b in a_bis)
            c_ext = max(b.high for b in c_bis)
            result['price_new_extreme'] = c_ext > a_ext
        else:
            a_ext = min(b.low for b in a_bis)
            c_ext = min(b.low for b in c_bis)
            result['price_new_extreme'] = c_ext < a_ext
    else:
        result['kind'] = 'consolidation'
        last_zs = zs_list[-1]
        half = len(last_zs.bis) // 2
        a_bis = last_zs.bis[:half]
        c_bis = last_zs.bis[half:]
        if not a_bis or not c_bis:
            return result
        result['price_new_extreme'] = True

    area_a = _macd_area(a_bis, closes)
    area_c = _macd_area(c_bis, closes)
    ratio = area_c / area_a if area_a > 0 else 999
    result['ratio'] = round(ratio, 3)
    result['area_a'] = round(area_a, 2)
    result['area_c'] = round(area_c, 2)
    result['direction'] = direction
    result['dif_weaken'] = ratio < 0.85
    result['is_divergence'] = result['price_new_extreme'] and result['dif_weaken']
    return result
