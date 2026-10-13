"""GET /chanlun/signals profile 查询参数（M1, 2026-10-12）。

默认 default 保持历史行为；显式 profile 经 SQL 参数传入（参数化防注入）。
"""
from flask import Flask

from compass.api.routes import chanlun


class Cursor:
    def __init__(self):
        self.sql = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return [{"stock_code": "600001", "stock_name": "测试",
                 "signal_date": "2026-09-08", "signal_type": "buy1",
                 "signal_price": 10.0, "stop_loss": 9.0, "target_price": 13.0,
                 "target_type": "fixed_pct", "score": 80, "total_score": 85,
                 "environment_score": 20, "macd_area_ratio": 0.5,
                 "reason": "x", "grade": "A", "industry": "银行",
                 "status": "pending"}]


class Conn:
    def __init__(self):
        self.cur = Cursor()

    def cursor(self):
        return self.cur

    def close(self):
        pass


def _call(query, monkeypatch):
    conn = Conn()
    monkeypatch.setattr(chanlun, "get_db", lambda: conn)
    app = Flask(__name__)
    with app.test_request_context(query):
        response = chanlun.get_signals()
    return conn.cur, response.get_json()


def test_profile_defaults_to_default(monkeypatch):
    cur, body = _call("/signals?date=2026-09-08&min_score=0&limit=5", monkeypatch)
    assert cur.params[2] == "default"
    assert body["count"] == 1


def test_profile_experimental_passed_as_param(monkeypatch):
    cur, _ = _call("/signals?date=2026-09-08&profile=experimental", monkeypatch)
    assert cur.params[2] == "experimental"
    assert "experimental" not in cur.sql


def test_profile_blank_falls_back_to_default(monkeypatch):
    cur, _ = _call("/signals?date=2026-09-08&profile=%20%20", monkeypatch)
    assert cur.params[2] == "default"


def test_profile_is_parameterized_not_inlined(monkeypatch):
    cur, _ = _call("/signals?date=2026-09-08&profile=default", monkeypatch)
    assert "h.profile = %s" in cur.sql
    assert "h.profile = 'default'" not in cur.sql
