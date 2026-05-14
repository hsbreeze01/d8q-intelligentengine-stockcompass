"""测试 DataAgentFetcher.search_news_by_keywords"""
from unittest.mock import patch, MagicMock



class TestSearchNewsByKeywords:
    """关键词搜索资讯测试"""

    def test_empty_keywords_returns_empty(self):
        """空关键词列表返回空列表"""
        from compass.services.data_gateway import DataAgentFetcher
        fetcher = DataAgentFetcher()
        result = fetcher.search_news_by_keywords([])
        assert result == []

    @patch("compass.services.data_gateway._http_get")
    def test_service_unavailable_returns_empty(self, mock_get):
        """DataAgent 不可用时返回空列表"""
        mock_get.return_value = None
        from compass.services.data_gateway import DataAgentFetcher
        fetcher = DataAgentFetcher()
        result = fetcher.search_news_by_keywords(["半导体"])
        assert result == []

    @patch("compass.services.data_gateway._http_get")
    def test_normal_keyword_matching(self, mock_get):
        """正常关键词匹配场景"""
        tracks_resp = [
            {"id": 1, "name": "半导体"},
            {"id": 2, "name": "AI"},
        ]

        track1_news = {
            "items": [
                {"title": "半导体行业迎来爆发期", "content": "半导体芯片需求激增", "source": "财经网", "date": "2025-01-15"},
                {"title": "AI芯片市场竞争加剧", "content": "各大厂商推出新一代AI芯片", "source": "科技日报", "date": "2025-01-14"},
            ]
        }
        track2_news = {
            "items": [
                {"title": "新能源汽车销量大涨", "content": "电动车市场持续增长", "source": "汽车周刊", "date": "2025-01-13"},
            ]
        }

        def side_effect(url, timeout=10):
            if "tracks" in url and url.endswith("/tracks"):
                return tracks_resp
            elif "/tracks/1/news" in url:
                return track1_news
            elif "/tracks/2/news" in url:
                return track2_news
            return None

        mock_get.side_effect = side_effect

        from compass.services.data_gateway import DataAgentFetcher
        fetcher = DataAgentFetcher()
        result = fetcher.search_news_by_keywords(["半导体", "AI芯片"], limit=20)

        assert len(result) >= 2
        # 检查包含关键字段
        for item in result:
            assert "title" in item
            assert "relevance" in item
            assert "matched_keyword" in item
            assert item["relevance"] > 0

        # 结果按相关度排序
        if len(result) >= 2:
            assert result[0]["relevance"] >= result[1]["relevance"]

    @patch("compass.services.data_gateway._http_get")
    def test_no_matching_news(self, mock_get):
        """无匹配资讯返回空列表"""
        tracks_resp = [{"id": 1, "name": "半导体"}]
        track_news = {
            "items": [
                {"title": "房地产政策调整", "content": "各地出台新政", "source": "财经网", "date": "2025-01-15"},
            ]
        }

        def side_effect(url, timeout=10):
            if url.endswith("/tracks"):
                return tracks_resp
            elif "/tracks/1/news" in url:
                return track_news
            return None

        mock_get.side_effect = side_effect

        from compass.services.data_gateway import DataAgentFetcher
        fetcher = DataAgentFetcher()
        result = fetcher.search_news_by_keywords(["半导体"], limit=20)
        assert result == []

    @patch("compass.services.data_gateway._http_get")
    def test_limit_respected(self, mock_get):
        """limit 参数限制返回数量"""
        tracks_resp = [{"id": 1, "name": "半导体"}]
        items = [
            {"title": f"半导体新闻{i}", "content": "半导体" + "x" * 50, "source": "财经网", "date": "2025-01-15"}
            for i in range(10)
        ]
        track_news = {"items": items}

        def side_effect(url, timeout=10):
            if url.endswith("/tracks"):
                return tracks_resp
            elif "/tracks/1/news" in url:
                return track_news
            return None

        mock_get.side_effect = side_effect

        from compass.services.data_gateway import DataAgentFetcher
        fetcher = DataAgentFetcher()
        result = fetcher.search_news_by_keywords(["半导体"], limit=3)
        assert len(result) == 3

    def test_data_gateway_proxy(self):
        """DataGateway.search_news_by_keywords 代理到 DataAgentFetcher"""
        from compass.services.data_gateway import DataGateway
        gw = DataGateway()
        gw.agent = MagicMock()
        gw.agent.search_news_by_keywords.return_value = [{"title": "test"}]

        result = gw.search_news_by_keywords(["test"])
        assert result == [{"title": "test"}]
        gw.agent.search_news_by_keywords.assert_called_once_with(["test"], limit=20)
