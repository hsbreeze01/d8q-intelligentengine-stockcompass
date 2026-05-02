#!/usr/bin/env python3.12
import sys
import os

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
os.chdir('/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

import logging
import pymysql
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('fetch_valuation')

def get_db():
    return pymysql.connect(host='localhost', user='root', password='password', database='stock_analysis_system')

def create_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_valuation_daily (
            id INT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20) NOT NULL,
            pe_ttm FLOAT,
            pb FLOAT,
            roe FLOAT,
            total_market_cap BIGINT,
            circulating_market_cap BIGINT,
            price FLOAT,
            update_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_stock_date (stock_code, update_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_valuation (
            id INT AUTO_INCREMENT PRIMARY KEY,
            market VARCHAR(20) NOT NULL,
            pe FLOAT,
            pb FLOAT,
            update_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_market_date (market, update_date)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Tables ready")

def fetch_market_pe():
    try:
        import akshare as ak
        
        logger.info("Fetching A-share market PE...")
        df = ak.stock_market_pe_lg()
        
        if df is None or len(df) == 0:
            logger.error("No market PE fetched")
            return
        
        logger.info(f"Got PE data: {len(df)} rows")
        
        conn = get_db()
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            try:
                date = str(row.get('日期', ''))
                pe = float(row.get('平均市盈率', 0) or 0)
                
                cursor.execute("""
                    INSERT IGNORE INTO market_valuation 
                    (market, avg_pe, update_date)
                    VALUES (%s, %s, %s)
                """, ('000300.XSHG', pe, date))
            except Exception as e:
                pass
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Market PE stored")
        
    except Exception as e:
        logger.error(f"Market PE error: {e}")

def fetch_market_pb():
    try:
        import akshare as ak
        
        logger.info("Fetching A-share market PB...")
        df = ak.stock_market_pb_lg()
        
        if df is None or len(df) == 0:
            logger.error("No market PB fetched")
            return
        
        logger.info(f"Got PB data: {len(df)} rows")
        
        conn = get_db()
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            try:
                date = str(row.get('日期', ''))
                pb = float(row.get('平均市净率', 0) or 0)
                
                cursor.execute("""
                    INSERT IGNORE INTO market_valuation 
                    (market, avg_pb, update_date)
                    VALUES (%s, %s, %s)
                """, ('000300.XSHG', pb, date))
            except Exception as e:
                pass
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Market PB stored")
        
    except Exception as e:
        logger.error(f"Market PB error: {e}")

def fetch_individual_batch():
    try:
        import akshare as ak
        
        logger.info("Fetching A-share spot data...")
        
        for retry in range(3):
            try:
                df = ak.stock_zh_a_spot_em()
                break
            except Exception as e:
                logger.warning(f"Retry {retry+1}/3: {e}")
                time.sleep(10)
        else:
            logger.error("All retries failed")
            return
        
        if df is None or len(df) == 0:
            logger.error("No spot data fetched")
            return
        
        logger.info(f"Got {len(df)} stocks")
        
        conn = get_db()
        cursor = conn.cursor()
        
        success = 0
        batch_size = 200
        
        for start in range(0, len(df), batch_size):
            end = min(start + batch_size, len(df))
            df_batch = df.iloc[start:end]
            
            for _, row in df_batch.iterrows():
                try:
                    stock_code = str(row.get('代码', '')).zfill(6)
                    if not stock_code:
                        continue
                    
                    cursor.execute("""
                        INSERT IGNORE INTO stock_valuation_daily 
                        (stock_code, pe_ttm, pb, total_market_cap, circulating_market_cap, price, update_date)
                        VALUES (%s, %s, %s, %s, %s, %s, CURDATE())
                    """, (
                        stock_code,
                        float(row.get('市盈率-动态', 0) or 0),
                        float(row.get('市净率', 0) or 0),
                        float(row.get('总市值', 0) or 0),
                        float(row.get('流通市值', 0) or 0),
                        float(row.get('最新价', 0) or 0)
                    ))
                    
                    success += 1
                    
                except Exception as e:
                    pass
            
            conn.commit()
            logger.info(f"Stored {success} records...")
            time.sleep(15)
        
        conn.close()
        logger.info(f"✅ Individual valuation stored: {success}")
        
    except Exception as e:
        logger.error(f"Individual fetch error: {e}")

def main():
    logger.info("=== Starting valuation data fetch ===")
    create_table()
    
    fetch_market_pe()
    fetch_market_pb()
    
    logger.info("=== Valuation fetch completed ===")

if __name__ == '__main__':
    main()