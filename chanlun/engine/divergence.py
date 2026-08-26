"""MACD背驰判断模块

核心逻辑（缠论第24课）：
- 背驰发生在趋势中：A段(推动) + B段(中枢/回调) + C段(推动)
- B段将MACD黄白线回拉到0轴附近
- C段MACD柱面积 < A段MACD柱面积 → 背驰成立

MACD定律：
- 第一类买点在0轴之下背驰形成
- 第二类买点在第一次上0轴后回抽确认
"""
import numpy as np
from typing import List, Optional, Tuple
from .types import Divergence


def compute_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
                 ) -> Tuple[List[float], List[float], List[float]]:
    """计算MACD指标
    
    Returns:
        (dif_list, dea_list, macd_bar_list)
        macd_bar = (dif - dea) * 2
    """
    closes_arr = np.array(closes, dtype=float)
    
    # EMA计算
    ema_fast = _ema(closes_arr, fast)
    ema_slow = _ema(closes_arr, slow)
    
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    macd_bar = (dif - dea) * 2
    
    return dif.tolist(), dea.tolist(), macd_bar.tolist()


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均"""
    result = np.zeros_like(data)
    multiplier = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
    return result


def calc_macd_area(macd_bar: List[float], start_idx: int, end_idx: int) -> float:
    """计算指定区间内MACD柱面积（绝对值累加）
    
    Args:
        macd_bar: MACD柱值序列
        start_idx: 起始索引
        end_idx: 结束索引（包含）
    
    Returns:
        面积（绝对值累加）
    """
    if start_idx < 0 or end_idx >= len(macd_bar):
        return 0.0
    segment = macd_bar[start_idx:end_idx + 1]
    return sum(abs(v) for v in segment)


def check_divergence(macd_bar: List[float], dif: List[float],
                     a_start: int, a_end: int,
                     c_start: int, c_end: int,
                     threshold: float = 0.7) -> Divergence:
    """检查A段与C段之间是否存在背驰
    
    Args:
        macd_bar: MACD柱值序列
        dif: DIF值序列
        a_start, a_end: A段起止索引
        c_start, c_end: C段起止索引
        threshold: 背驰判断阈值（C/A面积比 < threshold 则背驰）
    
    Returns:
        Divergence对象
    """
    area_a = calc_macd_area(macd_bar, a_start, a_end)
    area_c = calc_macd_area(macd_bar, c_start, c_end)
    
    # 避免除零
    ratio = area_c / area_a if area_a > 0 else 1.0
    is_divergent = ratio < threshold
    
    return Divergence(
        area_a=round(area_a, 2),
        area_c=round(area_c, 2),
        ratio=round(ratio, 3),
        is_divergent=is_divergent,
        a_start_idx=a_start,
        a_end_idx=a_end,
        c_start_idx=c_start,
        c_end_idx=c_end
    )


def find_trend_divergence(strokes, pivots, macd_bar: List[float], dif: List[float]
                          ) -> Optional[Divergence]:
    """在走势中自动寻找趋势背驰
    
    逻辑：
    1. 找到最后一个已完成的中枢
    2. 中枢前的推动段为A段
    3. 中枢后的推动段为C段
    4. 比较A和C段的MACD面积
    """
    if not pivots or len(strokes) < 5:
        return None
    
    last_pivot = pivots[-1]
    
    # 找中枢前的推动段（A段）
    # A段 = 中枢第一笔之前的同向笔
    pivot_start_idx = last_pivot.start_idx
    a_strokes = [s for s in strokes if s.end_idx <= pivot_start_idx]
    if not a_strokes:
        return None
    
    # A段范围
    a_start = a_strokes[-1].start_idx if len(a_strokes) >= 1 else 0
    a_end = pivot_start_idx
    
    # 找中枢后的推动段（C段）
    # P0-B4: 锚点改用"中枢最后一笔的起点"而非中枢结束索引。
    # 中枢常延伸至最后一笔, 此时没有任何笔满足 start_idx >= pivot_end_idx,
    # c_strokes 恒空 -> 静默 return None。同源问题在 czsc 引擎实测 87% 失效率。
    # 用最后一笔起点作锚点, 可纳入"正在离开中枢的那一笔", 实现实时背驰识别。
    pivot_end_idx = last_pivot.end_idx
    _pivot_strokes = getattr(last_pivot, 'strokes', None)
    if _pivot_strokes:
        _c_anchor = _pivot_strokes[-1].start_idx
    else:
        _c_anchor = pivot_end_idx
    c_strokes = [s for s in strokes if s.start_idx >= _c_anchor]
    if not c_strokes:
        # 退化: 直接取最后一笔作为离开段候选
        c_strokes = strokes[-1:] if strokes else []
    if not c_strokes:
        return None

    c_start = min(_c_anchor, c_strokes[0].start_idx)
    c_end = c_strokes[-1].end_idx
    
    # 确保索引在有效范围内
    if c_end >= len(macd_bar):
        c_end = len(macd_bar) - 1
    if a_end >= len(macd_bar):
        a_end = len(macd_bar) - 1
    
    return check_divergence(macd_bar, dif, a_start, a_end, c_start, c_end)
