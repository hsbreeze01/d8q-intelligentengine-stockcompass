#!/usr/bin/env python3.12
"""Data fetcher for the Compass data pipeline using Sina API via akshare."""

import logging
import time
import numpy as np
import pandas as pd
import akshare as ak
from pipeline_config import MAX_RETRIES, RETRY_BASE_DELAY

logger = logging.getLogger("pipeline.fetcher")


def _get_prefix(code):
    """Get market prefix for stock code: 6->sh, 0/3->sz, else None (skip bj)."""
    if code.startswith("6"):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    else:
        return None


def _retry_fetch(fn, *args, **kwargs):
    """Execute fn with exponential backoff retry."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"Fetch attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {MAX_RETRIES} attempts failed: {e}")
    raise last_error


def fetch_kline_daily(code, start_date, end_date):
    """
    Fetch daily K-line data from Sina via akshare.

    Args:
        code: Stock code without prefix (e.g. "600036")
        start_date: Start date string "YYYYMMDD"
        end_date: End date string "YYYYMMDD"

    Returns:
        DataFrame with columns: 日期, 股票代码, 开盘, 收盘, 最高, 最低,
                                成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        Returns empty DataFrame if skipped (bj stocks) or no data.
    """
    prefix = _get_prefix(code)
    if prefix is None:
        logger.debug(f"Skipping non-sh/sz stock: {code}")
        return pd.DataFrame()

    symbol = f"{prefix}{code}"

    def _do_fetch():
        return ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

    raw_df = _retry_fetch(_do_fetch)

    if raw_df is None or raw_df.empty:
        logger.debug(f"No data returned for {code}")
        return pd.DataFrame()

    # Build result DataFrame with mapped column names
    result = pd.DataFrame()
    result["日期"] = raw_df["date"]
    result["股票代码"] = code
    result["开盘"] = raw_df["open"].astype(float)
    result["收盘"] = raw_df["close"].astype(float)
    result["最高"] = raw_df["high"].astype(float)
    result["最低"] = raw_df["low"].astype(float)
    result["成交量"] = (raw_df["volume"].astype(float) / 100).round().astype(int)
    result["成交额"] = raw_df["amount"].astype(float)
    result["换手率"] = (raw_df["turnover"].astype(float) * 100).round(2)

    # Self-compute: 振幅, 涨跌幅, 涨跌额
    close = result["收盘"].values.astype(float)
    high = result["最高"].values.astype(float)
    low = result["最低"].values.astype(float)

    # prev_close: shift by 1, first row uses open
    prev_close = np.empty_like(close)
    prev_close[0] = result["开盘"].values[0]
    prev_close[1:] = close[:-1]

    with np.errstate(divide="ignore", invalid="ignore"):
        result["振幅"] = np.where(
            prev_close != 0,
            ((high - low) / prev_close * 100).round(2),
            0.0
        )
        result["涨跌幅"] = np.where(
            prev_close != 0,
            ((close - prev_close) / prev_close * 100).round(2),
            0.0
        )

    result["涨跌额"] = (close - prev_close).round(2)

    logger.debug(f"Fetched {len(result)} rows for {code} ({start_date}~{end_date})")
    return result


def fetch_stock_list():
    """
    Fetch all A-share stock list.

    Returns:
        DataFrame with columns: code, name
    """
    def _do_fetch():
        df = ak.stock_info_a_code_name()
        return df

    raw = _retry_fetch(_do_fetch)
    result = pd.DataFrame()
    result["code"] = raw["code"].astype(str)
    result["name"] = raw["name"].astype(str)
    logger.info(f"Fetched stock list: {len(result)} stocks")
    return result


def fetch_industry_for_stock(code):
    """
    Attempt to fetch industry classification for a single stock.
    Best-effort: returns None if unavailable.

    Args:
        code: Stock code (e.g. "600036")

    Returns:
        Industry string or None
    """
    try:
        stock_info = ak.stock_individual_info_em(symbol=code)
        industry = stock_info.loc[
            stock_info["item"] == "行业", "value"
        ].values
        if len(industry) > 0:
            return str(industry[0])
    except Exception as e:
        logger.debug(f"Could not fetch industry for {code}: {e}")
    return None
