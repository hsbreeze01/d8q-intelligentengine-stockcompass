# -*- coding: utf-8 -*-
"""线段适配层: 将 czsc_core.BI 对象转换为 engine/types.Stroke 格式,
然后调用 segment.build_segments 生成线段, 再基于线段构建中枢。

用途: 解决"笔直接构中枢导致级别错位"的核心问题。
线段中枢 = 日线操作级别的真实中枢。
"""
from typing import List
from ..czsc_core import BI, Direction as CDirection
from .types import Stroke, Segment, Fractal, FractalType, Direction as TDirection
from .segment import build_segments

MAX_ZS_SEGS = 9


def _czsc_dir_to_types_dir(d: CDirection) -> TDirection:
    if d == CDirection.Up:
        return TDirection.UP
    return TDirection.DOWN


def bi_to_stroke(bi: BI, idx: int) -> Stroke:
    """将 czsc BI 对象适配为 types.Stroke"""
    direction = _czsc_dir_to_types_dir(bi.direction)
    if direction == TDirection.UP:
        start_value = bi.low
        end_value = bi.high
        start_fx_type = FractalType.BOTTOM
        end_fx_type = FractalType.TOP
    else:
        start_value = bi.high
        end_value = bi.low
        start_fx_type = FractalType.TOP
        end_fx_type = FractalType.BOTTOM

    start_id = bi.raw_bars[0].id if bi.raw_bars else idx * 2
    end_id = bi.raw_bars[-1].id if bi.raw_bars else idx * 2 + 1
    start_dt = str(bi.sdt)[:10] if bi.sdt else ''
    end_dt = str(bi.edt)[:10] if bi.edt else ''

    start_fx = Fractal(type=start_fx_type, idx=start_id, dt=start_dt, value=start_value)
    end_fx = Fractal(type=end_fx_type, idx=end_id, dt=end_dt, value=end_value)

    return Stroke(
        direction=direction,
        start_fractal=start_fx,
        end_fractal=end_fx,
        start_idx=start_id,
        end_idx=end_id,
        start_value=start_value,
        end_value=end_value,
        kline_count=len(bi.raw_bars) if bi.raw_bars else 0,
    )


def bis_to_segments(bis: List[BI]) -> List[Segment]:
    """czsc BI 序列 → Stroke 序列 → Segment 线段序列"""
    if len(bis) < 3:
        return []
    strokes = [bi_to_stroke(bi, i) for i, bi in enumerate(bis)]
    return build_segments(strokes)


def segment_pivots(segments: List[Segment]) -> List[dict]:
    """基于线段序列构建线段级别中枢。

    连续3段的共同重叠区间确立中枢。后续线段仅在与既有
    [ZD, ZG] 重叠时延伸；方向性离开或达到9段时封闭。
    """
    if len(segments) < 3:
        return []

    pivots = []
    start = 0
    while start <= len(segments) - 3:
        seed = segments[start:start + 3]
        seed_highs = [max(s.start_value, s.end_value) for s in seed]
        seed_lows = [min(s.start_value, s.end_value) for s in seed]
        zg = min(seed_highs)
        zd = max(seed_lows)
        if zg < zd:
            start += 1
            continue

        cur_segs = list(seed)
        next_idx = start + 3
        while next_idx < len(segments) and len(cur_segs) < MAX_ZS_SEGS:
            seg = segments[next_idx]
            high = max(seg.start_value, seg.end_value)
            low = min(seg.start_value, seg.end_value)
            leaves_up = seg.direction == TDirection.UP and low > zg
            leaves_down = seg.direction == TDirection.DOWN and high < zd
            if leaves_up or leaves_down or high < zd or low > zg:
                break
            cur_segs.append(seg)
            next_idx += 1

        seg_highs = [max(s.start_value, s.end_value) for s in cur_segs]
        seg_lows = [min(s.start_value, s.end_value) for s in cur_segs]
        pivots.append({
            'zg': zg,
            'zd': zd,
            'gg': max(seg_highs),
            'dd': min(seg_lows),
            'seg_count': len(cur_segs),
            'level': 'segment',
        })
        start = next_idx

    return pivots
