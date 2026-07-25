"""线段划分模块 - 特征序列法

理论依据: 缠中说禅 65/67 课。
- 线段至少由3笔构成，方向与首笔一致。
- 特征序列: 向上线段取所有向下笔; 向下线段取所有向上笔。
- 特征序列元素按线段方向做包含处理。
- 线段结束: 特征序列出现反向分型。
  - 情况一(无缺口): 分型前两元素区间重叠 -> 直接确认(is_confirmed=True)。
  - 情况二(有缺口): 前两元素不重叠 -> 标记 gap=True, is_confirmed=False, 待后续迭代确认。
"""
from typing import List, Optional, Tuple
from .types import Stroke, Segment, Direction


def _merge_feature(feature: List[dict], direction: Direction) -> List[dict]:
    """特征序列包含处理（方向与线段方向一致）"""
    if not feature:
        return []
    merged = [dict(feature[0])]
    for cur in feature[1:]:
        prev = merged[-1]
        contain = (
            (prev["high"] >= cur["high"] and prev["low"] <= cur["low"]) or
            (cur["high"] >= prev["high"] and cur["low"] <= prev["low"])
        )
        if contain:
            if direction == Direction.UP:
                # 向上线段: 高取高, 低取高
                nh = max(prev["high"], cur["high"])
                nl = max(prev["low"], cur["low"])
                idx = cur["idx"] if cur["high"] >= prev["high"] else prev["idx"]
            else:
                # 向下线段: 低取低, 高取低
                nh = min(prev["high"], cur["high"])
                nl = min(prev["low"], cur["low"])
                idx = cur["idx"] if cur["low"] <= prev["low"] else prev["idx"]
            merged[-1] = {"high": nh, "low": nl, "idx": idx}
        else:
            merged.append(dict(cur))
    return merged


def _find_segment_end(strokes: List[Stroke], start: int,
                      direction: Direction) -> Tuple[Optional[int], bool, bool]:
    """在从 start 开始、方向为 direction 的笔序列中寻找线段终点。

    Returns: (end_stroke_index, is_confirmed, gap)；找不到返回 (None, False, False)。
    """
    opp = Direction.DOWN if direction == Direction.UP else Direction.UP
    feature: List[dict] = []
    for i in range(start, len(strokes)):
        s = strokes[i]
        if s.direction == opp:
            hi = max(s.start_value, s.end_value)
            lo = min(s.start_value, s.end_value)
            feature.append({"high": hi, "low": lo, "idx": i})
    if len(feature) < 3:
        return None, False, False

    merged = _merge_feature(feature, direction)
    if len(merged) < 3:
        return None, False, False

    for k in range(1, len(merged) - 1):
        e1, e2, e3 = merged[k - 1], merged[k], merged[k + 1]
        if direction == Direction.UP:
            # 向上线段: 特征序列顶分型只看主维度(高点)，e2 高点为三者最高
            is_fx = e2["high"] > e1["high"] and e2["high"] > e3["high"]
        else:
            # 向下线段: 特征序列底分型只看主维度(低点)，e2 低点为三者最低
            is_fx = e2["low"] < e1["low"] and e2["low"] < e3["low"]
        if not is_fx:
            continue

        # 转折笔(e2对应的反向笔)之前的同向笔为线段终点笔
        end_idx = e2["idx"] - 1
        if end_idx < start + 2:
            continue  # 线段至少3笔

        # 缺口判断: 分型前两元素区间是否重叠
        overlap = min(e1["high"], e2["high"]) >= max(e1["low"], e2["low"])
        gap = not overlap
        confirmed = not gap
        return end_idx, confirmed, gap

    return None, False, False


def _make_segment(strokes: List[Stroke], start: int, end: int,
                  direction: Direction, confirmed: bool, gap: bool) -> Segment:
    seg_strokes = strokes[start:end + 1]
    return Segment(
        direction=direction,
        start_idx=strokes[start].start_idx,
        end_idx=strokes[end].end_idx,
        start_value=strokes[start].start_value,
        end_value=strokes[end].end_value,
        strokes=seg_strokes,
        is_confirmed=confirmed,
        gap=gap,
    )


def build_segments(strokes: List[Stroke]) -> List[Segment]:
    """从笔序列构建线段序列。

    线段方向由首笔方向决定；用特征序列分型确定线段终点，
    终点笔作为下一线段的前一笔（首尾相接于同一转折点）。
    """
    if len(strokes) < 3:
        return []

    segments: List[Segment] = []
    start = 0
    n = len(strokes)
    guard = 0

    while start + 2 < n and guard < n + 5:
        guard += 1
        direction = strokes[start].direction
        end, confirmed, gap = _find_segment_end(strokes, start, direction)

        if end is None:
            # 剩余笔不足以确认新线段终点 -> 归为一条未确认线段
            seg = _make_segment(strokes, start, n - 1, direction, False, False)
            if len(seg.strokes) >= 3:
                segments.append(seg)
            break

        segments.append(_make_segment(strokes, start, end, direction, confirmed, gap))
        start = end + 1

    return segments
