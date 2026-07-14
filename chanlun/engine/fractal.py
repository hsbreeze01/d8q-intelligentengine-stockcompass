"""分型识别模块

核心逻辑：
1. 包含关系处理：相邻K线存在包含时合并
   - 上涨中：取高点最高、低点较高者
   - 下跌中：取低点最低、高点较低者
2. 顶分型：中间K线高点最高且低点最高
3. 底分型：中间K线低点最低且高点最低
"""
from typing import List, Tuple
from .types import Kline, Fractal, FractalType, Direction


def process_inclusion(klines: List[Kline]) -> List[Kline]:
    """处理K线包含关系，返回标准化K线序列
    
    规则：
    - 向上时（前K线high < 当前high）：取两K线最高high，取两K线较高low
    - 向下时（前K线high > 当前high）：取两K线最低low，取两K线较低high
    """
    if len(klines) < 2:
        return klines

    result: List[Kline] = [klines[0]]
    
    for i in range(1, len(klines)):
        curr = klines[i]
        prev = result[-1]
        
        # 判断是否存在包含关系
        # 包含：一根K线的高低点完全在另一根内部
        has_inclusion = (
            (prev.merged_high >= curr.high and prev.merged_low <= curr.low) or
            (curr.high >= prev.merged_high and curr.low <= prev.merged_low)
        )
        
        if has_inclusion:
            # 确定当前方向
            if len(result) >= 2:
                direction = Direction.UP if result[-1].merged_high > result[-2].merged_high else Direction.DOWN
            else:
                direction = Direction.UP if curr.high >= prev.merged_high else Direction.DOWN
            
            # 合并
            if direction == Direction.UP:
                merged_high = max(prev.merged_high, curr.high)
                merged_low = max(prev.merged_low, curr.low)
            else:
                merged_high = min(prev.merged_high, curr.high)
                merged_low = min(prev.merged_low, curr.low)
            
            # 更新前一根K线的合并高低点
            prev.merged_high = merged_high
            prev.merged_low = merged_low
            prev.is_merged = True
        else:
            # 无包含关系，直接加入
            new_k = Kline(
                idx=curr.idx, dt=curr.dt,
                open=curr.open, high=curr.high,
                low=curr.low, close=curr.close,
                volume=curr.volume,
                merged_high=curr.high, merged_low=curr.low
            )
            result.append(new_k)
    
    return result


def find_fractals(klines: List[Kline]) -> List[Fractal]:
    """在标准化K线序列中识别顶底分型
    
    顶分型：K[i]的merged_high > K[i-1]和K[i+1]的merged_high
            且K[i]的merged_low > K[i-1]和K[i+1]的merged_low
    底分型：K[i]的merged_low < K[i-1]和K[i+1]的merged_low
            且K[i]的merged_high < K[i-1]和K[i+1]的merged_high
    """
    fractals: List[Fractal] = []
    
    if len(klines) < 3:
        return fractals
    
    for i in range(1, len(klines) - 1):
        prev_h, curr_h, next_h = klines[i-1].merged_high, klines[i].merged_high, klines[i+1].merged_high
        prev_l, curr_l, next_l = klines[i-1].merged_low, klines[i].merged_low, klines[i+1].merged_low
        
        # 顶分型
        if curr_h > prev_h and curr_h > next_h and curr_l > prev_l and curr_l > next_l:
            f = Fractal(
                type=FractalType.TOP,
                idx=klines[i].idx,
                dt=klines[i].dt,
                value=curr_h,
                kline_indices=[klines[i-1].idx, klines[i].idx, klines[i+1].idx]
            )
            fractals.append(f)
        
        # 底分型
        elif curr_l < prev_l and curr_l < next_l and curr_h < prev_h and curr_h < next_h:
            f = Fractal(
                type=FractalType.BOTTOM,
                idx=klines[i].idx,
                dt=klines[i].dt,
                value=curr_l,
                kline_indices=[klines[i-1].idx, klines[i].idx, klines[i+1].idx]
            )
            fractals.append(f)
    
    return fractals


def identify_fractals(raw_klines: List[dict]) -> Tuple[List[Kline], List[Fractal]]:
    """完整的分型识别流程
    
    输入: 原始K线数据列表 [{"dt":..,"open":..,"high":..,"low":..,"close":..,"volume":..}]
    输出: (标准化K线序列, 分型序列)
    """
    # 转换为Kline对象
    klines = [
        Kline(
            idx=i, dt=str(k.get("dt", k.get("date", ""))),
            open=float(k["open"]), high=float(k["high"]),
            low=float(k["low"]), close=float(k["close"]),
            volume=float(k.get("volume", k.get("vol", 0)))
        )
        for i, k in enumerate(raw_klines)
    ]
    
    # 包含关系处理
    merged_klines = process_inclusion(klines)
    
    # 分型识别
    fractals = find_fractals(merged_klines)
    
    return merged_klines, fractals
