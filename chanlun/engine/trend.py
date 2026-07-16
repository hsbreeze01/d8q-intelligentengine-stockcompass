# -*- coding: utf-8 -*-
"""走势类型判定: 盘整(单中枢) / 趋势(>=2个依次同向且不重叠的中枢)。

理论依据: 缠论 - 趋势由至少两个同方向连续的中枢构成; 盘整只有一个中枢。
基于 czsc 中枢序列(ZS)判定。
"""
from enum import Enum
from typing import List, Dict
from ..czsc_core import ZS


class TrendType(Enum):
    UP = "up_trend"            # 上涨趋势(>=2上涨中枢)
    DOWN = "down_trend"        # 下跌趋势(>=2下跌中枢)
    CONSOLIDATION = "consolidation"  # 盘整(单中枢)


def pivot_relation(z1: ZS, z2: ZS) -> str:
    """相邻两中枢的关系: up(z2整体在z1上方) / down(z2整体在下方) / overlap(有重叠)"""
    if z2.zd > z1.zg:
        return "up"
    if z2.zg < z1.zd:
        return "down"
    return "overlap"


def classify_trends(zs_list: List[ZS]) -> List[Dict]:
    """将中枢序列切分为走势段。

    连续 >=2 个同向不重叠中枢 => 趋势; 其余 => 盘整。
    返回: [{'type': TrendType, 'pivots': [ZS,...]}]
    """
    if not zs_list:
        return []

    groups = []
    cur = [zs_list[0]]
    cur_dir = None

    for i in range(1, len(zs_list)):
        rel = pivot_relation(cur[-1], zs_list[i])
        if rel in ("up", "down") and (cur_dir is None or cur_dir == rel):
            cur_dir = rel
            cur.append(zs_list[i])
        else:
            groups.append((cur_dir, cur))
            cur = [zs_list[i]]
            cur_dir = None
    groups.append((cur_dir, cur))

    result = []
    for d, ps in groups:
        if d == "up" and len(ps) >= 2:
            t = TrendType.UP
        elif d == "down" and len(ps) >= 2:
            t = TrendType.DOWN
        else:
            t = TrendType.CONSOLIDATION
        result.append({"type": t, "pivots": ps})
    return result


def last_trend(zs_list: List[ZS]) -> Dict:
    """返回最后一个走势段(用于判定当前处于趋势还是盘整)"""
    trends = classify_trends(zs_list)
    return trends[-1] if trends else {"type": TrendType.CONSOLIDATION, "pivots": []}


def is_trend_end_pivot(zs_list: List[ZS]) -> bool:
    """最后一个中枢是否为趋势的末端中枢(>=2同向中枢, 一/三类买卖点前提)"""
    lt = last_trend(zs_list)
    return lt["type"] in (TrendType.UP, TrendType.DOWN) and len(lt["pivots"]) >= 2
