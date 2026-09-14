#!/usr/bin/env python3
"""除权除息日涨跌幅校正(前向): 东财/新浪源在除权日给不出官方调整值,
自算 raw 口径会产生假跳空。本任务对近期行做腾讯qfq对账, 将除权行
change_percentage/change_amount 校正为官方调整口径(除权参考价基准)。

检测: raw口径 与 开盘口径 差异<=-1.2 的近期行(除权特征, 含假阳);
精筛: 腾讯前复权序列日涨跌幅(=官方调整值, 基准无关) 与库内差异>1.5 才改写。
用法: fix_exdiv.py [--days N]   默认校正最近3个自然日内写入的行。
"""
import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_db import _get_db  # noqa: E402  复用连接封装

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fix_exdiv")

DIFF_GATE = -1.2     # 粗筛: raw - open口径 <= 此值视为除权候选
WRITE_GATE = 1.5     # 精筛: 与腾讯官方值差异超过此值才改写
SLEEP_SEC = 0.25
RETRIES = 3


def _candidates(days: int):
    mc = _get_db()
    try:
        since = (date.today() - timedelta(days=days)).isoformat()
        _, rows, _cols = mc.select_many_cols(
            """
            SELECT t.stock_code, t.id, t.date, t.close, t.change_percentage cur_val
            FROM stock_data_daily t
            JOIN stock_data_daily p
              ON p.stock_code = t.stock_code
             AND p.date = (SELECT MAX(d.date) FROM stock_data_daily d
                            WHERE d.stock_code = t.stock_code AND d.date < t.date)
            WHERE t.date >= %s AND t.open > 0
              AND (t.change_percentage - ROUND((t.close - t.open)/t.open*100, 2)) <= %s
            """,
            (since, DIFF_GATE),
        )
        return rows or []
    finally:
        mc.close()


def _tx_pct_series(code: str):
    for attempt in range(RETRIES):
        try:
            prefix = "sh" if code[0] == "6" else "sz"
            df = ak.stock_zh_a_hist_tx(symbol=prefix + code, start_date="20240101",
                                       end_date=date.today().strftime("%Y%m%d"),
                                       adjust="qfq")
            if df is None or len(df) < 2:
                return {}
            s = df["close"].astype(float)
            d = df["date"].astype(str)
            pct = ((s / s.shift(1)) - 1) * 100
            pct.index = d
            return {k: round(float(v), 2) for k, v in pct.dropna().items()}
        except Exception as exc:
            logger.warning("fetch tx %s attempt %d fail: %s", code, attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    args = ap.parse_args()

    rows = _candidates(args.days)
    by_stock = {}
    for r in rows:
        by_stock.setdefault(r["stock_code"], {})[str(r["date"])] = r
    logger.info("candidates: %d rows / %d stocks", len(rows), len(by_stock))
    if not by_stock:
        return

    mc = _get_db()
    fixed = errs = 0
    try:
        for code, items in sorted(by_stock.items()):
            pct_map = _tx_pct_series(code)
            if pct_map is None:
                errs += 1
                continue
            updates = []
            for dt, r in items.items():
                p = pct_map.get(dt)
                if p is not None and abs(p - float(r["cur_val"])) > WRITE_GATE:
                    ref = float(r["close"]) / (1 + p / 100.0)
                    amt = round(float(r["close"]) - ref, 2)
                    updates.append((p, amt, r["id"]))
            if updates:
                for u in updates:
                    mc.execute(
                        "UPDATE stock_data_daily SET change_percentage=%s, change_amount=%s "
                        "WHERE id=%s", u)
                mc.commit()
                fixed += len(updates)
                logger.info("%s fixed %d: %s", code, len(updates),
                            json.dumps({str(r["date"]): u[0] for u, r in
                                        zip(updates, [items[k] for k in items])})[:160])
            time.sleep(SLEEP_SEC)
    finally:
        mc.close()
    logger.info("done: fixed=%d stocks_err=%d", fixed, errs)


if __name__ == "__main__":
    main()
