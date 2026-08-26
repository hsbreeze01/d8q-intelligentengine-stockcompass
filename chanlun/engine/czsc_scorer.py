# -*- coding: utf-8 -*-
"""czsc信号评分系统: 基于多维度加权评分，输出分级(⭐⭐⭐/⭐⭐/⭐)。

评分维度(满分100):
- 信号类型权重 (25分): buy1=25, buy2=20, buy3=15, sell类同理
- 环境分 (25分): 来自 market_state.env_score
- 周线方向 (20分): 周线顺势=20, 盘整=12, 逆势=0
- 背驰强度 (15分): 有背驰且ratio<0.7=15, ratio<0.85=10, 无=5
- 止损空间 (15分): <=5%=15, <=8%=10, <=10%=5, >10%=0
"""

# 信号类型基础分
TYPE_SCORE = {
    'buy1': 25, 'buy2': 20, 'buy3': 15,
    'sell1': 25, 'sell2': 20, 'sell3': 15,
}

def score_signal(sig: dict, env_score: int = 12) -> dict:
    """对单个信号评分，返回 {score, grade, grade_label, detail}"""
    # 1. 信号类型分 (max 25)
    type_s = TYPE_SCORE.get(sig.get('type', ''), 10)

    is_buy = sig.get('type', '').startswith('buy')

    # 2. 环境分 (max 25) - 按信号方向取值
    # B3-8: 旧实现买卖共用 env_score, 大盘看多时卖出信号也白拿满分(实测 sell2 白拿18分)。
    # 卖出信号在大盘强势时属逆势, 应反向计分。
    if is_buy:
        env_s = min(max(env_score, 0), 25)
    else:
        env_s = min(max(25 - env_score, 0), 25)

    # 3. 周线方向分 (max 20)
    weekly_allow = sig.get('weekly_allow', True)
    weekly_trend = sig.get('weekly_trend', '')
    if not weekly_allow:
        week_s = 0
    elif weekly_trend == 'up_trend' and is_buy:
        week_s = 20
    elif weekly_trend == 'down_trend' and not is_buy:
        week_s = 20
    elif weekly_trend == 'consolidation':
        week_s = 12
    else:
        week_s = 6

    # 4. 背驰强度分 (max 15)
    has_div = sig.get('divergence', False)
    div_ratio = sig.get('div_ratio', 1.0)
    if has_div and div_ratio < 0.7:
        div_s = 15
    elif has_div and div_ratio < 0.85:
        div_s = 10
    elif has_div:
        div_s = 7
    else:
        div_s = 5  # 无背驰给基础分

    # 5. 止损空间分 (max 15)
    # B1-4: 缺失时给 999 使其落入 0 分档(fail-safe)，
    # 旧默认 5.0 会让缺字段的信号白拿满分15。
    sl_pct = sig.get('stop_loss_pct')
    if sl_pct is None:
        sl_pct = 999.0
    if sl_pct <= 5:
        sl_s = 15
    elif sl_pct <= 8:
        sl_s = 10
    elif sl_pct <= 10:
        sl_s = 5
    else:
        sl_s = 0

    # 6. 题材共振加分 (max 10, 来自热点系统)
    resonance_bonus = sig.get('resonance_bonus', 0)

    # P2-1: 五个基础维度合计满分 100(type25+env25+week20+div15+sl15)。
    # 题材共振是额外加分, 若直接相加会使总分达 110, 而分级阈值 75/55 按 100 分制设定 ——
    # 等于共振把及格线变相拉低。故 clamp 到 100, 并保留 base_score 供追溯。
    base_score = type_s + env_s + week_s + div_s + sl_s
    total = min(100, base_score + resonance_bonus)

    # 分级: ⭐⭐⭐ >= 75, ⭐⭐ >= 55, ⭐ < 55 (共振加分不会突破100上限)
    if total >= 75:
        grade = 3
        grade_label = '⭐⭐⭐'
    elif total >= 55:
        grade = 2
        grade_label = '⭐⭐'
    else:
        grade = 1
        grade_label = '⭐'

    return {
        'score': total,
        'base_score': base_score,          # P2-1: 五维基础分(0~100), 不含共振
        'resonance_bonus': resonance_bonus,  # P2-1: 共振加分(已计入 score 且受100上限约束)
        'grade': grade,
        'grade_label': grade_label,
        'detail': {
            'type': type_s,
            'env': env_s,
            'weekly': week_s,
            'divergence': div_s,
            'stop_loss': sl_s,
            'resonance': resonance_bonus,
        }
    }
