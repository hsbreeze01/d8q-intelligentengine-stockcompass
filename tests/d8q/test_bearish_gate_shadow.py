# -*- coding: utf-8 -*-
"""选项B: 环境闸门影子观测逻辑测试 (2026-09-04)。

锁定 czsc_scan.scan() 内 buy 环境闸门 + 影子计数的决策语义:
- default(filter_bearish_buys=False): bearish 环境下累计影子计数, 但 buys 不被清空(行为不变)
- experimental(filter=True): bearish 环境下累计影子计数, 且 buys 被清空(真拦)
- bullish 环境: 不累计、不清空
- 无 buy 信号: 不累计

复刻 scan() 内联逻辑(若 scan 改动需同步), 与 test_czsc_scan_profile 的 _resolve 同风格。
不连 DB、不写文件。
"""


def _gate(buys, market_bullish, filter_bearish_buys, shadow=0):
    """复刻 scan() 内 buy 环境闸门 + 影子观测决策。

    返回 (处理后的 buys, 更新后的 shadow 计数)。
    """
    _mkt_blocks_long = not market_bullish
    if buys and _mkt_blocks_long:
        shadow += len(buys)
        if filter_bearish_buys:
            buys = []
    return buys, shadow


def test_default_bearish_counts_shadow_but_keeps_buys():
    # default: 空头环境下累计影子计数, 但买入信号保留(选股行为不变)
    buys = [{'type': 'buy1'}, {'type': 'buy3'}]
    out, shadow = _gate(buys, market_bullish=False, filter_bearish_buys=False)
    assert out == buys          # 未被清空
    assert shadow == 2          # 影子计数累计


def test_experimental_bearish_counts_and_blocks():
    # experimental: 空头环境下累计影子计数, 且真正清空买入
    buys = [{'type': 'buy1'}, {'type': 'buy2'}, {'type': 'buy3'}]
    out, shadow = _gate(buys, market_bullish=False, filter_bearish_buys=True)
    assert out == []            # 被拦
    assert shadow == 3


def test_bullish_no_shadow_no_block_default():
    buys = [{'type': 'buy1'}]
    out, shadow = _gate(buys, market_bullish=True, filter_bearish_buys=False)
    assert out == buys
    assert shadow == 0


def test_bullish_no_shadow_no_block_experimental():
    buys = [{'type': 'buy1'}]
    out, shadow = _gate(buys, market_bullish=True, filter_bearish_buys=True)
    assert out == buys          # bullish 时即便闸门开启也不拦
    assert shadow == 0


def test_no_buys_no_shadow():
    out, shadow = _gate([], market_bullish=False, filter_bearish_buys=True)
    assert out == []
    assert shadow == 0


def test_shadow_accumulates_across_stocks():
    # 模拟多只股票循环累加
    shadow = 0
    _, shadow = _gate([{'type': 'buy1'}], False, False, shadow)
    _, shadow = _gate([{'type': 'buy1'}, {'type': 'buy3'}], False, False, shadow)
    _, shadow = _gate([{'type': 'buy1'}], True, False, shadow)   # bullish 不计
    assert shadow == 3
