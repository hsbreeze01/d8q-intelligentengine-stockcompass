"""三类买卖点检测模块

第一类买点：下跌趋势最后中枢后出现MACD背驰
第二类买点：一买后第一次回调不破前低
第三类买点：次级别离开中枢后回试不破ZG

卖点逻辑反之。
"""
from typing import List, Optional
from ..engine.types import (
    Stroke, Pivot, Divergence, Signal, SignalType,
    Direction, PivotStatus
)

# ===== P0-B2/B3: 价格语义与止损约束(与 czsc 引擎 czsc_buysell.py 对齐) =====
# 结构止损与执行价的最大距离。结构位过远时用该上限收紧,
# 避免出现 buy3 那种 zg*0.97 距现价 40%+ 的不可用止损。
MAX_STOP_PCT = 0.08


def _exec_price(idx, closes, fallback):
    """信号确认K线的收盘价 = 用户次一交易日可执行的基准价。

    P0-B2: 原实现 price 取笔极值(end_value, 盘中瞬时价), 用户无法成交。
    改为取该笔结束K线的收盘价; 拿不到时回退原结构值。
    """
    if closes:
        try:
            if 0 <= idx < len(closes):
                return float(closes[idx])
        except Exception:
            pass
    return fallback


def _ceil2(x):
    import math
    return math.ceil(float(x) * 100 - 1e-9) / 100.0


def _buy_stop(structural, exec_p):
    """买入止损: 结构位与 exec*(1-MAX_STOP_PCT) 取较高者(收紧过远的结构止损)"""
    if not exec_p or exec_p <= 0:
        return round(float(structural), 2)
    cap = exec_p * (1 - MAX_STOP_PCT)
    if float(structural) >= cap:
        return round(float(structural), 2)
    return _ceil2(cap)


def detect_buy3(strokes: List[Stroke], pivots: List[Pivot],
                current_price: float, closes: Optional[List[float]] = None) -> Optional[Signal]:
    """检测第三类买点
    
    条件：
    1. 存在已完成的中枢
    2. 一笔向上离开中枢（突破ZG）
    3. 随后回试（向下笔），低点不跌破ZG
    4. 当前价格在ZG上方
    """
    if not pivots or len(strokes) < 2:
        return None
    
    # 找最后一个已完成中枢
    completed_pivots = [p for p in pivots if p.status == PivotStatus.COMPLETED]
    if not completed_pivots:
        return None
    
    last_pivot = completed_pivots[-1]
    zg = last_pivot.zg
    
    # 找中枢之后的笔
    post_strokes = [s for s in strokes if s.start_idx >= last_pivot.end_idx]
    if len(post_strokes) < 2:
        return None
    
    # 检查是否有向上突破笔
    breakout_stroke = None
    for s in post_strokes:
        if s.direction == Direction.UP and s.end_value > zg:
            breakout_stroke = s
            break
    
    if not breakout_stroke:
        return None
    
    # 找突破后的回试笔
    pullback_strokes = [s for s in post_strokes 
                        if s.start_idx >= breakout_stroke.end_idx 
                        and s.direction == Direction.DOWN]
    
    if not pullback_strokes:
        return None
    
    pullback = pullback_strokes[0]
    pullback_low = pullback.end_value
    
    # 核心条件：回试不破ZG
    if pullback_low >= zg and current_price >= zg:
        reason = [
            f"中枢[{last_pivot.zd:.2f}-{zg:.2f}]已完成",
            f"向上突破至{breakout_stroke.end_value:.2f}",
            f"回试低点{pullback_low:.2f} >= ZG({zg:.2f})",
            "第三类买点成立"
        ]
        
        _exec = _exec_price(pullback.end_idx, closes, pullback_low)
        reason.append(f"可执行价{_exec:.2f}(结构参考{pullback_low:.2f})")
        return Signal(
            type=SignalType.BUY3,
            idx=pullback.end_idx,
            dt=pullback.end_fractal.dt if pullback.end_fractal else "",
            price=_exec,                              # P0-B2: 可执行价
            signal_ref_price=pullback_low,            # 结构参考: 回试低点
            exec_price=_exec,
            stop_loss=_buy_stop(zg * 0.97, _exec),    # P0-B3: 8%上限
            target=breakout_stroke.end_value + (breakout_stroke.end_value - zg),
            pivot=last_pivot,
            reason_chain=reason
        )
    
    return None


def detect_buy2(strokes: List[Stroke], pivots: List[Pivot],
                divergence: Optional[Divergence],
                closes: Optional[List[float]] = None) -> Optional[Signal]:
    """检测第二类买点
    
    条件：
    1. 此前存在MACD背驰（一买前提）
    2. 背驰后出现反弹（第一笔向上）
    3. 第一次回调的低点高于前低（二买核心）
    """
    if not divergence or not divergence.is_divergent:
        return None
    
    if len(strokes) < 4:
        return None
    
    # 最后几笔的分析
    # 假设: ...下跌笔(背驰低点) → 上涨笔(一买反弹) → 下跌笔(回调) → 当前
    last_strokes = strokes[-4:]
    
    # 找到背驰后的结构
    # 下跌底 → 反弹 → 回调（回调不破底 = 二买）
    decline_low = None
    rebound_high = None
    pullback_low = None
    pullback_stroke = None   # P0-B2: 记录回调笔本身, 使 idx/price/stop 三者同源
    
    for i in range(len(last_strokes) - 2):
        s1, s2, s3 = last_strokes[i], last_strokes[i+1], last_strokes[i+2]
        if (s1.direction == Direction.DOWN and 
            s2.direction == Direction.UP and 
            s3.direction == Direction.DOWN):
            decline_low = s1.end_value
            rebound_high = s2.end_value
            pullback_low = s3.end_value
            pullback_stroke = s3
            break
    
    if decline_low is None or pullback_low is None:
        return None
    
    # 二买条件：回调低点 > 前低
    if pullback_low > decline_low:
        reason = [
            f"MACD背驰确认（面积比{divergence.ratio:.2f}）",
            f"背驰低点{decline_low:.2f}",
            f"反弹至{rebound_high:.2f}后回调",
            f"回调低点{pullback_low:.2f} > 前低{decline_low:.2f}",
            "第二类买点成立"
        ]
        
        target = rebound_high  # 至少到前高
        if pivots:
            target = max(target, pivots[-1].zg)  # 或中枢上沿
        
        # P0-B2: idx 必须取回调笔(s3)的结束K线, 原实现用 last_strokes[-1].end_idx
        # 与 pullback_low 来自不同笔, 导致可执行价与结构价错配,
        # 极端情况下会让买入止损高于入场价(实测出现 9.4% 的异常止损距离)。
        _idx = pullback_stroke.end_idx if pullback_stroke is not None else last_strokes[-1].end_idx
        _exec = _exec_price(_idx, closes, pullback_low)
        reason.append(f"可执行价{_exec:.2f}(结构参考{pullback_low:.2f})")
        return Signal(
            type=SignalType.BUY2,
            idx=_idx,
            dt=(pullback_stroke.end_fractal.dt if (pullback_stroke is not None and pullback_stroke.end_fractal)
                else (last_strokes[-1].end_fractal.dt if last_strokes[-1].end_fractal else "")),
            price=_exec,
            signal_ref_price=pullback_low,
            exec_price=_exec,
            stop_loss=_buy_stop(decline_low * 0.97, _exec),
            target=target,
            divergence=divergence,
            reason_chain=reason
        )
    
    return None


def detect_buy1(strokes: List[Stroke], pivots: List[Pivot],
                divergence: Optional[Divergence],
                dif: List[float],
                closes: Optional[List[float]] = None) -> Optional[Signal]:
    """检测第一类买点
    
    条件：
    1. 处于下跌趋势（至少2个向下中枢）
    2. 最后一段出现MACD背驰
    3. DIF在0轴下方
    """
    if not divergence or not divergence.is_divergent:
        return None
    
    if not pivots or len(pivots) < 1:
        return None
    
    # DIF应在0轴下方（下跌中的背驰）
    if divergence.c_end_idx < len(dif):
        if dif[divergence.c_end_idx] >= 0:
            return None
    
    # 最后一笔应该是向下笔
    if not strokes or strokes[-1].direction != Direction.DOWN:
        return None
    
    last_stroke = strokes[-1]
    
    reason = [
        f"下跌趋势中MACD背驰（面积比{divergence.ratio:.2f}）",
        f"DIF在0轴下方",
        f"背驰低点{last_stroke.end_value:.2f}",
        "第一类买点成立（风险较高，需确认）"
    ]
    
    _exec = _exec_price(last_stroke.end_idx, closes, last_stroke.end_value)
    reason.append(f"可执行价{_exec:.2f}(结构参考{last_stroke.end_value:.2f})")
    return Signal(
        type=SignalType.BUY1,
        idx=last_stroke.end_idx,
        dt=last_stroke.end_fractal.dt if last_stroke.end_fractal else "",
        price=_exec,
        signal_ref_price=last_stroke.end_value,
        exec_price=_exec,
        stop_loss=_buy_stop(last_stroke.end_value * 0.95, _exec),
        target=pivots[-1].zd if pivots else last_stroke.end_value * 1.1,
        divergence=divergence,
        reason_chain=reason
    )
