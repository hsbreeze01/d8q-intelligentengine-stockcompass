"""缠论策略回测执行器

支持：
- 单策略回测（type3_buy / type2_buy）
- 多标的滚动回测
- 输出：胜率、盈亏比、最大回撤、年化收益、夏普比率
- 结果写入 chanlun_backtest 表
"""
import sys
import os
import json
import math
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, "/home/ecs-assist-user/d8q-intelligentengine-stockcompass")

import pymysql
from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2
from chanlun.engine.types import PivotStatus, Direction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backtest")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "password", "database": "stock_analysis_system",
    "charset": "utf8mb4"
}


@dataclass
class Trade:
    """单笔交易记录"""
    stock_code: str
    signal_type: str
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    pnl: float = 0.0       # 盈亏金额
    pnl_pct: float = 0.0   # 盈亏百分比
    hold_days: int = 0
    exit_reason: str = ""   # stop_loss / target / timeout


@dataclass
class BacktestResult:
    """回测结果"""
    strategy: str
    period_start: str
    period_end: str
    stock_pool: str
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades: List[Trade] = field(default_factory=list)


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_all_klines(conn, stock_code):
    """获取一只股票的全部历史K线"""
    sql = "SELECT date as dt, open, high, low, close, volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date"
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        rows = cur.fetchall()
    return [{"dt": str(r["dt"]), "open": float(r["open"]), "high": float(r["high"]),
             "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]


def run_backtest(strategy="type3_buy", stock_codes=None, lookback=120, 
                 max_hold_days=20, cost_rate=0.002):
    """运行回测
    
    Args:
        strategy: 策略名称 (type3_buy / type2_buy)
        stock_codes: 回测标的列表
        lookback: 引擎计算需要的K线回看长度
        max_hold_days: 最大持仓天数
        cost_rate: 单边交易成本(佣金+滑点)
    """
    conn = get_db()
    
    if stock_codes is None:
        # 默认取成交额前30的股票
        sql = ("SELECT stock_code FROM stock_data_daily "
               "WHERE date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY) "
               "GROUP BY stock_code HAVING AVG(turnover)>=5e8 "
               "ORDER BY AVG(turnover) DESC LIMIT 30")
        with conn.cursor() as cur:
            cur.execute(sql)
            stock_codes = [r["stock_code"] for r in cur.fetchall()]
        stock_codes = [c for c in stock_codes if c[:3] in ("000","001","002","003","300","600","601","603","605")]
    
    log.info(f"回测策略: {strategy} | 标的: {len(stock_codes)}只 | 回看: {lookback}天")
    
    all_trades: List[Trade] = []
    
    for code in stock_codes:
        klines = get_all_klines(conn, code)
        if len(klines) < lookback + max_hold_days:
            continue
        
        # 滑动窗口回测
        trades = _backtest_single_stock(klines, code, strategy, lookback, max_hold_days, cost_rate)
        all_trades.extend(trades)
    
    # 计算汇总指标
    result = _calc_metrics(all_trades, strategy, stock_codes)
    
    # 保存到数据库
    _save_result(conn, result)
    conn.close()
    
    return result


def _backtest_single_stock(klines, stock_code, strategy, lookback, max_hold_days, cost_rate):
    """对单只股票做滑动窗口回测"""
    trades = []
    i = lookback  # 从第lookback根开始
    
    while i < len(klines) - 1:
        # 取截止到第i根的K线做分析
        window = klines[max(0, i-lookback):i+1]
        
        signal = _generate_signal(window, strategy)
        
        if signal is None:
            i += 1
            continue
        
        # 模拟交易
        entry_price = klines[i]["close"]  # 信号日收盘买入（简化为次日开盘）
        if i + 1 < len(klines):
            entry_price = klines[i+1]["open"]  # 次日开盘买入
        
        entry_date = klines[min(i+1, len(klines)-1)]["dt"]
        stop_loss = signal.stop_loss
        target = signal.target
        
        # 模拟持仓
        exit_price = entry_price
        exit_date = entry_date
        exit_reason = "timeout"
        
        for j in range(1, max_hold_days + 1):
            if i + 1 + j >= len(klines):
                break
            
            day = klines[i + 1 + j]
            
            # 检查止损
            if day["low"] <= stop_loss:
                exit_price = stop_loss
                exit_date = day["dt"]
                exit_reason = "stop_loss"
                break
            
            # 检查目标价
            if day["high"] >= target:
                exit_price = target
                exit_date = day["dt"]
                exit_reason = "target"
                break
            
            exit_price = day["close"]
            exit_date = day["dt"]
        
        # 计算盈亏
        pnl_pct = (exit_price - entry_price) / entry_price - cost_rate * 2
        
        trade = Trade(
            stock_code=stock_code,
            signal_type=signal.type.value,
            entry_date=entry_date,
            entry_price=round(entry_price, 2),
            exit_date=exit_date,
            exit_price=round(exit_price, 2),
            stop_loss=round(stop_loss, 2),
            target=round(target, 2),
            pnl_pct=round(pnl_pct * 100, 2),
            exit_reason=exit_reason
        )
        trades.append(trade)
        
        # 跳过持仓期间
        i += max_hold_days + 2
    
    return trades


def _generate_signal(klines, strategy):
    """对一段K线生成信号"""
    if len(klines) < 30:
        return None
    
    try:
        merged, fractals = identify_fractals(klines)
        strokes = build_strokes(fractals)
        pivots = find_pivots(strokes)
        
        if not strokes or not pivots:
            return None
        
        closes = [k["close"] for k in klines]
        dif, dea, macd_bar = compute_macd(closes)
        current_price = klines[-1]["close"]
        
        if strategy == "type3_buy":
            return detect_buy3(strokes, pivots, current_price)
        elif strategy == "type2_buy":
            divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)
            return detect_buy2(strokes, pivots, divergence)
    except:
        return None
    
    return None


def _calc_metrics(trades: List[Trade], strategy: str, stock_codes: list) -> BacktestResult:
    """计算回测绩效指标"""
    result = BacktestResult(
        strategy=strategy,
        period_start=trades[0].entry_date if trades else "",
        period_end=trades[-1].exit_date if trades else "",
        stock_pool=f"{len(stock_codes)} stocks",
        trades=trades
    )
    
    if not trades:
        return result
    
    result.total_trades = len(trades)
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    
    result.win_count = len(wins)
    result.loss_count = len(losses)
    result.win_rate = len(wins) / len(trades) * 100 if trades else 0
    
    result.avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
    result.avg_loss = sum(abs(t.pnl_pct) for t in losses) / len(losses) if losses else 1
    result.profit_loss_ratio = result.avg_win / result.avg_loss if result.avg_loss > 0 else 0
    
    # 总收益（假设等权分配）
    result.total_return = sum(t.pnl_pct for t in trades) / len(trades) * len(trades)
    
    # 年化（简化）
    if result.period_start and result.period_end:
        try:
            days = (datetime.strptime(result.period_end, "%Y-%m-%d") - 
                    datetime.strptime(result.period_start, "%Y-%m-%d")).days
            if days > 0:
                total_pct = sum(t.pnl_pct for t in trades)
                result.annual_return = total_pct / days * 252
        except:
            pass
    
    # 最大回撤（基于累计净值）
    equity = [1.0]
    for t in trades:
        equity.append(equity[-1] * (1 + t.pnl_pct / 100))
    
    peak = equity[0]
    max_dd = 0
    for e in equity:
        peak = max(peak, e)
        dd = (peak - e) / peak * 100
        max_dd = max(max_dd, dd)
    result.max_drawdown = round(max_dd, 2)
    
    # 夏普比率（简化）
    returns = [t.pnl_pct for t in trades]
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = (sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
        result.sharpe_ratio = round(mean_r / std_r * math.sqrt(12) if std_r > 0 else 0, 2)  # 月化
    
    return result


def _save_result(conn, result: BacktestResult):
    """保存回测结果到数据库"""
    sql = """INSERT INTO chanlun_backtest 
        (strategy_name, run_date, period_start, period_end, stock_pool, 
         total_trades, win_count, win_rate, profit_loss_ratio, 
         max_drawdown, annual_return, sharpe_ratio, params_json, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    
    with conn.cursor() as cur:
        cur.execute(sql, (
            result.strategy, datetime.now().strftime("%Y-%m-%d"),
            result.period_start, result.period_end, result.stock_pool,
            result.total_trades, result.win_count,
            round(result.win_rate, 2), round(result.profit_loss_ratio, 2),
            result.max_drawdown, round(result.annual_return, 2),
            result.sharpe_ratio, 
            json.dumps({"max_hold_days": 20, "cost_rate": 0.002}),
            f"Wins: {result.win_count}, Losses: {result.loss_count}"
        ))
    conn.commit()
    
    log.info("=" * 50)
    log.info(f"回测结果: {result.strategy}")
    log.info(f"  期间: {result.period_start} ~ {result.period_end}")
    log.info(f"  总交易: {result.total_trades}笔")
    log.info(f"  胜率: {result.win_rate:.1f}%")
    log.info(f"  盈亏比: {result.profit_loss_ratio:.2f}")
    log.info(f"  最大回撤: {result.max_drawdown:.1f}%")
    log.info(f"  年化收益: {result.annual_return:.1f}%")
    log.info(f"  夏普比率: {result.sharpe_ratio:.2f}")
    log.info("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="缠论策略回测")
    parser.add_argument("--strategy", default="type3_buy", choices=["type3_buy", "type2_buy"])
    parser.add_argument("--stocks", nargs="+", help="指定股票代码列表")
    args = parser.parse_args()
    
    result = run_backtest(strategy=args.strategy, stock_codes=args.stocks)
