"""P1能力模块: 行业板块/估值分位/股息率/涨跌停/模拟盘"""
import json, logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---- P1-5: 行业板块+概念映射 ----
def get_stock_industry_map(fetcher):
    """获取概念板块列表(同花顺)"""
    return fetcher.get_concept_list()


# ---- P1-6: 估值分位数 ----
def compute_pe_percentile(fetcher, symbol, current_pe, lookback_years=3):
    """计算PE在近N年历史中的分位数(0-1)"""
    end = datetime.now().strftime('%Y%m%d')
    start_dt = datetime.now().replace(year=datetime.now().year - lookback_years)
    start = start_dt.strftime('%Y%m%d')
    df = fetcher.get_stock_history(symbol, start, end)
    if df.empty or len(df) < 100:
        return 0.5  # 数据不足返回中位
    fin = fetcher.get_financial_data(symbol)
    eps = fin.get('eps', 0)
    if eps <= 0:
        return 0.5
    # 用收盘价/EPS计算历史PE序列
    pe_series = df['close'] / eps
    pe_series = pe_series[pe_series > 0].dropna()
    if len(pe_series) < 50:
        return 0.5
    percentile = float((pe_series < current_pe).sum()) / len(pe_series)
    return percentile


# ---- P1-7: 股息率 ----
def compute_dividend_yield(fetcher, symbol):
    """计算年化股息率 = 近12月分红 / 当前股价"""
    data = fetcher.get_dividend_yield(symbol)
    div_per_share = data.get('dividend_yield', 0)
    if div_per_share <= 0:
        return 0.0
    # 获取最新收盘价
    end = datetime.now().strftime('%Y%m%d')
    start = datetime(datetime.now().year, 1, 1).strftime('%Y%m%d')
    df = fetcher.get_stock_history(symbol, start, end)
    if df.empty:
        return 0.0
    price = df['close'].iloc[-1]
    if price <= 0:
        return 0.0
    return div_per_share / price * 100  # 百分比


# ---- P1-8: 涨跌停处理 ----
def is_limit_up(change_pct, threshold=9.8):
    """判断是否涨停(无法买入)"""
    return change_pct >= threshold

def is_limit_down(change_pct, threshold=-9.8):
    """判断是否跌停(无法卖出)"""
    return change_pct <= threshold

def check_trade_feasibility(df, date, direction='buy'):
    """检查某日是否可交易"""
    if date not in df.index:
        return False
    pct = df.loc[date].get('change_pct', 0)
    if direction == 'buy' and is_limit_up(pct):
        return False
    if direction == 'sell' and is_limit_down(pct):
        return False
    return True


# ---- P1-10: 持仓模拟盘 ----
class PortfolioTracker:
    """模拟盘持仓跟踪"""
    def __init__(self, initial_capital=1000000):
        self.capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {code: {shares, avg_cost, entry_date}}
        self.history = []    # [{date, nav, positions_snapshot}]
        self.log_path = Path(__file__).parent / 'output' / 'portfolio.json'

    def buy(self, code, price, amount_pct=0.1, date=None):
        """买入, amount_pct为占总资产比例"""
        target_value = self.capital * amount_pct
        shares = int(target_value / price // 100) * 100
        if shares < 100 or price * shares > self.cash:
            return False
        cost = price * shares * 1.0013  # 含交易成本
        self.cash -= cost
        if code in self.positions:
            pos = self.positions[code]
            total = pos['shares'] + shares
            pos['avg_cost'] = (pos['avg_cost'] * pos['shares'] + price * shares) / total
            pos['shares'] = total
        else:
            self.positions[code] = {'shares': shares, 'avg_cost': price, 'entry_date': date or datetime.now().strftime('%Y%m%d')}
        return True

    def sell(self, code, price, pct=1.0, date=None):
        """卖出, pct为卖出比例"""
        if code not in self.positions:
            return False
        pos = self.positions[code]
        shares = int(pos['shares'] * pct // 100) * 100
        if shares <= 0:
            shares = pos['shares']
        revenue = price * shares * 0.9985  # 扣交易成本
        self.cash += revenue
        pos['shares'] -= shares
        if pos['shares'] <= 0:
            del self.positions[code]
        return True

    def nav(self, prices):
        """计算当前净值"""
        value = self.cash
        for code, pos in self.positions.items():
            value += prices.get(code, pos['avg_cost']) * pos['shares']
        return value / self.capital

    def check_signals(self, prices, stop_loss=-0.05, tp_half=0.08):
        """检查止损止盈信号"""
        signals = []
        for code, pos in list(self.positions.items()):
            p = prices.get(code, pos['avg_cost'])
            pnl = (p - pos['avg_cost']) / pos['avg_cost']
            if pnl <= stop_loss:
                signals.append({'code': code, 'action': 'SELL', 'reason': f'止损{pnl:.1%}'})
            elif pnl >= tp_half:
                signals.append({'code': code, 'action': 'REDUCE', 'reason': f'止盈{pnl:.1%}'})
        return signals

    def save(self):
        data = {
            'cash': self.cash,
            'positions': self.positions,
            'nav': self.cash / self.capital,
            'updated': datetime.now().isoformat(),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
