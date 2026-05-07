"""单元测试 — 推荐评分引擎（compass/services/recommendation.py）

覆盖范围：
- _filter_eligible 排除规则
- _calc_technical_score 技术指标评分
- _calc_trend_score 趋势动量评分
- _calc_fundamental_score 基本面评分
- _calc_volume_score 量价配合评分
- _generate_reason 推荐理由生成
- _generate_risk_warning 风险提示生成
- RecommendationService.generate_daily（mock Database）
- RecommendationService.get_daily（mock Database）
"""
import datetime
from unittest.mock import patch, MagicMock

import pytest

from compass.services.recommendation import (
    _filter_eligible,
    _calc_technical_score,
    _calc_trend_score,
    _calc_fundamental_score,
    _calc_volume_score,
    _generate_reason,
    _generate_risk_warning,
    RecommendationService,
)


# ---------------------------------------------------------------------------
# _filter_eligible
# ---------------------------------------------------------------------------
class TestFilterEligible:
    """排除规则测试"""

    def test_excludes_st_stock(self):
        stocks = [{"stock_name": "*ST华讯", "change_percentage": 1, "turnover": 1e8, "turnover_rate": 1}]
        assert _filter_eligible(stocks) == []

    def test_keeps_normal_stock(self):
        s = {"stock_name": "贵州茅台", "change_percentage": 2, "turnover": 1e8, "turnover_rate": 1}
        assert _filter_eligible([s]) == [s]

    def test_excludes_high_change_percentage(self):
        s = {"stock_name": "正常股", "change_percentage": 10, "turnover": 1e8, "turnover_rate": 1}
        assert _filter_eligible([s]) == []

    def test_excludes_low_turnover_amount(self):
        s = {"stock_name": "正常股", "change_percentage": 1, "turnover": 1000, "turnover_rate": 1}
        assert _filter_eligible([s]) == []

    def test_excludes_low_turnover_rate(self):
        s = {"stock_name": "正常股", "change_percentage": 1, "turnover": 1e8, "turnover_rate": 0.1}
        assert _filter_eligible([s]) == []

    def test_accepts_stock_with_missing_optional_fields(self):
        """缺失 turnover/change_percentage 时不应被排除"""
        s = {"stock_name": "正常股"}
        assert len(_filter_eligible([s])) == 1

    def test_st_case_insensitive(self):
        s = {"stock_name": "st某某", "change_percentage": 1, "turnover": 1e8, "turnover_rate": 1}
        assert _filter_eligible([s]) == []

    def test_mixed_list(self):
        stocks = [
            {"stock_name": "贵州茅台", "change_percentage": 2, "turnover": 5e8, "turnover_rate": 1.5},
            {"stock_name": "*ST华讯", "change_percentage": 1, "turnover": 1e8, "turnover_rate": 1},
            {"stock_name": "低流股", "change_percentage": 1, "turnover": 100, "turnover_rate": 1},
        ]
        result = _filter_eligible(stocks)
        assert len(result) == 1
        assert result[0]["stock_name"] == "贵州茅台"


# ---------------------------------------------------------------------------
# _calc_technical_score
# ---------------------------------------------------------------------------
class TestCalcTechnicalScore:
    def test_more_buy_than_sell(self):
        score = _calc_technical_score(buy=5, sell=1)
        assert score == 90.0  # 50 + (5-1)*10

    def test_more_sell_than_buy(self):
        score = _calc_technical_score(buy=1, sell=5)
        assert score == 10.0  # 50 + (1-5)*10

    def test_equal_buy_sell(self):
        score = _calc_technical_score(buy=3, sell=3)
        assert score == 50.0

    def test_clamped_at_100(self):
        score = _calc_technical_score(buy=10, sell=0)
        assert score == 100.0  # 50 + 100 => clamped

    def test_clamped_at_0(self):
        score = _calc_technical_score(buy=0, sell=10)
        assert score == 0.0  # 50 - 100 => clamped

    def test_zero_signals(self):
        score = _calc_technical_score(buy=0, sell=0)
        assert score == 50.0


# ---------------------------------------------------------------------------
# _calc_trend_score
# ---------------------------------------------------------------------------
class TestCalcTrendScore:
    def _make_row(self, close=10, ma5=10, ma10=10, ma20=10, ma30=10, change=0):
        return {
            "close": close, "ma5": ma5, "ma10": ma10,
            "ma20": ma20, "ma30": ma30, "change_percentage": change,
        }

    def test_empty_rows_returns_zero(self):
        assert _calc_trend_score([]) == 0.0

    def test_full_bullish_alignment(self):
        """MA5 > MA10 > MA20 > MA30 → +25"""
        rows = [self._make_row() for _ in range(5)]
        rows[-1] = self._make_row(ma5=30, ma10=25, ma20=20, ma30=15, change=1)
        for r in rows:
            r["change_percentage"] = 1
        score = _calc_trend_score(rows)
        assert score >= 75  # 50 + 25 (MA) + 15 (positive avg change)

    def test_partial_alignment(self):
        """MA5 > MA10 > MA20 only → +15"""
        rows = [self._make_row() for _ in range(5)]
        rows[-1] = self._make_row(ma5=25, ma10=20, ma20=15, ma30=30, change=1)
        for r in rows:
            r["change_percentage"] = 1
        score = _calc_trend_score(rows)
        # MA partial = +15, positive avg change ~1% → +15
        assert score >= 65

    def test_negative_trend(self):
        rows = [self._make_row(change=-5) for _ in range(5)]
        rows[-1] = self._make_row(ma5=5, ma10=10, ma20=15, ma30=20, change=-5)
        for r in rows:
            r["change_percentage"] = -5
        score = _calc_trend_score(rows)
        # No MA bonus, avg_change = -5 → -10 → 40
        assert score <= 45


# ---------------------------------------------------------------------------
# _calc_fundamental_score
# ---------------------------------------------------------------------------
class TestCalcFundamentalScore:
    def test_good_fundamentals(self):
        stock = {"pe": 20, "pb": 2, "outstanding": 50e8}
        score = _calc_fundamental_score(stock)
        # PE 10-30 → +20, PB 1-3 → +15, outstanding 50亿 in [10,500] → +10
        # 50 + 20 + 15 + 10 = 95
        assert score == 95.0

    def test_negative_pe(self):
        stock = {"pe": -5}
        score = _calc_fundamental_score(stock)
        # PE < 0 → -30 → 20
        assert score == 20.0

    def test_empty_stock(self):
        score = _calc_fundamental_score({})
        assert score == 50.0  # baseline

    def test_high_pe(self):
        stock = {"pe": 60}
        score = _calc_fundamental_score(stock)
        # PE 30-50 → +5, else nothing → 55 but 60>50 → no PE bonus → 50
        assert score == 50.0


# ---------------------------------------------------------------------------
# _calc_volume_score
# ---------------------------------------------------------------------------
class TestCalcVolumeScore:
    def test_too_few_rows(self):
        assert _calc_volume_score([{"close": 10, "volume": 100}]) == 50.0

    def test_price_up_vol_up(self):
        rows = [
            {"close": 10, "volume": 100},
            {"close": 11, "volume": 200},
            {"close": 12, "volume": 300},
        ]
        score = _calc_volume_score(rows)
        assert score > 50  # all days are price_up_vol_up

    def test_price_down_vol_down(self):
        rows = [
            {"close": 12, "volume": 300},
            {"close": 11, "volume": 200},
            {"close": 10, "volume": 100},
        ]
        score = _calc_volume_score(rows)
        # price_down_vol_down gives partial points
        assert 50 <= score <= 80


# ---------------------------------------------------------------------------
# _generate_reason
# ---------------------------------------------------------------------------
class TestGenerateReason:
    def test_basic_reason(self):
        reason = _generate_reason("贵州茅台", 80, 70, 60, 50, 3, 1)
        assert "贵州茅台" in reason
        assert "技术指标" in reason  # highest score
        assert len(reason) <= 200

    def test_with_buy_signals(self):
        reason = _generate_reason("测试股", 80, 60, 60, 60, 5, 0)
        assert "5个买入信号" in reason

    def test_length_cap(self):
        reason = _generate_reason("X" * 200, 80, 80, 80, 80, 10, 0)
        assert len(reason) <= 200


# ---------------------------------------------------------------------------
# _generate_risk_warning
# ---------------------------------------------------------------------------
class TestGenerateRiskWarning:
    def test_basic_warning(self):
        warning = _generate_risk_warning("测试股", 70, 70, 70, 70)
        assert len(warning) <= 200

    def test_st_warning(self):
        warning = _generate_risk_warning("ST股", 70, 70, 70, 70, is_st=True)
        assert "ST" in warning

    def test_high_change_warning(self):
        warning = _generate_risk_warning("测试股", 70, 70, 70, 70, high_change=True)
        assert "涨跌幅" in warning

    def test_low_fundamental_warning(self):
        warning = _generate_risk_warning("测试股", 70, 70, 30, 70)
        assert "基本面" in warning

    def test_length_cap(self):
        warning = _generate_risk_warning("X" * 200, 70, 70, 70, 70, is_st=True, high_change=True)
        assert len(warning) <= 200


# ---------------------------------------------------------------------------
# RecommendationService — generate_daily (mock Database)
# ---------------------------------------------------------------------------
class TestGenerateDaily:
    """测试 generate_daily 主流程 — 使用 mock Database"""

    @patch("compass.services.recommendation.Database")
    def test_generate_daily_basic(self, MockDB):
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        # select_many returns (count, rows) tuples
        mock_db.select_many.side_effect = [
            # stocks query
            (2, [
                {"stock_code": "600519", "stock_name": "贵州茅台", "pe": 20, "pb": 2,
                 "outstanding": 50e8, "turnover_rate": 1.5, "latest_price": 1800,
                 "change_percentage": 1.0, "turnover": 1e9},
                {"stock_code": "000001", "stock_name": "平安银行", "pe": 8, "pb": 1,
                 "outstanding": 20e8, "turnover_rate": 2.0, "latest_price": 15,
                 "change_percentage": 0.5, "turnover": 5e8},
            ]),
            # trend_rows for 600519
            (20, [{"close": 1800, "change_percentage": 1.0, "ma5": 1790, "ma10": 1780,
                   "ma20": 1770, "ma30": 1760} for _ in range(20)]),
            # vol_rows for 600519
            (10, [{"close": 1800 + i, "volume": 1000 + i * 100} for i in range(10)]),
            # trend_rows for 000001
            (20, [{"close": 15, "change_percentage": 0.5} for _ in range(20)]),
            # vol_rows for 000001
            (10, [{"close": 15, "volume": 500} for _ in range(10)]),
        ]

        # select_one returns (count, row) tuples
        mock_db.select_one.side_effect = [
            (1, {"buy": 3, "sell": 1}),       # stock_analysis 600519
            (1, {"change_percentage": 1.0}),   # latest change 600519
            (1, {"buy": 2, "sell": 1}),        # stock_analysis 000001
            (1, {"change_percentage": 0.5}),   # latest change 000001
        ]

        svc = RecommendationService()
        result = svc.generate_daily(target_date="2025-06-01")

        assert "count" in result
        assert "elapsed_seconds" in result
        assert result["count"] == 2
        assert mock_db.execute.called  # wrote to DB


# ---------------------------------------------------------------------------
# RecommendationService — get_daily (mock Database)
# ---------------------------------------------------------------------------
class TestGetDaily:
    @patch("compass.services.recommendation.Database")
    def test_get_daily_empty(self, MockDB):
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.select_one.return_value = (1, {"total": 0})

        svc = RecommendationService()
        result = svc.get_daily(date="2025-01-01")

        assert result["recommendations"] == []
        assert result["total"] == 0
        assert result["generated_at"] is None

    @patch("compass.services.recommendation.Database")
    def test_get_daily_with_data(self, MockDB):
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.select_one.return_value = (1, {"total": 2})

        gen_at = datetime.datetime(2025, 6, 1, 10, 0, 0)
        mock_db.select_many.return_value = (2, [
            {
                "stock_code": "600519", "stock_name": "贵州茅台",
                "score": 85.5, "rank": 1, "reason": "推荐理由",
                "risk_warning": "风险提示",
                "recommendation_date": datetime.date(2025, 6, 1),
                "generated_at": gen_at,
            },
            {
                "stock_code": "000001", "stock_name": "平安银行",
                "score": 72.3, "rank": 2, "reason": "推荐理由2",
                "risk_warning": "风险提示2",
                "recommendation_date": datetime.date(2025, 6, 1),
                "generated_at": gen_at,
            },
        ])

        svc = RecommendationService()
        result = svc.get_daily(date="2025-06-01")

        assert result["total"] == 2
        assert len(result["recommendations"]) == 2
        assert result["recommendations"][0]["stock_code"] == "600519"
        assert result["recommendations"][0]["score"] == 85.5
        assert result["generated_at"] is not None

    @patch("compass.services.recommendation.Database")
    def test_get_daily_with_limit_offset(self, MockDB):
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.select_one.return_value = (1, {"total": 10})

        gen_at = datetime.datetime(2025, 6, 1, 10, 0, 0)
        mock_db.select_many.return_value = (1, [
            {
                "stock_code": "600519", "stock_name": "贵州茅台",
                "score": 85.5, "rank": 1, "reason": "理由", "risk_warning": "风险",
                "recommendation_date": datetime.date(2025, 6, 1),
                "generated_at": gen_at,
            },
        ])

        svc = RecommendationService()
        result = svc.get_daily(date="2025-06-01", limit=1, offset=0)

        # Verify the query used limit/offset
        call_args = mock_db.select_many.call_args
        assert call_args[0][1] == ("2025-06-01", 1, 0)
