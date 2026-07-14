"""中枢计算模块

核心定义：
- 走势中枢 = 至少三个连续次级别走势类型的重叠部分
- 简化实现：至少连续3笔的价格重叠区间
- ZG = min(第1笔高点, 第2笔高点) — 中枢上沿
- ZD = max(第1笔低点, 第2笔低点) — 中枢下沿  
- GG = max(所有笔高点) — 中枢区间最高
- DD = min(所有笔低点) — 中枢区间最低
- 中枢有效条件: ZG > ZD（存在重叠）
"""
from typing import List, Optional
from .types import Stroke, Pivot, PivotStatus, Direction


def find_pivots(strokes: List[Stroke], min_strokes: int = 3) -> List[Pivot]:
    """从笔序列中寻找所有中枢
    
    算法：
    1. 从第1笔开始，取连续3笔计算重叠区间
    2. 如果存在重叠（ZG > ZD），则中枢成立
    3. 继续检查后续笔是否还在中枢内（延伸）
    4. 一旦笔完全离开中枢，中枢结束，继续寻找下一个
    
    Args:
        strokes: 笔序列
        min_strokes: 构成中枢的最少笔数（默认3）
    
    Returns:
        中枢列表
    """
    if len(strokes) < min_strokes:
        return []
    
    pivots: List[Pivot] = []
    i = 0
    
    while i <= len(strokes) - min_strokes:
        # 尝试用第i, i+1, i+2笔构建中枢
        s1, s2, s3 = strokes[i], strokes[i+1], strokes[i+2]
        
        # 计算三笔的高低点
        highs = [max(s.start_value, s.end_value) for s in [s1, s2, s3]]
        lows = [min(s.start_value, s.end_value) for s in [s1, s2, s3]]
        
        # ZG = min(前两笔的高点), ZD = max(前两笔的低点)
        # 用三笔两两重叠的方式：取所有高点的次低值和所有低点的次高值
        zg = min(highs[0], highs[2])  # 第1、3笔高点的较低者
        zd = max(lows[0], lows[2])    # 第1、3笔低点的较高者
        
        if zg <= zd:
            # 不存在重叠，不构成中枢，前进一步
            i += 1
            continue
        
        # 中枢成立，计算GG/DD
        gg = max(highs)
        dd = min(lows)
        pivot_strokes = [s1, s2, s3]
        
        # 检查后续笔是否在中枢内（中枢延伸）
        j = i + 3
        while j < len(strokes):
            sj = strokes[j]
            sj_high = max(sj.start_value, sj.end_value)
            sj_low = min(sj.start_value, sj.end_value)
            
            # 笔与中枢[ZD, ZG]有重叠则属于中枢延伸
            if sj_low < zg and sj_high > zd:
                pivot_strokes.append(sj)
                gg = max(gg, sj_high)
                dd = min(dd, sj_low)
                j += 1
            else:
                # 笔完全离开中枢
                break
        
        # 判断中枢方向
        direction = _determine_pivot_direction(pivot_strokes)
        
        # 判断状态
        status = PivotStatus.COMPLETED if j < len(strokes) else PivotStatus.ACTIVE
        
        pivot = Pivot(
            start_idx=s1.start_idx,
            end_idx=pivot_strokes[-1].end_idx,
            zg=zg,
            zd=zd,
            gg=gg,
            dd=dd,
            direction=direction,
            status=status,
            strokes=pivot_strokes
        )
        pivots.append(pivot)
        
        # 从中枢结束位置继续寻找下一个
        i = j
    
    return pivots


def _determine_pivot_direction(strokes: List[Stroke]) -> Optional[Direction]:
    """判断中枢方向：看中枢前后的走势方向"""
    if not strokes:
        return None
    # 简单判断：如果中枢内向上笔多则向上，反之向下
    up_count = sum(1 for s in strokes if s.direction == Direction.UP)
    down_count = len(strokes) - up_count
    if up_count > down_count:
        return Direction.UP
    elif down_count > up_count:
        return Direction.DOWN
    return None


def check_pivot_break(pivot: Pivot, stroke: Stroke) -> Optional[str]:
    """检查笔是否突破/跌破中枢（第三类买卖点判断基础）
    
    Returns:
        'break_up' - 向上突破ZG
        'break_down' - 向下跌破ZD
        None - 未突破
    """
    s_high = max(stroke.start_value, stroke.end_value)
    s_low = min(stroke.start_value, stroke.end_value)
    
    if s_low > pivot.zg:
        return "break_up"
    elif s_high < pivot.zd:
        return "break_down"
    return None
