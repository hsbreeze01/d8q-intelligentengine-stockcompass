import sys
import types


class _FakeCursor:
    def execute(self, *a, **k):
        return None

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeDBClient:
    def cursor(self):
        return _FakeCursor()

    def select_many(self, *a, **k):
        return (0, [])

    def close(self):
        return None


# GitHub runners have no MySQL. buy/cache/DicStockFactory.py builds a
# module-level singleton (dicStock = DicStockFactory()) that opens a real
# connection at import time via the buy.DBClient class. Inject a fake
# buy.DBClient module into sys.modules BEFORE buy is imported so the
# singleton (and any DicStockFactory instance) uses an in-memory client
# instead of a live DB. This keeps tests/d8q importable without a database.
_fake_dbclient = types.ModuleType('buy.DBClient')
_fake_dbclient.DBClient = lambda: _FakeDBClient()
sys.modules['buy.DBClient'] = _fake_dbclient
