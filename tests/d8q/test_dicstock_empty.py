from unittest import mock
from buy.cache import DicStockFactory


class FakeCur:
    def execute(self, *a, **k):
        return None

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class FakeMC:
    def cursor(self):
        return FakeCur()

    def select_many(self, *a, **k):
        return (0, [])

    def close(self):
        return None


def test_load_handles_empty_table_without_keyerror():
    with mock.patch('buy.cache.DicStockFactory.DBClient', lambda: FakeMC()):
        f = DicStockFactory()
        f.load()
        assert f.data.empty is True
        assert f.isExist('600000') is False
