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


def get_zs_seq(bis):
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
        else:
            if (bi.direction == Direction.Up and bi.high < zs.zd) or                (bi.direction == Direction.Down and bi.low > zs.zg):
                zs_list.append(ZS(bis=[bi]))
            else:
                zs.bis.append(bi); zs_list[-1] = zs
    return zs_list


def valid_pivots(bis):
    return [zs for zs in get_zs_seq(bis) if len(zs.bis) >= 3 and zs.is_valid]
