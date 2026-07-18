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

    连续3段以上有重叠区间 → 构成中枢, zg=min(前3段高), zd=max(前3段低)。
    """
    if len(segments) < 3:
        return []

    pivots = []
    cur_segs = [segments[0]]

    for seg in segments[1:]:
        # 计算当前组加入新段后是否仍有公共区间
        all_segs = cur_segs + [seg]
        highs = [max(s.start_value, s.end_value) for s in all_segs[:3]]
        lows = [min(s.start_value, s.end_value) for s in all_segs[:3]]
        zg = min(highs)
        zd = max(lows)
        if zg >= zd:
            cur_segs.append(seg)
            continue

        # 当前组形成中枢
        if len(cur_segs) >= 3:
            seg_highs = [max(s.start_value, s.end_value) for s in cur_segs]
            seg_lows = [min(s.start_value, s.end_value) for s in cur_segs]
            pivots.append({
                'zg': min(seg_highs[:3]),
                'zd': max(seg_lows[:3]),
                'gg': max(seg_highs),
                'dd': min(seg_lows),
                'seg_count': len(cur_segs),
                'level': 'segment',
            })
        cur_segs = [seg]

    # 最后一组
    if len(cur_segs) >= 3:
        seg_highs = [max(s.start_value, s.end_value) for s in cur_segs]
        seg_lows = [min(s.start_value, s.end_value) for s in cur_segs]
        pivots.append({
            'zg': min(seg_highs[:3]),
            'zd': max(seg_lows[:3]),
            'gg': max(seg_highs),
            'dd': min(seg_lows),
            'seg_count': len(cur_segs),
            'level': 'segment',
        })

    return pivots
