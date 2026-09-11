# -*- coding: utf-8 -*-
"""signal_review 无前视与并发保护回归测试。"""
from datetime import date, datetime, timedelta

from chanlun.strategy import signal_review as sr


class Cursor:
    def __init__(self, update_result=1):
        self.update_result = update_result
        self.rows = []
        self.calls = []

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        if compact.startswith("SELECT id, signal_date, created_at"):
            self.rows = [{
                "id": 7, "signal_date": date(2026, 9, 9),
                "created_at": datetime(2026, 9, 10, 20, 15, 52),
                "code": "600864", "type": "buy1", "price": 5.7, "stop_loss": 5.2,
            }]
            return 1
        if compact.startswith("SELECT d.date"):
            self.rows = [
                {"date": date(2026, 9, 11) + timedelta(days=i), "open": 6.0,
                 "high": 6.3, "low": 5.9, "close": 6.2}
                for i in range(10)
            ]
            return 10
        if compact.startswith("UPDATE czsc_signal_history"):
            return self.update_result
        raise AssertionError(f"unexpected SQL: {compact}")

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self, update_result=1):
        self.cur = Cursor(update_result)
        self.committed = False

    def cursor(self, *_args, **_kwargs):
        return self.cur

    def commit(self):
        self.committed = True


def test_backfill_uses_confirmation_window_and_next_open():
    conn = Conn(update_result=1)
    assert sr._backfill_czsc_history(conn) == 1

    bars_call = next(c for c in conn.cur.calls if c[0].startswith("SELECT d.date"))
    assert "date>DATE(%s)" in bars_call[0]
    assert "MAX(id) keep_id" in bars_call[0]
    assert "GROUP BY date" in bars_call[0]
    assert bars_call[1] == ("600864", datetime(2026, 9, 10, 20, 15, 52))

    update_call = next(c for c in conn.cur.calls if c[0].startswith("UPDATE czsc_signal_history"))
    assert "WHERE id=%s AND outcome IS NULL" in update_call[0]
    assert update_call[1][0] == 6.0  # next_open = 确认后下一交易日 open
    assert conn.committed


def test_backfill_does_not_count_or_overwrite_concurrently_completed_row():
    conn = Conn(update_result=0)
    assert sr._backfill_czsc_history(conn) == 0
    update_sql = next(c[0] for c in conn.cur.calls if c[0].startswith("UPDATE czsc_signal_history"))
    assert "AND outcome IS NULL" in update_sql
