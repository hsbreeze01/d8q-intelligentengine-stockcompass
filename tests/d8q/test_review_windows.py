# -*- coding: utf-8 -*-
"""review_weekly 多窗口复盘口径测试 (5/10/20 日 + MFE/MAE + R 倍数期望)

覆盖点:
- _risk_pct: 初始风险幅度换算与缺失止损兜底
- _r_multiples: R 倍数与"触发止损记 -1R"的执行口径
- _buy_window_metrics / _sell_window_metrics: MFE/MAE 方向归一
- 多窗口切片: 短窗满窗、长窗 pending
- compute_window_stats: 胜率/盈亏比/盈亏平衡胜率/期望
- 向后兼容: 旧字段(day5_pnl_pct / max_profit_pct / hit_stop_loss)仍保持 5 日语义
"""
import chanlun.strategy.review_weekly as rw


def _bar(o, h, lo, c):
    return {'open': o, 'high': h, 'low': lo, 'close': c, 'volume': 1000}


def _ramp(n, start=10.0, step=0.0):
    """生成 n 根K线, 每根收盘价 = start + i*step"""
    bars = []
    for i in range(n):
        c = start + i * step
        bars.append(_bar(c, c + 0.05, c - 0.05, c))
    return bars


# --- _risk_pct ---------------------------------------------------------------

def test_risk_pct_from_stop_loss():
    # 基准 10.0, 止损 9.2 => 风险 8%
    assert rw._risk_pct(10.0, 9.2) == 8.0


def test_risk_pct_falls_back_to_default_when_no_stop():
    # 无止损价时回退 DEFAULT_STOP_LOSS_PCT(-0.08) => 8%
    assert rw._risk_pct(10.0, None) == 8.0
    assert rw._risk_pct(10.0, 0) == 8.0


# --- _r_multiples ------------------------------------------------------------

def test_r_multiple_raw_and_realized_without_stop():
    # 涨 4%, 风险 8% => 0.5R; 未触发止损则 realized == raw
    r_raw, r_real = rw._r_multiples(4.0, 8.0, False)
    assert r_raw == 0.5
    assert r_real == 0.5


def test_r_multiple_realized_is_minus_one_when_stopped():
    # 触发止损: 无论窗口末涨跌, 实际执行口径记 -1R
    r_raw, r_real = rw._r_multiples(6.0, 8.0, True)
    assert r_raw == 0.75
    assert r_real == -1.0


def test_r_multiple_none_when_no_pnl():
    assert rw._r_multiples(None, 8.0, False) == (None, None)


# --- 买入窗口指标 ------------------------------------------------------------

def test_buy_window_mfe_mae_and_pnl():
    # 基准 10.0; 窗口内最高 11.0(MFE +10%), 最低 9.5(MAE -5%), 末收 10.5(+5%)
    bars = [_bar(10.0, 10.2, 9.5, 9.8),
            _bar(9.8, 11.0, 9.7, 10.9),
            _bar(10.9, 10.9, 10.4, 10.5)]
    m = rw._buy_window_metrics(bars, 10.0, None, 8.0)
    assert m['mfe_pct'] == 10.0
    assert m['mae_pct'] == -5.0
    assert m['pnl_pct'] == 5.0
    assert m['win'] is True
    # max_profit_pct 与 MFE 同义(旧字段兼容)
    assert m['max_profit_pct'] == m['mfe_pct']


def test_buy_window_detects_stop_loss_hit():
    # 止损 9.2, 第二根最低 9.1 => 触发
    bars = [_bar(10.0, 10.1, 9.8, 9.9), _bar(9.9, 10.0, 9.1, 9.3)]
    m = rw._buy_window_metrics(bars, 10.0, 9.2, 8.0)
    assert m['hit_stop_loss'] is True
    # 触发止损 => realized 记 -1R
    assert m['r_realized'] == -1.0


def test_buy_window_stop_loss_fallback_uses_default_pct():
    # 无止损价, 但跌幅超过默认 -8% => 兜底判定触发
    bars = [_bar(10.0, 10.0, 9.1, 9.2)]
    m = rw._buy_window_metrics(bars, 10.0, None, 8.0)
    assert m['hit_stop_loss'] is True


def test_buy_window_actionable_uses_range_overlap():
    # entry_zone = 10.0 +/- 3% = [9.7, 10.3]; K线区间 [10.5,11.0] 无交集 => 不可操作
    bars = [_bar(10.6, 11.0, 10.5, 10.9)]
    m = rw._buy_window_metrics(bars, 10.0, None, 8.0)
    assert m['had_chance'] is False
    # 区间下探进入 zone => 可操作
    bars2 = [_bar(10.6, 11.0, 10.2, 10.9)]
    assert rw._buy_window_metrics(bars2, 10.0, None, 8.0)['had_chance'] is True


# --- 卖出窗口指标(方向归一) --------------------------------------------------

def test_sell_window_mfe_is_positive_when_price_falls():
    # 卖出后下跌 = 有利. 基准 10.0, 最低 9.0 => MFE +10%; 最高 10.2 => MAE -2%
    bars = [_bar(10.0, 10.2, 9.0, 9.5)]
    m = rw._sell_window_metrics(bars, 10.0, 8.0)
    assert m['mfe_pct'] == 10.0
    assert m['mae_pct'] == -2.0
    # 窗口末收 9.5 低于基准 => 避险有效
    assert m['effective'] is True
    assert m['win'] is True
    # 卖出的 R 倍数: 下跌为正收益 => -(-5%)/8% = 0.625R
    assert m['r_raw'] == 0.625


def test_sell_window_false_alarm_when_price_rises():
    # 涨超 SELL_FALSE_ALARM_PCT(3%) => 误报
    bars = [_bar(10.0, 10.5, 10.0, 10.4)]
    m = rw._sell_window_metrics(bars, 10.0, 8.0)
    assert m['false_alarm'] is True
    assert m['effective'] is False
    assert m['mae_pct'] == -5.0


# --- 多窗口切片 --------------------------------------------------------------

def test_analyze_buy_signal_builds_all_windows():
    sig = {'stop_loss': 9.2}
    bars = _ramp(20, start=10.0, step=0.1)
    out = rw.analyze_buy_signal(sig, bars, 10.0, 'entry_price')
    assert set(out['windows'].keys()) == {'5', '10', '20'}
    for w in ('5', '10', '20'):
        assert out['windows'][w]['window_complete'] is True
    # 窗口越长, 上涨行情下 MFE 越大
    assert out['windows']['20']['mfe_pct'] > out['windows']['5']['mfe_pct']


def test_short_window_complete_long_window_pending():
    # 只有 12 根后续K线: 5/10 满窗, 20 未满
    sig = {'stop_loss': 9.2}
    bars = _ramp(12, start=10.0, step=0.1)
    out = rw.analyze_buy_signal(sig, bars, 10.0, 'entry_price')
    assert out['windows']['5']['window_complete'] is True
    assert out['windows']['10']['window_complete'] is True
    assert out['windows']['20']['window_complete'] is False
    # 未满窗仍会给出已有K线的指标, 但 bars_used 反映真实根数
    assert out['windows']['20']['bars_used'] == 12
    assert out['windows']['10']['bars_used'] == 10


def test_buy_legacy_fields_keep_five_day_semantics():
    """旧字段必须等于 5 日窗口的值, 保证既有前端/推送不受影响"""
    sig = {'stop_loss': 9.2}
    bars = _ramp(20, start=10.0, step=0.1)
    out = rw.analyze_buy_signal(sig, bars, 10.0, 'entry_price')
    w5 = out['windows']['5']
    assert out['day5_pnl_pct'] == w5['pnl_pct']
    assert out['max_profit_pct'] == w5['max_profit_pct']
    assert out['hit_stop_loss'] == w5['hit_stop_loss']
    assert out['had_chance'] == w5['had_chance']


def test_sell_legacy_fields_keep_five_day_semantics():
    sig = {'stop_loss': 10.8}
    bars = _ramp(20, start=10.0, step=-0.1)
    out = rw.analyze_sell_signal(sig, bars, 10.0, 'entry_price')
    w5 = out['windows']['5']
    assert out['day5_pnl_pct'] == w5['pnl_pct']
    assert out['avoided_loss_pct'] == w5['avoided_loss_pct']
    assert out['effective'] == w5['effective']


# --- 窗口统计 ----------------------------------------------------------------

def _mk_detail(side, window_vals):
    """构造带 windows 的 detail; window_vals: {window: metrics_dict}"""
    return {'side': side, 'windows': window_vals}


def test_compute_window_stats_only_counts_complete_windows():
    d_complete = _mk_detail('buy', {'5': {'window_complete': True, 'win': True,
                                          'pnl_pct': 4.0, 'mfe_pct': 5.0, 'mae_pct': -1.0,
                                          'r_raw': 0.5, 'r_realized': 0.5,
                                          'hit_stop_loss': False, 'had_chance': True}})
    d_pending = _mk_detail('buy', {'5': {'window_complete': False, 'win': True,
                                         'pnl_pct': 99.0, 'mfe_pct': 99.0, 'mae_pct': 0.0,
                                         'r_raw': 9.9, 'r_realized': 9.9,
                                         'hit_stop_loss': False, 'had_chance': True}})
    s = rw.compute_window_stats([d_complete, d_pending], 5, 'buy')
    # 未满窗的信号不得进入统计(否则会污染指标)
    assert s['count'] == 1
    assert s['avg_pnl'] == 4.0
    assert s['expectancy_r'] == 0.5


def test_compute_window_stats_expectancy_and_payoff():
    """2 胜 2 负: 胜均 +6%, 负均 -3% => 盈亏比 2.0, 盈亏平衡胜率 0.33"""
    def mk(win, pnl, r):
        return _mk_detail('buy', {'5': {'window_complete': True, 'win': win,
                                        'pnl_pct': pnl, 'mfe_pct': abs(pnl),
                                        'mae_pct': -abs(pnl), 'r_raw': r, 'r_realized': r,
                                        'hit_stop_loss': False, 'had_chance': True}})
    rows = [mk(True, 6.0, 0.75), mk(True, 6.0, 0.75),
            mk(False, -3.0, -0.375), mk(False, -3.0, -0.375)]
    s = rw.compute_window_stats(rows, 5, 'buy')
    assert s['count'] == 4
    assert s['win_rate'] == 0.5
    assert s['payoff_ratio'] == 2.0
    assert s['breakeven_win_rate'] == 0.33
    # 期望 = (0.75+0.75-0.375-0.375)/4 = 0.1875 -> round 3
    assert s['expectancy_r'] == 0.188


def test_compute_window_stats_empty_returns_zeros():
    s = rw.compute_window_stats([], 20, 'buy')
    assert s['count'] == 0
    assert s['win_rate'] == 0
    assert s['expectancy_r'] == 0
    assert 'stop_loss_hit_rate' in s
    s2 = rw.compute_window_stats([], 20, 'sell')
    assert 'effective_rate' in s2 and 'false_alarm_rate' in s2


def test_compute_all_window_stats_covers_every_window():
    out = rw.compute_all_window_stats([], 'buy')
    assert set(out.keys()) == {str(w) for w in rw.REVIEW_WINDOWS}


def test_compute_pending_by_window_counts_per_window():
    # 一个买入信号: 5 日满窗, 20 日未满 => 只在 20 日档计 pending
    d = _mk_detail('buy', {'5': {'window_complete': True},
                           '10': {'window_complete': True},
                           '20': {'window_complete': False}})
    out = rw.compute_pending_by_window([d])
    assert out['5']['buy_count'] == 0
    assert out['10']['buy_count'] == 0
    assert out['20']['buy_count'] == 1
    assert out['20']['sell_count'] == 0


# --- 配置一致性 --------------------------------------------------------------

def test_review_windows_config_is_consistent():
    # 最短窗口必须等于 MIN_REVIEW_BARS, 否则 <5 根被整体剔除的信号会漏掉可评估窗口
    assert min(rw.REVIEW_WINDOWS) == rw.MIN_REVIEW_BARS
    assert rw.MAX_REVIEW_WINDOW == max(rw.REVIEW_WINDOWS)
    assert rw.REVIEW_WINDOW_BARS in rw.REVIEW_WINDOWS


def test_empty_result_exposes_window_blocks():
    r = rw.empty_result('2026-W35', '2026-08-25 ~ 2026-08-29')
    assert r['review_windows'] == list(rw.REVIEW_WINDOWS)
    assert set(r['buy_by_window'].keys()) == {str(w) for w in rw.REVIEW_WINDOWS}
    assert set(r['sell_by_window'].keys()) == {str(w) for w in rw.REVIEW_WINDOWS}
    assert set(r['pending_by_window'].keys()) == {str(w) for w in rw.REVIEW_WINDOWS}


def test_webhook_key_not_hardcoded():
    """凭据必须来自环境变量, 不得硬编码入源码"""
    import inspect
    src = inspect.getsource(rw)
    assert '7c097c2e' not in src
    assert 'D8Q_REVIEW_WECOM_KEY' in src


# --- 市场环境归因 ------------------------------------------------------------

def test_summarize_market_context_empty():
    m = rw.summarize_market_context({})
    assert m['available'] is False
    assert m['by_date'] == {}


def test_summarize_market_context_detects_rising_regime():
    ctx = {
        '2026-08-24': {'composite': 33.93, 'phase': '修复'},
        '2026-08-27': {'composite': 76.77, 'phase': '亢奋'},
    }
    m = rw.summarize_market_context(ctx)
    assert m['available'] is True
    assert m['min_composite'] == 33.93
    assert m['max_composite'] == 76.77
    assert m['avg_composite'] == 55.35
    # 情绪升温 => 胜率含 beta 成分, 必须标注
    assert m['rising'] is True
    # 相位按温度序(冰点->过热)排列, 不是码点序('亢奋'码点小于'修复')
    assert m['phase_span'] == ['修复', '亢奋']


def test_phase_span_sorted_by_temperature_not_codepoint():
    ctx = {
        'd1': {'composite': 10.0, 'phase': '过热'},
        'd2': {'composite': 20.0, 'phase': '冰点'},
        'd3': {'composite': 30.0, 'phase': '温和'},
    }
    # 码点序会给出 ['冰点','温和','过热'] 之外的顺序; 必须按温度档位排
    assert rw.summarize_market_context(ctx)['phase_span'] == ['冰点', '温和', '过热']


def test_phase_order_matches_sentiment_module_semantics():
    # 与 datafactory/sentiment.py PHASES 的 5 档一致
    assert rw.PHASE_ORDER == ['冰点', '修复', '温和', '亢奋', '过热']


# --- 推送守卫 ----------------------------------------------------------------

def test_push_skips_without_credential(monkeypatch):
    """无凭据时跳过推送且不抛异常(复盘计算不能被推送失败阻断)"""
    monkeypatch.setattr(rw, 'WEBHOOK_KEY', '')
    r = rw._push_wecom('hello')
    assert r['errcode'] == -2


def test_format_review_push_includes_window_block():
    """推送内容需带多窗口口径, 否则用户只看到会低估的5日胜率"""
    result = rw.empty_result('2026-W35', '2026-08-24 ~ 2026-08-28')
    result['buy_summary'] = {'count': 10, 'actionable_rate': 1.0, 'avg_max_profit': 6.9,
                             'win_rate_5d': 0.71, 'stop_loss_hit_rate': 0.03}
    result['buy_by_window']['5'].update(
        {'count': 10, 'win_rate': 0.71, 'payoff_ratio': 1.99,
         'expectancy_r': 0.444, 'avg_mfe': 6.96, 'avg_mae': -2.24})
    msg = rw._format_review_push(result)
    assert '多窗口口径' in msg
    assert '期望' in msg


def test_format_review_push_returns_none_when_nothing_to_report():
    assert rw._format_review_push(rw.empty_result('2026-W35', 'x ~ y')) is None


def test_summarize_market_context_detects_falling_regime():
    ctx = {
        '2026-08-24': {'composite': 70.0, 'phase': '亢奋'},
        '2026-08-27': {'composite': 30.0, 'phase': '修复'},
    }
    assert rw.summarize_market_context(ctx)['rising'] is False


def test_compute_by_phase_splits_by_sentiment_phase():
    """环境分层归因: 同样的窗口指标按情绪相位拆开, 才能看出环境是否该做闸门"""
    def mk(phase, win, pnl, r, stopped=False):
        return {'side': 'buy', 'sentiment_phase': phase,
                'windows': {'5': {'window_complete': True, 'win': win, 'pnl_pct': pnl,
                                  'mfe_pct': abs(pnl), 'mae_pct': -abs(pnl),
                                  'r_raw': r, 'r_realized': r,
                                  'hit_stop_loss': stopped, 'had_chance': True}}}
    rows = [mk('亢奋', True, 5.0, 0.6), mk('亢奋', True, 5.0, 0.6),
            mk('冰点', False, -4.0, -1.0, stopped=True)]
    out = rw.compute_by_phase(rows, 5, 'buy')
    assert set(out.keys()) == {'亢奋', '冰点'}
    assert out['亢奋']['count'] == 2
    assert out['亢奋']['win_rate'] == 1.0
    assert out['冰点']['count'] == 1
    assert out['冰点']['win_rate'] == 0.0
    assert out['冰点']['stop_loss_hit_rate'] == 1.0


def test_compute_by_phase_ignores_signals_without_phase():
    rows = [{'side': 'buy', 'windows': {'5': {'window_complete': True, 'win': True,
                                              'pnl_pct': 1.0, 'r_raw': 0.1,
                                              'r_realized': 0.1}}}]
    assert rw.compute_by_phase(rows, 5, 'buy') == {}
