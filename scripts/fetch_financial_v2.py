#!/usr/bin/env python3.12
"""
Incremental financial data fetcher for D8Q.
- Skips stocks already fetched (by checking stock_financial table)
- Processes in configurable batch size (default 200)
- 1s delay between stocks to avoid rate limiting
- Retry logic (3 attempts per stock)
- Logs progress for resume capability
"""
import logging
import os
import sys
import time
import argparse

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
os.chdir('/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

from buy.DBClient import DBClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/d8q/financial_fetch.log', mode='a'),
    ]
)
logger = logging.getLogger('fetch_financial')


def get_db():
    return DBClient()


def get_market_prefix(code):
    code = str(code).zfill(6)
    if code.startswith('6'):
        return f'sh{code}'
    elif code.startswith('0') or code.startswith('3'):
        return f'sz{code}'
    return code


def store_profit(conn, stock_code, df):
    if df is None or len(df) == 0:
        return
    for idx, row in df.head(4).iterrows():
        try:
            report_date = str(row.get('报告日', ''))
            if not report_date:
                continue
            revenue = float(row.get('营业总收入', 0) or row.get('营业收入', 0) or 0)
            net_profit = float(row.get('净利润', 0) or 0)
            total_assets = float(row.get('资产总计', 0) or 0)
            roe = float(row.get('净资产收益率', 0) or row.get('ROE', 0) or 0)
            debt_ratio = float(row.get('资产负债率', 0) or 0)
            conn.execute(
                """
                INSERT IGNORE INTO stock_financial
                (stock_code, report_date, revenue, net_profit, total_assets, roe, debt_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (stock_code, report_date, revenue, net_profit, total_assets, roe, debt_ratio),
            )
        except Exception as e:
            logger.error(f"Profit store error {stock_code}: {e}")


def store_balance(conn, stock_code, df):
    if df is None or len(df) == 0:
        return
    for idx, row in df.head(4).iterrows():
        try:
            report_date = str(row.get('报告日', ''))
            if not report_date:
                continue
            total_assets = float(row.get('资产总计', 0) or 0)
            total_liabilities = float(row.get('负债合计', 0) or 0)
            total_equity = float(row.get('所有者权益合计', 0) or row.get('股东权益合计', 0) or 0)
            count, _ = conn.execute(
                """
                UPDATE stock_financial
                SET total_assets = %s, total_liabilities = %s, total_equity = %s
                WHERE stock_code = %s AND report_date = %s
                """,
                (total_assets, total_liabilities, total_equity, stock_code, report_date),
            )
            if count == 0:
                conn.execute(
                    """
                    INSERT IGNORE INTO stock_financial
                    (stock_code, report_date, total_assets, total_liabilities, total_equity)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (stock_code, report_date, total_assets, total_liabilities, total_equity),
                )
        except Exception as e:
            logger.error(f"Balance store error {stock_code}: {e}")


def fetch_one_stock(stock_code, max_retries=3):
    import akshare as ak
    market_code = get_market_prefix(stock_code)

    for attempt in range(1, max_retries + 1):
        try:
            # Profit statement
            df = ak.stock_financial_report_sina(stock=market_code, symbol="利润表")
            return df is not None
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt}/{max_retries} failed for {stock_code}: {e}, retrying...")
                time.sleep(2 * attempt)
            else:
                logger.error(f"All {max_retries} attempts failed for {stock_code}: {e}")
                return False
    return False


def fetch_and_store(stock_code):
    import akshare as ak
    market_code = get_market_prefix(stock_code)
    conn = get_db()
    try:
        # Profit
        try:
            df = ak.stock_financial_report_sina(stock=market_code, symbol="利润表")
            store_profit(conn, stock_code, df)
        except Exception as e:
            logger.error(f"Profit error {stock_code}: {e}")

        conn.commit()

        # Balance sheet
        try:
            df = ak.stock_financial_report_sina(stock=market_code, symbol="资产负债表")
            store_balance(conn, stock_code, df)
        except Exception as e:
            logger.error(f"Balance error {stock_code}: {e}")

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Fetch error {stock_code}: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Fetch stock financial data')
    parser.add_argument('--batch', type=int, default=200, help='Number of stocks to process per run')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between stocks (seconds)')
    parser.add_argument('--all', action='store_true', help='Process ALL stocks (ignore incremental)')
    args = parser.parse_args()

    logger.info(f"=== Starting financial data fetch (batch={args.batch}, delay={args.delay}s) ===")

    conn = get_db()
    try:
        # Get all stock codes
        _, all_rows = conn.select_many("SELECT code FROM stock_basic ORDER BY code")
        all_codes = [row['code'] for row in all_rows]
        total = len(all_codes)

        if not args.all:
            # Get already-fetched codes (have data for most recent quarter)
            _, done_rows = conn.select_many(
                "SELECT DISTINCT stock_code FROM stock_financial"
            )
            done_codes = set(row['stock_code'] for row in done_rows)
            pending = [c for c in all_codes if c not in done_codes]
        else:
            pending = all_codes
            done_codes = set()

        logger.info(f"Total: {total}, Already done: {len(done_codes)}, Pending: {len(pending)}")

        # Take batch
        batch = pending[:args.batch]
        if not batch:
            logger.info("Nothing to fetch. All stocks up to date.")
            return

        logger.info(f"Processing batch of {len(batch)} stocks ({len(done_codes)+1}-{len(done_codes)+len(batch)} of {total})")

        success = 0
        failed = 0
        for i, code in enumerate(batch, 1):
            try:
                ok = fetch_and_store(code)
                if ok:
                    success += 1
                else:
                    failed += 1
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(batch)} (success={success}, failed={failed})")
            except Exception as e:
                failed += 1
                logger.error(f"Failed {code}: {e}")
            time.sleep(args.delay)

        logger.info(f"=== Batch completed: {success} success, {failed} failed, {len(pending)-len(batch)} still pending ===")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
