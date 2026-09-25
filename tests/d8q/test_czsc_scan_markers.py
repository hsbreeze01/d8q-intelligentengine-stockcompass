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


def test_scan_and_push_dedup_by_data_date(tmp_path):
    """2026-09-25 事故回归: 同一 data_date 重试重跑时至多推送一次"""
    result = {'data_date': '2026-09-24', 'signals': [{'code': '600000'}]}
    with mock.patch.object(czsc_scan, 'scan', return_value=result), \
            mock.patch.object(czsc_scan, '_write_status'), \
            mock.patch.object(czsc_scan, 'format_push_message', return_value='msg'), \
            mock.patch.object(czsc_scan, 'push_wecom', return_value={'errcode': 0}) as push, \
            mock.patch.object(czsc_scan, '_PUSH_MARKER_DIR', str(tmp_path)):
        czsc_scan.scan_and_push()
        czsc_scan.scan_and_push()
        czsc_scan.scan_and_push()
    assert push.call_count == 1
    assert (tmp_path / 'czsc_pushed_2026-09-24').exists()


def test_scan_and_push_push_failure_no_marker(tmp_path):
    """推送失败不落标记, 下一轮重试仍会推"""
    result = {'data_date': '2026-09-24', 'signals': [{'code': '600000'}]}
    with mock.patch.object(czsc_scan, 'scan', return_value=result), \
            mock.patch.object(czsc_scan, '_write_status'), \
            mock.patch.object(czsc_scan, 'format_push_message', return_value='msg'), \
            mock.patch.object(czsc_scan, 'push_wecom', return_value={'errcode': -1}), \
            mock.patch.object(czsc_scan, '_PUSH_MARKER_DIR', str(tmp_path)):
        czsc_scan.scan_and_push()
    assert not (tmp_path / 'czsc_pushed_2026-09-24').exists()


def test_scan_and_push_no_signal_no_marker(tmp_path):
    """无信号不推送也不落标记"""
    with mock.patch.object(czsc_scan, 'scan', return_value={'signals': []}), \
            mock.patch.object(czsc_scan, '_write_status'), \
            mock.patch.object(czsc_scan, 'format_push_message', return_value=None), \
            mock.patch.object(czsc_scan, 'push_wecom') as push, \
            mock.patch.object(czsc_scan, '_PUSH_MARKER_DIR', str(tmp_path)):
        czsc_scan.scan_and_push()
    push.assert_not_called()
    assert list(tmp_path.iterdir()) == []
