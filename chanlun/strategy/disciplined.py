"""纪律化交易策略 — 用户配置驱动

基于原有缠论引擎（fractal/stroke/pivot/divergence/buy_sell），
新增策略执行层，与原有逻辑完全隔离。

核心设计：
- 用户投资配置（UserProfile）决定推送内容和操作建议
- 不同用户看到不同的仓位、止损、信号级别
- 所有策略参数从配置中读取，不硬编码

配置维度：
- 资金量 → 影响每笔金额
- 风险偏好(conservative/balanced/aggressive) → 影响止损宽度、信号过滤
- 操作频率(low/medium/high) → 影响信号阈值
- 持仓周期(short/medium) → 影响超时天数
"""
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2, detect_buy1
from chanlun.signals.scorer import score_signal
from chanlun.engine.types import PivotStatus, Direction, SignalType


# === 用户投资配置 ===
@dataclass
class UserProfile:
    """用户投资配置
    
    不同用户根据自身情况选择配置，系统据此生成个性化推送。
    """
    user_id: str
    name: str
    
    # 资金配置
    total_capital: int = 50000          # 总可用资金（元）
    max_position_pct: float = 0.20      # 单笔仓位上限(占总资金)
    max_holdings: int = 3               # 最多同时持有
    
    # 风险偏好: conservative / balanced / aggressive
    risk_preference: str = "balanced"
    
    # 操作频率: low(每周1-2次) / medium(每周3-5次) / high(每天)
    trade_frequency: str = "low"
    
    # 持仓周期: short(5-10天) / medium(10-20天)
    hold_period: str = "short"
    
    # 信号偏好: 接受哪些类型
    accept_buy1: bool = True            # 接受一买（高风险高回报）
    accept_buy2: bool = True            # 接受二买
    accept_buy3: bool = True            # 接受三买
    
    # 推送渠道
    push_channel: str = "wecom_webhook"  # wecom_webhook / email / none
    push_webhook_key: str = ""           # webhook key


# === 风险偏好映射的策略参数 ===
RISK_PARAMS = {
    "conservative": {
        "stop_loss_pct": 0.03,       # 止损3%（更紧）
        "trailing_trigger": 0.05,    # 5%盈利开始移动止盈
        "trailing_drawdown": 0.02,   # 回撤2%就止盈
        "min_score": 70,             # 只看高分信号
        "min_score_buy3": 75,        # 三买要更高分
        "position_scale": 0.7,       # 仓位缩减30%
    },
    "balanced": {
        "stop_loss_pct": 0.05,       # 止损5%
        "trailing_trigger": 0.08,    # 8%盈利开始移动止盈
        "trailing_drawdown": 0.03,   # 回撤3%止盈
        "min_score": 65,             # 标准分数线
        "min_score_buy3": 70,        # 三买70分
        "position_scale": 1.0,       # 标准仓位
    },
    "aggressive": {
        "stop_loss_pct": 0.07,       # 止损7%（更宽）
        "trailing_trigger": 0.12,    # 12%盈利才止盈
        "trailing_drawdown": 0.05,   # 容忍5%回撤
        "min_score": 60,             # 接受更多信号
        "min_score_buy3": 65,        # 三买门槛低
        "position_scale": 1.2,       # 仓位放大20%
    },
}

HOLD_PERIOD_DAYS = {
    "short": 10,
    "medium": 20,
}

COST_RATE = 0.002  # 单边成本


# === 信号级别 ===
class SignalGrade:
    HIGH = "high"       # ⭐⭐⭐ 高确信
    MEDIUM = "medium"   # ⭐⭐ 中确信
    WATCH = "watch"     # ⭐ 观察（不推送操作）


@dataclass
class DisciplinedSignal:
    """纪律化信号（含个性化操作指令）"""
    stock_code: str
    stock_name: str
    signal_type: str        # buy1/buy2/buy3
    grade: str              # high/medium/watch
    score: int
    morphology_score: int
    dynamics_score: int
    environment_score: int
    signal_price: float     # 信号触发价
    stop_loss: float        # 止损价
    suggested_entry: float  # 建议入场价
    position_amount: int    # 建议金额（元）
    position_shares: int    # 建议股数（手的整数倍×100）
    valid_range: Tuple[float, float] = (0, 0)  # 有效入场区间
    reason_chain: List[str] = field(default_factory=list)
    volume_ratio: float = 1.0
    max_hold_days: int = 10
    trailing_trigger_pct: float = 8.0
    trailing_drawdown_pct: float = 3.0


@dataclass
class HoldingStatus:
    """持仓状态"""
    stock_code: str
    stock_name: str
    entry_date: str
    entry_price: float
    position_amount: int
    shares: int
    current_price: float = 0.0
    highest_close: float = 0.0
    hold_days: int = 0
    pnl_pct: float = 0.0
    pnl_amount: float = 0.0
    trailing_active: bool = False
    exit_signal: str = ""
    exit_reason: str = ""


def get_strategy_params(profile: UserProfile) -> dict:
    """根据用户配置生成策略参数"""
    risk = RISK_PARAMS.get(profile.risk_preference, RISK_PARAMS["balanced"])
    max_days = HOLD_PERIOD_DAYS.get(profile.hold_period, 10)
    
    base_position = profile.total_capital * profile.max_position_pct
    position_amount = int(base_position * risk["position_scale"])
    half_position = int(position_amount * 0.5)
    
    return {
        "stop_loss_pct": risk["stop_loss_pct"],
        "trailing_trigger": risk["trailing_trigger"],
        "trailing_drawdown": risk["trailing_drawdown"],
        "min_score": risk["min_score"],
        "min_score_buy3": risk["min_score_buy3"],
        "max_hold_days": max_days,
        "full_position": position_amount,
        "half_position": half_position,
        "max_holdings": profile.max_holdings,
    }


def grade_signal(signal_type: str, score: int, volume_ratio: float,
                 params: dict, profile: UserProfile) -> str:
    """信号分级（基于用户配置）"""
    # 用户不接受的信号类型直接排除
    if signal_type == "buy1" and not profile.accept_buy1:
        return SignalGrade.WATCH
    if signal_type == "buy2" and not profile.accept_buy2:
        return SignalGrade.WATCH
    if signal_type == "buy3" and not profile.accept_buy3:
        return SignalGrade.WATCH
    
    min_score = params["min_score"]
    min_score_buy3 = params["min_score_buy3"]
    
    if signal_type in ("buy1", "buy2") and score >= min_score:
        return SignalGrade.HIGH
    if signal_type == "buy3" and score >= min_score_buy3:
        return SignalGrade.MEDIUM
    return SignalGrade.WATCH


def analyze_stock(klines: list, stock_code: str, profile: UserProfile,
                  stock_name: str = "") -> Optional[DisciplinedSignal]:
    """分析单只股票，根据用户配置返回个性化信号

    Args:
        klines: K线数据
        stock_code: 股票代码
        profile: 用户投资配置
        stock_name: 股票名称
    """
    if len(klines) < 60:
        return None

    params = get_strategy_params(profile)

    try:
        merged, fractals = identify_fractals(klines)
        strokes = build_strokes(fractals)
        pivots = find_pivots(strokes)

        if not strokes or not pivots:
            return None

        closes = [k["close"] for k in klines]
        dif, dea, macd_bar = compute_macd(closes)
        current_price = klines[-1]["close"]
        divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)

        # 量比
        vol_window = [k["volume"] for k in klines[-20:]]
        vol_avg = sum(vol_window) / len(vol_window) if vol_window else 1
        vol_ratio = klines[-1]["volume"] / vol_avg if vol_avg > 0 else 1.0
        macd_dif_val = dif[-1] if dif else 0.0

        # 检测买点
        signal = None
        pivot_used = None

        sig1 = detect_buy1(strokes, pivots, divergence, dif)
        if sig1:
            signal = sig1
            pivot_used = pivots[-1] if pivots else None

        if not signal:
            sig2 = detect_buy2(strokes, pivots, divergence)
            if sig2:
                signal = sig2
                pivot_used = pivots[-1] if pivots else None

        if not signal:
            sig3 = detect_buy3(strokes, pivots, current_price)
            if sig3:
                signal = sig3
                completed = [p for p in pivots if p.status == PivotStatus.COMPLETED]
                pivot_used = completed[-1] if completed else None

        if not signal:
            return None

        # 评分
        scored = score_signal(
            signal, pivot=pivot_used, divergence=divergence,
            volume_ratio=vol_ratio, macd_dif=macd_dif_val,
            market_bullish=False, sector_strong=False, capital_inflow=False
        )

        # 分级
        grade = grade_signal(scored.type.value, scored.score, vol_ratio, params, profile)
        if grade == SignalGrade.WATCH:
            return None

        # 计算止损
        stop_loss_pct = params["stop_loss_pct"]
        stop_loss = round(current_price * (1 - stop_loss_pct), 2)

        # 计算仓位
        if grade == SignalGrade.HIGH:
            position_amount = params["full_position"]
        else:
            position_amount = params["half_position"]

        # 计算股数（100股整数倍）
        shares = int(position_amount / current_price / 100) * 100
        if shares < 100:
            shares = 100
        actual_amount = int(shares * current_price)

        # 有效入场区间
        valid_range = (round(current_price * 0.95, 2), round(current_price * 1.05, 2))

        return DisciplinedSignal(
            stock_code=stock_code,
            stock_name=stock_name or stock_code,
            signal_type=scored.type.value,
            grade=grade,
            score=scored.score,
            morphology_score=scored.morphology_score,
            dynamics_score=scored.dynamics_score,
            environment_score=scored.environment_score,
            signal_price=round(current_price, 2),
            stop_loss=stop_loss,
            suggested_entry=round(current_price, 2),
            position_amount=actual_amount,
            position_shares=shares,
            valid_range=valid_range,
            reason_chain=scored.reason_chain or [],
            volume_ratio=round(vol_ratio, 2),
            max_hold_days=params["max_hold_days"],
            trailing_trigger_pct=params["trailing_trigger"] * 100,
            trailing_drawdown_pct=params["trailing_drawdown"] * 100,
        )

    except Exception:
        return None


def check_exit(holding: HoldingStatus, today_close: float,
               profile: UserProfile) -> HoldingStatus:
    """每日收盘后检查出场条件（基于用户配置）"""
    params = get_strategy_params(profile)
    h = holding
    h.current_price = today_close
    h.hold_days += 1
    h.pnl_pct = round((today_close - h.entry_price) / h.entry_price * 100, 2)
    h.pnl_amount = round(h.shares * (today_close - h.entry_price), 2)

    if today_close > h.highest_close:
        h.highest_close = today_close

    # 移动止盈是否激活
    if h.pnl_pct >= params["trailing_trigger"] * 100:
        h.trailing_active = True

    # 规则A: 止损
    stop_price = h.entry_price * (1 - params["stop_loss_pct"])
    if today_close <= stop_price:
        h.exit_signal = "stop_loss"
        h.exit_reason = "收盘价%.2f跌破止损%.2f（-%d%%）" % (
            today_close, stop_price, params["stop_loss_pct"] * 100)
        return h

    # 规则B: 移动止盈
    if h.trailing_active:
        drawdown = (h.highest_close - today_close) / h.highest_close
        if drawdown >= params["trailing_drawdown"]:
            h.exit_signal = "trailing"
            h.exit_reason = "盈利后回撤%.1f%%（高点%.2f→%.2f）" % (
                drawdown * 100, h.highest_close, today_close)
            return h

    # 规则C: 超时
    if h.hold_days >= params["max_hold_days"]:
        h.exit_signal = "timeout"
        h.exit_reason = "持仓满%d天" % params["max_hold_days"]
        return h

    return h


# === 推送内容格式化 ===
def format_signal_push(signal: DisciplinedSignal, profile: UserProfile) -> str:
    """格式化信号推送消息（Markdown）"""
    type_map = {"buy1": "一买", "buy2": "二买", "buy3": "三买"}
    grade_icon = {"high": "🔴 高确信", "medium": "🟡 中确信"}
    
    params = get_strategy_params(profile)
    
    lines = [
        "## %s | %s | %s" % (grade_icon.get(signal.grade, ""), type_map.get(signal.signal_type, ""), signal.stock_code),
        "",
        "**入场**: 明日开盘(9:30) 市价买入",
        "**仓位**: %d股 ≈ %d元（总资金%d的%d%%）" % (
            signal.position_shares, signal.position_amount,
            profile.total_capital, int(signal.position_amount / profile.total_capital * 100)),
        "**止损**: 收盘跌破<font color=\"warning\">%.2f</font>即次日卖出（-%.0f%%）" % (
            signal.stop_loss, params["stop_loss_pct"] * 100),
        "**止盈**: 盈利%.0f%%后回撤%.0f%%离场" % (
            params["trailing_trigger"] * 100, params["trailing_drawdown"] * 100),
        "**超时**: 持仓满%d天无条件卖出" % params["max_hold_days"],
        "",
        "> 评分%d | 信号价%.2f | 量比%.1f" % (signal.score, signal.signal_price, signal.volume_ratio),
        "> 有效区间: %.2f ~ %.2f" % signal.valid_range,
        "",
        "**推理**:",
    ]
    for r in signal.reason_chain[:4]:
        lines.append("• " + r)
    
    return "\n".join(lines)


def format_holding_check(holdings: List[HoldingStatus], profile: UserProfile) -> str:
    """格式化每日持仓检查推送"""
    if not holdings:
        return "📊 持仓检查：当前无持仓"
    
    params = get_strategy_params(profile)
    lines = ["## 📊 持仓检查（收盘）", ""]
    
    total_pnl = 0
    for h in holdings:
        total_pnl += h.pnl_amount
        status_icon = "🟢" if h.pnl_pct > 0 else "🔴"
        
        lines.append("**%s** %s | 第%d天 | %s%.1f%% (%.0f元)" % (
            h.stock_code, h.stock_name, h.hold_days,
            "+" if h.pnl_pct > 0 else "", h.pnl_pct, h.pnl_amount))
        
        if h.exit_signal:
            lines.append("> ⚠️ **明日开盘卖出** — %s" % h.exit_reason)
        elif h.trailing_active:
            drawdown = (h.highest_close - h.current_price) / h.highest_close * 100
            lines.append("> 🔒 移动止盈已激活（高点%.2f, 当前回撤%.1f%%/%.0f%%）" % (
                h.highest_close, drawdown, params["trailing_drawdown"] * 100))
        elif h.hold_days >= params["max_hold_days"] - 2:
            lines.append("> ⏰ 即将超时（还剩%d天）" % (params["max_hold_days"] - h.hold_days))
        else:
            lines.append("> 继续持有")
        lines.append("")
    
    lines.append("---")
    lines.append("总盈亏: %s%.0f元" % ("+" if total_pnl >= 0 else "", total_pnl))
    
    return "\n".join(lines)


# === 回测用函数 ===
def simulate_trade_disciplined(klines: list, entry_idx: int, entry_price: float,
                                profile: UserProfile) -> dict:
    """用新版规则模拟一笔交易"""
    params = get_strategy_params(profile)
    stop_loss_price = entry_price * (1 - params["stop_loss_pct"])
    highest_close = entry_price
    trailing_active = False
    max_hold = params["max_hold_days"]

    for j in range(1, max_hold + 1):
        day_idx = entry_idx + j
        if day_idx >= len(klines):
            break

        day = klines[day_idx]
        day_close = day["close"]

        if day_close > highest_close:
            highest_close = day_close

        pnl = (day_close - entry_price) / entry_price
        if pnl >= params["trailing_trigger"]:
            trailing_active = True

        # 规则A: 止损
        if day_close <= stop_loss_price:
            pnl_pct = (day_close - entry_price) / entry_price * 100 - COST_RATE * 2 * 100
            return {"exit_price": day_close, "exit_date": day["dt"],
                    "exit_reason": "stop_loss", "pnl_pct": round(pnl_pct, 2),
                    "hold_days": j, "highest": highest_close}

        # 规则B: 移动止盈
        if trailing_active:
            drawdown = (highest_close - day_close) / highest_close
            if drawdown >= params["trailing_drawdown"]:
                pnl_pct = (day_close - entry_price) / entry_price * 100 - COST_RATE * 2 * 100
                return {"exit_price": day_close, "exit_date": day["dt"],
                        "exit_reason": "trailing", "pnl_pct": round(pnl_pct, 2),
                        "hold_days": j, "highest": highest_close}

    # 规则C: 超时
    last_idx = min(entry_idx + max_hold, len(klines) - 1)
    exit_price = klines[last_idx]["close"]
    pnl_pct = (exit_price - entry_price) / entry_price * 100 - COST_RATE * 2 * 100
    return {"exit_price": exit_price, "exit_date": klines[last_idx]["dt"],
            "exit_reason": "timeout", "pnl_pct": round(pnl_pct, 2),
            "hold_days": max_hold, "highest": highest_close}


# === 默认用户配置（你的配置）===
DEFAULT_PROFILE = UserProfile(
    user_id="lancer",
    name="Lancer",
    total_capital=50000,
    max_position_pct=0.20,
    max_holdings=3,
    risk_preference="balanced",
    trade_frequency="low",
    hold_period="short",
    accept_buy1=True,
    accept_buy2=True,
    accept_buy3=False,
    push_channel="wecom_webhook",
    push_webhook_key="7c097c2e-d664-46e4-bbdc-39ff5bc1b537",
)
