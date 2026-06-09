"""单元测试 - 策略评分模型"""
import pytest
import pandas as pd
import numpy as np
from strategy import ShortTermStrategy, MidTermStrategy


class TestShortTermStrategy:
    def setup_method(self):
        self.strategy = ShortTermStrategy()

    def test_score_range(self):
        """评分应在0-100之间"""
        mock_data = {
            "north_rank": 10, "main_net_inflow": 1.5, "margin_increasing": True,
            "price_breakout_20d": True, "macd_golden_cross": True,
            "volume_ratio": 1.8, "rsi": 60,
            "profit_growth_positive": True, "pe_below_industry": True,
            "market_cap": 80e8, "avg_turnover": 2e8,
        }
        score = self.strategy.score(mock_data)
        assert 0 <= score <= 100

    def test_full_score_conditions(self):
        """所有条件满足时得分应>=75"""
        mock_data = {
            "north_rank": 5, "main_net_inflow": 5.0, "margin_increasing": True,
            "price_breakout_20d": True, "macd_golden_cross": True,
            "volume_ratio": 2.0, "rsi": 60,
            "profit_growth_positive": True, "pe_below_industry": True,
            "market_cap": 100e8, "avg_turnover": 5e8,
        }
        score = self.strategy.score(mock_data)
        assert score >= 75

    def test_no_conditions_low_score(self):
        """无条件满足时得分应<50"""
        mock_data = {
            "north_rank": 100, "main_net_inflow": -2.0, "margin_increasing": False,
            "price_breakout_20d": False, "macd_golden_cross": False,
            "volume_ratio": 0.5, "rsi": 30,
            "profit_growth_positive": False, "pe_below_industry": False,
            "market_cap": 20e8, "avg_turnover": 0.3e8,
        }
        score = self.strategy.score(mock_data)
        assert score < 50

    def test_filter_excludes_low_cap(self):
        """流通市值<50亿应被排除"""
        mock_data = {"market_cap": 30e8, "avg_turnover": 0.5e8}
        assert not self.strategy.passes_filter(mock_data)

    def test_filter_passes_valid_stock(self):
        """满足流通市值和成交额应通过"""
        mock_data = {"market_cap": 80e8, "avg_turnover": 2e8}
        assert self.strategy.passes_filter(mock_data)


class TestMidTermStrategy:
    def setup_method(self):
        self.strategy = MidTermStrategy()

    def test_score_range(self):
        """评分应在0-100之间"""
        mock_data = {
            "industry_profit_growth": 25, "policy_support": True,
            "net_profit_growth": 30, "roe": 15, "cash_flow_positive": True,
            "peg": 1.2, "pe_percentile": 0.5, "dividend_yield": 2.0,
            "is_leader": True, "rd_ratio": 6,
        }
        score = self.strategy.score(mock_data)
        assert 0 <= score <= 100

    def test_high_score_for_ideal_stock(self):
        """理想中期标的应>=70分"""
        mock_data = {
            "industry_profit_growth": 30, "policy_support": True,
            "net_profit_growth": 35, "roe": 18, "cash_flow_positive": True,
            "peg": 1.0, "pe_percentile": 0.4, "dividend_yield": 2.5,
            "is_leader": True, "rd_ratio": 8,
        }
        score = self.strategy.score(mock_data)
        assert score >= 70

    def test_low_roe_penalized(self):
        """ROE<12%应降低业绩成长分"""
        high_roe = {"industry_profit_growth": 25, "policy_support": True,
                    "net_profit_growth": 25, "roe": 18, "cash_flow_positive": True,
                    "peg": 1.3, "pe_percentile": 0.5, "dividend_yield": 1.0,
                    "is_leader": False, "rd_ratio": 3}
        low_roe = dict(high_roe, roe=8)
        assert self.strategy.score(high_roe) > self.strategy.score(low_roe)
