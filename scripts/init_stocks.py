#!/usr/bin/env python3.12
"""Initialize stock_basic table with A-share stock list."""
import sys
import os

# Add project to path
sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
os.chdir('/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

import logging
import pymysql

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('init_stocks')

def main():
    logger.info("=== Initializing stock_basic table ===")
    
    try:
        import akshare as ak
        logger.info("Fetching A-share stock list from akshare...")
        df = ak.stock_info_a_code_name()
        logger.info(f"Got {len(df)} stocks")
        
        conn = pymysql.connect(host='localhost', user='root', password='password', database='stock_analysis_system')
        cursor = conn.cursor()
        
        count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute(
                    "INSERT IGNORE INTO stock_basic (code, name, industry, market) VALUES (%s, %s, %s, %s)",
                    (row.get('code', ''), row.get('name', ''), row.get('industry', ''), row.get('market', '')))
                count += 1
                if count % 100 == 0:
                    logger.info(f"Inserted {count} stocks...")
            except Exception as e:
                logger.error(f"Error inserting {row.get('code', '?')}: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Inserted {count} stocks into stock_basic")
        
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == '__main__':
    main()
