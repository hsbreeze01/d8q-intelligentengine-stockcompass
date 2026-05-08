"""单元测试 — 同步触发 API 端点 (compass/api/routes/sync.py)

覆盖范围：
- POST /api/sync/dic-stock — 管理员触发同步（202）
- POST /api/sync/dic-stock — 非管理员（403）
- POST /api/sync/dic-stock — 同步进行中（409）
- GET /api/sync/dic-stock/status — 状态查询
"""
from unittest.mock import patch

import pytest

from compass.api.app import create_app


@pytest.fixture
def app():
    """创建测试 Flask app"""
    app = create_app(env="testing")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_as_admin(client):
    """模拟管理员登录"""
    with client.session_transaction() as sess:
        sess["uid"] = 1


def _login_as_normal(client):
    """模拟普通用户登录"""
    with client.session_transaction() as sess:
        sess["uid"] = 2


class TestTriggerSync:
    """POST /api/sync/dic-stock"""

    @patch("compass.api.routes.sync._is_admin", return_value=True)
    @patch("compass.api.routes.sync.sync_dic_stock")
    def test_admin_trigger_returns_202(self, mock_sync, mock_admin, client):
        """管理员触发同步返回 202"""
        mock_sync.return_value = {"total": 100, "synced": 100, "failed": 0}

        # Reset module state
        import compass.api.routes.sync as sync_mod
        sync_mod._sync_running = False

        resp = client.post("/api/sync/dic-stock")
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["message"] == "Sync started"

    @patch("compass.api.routes.sync._is_admin", return_value=False)
    def test_non_admin_returns_403(self, mock_admin, client):
        """非管理员返回 403"""
        resp = client.post("/api/sync/dic-stock")
        assert resp.status_code == 403

    @patch("compass.api.routes.sync._is_admin", return_value=True)
    def test_sync_already_running_returns_409(self, mock_admin, client):
        """同步进行中返回 409"""
        import compass.api.routes.sync as sync_mod
        sync_mod._sync_running = True

        resp = client.post("/api/sync/dic-stock")
        assert resp.status_code == 409
        data = resp.get_json()
        assert "already in progress" in data["error"]

        # Cleanup
        sync_mod._sync_running = False


class TestSyncStatus:
    """GET /api/sync/dic-stock/status"""

    def test_status_returns_running_false(self, client):
        """默认状态：未在运行"""
        import compass.api.routes.sync as sync_mod
        sync_mod._sync_running = False
        sync_mod._last_result = None

        resp = client.get("/api/sync/dic-stock/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False
        assert data["last_result"] is None

    def test_status_with_last_result(self, client):
        """返回上次同步结果"""
        import compass.api.routes.sync as sync_mod
        sync_mod._sync_running = False
        sync_mod._last_result = {
            "total": 5200,
            "synced": 5200,
            "failed": 0,
            "duration_seconds": 15.3,
            "source": "akshare-sina",
        }

        resp = client.get("/api/sync/dic-stock/status")
        data = resp.get_json()
        assert data["running"] is False
        assert data["last_result"]["total"] == 5200
        assert data["last_result"]["source"] == "akshare-sina"
