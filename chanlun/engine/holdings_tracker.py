# -*- coding: utf-8 -*-
"""持仓跟踪器: 管理 holdings.json 的读写和出场条件检查。

规则(来自optimization-plan):
- 止损: 收盘价跌破止损价 → 次日离场
- 移动止盈: 盈利>=8%后回撤3% → 次日离场
- 超时: 持仓满10天 → 次日离场
"""
import json, os
from datetime import datetime, date

HOLDINGS_PATH = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/holdings.json'
MAX_HOLD_DAYS = 10
TRAILING_TRIGGER = 0.08  # 8%盈利触发
TRAILING_DRAWDOWN = 0.03  # 3%回撤离场


def load_holdings() -> list:
    try:
        if os.path.exists(HOLDINGS_PATH):
            with open(HOLDINGS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_holdings(holdings: list):
    os.makedirs(os.path.dirname(HOLDINGS_PATH), exist_ok=True)
    with open(HOLDINGS_PATH, 'w') as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2, default=str)


def next_trading_day(d, trading_days=None):
    """返回 d 之后的第一个交易日(字符串 YYYY-MM-DD)。

    B1-6: 信号在收盘后产生, 实际建仓发生在次一交易日。
    旧实现用信号日作 entry_date, 使持仓天数早算一天, 10天超时提前触发。
    无交易日历时按自然日跳过周末近似。
    """
    from datetime import timedelta
    if isinstance(d, str):
        d = datetime.strptime(d[:10], '%Y-%m-%d').date()
    if trading_days:
        later = [x for x in trading_days if x > d]
        if later:
            return str(min(later))
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:      # 跳过周六(5)/周日(6)
        nxt += timedelta(days=1)
    return str(nxt)


def add_holding(sig: dict, trading_days=None) -> dict:
    """从信号创建持仓记录"""
    _sig_dt = str(sig.get('dt') or datetime.now())[:10]
    # B2-4: 成本价用可执行价(exec_price/entry_price), 不用 price 兜底以外的结构极值。
    # 旧实现直接取 sig['price'], 而 buy1/buy2 的 price 曾是笔极值(不可成交),
    # 导致持仓成本虚低、pnl 虚高(如联环药业 14.73 / +4.7%)。
    _exec = sig.get('exec_price') or sig.get('entry_price') or sig.get('price')
    return {
        'code': sig['code'],
        'name': sig.get('name', ''),
        'type': sig['type'],
        'entry_price': _exec,
        'signal_ref_price': sig.get('signal_ref_price'),
        'stop_loss': sig['stop_loss'],
        'signal_date': _sig_dt,
        # B1-6: 实际建仓日 = 信号日的次一交易日
        'entry_date': next_trading_day(_sig_dt, trading_days),
        'score': sig.get('score', 0),
        'grade_label': sig.get('grade_label', ''),
        'max_close': _exec,  # 跟踪最高收盘价(基于可执行成本价)
        'status': 'holding',
        'exit_reason': None,
        'exit_date': None,
    }


def check_exit(holding: dict, last_close: float, today_str: str = None) -> dict:
    """检查出场条件，返回更新后的 holding（status可能变为exit_xxx）"""
    if today_str is None:
        today_str = date.today().isoformat()

    entry_price = holding['entry_price']
    stop_loss = holding['stop_loss']
    max_close = holding.get('max_close', entry_price)

    # 更新最高收盘价
    if last_close > max_close:
        holding['max_close'] = last_close
        max_close = last_close

    # 计算指标
    pnl_pct = (last_close - entry_price) / entry_price
    from_max_pct = (max_close - last_close) / max_close if max_close > 0 else 0

    # 持仓天数
    try:
        entry_d = datetime.strptime(holding['entry_date'][:10], '%Y-%m-%d').date()
        today_d = datetime.strptime(today_str[:10], '%Y-%m-%d').date()
        days = (today_d - entry_d).days
    except:
        days = 0

    holding['days'] = days
    holding['pnl_pct'] = round(pnl_pct * 100, 1)
    holding['last_close'] = last_close

    # 出场条件判定
    if last_close <= stop_loss:
        holding['status'] = 'exit_stoploss'
        holding['exit_reason'] = '止损(收盘%.2f<=止损%.2f)' % (last_close, stop_loss)
        holding['exit_date'] = today_str
    elif pnl_pct >= TRAILING_TRIGGER and from_max_pct >= TRAILING_DRAWDOWN:
        holding['status'] = 'exit_trailing'
        holding['exit_reason'] = '移动止盈(盈利%.1f%%后回撤%.1f%%)' % (pnl_pct*100, from_max_pct*100)
        holding['exit_date'] = today_str
    elif days >= MAX_HOLD_DAYS:
        holding['status'] = 'exit_timeout'
        holding['exit_reason'] = '超时(%d天)' % days
        holding['exit_date'] = today_str

    return holding


def update_holdings_daily(stock_prices: dict):
    """每日更新: 传入 {code: last_close} 字典，检查所有持仓的出场条件。
    返回 (active_holdings, exited_holdings)
    """
    holdings = load_holdings()
    today_str = date.today().isoformat()
    active = []
    exited = []

    for h in holdings:
        if h['status'] != 'holding':
            exited.append(h)
            continue
        code = h['code']
        last_close = stock_prices.get(code)
        if last_close is None:
            active.append(h)
            continue
        h = check_exit(h, last_close, today_str)
        if h['status'] == 'holding':
            active.append(h)
        else:
            exited.append(h)

    save_holdings(active)
    return active, exited
