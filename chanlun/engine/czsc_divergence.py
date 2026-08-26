# -*- coding: utf-8 -*-
"""背驰判定(czsc路线): 趋势前提+同级别推动段+创新极值+有方向DIF柱面积比。"""
from typing import List, Dict, Optional
from ..czsc_core import BI, ZS, Direction
from .trend import classify_trends, TrendType

# DIF 预热长度: EMA26 需要至少这么多根K线才基本收敛。
# 注意语义: 这是对"区间终点位置"的要求(终点须已越过预热段),
# 不是对被度量区间自身长度的要求 —— 短区间只是求和项少, 不影响量纲。
MACD_MIN_BARS = 26

# P2-3: 记录 _macd_dif_area 最近一次返回 0 的成因, 供 last_divergence 细分 abort_reason。
# 单线程调用, 用模块级 dict 传递即可。
_macd_area_reason = {'last': None}


def _full_dif(all_closes):
    """在完整收盘序列上计算 DIF(EMA12-EMA26), 自序列起点预热。

    B1-2/B3d: 旧实现对每个区间单独切片后重新初始化 EMA,
    a 段与 c 段的 EMA 起点不同 -> DIF 基线漂移、两段不可比。
    改为全序列计算一次, 保证所有区间共享同一条 DIF 曲线。
    """
    import numpy as np
    s = np.array(all_closes, dtype=float)
    ema12 = s.copy(); ema26 = s.copy()
    for i in range(1, len(s)):
        ema12[i] = ema12[i-1] * 10/13 + s[i] * 2/13
        ema26[i] = ema26[i-1] * 24/27 + s[i] * 2/27
    return ema12 - ema26


def _macd_dif_area(bis: List[BI], all_closes: List[float], direction: Direction) -> float:
    """计算推动段的有方向 DIF 面积。

    - 下跌推动段取负 DIF 柱面积, 上涨推动段取正 DIF 柱面积, 返回绝对值
    - B1-1: 绝不返回平均股价等其它量纲的值; 无法计算时返回 0.0 (fail-closed)
    - B3d : 区间长度本身不再作为门槛, 仅要求区间终点已越过 EMA 预热段
    """
    if not bis or not all_closes:
        return 0.0
    try:
        start_id = bis[0].raw_bars[0].id
        end_id = bis[-1].raw_bars[-1].id
    except Exception:
        return 0.0

    n = len(all_closes)
    # 全序列过短 -> EMA26 无法收敛
    if n < MACD_MIN_BARS:
        return 0.0
    # 区间终点仍处于预热段内 -> DIF 不可信
    if end_id < MACD_MIN_BARS:
        return 0.0
    # P2-3: 供调用方区分 abort 成因(预热不足 vs 该方向无DIF柱)
    _macd_area_reason['last'] = None

    dif = _full_dif(all_closes)
    lo = max(0, min(start_id, len(dif) - 1))
    hi = min(end_id, len(dif) - 1)
    if hi < lo:
        return 0.0

    seg = dif[lo:hi+1]
    # 有方向的面积: 下跌看负DIF柱, 上涨看正DIF柱
    if direction == Direction.Down:
        signed = seg[seg < 0]
    else:
        signed = seg[seg > 0]
    if len(signed) == 0:
        # 该方向上无对应DIF柱 -> 无推动力度(不回退取全部绝对值, 避免掩盖)
        # P2-3: 标记成因, 与"预热不足"区分开
        _macd_area_reason['last'] = 'no_directional_bars'
        return 0.0
    import numpy as np
    return float(np.sum(np.abs(signed)))


def last_divergence(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> Dict:
    """判定最后一段是否背驰。返回 dict(is_divergence, kind, direction, ratio, ...)"""
    result = {'is_divergence': False, 'kind': 'none', 'direction': None,
              'ratio': 0.0, 'price_new_extreme': False, 'dif_weaken': False}
    if len(zs_list) < 1 or len(bis) < 5:
        return result

    trends = classify_trends(zs_list)
    if not trends:
        result['abort_reason'] = 'no_trend_segment'
        return result
    lt = trends[-1]
    is_trend = lt['type'] in (TrendType.UP, TrendType.DOWN)

    if is_trend and len(lt['pivots']) >= 2:
        # ===== 趋势背驰 =====
        result['kind'] = 'trend'
        direction = Direction.Up if lt['type'] == TrendType.UP else Direction.Down
        last_zs = lt['pivots'][-1]
        prev_zs = lt['pivots'][-2]

        # a段: 进入前一个中枢之前的同向推动笔(取最近3笔)
        a_bis = [b for b in bis if b.edt <= prev_zs.sdt and b.direction == direction][-3:]

        # B3-1: c段锚点改用"最后一个中枢的最后一笔的起点"。
        # 旧实现用 last_zs.edt(中枢结束时间), 但中枢常延伸至最后一笔,
        # 导致无任何笔满足 sdt >= edt, c段恒空 -> 实测 202/234 (87%) 静默放弃背驰。
        # 用最后一笔起点作锚点, 可纳入"正在离开中枢的那一笔", 实现实时背驰识别。
        _c_anchor = last_zs.bis[-1].sdt if getattr(last_zs, 'bis', None) else last_zs.edt
        c_bis = [b for b in bis if b.sdt >= _c_anchor and b.direction == direction]
        if not c_bis:
            _tail = [b for b in getattr(last_zs, 'bis', []) if b.direction == direction]
            c_bis = _tail[-1:] if _tail else []

        if not a_bis:
            result['direction'] = direction
            result['abort_reason'] = 'trend_a_seg_empty'
            return result
        if not c_bis:
            result['direction'] = direction
            result['abort_reason'] = 'trend_c_seg_empty'
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
        # ===== 盘整背驰 =====
        result['kind'] = 'consolidation'
        last_zs = zs_list[-1]

        # B3-4: 盘整时走势类型为 CONSOLIDATION, 旧三元表达式
        #   direction = Up if type==UP else Down
        # 使 direction 恒为 Down —— 盘整背驰永远只产生一买, 永不产生一卖。
        # 改为由最后一笔方向决定: 末笔向下->判底背驰, 末笔向上->判顶背驰。
        direction = bis[-1].direction

        # B3-3: a/c 段改为"同向笔"划分。
        # 旧实现机械对半切 last_zs.bis, 两段均混合上涨笔与下跌笔
        # (实测方向序列 a=UD, c=UDU), 与缠论"比较同向推动段"定义不符。
        _same = [b for b in getattr(last_zs, 'bis', []) if b.direction == direction]
        if len(_same) < 2:
            result['direction'] = direction
            result['abort_reason'] = 'consolidation_same_dir_bis_lt2'
            return result
        _half = len(_same) // 2
        a_bis = _same[:_half] or _same[:1]
        c_bis = _same[_half:]
        if not a_bis or not c_bis:
            result['direction'] = direction
            result['abort_reason'] = 'consolidation_seg_empty'
            return result

        # B3-2: 真实校验价格是否创新极值(原硬编码 True, 使盘整背驰只剩DIF一个条件)
        if direction == Direction.Up:
            a_ext = max(b.high for b in a_bis)
            c_ext = max(b.high for b in c_bis)
            result['price_new_extreme'] = c_ext > a_ext
        else:
            a_ext = min(b.low for b in a_bis)
            c_ext = min(b.low for b in c_bis)
            result['price_new_extreme'] = c_ext < a_ext

    result['a_ext'] = round(a_ext, 2)
    result['c_ext'] = round(c_ext, 2)

    _macd_area_reason['last'] = None      # P2-3: 本次判定前重置成因
    area_a = _macd_dif_area(a_bis, closes, direction)
    area_c = _macd_dif_area(c_bis, closes, direction)
    result['direction'] = direction
    result['area_a'] = round(area_a, 2)
    result['area_c'] = round(area_c, 2)

    # B1-1: 任一段无法可靠计算DIF面积(返回0) -> 放弃背驰判定(fail-closed)
    if area_a <= 0 or area_c <= 0:
        result['ratio'] = 0.0
        result['dif_weaken'] = False
        result['is_divergence'] = False
        # P2-3: 细分两种成因, 便于诊断
        if _macd_area_reason.get('last') == 'no_directional_bars':
            result['abort_reason'] = 'macd_no_directional_bars'
        else:
            result['abort_reason'] = 'macd_warmup_insufficient'
        return result

    ratio = area_c / area_a
    result['ratio'] = round(ratio, 3)
    result['dif_weaken'] = ratio < 0.85
    result['is_divergence'] = result['price_new_extreme'] and result['dif_weaken']
    return result
