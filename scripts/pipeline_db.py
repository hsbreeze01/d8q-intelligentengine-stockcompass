#!/usr/bin/env python3.12
"""Database operations for the Compass data pipeline."""

import os
import sys
import json
import logging
import datetime
import pandas as pd
import numpy as np

# Setup import paths to reuse existing modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "stockdata"))

from pipeline_config import MIN_INDICATOR_ROWS

logger = logging.getLogger("pipeline.db")

# Lazy imports
_DBClient_cls = None
_summery_trade_json = None
_buy_advice_v2 = None


def _get_db():
    """Get DBClient instance (lazy init)."""
    global _DBClient_cls
    if _DBClient_cls is None:
        from buy.DBClient import DBClient
        _DBClient_cls = DBClient
    return _DBClient_cls()


def _get_analysis_funcs():
    """Get analysis functions (lazy import, avoids stock_task.py -> dicStock chain)."""
    global _summery_trade_json, _buy_advice_v2
    if _summery_trade_json is None:
        from stockdata.main_analysis import summery_trade_json, buy_advice_v2
        _summery_trade_json = summery_trade_json
        _buy_advice_v2 = buy_advice_v2
    return _summery_trade_json, _buy_advice_v2


def get_stock_list():
    """Get all stock codes from stock_basic table."""
    mc = _get_db()
    try:
        count, rows, cols = mc.select_many_cols(
            "SELECT code, name FROM stock_basic ORDER BY code", ()
        )
        if count == 0:
            logger.warning("stock_basic table is empty!")
            return pd.DataFrame(columns=["code", "name"])
        return pd.DataFrame(rows, columns=cols)
    finally:
        mc.close()


def get_stock_count():
    """Count stocks in stock_basic."""
    mc = _get_db()
    try:
        count, result = mc.select_one("SELECT COUNT(*) as cnt FROM stock_basic")
        return result["cnt"]
    finally:
        mc.close()


def get_max_date(table, code):
    """Get max date for a stock in a given table. Returns None if no records."""
    mc = _get_db()
    try:
        date_col = "date"
        if table == "stock_analysis":
            date_col = "record_time"
        count, result = mc.select_one(
            "SELECT MAX(" + date_col + ") as max_date FROM " + table + " WHERE stock_code=%s",
            (code,)
        )
        return result["max_date"]
    finally:
        mc.close()


def save_kline_data(code, df):
    """Save K-line data to stock_data_daily using REPLACE INTO."""
    if df is None or df.empty:
        return 0
    mc = _get_db()
    try:
        for _, row in df.iterrows():
            sql = """
            REPLACE INTO stock_data_daily (
                date, stock_code, open, close, high, low,
                volume, turnover, amplitude,
                change_percentage, change_amount, turnover_rate
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                row["日期"], code,
                float(row["开盘"]), float(row["收盘"]),
                float(row["最高"]), float(row["最低"]),
                int(row["成交量"]), float(row["成交额"]),
                float(row["振幅"]) if pd.notna(row["振幅"]) else 0.0,
                float(row["涨跌幅"]) if pd.notna(row["涨跌幅"]) else 0.0,
                float(row["涨跌额"]) if pd.notna(row["涨跌额"]) else 0.0,
                float(row["换手率"]) if pd.notna(row["换手率"]) else 0.0,
            )
            mc.execute(sql, params)

        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mc.execute(
                "UPDATE dic_stock SET stock_data_daily_update_time=%s WHERE code=%s",
                (now_str, code)
            )
        except Exception:
            pass

        mc.commit()
        return len(df)
    except Exception as e:
        mc.rollback()
        logger.error("save_kline_data failed for " + code + ": " + str(e))
        raise
    finally:
        mc.close()


def calc_indicators(data, end_date=None, threshold=None, calc_threshold=None):
    """
    Calculate technical indicators using TA-Lib.
    Self-contained (no dicStock dependency).

    Parameters:
        data: DataFrame with columns date, close, high, low, open
    Returns:
        DataFrame with indicator columns added, or None on error
    """
    import talib as tl

    try:
        if end_date is not None:
            data = data.loc[data["date"] <= end_date].copy()

        if calc_threshold is not None:
            data = data.tail(n=calc_threshold).copy()

        # Always deep copy to ensure writable arrays
        data = data.copy(deep=True)

        data["close"] = data["close"].astype(float)
        data["high"] = data["high"].astype(float)
        data["low"] = data["low"].astype(float)
        data["open"] = data["open"].astype(float)

        with np.errstate(divide="ignore", invalid="ignore"):
            # MACD
            macd_dif, macd_dea, macd_hist = tl.MACD(
                data["close"].values, fastperiod=12, slowperiod=26, signalperiod=9
            )
            data["macd_dif"] = np.nan_to_num(macd_dif, nan=0.0)
            data["macd_dea"] = np.nan_to_num(macd_dea, nan=0.0)
            data["macd_macd"] = np.nan_to_num(macd_hist, nan=0.0) * 2

            # KDJ
            kdj_k, kdj_d = tl.STOCH(
                data["high"].values, data["low"].values, data["close"].values,
                fastk_period=9, slowk_period=5, slowk_matype=1,
                slowd_period=5, slowd_matype=1
            )
            data["kdj_k"] = np.nan_to_num(kdj_k, nan=0.0)
            data["kdj_d"] = np.nan_to_num(kdj_d, nan=0.0)
            data["kdj_j"] = 3.0 * data["kdj_k"].values - 2.0 * data["kdj_d"].values

            # BOLL
            boll_up, boll_mid, boll_low = tl.BBANDS(
                data["close"].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
            )
            data["boll_up"] = np.nan_to_num(boll_up, nan=0.0)
            data["boll_mid"] = np.nan_to_num(boll_mid, nan=0.0)
            data["boll_low"] = np.nan_to_num(boll_low, nan=0.0)

            # RSI
            for period in [6, 12, 24]:
                col = "rsi_" + str(period)
                vals = tl.RSI(data["close"].values, timeperiod=period)
                data[col] = np.nan_to_num(vals, nan=0.0)

            # MA
            for period in [5, 10, 20, 30, 60]:
                col = "ma" + str(period)
                vals = tl.MA(data["close"].values, timeperiod=period)
                data[col] = np.nan_to_num(vals, nan=0.0)

        if threshold is not None:
            data = data.tail(n=threshold).copy()
        return data
    except Exception as e:
        logger.error("calc_indicators error: " + str(e))
        import traceback
        logger.error(traceback.format_exc())
        return None


def calc_and_save_indicators(code):
    """Calculate technical indicators for a stock and save to indicators_daily."""
    mc = _get_db()
    try:
        count, rows, cols = mc.select_many_cols(
            "SELECT * FROM stock_data_daily WHERE stock_code=%s ORDER BY date",
            (code,)
        )
        if count == 0:
            logger.debug("No kline data for " + code + ", skipping indicators")
            return 0

        df = pd.DataFrame(rows, columns=cols)
        for col in ["id", "stock_code", "turnover", "amplitude",
                     "change_percentage", "change_amount", "turnover_rate"]:
            if col in df.columns:
                del df[col]

        max_ind = get_max_date("indicators_daily", code)
        start_date = datetime.date(2024, 1, 1)
        if max_ind is not None:
            start_date = max_ind

        result = calc_indicators(df, threshold=None)
        if result is None:
            logger.warning("calc_indicators returned None for " + code)
            return 0

        saved = 0
        for _, row in result.iterrows():
            row_date = row["date"]
            if row_date < start_date:
                continue

            sql = """
            REPLACE INTO indicators_daily (
                date, stock_code,
                macd_dif, macd_dea, macd_macd,
                kdj_k, kdj_d, kdj_j,
                boll_up, boll_mid, boll_low,
                rsi_6, rsi_12, rsi_24,
                ma5, ma10, ma20, ma30, ma60
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            params = (
                row["date"], code,
                float(row.get("macd_dif", 0) or 0),
                float(row.get("macd_dea", 0) or 0),
                float(row.get("macd_macd", 0) or 0),
                float(row.get("kdj_k", 0) or 0),
                float(row.get("kdj_d", 0) or 0),
                float(row.get("kdj_j", 0) or 0),
                float(row.get("boll_up", 0) or 0),
                float(row.get("boll_mid", 0) or 0),
                float(row.get("boll_low", 0) or 0),
                float(row.get("rsi_6", 0) or 0),
                float(row.get("rsi_12", 0) or 0),
                float(row.get("rsi_24", 0) or 0),
                float(row.get("ma5", 0) or 0),
                float(row.get("ma10", 0) or 0),
                float(row.get("ma20", 0) or 0),
                float(row.get("ma30", 0) or 0),
                float(row.get("ma60", 0) or 0),
            )
            mc.execute(sql, params)
            saved += 1

        mc.commit()
        logger.debug("Saved " + str(saved) + " indicator rows for " + code)
        return saved
    except Exception as e:
        mc.rollback()
        logger.error("calc_and_save_indicators failed for " + code + ": " + str(e))
        raise
    finally:
        mc.close()


def analyze_and_save(code):
    """Run buy_advice_v2 analysis for a stock and save to stock_analysis."""
    summery_trade_json, buy_advice_v2 = _get_analysis_funcs()
    mc = _get_db()
    try:
        count_ind, res_ind = mc.select_one(
            "SELECT COUNT(*) as cnt FROM indicators_daily WHERE stock_code=%s",
            (code,)
        )
        if res_ind["cnt"] < MIN_INDICATOR_ROWS:
            logger.debug(code + ": only " + str(res_ind["cnt"]) + " indicators, need " + str(MIN_INDICATOR_ROWS))
            return 0

        max_analysis = get_max_date("stock_analysis", code)
        start = "20260213"  # Recent ~60 trading days for initial batch
        if max_analysis is not None:
            start = (max_analysis - datetime.timedelta(days=1)).strftime("%Y%m%d")

        sql = "SELECT * FROM stock_data_daily WHERE stock_code='" + code + "' AND date > '" + start + "'"
        count, result = mc.select_many(sql)
        if count == 0:
            return 0

        mc.execute(
            "DELETE FROM stock_analysis WHERE stock_code='" + code + "' AND record_time > '" + start + "'"
        )
        mc.execute(
            "DELETE FROM stock_analysis_stat WHERE stock_code='" + code + "' AND date > '" + start + "'"
        )

        saved = 0
        consecutive_fail = 0
        for row in result:
            _, cnt_result = mc.select_one(
                "SELECT COUNT(*) as cnt FROM indicators_daily WHERE stock_code=%s AND date<=%s",
                (code, row["date"])
            )
            if cnt_result["cnt"] < MIN_INDICATOR_ROWS:
                continue
            try:
                date_str = row["date"].strftime("%Y%m%d")
                data = summery_trade_json(code, date_str)
                buy, sell, advice = buy_advice_v2(data)
                sql_insert = """
                INSERT INTO stock_analysis (
                    stock_code, analysis_data, buy_advice,
                    record_time, buy, sell
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    analysis_data = VALUES(analysis_data),
                    buy_advice = VALUES(buy_advice),
                    buy = VALUES(buy),
                    sell = VALUES(sell)
                """
                mc.execute(sql_insert, (
                    code, json.dumps(data), json.dumps(advice),
                    row["date"], buy, sell
                ))
                saved += 1
            except Exception as e:
                consecutive_fail += 1
                if consecutive_fail >= 10:
                    logger.warning(code + ": 10 consecutive failures, skipping remaining dates")
                    break
                logger.warning("Analysis failed for " + code + " on " + str(row["date"]) + ": " + str(e))
                continue

        mc.commit()
        logger.debug("Saved " + str(saved) + " analysis rows for " + code)
        return saved
    except Exception as e:
        mc.rollback()
        logger.error("analyze_and_save failed for " + code + ": " + str(e))
        raise
    finally:
        mc.close()


def get_table_stats():
    """Get row counts for key tables."""
    mc = _get_db()
    try:
        stats = {}
        for table in ["stock_basic", "stock_data_daily", "indicators_daily", "stock_analysis"]:
            _, result = mc.select_one("SELECT COUNT(*) as cnt FROM " + table)
            stats[table] = result["cnt"]
        _, result = mc.select_one(
            "SELECT COUNT(DISTINCT stock_code) as cnt FROM stock_data_daily"
        )
        stats["distinct_stocks_with_data"] = result["cnt"]
        return stats
    finally:
        mc.close()


def update_industry(code, industry):
    """Update industry field in stock_basic for a given stock."""
    if not industry:
        return False
    mc = _get_db()
    try:
        mc.execute("UPDATE stock_basic SET industry=%s WHERE code=%s", (industry, code))
        mc.commit()
        return True
    except Exception as e:
        mc.rollback()
        logger.error("update_industry failed for " + code + ": " + str(e))
        return False
    finally:
        mc.close()


def count_empty_industry():
    """Count stocks in stock_basic with empty or null industry."""
    mc = _get_db()
    try:
        _, result = mc.select_one(
            "SELECT COUNT(*) as cnt FROM stock_basic WHERE industry IS NULL OR industry='' OR industry='none'"
        )
        return result["cnt"]
    finally:
        mc.close()
