"""回测引擎 - 交易执行、净值计算、指标评估"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 交易成本
COMMISSION_RATE = 0.00025  # 佣金 0.025% 单边
STAMP_TAX_RATE = 0.0005   # 印花税 0.05% 卖出
SLIPPAGE_RATE = 0.001     # 滑点 0.1% 单边
RISK_FREE_RATE = 0.025    # 无风险利率 2.5%


@dataclass
class Trade:
    stock: str
    direction: str  # BUY / SELL
    price: float
    shares: int
    date: str
    cost: float = 0.0
    pnl: float = 0.0


class BacktestEngine:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, dict] = {}  # {code: {shares, avg_cost, entry_date}}
        self.trades: List[Trade] = []
        self.nav_series: List[float] = []
        self.date_series: List[str] = []

    def nav(self) -> float:
        return self.cash / self.initial_capital if not self.positions else self.nav_series[-1] if self.nav_series else 1.0

    def execute_buy(self, stock: str, price: float, shares: int, date: str):
        """执行买入, price 已含滑点"""
        cost = price * shares
        commission = cost * COMMISSION_RATE
        slippage = cost * SLIPPAGE_RATE
        total_cost = cost + commission + slippage

        if total_cost > self.cash:
            # 调整为可买数量
            shares = int(self.cash / (price * (1 + COMMISSION_RATE + SLIPPAGE_RATE)) // 100) * 100
            if shares <= 0:
                return
            cost = price * shares
            commission = cost * COMMISSION_RATE
            slippage = cost * SLIPPAGE_RATE
            total_cost = cost + commission + slippage

        self.cash -= total_cost
        if stock in self.positions:
            pos = self.positions[stock]
            total_shares = pos["shares"] + shares
            pos["avg_cost"] = (pos["avg_cost"] * pos["shares"] + price * shares) / total_shares
            pos["shares"] = total_shares
        else:
            self.positions[stock] = {"shares": shares, "avg_cost": price, "entry_date": date}

        self.trades.append(Trade(stock=stock, direction="BUY", price=price,
                                 shares=shares, date=date, cost=commission + slippage))

    def execute_sell(self, stock: str, price: float, shares: int, date: str):
        """执行卖出"""
        if stock not in self.positions:
            return
        pos = self.positions[stock]
        shares = min(shares, pos["shares"])
        if shares <= 0:
            return

        revenue = price * shares
        commission = revenue * COMMISSION_RATE
        stamp_tax = revenue * STAMP_TAX_RATE
        slippage = revenue * SLIPPAGE_RATE
        net_revenue = revenue - commission - stamp_tax - slippage

        pnl = (price - pos["avg_cost"]) * shares - commission - stamp_tax - slippage
        self.cash += net_revenue

        pos["shares"] -= shares
        if pos["shares"] <= 0:
            del self.positions[stock]

        self.trades.append(Trade(stock=stock, direction="SELL", price=price,
                                 shares=shares, date=date,
                                 cost=commission + stamp_tax + slippage, pnl=pnl))

    def calculate_nav(self, prices: Dict[str, float]) -> float:
        """计算当日净值"""
        portfolio_value = self.cash
        for stock, pos in self.positions.items():
            p = prices.get(stock, pos["avg_cost"])
            portfolio_value += p * pos["shares"]
        return portfolio_value / self.initial_capital

    def record_nav(self, prices: Dict[str, float], date: str):
        """记录每日净值"""
        nav = self.calculate_nav(prices)
        self.nav_series.append(nav)
        self.date_series.append(date)

    def check_stop_loss(self, prices: Dict[str, float], stop_loss: float = -0.05) -> List[str]:
        """检查止损触发, 返回需要止损的股票列表"""
        to_sell = []
        for stock, pos in self.positions.items():
            current = prices.get(stock, pos["avg_cost"])
            pnl_pct = (current - pos["avg_cost"]) / pos["avg_cost"]
            if pnl_pct <= stop_loss:
                to_sell.append(stock)
        return to_sell

    def check_take_profit(self, prices: Dict[str, float],
                          tp_half: float = 0.08, tp_full: float = 0.15) -> Dict[str, str]:
        """检查止盈, 返回 {stock: 'half'|'full'}"""
        signals = {}
        for stock, pos in self.positions.items():
            current = prices.get(stock, pos["avg_cost"])
            pnl_pct = (current - pos["avg_cost"]) / pos["avg_cost"]
            if pnl_pct >= tp_full:
                signals[stock] = "full"
            elif pnl_pct >= tp_half:
                signals[stock] = "half"
        return signals

    def get_closed_trades(self) -> List[dict]:
        """获取已平仓交易的盈亏列表"""
        return [{"pnl": t.pnl} for t in self.trades if t.direction == "SELL"]


def compute_metrics(nav_series: pd.Series, trades: Optional[List[dict]] = None,
                    benchmark_nav: Optional[pd.Series] = None) -> dict:
    """计算回测核心指标"""
    nav = np.array(nav_series, dtype=float)
    n = len(nav)

    # 收益
    total_return = (nav[-1] - nav[0]) / nav[0] if n > 1 else 0.0
    trading_days = n - 1 if n > 1 else 1
    annual_return = (1 + total_return) ** (252.0 / trading_days) - 1 if trading_days > 0 else 0.0

    # 最大回撤
    peak = np.maximum.accumulate(nav)
    drawdown = (peak - nav) / peak
    max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    # 波动率
    daily_returns = np.diff(nav) / nav[:-1] if n > 1 else np.array([0.0])
    volatility = float(np.std(daily_returns) * np.sqrt(252))

    # 夏普比率
    sharpe_ratio = (annual_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0.0

    # 卡玛比率
    calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0

    # 索提诺比率
    negative_returns = daily_returns[daily_returns < 0]
    downside_vol = float(np.std(negative_returns) * np.sqrt(252)) if len(negative_returns) > 0 else 0.0
    sortino_ratio = (annual_return - RISK_FREE_RATE) / downside_vol if downside_vol > 0 else 0.0

    # 交易指标
    win_rate = 0.0
    profit_loss_ratio = 0.0
    if trades:
        profits = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in trades if t["pnl"] < 0]
        total_trades = len([t for t in trades if t["pnl"] != 0])
        win_rate = len(profits) / total_trades if total_trades > 0 else 0.0
        avg_profit = np.mean(profits) if profits else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 1.0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0.0

    # 超额收益
    alpha = 0.0
    if benchmark_nav is not None and len(benchmark_nav) > 1:
        bench = np.array(benchmark_nav, dtype=float)
        bench_return = (bench[-1] - bench[0]) / bench[0]
        alpha = total_return - bench_return

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "calmar_ratio": calmar_ratio,
        "sortino_ratio": sortino_ratio,
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "alpha": alpha,
        "total_trades": len(trades) if trades else 0,
    }
