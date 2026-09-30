# -*- coding: utf-8 -*-
"""P0-01/P0-03/P0-04 strategy audit tests (pure; no production DB)."""
import copy
import json

from chanlun.strategy import strategy_audit as audit


def _window(pnl, mfe, mae, r, win=None, complete=True):
    return {"window_complete": complete, "pnl_pct": pnl, "mfe_pct": mfe,
            "mae_pct": mae, "r_raw": r, "r_realized": r,
            "win": (pnl > 0 if win is None else win)}


def _detail(day, code, ty="buy1", score=80, target_type="pivot_zg",
            entry=10.0, stop=9.0, target=13.0, mfes=(5.0, 10.0, 15.0)):
    return {"signal_date": day, "code": code, "type": ty, "score": score,
            "target_type": target_type, "entry_price": entry,
            "stop_loss": stop, "target_price": target,
            "windows": {
                "5": _window(1.0, mfes[0], -2.0, 0.1, win=(ty.startswith("buy"))),
                "10": _window(2.0, mfes[1], -3.0, 0.2, win=(ty.startswith("buy"))),
                "20": _window(3.0, mfes[2], -4.0, 0.3, win=(ty.startswith("buy"))),
            }}


def test_daily_breadth_is_day_clustered_and_directional():
    signals = [
        {"signal_date": "2026-09-01", "type": "buy1"},
        {"signal_date": "2026-09-01", "type": "sell1"},
        {"signal_date": "2026-09-02", "type": "sell1"},
        {"signal_date": "2026-09-02", "type": "sell3"},
        {"signal_date": "2026-09-02", "type": "buy3"},
    ]
    rows = audit.daily_sell_breadth(signals)
    assert len(rows) == 2
    assert rows[0]["sell_share"] == 0.5
    assert rows[0]["net_breadth"] == 0.0
    assert rows[0]["would_block_long"] is False  # strict > 50%
    assert rows[1]["sell_share"] == 0.6667
    assert rows[1]["net_breadth"] == -0.3333
    assert rows[1]["would_block_long"] is True
    assert rows[1]["shadow_only"] is True


def test_daily_breadth_keeps_non_directional_count_without_dividing_by_it():
    rows = audit.daily_sell_breadth([
        {"signal_date": "2026-09-01", "type": "watch"},
        {"signal_date": "2026-09-01", "type": "buy1"},
    ])
    assert rows[0]["other_count"] == 1
    assert rows[0]["directional_count"] == 1
    assert rows[0]["sell_share"] == 0.0


def test_sell_window_pnl_is_direction_normalized():
    detail = _detail("2026-09-01", "600001", ty="sell1")
    detail["windows"]["5"] = _window(-4.0, 6.0, -1.0, 0.5, win=True)
    out = audit.summarize_rows([detail], 5)
    assert out["avg_direction_pnl_pct"] == 4.0
    assert out["win_rate"] == 1.0
    assert out["expectancy_r"] == 0.5


def test_incomplete_windows_are_excluded_but_count_is_preserved():
    complete = _detail("2026-09-01", "a")
    pending = _detail("2026-09-02", "b")
    pending["windows"]["5"]["window_complete"] = False
    out = audit.summarize_rows([complete, pending], 5)
    assert out["count"] == 2
    assert out["mature_count"] == 1
    assert out["signal_days"] == 1


def test_effective_rr_caps_structure_target_with_empirical_mfe():
    history = [
        _detail("2026-09-01", "a", mfes=(5, 5, 5)),
        _detail("2026-09-02", "b", mfes=(10, 10, 10)),
        _detail("2026-09-03", "c", mfes=(15, 15, 15)),
    ]
    refs = audit.build_mfe_reference(history)
    row = audit.effective_rr_shadow(history[0], refs)
    assert row["structure_rr"] == 3.0
    p50 = row["windows"]["5"]["estimates"]["p50"]
    assert p50["empirical_mfe_pct"] == 10.0
    assert p50["effective_target_price"] == 11.0
    assert p50["effective_rr"] == 1.0
    p80 = row["windows"]["5"]["estimates"]["p80"]
    assert p80["effective_target_pct"] == 13.0
    assert p80["effective_rr"] == 1.3


def test_effective_rr_never_expands_a_near_structure_target():
    detail = _detail("2026-09-01", "a", target=10.8)
    refs = {"buy1|pivot_zg|5": {"sample_count": 4,
             "mfe_pct": {"p50": 10.0, "p70": 12.0, "p80": 15.0}}}
    row = audit.effective_rr_shadow(detail, refs)
    for value in row["windows"]["5"]["estimates"].values():
        assert value["effective_target_pct"] == 8.0
        assert value["effective_rr"] == 0.8


def test_effective_rr_unavailable_is_explicit_not_zero():
    bad = _detail("2026-09-01", "a", stop=10.0)
    row = audit.effective_rr_shadow(bad, {})
    assert row["status"] == "unavailable"
    assert row["reason"] == "invalid_entry_stop_target"
    good = _detail("2026-09-01", "b")
    row = audit.effective_rr_shadow(good, {})
    assert row["windows"]["5"] == {
        "status": "unavailable", "reason": "no_mfe_reference"}


def test_build_audit_reports_independent_days_and_all_group_dimensions():
    signals = [
        {"signal_date": "2026-09-01", "code": "b", "type": "buy1"},
        {"signal_date": "2026-09-01", "code": "a", "type": "sell1"},
        {"signal_date": "2026-09-02", "code": "c", "type": "buy3"},
    ]
    details = [
        _detail("2026-09-01", "b", score=86),
        _detail("2026-09-01", "a", ty="sell1", score=70, target_type=None),
        _detail("2026-09-02", "c", ty="buy3", score=76, target_type="partial_take"),
    ]
    out = audit.build_audit(signals, details, period="fixture")
    assert out["coverage"]["signal_count"] == 3
    assert out["coverage"]["signal_day_count"] == 2
    assert out["coverage"]["mature_by_window"]["5"] == 3
    assert set(out["grouped_window_stats"]) == {"type", "score_bucket", "target_type"}
    assert set(out["grouped_window_stats"]["score_bucket"]) == {"60-74", "75-84", "85+"}


def test_json_and_markdown_outputs_are_deterministic():
    signals = [{"signal_date": "2026-09-02", "code": "b", "type": "sell1"},
               {"signal_date": "2026-09-01", "code": "a", "type": "buy1"}]
    details = [_detail("2026-09-01", "a")]
    first = audit.build_audit(signals, details, period="x")
    second = audit.build_audit(list(reversed(signals)), copy.deepcopy(details), period="x")
    assert audit.render_json(first) == audit.render_json(second)
    assert json.loads(audit.render_json(first))["shadow_only"] is True
    md = audit.render_markdown(first)
    assert "independent signal days: 2" in md
    assert "no trading decision is changed" in md
    assert "would block long" in md


def test_score_bucket_handles_boundaries_and_missing():
    assert audit.score_bucket(None) == "unavailable"
    assert audit.score_bucket(59.99) == "<60"
    assert audit.score_bucket(60) == "60-74"
    assert audit.score_bucket(75) == "75-84"
    assert audit.score_bucket(85) == "85+"
