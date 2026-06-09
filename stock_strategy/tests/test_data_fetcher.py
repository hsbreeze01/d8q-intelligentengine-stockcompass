"""单元测试 - 数据获取层"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from data_fetcher import DataFetcher


class TestDataFetcher:
    def setup_method(self):
        self.fetcher = DataFetcher(use_cache=False)

    def test_get_stock_history_returns_dataframe(self):
        """行情数据应返回含OHLCV的DataFrame"""
        df = self.fetcher.get_stock_history("000001", "20240101", "20240131")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        for col in ["open", "close", "high", "low", "volume"]:
            assert col in df.columns

    def test_get_stock_history_date_range(self):
        """返回数据应在请求日期范围内"""
        df = self.fetcher.get_stock_history("000001", "20240101", "20240110")
        assert df.index.min() >= pd.Timestamp("2024-01-01")
        assert df.index.max() <= pd.Timestamp("2024-01-10")

    def test_get_index_history(self):
        """沪深300指数应返回有效数据"""
        df = self.fetcher.get_index_history("000300", "20240101", "20240131")
        assert isinstance(df, pd.DataFrame)
        assert "close" in df.columns
        assert len(df) > 0

    def test_get_stock_fund_flow(self):
        """资金流向数据应含主力净流入"""
        data = self.fetcher.get_stock_fund_flow("000001", days=5)
        assert isinstance(data, dict)
        assert "main_net_inflow" in data

    def test_get_financial_data(self):
        """财务数据应含ROE和净利润增速"""
        data = self.fetcher.get_financial_data("000001")
        assert isinstance(data, dict)
        assert "roe" in data
        assert "net_profit_growth" in data

    def test_get_stock_list_filters_st(self):
        """股票列表应排除ST股"""
        stocks = self.fetcher.get_stock_list()
        assert isinstance(stocks, list)
        assert len(stocks) > 0
        for s in stocks:
            assert "ST" not in s.get("name", "")

    def test_empty_symbol_returns_empty(self):
        """无效代码应返回空DataFrame"""
        df = self.fetcher.get_stock_history("999999", "20240101", "20240131")
        assert df.empty
