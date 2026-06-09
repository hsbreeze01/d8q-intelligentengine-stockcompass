"""数据获取层 - 新浪源(个股日线/指数) + 同花顺源(北向/融资/行业/分红)"""
import os, json, hashlib, pickle, logging, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)
CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(name): return CACHE_DIR / f"{hashlib.md5(name.encode()).hexdigest()[:12]}.pkl"

def _load_cache(name, ttl_hours=24):
    p = _cache_path(name)
    if p.exists() and (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)) < timedelta(hours=ttl_hours):
        with open(p, "rb") as f: return pickle.load(f)
    return None

def _save_cache(name, data):
    with open(_cache_path(name), "wb") as f: pickle.dump(data, f)


class DataFetcher:
    def __init__(self, use_cache=True):
        self.use_cache = use_cache

    def _cached(self, key, fn, ttl=24):
        if self.use_cache:
            c = _load_cache(key, ttl)
            if c is not None: return c
        try:
            data = fn()
        except Exception as e:
            logger.warning("Fetch %s failed: %s", key, e)
            return None
        if self.use_cache and data is not None: _save_cache(key, data)
        return data

    # ---- 个股日线 (新浪源) ----
    def get_stock_history(self, symbol, start, end):
        """前复权日线 index=date cols=[open,close,high,low,volume,change_pct]"""
        key = f"hist_{symbol}_{start}_{end}"
        def fetch():
            prefix = "sz" if symbol.startswith(("0","3")) else "sh"
            df = ak.stock_zh_a_daily(symbol=f"{prefix}{symbol}", start_date=start, end_date=end, adjust="qfq")
            if df is None or df.empty: return pd.DataFrame()
            df = df.rename(columns={"date":"date","open":"open","close":"close","high":"high","low":"low","volume":"volume"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            if "outstanding_share" in df.columns: df = df.drop(columns=["outstanding_share"], errors="ignore")
            # 计算涨跌幅
            df["change_pct"] = df["close"].pct_change() * 100
            return df
        result = self._cached(key, fetch)
        return result if result is not None else pd.DataFrame()

    # ---- 指数日线 (新浪API) ----
    def get_index_history(self, index_code, start, end):
        """沪深300=000300"""
        key = f"idx_{index_code}_{start}_{end}"
        def fetch():
            url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData?symbol=sh{index_code}&scale=240&ma=no&datalen=800"
            req = urllib.request.urlopen(url, timeout=15)
            raw = req.read().decode()
            # parse JSONP: =([ ... ])
            json_str = raw[raw.index("(")+1 : raw.rindex(")")]
            records = json.loads(json_str)
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["day"])
            df = df.set_index("date")
            for c in ["open","close","high","low","volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df[["open","close","high","low","volume"]]
            df = df.loc[start:end]
            return df
        result = self._cached(key, fetch)
        return result if result is not None else pd.DataFrame()

    # ---- 北向资金 ----
    def get_north_flow_history(self, start, end):
        """每日北向净流入(亿元), index=date"""
        key = f"north_{start}_{end}"
        def fetch():
            hu = ak.stock_hsgt_hist_em(symbol="沪股通")
            shen = ak.stock_hsgt_hist_em(symbol="深股通")
            hu["日期"] = pd.to_datetime(hu["日期"])
            shen["日期"] = pd.to_datetime(shen["日期"])
            merged = hu.set_index("日期")[["当日成交净买额"]].rename(columns={"当日成交净买额":"hu"})
            merged["shen"] = shen.set_index("日期")["当日成交净买额"]
            merged["net_flow"] = merged["hu"].fillna(0) + merged["shen"].fillna(0)
            return merged["net_flow"].loc[start:end]
        result = self._cached(key, fetch, ttl=12)
        return result if result is not None else pd.Series(dtype=float)

    # ---- 个股资金流(同花顺) ----
    def get_stock_fund_flow(self, symbol, days=5):
        key = f"fund_{symbol}_{days}"
        def fetch():
            market = "sz" if symbol.startswith(("0","3")) else "sh"
            df = ak.stock_individual_fund_flow(stock=symbol, market=market)
            if df is None or df.empty:
                return {"main_net_inflow": 0.0}
            df = df.tail(days)
            main_col = [c for c in df.columns if "主力" in c and "净流入" in c]
            val = df[main_col[0]].sum() if main_col else 0.0
            return {"main_net_inflow": float(val)}
        result = self._cached(key, fetch, ttl=12)
        return result if result is not None else {"main_net_inflow": 0.0}

    # ---- 融资融券(全市场趋势) ----
    def get_margin_data(self, symbol=None):
        key = "margin_trend"
        def fetch():
            df = ak.stock_margin_account_info()
            if df is None or df.empty:
                return {"margin_balance": 0.0, "margin_increasing": False}
            df["融资余额"] = pd.to_numeric(df["融资余额"], errors="coerce")
            recent = df.tail(20)
            latest = float(recent["融资余额"].iloc[-1])
            earliest = float(recent["融资余额"].iloc[0])
            return {"margin_balance": latest, "margin_increasing": latest > earliest}
        result = self._cached(key, fetch, ttl=12)
        return result if result is not None else {"margin_balance": 0.0, "margin_increasing": False}

    # ---- 财务数据 ----
    def get_financial_data(self, symbol):
        key = f"fin_{symbol}"
        def fetch():
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            if df is None or df.empty:
                return {"roe": 0.0, "net_profit_growth": 0.0, "eps": 0.0}
            for i in range(len(df)-1, -1, -1):
                row = df.iloc[i]
                dt = str(row.get("日期",""))
                if dt.startswith("1900"): continue
                roe = _safe_float(row.get("净资产收益率(%)", 0))
                growth = _safe_float(row.get("净利润增长率(%)", 0))
                eps = _safe_float(row.get("摊薄每股收益(元)", 0))
                return {"roe": roe, "net_profit_growth": growth, "eps": eps}
            return {"roe": 0.0, "net_profit_growth": 0.0, "eps": 0.0}
        result = self._cached(key, fetch, ttl=72)
        return result if result is not None else {"roe": 0.0, "net_profit_growth": 0.0, "eps": 0.0}

    # ---- 股息率 ----
    def get_dividend_yield(self, symbol):
        key = f"div_{symbol}"
        def fetch():
            df = ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
            if df is None or df.empty:
                return {"dividend_yield": 0.0}
            # 近2年分红合计
            df["年份"] = pd.to_numeric(df.get("报告期",pd.Series()).str[:4], errors="coerce")
            recent = df[df["年份"] >= 2024]
            total_div = recent["派息(税前)(元)"].sum() if "派息(税前)(元)" in df.columns else 0
            return {"dividend_yield": float(total_div)}
        result = self._cached(key, fetch, ttl=168)
        return result if result is not None else {"dividend_yield": 0.0}

    # ---- 行业概念 ----
    def get_concept_list(self):
        key = "concepts"
        def fetch():
            df = ak.stock_board_concept_name_ths()
            return df["name"].tolist() if df is not None else []
        result = self._cached(key, fetch, ttl=168)
        return result if result is not None else []

    # ---- 股票列表 ----
    def get_stock_list(self):
        key = "stock_list"
        def fetch():
            df = ak.stock_info_a_code_name()
            if df is None or df.empty: return []
            records = []
            for _, row in df.iterrows():
                name, code = str(row.get("name","")), str(row.get("code",""))
                if "ST" in name or "退" in name: continue
                if not (code.startswith("0") or code.startswith("3") or code.startswith("6")): continue
                records.append({"code": code, "name": name})
            return records
        result = self._cached(key, fetch, ttl=168)
        return result if result is not None else []


def _safe_float(val, default=0.0):
    if val is None: return default
    try:
        f = float(val)
        return default if np.isnan(f) else f
    except (ValueError, TypeError): return default
