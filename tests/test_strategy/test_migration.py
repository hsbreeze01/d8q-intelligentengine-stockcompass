"""策略组引擎 — Flask Blueprint 迁移测试

覆盖：
- 路由注册验证（所有 16 个端点）
- 策略组 CRUD（create/update/delete/toggle/list/get）
- 信号扫描与查询
- 群体事件查询/关闭
- 行业同步后台线程
- SSE 流式响应
- 无 FastAPI 残余 import
"""
import json
import threading
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_group():
    """示例策略组数据"""
    return {
        "id": 1,
        "name": "KDJ金叉+RSI超卖",
        "indicators": ["KDJ", "RSI"],
        "signal_logic": "AND",
        "conditions": [
            {"indicator": "KDJ_K", "operator": ">", "value": 80},
            {"indicator": "RSI", "operator": "<", "value": 30},
        ],
        "scoring_threshold": None,
        "aggregation": {
            "dimension": "industry",
            "min_stocks": 3,
            "time_window_minutes": 60,
        },
        "scan_cron": "0 15 * * 1-5",
        "status": "active",
        "created_at": "2025-01-15 10:00:00",
        "updated_at": "2025-01-15 10:00:00",
    }


@pytest.fixture
def flask_client():
    """创建测试用 Flask 客户端（mock 掉数据库和调度器）"""
    with patch("compass.strategy.scheduler.start_scheduler"):
        with patch("compass.strategy.db.init_tables"):
            with patch("compass.api.app._start_scheduler"):
                from compass.api.app import create_app
                app = create_app()
                app.config["TESTING"] = True
                with app.test_client() as client:
                    yield client


# ============================================================================
# Test: Task 3.2 — 端到端路由注册验证
# ============================================================================

class TestRouteRegistration:
    """验证所有 16 个策略组路由注册到 Flask 应用"""

    def test_app_creates_successfully(self):
        """create_app() 不抛异常"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()
                assert app is not None

    def test_strategy_group_routes_registered(self):
        """策略组 CRUD 6 个端点已注册"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()
                rules = {rule.rule for rule in app.url_map.iter_rules()}

                expected = {
                    "/api/strategy/groups",
                    "/api/strategy/groups/<int:group_id>",
                    "/api/strategy/groups/<int:group_id>/status",
                }
                assert expected.issubset(rules), f"Missing routes: {expected - rules}"

    def test_signal_routes_registered(self):
        """信号扫描与查询 3 个端点已注册"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()
                rules = {rule.rule for rule in app.url_map.iter_rules()}

                expected = {
                    "/api/strategy/<int:group_id>/scan",
                    "/api/signals",
                    "/api/signals/stream",
                }
                assert expected.issubset(rules), f"Missing routes: {expected - rules}"

    def test_event_routes_registered(self):
        """群体事件 3 个端点已注册"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()
                rules = {rule.rule for rule in app.url_map.iter_rules()}

                expected = {
                    "/api/events",
                    "/api/events/<int:event_id>",
                    "/api/events/<int:event_id>/close",
                }
                assert expected.issubset(rules), f"Missing routes: {expected - rules}"

    def test_industry_sync_routes_registered(self):
        """行业同步 4 个端点已注册"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()
                rules = {rule.rule for rule in app.url_map.iter_rules()}

                expected = {
                    "/api/admin/industry/sync",
                    "/api/admin/industry/sync/status",
                    "/api/admin/industry/stats",
                    "/api/admin/industry/status",
                }
                assert expected.issubset(rules), f"Missing routes: {expected - rules}"

    def test_all_16_strategy_endpoints_counted(self):
        """总计 16 个策略组端点"""
        with patch("compass.api.app._start_scheduler"):
            with patch("compass.strategy.app.init_strategy_engine"):
                from compass.api.app import create_app
                app = create_app()

                strategy_rules = [
                    r for r in app.url_map.iter_rules()
                    if any(p in r.rule for p in [
                        "/api/strategy/",
                        "/api/signals",
                        "/api/events",
                        "/api/admin/industry",
                    ])
                ]
                # Count unique (rule, method) combinations excluding HEAD/OPTIONS
                endpoints = set()
                for rule in strategy_rules:
                    for method in rule.methods:
                        if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                            endpoints.add((rule.rule, method))
                assert len(endpoints) >= 16, f"Expected 16 endpoints, got {len(endpoints)}: {endpoints}"


# ============================================================================
# Test: Task 3.1 — 无 FastAPI 残余
# ============================================================================

class TestNoFastAPIResidual:
    """确认路由文件无 FastAPI / sse_starlette import"""

    def test_strategy_groups_no_fastapi(self):
        import compass.strategy.routes.strategy_groups as mod
        source = open(mod.__file__).read()
        assert "from fastapi" not in source
        assert "from sse_starlette" not in source

    def test_signals_no_fastapi(self):
        import compass.strategy.routes.signals as mod
        source = open(mod.__file__).read()
        assert "from fastapi" not in source
        assert "from sse_starlette" not in source

    def test_events_no_fastapi(self):
        import compass.strategy.routes.events as mod
        source = open(mod.__file__).read()
        assert "from fastapi" not in source
        assert "from sse_starlette" not in source

    def test_industry_sync_no_fastapi(self):
        import compass.strategy.routes.industry_sync as mod
        source = open(mod.__file__).read()
        assert "from fastapi" not in source
        assert "from sse_starlette" not in source


# ============================================================================
# Test: Strategy Group CRUD via Flask test client
# ============================================================================

class TestStrategyGroupRoutes:
    """策略组 CRUD 路由 Flask 集成测试"""

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_create_group(self, mock_db, flask_client, sample_group):
        """POST /api/strategy/groups — 创建策略组返回 201"""
        mock_db.insert_strategy_group.return_value = 1
        mock_db.get_strategy_group.return_value = sample_group

        payload = {
            "name": "KDJ金叉+RSI超卖",
            "indicators": ["KDJ", "RSI"],
            "signal_logic": "AND",
            "conditions": [
                {"indicator": "KDJ_K", "operator": ">", "value": 80},
                {"indicator": "RSI", "operator": "<", "value": 30},
            ],
            "aggregation": {
                "dimension": "industry",
                "min_stocks": 3,
                "time_window_minutes": 60,
            },
        }

        resp = flask_client.post(
            "/api/strategy/groups",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == 1
        assert data["status"] == "active"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_create_group_invalid_body(self, mock_db, flask_client):
        """POST /api/strategy/groups — 无效请求体返回 400"""
        resp = flask_client.post(
            "/api/strategy/groups",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_update_group(self, mock_db, flask_client, sample_group):
        """PUT /api/strategy/groups/1 — 更新策略组"""
        updated = {**sample_group, "name": "新名称"}
        mock_db.get_strategy_group.side_effect = [sample_group, updated]
        mock_db.update_strategy_group.return_value = True

        resp = flask_client.put(
            "/api/strategy/groups/1",
            data=json.dumps({"name": "新名称"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "新名称"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_update_group_not_found(self, mock_db, flask_client):
        """PUT /api/strategy/groups/999 — 不存在返回 404"""
        mock_db.get_strategy_group.return_value = None

        resp = flask_client.put(
            "/api/strategy/groups/999",
            data=json.dumps({"name": "x"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_delete_group(self, mock_db, flask_client, sample_group):
        """DELETE /api/strategy/groups/1 — 软删除"""
        archived = {**sample_group, "status": "archived"}
        mock_db.soft_delete_strategy_group.return_value = True
        mock_db.get_strategy_group.return_value = archived

        resp = flask_client.delete("/api/strategy/groups/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "archived"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_delete_group_not_found(self, mock_db, flask_client):
        """DELETE /api/strategy/groups/999 — 不存在返回 404"""
        mock_db.soft_delete_strategy_group.return_value = True
        mock_db.get_strategy_group.return_value = None

        resp = flask_client.delete("/api/strategy/groups/999")
        assert resp.status_code == 404

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_toggle_status(self, mock_db, flask_client, sample_group):
        """PATCH /api/strategy/groups/1/status — 切换状态"""
        paused = {**sample_group, "status": "paused"}
        mock_db.get_strategy_group.side_effect = [sample_group, paused]
        mock_db.update_strategy_group_status.return_value = True

        resp = flask_client.patch(
            "/api/strategy/groups/1/status",
            data=json.dumps({"status": "paused"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "paused"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_toggle_status_not_found(self, mock_db, flask_client):
        """PATCH 不存在的策略组返回 404"""
        mock_db.get_strategy_group.return_value = None

        resp = flask_client.patch(
            "/api/strategy/groups/999/status",
            data=json.dumps({"status": "paused"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_toggle_status_invalid(self, mock_db, flask_client, sample_group):
        """PATCH 非法状态值返回 400"""
        mock_db.get_strategy_group.return_value = sample_group

        resp = flask_client.patch(
            "/api/strategy/groups/1/status",
            data=json.dumps({"status": "running"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_list_groups(self, mock_db, flask_client, sample_group):
        """GET /api/strategy/groups — 列表查询"""
        mock_db.list_strategy_groups.return_value = [sample_group]

        resp = flask_client.get("/api/strategy/groups")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == 1

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_list_groups_with_status_filter(self, mock_db, flask_client, sample_group):
        """GET /api/strategy/groups?status=active — 带过滤"""
        mock_db.list_strategy_groups.return_value = [sample_group]

        resp = flask_client.get("/api/strategy/groups?status=active")
        assert resp.status_code == 200

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_get_group_detail(self, mock_db, flask_client, sample_group):
        """GET /api/strategy/groups/1 — 详情"""
        mock_db.get_strategy_group.return_value = sample_group

        resp = flask_client.get("/api/strategy/groups/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["name"] == "KDJ金叉+RSI超卖"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_get_group_not_found(self, mock_db, flask_client):
        """GET /api/strategy/groups/999 — 不存在返回 404"""
        mock_db.get_strategy_group.return_value = None

        resp = flask_client.get("/api/strategy/groups/999")
        assert resp.status_code == 404


# ============================================================================
# Test: Signal Routes
# ============================================================================

class TestSignalRoutes:
    """信号路由测试"""

    @patch("compass.strategy.routes.signals.db")
    def test_query_signals(self, mock_db, flask_client):
        """GET /api/signals — 查询信号列表"""
        mock_db.query_signals.return_value = {
            "items": [{"id": 1, "stock_code": "000001"}],
            "total": 1,
        }

        resp = flask_client.get("/api/signals?strategy_group_id=1&limit=20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1

    @patch("compass.strategy.routes.signals.db")
    def test_query_signals_by_stock(self, mock_db, flask_client):
        """GET /api/signals?stock_code=000001 — 按股票查询"""
        mock_db.query_signals.return_value = {"items": [], "total": 0}

        resp = flask_client.get("/api/signals?stock_code=000001")
        assert resp.status_code == 200
        mock_db.query_signals.assert_called_once()

    @patch("compass.strategy.services.scanner.Scanner")
    def test_trigger_scan_success(self, MockScanner, flask_client):
        """POST /api/strategy/1/scan — 触发扫描"""
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = {
            "run_id": 100,
            "matched_count": 3,
            "events_created": 1,
            "duration_seconds": 1.5,
        }
        MockScanner.return_value = mock_scanner

        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["scan_run_id"] == 100
        assert data["signals_found"] == 3

    @patch("compass.strategy.services.scanner.Scanner")
    def test_trigger_scan_bad_request(self, MockScanner, flask_client):
        """POST /api/strategy/1/scan — 非活跃策略组返回 400"""
        mock_scanner = MagicMock()
        mock_scanner.scan.side_effect = ValueError("未处于 active 状态")
        MockScanner.return_value = mock_scanner

        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 400

    def test_signal_stream_sse(self, flask_client):
        """GET /api/signals/stream — SSE 流式响应"""
        resp = flask_client.get("/api/signals/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type


# ============================================================================
# Test: Event Routes
# ============================================================================

class TestEventRoutes:
    """群体事件路由测试"""

    @patch("compass.strategy.routes.events.db")
    def test_query_events(self, mock_db, flask_client):
        """GET /api/events — 查询事件列表"""
        mock_db.query_group_events.return_value = {
            "items": [{"id": 1, "dimension_value": "半导体"}],
            "total": 1,
        }

        resp = flask_client.get("/api/events")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1

    @patch("compass.strategy.routes.events.db")
    def test_query_events_with_filters(self, mock_db, flask_client):
        """GET /api/events?strategy_group_id=1&status=open — 带过滤"""
        mock_db.query_group_events.return_value = {"items": [], "total": 0}

        resp = flask_client.get("/api/events?strategy_group_id=1&status=open&limit=10")
        assert resp.status_code == 200

    @patch("compass.strategy.routes.events.db")
    def test_get_event_detail(self, mock_db, flask_client):
        """GET /api/events/1 — 事件详情"""
        mock_db.get_group_event.return_value = {
            "id": 1,
            "dimension_value": "半导体",
            "matched_stocks": [{"code": "000001", "name": "A", "buy_star": 3}],
        }

        resp = flask_client.get("/api/events/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1

    @patch("compass.strategy.routes.events.db")
    def test_get_event_not_found(self, mock_db, flask_client):
        """GET /api/events/999 — 不存在返回 404"""
        mock_db.get_group_event.return_value = None

        resp = flask_client.get("/api/events/999")
        assert resp.status_code == 404

    @patch("compass.strategy.routes.events.db")
    def test_close_event(self, mock_db, flask_client):
        """PATCH /api/events/1/close — 关闭事件"""
        mock_db.get_group_event.side_effect = [
            {"id": 1, "status": "open"},
            {"id": 1, "status": "closed"},
        ]
        mock_db.update_group_event.return_value = True

        resp = flask_client.patch("/api/events/1/close")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "closed"

    @patch("compass.strategy.routes.events.db")
    def test_close_event_not_found(self, mock_db, flask_client):
        """PATCH 不存在的事件返回 404"""
        mock_db.get_group_event.return_value = None

        resp = flask_client.patch("/api/events/999/close")
        assert resp.status_code == 404


# ============================================================================
# Test: Industry Sync Routes
# ============================================================================

class TestIndustrySyncRoutes:
    """行业同步路由测试"""

    @patch("compass.strategy.routes.industry_sync.get_sync_status")
    @patch("compass.strategy.routes.industry_sync.sync_industry_data")
    def test_trigger_sync_starts_thread(self, mock_sync, mock_status, flask_client):
        """POST /api/admin/industry/sync — 后台启动返回 202"""
        mock_status.return_value = {"running": False}

        resp = flask_client.post("/api/admin/industry/sync")
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["message"] == "同步任务已启动"

    @patch("compass.strategy.routes.industry_sync.get_sync_status")
    def test_trigger_sync_already_running(self, mock_status, flask_client):
        """POST /api/admin/industry/sync — 同步进行中返回 200"""
        mock_status.return_value = {"running": True}

        resp = flask_client.post("/api/admin/industry/sync")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "同步正在进行中" in data["message"]

    @patch("compass.strategy.routes.industry_sync.get_sync_status")
    def test_sync_status(self, mock_status, flask_client):
        """GET /api/admin/industry/sync/status"""
        mock_status.return_value = {"running": False, "last_sync": "2025-01-15"}

        resp = flask_client.get("/api/admin/industry/sync/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False

    @patch("compass.strategy.routes.industry_sync.get_industry_stats")
    def test_industry_stats(self, mock_stats, flask_client):
        """GET /api/admin/industry/stats"""
        mock_stats.return_value = [{"industry": "银行", "count": 42}]

        resp = flask_client.get("/api/admin/industry/stats")
        assert resp.status_code == 200

    @patch("compass.strategy.routes.industry_sync.get_industry_status")
    def test_industry_completion_status(self, mock_status, flask_client):
        """GET /api/admin/industry/status"""
        mock_status.return_value = {"total": 5000, "has_industry": 4000, "completion_rate": 80.0}

        resp = flask_client.get("/api/admin/industry/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 5000


# ============================================================================
# Test: Pydantic Models — Validation (unchanged by migration)
# ============================================================================

class TestPydanticModels:
    """Pydantic 模型校验测试（不受迁移影响）"""

    def test_create_group_missing_name(self):
        from compass.strategy.models import StrategyGroupCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            StrategyGroupCreate(
                indicators=["KDJ"],
                signal_logic="AND",
                conditions=[{"indicator": "KDJ_K", "operator": ">", "value": 80}],
                aggregation={"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
            )
        assert "name" in str(exc_info.value)

    def test_create_group_invalid_signal_logic(self):
        from compass.strategy.models import StrategyGroupCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StrategyGroupCreate(
                name="test",
                indicators=["KDJ"],
                signal_logic="XOR",
                conditions=[{"indicator": "KDJ_K", "operator": ">", "value": 80}],
                aggregation={"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
            )

    def test_create_group_valid(self):
        from compass.strategy.models import StrategyGroupCreate

        body = StrategyGroupCreate(
            name="test",
            indicators=["KDJ", "RSI"],
            signal_logic="SCORING",
            conditions=[
                {"indicator": "KDJ_K", "operator": ">", "value": 80},
                {"indicator": "RSI", "operator": "<", "value": 30},
            ],
            aggregation={"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
            scoring_threshold=2,
        )
        assert body.name == "test"
        assert body.signal_logic == "SCORING"
