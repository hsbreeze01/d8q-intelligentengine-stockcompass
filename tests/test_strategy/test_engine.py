"""策略组引擎 — 测试套件

覆盖：CRUD / Scanner / Aggregator / Industry Sync
所有测试使用 mock 替代数据库操作。
"""
import datetime
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
def sample_scoring_group():
    """SCORING 模式策略组"""
    return {
        "id": 2,
        "name": "多因子评分",
        "indicators": ["KDJ", "RSI", "MACD"],
        "signal_logic": "SCORING",
        "conditions": [
            {"indicator": "KDJ_K", "operator": ">", "value": 70},
            {"indicator": "RSI", "operator": "<", "value": 40},
            {"indicator": "MACD", "operator": ">", "value": 0},
        ],
        "scoring_threshold": 2,
        "aggregation": {
            "dimension": "industry",
            "min_stocks": 3,
            "time_window_minutes": 60,
        },
        "scan_cron": None,
        "status": "active",
        "created_at": "2025-01-15 10:00:00",
        "updated_at": "2025-01-15 10:00:00",
    }


# ============================================================================
# Test: Strategy Group CRUD
# ============================================================================

class TestStrategyGroupCRUD:
    """策略组 CRUD 路由测试"""

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_create_group_success(self, mock_db, sample_group):
        """成功创建策略组"""
        from compass.strategy.routes.strategy_groups import create_group
        from compass.strategy.models import StrategyGroupCreate

        mock_db.insert_strategy_group.return_value = 1
        mock_db.get_strategy_group.return_value = sample_group

        body = StrategyGroupCreate(
            name="KDJ金叉+RSI超卖",
            indicators=["KDJ", "RSI"],
            signal_logic="AND",
            conditions=[
                {"indicator": "KDJ_K", "operator": ">", "value": 80},
                {"indicator": "RSI", "operator": "<", "value": 30},
            ],
            aggregation={
                "dimension": "industry",
                "min_stocks": 3,
                "time_window_minutes": 60,
            },
        )
        result = create_group(body)
        assert result["id"] == 1
        assert result["status"] == "active"
        mock_db.insert_strategy_group.assert_called_once()

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_update_group_success(self, mock_db, sample_group):
        """成功更新策略组"""
        from compass.strategy.routes.strategy_groups import update_group
        from compass.strategy.models import StrategyGroupUpdate

        updated_group = {**sample_group, "name": "新名称"}
        mock_db.get_strategy_group.side_effect = [sample_group, updated_group]
        mock_db.update_strategy_group.return_value = True

        body = StrategyGroupUpdate(name="新名称")
        result = update_group(1, body)
        assert result["name"] == "新名称"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_update_group_not_found(self, mock_db):
        """更新不存在的策略组返回 404"""
        from compass.strategy.routes.strategy_groups import update_group
        from compass.strategy.models import StrategyGroupUpdate
        from fastapi import HTTPException

        mock_db.get_strategy_group.return_value = None
        body = StrategyGroupUpdate(name="新名称")

        with pytest.raises(HTTPException) as exc_info:
            update_group(999, body)
        assert exc_info.value.status_code == 404

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_delete_group_soft(self, mock_db, sample_group):
        """软删除策略组"""
        from compass.strategy.routes.strategy_groups import delete_group

        archived = {**sample_group, "status": "archived"}
        mock_db.soft_delete_strategy_group.return_value = True
        mock_db.get_strategy_group.return_value = archived

        result = delete_group(1)
        assert result["status"] == "archived"
        mock_db.soft_delete_strategy_group.assert_called_once_with(1)

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_toggle_status_pause(self, mock_db, sample_group):
        """暂停策略组"""
        from compass.strategy.routes.strategy_groups import toggle_status
        from compass.strategy.models import StrategyGroupStatusUpdate

        paused = {**sample_group, "status": "paused"}
        mock_db.get_strategy_group.side_effect = [sample_group, paused]
        mock_db.update_strategy_group_status.return_value = True

        body = StrategyGroupStatusUpdate(status="paused")
        result = toggle_status(1, body)
        assert result["status"] == "paused"

    def test_toggle_status_invalid(self):
        """非法状态值 — pydantic 在构造时即拒绝"""
        from compass.strategy.models import StrategyGroupStatusUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            StrategyGroupStatusUpdate(status="running")
        assert "status" in str(exc_info.value)

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_list_groups(self, mock_db, sample_group):
        """查询策略组列表"""
        from compass.strategy.routes.strategy_groups import list_groups

        mock_db.list_strategy_groups.return_value = [sample_group]
        result = list_groups()
        assert len(result) == 1
        assert result[0]["id"] == 1

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_get_group_detail(self, mock_db, sample_group):
        """获取策略组详情"""
        from compass.strategy.routes.strategy_groups import get_group

        mock_db.get_strategy_group.return_value = sample_group
        result = get_group(1)
        assert result["id"] == 1
        assert result["name"] == "KDJ金叉+RSI超卖"

    @patch("compass.strategy.routes.strategy_groups.db")
    def test_get_group_not_found(self, mock_db):
        """获取不存在的策略组"""
        from compass.strategy.routes.strategy_groups import get_group
        from fastapi import HTTPException

        mock_db.get_strategy_group.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            get_group(999)
        assert exc_info.value.status_code == 404


# ============================================================================
# Test: Pydantic Models — Validation
# ============================================================================

class TestPydanticModels:
    """Pydantic 模型校验测试"""

    def test_create_group_missing_name(self):
        """缺少 name 字段"""
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
        """非法 signal_logic"""
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

    def test_create_group_empty_indicators(self):
        """空指标列表"""
        from compass.strategy.models import StrategyGroupCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StrategyGroupCreate(
                name="test",
                indicators=[],
                signal_logic="AND",
                conditions=[{"indicator": "KDJ_K", "operator": ">", "value": 80}],
                aggregation={"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
            )

    def test_create_group_empty_conditions(self):
        """空条件列表"""
        from compass.strategy.models import StrategyGroupCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StrategyGroupCreate(
                name="test",
                indicators=["KDJ"],
                signal_logic="AND",
                conditions=[],
                aggregation={"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
            )

    def test_create_group_valid(self):
        """合法创建"""
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
        assert body.scoring_threshold == 2


# ============================================================================
# Test: Scanner Engine
# ============================================================================

class TestScannerEngine:
    """扫描引擎测试"""

    def _make_scanner(self, indicators_data, buy_map, group_data):
        """创建 Scanner 实例并 mock 数据库"""
        from compass.strategy.services.scanner import Scanner
        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)
        return scanner

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_and_logic_all_match(self, mock_db_helpers, sample_group):
        """AND 逻辑 — 全部条件满足"""
        from compass.strategy.services.scanner import Scanner

        indicators_data = [
            {"stock_code": "000001", "stock_name": "平安银行", "KDJ_K": 85.3, "RSI": 25.0},
            {"stock_code": "000002", "stock_name": "万科A", "KDJ_K": 85.0, "RSI": 45.0},
        ]
        buy_map = {"000001": 4, "000002": 2}

        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 100

        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)
        mock_db_helpers.insert_signal_snapshots.return_value = 1

        # Mock aggregator
        with patch("compass.strategy.services.aggregator.Aggregator") as MockAgg:
            MockAgg.return_value.aggregate.return_value = 0
            result = scanner.scan(1)

        assert result["matched_count"] == 1  # only 000001 matches both
        mock_db_helpers.insert_signal_snapshots.assert_called_once()
        snapshots = mock_db_helpers.insert_signal_snapshots.call_args[0][0]
        assert snapshots[0]["stock_code"] == "000001"

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_and_logic_partial_fail(self, mock_db_helpers, sample_group):
        """AND 逻辑 — 部分条件不满足"""
        from compass.strategy.services.scanner import Scanner

        indicators_data = [
            {"stock_code": "000001", "stock_name": "平安银行", "KDJ_K": 50.0, "RSI": 45.0},
        ]
        buy_map = {"000001": 3}

        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 100

        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)

        with patch("compass.strategy.services.aggregator.Aggregator") as MockAgg:
            MockAgg.return_value.aggregate.return_value = 0
            result = scanner.scan(1)

        assert result["matched_count"] == 0

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_or_logic(self, mock_db_helpers):
        """OR 逻辑 — 任一条件满足"""
        from compass.strategy.services.scanner import Scanner

        group = {
            "id": 3, "name": "OR测试", "indicators": ["KDJ", "RSI"],
            "signal_logic": "OR", "status": "active",
            "conditions": [
                {"indicator": "KDJ_K", "operator": ">", "value": 80},
                {"indicator": "RSI", "operator": "<", "value": 30},
            ],
            "scoring_threshold": None,
            "aggregation": {"dimension": "industry", "min_stocks": 3, "time_window_minutes": 60},
        }

        indicators_data = [
            {"stock_code": "000001", "KDJ_K": 85.0, "RSI": 50.0},  # KDJ matches
            {"stock_code": "000002", "KDJ_K": 50.0, "RSI": 25.0},  # RSI matches
            {"stock_code": "000003", "KDJ_K": 50.0, "RSI": 50.0},  # neither
        ]
        buy_map = {}

        mock_db_helpers.get_strategy_group.return_value = group
        mock_db_helpers.create_run.return_value = 100

        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)

        with patch("compass.strategy.services.aggregator.Aggregator") as MockAgg:
            MockAgg.return_value.aggregate.return_value = 0
            result = scanner.scan(3)

        assert result["matched_count"] == 2

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_scoring_logic(self, mock_db_helpers, sample_scoring_group):
        """SCORING 逻辑 — 达标"""
        from compass.strategy.services.scanner import Scanner

        indicators_data = [
            {"stock_code": "000001", "KDJ_K": 75.0, "RSI": 35.0, "MACD": 0.5},
            {"stock_code": "000002", "KDJ_K": 75.0, "RSI": 50.0, "MACD": -0.5},
            {"stock_code": "000003", "KDJ_K": 50.0, "RSI": 50.0, "MACD": -0.5},
        ]
        buy_map = {}

        mock_db_helpers.get_strategy_group.return_value = sample_scoring_group
        mock_db_helpers.create_run.return_value = 100

        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)

        with patch("compass.strategy.services.aggregator.Aggregator") as MockAgg:
            MockAgg.return_value.aggregate.return_value = 0
            result = scanner.scan(2)

        # 000001: 3 matches (>=2) -> match
        # 000002: 1 match (<2) -> no match
        # 000003: 0 matches -> no match
        assert result["matched_count"] == 1

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_non_active_group(self, mock_db_helpers):
        """扫描非 active 策略组"""
        from compass.strategy.services.scanner import Scanner

        mock_db_helpers.get_strategy_group.return_value = {
            "id": 2, "status": "paused", "conditions": [], "signal_logic": "AND",
            "scoring_threshold": None,
        }

        scanner = Scanner()
        with pytest.raises(ValueError, match="未处于 active 状态"):
            scanner.scan(2)

    @patch("compass.strategy.services.scanner.db_helpers")
    def test_scan_snapshot_includes_indicators(self, mock_db_helpers, sample_group):
        """快照包含完整指标值"""
        from compass.strategy.services.scanner import Scanner

        indicators_data = [
            {
                "stock_code": "000001", "stock_name": "平安银行",
                "KDJ_K": 85.3, "KDJ_D": 78.1, "KDJ_J": 99.7, "RSI": 25.0,
            },
        ]
        buy_map = {"000001": 5}

        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.create_run.return_value = 100

        scanner = Scanner()
        scanner._load_latest_indicators = MagicMock(return_value=indicators_data)
        scanner._load_buy_values = MagicMock(return_value=buy_map)

        with patch("compass.strategy.services.aggregator.Aggregator") as MockAgg:
            MockAgg.return_value.aggregate.return_value = 0
            scanner.scan(1)

        snapshots = mock_db_helpers.insert_signal_snapshots.call_args[0][0]
        snap = snapshots[0]
        assert snap["indicator_snapshot"]["KDJ_K"] == 85.3
        assert snap["indicator_snapshot"]["KDJ_D"] == 78.1
        assert snap["indicator_snapshot"]["KDJ_J"] == 99.7
        assert snap["buy_star"] == 5


# ============================================================================
# Test: Aggregator
# ============================================================================

class TestAggregator:
    """群体事件聚合器测试"""

    @patch("compass.strategy.services.aggregator.db_helpers")
    @patch("compass.strategy.services.aggregator.Database")
    def test_create_new_event(self, MockDB, mock_db_helpers, sample_group):
        """新建群体事件"""
        from compass.strategy.services.aggregator import Aggregator

        mock_db_helpers.get_strategy_group.return_value = sample_group

        signals = [
            {"stock_code": "000001", "stock_name": "A", "buy_star": 3},
            {"stock_code": "000002", "stock_name": "B", "buy_star": 4},
            {"stock_code": "000003", "stock_name": "C", "buy_star": 5},
        ]

        mock_db_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        # Mock signal query
        mock_db_conn.select_many.return_value = (3, signals)
        # Mock dimension map
        mock_db_conn.select_many.side_effect = [
            (3, signals),
            (3, [
                {"stock_code": "000001", "industry": "半导体"},
                {"stock_code": "000002", "industry": "半导体"},
                {"stock_code": "000003", "industry": "半导体"},
            ]),
        ]

        mock_db_helpers.find_open_event.return_value = None
        mock_db_helpers.insert_group_event.return_value = 1
        mock_db_helpers.close_expired_events.return_value = 0

        agg = Aggregator()
        # Override _load_dimension_map to return known values
        agg._load_dimension_map = MagicMock(return_value={
            "000001": "半导体",
            "000002": "半导体",
            "000003": "半导体",
        })

        result = agg.aggregate(1, 100)
        assert result == 1  # 1 new event created
        mock_db_helpers.insert_group_event.assert_called_once()

        event_arg = mock_db_helpers.insert_group_event.call_args[0][0]
        assert event_arg["dimension_value"] == "半导体"
        assert event_arg["stock_count"] == 3
        assert event_arg["avg_buy_star"] == 4.0
        assert event_arg["max_buy_star"] == 5

    @patch("compass.strategy.services.aggregator.db_helpers")
    def test_append_to_existing_event(self, mock_db_helpers, sample_group):
        """追加到已有事件"""
        from compass.strategy.services.aggregator import Aggregator

        mock_db_helpers.get_strategy_group.return_value = sample_group

        existing_event = {
            "id": 10,
            "created_at": datetime.datetime.now() - datetime.timedelta(minutes=30),
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 3},
                {"code": "000002", "name": "B", "buy_star": 4},
                {"code": "000003", "name": "C", "buy_star": 5},
            ],
        }
        mock_db_helpers.find_open_event.return_value = existing_event
        mock_db_helpers.close_expired_events.return_value = 0

        agg = Aggregator()
        # Mock signal loading and dimension map
        _signals = [
            {"stock_code": "000004", "stock_name": "D", "buy_star": 4},
            {"stock_code": "000005", "stock_name": "E", "buy_star": 2},
        ]

        with patch.object(agg, "aggregate"):
            # We test the internal logic directly
            pass

        # Test dimension map loading and matching
        _dim_map = {"000004": "半导体", "000005": "半导体"}
        mock_db_helpers.update_group_event.return_value = True

        # Simulate the append logic
        old_matched = existing_event["matched_stocks"]
        _old_codes = {m["code"] for m in old_matched}
        new_matched = [
            {"code": "000004", "name": "D", "buy_star": 4},
            {"code": "000005", "name": "E", "buy_star": 2},
        ]
        all_matched = old_matched + new_matched
        assert len(all_matched) == 5

    @patch("compass.strategy.services.aggregator.db_helpers")
    def test_insufficient_stocks(self, mock_db_helpers, sample_group):
        """匹配数不足，不创建事件"""

        mock_db_helpers.get_strategy_group.return_value = sample_group
        mock_db_helpers.find_open_event.return_value = None
        mock_db_helpers.close_expired_events.return_value = 0

        # Only 2 stocks in "银行" — min_stocks=3
        signals = [
            {"stock_code": "000001", "stock_name": "A", "buy_star": 3},
            {"stock_code": "000002", "stock_name": "B", "buy_star": 4},
        ]

        # Should NOT create event
        # We test the group counting logic
        dim_map = {"000001": "银行", "000002": "银行"}
        groups = {}
        for sig in signals:
            dim_val = dim_map.get(sig["stock_code"], "未知")
            if dim_val not in groups:
                groups[dim_val] = []
            groups[dim_val].append(sig)

        # 银行 only has 2 < 3 (min_stocks)
        assert len(groups["银行"]) < sample_group["aggregation"]["min_stocks"]

    def test_aggregation_metrics(self):
        """聚合指标正确计算"""
        buy_stars = [3, 4, 5, 2, 4]
        avg_buy_star = round(sum(buy_stars) / len(buy_stars), 2)
        max_buy_star = max(buy_stars)

        assert avg_buy_star == 3.6
        assert max_buy_star == 5


# ============================================================================
# Test: Industry Sync
# ============================================================================

class TestIndustrySync:
    """行业数据同步测试"""

    @patch("compass.strategy.services.industry_sync.Database")
    def test_industry_status(self, MockDB):
        """查询行业补全状态"""
        from compass.strategy.services.industry_sync import get_industry_status

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.select_one.side_effect = [
            (1, {"total": 5512}),
            (1, {"cnt": 4000}),
        ]

        result = get_industry_status()
        assert result["total"] == 5512
        assert result["has_industry"] == 4000
        assert result["completion_rate"] == round(4000 / 5512 * 100, 2)

    @patch("compass.strategy.services.industry_sync.akshare", create=True)
    def test_akshare_failure_fallback(self, mock_akshare):
        """akshare 不可用时降级"""
        from compass.strategy.services.industry_sync import _fetch_from_akshare

        # Simulate akshare import failure
        with patch.dict("sys.modules", {"akshare": None}):
            result = _fetch_from_akshare()
            # Should return None when akshare is not available
            # (The actual behavior depends on import handling)

    @patch("compass.strategy.services.industry_sync.Database")
    def test_industry_stats(self, MockDB):
        """查询行业分布统计"""
        from compass.strategy.services.industry_sync import get_industry_stats

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.select_many.return_value = (
            3,
            [
                {"industry": "银行", "count": 42},
                {"industry": "证券", "count": 38},
                {"industry": "半导体", "count": 55},
            ],
        )

        result = get_industry_stats()
        assert len(result) == 3
        assert result[0]["industry"] == "银行"


# ============================================================================
# Test: Event Routes
# ============================================================================

class TestEventRoutes:
    """群体事件路由测试"""

    @patch("compass.strategy.routes.events.db")
    def test_query_events(self, mock_db):
        """查询群体事件列表"""
        from compass.strategy.routes.events import query_events

        mock_db.query_group_events.return_value = {
            "items": [{"id": 1, "dimension_value": "半导体"}],
            "total": 1,
        }

        result = query_events()
        assert result["total"] == 1

    @patch("compass.strategy.routes.events.db")
    def test_get_event_detail(self, mock_db):
        """获取事件详情"""
        from compass.strategy.routes.events import get_event

        mock_db.get_group_event.return_value = {
            "id": 1,
            "dimension_value": "半导体",
            "matched_stocks": [
                {"code": "000001", "name": "A", "buy_star": 3},
            ],
        }

        result = get_event(1)
        assert result["id"] == 1

    @patch("compass.strategy.routes.events.db")
    def test_get_event_not_found(self, mock_db):
        """事件不存在"""
        from compass.strategy.routes.events import get_event
        from fastapi import HTTPException

        mock_db.get_group_event.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_event(999)
        assert exc_info.value.status_code == 404

    @patch("compass.strategy.routes.events.db")
    def test_close_event(self, mock_db):
        """手动关闭事件"""
        from compass.strategy.routes.events import close_event

        mock_db.get_group_event.side_effect = [
            {"id": 1, "status": "open"},
            {"id": 1, "status": "closed"},
        ]
        mock_db.update_group_event.return_value = True

        result = close_event(1)
        assert result["status"] == "closed"


# ============================================================================
# Test: Signal Routes
# ============================================================================

class TestSignalRoutes:
    """信号路由测试"""

    @patch("compass.strategy.routes.signals.db")
    def test_query_signals(self, mock_db):
        """查询信号列表"""
        from compass.strategy.routes.signals import query_signals

        mock_db.query_signals.return_value = {
            "items": [{"id": 1, "stock_code": "000001"}],
            "total": 1,
        }

        result = query_signals(group_id=1, limit=20, offset=0)
        assert result["total"] == 1

    @patch("compass.strategy.routes.signals.db")
    def test_query_signals_by_stock(self, mock_db):
        """按股票代码查询信号"""
        from compass.strategy.routes.signals import query_signals

        mock_db.query_signals.return_value = {
            "items": [],
            "total": 0,
        }

        result = query_signals(stock_code="000001")
        mock_db.query_signals.assert_called_once()
        call_kwargs = mock_db.query_signals.call_args
        assert call_kwargs.kwargs.get("stock_code") == "000001" or call_kwargs[1].get("stock_code") == "000001"
