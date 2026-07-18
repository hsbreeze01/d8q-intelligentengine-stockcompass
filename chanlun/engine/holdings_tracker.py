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


def add_holding(sig: dict) -> dict:
    """从信号创建持仓记录"""
    return {
        'code': sig['code'],
        'name': sig.get('name', ''),
        'type': sig['type'],
        'entry_price': sig['price'],
        'stop_loss': sig['stop_loss'],
        'entry_date': sig.get('dt', str(datetime.now()))[:10],
        'score': sig.get('score', 0),
        'grade_label': sig.get('grade_label', ''),
        'max_close': sig['price'],  # 跟踪最高收盘价
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
