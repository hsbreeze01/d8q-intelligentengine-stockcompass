# -*- coding: utf-8 -*-
"""三类买卖点(czsc路线): 基于笔+中枢+走势+背驰。"""
from typing import List, Dict
from ..czsc_core import BI, ZS, Direction
from .trend import classify_trends, TrendType, last_trend
from .czsc_divergence import last_divergence

# ===== B2: 价格语义与止损约束 =====
# 结构止损与执行价的最大距离。结构位过远时用该上限收紧, 避免出现 40%~69% 的不可用止损。
MAX_STOP_PCT = 0.08
# 信号生成阶段的硬门槛: 止损距离超过此值的信号直接丢弃(不再依赖前端筛选)
HARD_MAX_STOP_PCT = 0.15


def _exec_price(bi, closes):
    """信号确认K线的收盘价 = 用户次一交易日可执行的基准价。

    B2-1: 旧实现 buy1/buy2 用 bi.low(笔极值, 盘中瞬时价, 不可成交),
    buy3/sell3 用 closes[-1](最新收盘, 但与 dt 可能相差数日) —— 两种语义混存。
    统一改为取"该笔结束K线"的收盘价, 既可成交, 又与 dt 时间对齐。
    """
    if not closes:
        return 0.0
    try:
        idx = bi.raw_bars[-1].id
        if 0 <= idx < len(closes):
            return float(closes[idx])
    except Exception:
        pass
    return float(closes[-1])


def _ceil2(x):
    """向上取整到2位小数(用于买入止损, 使其靠近入场价而非远离)"""
    import math
    return math.ceil(float(x) * 100 - 1e-9) / 100.0


def _floor2(x):
    """向下取整到2位小数(用于卖出止损)"""
    import math
    return math.floor(float(x) * 100 + 1e-9) / 100.0


def _buy_stop(structural, exec_p):
    """买入止损: 取结构位与 exec*(1-MAX_STOP_PCT) 的较高者(收紧过远的结构止损)。

    取整方向向上(_ceil2): 保证 |stop-exec|/exec <= MAX_STOP_PCT 严格成立。
    若用 round() 会向下取整, 使距离略微越界(如 2.72*0.92=2.5024 -> 2.50 = 8.09%)。
    """
    if not exec_p or exec_p <= 0:
        return round(float(structural), 2)
    cap = exec_p * (1 - MAX_STOP_PCT)
    if float(structural) >= cap:
        # 结构位本身在上限内, 保留结构位(常规取整即可)
        return round(float(structural), 2)
    return _ceil2(cap)


def _sell_stop(structural, exec_p):
    """卖出止损: 取结构位与 exec*(1+MAX_STOP_PCT) 的较低者。

    取整方向向下(_floor2): 保证距离不越界。
    """
    if not exec_p or exec_p <= 0:
        return round(float(structural), 2)
    cap = exec_p * (1 + MAX_STOP_PCT)
    if float(structural) <= cap:
        return round(float(structural), 2)
    return _floor2(cap)


# B1-5: 二买回调幅度上限(占前一上涨段的比例)。与 detect_buy2 docstring(50%) 一致。
# 原内联注释误写 30%, 实际代码为 0.50; 此处常量化并订正注释, 行为不变。
PULLBACK_MAX_RATIO = 0.50
# 二买中枢关联: 回调低点不得高于最近中枢ZG的该倍数
PULLBACK_ZG_MULT = 1.5

# ===== P1: 三买(buy3)收紧参数 =====
# 突破笔起点相对线段中枢ZG的最大上浮。超出说明价格早已高悬于中枢之上,
# 该笔并非"离开中枢"的突破笔, 此时 high>ZG 条件无判别力。
BREAKOUT_START_TOL = 0.03
# 回踩低点相对 ZG 的最大上浮。三买要求回踩到中枢上沿附近确认支撑,
# 回踩离 ZG 太远只是高位小回调, 不构成三买。
PULLBACK_ZG_TOL = 0.05
# 形态新鲜度: 回踩笔必须落在最后 N 笔之内(避免命中旧形态)
SIGNAL_FRESH_BIS = 2
# 二买/二卖必须紧随最近的一买/一卖背驰结构。
SECOND_POINT_LOOKBACK_BIS = 12

# 调整3(2026-09-02): buy3 固定止盈目标价幅度。
# 数据分析(23个历史buy3): 平均MFE +4~5%(5-10日达峰), 风险~8%, 20日回吐达3.68%(31%大幅回吐);
# seg_zg 100%在入场价下方不能当目标。故用固定百分比目标, 取 6%(略高于MFE均值, 留余量),
# 配合 simulator A+ 方案: 达目标先减半仓、剩余靠结构止损跟踪(吃强势股后续)。
BUY3_TARGET_PCT = 0.06

# 调整(2026-09-04): buy1 目标中枢时效闸门(OR判定)。
# 下跌趋势一买时 zs_list[-1] 常是数月前高位旧中枢, 其 zg 远高于现价 -> 目标虚高 -> RR 架空
# (601012: 04-29 旧中枢 zg=19.33, 入场12.18, 目标涨幅59%, RR9.1, 实际5日仅+2.6%)。
# 任一命中即视为陈旧, 降级为 入场*(1+BUY1_TARGET_PCT) 固定目标, target_type=fixed_pct:
#   - 中枢结束距信号时点 > STALE_PIVOT_DAYS 日历天
#   - zg 相对可执行价涨幅 > MAX_PIVOT_ZG_GAIN
STALE_PIVOT_DAYS = 60
MAX_PIVOT_ZG_GAIN = 0.30
BUY1_TARGET_PCT = 0.09


def _preceding_divergence(bis, closes, direction):
    """校验二类买卖点之前的推动笔确实形成同向背驰。"""
    from .czsc_adapter import get_zs_seq

    preceding = bis[-(SECOND_POINT_LOOKBACK_BIS + 2):-2]
    if len(preceding) < 5:
        return False
    pivots = [zs for zs in get_zs_seq(preceding)
              if len(zs.bis) >= 3 and zs.is_valid]
    div = last_divergence(preceding, pivots, closes)
    return div['is_divergence'] and div['direction'] == direction

def detect_buy1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一买: 下跌背驰(趋势一买 + 盘整一买)"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Down:
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Down:
        return signals
    if div['kind'] == 'trend':
        reason = 'trend_bottom_divergence'
    elif div['kind'] == 'consolidation':
        # 盘整一买: 要求中枢内笔数>=5(盘整够充分)
        if not zs_list or len(zs_list[-1].bis) < 5:
            return signals
        reason = 'consolidation_bottom_divergence'
    else:
        return signals
    _exec = _exec_price(last_bi, closes)
    # 中枢时效闸门(OR): 旧中枢 zg 作目标会虚高 RR, 陈旧时降级为固定百分比目标
    _zs = zs_list[-1]
    _zg_gain = (_zs.zg / _exec - 1) if _exec and _exec > 0 else 0.0
    try:
        _stale_days = (last_bi.edt - _zs.edt).days
    except Exception:
        _stale_days = 0
    _pivot_stale = (_stale_days > STALE_PIVOT_DAYS) or (_zg_gain > MAX_PIVOT_ZG_GAIN)
    if _zs.zg > _exec and not _pivot_stale:
        _target_price, _target_type = round(_zs.zg, 2), 'pivot_zg'
    else:
        _target_price, _target_type = round(_exec * (1 + BUY1_TARGET_PCT), 2), 'fixed_pct'
    signals.append({'type': 'buy1',
                    'price': _exec,                      # B2-1: 可执行价
                    'exec_price': _exec,
                    'signal_ref_price': last_bi.low,     # 结构参考: 笔低点
                    'dt': str(last_bi.edt),
                    'stop_loss': _buy_stop(last_bi.low * 0.95, _exec),
                    'target_price': _target_price,
                    'target_type': _target_type,
                    'reason': reason, 'ratio': div['ratio']})
    return signals

def detect_buy2(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """二买: 一买后第一次回调不破前低（加严版）
    增加条件:
    1. 回调幅度不超过上涨段的50%（防止深度回调伪二买）
    2. 回调低点必须在最近中枢ZG附近或上方（中枢关联）
    """
    signals = []
    if len(bis) < 5:
        return signals
    b1, b2, b3 = bis[-3], bis[-2], bis[-1]
    if b1.direction != Direction.Down or b2.direction != Direction.Up or b3.direction != Direction.Down:
        return signals
    if b3.low > b1.low and b2.high > b1.high:
        if not _preceding_divergence(bis, closes, Direction.Down):
            return signals
        lt = last_trend(zs_list)
        if lt['type'] == TrendType.DOWN:
            return signals
        # P0-2a: 回调幅度限制 - 回调不超过上涨段(b2)的50% (见 PULLBACK_MAX_RATIO)
        up_range = b2.high - b1.low
        pullback = b2.high - b3.low
        if up_range > 0 and pullback / up_range > PULLBACK_MAX_RATIO:
            return signals
        # P0-2b: 中枢关联校验 - 回调低点不应远离最近中枢ZG（信号价不超ZG的50%以上）
        if zs_list:
            last_zg = zs_list[-1].zg
            if b3.low > last_zg * PULLBACK_ZG_MULT:
                return signals
        _exec = _exec_price(b3, closes)
        signals.append({'type': 'buy2',
                        'price': _exec,
                        'exec_price': _exec,
                        'signal_ref_price': b3.low,
                        'dt': str(b3.edt),
                        'stop_loss': _buy_stop(b3.low * 0.95, _exec),
                        'target_price': round(b2.high, 2),
                        'target_type': 'previous_high',
                        'reason': 'pullback_not_break_low'})
    return signals

def detect_buy3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三买: 离开线段中枢后回踩不破ZG（日线级别）

    宁可不出信号，也不出低质量三买。
    必须有线段中枢才产生三买，否则返回空。
    """
    from .segment_adapter import bis_to_segments, segment_pivots
    signals = []
    # 必须有线段中枢
    segs = bis_to_segments(bis)
    seg_zs = segment_pivots(segs)
    if not seg_zs:
        return signals
    last_seg = seg_zs[-1]
    seg_zg = last_seg['zg']
    seg_zd = last_seg['zd']
    # 寻找突破线段ZG后回踩不破的模式
    if len(bis) < 3:
        return signals
    if seg_zg is None or seg_zg <= 0:
        return signals
    for i in range(len(bis)-2, max(len(bis)-6, 0), -1):
        up_bi = bis[i]
        if up_bi.direction != Direction.Up or up_bi.high <= seg_zg:
            continue
        # P1-1 突破有效性: 突破笔起点须在 ZG 附近或之下, 说明这一笔确实在"离开中枢"。
        # 若起点已远高于 ZG, 则价格早已脱离该中枢, high>ZG 不具判别力。
        if up_bi.low > seg_zg * (1 + BREAKOUT_START_TOL):
            continue
        if i+1 < len(bis) and bis[i+1].direction == Direction.Down:
            pullback = bis[i+1]
            # P1-4 时间新鲜度: 回踩笔须落在最后 SIGNAL_FRESH_BIS 笔内
            if (len(bis) - 1 - (i + 1)) >= SIGNAL_FRESH_BIS:
                continue
            # P1-2 回踩须接近 ZG(回踩到中枢上沿附近确认支撑)
            if pullback.low > seg_zg * (1 + PULLBACK_ZG_TOL):
                continue
            # P1-3(已移除): 原拟加回踩不超过突破笔涨幅50%的限制, 但与 P1-2 逻辑冲突 ——
            # P1-1 已要求突破笔起点在 ZG 附近, P1-2 又要求回踩低点在 ZG 附近,
            # 二者同时成立时回踩幅度必然接近突破笔全幅, 该限制会误杀合规形态
            # (实测过 P1-2 的 34 个候选中有 31 个被它砍掉)。
            # 三买的本质约束是回踩位置(P1-2)而非回踩幅度(那是 buy2 缺少中枢参照时的替代判据)。
            if pullback.low > seg_zg:
                # B2-1: 用回踩笔结束K线的收盘价, 而非 closes[-1](可能相差数日)
                _exec = _exec_price(pullback, closes)
                signals.append({'type': 'buy3',
                                'price': _exec,
                                'exec_price': _exec,
                                'signal_ref_price': seg_zg,   # 结构参考: 线段中枢上沿
                                'dt': str(pullback.edt),
                                # B2-2: 结构止损(seg_zg*0.97)常远离现价, 用8%上限收紧
                                'stop_loss': _buy_stop(seg_zg * 0.97, _exec),
                                # 调整3 A+: 固定止盈目标 = 入场×(1+6%), 达标先减半仓、
                                # 剩余靠结构止损跟踪(见 simulator sell_decision partial_take)
                                'target_price': round(_exec * (1 + BUY3_TARGET_PCT), 2),
                                'target_type': 'partial_take',
                                'zg': seg_zg, 'zd': seg_zd,
                                'reason': 'segment_breakout_pullback_above_zg'})
                break
    return signals

def detect_sell1(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """一卖: 上涨背驰(趋势一卖 + 盘整一卖)"""
    signals = []
    div = last_divergence(bis, zs_list, closes)
    if not div['is_divergence']:
        return signals
    if div['direction'] != Direction.Up:
        return signals
    last_bi = bis[-1]
    if last_bi.direction != Direction.Up:
        return signals
    if div['kind'] == 'trend':
        reason = 'trend_top_divergence'
    elif div['kind'] == 'consolidation':
        if not zs_list or len(zs_list[-1].bis) < 5:
            return signals
        reason = 'consolidation_top_divergence'
    else:
        return signals
    _exec = _exec_price(last_bi, closes)
    signals.append({'type': 'sell1',
                    'price': _exec,
                    'exec_price': _exec,
                    'signal_ref_price': last_bi.high,    # 结构参考: 笔高点
                    'dt': str(last_bi.edt),
                    'stop_loss': _sell_stop(last_bi.high * 1.05, _exec),
                    'target_price': round(zs_list[-1].zd, 2),
                    'target_type': 'pivot_zd',
                    'reason': reason, 'ratio': div['ratio']})
    return signals

def detect_sell2(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """二卖: 一卖后第一次反弹不破前高(加严版, 与 detect_buy2 对称)

    B3-5 新增两道过滤(此前 sell2 仅有趋势过滤, 条件远松于 buy2,
    导致卖出信号泛滥 —— 实测占卖出信号 20/21):
    1. 反弹幅度不超过前一下跌段的 50%(防止深度反弹伪二卖)
    2. 反弹高点必须在最近中枢ZD附近或下方(中枢关联)
    """
    signals = []
    if len(bis) < 5:
        return signals
    b1, b2, b3 = bis[-3], bis[-2], bis[-1]
    if b1.direction != Direction.Up or b2.direction != Direction.Down or b3.direction != Direction.Up:
        return signals
    if b3.high < b1.high and b2.low < b1.low:
        if not _preceding_divergence(bis, closes, Direction.Up):
            return signals
        lt = last_trend(zs_list)
        if lt['type'] == TrendType.UP:
            return signals
        # B3-5a: 反弹幅度限制 — 镜像 buy2 的回调幅度限制
        down_range = b1.high - b2.low
        rebound_amp = b3.high - b2.low
        if down_range > 0 and rebound_amp / down_range > PULLBACK_MAX_RATIO:
            return signals
        # B3-5b: 中枢关联校验 — 反弹高点不应远低于最近中枢ZD
        if zs_list:
            last_zd = zs_list[-1].zd
            if last_zd > 0 and b3.high < last_zd / PULLBACK_ZG_MULT:
                return signals
        if True:
            _exec = _exec_price(b3, closes)
            signals.append({'type': 'sell2',
                            'price': _exec,
                            'exec_price': _exec,
                            'signal_ref_price': b3.high,
                            'dt': str(b3.edt),
                            'stop_loss': _sell_stop(b3.high * 1.05, _exec),
                            'target_price': round(b2.low, 2),
                            'target_type': 'previous_low',
                            'reason': 'rebound_not_break_high'})
    return signals

def detect_sell3(bis: List[BI], zs_list: List[ZS], closes: List[float]) -> List[Dict]:
    """三卖: 跌破中枢ZD后回抽不过ZD"""
    signals = []
    if not zs_list:
        return signals
    last_zs = zs_list[-1]
    after_bis = [b for b in bis if b.sdt >= last_zs.edt]
    if len(after_bis) < 2:
        return signals
    down_bi = after_bis[0]
    if down_bi.direction != Direction.Down or down_bi.low >= last_zs.zd:
        return signals
    rebound = after_bis[1] if len(after_bis) >= 2 else None
    if rebound is None or rebound.direction != Direction.Up:
        return signals
    # P1-5 时间新鲜度: 回抽笔须落在最后 SIGNAL_FRESH_BIS 笔内, 避免命中旧形态
    try:
        _r_pos = bis.index(rebound)
        if (len(bis) - 1 - _r_pos) >= SIGNAL_FRESH_BIS:
            return signals
    except ValueError:
        pass
    if rebound.high < last_zs.zd:
        _exec = _exec_price(rebound, closes)
        signals.append({'type': 'sell3',
                        'price': _exec,
                        'exec_price': _exec,
                        'signal_ref_price': last_zs.zd,   # 结构参考: 中枢下沿
                        'dt': str(rebound.edt),
                        # B2-3: 改用中枢ZD结构位(跌破ZD后回抽不过ZD, 站回ZD即失效),
                        # 与 buy3 的结构位止损对称; 旧实现为固定 price*1.05
                        'stop_loss': _sell_stop(last_zs.zd, _exec),
                        'target_price': None,
                        'target_type': 'invalidation_only',
                        'zg': last_zs.zg, 'zd': last_zs.zd,
                        'rebound_high': rebound.high,
                        'reason': 'breakdown_rebound_below_zd'})
    return signals

def detect_all_buys(bis, zs_list, closes):
    return detect_buy1(bis, zs_list, closes) + detect_buy2(bis, zs_list, closes) + detect_buy3(bis, zs_list, closes)

def detect_all_sells(bis, zs_list, closes):
    return detect_sell1(bis, zs_list, closes) + detect_sell2(bis, zs_list, closes) + detect_sell3(bis, zs_list, closes)
