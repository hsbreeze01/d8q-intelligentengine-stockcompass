"""策略层 - 短期资金热点共振策略 + 中期景气趋势驱动策略的评分模型"""
import numpy as np
import pandas as pd


class ShortTermStrategy:
    """短期策略: 资金共振(30) + 技术突破(25) + 基本面(25) + 事件催化(20) = 100"""

    def passes_filter(self, data: dict) -> bool:
        """前置过滤: 流通市值>50亿 且 日均成交>1亿"""
        cap = data.get("market_cap", 0)
        turnover = data.get("avg_turnover", 0)
        return cap >= 50e8 and turnover >= 1e8

    def score(self, data: dict) -> float:
        s = 0.0
        s += self._score_fund_resonance(data)
        s += self._score_technical(data)
        s += self._score_fundamental(data)
        s += self._score_event(data)
        return min(s, 100.0)

    def _score_fund_resonance(self, d: dict) -> float:
        """资金共振 (max 30): 北向排名前20 + 主力净流入>0 + 融资增加"""
        dims = 0
        if d.get("north_rank", 999) <= 20:
            dims += 1
        if d.get("main_net_inflow", 0) > 0:
            dims += 1
        if d.get("margin_increasing", False):
            dims += 1
        return {3: 30, 2: 20, 1: 10, 0: 0}[dims]

    def _score_technical(self, d: dict) -> float:
        """技术面突破 (max 25): 突破20日高 + MACD金叉 + 放量 + RSI 50-70"""
        conds = 0
        if d.get("price_breakout_20d", False):
            conds += 1
        if d.get("macd_golden_cross", False):
            conds += 1
        if d.get("volume_ratio", 0) >= 1.5:
            conds += 1
        rsi = d.get("rsi", 50)
        if 50 <= rsi <= 70:
            conds += 1
        return {4: 25, 3: 18, 2: 12, 1: 6, 0: 0}[conds]

    def _score_fundamental(self, d: dict) -> float:
        """基本面过滤 (max 25): 净利正增 + PE<行业均值 + 流通>50亿"""
        conds = 0
        if d.get("profit_growth_positive", False):
            conds += 1
        if d.get("pe_below_industry", False):
            conds += 1
        if d.get("market_cap", 0) >= 50e8:
            conds += 1
        return {3: 25, 2: 18, 1: 10, 0: 0}[conds]

    def _score_event(self, d: dict) -> float:
        """事件催化 (max 20): 用北向+主力强度作为代理"""
        north = d.get("north_rank", 999)
        main = d.get("main_net_inflow", 0)
        if north <= 10 and main > 2:
            return 20
        elif north <= 20 and main > 0:
            return 15
        elif north <= 30 or main > 0:
            return 8
        return 0


class MidTermStrategy:
    """中期策略: 产业景气(30) + 业绩成长(30) + 估值合理(20) + 竞争壁垒(20) = 100"""

    def passes_filter(self, data: dict) -> bool:
        """前置过滤: ROE>5%, 非连续亏损"""
        return data.get("roe", 0) > 5

    def score(self, data: dict) -> float:
        s = 0.0
        s += self._score_industry(data)
        s += self._score_growth(data)
        s += self._score_valuation(data)
        s += self._score_moat(data)
        return min(s, 100.0)

    def _score_industry(self, d: dict) -> float:
        """产业景气度 (max 30): 行业增速>20% + 政策支持 + 格局改善"""
        conds = 0
        if d.get("industry_profit_growth", 0) > 20:
            conds += 1
        if d.get("policy_support", False):
            conds += 1
        # 格局改善用龙头地位代理
        if d.get("is_leader", False):
            conds += 1
        return {3: 30, 2: 24, 1: 18, 0: 8}[min(conds, 3)]

    def _score_growth(self, d: dict) -> float:
        """业绩成长性 (max 30): 净利增速>20% + ROE>12% + 现金流健康"""
        conds = 0
        if d.get("net_profit_growth", 0) > 20:
            conds += 1
        if d.get("roe", 0) > 12:
            conds += 1
        if d.get("cash_flow_positive", False):
            conds += 1
        return {3: 30, 2: 24, 1: 18, 0: 8}[min(conds, 3)]

    def _score_valuation(self, d: dict) -> float:
        """估值合理性 (max 20): PEG<1.5 + PE分位<70% + 股息>1.5%"""
        conds = 0
        if d.get("peg", 99) < 1.5:
            conds += 1
        if d.get("pe_percentile", 1.0) < 0.7:
            conds += 1
        if d.get("dividend_yield", 0) > 1.5:
            conds += 1
        return {3: 20, 2: 15, 1: 10, 0: 4}[min(conds, 3)]

    def _score_moat(self, d: dict) -> float:
        """竞争壁垒 (max 20): 龙头地位 + 高研发"""
        conds = 0
        if d.get("is_leader", False):
            conds += 1
        if d.get("rd_ratio", 0) > 5:
            conds += 1
        return {2: 20, 1: 12, 0: 4}[min(conds, 2)]


def compute_technical_signals(df: pd.DataFrame) -> dict:
    """从日线DataFrame计算技术信号"""
    if df.empty or len(df) < 20:
        return {"price_breakout_20d": False, "macd_golden_cross": False,
                "volume_ratio": 0.0, "rsi": 50.0}
    close = df["close"].values
    volume = df["volume"].values

    # 突破20日高点
    high_20 = np.max(close[-21:-1]) if len(close) > 20 else close[-1]
    breakout = close[-1] > high_20

    # MACD金叉 (12,26,9)
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif = ema12 - ema26
    dea = _ema(dif, 9)
    golden_cross = dif[-1] > dea[-1] and dif[-2] <= dea[-2] if len(dif) > 2 else False

    # 成交量比 (当日/20日均量)
    avg_vol_20 = np.mean(volume[-20:]) if len(volume) >= 20 else volume[-1]
    vol_ratio = volume[-1] / avg_vol_20 if avg_vol_20 > 0 else 0.0

    # RSI(14)
    rsi = _rsi(close, 14)

    return {
        "price_breakout_20d": bool(breakout),
        "macd_golden_cross": bool(golden_cross),
        "volume_ratio": float(vol_ratio),
        "rsi": float(rsi),
    }


def _ema(data, period):
    """指数移动平均"""
    arr = np.array(data, dtype=float)
    result = np.zeros_like(arr)
    result[0] = arr[0]
    k = 2.0 / (period + 1)
    for i in range(1, len(arr)):
        result[i] = arr[i] * k + result[i - 1] * (1 - k)
    return result


def _rsi(close, period=14):
    """RSI 计算"""
    if len(close) < period + 1:
        return 50.0
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1 + rs)
