"""综合测试 - 验证全部能力模块"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np
from strategy import ShortTermStrategy, MidTermStrategy, compute_technical_signals
from backtest import BacktestEngine, compute_metrics
from capabilities import (compute_pe_percentile, compute_dividend_yield,
                          is_limit_up, is_limit_down, check_trade_feasibility,
                          PortfolioTracker, get_stock_industry_map)


class TestP0_DataSource:
    def test_stock_history(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        df = f.get_stock_history('000001', '20240101', '20240601')
        assert len(df) > 50
        assert 'close' in df.columns
        assert 'change_pct' in df.columns

    def test_index_history(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        df = f.get_index_history('000300', '20240101', '20240601')
        assert len(df) > 50
        assert 'close' in df.columns

    def test_north_flow(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        ns = f.get_north_flow_history('20240101', '20240601')
        assert len(ns) > 50
        assert ns.dtype == float or ns.dtype == np.float64

    def test_margin_data(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        m = f.get_margin_data()
        assert m['margin_balance'] > 10000  # 应大于1万亿
        assert isinstance(m['margin_increasing'], bool)


class TestP0_Strategy:
    def test_short_term_scoring(self):
        s = ShortTermStrategy()
        data = {'north_rank': 5, 'main_net_inflow': 5.0, 'margin_increasing': True,
                'price_breakout_20d': True, 'macd_golden_cross': True,
                'volume_ratio': 2.0, 'rsi': 60,
                'profit_growth_positive': True, 'pe_below_industry': True,
                'market_cap': 100e8, 'avg_turnover': 5e8}
        assert s.score(data) >= 75

    def test_mid_term_scoring(self):
        s = MidTermStrategy()
        data = {'industry_profit_growth': 30, 'policy_support': True,
                'net_profit_growth': 35, 'roe': 18, 'cash_flow_positive': True,
                'peg': 1.0, 'pe_percentile': 0.4, 'dividend_yield': 2.5,
                'is_leader': True, 'rd_ratio': 8}
        assert s.score(data) >= 70

    def test_technical_signals(self):
        df = pd.DataFrame({'close': np.linspace(10, 15, 30),
                          'volume': np.random.randint(1e6, 5e6, 30)})
        sig = compute_technical_signals(df)
        assert 'rsi' in sig
        assert 0 <= sig['rsi'] <= 100


class TestP0_Backtest:
    def test_metrics_calculation(self):
        nav = pd.Series(np.linspace(1.0, 1.3, 252))
        m = compute_metrics(nav)
        assert m['total_return'] > 0.25
        assert m['max_drawdown'] == 0.0
        assert m['sharpe_ratio'] > 0

    def test_engine_trade(self):
        e = BacktestEngine(1000000)
        e.execute_buy('000001', 10.0, 1000, '20240102')
        assert e.cash < 1000000
        e.execute_sell('000001', 11.0, 1000, '20240105')
        assert e.cash > 990000


class TestP1_Industry:
    def test_concept_list(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        concepts = f.get_concept_list()
        assert len(concepts) > 100


class TestP1_Valuation:
    def test_pe_percentile_range(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        pct = compute_pe_percentile(f, '000001', current_pe=8.0)
        assert 0 <= pct <= 1


class TestP1_Dividend:
    def test_dividend_yield(self):
        from data_fetcher import DataFetcher
        f = DataFetcher()
        dy = compute_dividend_yield(f, '000001')
        assert isinstance(dy, float)
        assert dy >= 0


class TestP1_LimitUpDown:
    def test_limit_up(self):
        assert is_limit_up(10.0) == True
        assert is_limit_up(9.8) == True
        assert is_limit_up(5.0) == False

    def test_limit_down(self):
        assert is_limit_down(-10.0) == True
        assert is_limit_down(-9.8) == True
        assert is_limit_down(-5.0) == False

    def test_trade_feasibility(self):
        df = pd.DataFrame({'close': [10, 11], 'change_pct': [10.0, -10.0]},
                         index=pd.to_datetime(['2024-01-02', '2024-01-03']))
        assert check_trade_feasibility(df, pd.Timestamp('2024-01-02'), 'buy') == False
        assert check_trade_feasibility(df, pd.Timestamp('2024-01-03'), 'sell') == False


class TestP1_Portfolio:
    def test_buy_sell(self):
        pt = PortfolioTracker(1000000)
        assert pt.buy('000001', 10.0, 0.1)
        assert '000001' in pt.positions
        assert pt.sell('000001', 11.0)
        assert '000001' not in pt.positions
        assert pt.cash > 990000

    def test_nav(self):
        pt = PortfolioTracker(1000000)
        pt.buy('000001', 10.0, 0.1)
        nav = pt.nav({'000001': 11.0})
        assert nav > 1.0

    def test_stop_loss_signal(self):
        pt = PortfolioTracker(1000000)
        pt.buy('000001', 10.0, 0.1)
        signals = pt.check_signals({'000001': 9.0})  # -10%
        assert len(signals) > 0
        assert signals[0]['action'] == 'SELL'
