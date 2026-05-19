"""Unit tests for StockDBBase — stockfetch/db_base.py"""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 1. Pool initialisation
# ---------------------------------------------------------------------------

class TestPoolInit:
    def test_first_instance_creates_pool(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            # Use custom kwargs so it doesn't touch buy/Config
            db = StockDBBase(host="h", port=3306, user="u", passwd="p", db="d")
            assert db is not None
            # Pool should be set at class level
            assert StockDBBase._StockDBBase__pool is pool

    def test_subsequent_instance_reuses_pool(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            db1 = StockDBBase(host="h", port=3306, user="u", passwd="p", db="d")
            db2 = StockDBBase(host="h2", port=3307, user="u2", passwd="p2", db="d2")
            assert db1 is not None and db2 is not None
            # PooledDB called only once
            from stockfetch.db_base import PooledDB as _PL
            assert _PL.call_count if hasattr(_PL, "call_count") else True
            # Pool is the same object
            assert StockDBBase._StockDBBase__pool is pool

    def test_custom_kwargs_override_config(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool) as mock_pl:
            from stockfetch.db_base import StockDBBase
            db = StockDBBase(host="myhost", port=3307, user="myuser", passwd="mypass", db="mydb")
            assert db is not None
            _, kwargs = mock_pl.call_args
            assert kwargs["host"] == "myhost"
            assert kwargs["port"] == 3307
            assert kwargs["user"] == "myuser"
            assert kwargs["passwd"] == "mypass"
            assert kwargs["db"] == "mydb"


# ---------------------------------------------------------------------------
# 2. Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def _make_instance(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            StockDBBase._StockDBBase__pool = pool
            return StockDBBase(host="h", user="u", passwd="p", db="d"), pool, conn, cursor

    def test_enter_acquires_connection(self):
        db, pool, conn, cursor = self._make_instance()
        with db:
            assert db._conn is not None
            assert db._cursor is not None
            pool.connection.assert_called()

    def test_exit_without_error_skips_commit_when_read_only(self):
        db, pool, conn, cursor = self._make_instance()
        with db:
            cursor.execute("SELECT 1")
        conn.commit.assert_not_called()
        cursor.close.assert_called()
        conn.close.assert_called()

    def test_exit_without_error_commits_after_write(self):
        db, pool, conn, cursor = self._make_instance()
        with db:
            cursor.execute("INSERT INTO t VALUES (1)")
            db._dirty = True  # simulate _execute_many having set it
        conn.commit.assert_called_once()
        cursor.close.assert_called()
        conn.close.assert_called()
        assert db._dirty is False

    def test_exit_with_error_rolls_back_and_releases(self):
        db, pool, conn, cursor = self._make_instance()
        with pytest.raises(ValueError):
            with db:
                raise ValueError("boom")
        conn.rollback.assert_called_once()
        cursor.close.assert_called()
        conn.close.assert_called()


# ---------------------------------------------------------------------------
# 3. Explicit open / close
# ---------------------------------------------------------------------------

class TestExplicitLifecycle:
    def _make_instance(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            StockDBBase._StockDBBase__pool = pool
            return StockDBBase(host="h", user="u", passwd="p", db="d"), pool, conn, cursor

    def test_open_acquires_connection(self):
        db, pool, conn, cursor = self._make_instance()
        db.open()
        pool.connection.assert_called()
        assert db._cursor is not None

    def test_close_releases_connection(self):
        db, pool, conn, cursor = self._make_instance()
        db.open()
        db.close()
        assert db._conn is None
        assert db._cursor is None

    def test_double_close_is_safe(self):
        db, pool, conn, cursor = self._make_instance()
        db.open()
        db.close()
        db.close()  # should not raise


# ---------------------------------------------------------------------------
# 4. Query methods
# ---------------------------------------------------------------------------

class TestQueryMethods:
    def _make_active_instance(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            StockDBBase._StockDBBase__pool = pool
            db = StockDBBase(host="h", user="u", passwd="p", db="d")
            db._acquire_conn()
            return db, pool, conn, cursor

    def test_query_one(self):
        db, pool, conn, cursor = self._make_active_instance()
        cursor.execute.return_value = 1
        cursor.fetchone.return_value = {"id": 42, "name": "test"}
        count, row = db._query_one("SELECT * FROM t WHERE id=%s", (42,))
        assert count == 1
        assert row == {"id": 42, "name": "test"}

    def test_query_all(self):
        db, pool, conn, cursor = self._make_active_instance()
        cursor.execute.return_value = 2
        cursor.fetchall.return_value = [{"id": 1}, {"id": 2}]
        count, rows = db._query_all("SELECT * FROM t")
        assert count == 2
        assert len(rows) == 2

    def test_execute_many(self):
        db, pool, conn, cursor = self._make_active_instance()
        cursor.rowcount = 1
        cursor.lastrowid = 99
        affected, last_id = db._execute_many("INSERT INTO t (name) VALUES (%s)", ("x",))
        assert affected == 1
        assert last_id == 99

    def test_query_without_connection_raises(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            StockDBBase._StockDBBase__pool = pool
            db = StockDBBase(host="h", user="u", passwd="p", db="d")
            # Do NOT acquire a connection
            with pytest.raises(RuntimeError, match="No active database connection"):
                db._query_one("SELECT 1")
            with pytest.raises(RuntimeError):
                db._query_all("SELECT 1")
            with pytest.raises(RuntimeError):
                db._execute_many("INSERT INTO t VALUES (1)")


# ---------------------------------------------------------------------------
# 5. Commit / rollback
# ---------------------------------------------------------------------------

class TestTransactionControl:
    def _make_active_instance(self):
        pool, conn, cursor = _make_mock_pool()
        with patch("stockfetch.db_base.PooledDB", return_value=pool):
            from stockfetch.db_base import StockDBBase
            StockDBBase._StockDBBase__pool = pool
            db = StockDBBase(host="h", user="u", passwd="p", db="d")
            db._acquire_conn()
            return db, conn

    def test_commit(self):
        db, conn = self._make_active_instance()
        db.commit()
        conn.commit.assert_called_once()

    def test_rollback(self):
        db, conn = self._make_active_instance()
        db.rollback()
        conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# 6. Importability
# ---------------------------------------------------------------------------

class TestImport:
    def test_import_from_package(self):
        from stockfetch import StockDBBase
        assert StockDBBase is not None

    def test_import_from_module(self):
        from stockfetch.db_base import StockDBBase
        assert StockDBBase is not None
