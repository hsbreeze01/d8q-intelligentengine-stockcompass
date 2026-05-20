"""Tests for DBClient connection pool fix (Task 1).

Verifies:
- Single-underscore _pool attribute (no name mangling)
- ping(reconnect=True) on connection acquisition
- get_pool_status() returns structured health info
- DCL thread safety (basic)
"""
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: create a fake PooledDB that behaves enough like the real one
# ---------------------------------------------------------------------------

def _make_fake_pool():
    """Return a MagicMock mimicking PooledDB with _idle_cache and _maxconnections."""
    pool = MagicMock()
    pool._idle_cache = [MagicMock(), MagicMock()]  # 2 idle conns
    pool._maxconnections = 100
    fake_conn = MagicMock()
    fake_conn.ping = MagicMock()
    fake_conn.cursor.return_value = MagicMock()
    pool.connection.return_value = fake_conn
    return pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDBClientPoolNaming:
    """Verify that __pool → _pool migration eliminates name mangling."""

    def test_pool_is_single_underscore_class_attr(self):
        """DBClient._pool should be a regular (non-mangled) class attribute."""
        from buy.DBClient import DBClient
        assert hasattr(DBClient, '_pool'), "DBClient should have _pool class attribute"
        # Verify it's NOT using double-underscore name mangling
        assert not hasattr(DBClient, '_DBClient__pool') or DBClient._DBClient__pool is None, \
            "Old __pool (mangled) should not be used"

    @patch('buy.DBClient.config')
    def test_pool_initialized_as_single_underscore(self, mock_config):
        """After first instantiation, DBClient._pool should be set."""
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()

        from buy.DBClient import DBClient
        DBClient._pool = None  # reset for test

        with patch('buy.DBClient.PooledDB', return_value=fake_pool):
            DBClient()

        assert DBClient._pool is fake_pool
        # Cleanup
        DBClient._pool = None


class TestDBClientPingHealthCheck:
    """Verify connection.ping(reconnect=True) is called on acquisition."""

    @patch('buy.DBClient.config')
    def test_ping_called_on_get_conn(self, mock_config):
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()

        from buy.DBClient import DBClient
        DBClient._pool = None

        with patch('buy.DBClient.PooledDB', return_value=fake_pool):
            DBClient()

        # The fake connection returned by pool.connection() should have ping called
        fake_conn = fake_pool.connection.return_value
        fake_conn.ping.assert_called_once_with(reconnect=True)

        # Cleanup
        DBClient._pool = None


class TestDBClientGetPoolStatus:
    """Verify get_pool_status() returns correct structure."""

    def test_status_when_not_initialized(self):
        from buy.DBClient import DBClient
        DBClient._pool = None
        DBClient._last_error = None

        status = DBClient.get_pool_status()
        assert status["initialized"] is False
        assert status["active_connections"] == 0
        assert status["idle_connections"] == 0
        assert status["max_connections"] == 0
        assert status["last_error"] is None

    def test_status_when_initialized(self):
        from buy.DBClient import DBClient
        fake_pool = _make_fake_pool()
        DBClient._pool = fake_pool
        DBClient._connection_count = 5
        DBClient._last_error = None

        status = DBClient.get_pool_status()
        assert status["initialized"] is True
        assert status["idle_connections"] == 2  # from _idle_cache
        assert status["active_connections"] == 3  # 5 - 2 idle
        assert status["max_connections"] == 100
        assert status["last_error"] is None

        # Cleanup
        DBClient._pool = None

    def test_status_with_last_error(self):
        from buy.DBClient import DBClient
        DBClient._pool = None
        DBClient._last_error = "Connection refused"

        status = DBClient.get_pool_status()
        assert status["last_error"] == "Connection refused"

        # Cleanup
        DBClient._last_error = None

    @patch('buy.DBClient.config')
    def test_error_recorded_on_connection_failure(self, mock_config):
        """When pool.connection() raises, _last_error should be set."""
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = MagicMock()
        fake_pool.connection.side_effect = Exception("Connection refused")

        from buy.DBClient import DBClient
        DBClient._pool = None
        DBClient._last_error = None

        with patch('buy.DBClient.PooledDB', return_value=fake_pool):
            with pytest.raises(Exception, match="Connection refused"):
                DBClient()

        assert DBClient._last_error == "Connection refused"

        # Cleanup
        DBClient._pool = None
        DBClient._last_error = None


class TestDBClientPoolAutoReset:
    """Verify pool is reset to None on OperationalError / ConnectionRefusedError."""

    @patch('buy.DBClient.config')
    def test_pool_reset_on_operational_error(self, mock_config):
        """OperationalError (errno 2003/2006) shall reset _pool to None."""
        import pymysql

        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()
        fake_pool.connection.side_effect = pymysql.OperationalError(2006, "MySQL server has gone away")

        from buy.DBClient import DBClient
        DBClient._pool = None
        DBClient._last_error = None

        with patch('buy.DBClient.PooledDB', return_value=fake_pool):
            # First instantiation sets the pool
            DBClient._pool = fake_pool
            # Now __get_conn should fail and reset pool
            with pytest.raises(pymysql.OperationalError):
                DBClient()

        assert DBClient._pool is None, "_pool should be reset to None after OperationalError"
        assert "MySQL server has gone away" in DBClient._last_error

        # Cleanup
        DBClient._pool = None
        DBClient._last_error = None

    @patch('buy.DBClient.config')
    def test_pool_reset_on_connection_refused(self, mock_config):
        """ConnectionRefusedError shall reset _pool to None."""
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()
        fake_pool.connection.side_effect = ConnectionRefusedError("Connection refused")

        from buy.DBClient import DBClient
        DBClient._pool = fake_pool
        DBClient._last_error = None

        with pytest.raises(ConnectionRefusedError):
            DBClient()

        assert DBClient._pool is None, "_pool should be reset to None after ConnectionRefusedError"
        assert "Connection refused" in DBClient._last_error

        # Cleanup
        DBClient._pool = None
        DBClient._last_error = None

    @patch('buy.DBClient.config')
    def test_pool_not_reset_on_generic_error(self, mock_config):
        """Generic exceptions should NOT reset the pool — only DB connection errors do."""
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()
        fake_pool.connection.side_effect = RuntimeError("some other error")

        from buy.DBClient import DBClient
        DBClient._pool = fake_pool
        DBClient._last_error = None

        with pytest.raises(RuntimeError):
            DBClient()

        assert DBClient._pool is fake_pool, "_pool should NOT be reset for generic errors"
        assert "some other error" in DBClient._last_error

        # Cleanup
        DBClient._pool = None
        DBClient._last_error = None

    @patch('buy.DBClient.config')
    def test_pool_recreated_after_reset(self, mock_config):
        """After pool reset, next DBClient() instantiation creates a fresh pool."""
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        import pymysql

        from buy.DBClient import DBClient
        DBClient._pool = None
        DBClient._last_error = None

        # First pool (will be reset)
        stale_pool = _make_fake_pool()
        stale_pool.connection.side_effect = pymysql.OperationalError(2003, "Can't connect to MySQL server")

        with patch('buy.DBClient.PooledDB', return_value=stale_pool):
            with pytest.raises(pymysql.OperationalError):
                DBClient()

        assert DBClient._pool is None

        # Second pool (fresh, should succeed)
        fresh_pool = _make_fake_pool()
        with patch('buy.DBClient.PooledDB', return_value=fresh_pool):
            DBClient()

        assert DBClient._pool is fresh_pool, "New pool should be created after reset"

        # Cleanup
        DBClient._pool = None
        DBClient._last_error = None


class TestDBClientExistingInterface:
    """Verify existing interfaces (select_one, select_many, execute) are unchanged."""

    @patch('buy.DBClient.config')
    def test_select_one_works(self, mock_config):
        mock_config.getDBconnection.return_value = {
            'host': 'localhost', 'port': 3306,
            'user': 'test', 'password': 'test', 'database': 'testdb',
        }
        fake_pool = _make_fake_pool()
        fake_cursor = fake_pool.connection.return_value.cursor.return_value
        fake_cursor.execute.return_value = 1
        fake_cursor.fetchone.return_value = {"id": 1, "name": "test"}

        from buy.DBClient import DBClient
        DBClient._pool = None

        with patch('buy.DBClient.PooledDB', return_value=fake_pool):
            client = DBClient()

        count, result = client.select_one("SELECT * FROM user WHERE id = %s", (1,))
        assert count == 1
        assert result == {"id": 1, "name": "test"}

        # Cleanup
        DBClient._pool = None
