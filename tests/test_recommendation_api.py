"""集成测试 — 推荐股票 API 路由（compass/api/routes/recommendation.py）

使用 Flask test client + mock RecommendationService。
覆盖三个端点：
- GET /api/recommendation/daily
- POST /api/recommendation/generate
- GET /api/recommendation/performance
"""
import datetime
from unittest.mock import patch, MagicMock

import pytest

from compass.api.app import create_app


@pytest.fixture(scope="module")
def app():
    """创建测试 Flask app（TESTING=True 跳过调度器）"""
    with patch.dict("os.environ", {"FLASK_ENV": "testing"}):
        application = create_app("testing")
    application.config["TESTING"] = True
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# GET /api/recommendation/daily
# ---------------------------------------------------------------------------
class TestGetDailyRecommendation:

    @patch("compass.services.recommendation.RecommendationService")
    def test_returns_200_with_recommendations(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.return_value = {
            "recommendations": [
                {
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "score": 85.5,
                    "rank": 1,
                    "reason": "推荐理由",
                    "risk_warning": "风险提示",
                    "recommendation_date": "2025-06-01",
                },
            ],
            "total": 1,
            "generated_at": "2025-06-01T10:00:00",
        }

        resp = client.get("/api/recommendation/daily")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["stock_code"] == "600519"

    @patch("compass.services.recommendation.RecommendationService")
    def test_returns_empty_when_no_data(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.return_value = {
            "recommendations": [],
            "total": 0,
            "generated_at": None,
        }

        resp = client.get("/api/recommendation/daily")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["recommendations"] == []
        assert data["total"] == 0

    @patch("compass.services.recommendation.RecommendationService")
    def test_passes_limit_and_offset(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.return_value = {
            "recommendations": [],
            "total": 0,
            "generated_at": None,
        }

        resp = client.get("/api/recommendation/daily?limit=5&offset=10")
        assert resp.status_code == 200
        mock_svc.get_daily.assert_called_once_with(date=None, limit=5, offset=10)

    @patch("compass.services.recommendation.RecommendationService")
    def test_passes_date_parameter(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.return_value = {
            "recommendations": [],
            "total": 0,
            "generated_at": None,
        }

        resp = client.get("/api/recommendation/daily?date=2025-01-20")
        assert resp.status_code == 200
        mock_svc.get_daily.assert_called_once_with(date="2025-01-20", limit=20, offset=0)

    @patch("compass.services.recommendation.RecommendationService")
    def test_invalid_limit_defaults_to_20(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.return_value = {
            "recommendations": [],
            "total": 0,
            "generated_at": None,
        }

        resp = client.get("/api/recommendation/daily?limit=abc")
        assert resp.status_code == 200
        mock_svc.get_daily.assert_called_once_with(date=None, limit=20, offset=0)

    @patch("compass.services.recommendation.RecommendationService")
    def test_service_error_returns_500(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_daily.side_effect = Exception("DB connection failed")

        resp = client.get("/api/recommendation/daily")
        assert resp.status_code == 500
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# POST /api/recommendation/generate
# ---------------------------------------------------------------------------
class TestGenerateRecommendation:

    @patch("compass.api.routes.recommendation._is_admin", return_value=True)
    @patch("compass.services.recommendation.RecommendationService")
    def test_admin_can_trigger_generate(self, MockSvc, mock_admin, client):
        mock_svc = MockSvc.return_value
        mock_svc.generate_daily.return_value = {
            "count": 15,
            "elapsed_seconds": 3.5,
        }

        resp = client.post(
            "/api/recommendation/generate",
            json={"date": "2025-06-01"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 15
        assert data["elapsed_seconds"] == 3.5
        mock_svc.generate_daily.assert_called_once_with(target_date="2025-06-01")

    @patch("compass.api.routes.recommendation._is_admin", return_value=False)
    def test_non_admin_gets_403(self, mock_admin, client):
        resp = client.post("/api/recommendation/generate")
        assert resp.status_code == 403

    @patch("compass.api.routes.recommendation._is_admin", return_value=True)
    @patch("compass.services.recommendation.RecommendationService")
    def test_generate_without_date_uses_default(self, MockSvc, mock_admin, client):
        mock_svc = MockSvc.return_value
        mock_svc.generate_daily.return_value = {"count": 0, "elapsed_seconds": 0.1}

        resp = client.post("/api/recommendation/generate", json={})
        assert resp.status_code == 200
        mock_svc.generate_daily.assert_called_once_with(target_date=None)

    @patch("compass.api.routes.recommendation._is_admin", return_value=True)
    @patch("compass.services.recommendation.RecommendationService")
    def test_generate_error_returns_500(self, MockSvc, mock_admin, client):
        mock_svc = MockSvc.return_value
        mock_svc.generate_daily.side_effect = Exception("calc error")

        resp = client.post("/api/recommendation/generate", json={})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/recommendation/performance
# ---------------------------------------------------------------------------
class TestGetPerformance:

    @patch("compass.services.recommendation.RecommendationService")
    def test_returns_performance_data(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_performance.return_value = {
            "recommendations": [
                {
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "score": 85.5,
                    "rank": 1,
                    "reason": "理由",
                    "risk_warning": "风险",
                    "recommendation_date": "2025-01-20",
                    "actual_change_1d": 2.5,
                    "actual_change_5d": 5.3,
                },
            ],
            "stats": {
                "avg_change_1d": 2.5,
                "win_rate_1d": 100.0,
                "count": 1,
                "avg_change_5d": 5.3,
                "win_rate_5d": 100.0,
            },
        }

        resp = client.get("/api/recommendation/performance?date=2025-01-20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stats"]["avg_change_1d"] == 2.5
        assert data["recommendations"][0]["actual_change_1d"] == 2.5

    def test_missing_date_returns_400(self, client):
        resp = client.get("/api/recommendation/performance")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    @patch("compass.services.recommendation.RecommendationService")
    def test_no_data_returns_empty(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_performance.return_value = {
            "recommendations": [],
            "stats": None,
        }

        resp = client.get("/api/recommendation/performance?date=2025-01-20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["recommendations"] == []
        assert data["stats"] is None

    @patch("compass.services.recommendation.RecommendationService")
    def test_service_error_returns_500(self, MockSvc, client):
        mock_svc = MockSvc.return_value
        mock_svc.get_performance.side_effect = Exception("DB error")

        resp = client.get("/api/recommendation/performance?date=2025-01-20")
        assert resp.status_code == 500
