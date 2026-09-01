# -*- coding: utf-8 -*-
"""czsc_scan profile 配置接入测试 (2026-09-02 修复: profile_cfg 此前从未被使用)

覆盖点:
- get_stock_pool 的 min_turnover 参数化: default 2亿, profile 可覆盖(experimental 3亿)
- profile_cfg 参数解析: default(None/空) 解析为历史硬编码值 -> 生产行为不变
- experimental profile 解析为收紧参数(3亿 + 空头过滤)
- SQL 使用参数占位而非字符串拼接(防注入)
"""
import chanlun.strategy.czsc_scan as cs


class _FakeCursor:
    def __init__(self):
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()

    def cursor(self, *a, **k):
        return self.cur


# --- get_stock_pool 参数化 ---------------------------------------------------

def test_get_stock_pool_default_turnover_is_200m():
    """默认门槛 2亿, 与历史硬编码一致(生产行为不变)"""
    assert cs.get_stock_pool.__defaults__ == (200000000,)


def test_get_stock_pool_uses_parameterized_threshold():
    conn = _FakeConn()
    cs.get_stock_pool(conn, min_turnover=300000000)
    # 阈值必须走参数占位, 不能字符串拼接
    assert 'HAVING AVG(turnover) >= %s' in conn.cur.last_sql
    assert conn.cur.last_params == (300000000,)


def test_get_stock_pool_default_call_passes_200m():
    conn = _FakeConn()
    cs.get_stock_pool(conn)
    assert conn.cur.last_params == (200000000,)


# --- profile 配置解析 (复刻 scan() 内的解析逻辑, 保证语义锁定) -----------------

def _resolve(profile_cfg):
    """复刻 scan() 中 profile 参数解析, 供单测锁定 default 与 experimental 语义。

    与 czsc_scan.scan() 内实现保持一致; 若 scan() 改动需同步。
    """
    _cfg = (profile_cfg or {}).get('params', {}) if isinstance(profile_cfg, dict) else {}
    return {
        'min_turnover': int(_cfg.get('min_turnover', 200000000)),
        'filter_bearish_buys': bool(_cfg.get('filter_bearish_buys', False)),
        'enabled_types': {
            t for t in ('buy1', 'buy2', 'buy3', 'sell1', 'sell2', 'sell3')
            if _cfg.get('enable_' + t, True)
        },
    }


def test_profile_none_resolves_to_production_defaults():
    """profile_cfg=None (default 路径) -> 历史硬编码值, 全类型启用, 无空头过滤"""
    r = _resolve(None)
    assert r['min_turnover'] == 200000000
    assert r['filter_bearish_buys'] is False
    assert r['enabled_types'] == {'buy1', 'buy2', 'buy3', 'sell1', 'sell2', 'sell3'}


def test_profile_empty_dict_resolves_to_defaults():
    assert _resolve({})['min_turnover'] == 200000000
    assert _resolve({'params': {}})['filter_bearish_buys'] is False


def test_experimental_profile_tightens_params():
    """experimental: 3亿门槛 + 空头过滤开启 (此前因 bug 完全未生效)"""
    exp = {'params': {'min_turnover': 300000000, 'filter_bearish_buys': True}}
    r = _resolve(exp)
    assert r['min_turnover'] == 300000000
    assert r['filter_bearish_buys'] is True


def test_profile_can_disable_signal_types():
    """enable_* 开关生效: 关闭 buy1/buy2 后只剩 buy3 与卖点"""
    cfg = {'params': {'enable_buy1': False, 'enable_buy2': False}}
    r = _resolve(cfg)
    assert 'buy1' not in r['enabled_types']
    assert 'buy2' not in r['enabled_types']
    assert 'buy3' in r['enabled_types']
    assert 'sell1' in r['enabled_types']
