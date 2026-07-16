"""笔划分模块

核心规则：
1. 笔由相邻的顶分型和底分型连接构成
2. 顶底分型之间至少有1根独立K线（即至少5根K线构成一笔）
3. 向上笔：底分型→顶分型，起点低终点高
4. 向下笔：顶分型→底分型，起点高终点低
5. 相邻分型必须交替出现（顶-底-顶-底）
"""
from typing import List
from .types import Fractal, FractalType, Stroke, Direction


def build_strokes(fractals: List[Fractal], min_kline_gap: int = 4) -> List[Stroke]:
    """从分型序列构建笔序列
    
    Args:
        fractals: 分型序列
        min_kline_gap: 顶底分型之间的最小K线间距（默认4，即中间至少1根独立K线）
    
    Returns:
        笔序列
    """
    if len(fractals) < 2:
        return []
    
    # 第一步：确保分型交替出现（顶底交替）
    # 相邻同类型分型只保留极值：顶取最高，底取最低
    alternating = _ensure_alternating(fractals)
    
    if len(alternating) < 2:
        return []
    
    # 第二步：检查间距，构建笔
    strokes: List[Stroke] = []
    
    i = 0
    while i < len(alternating) - 1:
        f1 = alternating[i]
        f2 = alternating[i + 1]
        
        # 检查间距要求
        gap = abs(f2.idx - f1.idx)
        if gap < min_kline_gap:
            # 间距不够，跳过f2，尝试下一个
            i += 1
            continue
        
        # 确定笔的方向
        if f1.type == FractalType.BOTTOM and f2.type == FractalType.TOP:
            direction = Direction.UP
            start_value = f1.value
            end_value = f2.value
        elif f1.type == FractalType.TOP and f2.type == FractalType.BOTTOM:
            direction = Direction.DOWN
            start_value = f1.value
            end_value = f2.value
        else:
            i += 1
            continue
        
        stroke = Stroke(
            direction=direction,
            start_fractal=f1,
            end_fractal=f2,
            start_idx=f1.idx,
            end_idx=f2.idx,
            start_value=start_value,
            end_value=end_value,
            kline_count=gap + 1
        )
        strokes.append(stroke)
        i += 1
    
    return strokes


def _ensure_alternating(fractals: List[Fractal]) -> List[Fractal]:
    """确保分型序列顶底交替出现
    
    规则：连续同类型分型中，顶分型保留最高的，底分型保留最低的
    """
    if not fractals:
        return []
    
    result: List[Fractal] = [fractals[0]]
    
    for i in range(1, len(fractals)):
        curr = fractals[i]
        prev = result[-1]
        
        if curr.type == prev.type:
            # 同类型：保留极值
            if curr.type == FractalType.TOP:
                if curr.value > prev.value:
                    result[-1] = curr
            else:  # BOTTOM
                if curr.value < prev.value:
                    result[-1] = curr
        else:
            # 不同类型：直接加入
            result.append(curr)
    
    return result


def build_strokes_strict(fractals: List[Fractal], min_kline_gap: int = 4) -> List[Stroke]:
    """严格笔构建（保证输出笔严格顶底交替且首尾相接）。

    与 build_strokes 的区别：间距不足时【删除分型并重新交替】，
    而非简单 i+=1 跳过——后者会产生连续同向笔与断裂（不相接）笔。
    """
    if len(fractals) < 2:
        return []

    alt = _ensure_alternating(fractals)

    # 反复删除间距不足的相邻分型，每次删除后重新确保交替（合并同型取极值）
    changed = True
    while changed and len(alt) >= 2:
        changed = False
        for i in range(len(alt) - 1):
            if abs(alt[i + 1].idx - alt[i].idx) < min_kline_gap:
                del alt[i + 1]
                alt = _ensure_alternating(alt)
                changed = True
                break

    strokes: List[Stroke] = []
    for i in range(len(alt) - 1):
        f1, f2 = alt[i], alt[i + 1]
        if f1.type == FractalType.BOTTOM and f2.type == FractalType.TOP:
            direction = Direction.UP
        elif f1.type == FractalType.TOP and f2.type == FractalType.BOTTOM:
            direction = Direction.DOWN
        else:
            continue  # 已交替，理论上不会走到
        strokes.append(Stroke(
            direction=direction,
            start_fractal=f1, end_fractal=f2,
            start_idx=f1.idx, end_idx=f2.idx,
            start_value=f1.value, end_value=f2.value,
            kline_count=abs(f2.idx - f1.idx) + 1,
        ))
    return strokes
