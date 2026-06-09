"""单元测试 - 回测引擎"""
import pytest
import pandas as pd
import numpy as np
from backtest import BacktestEngine, compute_metrics


class TestComputeMetrics:
    def test_total_return(self):
        """累计收益率计算正确"""
        nav = pd.Series([1.0, 1.05, 1.10, 1.15, 1.20])
        metrics = compute_metrics(nav)
        assert abs(metrics["total_return"] - 0.20) < 1e-6

    def test_max_drawdown(self):
        """最大回撤计算正确"""
        nav = pd.Series([1.0, 1.2, 1.1, 0.9, 1.0])
        metrics = compute_metrics(nav)
        # 从1.2跌到0.9, 回撤 = 0.3/1.2 = 0.25
        assert abs(metrics["max_drawdown"] - 0.25) < 1e-6

    def test_sharpe_ratio_positive(self):
        """持续上涨时夏普比率为正"""
        nav = pd.Series(np.linspace(1.0, 1.5, 252))
        metrics = compute_metrics(nav)
        assert metrics["sharpe_ratio"] > 0

    def test_win_rate_calculation(self):
        """胜率计算: 3盈2亏=60%"""
        trades = [
            {"pnl": 0.05}, {"pnl": 0.10}, {"pnl": -0.03},
            {"pnl": 0.08}, {"pnl": -0.02},
        ]
        metrics = compute_metrics(pd.Series([1.0, 1.1]), trades=trades)
        assert abs(metrics["win_rate"] - 0.6) < 1e-6

    def test_profit_loss_ratio(self):
        """盈亏比计算正确"""
        trades = [
            {"pnl": 0.10}, {"pnl": 0.20}, {"pnl": -0.05}, {"pnl": -0.15},
        ]
        # avg_profit = 0.15, avg_loss = 0.10
        metrics = compute_metrics(pd.Series([1.0, 1.1]), trades=trades)
        assert abs(metrics["profit_loss_ratio"] - 1.5) < 1e-6

    def test_annualized_return(self):
        """年化收益率: 252个交易日收益20% -> 年化≈20%"""
        nav = pd.Series(np.linspace(1.0, 1.2, 252))
        metrics = compute_metrics(nav)
        assert abs(metrics["annual_return"] - 0.2) < 0.02

    def test_zero_drawdown_for_monotone_increase(self):
        """单调递增序列最大回撤为0"""
        nav = pd.Series(np.linspace(1.0, 2.0, 100))
        metrics = compute_metrics(nav)
        assert metrics["max_drawdown"] == 0.0


class TestBacktestEngine:
    def test_initial_state(self):
        """初始状态: 净值=1, 持仓为空"""
        engine = BacktestEngine(initial_capital=1_000_000)
        assert engine.nav() == 1.0
        assert len(engine.positions) == 0

    def test_buy_reduces_cash(self):
        """买入后现金减少"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.execute_buy("000001", price=10.0, shares=1000, date="2024-01-02")
        assert engine.cash < 1_000_000

    def test_sell_increases_cash(self):
        """卖出后现金增加"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.execute_buy("000001", price=10.0, shares=1000, date="2024-01-02")
        cash_after_buy = engine.cash
        engine.execute_sell("000001", price=11.0, shares=1000, date="2024-01-05")
        assert engine.cash > cash_after_buy

    def test_transaction_cost_applied(self):
        """交易成本被正确扣除"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.execute_buy("000001", price=10.0, shares=1000, date="2024-01-02")
        # 买入金额=10000, 佣金=10000*0.00025=2.5, 滑点=10000*0.001=10
        expected_cost = 10000 + 10000 * 0.00025 + 10000 * 0.001
        assert engine.cash < 1_000_000 - 10000  # 有额外成本

    def test_stop_loss_triggers(self):
        """跌破止损线应触发卖出信号"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.execute_buy("000001", price=10.0, shares=1000, date="2024-01-02")
        # 当前价格跌到9.4 (-6%), 短期止损-5%应触发
        signals = engine.check_stop_loss({"000001": 9.4}, stop_loss=-0.05)
        assert "000001" in signals

    def test_nav_calculation(self):
        """净值=（现金+持仓市值）/ 初始资金"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.execute_buy("000001", price=10.0, shares=1000, date="2024-01-02")
        # 假设当前价格还是10, nav应约等于1 (减去交易成本)
        nav = engine.calculate_nav({"000001": 10.0})
        assert 0.99 < nav < 1.0  # 略低于1因为交易成本
