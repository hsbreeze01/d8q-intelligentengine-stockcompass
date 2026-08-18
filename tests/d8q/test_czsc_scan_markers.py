from datetime import datetime as DT
from unittest import mock
import chanlun.strategy.czsc_scan as czsc_scan


class FakeDT:
    @staticmethod
    def now():
        return DT(2026, 8, 18)

    @staticmethod
    def strptime(s, fmt):
        return DT.strptime(s, fmt)


def test_scan_prints_non_trading_day_marker(capsys):
    conn = mock.MagicMock()

    def fake_cursor(*a, **k):
        cur = mock.MagicMock()
        cur.fetchall.return_value = [{'date': '2026-08-10'}]
        return cur

    conn.cursor.side_effect = fake_cursor

    with mock.patch.object(czsc_scan, 'pymysql') as mp:
        mp.connect.return_value = conn
        with mock.patch.object(czsc_scan, '_check_data_ready', return_value=(True, 5000, 5000, '2026-08-17')):
            with mock.patch.object(czsc_scan, 'datetime', FakeDT):
                czsc_scan.scan()

    out = capsys.readouterr().out
    assert 'czsc_scan: reason=non_trading_day' in out
