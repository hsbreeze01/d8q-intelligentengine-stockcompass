"""缠论策略严格对照回测

目标：验证评分过滤是否提升胜率和盈亏比
方法：相同标的池、相同时间段，唯一变量是评分阈值

入场规则：信号日次日开盘买入
出场规则（优先级）：
  1. 盘中触及止损价 → 以止损价成交
  2. 盘中触及目标价 → 以目标价成交
  3. 持仓满20天 → 以第20天收盘价成交
成本：双边0.2%（佣金+印花税+滑点）

对照组：
  A. 全部信号（无评分过滤）
  B. 评分≥65
  C. 评分≥70
  D. 评分≥75
  E. 仅三买信号（无评分过滤）
  F. 三买 + 评分≥70
  G. 一买+二买（无评分过滤）

作者：D8Q Backtest Engine
日期：2026-07-15
"""
import sys
import os
import json
import math
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

sys.path.insert(0, "/home/ecs-assist-user/d8q-intelligentengine-stockcompass")

import pymysql
from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2, detect_buy1
from chanlun.signals.scorer import score_signal
from chanlun.engine.types import PivotStatus, Direction, SignalType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backtest_controlled")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "password", "database": "stock_analysis_system",
    "charset": "utf8mb4"
}

MAX_HOLD_DAYS = 20
COST_RATE = 0.002  # 单边0.1%佣金 + 0.05%印花(卖) + 0.05%滑点 ≈ 双边0.2%
LOOKBACK = 120


@dataclass
class Trade:
    stock_code: str
    signal_type: str
    signal_score: int
    morphology_score: int
    dynamics_score: int
    environment_score: int
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    pnl_pct: float = 0.0
    hold_days: int = 0
    exit_reason: str = ""


@dataclass
class GroupResult:
    name: str
    filter_desc: str
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_loss_ratio: float = 0.0
    total_pnl_pct: float = 0.0
    max_drawdown: float = 0.0
    avg_hold_days: float = 0.0
    exit_by_stop: int = 0
    exit_by_target: int = 0
    exit_by_timeout: int = 0
    expectancy: float = 0.0  # 期望值 = win_rate*avg_win - loss_rate*avg_loss


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_stock_pool(conn, min_avg_turnover=3e8, limit=50):
    """获取回测标的池：成交额前N、排除ST/退市"""
    sql = """SELECT stock_code, AVG(turnover) as avg_turnover
             FROM stock_data_daily 
             WHERE date >= '2024-06-01'
             GROUP BY stock_code 
             HAVING AVG(turnover) >= %s
             ORDER BY avg_turnover DESC 
             LIMIT %s"""
    with conn.cursor() as cur:
        cur.execute(sql, (min_avg_turnover, limit))
        rows = cur.fetchall()
    # 过滤有效A股代码
    valid_prefix = ("000", "001", "002", "003", "300", "600", "601", "603", "605")
    codes = [r["stock_code"] for r in rows if r["stock_code"][:3] in valid_prefix]
    return codes


def get_all_klines(conn, stock_code):
    sql = "SELECT date as dt, open, high, low, close, volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date"
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        rows = cur.fetchall()
    return [{"dt": str(r["dt"]), "open": float(r["open"]), "high": float(r["high"]),
             "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]


def generate_all_signals(klines, stock_code):
    """对一只股票生成全部信号（带评分），返回(idx, trade_info)列表"""
    signals_with_score = []
    i = LOOKBACK

    while i < len(klines) - MAX_HOLD_DAYS - 1:
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

            # 计算volume ratio
            vol_window = [k["volume"] for k in window[-20:]]
            vol_avg = sum(vol_window) / len(vol_window) if vol_window else 1
            vol_ratio = window[-1]["volume"] / vol_avg if vol_avg > 0 else 1.0
            macd_dif_val = dif[-1] if dif else 0.0

            # 检测所有买点
            signal = None
            pivot_used = None

            # 三买
            sig3 = detect_buy3(strokes, pivots, current_price)
            if sig3:
                signal = sig3
                completed = [p for p in pivots if p.status == PivotStatus.COMPLETED]
                pivot_used = completed[-1] if completed else None

            # 一买
            if not signal:
                sig1 = detect_buy1(strokes, pivots, divergence, dif)
                if sig1:
                    signal = sig1
                    pivot_used = pivots[-1] if pivots else None

            # 二买
            if not signal:
                sig2 = detect_buy2(strokes, pivots, divergence)
                if sig2:
                    signal = sig2
                    pivot_used = pivots[-1] if pivots else None

            if signal:
                # 评分（环境分不用真实数据，统一设为False避免偏差）
                scored = score_signal(
                    signal, pivot=pivot_used, divergence=divergence,
                    volume_ratio=vol_ratio, macd_dif=macd_dif_val,
                    market_bullish=False, sector_strong=False, capital_inflow=False
                )

                # 记录信号
                entry_price = klines[i + 1]["open"]  # 次日开盘买入
                entry_date = klines[i + 1]["dt"]

                signals_with_score.append({
                    "idx": i,
                    "stock_code": stock_code,
                    "signal_type": signal.type.value,
                    "score": scored.score,
                    "morphology_score": scored.morphology_score,
                    "dynamics_score": scored.dynamics_score,
                    "environment_score": scored.environment_score,
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "stop_loss": signal.stop_loss,
                    "target": signal.target,
                })

                # 跳过持仓期避免重复信号
                i += MAX_HOLD_DAYS + 2
                continue

        except Exception as e:
            pass

        i += 1

    return signals_with_score


def simulate_trade(klines, sig_info) -> Trade:
    """模拟单笔交易"""
    idx = sig_info["idx"]
    entry_price = sig_info["entry_price"]
    stop_loss = sig_info["stop_loss"]
    target = sig_info["target"]

    exit_price = entry_price
    exit_date = sig_info["entry_date"]
    exit_reason = "timeout"
    hold_days = 0

    for j in range(1, MAX_HOLD_DAYS + 1):
        day_idx = idx + 1 + j
        if day_idx >= len(klines):
            break

        day = klines[day_idx]
        hold_days = j

        # 止损检查（优先）
        if day["low"] <= stop_loss:
            exit_price = stop_loss
            exit_date = day["dt"]
            exit_reason = "stop_loss"
            break

        # 目标检查
        if day["high"] >= target:
            exit_price = target
            exit_date = day["dt"]
            exit_reason = "target"
            break

        exit_price = day["close"]
        exit_date = day["dt"]

    pnl_pct = (exit_price - entry_price) / entry_price * 100 - COST_RATE * 2 * 100

    return Trade(
        stock_code=sig_info["stock_code"],
        signal_type=sig_info["signal_type"],
        signal_score=sig_info["score"],
        morphology_score=sig_info["morphology_score"],
        dynamics_score=sig_info["dynamics_score"],
        environment_score=sig_info["environment_score"],
        entry_date=sig_info["entry_date"],
        entry_price=round(entry_price, 3),
        exit_date=exit_date,
        exit_price=round(exit_price, 3),
        stop_loss=round(stop_loss, 3),
        target=round(target, 3),
        pnl_pct=round(pnl_pct, 2),
        hold_days=hold_days,
        exit_reason=exit_reason,
    )


def calc_group_result(trades: List[Trade], name: str, filter_desc: str) -> GroupResult:
    """计算一组交易的统计指标"""
    r = GroupResult(name=name, filter_desc=filter_desc)
    if not trades:
        return r

    r.total_trades = len(trades)
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]

    r.win_count = len(wins)
    r.loss_count = len(losses)
    r.win_rate = len(wins) / len(trades) * 100

    r.avg_win_pct = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
    r.avg_loss_pct = sum(abs(t.pnl_pct) for t in losses) / len(losses) if losses else 0
    r.profit_loss_ratio = r.avg_win_pct / r.avg_loss_pct if r.avg_loss_pct > 0 else 0

    r.total_pnl_pct = sum(t.pnl_pct for t in trades)
    r.avg_hold_days = sum(t.hold_days for t in trades) / len(trades)

    r.exit_by_stop = sum(1 for t in trades if t.exit_reason == "stop_loss")
    r.exit_by_target = sum(1 for t in trades if t.exit_reason == "target")
    r.exit_by_timeout = sum(1 for t in trades if t.exit_reason == "timeout")

    # 期望值
    win_rate_dec = r.win_rate / 100
    r.expectancy = win_rate_dec * r.avg_win_pct - (1 - win_rate_dec) * r.avg_loss_pct

    # 最大回撤（基于累计净值曲线）
    equity = [1.0]
    for t in trades:
        equity.append(equity[-1] * (1 + t.pnl_pct / 100))
    peak = equity[0]
    max_dd = 0
    for e in equity:
        peak = max(peak, e)
        dd = (peak - e) / peak * 100
        max_dd = max(max_dd, dd)
    r.max_drawdown = round(max_dd, 2)

    # 四舍五入
    r.win_rate = round(r.win_rate, 1)
    r.avg_win_pct = round(r.avg_win_pct, 2)
    r.avg_loss_pct = round(r.avg_loss_pct, 2)
    r.profit_loss_ratio = round(r.profit_loss_ratio, 2)
    r.total_pnl_pct = round(r.total_pnl_pct, 2)
    r.avg_hold_days = round(r.avg_hold_days, 1)
    r.expectancy = round(r.expectancy, 2)

    return r


def main():
    t0 = time.time()
    conn = get_db()

    # Step 1: 获取标的池
    stock_codes = get_stock_pool(conn, min_avg_turnover=3e8, limit=50)
    log.info("标的池: %d 只股票", len(stock_codes))

    # Step 2: 生成全部信号（所有标的，所有类型）
    all_signals = []
    for i, code in enumerate(stock_codes):
        klines = get_all_klines(conn, code)
        if len(klines) < LOOKBACK + MAX_HOLD_DAYS + 10:
            continue
        sigs = generate_all_signals(klines, code)
        all_signals.extend([(sig, klines) for sig in sigs])
        if (i + 1) % 10 == 0:
            log.info("  已处理 %d/%d 只，累计信号 %d 个", i + 1, len(stock_codes), len(all_signals))

    log.info("信号生成完成: %d 个信号, 耗时 %.1fs", len(all_signals), time.time() - t0)

    # Step 3: 模拟全部交易
    all_trades = []
    for sig_info, klines in all_signals:
        trade = simulate_trade(klines, sig_info)
        all_trades.append(trade)

    log.info("交易模拟完成: %d 笔交易", len(all_trades))

    # Step 4: 分组统计
    groups = [
        ("A_all", "全部信号(无过滤)", lambda t: True),
        ("B_score65", "评分≥65", lambda t: t.signal_score >= 65),
        ("C_score70", "评分≥70", lambda t: t.signal_score >= 70),
        ("D_score75", "评分≥75", lambda t: t.signal_score >= 75),
        ("E_buy3_all", "仅三买(无评分)", lambda t: t.signal_type == "buy3"),
        ("F_buy3_s70", "三买+评分≥70", lambda t: t.signal_type == "buy3" and t.signal_score >= 70),
        ("G_buy12", "一买+二买(无评分)", lambda t: t.signal_type in ("buy1", "buy2")),
    ]

    results = []
    for name, desc, filter_fn in groups:
        filtered = [t for t in all_trades if filter_fn(t)]
        r = calc_group_result(filtered, name, desc)
        results.append(r)

    # Step 5: 输出报告
    print("\n" + "=" * 90)
    print("缠论策略对照回测报告")
    print("=" * 90)
    print(f"回测期间: {all_trades[0].entry_date if all_trades else 'N/A'} ~ {all_trades[-1].exit_date if all_trades else 'N/A'}")
    print(f"标的池: {len(stock_codes)}只 (日均成交额≥3亿)")
    print(f"入场: 信号日次日开盘 | 出场: 止损/目标/20天超时 | 成本: 双边0.4%")
    print(f"总信号数: {len(all_trades)} | 生成耗时: {time.time()-t0:.0f}s")
    print("-" * 90)
    print(f"{'组别':<14} {'笔数':>5} {'胜率':>6} {'均盈%':>7} {'均亏%':>7} {'盈亏比':>6} "
          f"{'期望值':>6} {'累计%':>8} {'最大回撤%':>8} {'止损':>4} {'达标':>4} {'超时':>4}")
    print("-" * 90)

    for r in results:
        print(f"{r.filter_desc:<12} {r.total_trades:>5} {r.win_rate:>5.1f}% "
              f"{r.avg_win_pct:>6.2f} {r.avg_loss_pct:>6.2f} {r.profit_loss_ratio:>6.2f} "
              f"{r.expectancy:>6.2f} {r.total_pnl_pct:>7.1f} {r.max_drawdown:>7.1f} "
              f"{r.exit_by_stop:>4} {r.exit_by_target:>4} {r.exit_by_timeout:>4}")

    print("-" * 90)
    print("\n注意事项:")
    print("- 环境分统一设为False(9分)，避免引入未来信息偏差")
    print("- 止损价基于信号结构(ZG下方3%或背驰低点下方3%)，非固定比例")
    print("- 目标价基于中枢等距投影或前高")
    print("- 期望值 = 胜率×均盈 - 败率×均亏，>0表示正期望")
    print("- 盈亏比 = 均盈/均亏，>1表示赚的比亏的多")
    print("- 此回测不含仓位管理和资金曲线，仅评估信号质量")
    print("")

    # 保存详细数据
    output = {
        "meta": {
            "run_time": datetime.now().isoformat(),
            "stock_pool_size": len(stock_codes),
            "total_signals": len(all_trades),
            "period": f"{all_trades[0].entry_date if all_trades else ''} ~ {all_trades[-1].exit_date if all_trades else ''}",
            "params": {"lookback": LOOKBACK, "max_hold_days": MAX_HOLD_DAYS, "cost_rate": COST_RATE},
        },
        "groups": [asdict(r) for r in results],
        "score_distribution": {
            "mean": round(sum(t.signal_score for t in all_trades) / len(all_trades), 1) if all_trades else 0,
            "median": sorted(t.signal_score for t in all_trades)[len(all_trades)//2] if all_trades else 0,
            "min": min(t.signal_score for t in all_trades) if all_trades else 0,
            "max": max(t.signal_score for t in all_trades) if all_trades else 0,
        },
        "trades_sample": [asdict(t) for t in all_trades[:50]],  # 前50笔样本
    }

    output_path = "/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/backtest/controlled_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("详细结果已保存: %s", output_path)

    conn.close()


if __name__ == "__main__":
    main()
