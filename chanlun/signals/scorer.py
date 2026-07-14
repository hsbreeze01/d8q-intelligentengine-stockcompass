"""综合评分系统

评分维度：
- 形态分（40分）：中枢级别 + 买卖点明确度 + 划分无争议
- 动力分（30分）：MACD背驰程度 + 量价配合 + 黄白线位置
- 环境分（30分）：大盘状态 + 板块强弱 + 资金流向
"""
from typing import Optional
from ..engine.types import Signal, Pivot, Divergence, PivotStatus


def score_signal(signal: Signal,
                 pivot: Optional[Pivot] = None,
                 divergence: Optional[Divergence] = None,
                 volume_ratio: float = 1.0,
                 macd_dif: float = 0.0,
                 market_bullish: bool = False,
                 sector_strong: bool = False,
                 capital_inflow: bool = False) -> Signal:
    """计算信号的综合评分
    
    Args:
        signal: 原始信号
        pivot: 关联中枢
        divergence: 背驰信息
        volume_ratio: 成交量比率（当前量/20日均量）
        macd_dif: 当前DIF值
        market_bullish: 大盘是否友好
        sector_strong: 板块是否强势
        capital_inflow: 资金是否流入
    
    Returns:
        评分后的Signal对象
    """
    morphology = _score_morphology(signal, pivot)
    dynamics = _score_dynamics(signal, divergence, volume_ratio, macd_dif)
    environment = _score_environment(market_bullish, sector_strong, capital_inflow)
    
    signal.morphology_score = morphology
    signal.dynamics_score = dynamics
    signal.environment_score = environment
    signal.score = morphology + dynamics + environment
    
    return signal


def _score_morphology(signal: Signal, pivot: Optional[Pivot]) -> int:
    """形态分（满分40）"""
    score = 0
    
    # 中枢级别（日线级别 +15，更低级别 +8）
    # 简化：有完成的中枢就是日线级别
    if pivot and pivot.status == PivotStatus.COMPLETED:
        score += 15
    elif pivot:
        score += 8
    
    # 买卖点明确度：三买最明确(+15)，二买次之(+12)，一买(+8)
    type_val = signal.type.value
    if "buy3" in type_val or "sell3" in type_val:
        score += 15
    elif "buy2" in type_val or "sell2" in type_val:
        score += 12
    else:
        score += 8
    
    # 中枢笔数合理（3-5笔清晰 +10，过多笔延伸 +5）
    if pivot:
        if 3 <= len(pivot.strokes) <= 5:
            score += 10
        else:
            score += 5
    
    return min(score, 40)


def _score_dynamics(signal: Signal, divergence: Optional[Divergence],
                    volume_ratio: float, macd_dif: float) -> int:
    """动力分（满分30）"""
    score = 0
    
    # MACD背驰程度（面积比<0.7 +15，0.7-0.85 +8）
    if divergence:
        if divergence.ratio < 0.7:
            score += 15
        elif divergence.ratio < 0.85:
            score += 8
    elif signal.type.value in ("buy3", "sell3"):
        # 三买不需要背驰，给基础分
        score += 10
    
    # 量价配合（放量突破 +10，正常 +5）
    if volume_ratio >= 1.5:
        score += 10
    elif volume_ratio >= 1.0:
        score += 5
    
    # 黄白线位置（买点时DIF>0为+5，卖点时DIF<0为+5）
    if "buy" in signal.type.value and macd_dif > 0:
        score += 5
    elif "sell" in signal.type.value and macd_dif < 0:
        score += 5
    else:
        score += 2
    
    return min(score, 30)


def _score_environment(market_bullish: bool, sector_strong: bool,
                       capital_inflow: bool) -> int:
    """环境分（满分30）"""
    score = 0
    score += 10 if market_bullish else 3
    score += 10 if sector_strong else 3
    score += 10 if capital_inflow else 3
    return min(score, 30)


def get_action_suggestion(score: int, capital: float = 150000) -> dict:
    """根据评分给出操作建议
    
    Args:
        score: 综合评分
        capital: 总资金
    
    Returns:
        {"action": str, "position": float, "reason": str}
    """
    max_single = capital * 0.27  # 单票上限27%
    
    if score >= 75:
        return {
            "action": "standard_buy",
            "position": min(max_single, 40000),
            "reason": "高分信号，标准仓位介入"
        }
    elif score >= 60:
        return {
            "action": "half_buy",
            "position": min(max_single * 0.5, 20000),
            "reason": "中等信号，半仓位介入"
        }
    else:
        return {
            "action": "watch",
            "position": 0,
            "reason": "评分不足，继续观望"
        }
