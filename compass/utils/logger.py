"""日志配置 — 输出到 /var/log/d8q/compass*.log"""
import logging
import os
from logging.handlers import RotatingFileHandler

from compass.config import get_config


def setup_logging():
    cfg = get_config()

    log_dir = cfg.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s"
    )

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "compass.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Access log
    access_handler = RotatingFileHandler(
        os.path.join(log_dir, "compass-access.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    access_handler.setFormatter(fmt)
    access_logger = logging.getLogger("compass.access")
    access_logger.addHandler(access_handler)
    access_logger.propagate = False

    logging.getLogger("compass").info("Logging initialized, dir=%s, level=%s", log_dir, cfg.LOG_LEVEL)
