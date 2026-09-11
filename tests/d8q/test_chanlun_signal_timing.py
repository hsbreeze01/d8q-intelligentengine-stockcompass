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
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        self.calls.append((sql, params))
        return 1

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self, rows):
        self.cur = Cursor(rows)
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


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
    assert signal["type_code"] == "B1"
    assert signal["type_label"] == "B1 一买"
    assert "scan_date" in conn.cur.sql
    assert "created_at" in conn.cur.sql
    assert "ORDER BY created_at DESC, id DESC" in conn.cur.sql


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
    with app.test_request_context("/signals?date=2026-09-10&min_score=0&limit=5"):
        response = chanlun.get_signals()

    signal = response.get_json()["signals"][0]
    assert signal["signal_date"] == "2026-09-09"
    assert signal["structure_date"] == "2026-09-09"
    assert signal["confirmed_date"] == "2026-09-10"
    assert signal["confirmed_at"] == "2026-09-10 20:15:52"
    assert signal["type_code"] == "B1"
    assert signal["type_label"] == "B1 一买"
    assert "h.created_at >= %s" in conn.cur.sql
    assert "h.created_at < DATE_ADD(%s, INTERVAL 1 DAY)" in conn.cur.sql
    assert "h.signal_date = %s" not in conn.cur.sql
    assert conn.cur.params[:2] == ("2026-09-10", "2026-09-10")
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


def test_all_signal_types_expose_standard_bs_labels():
    expected = {
        "buy1": ("B1", "B1 一买"), "buy2": ("B2", "B2 二买"),
        "buy3": ("B3", "B3 三买"), "sell1": ("S1", "S1 一卖"),
        "sell2": ("S2", "S2 二卖"), "sell3": ("S3", "S3 三卖"),
    }
    for signal_type, (code, label) in expected.items():
        fields = chanlun._signal_type_fields(signal_type)
        assert fields == {"type_code": code, "type_label": label}


def test_push_uses_confirmation_time_and_updates_only_selected_ids(monkeypatch):
    import requests

    rows = [{
        "id": 17, "stock_code": "600864", "stock_name": "哈投股份",
        "signal_type": "buy1", "structure_date": date(2026, 9, 9),
        "confirmed_at": datetime(2026, 9, 10, 20, 15, 52),
        "signal_price": 5.7, "stop_loss": 5.2, "target_price": 6.3,
        "score": 88, "reason": "trend_bottom_divergence",
    }]
    conn = Conn(rows)
    sent = {}

    class Response:
        status_code = 200

    def fake_post(url, json, timeout):
        sent.update({"url": url, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(chanlun, "get_db", lambda: conn)
    monkeypatch.setattr(requests, "post", fake_post)

    assert chanlun.push_high_score_signals(75) == 1
    select_sql, select_params = conn.cur.calls[0]
    assert "created_at >= %s" in select_sql
    assert "created_at < DATE_ADD(%s, INTERVAL 1 DAY)" in select_sql
    assert "signal_date=%s" not in select_sql
    assert select_params[0] == select_params[1]
    assert "B1 一买结构已确认" in sent["json"]["content"]
    assert "结构日：2026-09-09" in sent["json"]["content"]
    assert "确认时间：2026-09-10 20:15:52" in sent["json"]["content"]
    assert "最早可执行：确认后的下一交易日" in sent["json"]["content"]
    update_sql, update_params = conn.cur.calls[1]
    assert "WHERE id IN (%s)" in update_sql
    assert update_params == [17]
    assert conn.committed and conn.closed


def test_czsc_detail_json_safe_converts_nested_enums():
    from enum import Enum
    from chanlun.engine import czsc_detail

    class Direction(Enum):
        UP = "up"

    value = {"direction": Direction.UP, "nested": [Direction.UP, {"x": Direction.UP}]}
    assert czsc_detail._json_safe(value) == {
        "direction": "up", "nested": ["up", {"x": "up"}]
    }
