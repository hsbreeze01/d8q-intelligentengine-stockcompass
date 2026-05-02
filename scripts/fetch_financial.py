#!/usr/bin/env python3.12
import sys
import os

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
os.chdir('/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

import logging
import pymysql
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('fetch_financial')

def get_db():
    return pymysql.connect(host='localhost', user='root', password='password', database='stock_analysis_system')

def get_market_prefix(code):
    code = str(code).zfill(6)
    if code.startswith('6'):
        return f'sh{code}'
    elif code.startswith('0') or code.startswith('3'):
        return f'sz{code}'
    return code

def store_profit(stock_code, df):
    if df is None or len(df) == 0:
        return
    conn = get_db()
    cursor = conn.cursor()
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
            cursor.execute("""
                INSERT IGNORE INTO stock_financial 
                (stock_code, report_date, revenue, net_profit, total_assets, roe, debt_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (stock_code, report_date, revenue, net_profit, total_assets, roe, debt_ratio))
        except Exception as e:
            logger.error(f"Profit store error {stock_code}: {e}")
    conn.commit()
    conn.close()

def store_balance(stock_code, df):
    if df is None or len(df) == 0:
        return
    conn = get_db()
    cursor = conn.cursor()
    for idx, row in df.head(4).iterrows():
        try:
            report_date = str(row.get('报告日', ''))
            if not report_date:
                continue
            total_assets = float(row.get('资产总计', 0) or 0)
            total_liabilities = float(row.get('负债合计', 0) or 0)
            total_equity = float(row.get('所有者权益合计', 0) or row.get('股东权益合计', 0) or 0)
            cursor.execute("""
                UPDATE stock_financial 
                SET total_assets = %s, total_liabilities = %s, total_equity = %s
                WHERE stock_code = %s AND report_date = %s
            """, (total_assets, total_liabilities, total_equity, stock_code, report_date))
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT IGNORE INTO stock_financial 
                    (stock_code, report_date, total_assets, total_liabilities, total_equity)
                    VALUES (%s, %s, %s, %s, %s)
                """, (stock_code, report_date, total_assets, total_liabilities, total_equity))
        except Exception as e:
            logger.error(f"Balance store error {stock_code}: {e}")
    conn.commit()
    conn.close()

def fetch_one_stock(stock_code):
    try:
        import akshare as ak
        
        market_code = get_market_prefix(stock_code)
        logger.info(f"Fetching {stock_code} ({market_code})")
        
        try:
            df = ak.stock_financial_report_sina(stock=market_code, symbol="利润表")
            store_profit(stock_code, df)
        except Exception as e:
            logger.error(f"Profit error {stock_code}: {e}")
        
        try:
            df = ak.stock_financial_report_sina(stock=market_code, symbol="资产负债表")
            store_balance(stock_code, df)
        except Exception as e:
            logger.error(f"Balance error {stock_code}: {e}")
        
        try:
            df = ak.stock_financial_report_sina(stock=market_code, symbol="现金流量表")
            if df is not None and len(df) > 0:
                for idx, row in df.head(2).iterrows():
                    report_date = str(row.get('报告日', ''))
                    operating_cf = float(row.get('经营活动产生的现金流量净额', 0) or 0)
                    logger.info(f"Cash flow {stock_code} {report_date}: {operating_cf}")
        except Exception as e:
            logger.error(f"Cash flow error {stock_code}: {e}")
        
        try:
            df = ak.stock_financial_abstract(symbol=stock_code)
            if df is not None and len(df) > 0:
                logger.info(f"Abstract {stock_code}: {len(df)} indicators")
        except Exception as e:
            logger.error(f"Abstract error {stock_code}: {e}")
        
        logger.info(f"✅ {stock_code} completed")
        time.sleep(1)
        
    except Exception as e:
        logger.error(f"Fetch error {stock_code}: {e}")

def main():
    logger.info("=== Starting financial data fetch ===")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM stock_basic LIMIT 20")
    stocks = cursor.fetchall()
    conn.close()
    
    logger.info(f"Processing {len(stocks)} stocks (test mode)")
    success = 0
    failed = 0
    for (code,) in stocks:
        try:
            fetch_one_stock(code)
            success += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed {code}: {e}")
    
    logger.info(f"=== Completed: {success} success, {failed} failed ===")

if __name__ == '__main__':
    main()
