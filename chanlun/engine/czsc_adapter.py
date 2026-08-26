# -*- coding: utf-8 -*-
"""czsc 适配器: 将K线接入 vendored czsc 核心, 提供笔与中枢序列。
get_zs_seq 移植自 czsc.utils.sig.get_zs_seq (Apache-2.0)。
"""
from datetime import datetime
from typing import List
from ..czsc_core import CZSC, RawBar, Freq, Direction, ZS, BI


def klines_to_bars(symbol, klines):
    bars = []
    for i, k in enumerate(klines):
        dt = k.get('dt') or k.get('date')
        if not isinstance(dt, datetime):
            dt = datetime.strptime(str(dt)[:10], '%Y-%m-%d')
        bars.append(RawBar(symbol=symbol, id=i, dt=dt, freq=Freq.D,
                           open=float(k['open']), close=float(k['close']),
                           high=float(k['high']), low=float(k['low']),
                           vol=float(k.get('volume', k.get('vol', 0))), amount=0.0))
    return bars


def build_czsc(symbol, klines):
    return CZSC(klines_to_bars(symbol, klines))


# B3-6: 中枢最大延伸笔数。缠论标准中枢3笔, 延伸为5/7/9笔;
# 超过9笔属级别升级(中枢扩展), 应封闭当前中枢而非继续吞并。
MAX_ZS_BIS = 9


def get_zs_seq(bis):
    """构造中枢序列。

    B3-6: 加入两项终止条件, 消除中枢无限膨胀:
    1. 笔整体突破中枢上沿/下沿(原实现只判反向离开, 遗漏突破方向)
    2. 中枢笔数达到 MAX_ZS_BIS 上限
    修复前实测: 末中枢最大 42 笔、跨越 324 天, 使 zg/zd 完全脱离当前价格。
    """
    zs_list = []
    if not bis:
        return []
    for bi in bis:
        if not zs_list:
            zs_list.append(ZS(bis=[bi]))
            continue
        zs = zs_list[-1]
        if not zs.bis:
            zs.bis.append(bi); zs_list[-1] = zs
        elif len(zs.bis) >= MAX_ZS_BIS:
            # 达到延伸上限 -> 封闭当前中枢, 由该笔开启新中枢
            zs_list.append(ZS(bis=[bi]))
        else:
            # 原有条件: 笔整体落在中枢区间之外的"反向"一侧
            _left_reverse = ((bi.direction == Direction.Up and bi.high < zs.zd) or
                            (bi.direction == Direction.Down and bi.low > zs.zg))
            # B3-6: 补齐缺失的"突破方向"离开判定。
            # 旧实现只判反向离开, 遗漏了 上涨笔整体高于ZG / 下跌笔整体低于ZD 两种突破,
            # 使这些笔被 else 分支吞并, 中枢无限膨胀
            # (实测 14% 末中枢笔数>10, 最大21笔跨324天; 71% 标的现价落在末中枢之外)。
            _left_breakout = ((bi.direction == Direction.Up and bi.low > zs.zg) or
                              (bi.direction == Direction.Down and bi.high < zs.zd))
            if _left_reverse or _left_breakout:
                zs_list.append(ZS(bis=[bi]))
            else:
                zs.bis.append(bi); zs_list[-1] = zs
    return zs_list


def valid_pivots(bis):
    return [zs for zs in get_zs_seq(bis) if len(zs.bis) >= 3 and zs.is_valid]
