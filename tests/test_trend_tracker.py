"""测试趋势跟踪器 — 核心逻辑"""
import json
from unittest.mock import MagicMock, patch



class TestTrendTracker:
    """趋势跟踪器测试"""

    @patch("compass.strategy.services.trend_tracker.db")
    def test_track_all_no_events(self, mock_db):
        """无 tracking 事件时安全跳过"""
        from compass.strategy.services.trend_tracker import TrendTracker

        mock_db.list_tracking_events.return_value = []

        tracker = TrendTracker()
        result = tracker.track_all()

        assert result["tracked"] == 0
        assert result["decayed"] == 0
        assert result["errors"] == 0

    @patch("compass.strategy.services.trend_tracker.db")
    def test_track_single_event_success(self, mock_db):
        """单事件跟踪成功"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event = {
            "id": 1,
            "dimension": "industry",
            "dimension_value": "半导体",
            "stock_count": 3,
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 4},
                {"code": "000002", "name": "B", "buy_star": 5},
            ],
            "llm_keywords": None,
            "llm_related_themes": None,
        }
        mock_db.list_tracking_events.return_value = [event]
        mock_db.get_latest_trend_tracking.return_value = None  # 首次跟踪
        mock_db.get_event_micro_data.return_value = {
            "event_id": 1,
            "stocks": [
                {"stock_code": "000001", "buy_star": 4,
                 "indicator_snapshot": {"RSI": 65, "MACD": 0.5}},
                {"stock_code": "000002", "buy_star": 5,
                 "indicator_snapshot": {"RSI": 55, "MACD": 0.3}},
            ],
        }
        mock_db.insert_trend_tracking.return_value = 100
        mock_db.get_recent_trend_trackings.return_value = []

        tracker = TrendTracker(gateway=MagicMock())
        result = tracker.track_all()

        assert result["tracked"] == 1
        assert result["decayed"] == 0

        # 验证 insert_trend_tracking 被调用
        mock_db.insert_trend_tracking.assert_called_once()
        call_kwargs = mock_db.insert_trend_tracking.call_args.kwargs
        assert call_kwargs["stock_count"] == 2
        assert len(call_kwargs["new_stocks"]) == 2  # 首次：全部为 new
        assert len(call_kwargs["lost_stocks"]) == 0

    @patch("compass.strategy.services.trend_tracker.db")
    def test_decay_detection(self, mock_db):
        """连续 2 日低分触发衰减"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event = {
            "id": 2,
            "dimension": "industry",
            "dimension_value": "银行",
            "stock_count": 2,
            "matched_stocks": [
                {"code": "600000", "name": "X", "buy_star": 1},
            ],
            "llm_keywords": None,
            "llm_related_themes": None,
        }
        mock_db.list_tracking_events.return_value = [event]
        mock_db.get_latest_trend_tracking.return_value = {
            "avg_score": 0.3,
            "new_stocks": [],
            "lost_stocks": [],
        }
        mock_db.get_event_micro_data.return_value = {
            "event_id": 2,
            "stocks": [
                {"stock_code": "600000", "buy_star": 1,
                 "indicator_snapshot": {}},
            ],
        }
        mock_db.insert_trend_tracking.return_value = 200

        # 模拟连续 2 日低分（包括当天刚写入的）
        mock_db.get_recent_trend_trackings.return_value = [
            {"avg_score": 0.1},  # 今天（刚写入）
            {"avg_score": 0.3},  # 昨天
        ]

        tracker = TrendTracker(gateway=MagicMock())
        result = tracker.track_all()

        assert result["tracked"] == 1
        assert result["decayed"] == 1

        # 验证 lifecycle 被更新为 suggest_close
        mock_db.update_event_lifecycle.assert_called_once()
        call_kwargs = mock_db.update_event_lifecycle.call_args.kwargs
        assert call_kwargs["lifecycle"] == "suggest_close"
        assert "suggest_close_reason" in call_kwargs

    @patch("compass.strategy.services.trend_tracker.db")
    def test_no_decay_high_score(self, mock_db):
        """高分不触发衰减"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event = {
            "id": 3,
            "dimension": "industry",
            "dimension_value": "半导体",
            "stock_count": 5,
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 8},
            ],
            "llm_keywords": None,
            "llm_related_themes": None,
        }
        mock_db.list_tracking_events.return_value = [event]
        mock_db.get_latest_trend_tracking.return_value = {
            "avg_score": 0.7,
            "new_stocks": [],
            "lost_stocks": [],
        }
        mock_db.get_event_micro_data.return_value = {
            "event_id": 3,
            "stocks": [
                {"stock_code": "000001", "buy_star": 8,
                 "indicator_snapshot": {}},
            ],
        }
        mock_db.insert_trend_tracking.return_value = 300

        # 今天的 avg_score 基于 buy_star/10 = 0.8 > 0.5
        mock_db.get_recent_trend_trackings.return_value = [
            {"avg_score": 0.8},
        ]

        tracker = TrendTracker(gateway=MagicMock())
        result = tracker.track_all()

        assert result["tracked"] == 1
        assert result["decayed"] == 0

    @patch("compass.strategy.services.trend_tracker.db")
    def test_news_association(self, mock_db):
        """资讯关联追加"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event = {
            "id": 4,
            "dimension": "industry",
            "dimension_value": "半导体",
            "stock_count": 3,
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 5},
            ],
            "llm_keywords": json.dumps(["半导体", "芯片"]),
            "llm_related_themes": json.dumps(["国产替代"]),
        }
        mock_db.list_tracking_events.return_value = [event]
        mock_db.get_latest_trend_tracking.return_value = {
            "avg_score": 0.6,
            "new_stocks": [],
            "lost_stocks": [],
        }
        mock_db.get_event_micro_data.return_value = {
            "event_id": 4,
            "stocks": [
                {"stock_code": "000001", "buy_star": 5,
                 "indicator_snapshot": {}},
            ],
        }
        mock_db.insert_trend_tracking.return_value = 400
        mock_db.get_recent_trend_trackings.return_value = [
            {"avg_score": 0.6},
        ]
        mock_db.append_event_news_matched.return_value = True

        mock_gateway = MagicMock()
        mock_gateway.search_news_by_keywords.return_value = [
            {"title": "半导体新政策", "relevance": 0.8},
            {"title": "芯片产能扩张", "relevance": 0.6},
        ]

        tracker = TrendTracker(gateway=mock_gateway)
        result = tracker.track_all()

        assert result["tracked"] == 1
        mock_gateway.search_news_by_keywords.assert_called_once()
        mock_db.append_event_news_matched.assert_called_once()

    @patch("compass.strategy.services.trend_tracker.db")
    def test_news_skip_when_no_keywords(self, mock_db):
        """关键词为空时跳过资讯关联"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event = {
            "id": 5,
            "dimension": "industry",
            "dimension_value": "能源",
            "stock_count": 2,
            "matched_stocks": [],
            "llm_keywords": None,
            "llm_related_themes": None,
        }
        mock_db.list_tracking_events.return_value = [event]
        mock_db.get_latest_trend_tracking.return_value = None
        mock_db.get_event_micro_data.return_value = {"event_id": 5, "stocks": []}
        mock_db.insert_trend_tracking.return_value = 500
        mock_db.get_recent_trend_trackings.return_value = []

        mock_gateway = MagicMock()

        tracker = TrendTracker(gateway=mock_gateway)
        result = tracker.track_all()

        assert result["tracked"] == 1
        mock_gateway.search_news_by_keywords.assert_not_called()

    @patch("compass.strategy.services.trend_tracker.db")
    def test_track_event_error_handling(self, mock_db):
        """单事件跟踪失败不影响其他事件"""
        from compass.strategy.services.trend_tracker import TrendTracker

        event1 = {"id": 10, "matched_stocks": None, "llm_keywords": None, "llm_related_themes": None}
        event2 = {"id": 11, "matched_stocks": [], "llm_keywords": None, "llm_related_themes": None}

        mock_db.list_tracking_events.return_value = [event1, event2]
        mock_db.get_latest_trend_tracking.return_value = None
        mock_db.get_event_micro_data.return_value = {"event_id": 10, "stocks": []}

        # 第一个事件在 insert 时抛出异常
        call_count = [0]
        def insert_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("DB error")
            return 100

        mock_db.insert_trend_tracking.side_effect = insert_side_effect

        tracker = TrendTracker(gateway=MagicMock())
        result = tracker.track_all()

        assert result["errors"] >= 1


class TestTrendTrackerDecay:
    """衰减判定逻辑专项测试"""

    def test_decay_threshold_constant(self):
        """验证衰减阈值常量"""
        from compass.strategy.services.trend_tracker import DECAY_SCORE_THRESHOLD
        from compass.strategy.services.trend_tracker import DECAY_CONSECUTIVE_DAYS

        assert DECAY_SCORE_THRESHOLD == 0.5
        assert DECAY_CONSECUTIVE_DAYS == 2
