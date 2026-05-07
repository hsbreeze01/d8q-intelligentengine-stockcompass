#!/usr/bin/env python3
"""Create daily_recommendation table for daily stock recommendation feature."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('create_daily_recommendation_table')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

DDL = """
CREATE TABLE IF NOT EXISTS daily_recommendation (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code      CHAR(10)       NOT NULL,
    stock_name      VARCHAR(32)    NOT NULL,
    recommendation_date DATE       NOT NULL,
    total_score     DECIMAL(5,2)   NOT NULL COMMENT '综合评分 0-100',
    technical_score DECIMAL(5,2)   NOT NULL COMMENT '技术指标评分',
    trend_score     DECIMAL(5,2)   NOT NULL COMMENT '趋势动量评分',
    fundamental_score DECIMAL(5,2) NOT NULL COMMENT '基本面评分',
    volume_score    DECIMAL(5,2)   NOT NULL COMMENT '量价配合评分',
    rank            INT            NOT NULL COMMENT '当日排名',
    reason          TEXT           NOT NULL COMMENT '推荐理由',
    risk_warning    TEXT           NOT NULL COMMENT '风险提示',
    generated_at    DATETIME       NOT NULL,
    UNIQUE KEY uk_stock_date (stock_code, recommendation_date),
    KEY idx_date_score (recommendation_date, total_score DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def main():
    logger.info("=== Creating daily_recommendation table ===")
    from compass.data.database import Database

    with Database() as db:
        db.execute(DDL)
        logger.info("✅ daily_recommendation table created successfully")


if __name__ == '__main__':
    main()
