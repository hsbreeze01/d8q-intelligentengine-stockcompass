# -*- coding: utf-8 -*-
"""buy1 目标中枢时效闸门测试 (方案A, OR 判定)。

隔离测试 detect_buy1 的 target 选择逻辑:
- 中枢新鲜(edt 近) 且 zg 涨幅合理(<=30%) -> 保留 pivot_zg
- 中枢陈旧(edt > 60 天) -> 降级 fixed_pct (OR 命中1)
- zg 涨幅虚高(> 30%) -> 降级 fixed_pct (OR 命中2)
- 601012 场景(双命中) -> fixed_pct
- zg 不在现价上方 -> fixed_pct

用轻量 stub 对象 + monkeypatch last_divergence, 避免构造完整 FX/BI/ZS 结构链。
"""
import datetime
import pytest

from chanlun.engine import czsc_buysell as cb
from chanlun.czsc_core import Direction


class _StubBI:
    """仅实现 detect_buy1 访问到的属性: direction / low / edt / raw_bars。"""
    def __init__(self, edt, low=10.0, direction=Direction.Down):
        self.direction = direction
        self.low = low
        self.edt = edt
        self.raw_bars = []  # 使 _exec_price 走 fallback closes[-1]


class _StubZS:
    """中枢 stub: 提供 zg / edt / bis(长度用于 consolidation 门槛)。"""
    def __init__(self, zg, edt, n_bis=5):
        self.zg = zg
        self.edt = edt
        self.bis = [None] * n_bis


@pytest.fixture
def patch_divergence(monkeypatch):
    """强制 last_divergence 返回下跌盘整背驰, 让 detect_buy1 走到 target 分支。"""
    monkeypatch.setattr(
        cb, "last_divergence",
        lambda bis, zs, closes: {"is_divergence": True,
                                 "direction": Direction.Down,
                                 "kind": "consolidation",
                                 "ratio": 0.5},
    )


def _run(zg, pivot_edt, signal_edt, exec_price):
    """构造单笔下跌 + 单中枢, 返回 detect_buy1 输出的首个信号。

    closes[-1] 即 exec_price (因 raw_bars 为空走 fallback)。
    """
    last_bi = _StubBI(edt=signal_edt, low=exec_price * 0.98)
    zs = _StubZS(zg=zg, edt=pivot_edt, n_bis=5)
    closes = [exec_price]
    sigs = cb.detect_buy1([last_bi], [zs], closes)
    assert len(sigs) == 1
    return sigs[0]


T = datetime.datetime(2026, 9, 4)


def test_fresh_pivot_reasonable_gain_keeps_pivot_zg(patch_divergence):
    # 中枢 5 天前结束, zg 涨幅 20% (<30%) -> 保留 pivot_zg
    sig = _run(zg=12.0, pivot_edt=T - datetime.timedelta(days=5),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "pivot_zg"
    assert sig["target_price"] == 12.0


def test_stale_pivot_downgrades_fixed_pct(patch_divergence):
    # 中枢 90 天前结束 (>60), 涨幅仅 10% -> OR 命中(时效) -> fixed_pct
    sig = _run(zg=11.0, pivot_edt=T - datetime.timedelta(days=90),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "fixed_pct"
    assert sig["target_price"] == round(10.0 * 1.09, 2)  # 10.9


def test_overinflated_gain_downgrades_fixed_pct(patch_divergence):
    # 中枢新鲜(5天), 但 zg 涨幅 50% (>30%) -> OR 命中(涨幅) -> fixed_pct
    sig = _run(zg=15.0, pivot_edt=T - datetime.timedelta(days=5),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "fixed_pct"
    assert sig["target_price"] == round(10.0 * 1.09, 2)


def test_601012_scenario_both_hit_fixed_pct(patch_divergence):
    # 601012: 旧中枢 zg=19.33, 入场 12.18 (涨幅 ~58.7% >30) 且中枢 ~120天前 -> 双命中
    sig = _run(zg=19.33, pivot_edt=T - datetime.timedelta(days=120),
               signal_edt=T, exec_price=12.18)
    assert sig["target_type"] == "fixed_pct"
    assert sig["target_price"] == round(12.18 * 1.09, 2)  # 13.28


def test_zg_below_exec_uses_fixed_pct(patch_divergence):
    # zg 在现价下方 (中枢下沿逻辑) -> 目标必须高于入场 -> fixed_pct
    sig = _run(zg=9.5, pivot_edt=T - datetime.timedelta(days=3),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "fixed_pct"
    assert sig["target_price"] == round(10.0 * 1.09, 2)


def test_boundary_gain_just_under_30pct_keeps_pivot_zg(patch_divergence):
    # 涨幅 29% (< 30%), 中枢新鲜 -> 保留 pivot_zg
    # (注: 正好 13.0/10.0-1 因浮点表示略大于 0.30 会判失效, 属边界不确定区, 故取明确 29%)
    sig = _run(zg=12.9, pivot_edt=T - datetime.timedelta(days=5),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "pivot_zg"
    assert sig["target_price"] == 12.9


def test_boundary_gain_just_over_30pct_downgrades(patch_divergence):
    # 涨幅 31% (> 30%) -> fixed_pct
    sig = _run(zg=13.1, pivot_edt=T - datetime.timedelta(days=5),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "fixed_pct"
    assert sig["target_price"] == round(10.0 * 1.09, 2)


def test_boundary_days_exactly_60_keeps_pivot_zg(patch_divergence):
    # 中枢正好 60 天 (不 > 60), 涨幅合理 -> 保留 pivot_zg
    sig = _run(zg=11.0, pivot_edt=T - datetime.timedelta(days=60),
               signal_edt=T, exec_price=10.0)
    assert sig["target_type"] == "pivot_zg"
    assert sig["target_price"] == 11.0
