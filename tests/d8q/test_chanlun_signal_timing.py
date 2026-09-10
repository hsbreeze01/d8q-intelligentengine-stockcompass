"""缠论信号必须区分结构日期与实际确认时间。"""
from datetime import date, datetime
from pathlib import Path

from flask import Flask

from compass.api.routes import chanlun


class Cursor:
    def __init__(self, rows):
        self.rows = rows
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
        return self.rows


class Conn:
    def __init__(self, rows):
        self.cur = Cursor(rows)

    def cursor(self):
        return self.cur

    def close(self):
        pass


def _detail():
    return {
        "klines": [
            {"dt": "2026-09-09", "open": 5.71, "close": 5.70,
             "low": 5.65, "high": 5.73, "volume": 1},
            {"dt": "2026-09-10", "open": 5.75, "close": 6.00,
             "low": 5.75, "high": 6.19, "volume": 2},
        ],
        "bis": [],
        "zs": [],
        "divergence": {},
        "trend": "consolidation",
    }


def test_signal_detail_exposes_structure_and_confirmation_timing(monkeypatch):
    rows = [{
        "signal_date": date(2026, 9, 9),
        "scan_date": date(2026, 9, 10),
        "created_at": datetime(2026, 9, 10, 20, 15, 52),
        "type": "buy1",
        "price": 5.70,
        "score": 88,
        "reason": "trend_bottom_divergence",
    }]
    conn = Conn(rows)
    monkeypatch.setattr(chanlun, "get_db", lambda: conn)
    monkeypatch.setattr(chanlun, "get_stock_detail", lambda code, limit=120: _detail())

    app = Flask(__name__)
    with app.test_request_context("/signals/600864"):
        response = chanlun.get_signal_detail("600864")

    signal = response.get_json()["signals"][0]
    assert signal["date"] == "2026-09-09"  # 旧客户端兼容字段
    assert signal["structure_date"] == "2026-09-09"
    assert signal["confirmed_date"] == "2026-09-10"
    assert signal["confirmed_at"] == "2026-09-10 20:15:52"
    assert signal["confirmed_after_structure"] is True
    assert "scan_date" in conn.cur.sql
    assert "created_at" in conn.cur.sql


def test_timing_fields_remain_unknown_without_created_at():
    timing = chanlun._signal_timing_fields({
        "signal_date": date(2026, 9, 9),
        "scan_date": date(2026, 9, 10),
    })
    assert timing == {
        "structure_date": "2026-09-09",
        "confirmed_date": None,
        "confirmed_at": None,
        "confirmed_after_structure": False,
    }


def test_created_at_wins_over_business_scan_date():
    timing = chanlun._signal_timing_fields({
        "signal_date": date(2026, 9, 11),
        "scan_date": date(2026, 9, 11),
        "created_at": datetime(2026, 9, 12, 9, 30),
    })
    assert timing["confirmed_date"] == "2026-09-12"
    assert timing["confirmed_at"] == "2026-09-12 09:30:00"
    assert timing["confirmed_after_structure"] is True


def test_signal_list_exposes_timing_without_changing_signal_date(monkeypatch):
    rows = [{
        "stock_code": "600864", "stock_name": "哈投股份",
        "signal_date": date(2026, 9, 9), "scan_date": date(2026, 9, 10),
        "created_at": datetime(2026, 9, 10, 20, 15, 52),
        "signal_type": "buy1", "signal_price": 5.70,
        "stop_loss": 5.37, "target_price": 6.21, "target_type": "fixed_pct",
        "score": 88, "total_score": 88, "environment_score": 18,
        "macd_area_ratio": 0.05, "reason": "trend_bottom_divergence",
        "grade": 3, "industry": "非银金融", "status": "pending",
    }]
    conn = Conn(rows)
    monkeypatch.setattr(chanlun, "get_db", lambda: conn)
    app = Flask(__name__)
    with app.test_request_context("/signals?date=2026-09-09&min_score=0&limit=5"):
        response = chanlun.get_signals()

    signal = response.get_json()["signals"][0]
    assert signal["signal_date"] == "2026-09-09"
    assert signal["structure_date"] == "2026-09-09"
    assert signal["confirmed_date"] == "2026-09-10"
    assert signal["confirmed_at"] == "2026-09-10 20:15:52"
    assert "h.scan_date" in conn.cur.sql
    assert "h.created_at" in conn.cur.sql


def test_detail_template_labels_structure_and_confirmation_separately():
    app = Flask("compass.api.app")
    loaded = app.jinja_env.get_template("chanlun_detail.html")
    template_path = Path(loaded.filename)
    assert template_path.as_posix().endswith("compass/api/templates/chanlun_detail.html")
    template = template_path.read_text()
    assert "○ 结构点" in template
    assert "◆ 确认点" in template
    assert "结构日期" in template
    assert "确认时间" in template
    assert "最早可执行" in template
    assert '<div class="label">信号日</div>' not in template
    assert "coord: [structureDate, s.price]" in template
    assert "coord: [s.confirmed_date" in template
    assert "if (data.macd)" in template
    assert "document.getElementById('macdChart').style.display = 'none'" in template
