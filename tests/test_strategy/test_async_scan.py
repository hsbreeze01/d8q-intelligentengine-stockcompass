"""策略扫描异步化 — 集成测试

覆盖：
- 扫描触发返回 202 + run_id
- 扫描期间其他 API 不阻塞
- LLM 分析失败不影响聚合结果
- stale running 记录清理逻辑
"""
import datetime
import threading
import time
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
# Test: Async scan trigger returns 202
# ============================================================================

class TestAsyncScanTrigger:
    """测试异步扫描触发"""

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_scan_returns_202_with_run_id(self, mock_db_helpers, flask_client, sample_group):
        """POST /scan 返回 202 + run_id + status=running"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 42

        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["run_id"] == 42
        assert data["status"] == "running"

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_scan_returns_quickly(self, mock_db_helpers, flask_client, sample_group):
        """扫描触发在 3 秒内返回"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 1

        start = time.time()
        resp = flask_client.post("/api/strategy/1/scan")
        elapsed = time.time() - start
        assert resp.status_code == 202
        assert elapsed < 3.0

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_scan_nonexistent_group_returns_400(self, mock_db_helpers, flask_client):
        """策略组不存在返回 400"""
        mock_db_helpers.get_strategy_group.return_value = None

        resp = flask_client.post("/api/strategy/999/scan")
        assert resp.status_code == 400

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_scan_inactive_group_returns_400(self, mock_db_helpers, flask_client):
        """非 active 策略组返回 400"""
        group = {"id": 1, "name": "test", "status": "paused"}
        mock_db_helpers.get_strategy_group.return_value = group

        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 400

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_other_api_not_blocked_during_scan(self, mock_db_helpers, flask_client, sample_group):
        """扫描期间其他 API 正常可用"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 1

        # 触发扫描
        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 202

        # 立即查询信号，应正常返回
        with patch("compass.strategy.routes.signals.db") as mock_db:
            mock_db.query_signals.return_value = {"items": [], "total": 0}
            resp2 = flask_client.get("/api/signals?strategy_group_id=1")
            assert resp2.status_code == 200


# ============================================================================
# Test: Background scan completion and failure
# ============================================================================

class TestBackgroundScanExecution:
    """测试后台扫描执行"""

    @patch("compass.strategy.routes.signals.Scanner")
    def test_background_scan_updates_run_completed(self, MockScanner, sample_group):
        """后台扫描完成后 run 状态更新为 completed"""
        scanner_instance = MagicMock()
        scanner_instance.scan.return_value = {
            "run_id": 42,
            "matched_count": 5,
            "total_stocks": 100,
            "duration_seconds": 3.5,
            "events_created": 1,
        }
        MockScanner.return_value = scanner_instance

        with patch("compass.strategy.routes.signals.db_helpers") as mock_db_helpers:
            from compass.strategy.routes.signals import _run_scan_background
            _run_scan_background(1, 42)

            scanner_instance.scan.assert_called_once_with(1, run_id=42, skip_llm=True)
            mock_db_helpers.update_run.assert_called()
            call_kwargs = mock_db_helpers.update_run.call_args[1]
            assert call_kwargs.get("status") == "completed"
            assert call_kwargs.get("matched_stocks") == 5
            assert call_kwargs.get("total_stocks") == 100

    @patch("compass.strategy.routes.signals.Scanner")
    def test_background_scan_failure_updates_run_failed(self, MockScanner, sample_group):
        """后台扫描失败时 run 状态更新为 failed"""
        scanner_instance = MagicMock()
        scanner_instance.scan.side_effect = RuntimeError("DB connection lost")
        MockScanner.return_value = scanner_instance

        with patch("compass.strategy.routes.signals.db_helpers") as mock_db_helpers:
            from compass.strategy.routes.signals import _run_scan_background
            _run_scan_background(1, 42)

            calls = mock_db_helpers.update_run.call_args_list
            failed_calls = [c for c in calls if c[1].get("status") == "failed"]
            assert len(failed_calls) > 0
            assert "error_message" in failed_calls[0][1]
            assert "DB connection lost" in failed_calls[0][1]["error_message"]


# ============================================================================
# Test: Scanner run_id reuse and skip_llm
# ============================================================================

class TestScannerParams:
    """测试 Scanner 新参数"""

    @patch("compass.strategy.services.scanner.db_helpers")
    @patch("compass.strategy.services.scanner.Database")
    def test_scan_reuses_run_id(self, MockDB, mock_db_helpers, sample_group):
        """scan(run_id=42) 复用已有 run 记录"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.update_run.return_value = True
        mock_db_helpers.insert_signal_snapshots.return_value = 0

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_one.return_value = (1, {"latest": None})

        from compass.strategy.services.scanner import Scanner
        scanner = Scanner()
        result = scanner.scan(1, run_id=42)

        # Should NOT call create_run since run_id was provided
        mock_db_helpers.create_run.assert_not_called()
        assert result["run_id"] == 42

    @patch("compass.strategy.services.scanner.db_helpers")
    @patch("compass.strategy.services.scanner.Database")
    def test_scan_creates_run_when_none(self, MockDB, mock_db_helpers, sample_group):
        """scan() 不传 run_id 时自动创建"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 99
        mock_db_helpers.update_run.return_value = True
        mock_db_helpers.insert_signal_snapshots.return_value = 0

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_one.return_value = (1, {"latest": None})

        from compass.strategy.services.scanner import Scanner
        scanner = Scanner()
        result = scanner.scan(1)

        mock_db_helpers.create_run.assert_called_once()
        assert result["run_id"] == 99

    @patch("compass.strategy.services.scanner.db_helpers")
    @patch("compass.strategy.services.scanner.Database")
    def test_scan_skip_llm_passed_to_aggregator(self, MockDB, mock_db_helpers, sample_group):
        """skip_llm=True 传递给 Aggregator"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.update_run.return_value = True
        mock_db_helpers.insert_signal_snapshots.return_value = 0

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_one.return_value = (1, {"latest": None})

        with patch("compass.strategy.services.scanner.Aggregator") as MockAgg:
            agg_instance = MagicMock()
            agg_instance.aggregate.return_value = 0
            MockAgg.return_value = agg_instance

            from compass.strategy.services.scanner import Scanner
            scanner = Scanner()
            scanner.scan(1, run_id=42, skip_llm=True)

            agg_instance.aggregate.assert_called_once_with(1, 42, skip_llm=True)


# ============================================================================
# Test: Aggregator skip_llm and fire-and-forget LLM
# ============================================================================

class TestAggregatorAsync:
    """测试聚合器异步改造"""

    @patch("compass.strategy.services.aggregator.db_helpers")
    @patch("compass.strategy.services.aggregator.Database")
    def test_aggregate_skip_llm_no_thread(self, MockDB, mock_db_helpers, sample_group):
        """skip_llm=True 时不启动 LLM 线程"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.find_open_event.return_value = None
        mock_db_helpers.insert_group_event.return_value = 1
        mock_db_helpers.update_event_lifecycle.return_value = True
        mock_db_helpers.close_expired_events.return_value = 0

        signals = [
            {"stock_code": "000001", "stock_name": "A", "buy_star": 3},
            {"stock_code": "000002", "stock_name": "B", "buy_star": 4},
            {"stock_code": "000003", "stock_name": "C", "buy_star": 5},
        ]
        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_many.return_value = (3, signals)

        from compass.strategy.services.aggregator import Aggregator
        agg = Aggregator()
        agg._load_dimension_map = MagicMock(return_value={
            "000001": "半导体",
            "000002": "半导体",
            "000003": "半导体",
        })

        with patch.object(agg, "_trigger_llm_analysis") as mock_trigger:
            result = agg.aggregate(1, 100, skip_llm=True)
            mock_trigger.assert_not_called()

    @patch("compass.strategy.services.aggregator.db_helpers")
    @patch("compass.strategy.services.aggregator.Database")
    def test_aggregate_without_skip_triggers_llm(self, MockDB, mock_db_helpers, sample_group):
        """skip_llm=False（默认）时启动 LLM 分析"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.find_open_event.return_value = None
        mock_db_helpers.insert_group_event.return_value = 1
        mock_db_helpers.update_event_lifecycle.return_value = True
        mock_db_helpers.close_expired_events.return_value = 0

        signals = [
            {"stock_code": "000001", "stock_name": "A", "buy_star": 3},
            {"stock_code": "000002", "stock_name": "B", "buy_star": 4},
            {"stock_code": "000003", "stock_name": "C", "buy_star": 5},
        ]
        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.select_many.return_value = (3, signals)

        from compass.strategy.services.aggregator import Aggregator
        agg = Aggregator()
        agg._load_dimension_map = MagicMock(return_value={
            "000001": "半导体",
            "000002": "半导体",
            "000003": "半导体",
        })

        with patch.object(agg, "_trigger_llm_analysis") as mock_trigger:
            result = agg.aggregate(1, 100, skip_llm=False)
            mock_trigger.assert_called_once_with(1)

    def test_trigger_llm_analysis_starts_daemon_thread(self):
        """_trigger_llm_analysis 启动 daemon 线程"""
        from compass.strategy.services.aggregator import Aggregator
        agg = Aggregator()

        started_threads = []
        original_init = threading.Thread.__init__

        def capture_thread(self_t, *args, **kwargs):
            original_init(self_t, *args, **kwargs)
            started_threads.append(self_t)

        with patch.object(threading.Thread, "__init__", capture_thread):
            with patch.object(threading.Thread, "start"):
                agg._trigger_llm_analysis(42)

        assert len(started_threads) == 1
        assert started_threads[0].daemon is True

    def test_llm_analyze_sync_handles_exception(self):
        """LLM 分析失败不影响聚合（_llm_analyze_sync 捕获异常）"""
        from compass.strategy.services.aggregator import Aggregator
        agg = Aggregator()

        with patch("compass.strategy.services.aggregator.LLMExtractor", create=True):
            # Patch the import inside _llm_analyze_sync
            with patch("compass.strategy.services.llm_extractor.LLMExtractor") as MockExt:
                MockExt.side_effect = RuntimeError("API timeout")
                # Should not raise
                agg._llm_analyze_sync(1)


# ============================================================================
# Test: Stale running records cleanup
# ============================================================================

class TestStaleRunCleanup:
    """测试 stale running 记录清理"""

    @patch("compass.strategy.routes.signals.db_helpers")
    def test_scan_creates_run_record(self, mock_db_helpers, flask_client, sample_group):
        """触发扫描时确实创建了 run 记录"""
        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 100

        resp = flask_client.post("/api/strategy/1/scan")
        assert resp.status_code == 202

        mock_db_helpers.create_run.assert_called_once_with(1, trigger_type="manual")
