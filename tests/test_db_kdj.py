"""Unit tests for KDJDaily — stockfetch/db_kdj.py"""
import datetime
import inspect
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeValue:
    """Mimics funcat's Value wrapper used in KDJ / DATETIME arrays."""

    def __init__(self, v):
        self.value = v


def _make_mock_pool():
    """Return a MagicMock that behaves like PooledDB returning a mock conn."""
    pool = MagicMock(name="PooledDB")
    conn = MagicMock(name="connection")
    cursor = MagicMock(name="cursor")
    conn.cursor.return_value = cursor
    pool.connection.return_value = conn
    return pool, conn, cursor


def _reset_pool_class():
    """Reset class-level pool so each test starts fresh."""
    from stockfetch.db_base import StockDBBase

    StockDBBase._StockDBBase__pool = None


@pytest.fixture(autouse=True)
def _clean_pool():
    """Ensure the class-level pool is reset before and after every test."""
    _reset_pool_class()
    yield
    _reset_pool_class()


def _make_kdj_daily(code="600036", param="933", **extra_kwargs):
    """Create a KDJDaily with a mock pool injected."""
    from stockfetch.db_base import StockDBBase as _Base

    pool, conn, cursor = _make_mock_pool()
    with patch("stockfetch.db_base.PooledDB", return_value=pool):
        _Base._StockDBBase__pool = pool
        from stockfetch.db_kdj import KDJDaily

        obj = KDJDaily(code, param, **extra_kwargs)
    return obj, pool, conn, cursor


# ---------------------------------------------------------------------------
# 1. Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_code_only_default_param(self):
        obj, _, _, _ = _make_kdj_daily("600036")
        assert obj.code == "600036"
        assert obj.param == "933"

    def test_param_522(self):
        obj, _, _, _ = _make_kdj_daily("600036", param="522")
        assert obj.param == "522"

    def test_explicit_db_kwargs_forwarded(self):
        pool, _, _ = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_kdj import KDJDaily

            KDJDaily.__mro__[1]._StockDBBase__pool = pool
            obj = KDJDaily(
                "600036",
                **{"host": "10.0.0.1", "port": 3307, "user": "admin", "passwd": "secret", "db": "testdb"},
            )
            assert obj.code == "600036"

    def test_inherits_stockdbbase(self):
        from stockfetch.db_base import StockDBBase

        obj, _, _, _ = _make_kdj_daily("600036")
        assert isinstance(obj, StockDBBase)


# ---------------------------------------------------------------------------
# 2. _table_name routing
# ---------------------------------------------------------------------------


class TestTableName:
    def test_default_param_returns_standard_table(self):
        obj, _, _, _ = _make_kdj_daily("600036")
        assert obj._table_name() == "indicators_kdj_daily"

    def test_param_522_returns_alternate_table(self):
        obj, _, _, _ = _make_kdj_daily("600036", param="522")
        assert obj._table_name() == "indicators_kdj_daily_522"


# ---------------------------------------------------------------------------
# 3. db_get_maxdate
# ---------------------------------------------------------------------------


class TestDbGetMaxdate:
    def test_returns_date(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")
        expected = datetime.date(2024, 6, 1)
        cursor.execute.return_value = 1
        cursor.fetchone.return_value = {"max(date)": expected}

        result = obj.db_get_maxdate()
        assert result == expected

    def test_returns_none_when_no_data(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")
        cursor.execute.return_value = 0
        cursor.fetchone.return_value = {"max(date)": None}

        result = obj.db_get_maxdate()
        assert result is None

    def test_uses_parameterised_query(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")
        cursor.execute.return_value = 1
        cursor.fetchone.return_value = {"max(date)": datetime.date(2024, 1, 1)}

        obj.db_get_maxdate()

        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "%s" in sql
        assert params == ("600036",)


# ---------------------------------------------------------------------------
# 4. getData
# ---------------------------------------------------------------------------


class TestGetData:
    def test_returns_dataframe_default_table(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        max_date = datetime.date(2024, 6, 1)
        cursor.execute.side_effect = [1, 2]
        cursor.fetchone.return_value = {"max(date)": max_date}
        cursor.fetchall.return_value = [
            {"stock_code": "600036", "k": 50.0, "d": 40.0, "j": 60.0, "record_time": "2024-05-01"},
            {"stock_code": "600036", "k": 55.0, "d": 45.0, "j": 65.0, "record_time": "2024-05-02"},
        ]

        import pandas as pd

        df = obj.getData()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "k" in df.columns

        # Verify default table is used
        second_call = cursor.execute.call_args_list[1]
        assert "indicators_kdj_daily" in second_call[0][0]
        assert "indicators_kdj_daily_522" not in second_call[0][0]

    def test_returns_dataframe_522_table(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036", param="522")

        max_date = datetime.date(2024, 6, 1)
        cursor.execute.side_effect = [1, 1]
        cursor.fetchone.return_value = {"max(date)": max_date}
        cursor.fetchall.return_value = [
            {"stock_code": "600036", "k": 50.0, "d": 40.0, "j": 60.0, "record_time": "2024-05-01"},
        ]

        import pandas as pd

        df = obj.getData()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

        # Verify 522 table is used
        second_call = cursor.execute.call_args_list[1]
        assert "indicators_kdj_daily_522" in second_call[0][0]

    def test_fallback_date_when_no_maxdate(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        cursor.execute.side_effect = [0, 0]
        cursor.fetchone.return_value = {"max(date)": None}
        cursor.fetchall.return_value = []

        import pandas as pd

        df = obj.getData()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_uses_parameterised_query(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        max_date = datetime.date(2024, 6, 1)
        cursor.execute.side_effect = [1, 0]
        cursor.fetchone.return_value = {"max(date)": max_date}
        cursor.fetchall.return_value = []

        obj.getData()

        second_call = cursor.execute.call_args_list[1]
        sql = second_call[0][0]
        params = second_call[0][1]
        assert "%s" in sql
        assert params[0] == "600036"


# ---------------------------------------------------------------------------
# 5. insert
# ---------------------------------------------------------------------------


class TestInsert:
    def test_inserts_valid_records(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        KDJ = [
            [_FakeValue(50.0), _FakeValue(55.0)],
            [_FakeValue(40.0), _FakeValue(45.0)],
            [_FakeValue(60.0), _FakeValue(65.0)],
        ]
        DATETIME = [_FakeValue(20240501000000), _FakeValue(20240502000000)]

        obj.insert(KDJ, DATETIME)

        assert cursor.execute.call_count >= 2

    def test_skips_nan_on_j(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        KDJ = [
            [_FakeValue(50.0), _FakeValue(55.0)],
            [_FakeValue(40.0), _FakeValue(45.0)],
            [_FakeValue(float("nan")), _FakeValue(65.0)],
        ]
        DATETIME = [_FakeValue(20240501000000), _FakeValue(20240502000000)]

        obj.insert(KDJ, DATETIME)

        # Only 1 valid record (index 1 has j=NaN, skipped; index 0 valid)
        assert cursor.execute.call_count == 1

    def test_targets_correct_table_per_param(self):
        KDJ = [
            [_FakeValue(50.0)],
            [_FakeValue(40.0)],
            [_FakeValue(60.0)],
        ]
        DATETIME = [_FakeValue(20240501000000)]

        # Test default param → standard table
        _reset_pool_class()
        obj_default, _, _, cursor_default = _make_kdj_daily("600036")
        obj_default.insert(KDJ, DATETIME)
        sql_default = cursor_default.execute.call_args[0][0]
        assert "indicators_kdj_daily_522" not in sql_default
        assert "indicators_kdj_daily" in sql_default

        # Test param="522" → alternate table
        _reset_pool_class()
        obj_522, _, _, cursor_522 = _make_kdj_daily("600036", param="522")
        obj_522.insert(KDJ, DATETIME)
        sql_522 = cursor_522.execute.call_args[0][0]
        assert "indicators_kdj_daily_522" in sql_522

    def test_uses_parameterised_replace_into(self):
        obj, pool, conn, cursor = _make_kdj_daily("600036")

        KDJ = [
            [_FakeValue(50.0)],
            [_FakeValue(40.0)],
            [_FakeValue(60.0)],
        ]
        DATETIME = [_FakeValue(20240501000000)]

        obj.insert(KDJ, DATETIME)

        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "REPLACE INTO" in sql
        assert "%s" in sql
        assert "\\'" not in sql


# ---------------------------------------------------------------------------
# 6. No raw pymysql
# ---------------------------------------------------------------------------


class TestNoRawConnection:
    def test_no_pymysql_connect(self):
        """Verify KDJDaily source does not use pymysql.connect directly."""
        from stockfetch.db_kdj import KDJDaily

        source = inspect.getsource(KDJDaily)
        assert "pymysql.connect" not in source
        assert "get_conn" not in source
        assert "db_disconnect" not in source
        assert "db_insertsql" not in source
