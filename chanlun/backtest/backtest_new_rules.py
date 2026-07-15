"""新版纪律化规则回测 — 对比原始规则

对比：
- 旧规则: 止损=ZG下3%, 目标=等距投影, 超时=20天
- 新规则: 止损=信号价-5%, 移动止盈(8%触发/3%回撤), 超时=10天

同一批信号，只改出场规则，直接对比效果。
"""
import sys
import os
import json
import time
import logging

sys.path.insert(0, "/home/ecs-assist-user/d8q-intelligentengine-stockcompass")

import pymysql
from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2, detect_buy1
from chanlun.signals.scorer import score_signal
from chanlun.engine.types import PivotStatus, Direction, SignalType
from chanlun.strategy.disciplined import (
    simulate_trade_disciplined, UserProfile, DEFAULT_PROFILE,
    RISK_PARAMS, HOLD_PERIOD_DAYS, COST_RATE
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bt_new_rules")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "password", "database": "stock_analysis_system",
    "charset": "utf8mb4"
}
LOOKBACK = 120


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_stock_pool(conn, limit=50):
    sql = """SELECT stock_code, AVG(turnover) as avg_turnover
             FROM stock_data_daily WHERE date >= '2024-06-01'
             GROUP BY stock_code HAVING AVG(turnover) >= 300000000
             ORDER BY avg_turnover DESC LIMIT %s"""
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    valid_prefix = ("000", "001", "002", "003", "300", "600", "601", "603", "605")
    return [r["stock_code"] for r in rows if r["stock_code"][:3] in valid_prefix]


def get_all_klines(conn, stock_code):
    sql = "SELECT date as dt, open, high, low, close, volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date"
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        rows = cur.fetchall()
    return [{"dt": str(r["dt"]), "open": float(r["open"]), "high": float(r["high"]),
             "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]


def generate_signals(klines, stock_code):
    """生成全部信号（不做评分过滤，为了公平对比出场规则）"""
    signals = []
    i = LOOKBACK
    while i < len(klines) - 25:
        window = klines[max(0, i - LOOKBACK):i + 1]
        if len(window) < 50:
            i += 1
            continue
        try:
            merged, fractals = identify_fractals(window)
            strokes = build_strokes(fractals)
            pivots = find_pivots(strokes)
            if not strokes or not pivots:
                i += 1
                continue
            closes = [k["close"] for k in window]
            dif, dea, macd_bar = compute_macd(closes)
            current_price = window[-1]["close"]
            divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)

            signal = None
            pivot_used = None
            sig1 = detect_buy1(strokes, pivots, divergence, dif)
            if sig1:
                signal = sig1
                pivot_used = pivots[-1]
            if not signal:
                sig2 = detect_buy2(strokes, pivots, divergence)
                if sig2:
                    signal = sig2
                    pivot_used = pivots[-1]
            if not signal:
                sig3 = detect_buy3(strokes, pivots, current_price)
                if sig3:
                    signal = sig3
                    completed = [p for p in pivots if p.status == PivotStatus.COMPLETED]
                    pivot_used = completed[-1] if completed else None

            if signal:
                # 评分
                vol_window = [k["volume"] for k in window[-20:]]
                vol_avg = sum(vol_window) / len(vol_window) if vol_window else 1
                vol_ratio = window[-1]["volume"] / vol_avg if vol_avg > 0 else 1.0
                scored = score_signal(signal, pivot=pivot_used, divergence=divergence,
                                      volume_ratio=vol_ratio, macd_dif=dif[-1] if dif else 0,
                                      market_bullish=False, sector_strong=False, capital_inflow=False)

                entry_price = klines[i + 1]["open"] if i + 1 < len(klines) else current_price
                signals.append({
                    "idx": i + 1,  # 入场日idx
                    "stock_code": stock_code,
                    "signal_type": signal.type.value,
                    "score": scored.score,
                    "entry_price": entry_price,
                    "signal_price": current_price,
                    "stop_loss_original": signal.stop_loss,
                    "target_original": signal.target,
                })
                i += 12  # 跳过
                continue
        except Exception:
            pass
        i += 1
    return signals


def simulate_old_rules(klines, sig):
    """旧规则模拟: 止损=原始结构止损, 目标=原始目标, 超时=20天"""
    entry_idx = sig["idx"]
    entry_price = sig["entry_price"]
    stop_loss = sig["stop_loss_original"]
    target = sig["target_original"]

    for j in range(1, 21):
        day_idx = entry_idx + j
        if day_idx >= len(klines):
            break
        day = klines[day_idx]
        if day["low"] <= stop_loss:
            pnl = (stop_loss - entry_price) / entry_price * 100 - 0.4
            return {"pnl_pct": round(pnl, 2), "exit_reason": "stop_loss", "hold_days": j}
        if day["high"] >= target:
            pnl = (target - entry_price) / entry_price * 100 - 0.4
            return {"pnl_pct": round(pnl, 2), "exit_reason": "target", "hold_days": j}

    last_idx = min(entry_idx + 20, len(klines) - 1)
    exit_p = klines[last_idx]["close"]
    pnl = (exit_p - entry_price) / entry_price * 100 - 0.4
    return {"pnl_pct": round(pnl, 2), "exit_reason": "timeout", "hold_days": 20}


def simulate_new_rules(klines, sig, profile):
    """新规则模拟: 止损=信号价-5%, 移动止盈, 超时=10天"""
    return simulate_trade_disciplined(klines, sig["idx"], sig["entry_price"], profile)


def calc_stats(results):
    if not results:
        return {"n": 0}
    n = len(results)
    wins = [r for r in results if r["pnl_pct"] > 0]
    losses = [r for r in results if r["pnl_pct"] <= 0]
    win_rate = len(wins) / n * 100
    avg_win = sum(r["pnl_pct"] for r in wins) / len(wins) if wins else 0
    avg_loss = sum(abs(r["pnl_pct"]) for r in losses) / len(losses) if losses else 0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    expectancy = win_rate / 100 * avg_win - (1 - win_rate / 100) * avg_loss
    total_pnl = sum(r["pnl_pct"] for r in results)
    avg_hold = sum(r["hold_days"] for r in results) / n
    
    # 最大回撤
    equity = [1.0]
    for r in results:
        equity.append(equity[-1] * (1 + r["pnl_pct"] / 100))
    peak = 1.0
    max_dd = 0
    for e in equity:
        peak = max(peak, e)
        dd = (peak - e) / peak * 100
        max_dd = max(max_dd, dd)

    by_reason = {}
    for r in results:
        by_reason[r["exit_reason"]] = by_reason.get(r["exit_reason"], 0) + 1

    return {
        "n": n, "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "pl_ratio": round(pl_ratio, 2), "expectancy": round(expectancy, 2),
        "total_pnl": round(total_pnl, 1), "max_dd": round(max_dd, 1),
        "avg_hold": round(avg_hold, 1), "by_reason": by_reason,
    }


def main():
    t0 = time.time()
    conn = get_db()
    stock_codes = get_stock_pool(conn, limit=50)
    log.info("标的池: %d只", len(stock_codes))

    all_signals = []
    for i, code in enumerate(stock_codes):
        klines = get_all_klines(conn, code)
        if len(klines) < LOOKBACK + 25:
            continue
        sigs = generate_signals(klines, code)
        for s in sigs:
            all_signals.append((s, klines))
        if (i + 1) % 10 == 0:
            log.info("  %d/%d, signals=%d", i + 1, len(stock_codes), len(all_signals))

    log.info("信号总计: %d, 耗时%.0fs", len(all_signals), time.time() - t0)

    # 对比三种配置
    profiles = [
        ("conservative", UserProfile(user_id="c", name="保守", total_capital=50000,
                                     risk_preference="conservative", hold_period="short")),
        ("balanced", DEFAULT_PROFILE),
        ("aggressive", UserProfile(user_id="a", name="激进", total_capital=50000,
                                   risk_preference="aggressive", hold_period="short")),
    ]

    # 旧规则
    old_results = [simulate_old_rules(kl, s) for s, kl in all_signals]
    old_stats = calc_stats(old_results)

    # 新规则（三种风险偏好）
    new_results_by_profile = {}
    for pname, profile in profiles:
        new_results = [simulate_new_rules(kl, s, profile) for s, kl in all_signals]
        new_results_by_profile[pname] = calc_stats(new_results)

    # 按信号类型分组（新balanced规则）
    buy12_signals = [(s, kl) for s, kl in all_signals if s["signal_type"] in ("buy1", "buy2")]
    buy3_signals = [(s, kl) for s, kl in all_signals if s["signal_type"] == "buy3"]
    buy12_new = [simulate_new_rules(kl, s, DEFAULT_PROFILE) for s, kl in buy12_signals]
    buy3_new = [simulate_new_rules(kl, s, DEFAULT_PROFILE) for s, kl in buy3_signals]

    # 高分过滤（balanced, score>=70）
    high_score = [(s, kl) for s, kl in all_signals if s["score"] >= 70]
    high_score_new = [simulate_new_rules(kl, s, DEFAULT_PROFILE) for s, kl in high_score]

    conn.close()

    # 输出报告
    print("\n" + "=" * 90)
    print("缠论策略出场规则对比回测")
    print("=" * 90)
    print("期间: 2024-07 ~ 2026-06 | 标的: %d只 | 信号: %d笔" % (len(stock_codes), len(all_signals)))
    print("旧规则: 止损=结构位, 目标=等距投影, 超时=20天")
    print("新规则: 止损=信号价-N%, 移动止盈, 超时=10天")
    print("-" * 90)
    
    header = "%s %5s %6s %7s %7s %6s %7s %8s %7s %6s  %s"
    print(header % ("组别", "笔数", "胜率", "均盈%", "均亏%", "盈亏比", "期望值", "累计%", "最大DD", "均持天", "出场分布"))
    print("-" * 90)

    def print_row(name, s):
        reasons = s.get("by_reason", {})
        reason_str = "止%d 盈%d 超%d" % (reasons.get("stop_loss", 0), reasons.get("target", 0) + reasons.get("trailing", 0), reasons.get("timeout", 0))
        print("%-14s %5d %5.1f%% %6.2f %6.2f %6.2f %6.2f %7.1f %6.1f %5.1f  %s" % (
            name, s["n"], s["win_rate"], s["avg_win"], s["avg_loss"],
            s["pl_ratio"], s["expectancy"], s["total_pnl"], s["max_dd"], s["avg_hold"], reason_str))

    print_row("旧规则(基准)", old_stats)
    print("-" * 90)
    for pname, stats in new_results_by_profile.items():
        label = {"conservative": "新-保守", "balanced": "新-均衡", "aggressive": "新-激进"}[pname]
        print_row(label, stats)
    print("-" * 90)
    print_row("新均衡-一买二买", calc_stats(buy12_new))
    print_row("新均衡-三买", calc_stats(buy3_new))
    print_row("新均衡-评分≥70", calc_stats(high_score_new))
    print("=" * 90)

    # 保存JSON
    output = {
        "meta": {"run_time": time.strftime("%Y-%m-%d %H:%M"), "signals": len(all_signals),
                 "stocks": len(stock_codes)},
        "old_rules": old_stats,
        "new_conservative": new_results_by_profile["conservative"],
        "new_balanced": new_results_by_profile["balanced"],
        "new_aggressive": new_results_by_profile["aggressive"],
        "new_balanced_buy12": calc_stats(buy12_new),
        "new_balanced_buy3": calc_stats(buy3_new),
        "new_balanced_score70": calc_stats(high_score_new),
    }
    out_path = "/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/backtest/new_rules_result.json"
    with open(out_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("结果已保存: %s", out_path)


if __name__ == "__main__":
    main()
