#!/usr/bin/env python3.12
"""Configuration for the Compass data pipeline."""

# Database
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "password"
DB_DATABASE = "stock_analysis_system"

# Data source constants
API_SINA = 0       # ak.stock_zh_a_daily (Sina)
API_EASTMONEY = 1  # ak.stock_zh_a_hist (blocked)

# Default date range
START_DATE = "20240101"

# Rate limiting
INIT_SLEEP = 0.3   # seconds between stocks during init
DAILY_SLEEP = 0.1  # seconds between stocks during daily update

# Retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds, exponential backoff base

# Logging
LOG_FILE = "/var/log/d8q/datapipeline.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# Analysis
MIN_INDICATOR_ROWS = 30  # minimum indicators_daily rows before analysis

# Daemon mode
DAILY_SCHEDULE_HOUR = 16
DAILY_SCHEDULE_MINUTE = 30
