#!/usr/bin/env python3.12
"""
Compass Data Pipeline - Stock data initialization and daily incremental updates.

Usage:
    python scripts/pipeline.py --mode init          # Full initialization
    python scripts/pipeline.py --mode daily          # Daily incremental update
    python scripts/pipeline.py --mode single --code 600036  # Single stock
    python scripts/pipeline.py --mode daemon         # Daemon with APScheduler
"""

import os
import sys
import time
import logging
import argparse
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "stockdata"))

from pipeline_config import (
    START_DATE, INIT_SLEEP, DAILY_SLEEP, LOG_FILE, LOG_LEVEL, LOG_FORMAT,
    DAILY_SCHEDULE_HOUR, DAILY_SCHEDULE_MINUTE
)
from pipeline_fetcher import fetch_kline_daily
from pipeline_db import (
    get_stock_list, save_kline_data, calc_and_save_indicators,
    analyze_and_save, get_table_stats, get_max_date, count_empty_industry
)


def setup_logging(verbose=False):
    """Configure logging to both file and console."""
    level = getattr(logging, "DEBUG" if verbose else LOG_LEVEL)
    fmt = LOG_FORMAT

    handlers = [
        logging.StreamHandler(sys.stdout),
    ]

    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE))
    except Exception:
        pass

    logging.basicConfig(level=level, format=fmt, handlers=handlers)
    return logging.getLogger("pipeline")


def run_single(code, start_date=None, end_date=None, sleep=0, skip_analysis=False):
    """Process a single stock: fetch kline -> calc indicators -> [analyze]."""
    logger = logging.getLogger("pipeline")
    start = start_date or START_DATE
    end = end_date or datetime.datetime.now().strftime("%Y%m%d")

    logger.info("[" + code + "] Starting single stock pipeline (" + start + " ~ " + end + ")")

    # Step 1: Fetch kline
    try:
        df = fetch_kline_daily(code, start, end)
        if df is None or df.empty:
            logger.warning("[" + code + "] No kline data returned, skipping")
            return False
        logger.info("[" + code + "] Fetched " + str(len(df)) + " kline rows")
    except Exception as e:
        logger.error("[" + code + "] Fetch kline failed: " + str(e))
        return False

    # Step 2: Save kline
    try:
        saved = save_kline_data(code, df)
        logger.info("[" + code + "] Saved " + str(saved) + " kline rows")
    except Exception as e:
        logger.error("[" + code + "] Save kline failed: " + str(e))
        return False

    if sleep > 0:
        time.sleep(sleep)

    # Step 3: Calc indicators
    try:
        ind = calc_and_save_indicators(code)
        logger.info("[" + code + "] Saved " + str(ind) + " indicator rows")
    except Exception as e:
        logger.error("[" + code + "] Calc indicators failed: " + str(e))
        return False

    if skip_analysis:
        logger.debug("[" + code + "] Skipping analysis (skip_analysis=True)")
        return True

    # Step 4: Analyze
    try:
        ana = analyze_and_save(code)
        logger.info("[" + code + "] Saved " + str(ana) + " analysis rows")
    except Exception as e:
        logger.error("[" + code + "] Analysis failed: " + str(e))
        return False

    return True


def run_init(start_date=None, end_date=None, sleep=None, skip_analysis=False):
    logger = logging.getLogger("pipeline")
    sleep = sleep or INIT_SLEEP
    start_time = time.time()

    logger.info("=== INIT MODE START ===")
    stocks = get_stock_list()
    total = len(stocks)
    logger.info("Found " + str(total) + " stocks in stock_basic")

    success = 0
    failed = 0
    skipped = 0
    failed_codes = []

    for idx, row in stocks.iterrows():
        code = row["code"]

        max_d = get_max_date("stock_data_daily", code)
        if max_d is not None:
            days = (datetime.date.today() - max_d).days
            if days <= 3:
                skipped += 1
                if (idx + 1) % 500 == 0:
                    logger.info("Progress: " + str(idx + 1) + "/" + str(total) + " (skipped=" + str(skipped) + ")")
                continue

        try:
            ok = run_single(code, start_date, end_date, sleep=0, skip_analysis=skip_analysis)
            if ok:
                success += 1
            else:
                failed += 1
                failed_codes.append(code)
        except Exception as e:
            logger.error("[" + code + "] Unexpected error: " + str(e))
            failed += 1
            failed_codes.append(code)

        if sleep > 0:
            time.sleep(sleep)

        if (idx + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total - idx - 1) / rate if rate > 0 else 0
            logger.info(
                "Progress: " + str(idx + 1) + "/" + str(total) +
                " (ok=" + str(success) + " fail=" + str(failed) + " skip=" + str(skipped) + ")" +
                " rate=" + str(round(rate, 1)) + "/s ETA=" + str(round(eta / 60)) + "min"
            )

    elapsed = time.time() - start_time
    logger.info("=== INIT PHASE 1 COMPLETE in " + str(round(elapsed / 60, 1)) + "min ===")
    logger.info("Total: " + str(total) + " Success: " + str(success) + " Failed: " + str(failed) + " Skipped: " + str(skipped))
    if failed_codes:
        logger.warning("Failed codes: " + str(failed_codes[:50]))

    stats = get_table_stats()
    for k, v in stats.items():
        logger.info("  " + k + ": " + str(v))

    if not skip_analysis:
        run_analysis_all()

    return success, failed, skipped


def run_analysis_all():
    logger = logging.getLogger("pipeline")
    start_time = time.time()
    logger.info("=== ANALYSIS PHASE START ===")

    stocks = get_stock_list()
    total = len(stocks)
    success = 0
    failed = 0

    for idx, row in stocks.iterrows():
        code = row["code"]
        try:
            ana = analyze_and_save(code)
            if ana > 0:
                success += 1
        except Exception as e:
            logger.error("[" + code + "] Analysis failed: " + str(e))
            failed += 1

        if (idx + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total - idx - 1) / rate if rate > 0 else 0
            logger.info(
                "Analysis progress: " + str(idx + 1) + "/" + str(total) +
                " (ok=" + str(success) + " fail=" + str(failed) + ")" +
                " rate=" + str(round(rate, 1)) + "/s ETA=" + str(round(eta / 60)) + "min"
            )

    elapsed = time.time() - start_time
    logger.info("=== ANALYSIS PHASE COMPLETE in " + str(round(elapsed / 60, 1)) + "min ===")
    logger.info("Analysis: " + str(success) + " ok, " + str(failed) + " failed")

    stats = get_table_stats()
    for k, v in stats.items():
        logger.info("  " + k + ": " + str(v))

    return success, failed


def run_daily(sleep=None):
    """Daily incremental update: fetch new data for all stocks."""
    logger = logging.getLogger("pipeline")
    sleep = sleep or DAILY_SLEEP
    start_time = time.time()

    logger.info("=== DAILY MODE START ===")
    stocks = get_stock_list()
    total = len(stocks)
    today = datetime.datetime.now().strftime("%Y%m%d")

    success = 0
    failed = 0
    skipped = 0

    for idx, row in stocks.iterrows():
        code = row["code"]

        # Check if already up to date
        max_d = get_max_date("stock_data_daily", code)
        if max_d is not None and max_d >= datetime.date.today():
            skipped += 1
            continue

        # Incremental: fetch from max_date + 1 to today
        if max_d is not None:
            start = (max_d - datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            start = START_DATE

        try:
            ok = run_single(code, start, today, sleep=0)
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[{code}] {e}")
            failed += 1

        if sleep > 0:
            time.sleep(sleep)

        if (idx + 1) % 200 == 0:
            logger.info(f"Progress: {idx + 1}/{total} (ok={success} fail={failed} skip={skipped})")

    elapsed = time.time() - start_time
    logger.info(f"=== DAILY MODE COMPLETE in {elapsed/60:.1f}min ===")
    logger.info(f"Total: {total} Success: {success} Failed: {failed} Skipped: {skipped}")

    stats = get_table_stats()
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")

    return success, failed, skipped


def run_daemon():
    """Run as daemon with APScheduler."""
    logger = logging.getLogger("pipeline")

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
    except ImportError:
        logger.error("APScheduler not installed. Install with: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_daily,
        "cron",
        hour=DAILY_SCHEDULE_HOUR,
        minute=DAILY_SCHEDULE_MINUTE,
        id="daily_update",
        name="Daily stock data update",
    )

    logger.info(f"Daemon started. Daily update scheduled at {DAILY_SCHEDULE_HOUR}:{DAILY_SCHEDULE_MINUTE:02d}")
    logger.info("Press Ctrl+C to exit")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Daemon stopped")


def main():
    parser = argparse.ArgumentParser(description="Compass Data Pipeline")
    parser.add_argument("--mode", choices=["init", "daily", "single", "daemon", "analyze"], required=True)
    parser.add_argument("--code", help="Stock code for single mode")
    parser.add_argument("--start", help="Start date YYYYMMDD")
    parser.add_argument("--end", help="End date YYYYMMDD")
    parser.add_argument("--sleep", type=float, help="Sleep between stocks (seconds)")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip analysis phase in init mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("Pipeline starting in " + args.mode + " mode")

    if args.mode == "single" and not args.code:
        parser.error("--code is required for single mode")

    if args.mode == "init":
        run_init(args.start, args.end, args.sleep, skip_analysis=args.skip_analysis)
    elif args.mode == "daily":
        run_daily(args.sleep)
    elif args.mode == "single":
        ok = run_single(args.code, args.start, args.end, sleep=0, skip_analysis=args.skip_analysis)
        if not ok:
            sys.exit(1)
    elif args.mode == "analyze":
        run_analysis_all()
    elif args.mode == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()
