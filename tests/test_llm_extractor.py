"""测试 LLM 特征提取器 — 三阶段分析编排"""
import json
from unittest.mock import MagicMock, patch



class TestLLMExtractor:
    """LLM 三阶段分析测试"""

    @patch("compass.strategy.services.llm_extractor.db")
    def test_full_pipeline_success(self, mock_db):
        """三阶段全部成功"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        event = {
            "id": 1,
            "dimension": "industry",
            "dimension_value": "半导体",
            "stock_count": 5,
            "avg_buy_star": 4.2,
            "max_buy_star": 6,
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 4},
                {"code": "000002", "name": "B", "buy_star": 5},
            ],
        }
        mock_db.get_group_event.return_value = event
        mock_db.get_event_micro_data.return_value = {
            "event_id": 1,
            "stocks": [
                {"stock_code": "000001", "buy_star": 4, "indicator_snapshot": {"RSI": 65}},
            ],
        }

        # Mock LLM clients
        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = json.dumps({
            "event_type": "板块联动",
            "confidence": 0.85,
            "keywords": ["半导体", "AI芯片"],
            "possible_drivers": ["政策利好", "产能扩张"],
            "related_themes": ["国产替代"],
        })

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.return_value = "## 半导体板块联动分析\n..."

        # Mock gateway
        mock_gateway = MagicMock()
        mock_gateway.search_news_by_keywords.return_value = [
            {"title": "半导体利好", "relevance": 0.5, "matched_keyword": "半导体"},
        ]

        extractor = LLMExtractor(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

        result = extractor.analyze_event(1)

        assert result["event_id"] == 1
        assert result["structured"] is not None
        assert result["structured"]["confidence"] == 0.85
        assert result["structured"]["keywords"] == ["半导体", "AI芯片"]
        assert len(result["news_matched"]) == 1
        assert result["news_confirm_score"] > 0
        assert result["news_confirmed"] is True
        assert result["llm_summary"] is not None

        # 验证持久化被调用
        mock_db.update_event_llm_result.assert_called_once()
        call_kwargs = mock_db.update_event_llm_result.call_args
        assert call_kwargs.kwargs.get("llm_keywords") == ["半导体", "AI芯片"]
        assert call_kwargs.kwargs.get("news_confirmed") is True

    @patch("compass.strategy.services.llm_extractor.db")
    def test_doubao_failure_graceful(self, mock_db):
        """Doubao 失败不阻塞后续阶段"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        event = {
            "id": 2,
            "dimension": "industry",
            "dimension_value": "银行",
            "stock_count": 3,
            "matched_stocks": [{"code": "600000", "name": "X", "buy_star": 3}],
        }
        mock_db.get_group_event.return_value = event
        mock_db.get_event_micro_data.return_value = {"event_id": 2, "stocks": []}

        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = None

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.return_value = "## 分析摘要"

        mock_gateway = MagicMock()
        mock_gateway.search_news_by_keywords.return_value = []

        extractor = LLMExtractor(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

        result = extractor.analyze_event(2)

        assert result["structured"] is None
        assert result["news_matched"] == []
        assert result["news_confirm_score"] == 0.0
        assert result["llm_summary"] is not None

    @patch("compass.strategy.services.llm_extractor.db")
    def test_deepseek_failure_graceful(self, mock_db):
        """DeepSeek 失败不影响已有结果"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        event = {
            "id": 3,
            "dimension": "concept",
            "dimension_value": "AI",
            "stock_count": 4,
            "matched_stocks": [{"code": "300001", "name": "Y", "buy_star": 5}],
        }
        mock_db.get_group_event.return_value = event
        mock_db.get_event_micro_data.return_value = {"event_id": 3, "stocks": []}

        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = json.dumps({
            "event_type": "概念爆发",
            "confidence": 0.7,
            "keywords": ["AI"],
            "possible_drivers": ["技术突破"],
            "related_themes": ["大模型"],
        })

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.side_effect = Exception("DeepSeek timeout")

        mock_gateway = MagicMock()
        mock_gateway.search_news_by_keywords.return_value = [
            {"title": "AI新闻", "relevance": 1.0, "matched_keyword": "AI"},
        ]

        extractor = LLMExtractor(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

        result = extractor.analyze_event(3)

        assert result["structured"] is not None
        assert len(result["news_matched"]) == 1
        assert result["llm_summary"] is None  # DeepSeek failed

    @patch("compass.strategy.services.llm_extractor.db")
    def test_event_not_found(self, mock_db):
        """事件不存在返回错误"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        mock_db.get_group_event.return_value = None

        extractor = LLMExtractor()
        result = extractor.analyze_event(999)

        assert result["error"] == "事件不存在"

    @patch("compass.strategy.services.llm_extractor.db")
    def test_empty_keywords_skip_search(self, mock_db):
        """Doubao 未输出关键词时跳过搜索"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        event = {
            "id": 4,
            "dimension": "industry",
            "dimension_value": "能源",
            "stock_count": 2,
            "matched_stocks": [],
        }
        mock_db.get_group_event.return_value = event
        mock_db.get_event_micro_data.return_value = {"event_id": 4, "stocks": []}

        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = json.dumps({
            "event_type": "资金异动",
            "confidence": 0.5,
            "keywords": [],
            "possible_drivers": [],
            "related_themes": [],
        })

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.return_value = "## 摘要"

        mock_gateway = MagicMock()

        extractor = LLMExtractor(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

        result = extractor.analyze_event(4)

        assert result["news_matched"] == []
        assert result["news_confirm_score"] == 0.0
        mock_gateway.search_news_by_keywords.assert_not_called()

    @patch("compass.strategy.services.llm_extractor.db")
    def test_persistence_failure_doesnt_crash(self, mock_db):
        """持久化失败不影响返回结果"""
        from compass.strategy.services.llm_extractor import LLMExtractor

        event = {
            "id": 5,
            "dimension": "industry",
            "dimension_value": "军工",
            "stock_count": 3,
            "matched_stocks": [],
        }
        mock_db.get_group_event.return_value = event
        mock_db.get_event_micro_data.return_value = {"event_id": 5, "stocks": []}
        mock_db.update_event_llm_result.side_effect = Exception("DB error")

        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = json.dumps({
            "event_type": "板块联动",
            "confidence": 0.6,
            "keywords": ["军工"],
            "possible_drivers": ["地缘"],
            "related_themes": [],
        })

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.return_value = "## 摘要"

        mock_gateway = MagicMock()
        mock_gateway.search_news_by_keywords.return_value = []

        extractor = LLMExtractor(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

        result = extractor.analyze_event(5)
        assert result["event_id"] == 5
        assert "error" not in result
