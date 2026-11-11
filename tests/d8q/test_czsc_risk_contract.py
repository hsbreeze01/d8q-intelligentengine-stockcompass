"""止损/目标公式显式契约：只补可观测字段，不改变既有价格。"""
import pytest

from chanlun.engine.czsc_buysell import (
    FORMULA_VERSION, _buy_stop, _risk_contract, _sell_stop,
)


def test_buy_structure_branch_preserves_existing_stop_price():
    contract = _risk_contract(
        "buy", 95.0, 100.0, "bi_low", 100.0, "2026-11-10",
        0.05, 120.0, "pivot_zg", 120.0, "2026-10-31")
    assert contract["stop_loss"] == _buy_stop(95.0, 100.0) == 95.0
    assert contract["stop_basis"] == "structure_buffer"
    assert contract["formula_version"] == FORMULA_VERSION
    assert contract["rr_at_signal"] == pytest.approx(4.0)


def test_buy_signal_cap_branch_preserves_existing_stop_price():
    contract = _risk_contract(
        "buy", 85.0, 100.0, "bi_low", 89.47, "2026-11-10",
        0.05, 116.0, "fixed_pct", 100.0, "2026-11-10")
    assert contract["stop_loss"] == _buy_stop(85.0, 100.0) == 92.0
    assert contract["stop_basis"] == "signal_cap"
    assert contract["stop_cap_pct"] == 0.08
    assert contract["structure_ref_type"] == "bi_low"


def test_sell_structure_and_cap_branches_preserve_prices():
    structural = _risk_contract(
        "sell", 105.0, 100.0, "bi_high", 100.0, "2026-11-10",
        0.05, 90.0, "pivot_zd", 90.0, "2026-10-31")
    capped = _risk_contract(
        "sell", 115.0, 100.0, "bi_high", 109.52, "2026-11-10",
        0.05, 90.0, "previous_low", 90.0, "2026-11-01")
    assert structural["stop_loss"] == _sell_stop(105.0, 100.0) == 105.0
    assert structural["stop_basis"] == "structure_buffer"
    assert capped["stop_loss"] == _sell_stop(115.0, 100.0) == 108.0
    assert capped["stop_basis"] == "signal_cap"


def test_invalidation_only_has_explicit_basis_without_fake_rr():
    contract = _risk_contract(
        "sell", 103.0, 100.0, "pivot_zd", 103.0, "2026-11-01",
        0.0, None, "invalidation_only")
    assert contract["target_basis"] == "invalidation_only"
    assert contract["target_ref_price"] is None
    assert contract["rr_at_signal"] is None
