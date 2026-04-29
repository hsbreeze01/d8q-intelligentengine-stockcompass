"""StockCompass 配置模块 — 遵循 D8Q 生态环境变量规范"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置类"""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY") or "stockcompass-secret-change-in-production"
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

    # MySQL
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "127.0.0.1"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT") or 3306)
    MYSQL_USER = os.environ.get("MYSQL_USER") or "root"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or ""
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "stock_analysis_system"

    # DB Pool
    DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN") or 5)
    DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX") or 20)

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL") or "INFO"
    LOG_DIR = os.environ.get("LOG_DIR") or "/var/log/d8q"

    # Schedule
    SCHEDULE_HOUR = int(os.environ.get("SCHEDULE_HOUR") or 17)
    SCHEDULE_MINUTE = int(os.environ.get("SCHEDULE_MINUTE") or 0)

    # LLM
    DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY") or ""
    DOUBAO_BASE_URL = os.environ.get("DOUBAO_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL_ID = os.environ.get("DOUBAO_MODEL_ID") or ""

    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or ""
    DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    DEEPSEEK_MODEL_ID = os.environ.get("DEEPSEEK_MODEL_ID") or "deepseek-reasoner"

    # WeChat
    WX_APPID = os.environ.get("WX_APPID") or ""
    WX_SECRET = os.environ.get("WX_SECRET") or ""

    # API
    API_PREFIX = "/api"

    # Session
    SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME") or 86400)

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS") or "*"


class DevelopmentConfig(Config):
    DEBUG = True
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "stock"


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    MYSQL_DATABASE = "test_stock_analysis_system"


_config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str = None) -> Config:
    """获取配置对象"""
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return _config_map.get(env, _config_map["default"])()
