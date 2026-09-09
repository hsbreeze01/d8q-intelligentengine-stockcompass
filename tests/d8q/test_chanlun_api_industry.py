"""GET /chanlun/signals 应从 stock_basic 透传行业且保持 default profile。"""
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


def test_signals_api_joins_and_returns_industry(monkeypatch):
    conn = Conn()
    monkeypatch.setattr(chanlun, "get_db", lambda: conn)
    app = Flask(__name__)
    with app.test_request_context("/signals?date=2026-09-08&min_score=0&limit=5"):
        response = chanlun.get_signals()
    body = response.get_json()
    assert body["signals"][0]["industry"] == "银行"
    assert "LEFT JOIN stock_basic" in conn.cur.sql
    assert "COLLATE utf8mb4_unicode_ci" in conn.cur.sql
    assert "h.profile = 'default'" in conn.cur.sql
