"""策略组页面路由上下文数据测试

验证所有策略组页面路由正确传递 is_admin 和 event 完整字段。
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_event():
    """示例群体事件数据 — 包含完整 LLM 字段"""
    return {
        "id": 42,
        "strategy_group_id": 1,
        "run_id": 100,
        "dimension": "industry",
        "dimension_value": "半导体",
        "stock_count": 8,
        "avg_buy_star": 0.75,
        "max_buy_star": 5,
        "matched_stocks": [
            {"code": "000001", "name": "A", "buy_star": 5},
            {"code": "000002", "name": "B", "buy_star": 4},
        ],
        "status": "open",
        "lifecycle": "tracking",
        "llm_keywords": ["半导体", "芯片", "AI"],
        "llm_summary": "## 半导体板块分析\n近期半导体板块表现强势...",
        "llm_confidence": 0.82,
        "llm_drivers": ["政策利好", "需求增长"],
        "llm_related_themes": ["人工智能", "国产替代"],
        "news_confirmed": True,
        "news_confirm_score": 0.65,
        "news_matched": [{"title": "半导体政策", "source": "新浪"}],
        "suggest_close_reason": None,
        "closed_at": None,
        "closed_by": None,
        "window_start": "2025-01-13 00:00:00",
        "window_end": "2025-01-20 00:00:00",
        "created_at": datetime.datetime(2025, 1, 15, 10, 0, 0),
        "updated_at": "2025-01-15 12:00:00",
    }


@pytest.fixture
def sample_group():
    """示例策略组数据"""
    return {
        "id": 1,
        "name": "行业动量策略",
        "indicators": ["KDJ", "RSI"],
        "signal_logic": "AND",
        "conditions": [],
        "scoring_threshold": None,
        "aggregation": {"dimension": "industry", "min_stocks": 3},
        "scan_cron": "0 15 * * 1-5",
        "status": "active",
        "created_at": "2025-01-15 10:00:00",
        "updated_at": "2025-01-15 10:00:00",
    }


# ============================================================================
# Helpers — mock session + render_template to verify template context
# ============================================================================

def _patch_session(uid=1, name="admin_user"):
    """返回一个 mock session dict patch"""
    return patch(
        "compass.strategy.routes.strategy_pages.session",
        {"uid": uid, "name": name, "last_activity": datetime.datetime.now().timestamp()},
    )


# ============================================================================
# Test: is_admin top-level variable in all routes
# ============================================================================

class TestIsAdminPassedToAllRoutes:
    """验证所有路由传递 is_admin 作为顶级模板变量"""

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=True)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_discover_passes_is_admin_true(self, mock_render, mock_db, mock_admin):
        """策略发现页传递 is_admin=True"""
        mock_render.return_value = "ok"
        mock_db.list_strategy_groups_with_subscription.return_value = []
        mock_db.query_group_events.return_value = {"total": 0}

        with _patch_session(uid=1, name="admin_user"):
            from compass.strategy.routes.strategy_pages import discover
            discover()

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is True

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_discover_passes_is_admin_false(self, mock_render, mock_db, mock_admin):
        """策略发现页传递 is_admin=False"""
        mock_render.return_value = "ok"
        mock_db.list_strategy_groups_with_subscription.return_value = []
        mock_db.query_group_events.return_value = {"total": 0}

        with _patch_session(uid=2, name="normal_user"):
            from compass.strategy.routes.strategy_pages import discover
            discover()

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is False

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_my_strategies_passes_is_admin(self, mock_render, mock_db, mock_admin):
        """我的策略页传递 is_admin"""
        mock_render.return_value = "ok"
        mock_db.list_user_subscriptions.return_value = []

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import my_strategies
            my_strategies()

        call_kwargs = mock_render.call_args
        assert "is_admin" in call_kwargs[1]

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=True)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_detail_passes_is_admin(self, mock_render, mock_db, mock_admin, sample_event, sample_group):
        """事件详情页传递 is_admin"""
        mock_render.return_value = "ok"
        mock_db.get_group_event.return_value = sample_event
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=1):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(42)

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is True

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=True)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_admin_list_passes_is_admin(self, mock_render, mock_db, mock_admin):
        """管理员列表页传递 is_admin"""
        mock_render.return_value = "ok"
        mock_db.list_strategy_groups.return_value = []
        mock_db.count_subscribers.return_value = 0

        with _patch_session(uid=1):
            from compass.strategy.routes.strategy_pages import admin_list
            admin_list()

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is True

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=True)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_admin_new_passes_is_admin(self, mock_render, mock_db, mock_admin):
        """管理员新建页传递 is_admin"""
        mock_render.return_value = "ok"

        with _patch_session(uid=1):
            from compass.strategy.routes.strategy_pages import admin_new
            admin_new()

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is True

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=True)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_admin_edit_passes_is_admin(self, mock_render, mock_db, mock_admin, sample_group):
        """管理员编辑页传递 is_admin"""
        mock_render.return_value = "ok"
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=1):
            from compass.strategy.routes.strategy_pages import admin_edit
            admin_edit(1)

        call_kwargs = mock_render.call_args
        assert call_kwargs[1]["is_admin"] is True


# ============================================================================
# Test: Event detail route passes complete LLM data
# ============================================================================

class TestEventDetailContext:
    """验证事件详情路由传递完整 event 数据（含 LLM 字段）"""

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_has_strategy_name(
        self, mock_render, mock_db, mock_admin, sample_event, sample_group
    ):
        """event 对象包含 strategy_name"""
        mock_render.return_value = "ok"
        mock_db.get_group_event.return_value = sample_event
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(42)

        event = mock_render.call_args[1]["event"]
        assert event["strategy_name"] == "行业动量策略"

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_has_llm_fields(
        self, mock_render, mock_db, mock_admin, sample_event, sample_group
    ):
        """event 对象包含所有 LLM 分析字段"""
        mock_render.return_value = "ok"
        mock_db.get_group_event.return_value = sample_event
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(42)

        event = mock_render.call_args[1]["event"]

        # LLM 分析字段
        assert event["llm_summary"] == "## 半导体板块分析\n近期半导体板块表现强势..."
        assert event["llm_confidence"] == 0.82
        assert event["llm_keywords"] == ["半导体", "芯片", "AI"]
        assert event["llm_drivers"] == ["政策利好", "需求增长"]
        assert event["llm_related_themes"] == ["人工智能", "国产替代"]

        # 消息面确认字段
        assert event["news_confirmed"] is True
        assert event["news_confirm_score"] == 0.65

        # 生命周期和维度
        assert event["lifecycle"] == "tracking"
        assert event["avg_buy_star"] == 0.75
        assert event["dimension_value"] == "半导体"

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_has_duration_days(
        self, mock_render, mock_db, mock_admin, sample_event, sample_group
    ):
        """模板上下文包含 duration_days"""
        mock_render.return_value = "ok"
        mock_db.get_group_event.return_value = sample_event
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(42)

        assert mock_render.call_args[1]["duration_days"] >= 1

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_not_found_returns_404(
        self, mock_render, mock_db, mock_admin
    ):
        """事件不存在返回 404"""
        mock_render.return_value = "not found"
        mock_db.get_group_event.return_value = None

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            result = event_detail(999)

        # Should return (response, status_code)
        assert isinstance(result, tuple)
        assert result[1] == 404

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_without_llm_data(
        self, mock_render, mock_db, mock_admin, sample_group
    ):
        """无 LLM 分析结果时 event 字段为 None"""
        mock_render.return_value = "ok"
        event_no_llm = {
            "id": 50,
            "strategy_group_id": 1,
            "dimension": "industry",
            "dimension_value": "银行",
            "stock_count": 3,
            "avg_buy_star": 0.5,
            "matched_stocks": [],
            "status": "open",
            "lifecycle": "tracking",
            "llm_keywords": None,
            "llm_summary": None,
            "llm_confidence": None,
            "llm_drivers": None,
            "llm_related_themes": None,
            "news_confirmed": None,
            "news_confirm_score": None,
            "created_at": datetime.datetime.now(),
            "window_start": "2025-01-15 00:00:00",
            "window_end": "2025-01-22 00:00:00",
        }
        mock_db.get_group_event.return_value = event_no_llm
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(50)

        event = mock_render.call_args[1]["event"]
        assert event["llm_summary"] is None
        assert event["llm_confidence"] is None
        assert event["news_confirmed"] is None

    @patch("compass.strategy.routes.strategy_pages._is_admin", return_value=False)
    @patch("compass.strategy.routes.strategy_pages.db")
    @patch("compass.strategy.routes.strategy_pages.render_template")
    def test_event_preserves_group_name(
        self, mock_render, mock_db, mock_admin, sample_event, sample_group
    ):
        """同时传递 group_name 和 event.strategy_name"""
        mock_render.return_value = "ok"
        mock_db.get_group_event.return_value = sample_event
        mock_db.get_strategy_group.return_value = sample_group

        with _patch_session(uid=2):
            from compass.strategy.routes.strategy_pages import event_detail
            event_detail(42)

        call_kwargs = mock_render.call_args[1]
        assert call_kwargs["group_name"] == "行业动量策略"
        assert call_kwargs["event"]["strategy_name"] == "行业动量策略"


# ============================================================================
# Test: Admin detection uses session + DB pattern
# ============================================================================

class TestAdminDetection:
    """验证 admin 检测逻辑复用现有 session + DB 查询模式"""

    def test_is_admin_returns_false_when_not_logged_in(self):
        """未登录时 _is_admin 返回 False"""
        with patch("compass.strategy.routes.strategy_pages.session", {}):
            from compass.strategy.routes.strategy_pages import _is_admin
            assert _is_admin() is False

    @patch("compass.strategy.routes.strategy_pages.Database")
    def test_is_admin_returns_true_for_admin_user(self, MockDB):
        """管理员用户 _is_admin 返回 True"""
        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_one.return_value = (1, {"is_admin": 1})

        with patch("compass.strategy.routes.strategy_pages.session", {"uid": 1}):
            from compass.strategy.routes.strategy_pages import _is_admin
            assert _is_admin() is True

    @patch("compass.strategy.routes.strategy_pages.Database")
    def test_is_admin_returns_false_for_normal_user(self, MockDB):
        """普通用户 _is_admin 返回 False"""
        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_one.return_value = (1, {"is_admin": 0})

        with patch("compass.strategy.routes.strategy_pages.session", {"uid": 2}):
            from compass.strategy.routes.strategy_pages import _is_admin
            assert _is_admin() is False

    @patch("compass.strategy.routes.strategy_pages.Database")
    def test_is_admin_returns_false_on_db_error(self, MockDB):
        """DB 异常时 _is_admin 返回 False"""
        MockDB.return_value.__enter__ = MagicMock(side_effect=Exception("DB error"))
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        with patch("compass.strategy.routes.strategy_pages.session", {"uid": 1}):
            from compass.strategy.routes.strategy_pages import _is_admin
            assert _is_admin() is False
