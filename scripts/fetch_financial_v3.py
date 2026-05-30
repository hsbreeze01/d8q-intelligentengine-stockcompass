#!/usr/bin/env python3.12
"""
Incremental financial data fetcher for D8Q (v3 - THS API).
Uses stock_financial_abstract_ths (同花顺) instead of sina (rate-limited).
Features:
- Incremental: skips already-fetched stocks
- Configurable batch size
- Rate limit protection with adaptive delay
- Progress logging for resume
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


def parse_financial_value(val):
    """Parse Chinese financial notation (亿/万/%) to float."""
    if val is None or val == 'False' or val == 'None':
        return None
    s = str(val).strip().replace(',', '')
    try:
        multiplier = 1
        if s.endswith('亿'):
            s = s[:-1]
            multiplier = 100000000
        elif s.endswith('万'):
            s = s[:-1]
            multiplier = 10000
        elif s.endswith('%'):
            s = s[:-1]
            multiplier = 1
        return float(s) * multiplier
    except (ValueError, TypeError):
        return None


def store_financial_data(stock_code, df_by_quarter):
    """Store quarterly financial data from THS abstract."""
    if df_by_quarter is None or len(df_by_quarter) == 0:
        return 0

    conn = get_db()
    stored = 0
    try:
        for _, row in df_by_quarter.iterrows():
            try:
                report_date = str(row.get('报告期', '')).strip()
                if not report_date or len(report_date) < 8:
                    continue

                # Parse key metrics
                revenue = parse_financial_value(row.get('营业总收入'))
                net_profit = parse_financial_value(row.get('净利润'))
                roe = parse_financial_value(row.get('净资产收益率'))
                debt_ratio = parse_financial_value(row.get('资产负债率'))

                # Skip if no meaningful data
                if revenue is None and net_profit is None:
                    continue

                conn.execute(
                    """
                    INSERT INTO stock_financial
                    (stock_code, report_date, revenue, net_profit, roe, debt_ratio)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        revenue = COALESCE(VALUES(revenue), revenue),
                        net_profit = COALESCE(VALUES(net_profit), net_profit),
                        roe = COALESCE(VALUES(roe), roe),
                        debt_ratio = COALESCE(VALUES(debt_ratio), debt_ratio)
                    """,
                    (stock_code, report_date, revenue, net_profit, roe, debt_ratio),
                )
                stored += 1
            except Exception as e:
                logger.debug(f"Row error {stock_code}: {e}")

        conn.commit()
    finally:
        conn.close()
    return stored


def fetch_one(stock_code, max_retries=2):
    """Fetch financial data for one stock via THS API."""
    import akshare as ak

    for attempt in range(1, max_retries + 1):
        try:
            df = ak.stock_financial_abstract_ths(symbol=stock_code, indicator='按单季度')
            if df is not None and len(df) > 0:
                return df
            return None
        except Exception as e:
            err_str = str(e)
            if 'rate' in err_str.lower() or 'limit' in err_str.lower() or '频繁' in err_str:
                wait = 30 * attempt
                logger.warning(f"Rate limited on {stock_code}, waiting {wait}s...")
                time.sleep(wait)
            elif attempt < max_retries:
                time.sleep(3 * attempt)
            else:
                logger.error(f"Fetch failed {stock_code}: {e}")
                return None
    return None


def main():
    parser = argparse.ArgumentParser(description='Fetch stock financial data via THS')
    parser.add_argument('--batch', type=int, default=200, help='Stocks per run')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between stocks (s)')
    parser.add_argument('--all', action='store_true', help='Re-fetch all stocks')
    args = parser.parse_args()

    logger.info(f"=== Starting THS financial fetch (batch={args.batch}, delay={args.delay}s) ===")

    conn = get_db()
    try:
        _, all_rows = conn.select_many("SELECT code FROM stock_basic ORDER BY code")
        all_codes = [row['code'] for row in all_rows]
        total = len(all_codes)

        if not args.all:
            _, done_rows = conn.select_many(
                "SELECT DISTINCT stock_code FROM stock_financial"
            )
            done_codes = set(row['stock_code'] for row in done_rows)
            pending = [c for c in all_codes if c not in done_codes]
        else:
            pending = all_codes
            done_codes = set()

        logger.info(f"Total: {total}, Done: {len(done_codes)}, Pending: {len(pending)}")

        batch = pending[:args.batch]
        if not batch:
            logger.info("All stocks up to date.")
            return

        logger.info(f"Batch: {len(batch)} stocks ({len(done_codes)+1}-{len(done_codes)+len(batch)} of {total})")

        success = 0
        failed = 0
        consecutive_failures = 0

        for i, code in enumerate(batch, 1):
            try:
                df = fetch_one(code)
                if df is not None:
                    rows = store_financial_data(code, df)
                    success += 1
                    consecutive_failures = 0
                    if i % 20 == 0:
                        logger.info(f"Progress: {i}/{len(batch)} (success={success}, failed={failed})")
                else:
                    failed += 1
                    consecutive_failures += 1
            except Exception as e:
                failed += 1
                consecutive_failures += 1
                logger.error(f"Failed {code}: {e}")

            # Circuit breaker: too many consecutive failures → pause
            if consecutive_failures >= 10:
                logger.warning(f"Circuit breaker: {consecutive_failures} consecutive failures, pausing 60s...")
                time.sleep(60)
                consecutive_failures = 0

            time.sleep(args.delay)

        logger.info(f"=== Batch done: {success} ok, {failed} fail, {len(pending)-len(batch)} remaining ===")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
